"""labels.py 순수 함수 단위 테스트 (합성 입력 주입, 네트워크/Streamlit 없음)."""
from __future__ import annotations

import pandas as pd

import config
from core.analytics import labels


# ── badges ───────────────────────────────────────────────────────────
def test_badges_all_three_when_subscores_high():
    """세 서브스코어가 모두 임계 이상이고 DIV>0이면 뱃지 3개."""
    row = {
        "value_score": 80.0,
        "quality_score": 75.0,
        "income_score": 90.0,
        "DIV": 3.2,
    }
    assert labels.badges(row) == ["저평가", "우량", "고배당"]


def test_badges_boundary_70_included_69_excluded():
    """경계: 70은 포함, 69는 제외(BADGE_PERCENTILE=70)."""
    assert config.BADGE_PERCENTILE == 70
    row_70 = {"value_score": 70.0, "quality_score": 70.0, "income_score": 70.0, "DIV": 1.0}
    assert labels.badges(row_70) == ["저평가", "우량", "고배당"]
    row_69 = {"value_score": 69.0, "quality_score": 69.0, "income_score": 69.0, "DIV": 1.0}
    assert labels.badges(row_69) == []


def test_badges_high_income_but_no_dividend_excluded():
    """income_score는 높지만 DIV<=0이면 고배당 뱃지 제외."""
    row = {"value_score": 10.0, "quality_score": 10.0, "income_score": 95.0, "DIV": 0.0}
    assert labels.badges(row) == []


def test_badges_nan_subscores_yield_empty():
    """서브스코어가 NaN이면 해당 뱃지 없음(깨지지 않음)."""
    row = {"value_score": float("nan"), "quality_score": float("nan"),
           "income_score": float("nan"), "DIV": float("nan")}
    assert labels.badges(row) == []


def test_badges_accepts_series():
    """pandas Series 입력도 dict와 동일하게 동작."""
    row = pd.Series({"value_score": 72.0, "quality_score": 10.0,
                     "income_score": 10.0, "DIV": 0.0})
    assert labels.badges(row) == ["저평가"]


# ── score_tier ───────────────────────────────────────────────────────
def test_score_tier_boundaries():
    """경계: >=75 good / 50~74 warn / <50 muted."""
    assert labels.score_tier(75) == "good"
    assert labels.score_tier(74.9) == "warn"
    assert labels.score_tier(50) == "warn"
    assert labels.score_tier(49.9) == "muted"
    assert labels.score_tier(0) == "muted"
    assert labels.score_tier(100) == "good"


def test_score_tier_none_or_nan_muted():
    """결측 점수는 muted로 폴백(UI 안전)."""
    assert labels.score_tier(None) == "muted"
    assert labels.score_tier(float("nan")) == "muted"


# ── verdict_* ────────────────────────────────────────────────────────
def test_verdict_value_mapping():
    """가치: >=70 저평가 / 40~69 보통 / <40 비싼 편."""
    assert labels.verdict_value({"value_score": 70.0}) == ("저평가", "good")
    assert labels.verdict_value({"value_score": 69.9}) == ("보통", "warn")
    assert labels.verdict_value({"value_score": 40.0}) == ("보통", "warn")
    assert labels.verdict_value({"value_score": 39.9}) == ("비싼 편", "muted")


def test_verdict_quality_mapping():
    """수익성: >=70 우량 / 40~69 보통 / <40 수익성 낮음."""
    assert labels.verdict_quality({"quality_score": 88.0}) == ("우량", "good")
    assert labels.verdict_quality({"quality_score": 55.0}) == ("보통", "warn")
    assert labels.verdict_quality({"quality_score": 12.0}) == ("수익성 낮음", "muted")


def test_verdict_income_mapping_and_no_dividend():
    """배당: >=70 고배당 / 40~69 보통 / DIV없음·0 배당 적음."""
    assert labels.verdict_income({"income_score": 80.0, "DIV": 4.0}) == ("고배당", "good")
    assert labels.verdict_income({"income_score": 50.0, "DIV": 1.0}) == ("보통", "warn")
    # DIV가 0이면 income_score와 무관하게 "배당 적음"
    assert labels.verdict_income({"income_score": 80.0, "DIV": 0.0}) == ("배당 적음", "muted")
    # DIV 결측도 "배당 적음"
    assert labels.verdict_income({"income_score": 80.0}) == ("배당 적음", "muted")


def test_verdict_none_score_muted():
    """서브스코어 결측 시 안전 폴백(보통/muted 계열로 깨지지 않음)."""
    assert labels.verdict_value({}) == ("정보 없음", "muted")
    assert labels.verdict_quality({}) == ("정보 없음", "muted")
    assert labels.verdict_income({}) == ("배당 적음", "muted")


# ── explain_row ──────────────────────────────────────────────────────
def test_explain_row_top2_by_subscore_descending():
    """서브스코어 높은 순 상위 2개를 ', '로 연결, 근거 숫자 포함."""
    row = {
        "value_score": 90.0, "quality_score": 80.0, "income_score": 65.0,
        "PER": 8.0, "PBR": 0.9, "ROE_approx": 15.0, "DIV": 3.0,
    }
    text = labels.explain_row(row)
    # value(90) > quality(80) > income(65) → 상위 2 = 가치, 수익성
    assert text == "PER 8.0배·PBR 0.9배로 저렴, ROE(근사) 15%로 수익성 양호"


