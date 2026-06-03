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


# 정렬 옵션 레지스트리(자유 정렬). (컬럼, 오름차순여부, 양수만필요).
# UI selectbox가 이 키를 그대로 노출하고, apply_screen(sort_by=key)로 전달한다.
SORT_OPTIONS: dict[str, tuple] = {
    "종합점수 높은순": ("score", False, False),
    "시가총액 큰순": ("시가총액", False, False),
    "거래대금 많은순": ("거래대금", False, False),
    "당일 등락률 높은순": ("등락률", False, False),
    "당일 등락률 낮은순": ("등락률", True, False),
    "PER 낮은순": ("PER", True, True),
    "PBR 낮은순": ("PBR", True, True),
    "배당수익률 높은순": ("DIV", False, False),
}


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

    # 자유 검색(이름 부분일치 OR 6자리 코드 부분일치). 빈 문자열이면 전체 통과.
    q = (query or "").strip()
    if q:
        by_name = df["name"].astype(str).str.contains(q, regex=False, na=False)
        by_code = df["ticker"].astype(str).str.contains(q, regex=False, na=False)
        mask &= by_name | by_code

    return df[mask]


def _apply_range_filters(
    df: pd.DataFrame,
    *,
    max_cap: float | None,
    change_min: float | None,
    change_max: float | None,
    max_per: float | None,
    max_pbr: float | None,
) -> pd.DataFrame:
    """자유 범위 필터(선택). 값이 None이면 해당 조건은 통과(미적용).

    - max_cap: 시가총액 상한(원)
    - change_min/change_max: 당일 등락률(%) 하/상한
    - max_per/max_pbr: PER/PBR 상한(밸류에이션 enrich 시에만 의미). 0 이하(적자)는 제외.
    """
    mask = pd.Series(True, index=df.index)
    if max_cap is not None and "시가총액" in df.columns:
        mask &= df["시가총액"].fillna(float("inf")) <= max_cap
    if "등락률" in df.columns:
        if change_min is not None:
            mask &= df["등락률"].fillna(-9999) >= change_min
        if change_max is not None:
            mask &= df["등락률"].fillna(9999) <= change_max
    if max_per is not None and "PER" in df.columns:
        mask &= (df["PER"] > 0) & (df["PER"] <= max_per)
    if max_pbr is not None and "PBR" in df.columns:
        mask &= (df["PBR"] > 0) & (df["PBR"] <= max_pbr)
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
    max_cap: float | None = None,
    change_min: float | None = None,
    change_max: float | None = None,
    max_per: float | None = None,
    max_pbr: float | None = None,
    sort_by: str | None = None,
) -> pd.DataFrame:
    """프리셋 + 자유 필터/정렬로 스크리닝한 결과를 반환.

    처리 순서:
      1) 공통 필터(시장·유동성·자유검색[이름 OR 코드])
      2) 프리셋 추가 필터
      3) 자유 범위 필터(시총상한·등락률·PER/PBR 상한 — 값 있으면)
      4) 정렬: sort_by(SORT_OPTIONS) 지정 시 그것으로, 아니면 프리셋 sort_key
      5) 정렬 키 NaN 제외 + 상위 limit개

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

    # 3) 자유 범위 필터(선택)
    if not df.empty:
        df = _apply_range_filters(
            df, max_cap=max_cap, change_min=change_min, change_max=change_max,
            max_per=max_per, max_pbr=max_pbr,
        )

    if df.empty:
        return df.reset_index(drop=True)

    # 4) 정렬: 자유 정렬(sort_by) 우선, 없으면 프리셋 기본 정렬
    if sort_by and sort_by in SORT_OPTIONS:
        col, ascending, positive_only = SORT_OPTIONS[sort_by]
        if col not in df.columns:
            return df.head(0).reset_index(drop=True)
        sort_values = df[col]
        if positive_only:
            sort_values = sort_values.where(sort_values > 0)
    else:
        sort_values, ascending = preset["sort_key"](df), False

    # 정렬 키가 전부 NaN이면(예: 무키 모드의 score 기반 프리셋) 시가총액으로 폴백 —
    # 자유 검색/필터 결과가 통째로 사라지지 않도록 한다.
    if hasattr(sort_values, "notna") and sort_values.notna().sum() == 0 \
            and "시가총액" in df.columns:
        sort_values, ascending = df["시가총액"], False

    # 5) 정렬 키 NaN 제외 → 정렬 → 상위 limit개
    df = df.assign(_sort_key=sort_values)
    df = df[df["_sort_key"].notna()]
    df = df.sort_values("_sort_key", ascending=ascending, kind="mergesort")
    df = df.drop(columns="_sort_key")
    df = df.head(limit)
    return df.reset_index(drop=True)
