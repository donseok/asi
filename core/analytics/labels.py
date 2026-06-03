"""결정론적 라벨/뱃지/설명/평가 문구 (순수 함수, 외부 의존 없음).

입력 `row`는 스냅샷 1행(dict 또는 pandas Series). 컬럼:
PER, PBR, EPS, BPS, DIV, DPS, ROE_approx, value_score, quality_score,
income_score, score, 종가, 시가총액.

모든 임계값/상수는 config에서 가져온다(단일 진실원천).
숫자 결측(None/NaN)은 안전하게 건너뛴다 — UI가 깨지지 않게.
"""
from __future__ import annotations

import math
from typing import Any

import config


def _get(row: Any, key: str) -> float | None:
    """row(dict/Series)에서 숫자값을 안전하게 꺼낸다. 결측/비숫자는 None."""
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        try:
            val = row.get(key)  # dict.get / Series.get
        except AttributeError:
            return None
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def badges(row: Any) -> list[str]:
    """행별 색 뱃지 목록(프리셋과 무관). 임계 config.BADGE_PERCENTILE.

    - 저평가  ← value_score   >= 임계
    - 우량    ← quality_score >= 임계
    - 고배당  ← income_score  >= 임계  AND  DIV > 0
    0~3개. 없으면 빈 리스트.
    """
    th = config.BADGE_PERCENTILE
    out: list[str] = []
    vs = _get(row, "value_score")
    qs = _get(row, "quality_score")
    isc = _get(row, "income_score")
    div = _get(row, "DIV")
    if vs is not None and vs >= th:
        out.append("저평가")
    if qs is not None and qs >= th:
        out.append("우량")
    if isc is not None and isc >= th and div is not None and div > 0:
        out.append("고배당")
    return out


def score_tier(score: float | None) -> str:
    """종합점수 색 등급: >=75 good · 50~74 warn · <50 muted. 결측은 muted."""
    if score is None:
        return "muted"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "muted"
    if math.isnan(s):
        return "muted"
    if s >= 75:
        return "good"
    if s >= 50:
        return "warn"
    return "muted"


def _tier3(score: float | None, labels3: tuple[str, str, str]) -> tuple[str, str]:
    """>=70 → (labels3[0], good) · 40~69 → (labels3[1], warn) · <40 → (labels3[2], muted).
    결측이면 ("정보 없음", muted).
    """
    if score is None:
        return ("정보 없음", "muted")
    if score >= 70:
        return (labels3[0], "good")
    if score >= 40:
        return (labels3[1], "warn")
    return (labels3[2], "muted")


def verdict_value(row: Any) -> tuple[str, str]:
    """가치 평가: (라벨, 톤). value_score 기준."""
    return _tier3(_get(row, "value_score"), ("저평가", "보통", "비싼 편"))


def verdict_quality(row: Any) -> tuple[str, str]:
    """수익성 평가: (라벨, 톤). quality_score 기준."""
    return _tier3(_get(row, "quality_score"), ("우량", "보통", "수익성 낮음"))


def verdict_income(row: Any) -> tuple[str, str]:
    """배당 평가: (라벨, 톤). DIV가 없거나 0이면 income_score와 무관하게 "배당 적음"."""
    div = _get(row, "DIV")
    if div is None or div <= 0:
        return ("배당 적음", "muted")
    return _tier3(_get(row, "income_score"), ("고배당", "보통", "보통"))


def explain_row(row: Any) -> str:
    """"왜 추천?" 결정론적 한 줄(§4.3).

    각 후보 문구는 (서브스코어 >= EXPLAIN_MIN_SUBSCORE) AND (근거 숫자 유효)일 때만 후보.
    서브스코어가 높은 순으로 상위 2개를 ', '로 연결.
    유효 후보가 없으면 "종합점수 기준 상위 후보".
    """
    th = config.EXPLAIN_MIN_SUBSCORE
    per = _get(row, "PER")
    pbr = _get(row, "PBR")
    roe = _get(row, "ROE_approx")
    div = _get(row, "DIV")
    vs = _get(row, "value_score")
    qs = _get(row, "quality_score")
    isc = _get(row, "income_score")

    candidates: list[tuple[float, str]] = []
    # 가치: value_score >= th AND PER>0 AND PBR>0
    if vs is not None and vs >= th and per is not None and per > 0 and pbr is not None and pbr > 0:
        candidates.append((vs, f"PER {per:.1f}배·PBR {pbr:.1f}배로 저렴"))
    # 수익성: quality_score >= th AND ROE 유효
    if qs is not None and qs >= th and roe is not None:
        candidates.append((qs, f"ROE(근사) {roe:.0f}%로 수익성 양호"))
    # 배당: income_score >= th AND DIV>0
    if isc is not None and isc >= th and div is not None and div > 0:
        candidates.append((isc, f"배당수익률 {div:.1f}%로 배당 넉넉"))

    if not candidates:
        return "종합점수 기준 상위 후보"
    candidates.sort(key=lambda x: x[0], reverse=True)
    return ", ".join(text for _, text in candidates[:2])


