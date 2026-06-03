"""config.py 신규 상수 스모크 테스트.

상수만 추가하므로 import·값·타입 회귀만 막는다(순수 검증, 네트워크 없음).
"""
from __future__ import annotations

import config


def test_screener_default_limit():
    assert config.SCREENER_DEFAULT_LIMIT == 30
    assert isinstance(config.SCREENER_DEFAULT_LIMIT, int)


def test_badge_percentile():
    assert config.BADGE_PERCENTILE == 70
    assert isinstance(config.BADGE_PERCENTILE, int)


def test_stable_cap_percentile():
    assert config.STABLE_CAP_PERCENTILE == 80
    assert isinstance(config.STABLE_CAP_PERCENTILE, int)


def test_explain_min_subscore():
    assert config.EXPLAIN_MIN_SUBSCORE == 60
    assert isinstance(config.EXPLAIN_MIN_SUBSCORE, int)


def test_week52_window():
    assert config.WEEK52_WINDOW == 252
    assert isinstance(config.WEEK52_WINDOW, int)


def test_period_return_windows():
    assert config.PERIOD_RETURN_WINDOWS == {
        "1개월": 21,
        "3개월": 63,
        "6개월": 126,
        "12개월": 252,
    }
    assert isinstance(config.PERIOD_RETURN_WINDOWS, dict)
    # 모든 값은 양의 정수(거래일 수).
    assert all(isinstance(v, int) and v > 0 for v in config.PERIOD_RETURN_WINDOWS.values())


def test_volatility_grade_bounds():
    assert config.VOLATILITY_GRADE_BOUNDS == (1.5, 3.0)
    assert isinstance(config.VOLATILITY_GRADE_BOUNDS, tuple)
    assert len(config.VOLATILITY_GRADE_BOUNDS) == 2
    # 하한 < 상한.
    assert config.VOLATILITY_GRADE_BOUNDS[0] < config.VOLATILITY_GRADE_BOUNDS[1]


def test_dividend_principal():
    assert config.DIVIDEND_PRINCIPAL == 1_000_000
    assert isinstance(config.DIVIDEND_PRINCIPAL, int)


def test_overheat_volume_spike():
    assert config.OVERHEAT_VOLUME_SPIKE == 2.0
    assert isinstance(config.OVERHEAT_VOLUME_SPIKE, float)


def test_overheat_rsi():
    assert config.OVERHEAT_RSI == (30, 70)
    assert isinstance(config.OVERHEAT_RSI, tuple)
    assert len(config.OVERHEAT_RSI) == 2
    # 과매도 하한 < 과매수 상한.
    assert config.OVERHEAT_RSI[0] < config.OVERHEAT_RSI[1]
