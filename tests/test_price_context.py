"""price_context 순수 함수 테스트 — 합성 OHLCV 주입(네트워크/pykrx 없음)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.analytics import price_context as pc


def _ohlcv(closes, *, highs=None, lows=None, volumes=None, values=None):
    """종가 리스트로 합성 OHLCV(index=영업일)를 만든다. 미지정 컬럼은 종가/기본값 파생."""
    closes = list(closes)
    n = len(closes)
    idx = pd.bdate_range("2024-01-01", periods=n)
    highs = list(highs) if highs is not None else [c * 1.0 for c in closes]
    lows = list(lows) if lows is not None else [c * 1.0 for c in closes]
    volumes = list(volumes) if volumes is not None else [1000] * n
    values = list(values) if values is not None else [c * v for c, v in zip(closes, volumes)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "value": values,
        },
        index=idx,
    )
    df.index.name = "date"
    return df


# ── week52_position ──────────────────────────────────────────────────
def test_week52_position_current_equals_high():
    # 현재가가 52주 최고가 → 위치 100%, 낙폭 0%
    df = _ohlcv([100, 90, 80, 110], highs=[100, 90, 80, 110], lows=[100, 90, 80, 110])
    res = pc.week52_position(df)
    assert res["high"] == 110
    assert res["low"] == 80
    assert res["pos_pct"] == 100.0
    assert res["drawdown_pct"] == 0.0


def test_week52_position_midpoint():
    # 고가 200, 저가 100, 현재가 150 → 위치 50%, 낙폭 -25%
    df = _ohlcv([100, 200, 150], highs=[100, 200, 150], lows=[100, 200, 150])
    res = pc.week52_position(df)
    assert res["high"] == 200
    assert res["low"] == 100
    assert res["pos_pct"] == 50.0
    assert res["drawdown_pct"] == -25.0


def test_week52_position_empty():
    df = _ohlcv([])
    res = pc.week52_position(df)
    assert res["pos_pct"] is None
    assert res["drawdown_pct"] is None


# ── period_returns ───────────────────────────────────────────────────
def test_period_returns_sign_and_keys():
    # 21봉 전 100 → 현재 110: 1개월 +10%. 63봉 등 데이터 부족분은 None.
    closes = [100] * 21 + [110]  # 길이 22, 인덱스 -22가 100, 마지막 110
    df = _ohlcv(closes)
    res = pc.period_returns(df)
    # 키는 PERIOD_RETURN_WINDOWS와 동일
    assert set(res.keys()) == set(["1개월", "3개월", "6개월", "12개월"])
    assert res["1개월"] == 10.0  # (110/100 - 1)*100
    # 3·6·12개월은 데이터 부족 → None
    assert res["3개월"] is None
    assert res["12개월"] is None


def test_period_returns_negative():
    closes = [200] * 21 + [150]
    df = _ohlcv(closes)
    res = pc.period_returns(df)
    assert res["1개월"] == -25.0


def test_period_returns_empty():
    res = pc.period_returns(_ohlcv([]))
    assert res == {"1개월": None, "3개월": None, "6개월": None, "12개월": None}


# ── ma_alignment ─────────────────────────────────────────────────────
def test_ma_alignment_bullish():
    # 꾸준히 상승 → SMA20 > SMA60 > SMA120 → 정배열
    closes = list(range(1, 201))  # 1..200 단조 증가, 200봉
    df = _ohlcv([float(c) for c in closes])
    assert pc.ma_alignment(df) == "정배열"


def test_ma_alignment_bearish():
    # 꾸준히 하락 → SMA20 < SMA60 < SMA120 → 역배열
    closes = list(range(200, 0, -1))  # 200..1 단조 감소
    df = _ohlcv([float(c) for c in closes])
    assert pc.ma_alignment(df) == "역배열"


def test_ma_alignment_mixed():
    # 장기 상승 후 최근 20봉 급락(플랫) → SMA20<SMA60 이지만 SMA60>SMA120 → 비단조 → 혼조
    # (정배열=20>60>120, 역배열=20<60<120 둘 다 아님)
    closes = [float(c) for c in range(1, 181)] + [100.0] * 20  # 200봉
    df = _ohlcv(closes)
    assert pc.ma_alignment(df) == "혼조"


def test_ma_alignment_insufficient():
    # 120봉 미만 → 혼조(판정 불가 안전값)
    df = _ohlcv([float(c) for c in range(1, 50)])
    assert pc.ma_alignment(df) == "혼조"


# ── disparity ────────────────────────────────────────────────────────
def test_disparity_above_ma():
    # 60봉 동일가 100 후 마지막 110 → 종가>이동평균 → 이격도 양수
    closes = [100.0] * 60 + [110.0]
    df = _ohlcv(closes)
    res = pc.disparity(df, windows=(20, 60))
    assert set(res.keys()) == {20, 60}
    # 20일선은 (19*100+110)/20=100.5 → (110/100.5-1)*100 ≈ 9.45
    assert res[20] > 0
    assert res[60] > 0
    # 20일 이격도 > 60일 이격도(짧은 평균이 현재가에 더 가까움)
    assert res[20] < res[60]


def test_disparity_insufficient_window():
    # 30봉뿐 → 60일선 미산출 → None, 20일선은 산출
    closes = [100.0] * 30
    df = _ohlcv(closes)
    res = pc.disparity(df, windows=(20, 60))
    assert res[20] == 0.0  # 전부 동일가 → 종가=이동평균 → 0%
    assert res[60] is None


def test_disparity_empty():
    res = pc.disparity(_ohlcv([]), windows=(20, 60))
    assert res == {20: None, 60: None}


# ── max_drawdown ─────────────────────────────────────────────────────
def test_max_drawdown_basic():
    # 100 → 200(고점) → 100(반토막) → MDD = -50%
    closes = [100.0, 200.0, 100.0, 150.0]
    df = _ohlcv(closes)
    mdd = pc.max_drawdown(df)
    assert mdd == -50.0


def test_max_drawdown_monotonic_up_is_zero():
    # 단조 상승 → 낙폭 없음 → 0%
    closes = [100.0, 110.0, 120.0, 130.0]
    df = _ohlcv(closes)
    assert pc.max_drawdown(df) == 0.0


def test_max_drawdown_non_positive():
    closes = [100.0, 80.0, 120.0, 60.0, 90.0]
    df = _ohlcv(closes)
    mdd = pc.max_drawdown(df)
    assert mdd <= 0.0


def test_max_drawdown_empty():
    assert pc.max_drawdown(_ohlcv([])) is None


# ── volume_ratio ─────────────────────────────────────────────────────
def test_volume_ratio_double():
    # 직전 20일 거래량 1000, 마지막날 2000 → 배수 2.0
    # 비교 기준은 '직전 window일 평균'(마지막날 제외)
    volumes = [1000] * 20 + [2000]
    df = _ohlcv([100.0] * 21, volumes=volumes)
    ratio = pc.volume_ratio(df, window=20)
    assert ratio == 2.0


def test_volume_ratio_normal():
    volumes = [1000] * 21
    df = _ohlcv([100.0] * 21, volumes=volumes)
    assert pc.volume_ratio(df, window=20) == 1.0


def test_volume_ratio_insufficient():
    # window+1 봉 미만 → None
    df = _ohlcv([100.0] * 10, volumes=[1000] * 10)
    assert pc.volume_ratio(df, window=20) is None


def test_volume_ratio_empty():
    assert pc.volume_ratio(_ohlcv([]), window=20) is None


# ── volatility_grade ─────────────────────────────────────────────────
def _closes_for_daily_std(target_pct, n=21):
    """일간 수익률이 +target%/-target% 교대가 되도록 종가열 생성.
    표준편차(모집단? 표본?)는 구현이 pandas std(ddof=1)를 쓰므로 근사로만 사용.
    경계 테스트는 명확히 낮음/보통/높음 구간에 들도록 여유를 둔다."""
    closes = [100.0]
    up = 1 + target_pct / 100.0
    down = 1 - target_pct / 100.0
    for i in range(n):
        closes.append(closes[-1] * (up if i % 2 == 0 else down))
    return closes


def test_volatility_grade_low():
    # 일간 변동 ±0.5% → 표준편차 < 1.5 → 낮음
    df = _ohlcv(_closes_for_daily_std(0.5))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "낮음"
    assert pct < 1.5


def test_volatility_grade_mid():
    # 일간 변동 ±2% → 1.5 ≤ std < 3.0 → 보통
    df = _ohlcv(_closes_for_daily_std(2.0))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "보통"
    assert 1.5 <= pct < 3.0


def test_volatility_grade_high():
    # 일간 변동 ±5% → std ≥ 3.0 → 높음
    df = _ohlcv(_closes_for_daily_std(5.0))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "높음"
    assert pct >= 3.0


def test_volatility_grade_empty():
    grade, pct = pc.volatility_grade(_ohlcv([]), window=20)
    assert grade is None
    assert pct is None


# ── overheating ──────────────────────────────────────────────────────
def test_overheating_calm_is_low():
    # 동일가·동일거래량 → RSI 미산출/중립·급증 없음·이격도 0·저변동 → 낮음
    df = _ohlcv([100.0] * 130, volumes=[1000] * 130)
    res = pc.overheating(df)
    assert res["level"] == "낮음"
    assert "components" in res
    # 어떤 신호도 켜지지 않음
    assert res["components"]["volume_spike"] is False


def test_overheating_high_when_overbought_and_spike():
    # 강한 단조 상승(RSI 과매수) + 마지막날 거래대금 급증 + 큰 이격도
    closes = [float(c) for c in range(1, 131)]  # 1..130 단조 상승 → RSI 100, 이격도 큼
    volumes = [1000] * 129 + [5000]  # 마지막날 5배 급증
    df = _ohlcv(closes, volumes=volumes)
    res = pc.overheating(df)
    # RSI 과매수 + 거래대금 급증 + 이격도 신호 → 다수 충족
    assert res["components"]["rsi_overbought"] is True
    assert res["components"]["volume_spike"] is True
    assert res["level"] in ("높음", "과열")


def test_overheating_empty():
    res = pc.overheating(_ohlcv([]))
    assert res["level"] is None
    assert res["components"] == {}


# ── monitor_targets ──────────────────────────────────────────────────
def test_monitor_targets_take_profit_reached():
    # 종가 ≥ 익절가 → 익절도달
    res = pc.monitor_targets(close=11000, stop=9000, target=10500)
    assert res["status"] == "익절도달"


def test_monitor_targets_stop_breached():
    # 종가 ≤ 손절가 → 손절이탈
    res = pc.monitor_targets(close=8900, stop=9000, target=10500)
    assert res["status"] == "손절이탈"


def test_monitor_targets_in_range():
    res = pc.monitor_targets(close=10000, stop=9000, target=10500)
    assert res["status"] == "범위내"


def test_monitor_targets_only_stop():
    # 익절가 미입력 → 손절만 감시
    assert pc.monitor_targets(close=9500, stop=9000, target=None)["status"] == "범위내"
    assert pc.monitor_targets(close=8500, stop=9000, target=None)["status"] == "손절이탈"


def test_monitor_targets_no_inputs():
    # 둘 다 없음 → 범위내(감시 대상 없음), close는 보존
    res = pc.monitor_targets(close=10000, stop=None, target=None)
    assert res["status"] == "범위내"
    assert res["close"] == 10000