def value_badge(row: Any) -> str | None:
    """직관 배지(§5.7): value_score(가치 백분위) 기준 한 줄. 결측이면 None.

    >=66 → 싼 편 · 34~65 → 평균 수준 · <34 → 비싼 편 (백분위 3분할).
    """
    vs = _get(row, "value_score")
    if vs is None:
        return None
    if vs >= 66:
        return "시장 평균보다 싼 편"
    if vs >= 34:
        return "시장 평균 수준"
    return "시장 평균보다 비싼 편"


def dividend_won(row: Any, principal: int = config.DIVIDEND_PRINCIPAL) -> int:
    """기준금액(principal) 투자 시 연 배당액(원) 환산(§5.7).

    DIV는 배당수익률(%) → principal × DIV / 100. 정수 원 단위로 반올림.
    DIV 없음/0/음수면 0.
    """
    div = _get(row, "DIV")
    if div is None or div <= 0:
        return 0
    return int(round(principal * div / 100.0))


def earnings_yield(row: Any) -> str:
    """이익수익률(1/PER, §5.7). PER<=0이면 "적자", PER 결측이면 "정보 없음".

    표기는 백분율 문자열(예: "10.0%").
    """
    per = _get(row, "PER")
    if per is None:
        return "정보 없음"
    if per <= 0:
        return "적자"
    return f"{100.0 / per:.1f}%"


def indicator_plain(latest_signals: dict | None) -> str:
    """RSI·MACD 말풀이 + 과매수/과매도 주의 캡션(§5.7).

    주의 캡션은 RSI>=70(과매수) 또는 RSI<=30(과매도)일 때만 붙인다.
    그 외 구간은 사실 설명만(주의 없음).
    """
    if not latest_signals:
        return "지표 데이터가 없습니다."

    parts: list[str] = []
    rsi_val = latest_signals.get("rsi")
    rsi_f: float | None
    try:
        rsi_f = float(rsi_val) if rsi_val is not None else None
        if rsi_f is not None and math.isnan(rsi_f):
            rsi_f = None
    except (TypeError, ValueError):
        rsi_f = None

    if rsi_f is not None:
        if rsi_f >= 70:
            parts.append(f"RSI {rsi_f:.0f} — 과매수 구간, 단기 과열 주의")
        elif rsi_f <= 30:
            parts.append(f"RSI {rsi_f:.0f} — 과매도 구간, 단기 낙폭 주의")
        else:
            parts.append(f"RSI {rsi_f:.0f} — 중립 구간")

    hist = latest_signals.get("macd_hist")
    try:
        hist_f = float(hist) if hist is not None else None
        if hist_f is not None and math.isnan(hist_f):
            hist_f = None
    except (TypeError, ValueError):
        hist_f = None
    if hist_f is not None:
        if hist_f > 0:
            parts.append("MACD 상승 모멘텀")
        elif hist_f < 0:
            parts.append("MACD 하락 모멘텀")
        else:
            parts.append("MACD 모멘텀 중립")

    if not parts:
        return "지표 데이터가 없습니다."
    return " · ".join(parts)


