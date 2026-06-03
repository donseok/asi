"""스크리너 순수 로직 — 목적 프리셋 레지스트리 + apply_screen().

설계 §4.2:
- 모든 프리셋에 공통 필터(시장·유동성·이름검색)를 먼저 적용한다.
- 그 다음 프리셋별 추가 필터를 적용하고, 정렬 키 내림차순으로 정렬한다.
- 정렬 키가 NaN인 행은 제외하고 상위 N개만 반환한다.
- 입력 DataFrame은 변형하지 않는다(비파괴).
- 네트워크/Streamlit 호출 없음. 합성 DataFrame으로 테스트 가능한 순수 함수.
"""
from __future__ import annotations

import pandas as pd

import config

# 시장 토글 표기(UI) → 스냅샷의 market 값 매핑
_MARKET_MAP = {"코스피": "KOSPI", "코스닥": "KOSDAQ"}


def _value_quality_avg(df: pd.DataFrame) -> pd.Series:
    """저평가 우량주 정렬 키: (value_score + quality_score) / 2."""
    return df[["value_score", "quality_score"]].mean(axis=1)


def _filter_value(df: pd.DataFrame) -> pd.Series:
    """저평가 우량주 추가 필터: PER>0 & PBR>0 (적자/무효 제외)."""
    return (df["PER"] > 0) & (df["PBR"] > 0)


def _filter_income(df: pd.DataFrame) -> pd.Series:
    """배당 프리셋 추가 필터: DIV>0 (배당 있는 종목만)."""
    return df["DIV"] > 0


def _filter_stable_cap(df: pd.DataFrame) -> pd.Series:
    """안정적 대형주 추가 필터: 공통 필터 후 집합에서 시총 STABLE_CAP_PERCENTILE 백분위 이상.

    자격 종목 중 시총 상위 ~20%(기본 80번째 백분위)만 남긴다.
    빈 집합/단일 종목은 quantile이 NaN/단일값이 되므로 안전하게 처리.
    """
    cap = df["시가총액"]
    if cap.dropna().empty:
        return pd.Series(False, index=df.index)
    threshold = cap.quantile(config.STABLE_CAP_PERCENTILE / 100.0)
    return cap >= threshold


def _no_filter(df: pd.DataFrame) -> pd.Series:
    """종합 추천: 추가 필터 없음(모두 통과)."""
    return pd.Series(True, index=df.index)


# 프리셋 레지스트리.
# extra_filter: (df) -> bool Series  /  sort_key: (df) -> 정렬용 Series (내림차순)
PRESETS: dict[str, dict] = {
    "value": {
        "emoji": "💎",
        "label": "저평가 우량주",
        "desc": "싸면서 돈 잘 버는 회사",
        "guide": "낮은 가격에 좋은 회사를 사고 싶다면",
        "extra_filter": _filter_value,
        "sort_key": _value_quality_avg,
    },
    "income": {
        "emoji": "💰",
        "label": "배당 잘 주는 주식",
        "desc": "배당수익률이 높은 회사",
        "guide": "꾸준한 현금흐름을 원한다면",
        "extra_filter": _filter_income,
        "sort_key": lambda df: df["income_score"],
    },
    "stable": {
        "emoji": "🛡️",
        "label": "안정적인 대형주",
        "desc": "덩치 큰 회사(시가총액 상위)",
        "guide": "흔들림이 덜한 큰 회사를 원한다면 (※ 덩치 기준, 변동성 미반영)",
        "extra_filter": _filter_stable_cap,
        "sort_key": lambda df: df["시가총액"],
    },
    "comprehensive": {
        "emoji": "⭐",
        "label": "종합 추천",
        "desc": "가치+품질+배당 종합 점수 상위",
        "guide": "뭘 골라야 할지 모르겠다면",
        "extra_filter": _no_filter,
        "sort_key": lambda df: df["score"],
    },
}


def _apply_common_filters(
    df: pd.DataFrame,
    *,
    market: str,
    query: str,
    min_cap: float,
    min_value: float,
) -> pd.DataFrame:
    """공통 필터: 시장 → 유동성(시총·거래대금) → 이름검색.

    스펙 §8: 거래대금은 '당일값'(스냅샷 컬럼) 기준이다.
    """
    mask = pd.Series(True, index=df.index)

    # 시장 토글(전체면 통과)
    krx_market = _MARKET_MAP.get(market)
    if krx_market is not None:
        mask &= df["market"] == krx_market

    # 유동성 하한(NaN은 미충족으로 간주 → False)
    mask &= df["시가총액"].fillna(-1) >= min_cap
    mask &= df["거래대금"].fillna(-1) >= min_value

    # 이름검색(부분 일치, 공백 제거). 빈 문자열이면 전체 통과.
    q = (query or "").strip()
    if q:
        mask &= df["name"].astype(str).str.contains(q, regex=False, na=False)

    return df[mask]


def apply_screen(
    scored_df: pd.DataFrame,
    preset_key: str,
    *,
    market: str = "전체",
    query: str = "",
    limit: int = config.SCREENER_DEFAULT_LIMIT,
    min_cap: float = config.MIN_MARKET_CAP,
    min_value: float = config.MIN_AVG_TRADING_VALUE,
) -> pd.DataFrame:
    """프리셋 조건으로 스크리닝한 결과를 반환.

    처리 순서(스펙 §4.2):
      1) 공통 필터(시장·유동성·이름검색)
      2) 프리셋 추가 필터
      3) 정렬 키 내림차순 정렬 + 정렬 키 NaN 행 제외
      4) 상위 limit개

    입력은 변형하지 않는다(비파괴). 빈 결과는 0행 DataFrame으로 반환.
    """
    if preset_key not in PRESETS:
        raise KeyError(f"알 수 없는 프리셋 키: {preset_key}")
    preset = PRESETS[preset_key]

    # 비파괴: 원본을 복사한 뒤에만 다룬다.
    df = scored_df.copy()

    # 1) 공통 필터
    df = _apply_common_filters(
        df, market=market, query=query, min_cap=min_cap, min_value=min_value
    )

    # 2) 프리셋 추가 필터 (공통 필터 후 집합 기준 — 안정대형주 백분위 포함)
    if not df.empty:
        df = df[preset["extra_filter"](df)]

    if df.empty:
        return df.reset_index(drop=True)

    # 3) 정렬 키 계산 → NaN 제외 → 내림차순
    sort_values = preset["sort_key"](df)
    df = df.assign(_sort_key=sort_values)
    df = df[df["_sort_key"].notna()]
    df = df.sort_values("_sort_key", ascending=False, kind="mergesort")
    df = df.drop(columns="_sort_key")

    # 4) 상위 limit개
    df = df.head(limit)
    return df.reset_index(drop=True)