def test_explain_row_boundary_60_included():
    """경계: 서브스코어 60(EXPLAIN_MIN_SUBSCORE)은 포함."""
    assert config.EXPLAIN_MIN_SUBSCORE == 60
    row = {
        "value_score": 60.0, "quality_score": 10.0, "income_score": 10.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    assert labels.explain_row(row) == "PER 12.0배·PBR 1.5배로 저렴"


def test_explain_row_fallback_when_all_below_60():
    """모든 서브스코어가 60 미만이면 fallback 문구."""
    row = {
        "value_score": 59.9, "quality_score": 30.0, "income_score": 10.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    assert labels.explain_row(row) == "종합점수 기준 상위 후보"


def test_explain_row_skips_when_underlying_number_invalid():
    """서브스코어는 높아도 근거 숫자가 무효면 해당 문구 제외."""
    # value_score 높지만 PER<=0(적자) → 가치 문구 제외, income으로 대체
    row = {
        "value_score": 90.0, "quality_score": 10.0, "income_score": 75.0,
        "PER": -3.0, "PBR": 0.8, "ROE_approx": 5.0, "DIV": 4.0,
    }
    assert labels.explain_row(row) == "배당수익률 4.0%로 배당 넉넉"


def test_explain_row_income_requires_positive_div():
    """배당 문구는 DIV>0일 때만."""
    row = {
        "value_score": 10.0, "quality_score": 10.0, "income_score": 95.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    # income_score 높지만 DIV=0 → 배당 문구 불가, 나머지도 60 미만 → fallback
    assert labels.explain_row(row) == "종합점수 기준 상위 후보"


# ── value_badge ──────────────────────────────────────────────────────
def test_value_badge_cheap_normal_expensive():
    """value_score 기준 직관 배지: 높음=싼 편 / 중간=평균 수준 / 낮음=비싼 편."""
    assert labels.value_badge({"value_score": 75.0}) == "시장 평균보다 싼 편"
    assert labels.value_badge({"value_score": 50.0}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 20.0}) == "시장 평균보다 비싼 편"


def test_value_badge_boundaries():
    """경계: >=66 싼 편 / 34~65 평균 수준 / <34 비싼 편."""
    assert labels.value_badge({"value_score": 66.0}) == "시장 평균보다 싼 편"
    assert labels.value_badge({"value_score": 65.9}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 34.0}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 33.9}) == "시장 평균보다 비싼 편"


def test_value_badge_none():
    """value_score 결측이면 None 반환(배지 숨김)."""
    assert labels.value_badge({}) is None
    assert labels.value_badge({"value_score": float("nan")}) is None


# ── dividend_won ─────────────────────────────────────────────────────
def test_dividend_won_from_div_rate():
    """DIV(배당수익률 %)로 기준금액당 연 배당액 환산: 100만원 × DIV%."""
    # DIV 3.0% → 100만원당 30,000원
    assert labels.dividend_won({"DIV": 3.0}) == 30000


def test_dividend_won_custom_principal():
    """principal 인자 적용."""
    assert labels.dividend_won({"DIV": 2.5}, principal=2_000_000) == 50000


def test_dividend_won_default_principal_from_config():
    """기본 principal은 config.DIVIDEND_PRINCIPAL(100만원)."""
    assert config.DIVIDEND_PRINCIPAL == 1_000_000
    assert labels.dividend_won({"DIV": 1.0}) == 10000


def test_dividend_won_zero_or_missing():
    """DIV 없음/0이면 0 반환(배당 없음)."""
    assert labels.dividend_won({"DIV": 0.0}) == 0
    assert labels.dividend_won({}) == 0
    assert labels.dividend_won({"DIV": float("nan")}) == 0


# ── earnings_yield ───────────────────────────────────────────────────
def test_earnings_yield_from_per():
    """이익수익률 = 1/PER × 100 (%). PER 10 → 10.0%."""
    assert labels.earnings_yield({"PER": 10.0}) == "10.0%"
    assert labels.earnings_yield({"PER": 8.0}) == "12.5%"


def test_earnings_yield_negative_or_zero_per():
    """PER<=0(적자)이면 '적자'."""
    assert labels.earnings_yield({"PER": 0.0}) == "적자"
    assert labels.earnings_yield({"PER": -5.0}) == "적자"


def test_earnings_yield_missing_per():
    """PER 결측이면 '적자' 아님 — 정보 없음 표기."""
    assert labels.earnings_yield({}) == "정보 없음"
    assert labels.earnings_yield({"PER": float("nan")}) == "정보 없음"


# ── indicator_plain ──────────────────────────────────────────────────
def test_indicator_plain_overbought_caption():
    """RSI>=70이면 과매수 주의 캡션 포함."""
    sig = {"rsi": 72.0, "macd_hist": 0.5, "rsi_state": "과매수(≥70)"}
    text = labels.indicator_plain(sig)
    assert "RSI 72" in text
    assert "과매수" in text
    assert "주의" in text