def signal_text(latest_signals: dict | None, ma_alignment: str | None = None) -> str:
    """차트 위 "신호 한 줄"(§5.5). 추세(ma_alignment) → 20일선 위치 → RSI → MACD.

    각 항목은 데이터가 있을 때만 포함한다. 모두 없으면 안내 문구.
    """
    parts: list[str] = []
    if ma_alignment:
        parts.append(str(ma_alignment))

    sig = latest_signals or {}

    above20 = sig.get("above_sma20")
    if above20 is True:
        parts.append("20일선 위")
    elif above20 is False:
        parts.append("20일선 아래")

    rsi_val = sig.get("rsi")
    try:
        rsi_f = float(rsi_val) if rsi_val is not None else None
        if rsi_f is not None and math.isnan(rsi_f):
            rsi_f = None
    except (TypeError, ValueError):
        rsi_f = None
    if rsi_f is not None:
        state = sig.get("rsi_state")
        if state == "중립" or state is None:
            parts.append(f"RSI {rsi_f:.0f}(중립)")
        elif "과매수" in str(state):
            parts.append(f"RSI {rsi_f:.0f}(과매수)")
        elif "과매도" in str(state):
            parts.append(f"RSI {rsi_f:.0f}(과매도)")
        else:
            parts.append(f"RSI {rsi_f:.0f}")

    hist = sig.get("macd_hist")
    try:
        hist_f = float(hist) if hist is not None else None
        if hist_f is not None and math.isnan(hist_f):
            hist_f = None
    except (TypeError, ValueError):
        hist_f = None
    if hist_f is not None:
        if hist_f > 0:
            parts.append("MACD 상승")
        elif hist_f < 0:
            parts.append("MACD 하락")
        else:
            parts.append("MACD 보합")

    if not parts:
        return "신호 데이터가 없습니다."
    return " · ".join(parts)


# --- 정적 용어 사전(§5.7 용어 ⓘ 툴팁) ---
GLOSSARY: dict[str, str] = {
    "PER": "주가수익비율 — 주가가 주당순이익(EPS)의 몇 배인지. 낮을수록 이익 대비 저렴.",
    "PBR": "주가순자산비율 — 주가가 주당순자산(BPS)의 몇 배인지. 낮을수록 자산 대비 저렴.",
    "ROE_approx": "자기자본이익률(근사, EPS÷BPS) — 자본으로 얼마나 버는지. 높을수록 수익성 양호.",
    "DIV": "배당수익률(%) — 주가 대비 1년 배당금 비율. 높을수록 현금 환원이 큼.",
    "시가총액": "주가 × 발행주식수 — 회사의 시장가치(덩치). 클수록 대형주.",
    "EPS": "주당순이익 — 1주가 1년간 벌어들인 순이익.",
    "BPS": "주당순자산 — 1주에 해당하는 회사 순자산(자본).",
    "DPS": "주당배당금 — 1주당 지급되는 연 배당금(원).",
    "RSI": "상대강도지수(0~100) — 70 이상이면 과매수, 30 이하면 과매도로 본다.",
    "이동평균": "최근 일정 기간 종가의 평균선 — 추세 방향을 가늠하는 기준선.",
    "MACD": "단기·장기 이동평균의 차이 — 0선 위/아래와 시그널 교차로 모멘텀을 본다.",
}

# --- 정적 고지/캡션(§4.5 · §5.4 · §8 정직 원칙) ---
CAPTIONS: dict[str, str] = {
    "relative_rank": (
        "점수와 막대는 전체 종목 중 상대 순위(백분위)이며, 매수 신호가 아닙니다. "
        "🟢상위 · 🟠중간 · ⚪하위는 같은 시점 다른 종목 대비 위치입니다."
    ),
    "stable_cap_limit": (
        "‘안정적인 대형주’는 시가총액(덩치)만 기준입니다. "
        "주가 변동성·재무 안정성은 반영하지 않으므로 ‘덩치 큰 회사’ 정도로만 해석하세요."
    ),
    "negative_per": (
        "PER가 ‘−’로 비어 있으면 최근 적자라 PER 계산이 불가한 경우이며 오류가 아닙니다."
    ),
    "buy_signal_not": (
        "본 화면의 모든 지표는 판단 보조용 참고 자료이며 단독 투자 판단 근거가 될 수 없습니다. "
        "투자 권유가 아닙니다."
    ),
    "roe_approx": (
        "ROE는 EPS÷BPS 근사치입니다. 정확한 ROE(당기순이익÷자본총계)는 다음 단계에서 제공됩니다."
    ),
    "alert_unknown": (
        "관리종목·투자경고 ‘지정’ 여부는 아직 미확인이며, 다음 단계(시장경보)에서 추가될 예정입니다."
    ),
}