def test_indicator_plain_oversold_caption():
    """RSI<=30이면 과매도 주의 캡션 포함."""
    sig = {"rsi": 28.0, "macd_hist": -0.3, "rsi_state": "과매도(≤30)"}
    text = labels.indicator_plain(sig)
    assert "RSI 28" in text
    assert "과매도" in text
    assert "주의" in text


def test_indicator_plain_neutral_no_caution():
    """RSI 30~70(경계 70/30 제외 구간)에서는 주의 캡션 없음."""
    sig = {"rsi": 55.0, "macd_hist": 0.1, "rsi_state": "중립"}
    text = labels.indicator_plain(sig)
    assert "RSI 55" in text
    assert "주의" not in text


def test_indicator_plain_boundary_70_and_30():
    """경계: RSI 정확히 70/30은 주의 대상."""
    assert "주의" in labels.indicator_plain({"rsi": 70.0})
    assert "주의" in labels.indicator_plain({"rsi": 30.0})
    assert "주의" not in labels.indicator_plain({"rsi": 69.9})
    assert "주의" not in labels.indicator_plain({"rsi": 30.1})


def test_indicator_plain_macd_direction():
    """MACD 히스토그램 부호로 상승/하락 모멘텀 말풀이."""
    assert "상승" in labels.indicator_plain({"rsi": 50.0, "macd_hist": 0.4})
    assert "하락" in labels.indicator_plain({"rsi": 50.0, "macd_hist": -0.4})


def test_indicator_plain_empty():
    """빈 신호면 안내 문구(깨지지 않음)."""
    assert labels.indicator_plain({}) == "지표 데이터가 없습니다."
    assert labels.indicator_plain(None) == "지표 데이터가 없습니다."


# ── signal_text ──────────────────────────────────────────────────────
def test_signal_text_basic():
    """20일선 위/RSI/MACD를 한 줄로 요약."""
    sig = {
        "above_sma20": True, "rsi": 58.0, "rsi_state": "중립", "macd_hist": 0.2,
    }
    text = labels.signal_text(sig)
    assert "20일선 위" in text
    assert "RSI 58" in text
    assert "MACD 상승" in text


def test_signal_text_below_sma20():
    """20일선 아래 표기."""
    sig = {"above_sma20": False, "rsi": 45.0, "rsi_state": "중립", "macd_hist": -0.1}
    text = labels.signal_text(sig)
    assert "20일선 아래" in text
    assert "MACD 하락" in text


def test_signal_text_with_ma_alignment():
    """ma_alignment 인자가 주어지면 추세 한 줄로 보강(맨 앞)."""
    sig = {"above_sma20": True, "rsi": 60.0, "rsi_state": "중립", "macd_hist": 0.1}
    text = labels.signal_text(sig, ma_alignment="정배열")
    assert "정배열" in text
    assert "20일선 위" in text


def test_signal_text_none_and_empty():
    """빈 신호 / None 안전 처리."""
    assert labels.signal_text({}) == "신호 데이터가 없습니다."
    assert labels.signal_text(None) == "신호 데이터가 없습니다."
    # ma_alignment만 있고 신호 비었으면 추세만이라도 표기
    assert labels.signal_text(None, ma_alignment="역배열") == "역배열"


def test_signal_text_handles_missing_fields():
    """일부 필드 결측 시 가능한 항목만 표기(깨지지 않음)."""
    sig = {"rsi": 50.0, "rsi_state": "중립"}  # above_sma20/macd 없음
    text = labels.signal_text(sig)
    assert "RSI 50" in text
    assert "20일선" not in text


# ── GLOSSARY / CAPTIONS ──────────────────────────────────────────────
def test_glossary_has_required_terms():
    """GLOSSARY는 dict이며 필수 용어 키를 모두 포함하고, 값은 비지 않은 한 줄 정의."""
    assert isinstance(labels.GLOSSARY, dict)
    required = ["PER", "PBR", "ROE_approx", "DIV", "시가총액",
                "EPS", "BPS", "DPS", "RSI", "이동평균", "MACD"]
    for term in required:
        assert term in labels.GLOSSARY, f"용어 누락: {term}"
        assert isinstance(labels.GLOSSARY[term], str)
        assert labels.GLOSSARY[term].strip() != ""


def test_captions_static_disclosures_present():
    """CAPTIONS는 dict이며 핵심 정적 고지(상대순위·대형주 한계·적자 PER) 포함."""
    assert isinstance(labels.CAPTIONS, dict)
    for key in ["relative_rank", "stable_cap_limit", "negative_per"]:
        assert key in labels.CAPTIONS
        assert isinstance(labels.CAPTIONS[key], str)
        assert labels.CAPTIONS[key].strip() != ""
    # 의미 단언: 상대순위 캡션은 매수신호가 아님을 명시
    assert "매수 신호" in labels.CAPTIONS["relative_rank"]
    # 적자 PER 캡션은 "오류 아님" 명시(§4.5)
    assert "오류" in labels.CAPTIONS["negative_per"]
