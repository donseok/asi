"""기존 순수 기술지표 로직 백필 회귀 테스트.

네트워크/pykrx 호출 없이 작은 합성 Series/DataFrame만 주입한다.
실행: 프로젝트 루트에서 python -m pytest tests/test_indicators.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from core.analytics.indicators import (
    add_indicators,
    latest_signals,
    macd,
    rsi,
    sma,
)


def test_rsi_pure_rise_is_100():
    # 단조 상승만 있는 시계열 → 하락분이 0 → RSI는 100으로 수렴
    close = pd.Series([float(x) for x in range(1, 41)])  # 1..40
    out = rsi(close, period=config.RSI_PERIOD)
    # 워밍업 구간(period 미만) 이후 마지막 값은 정확히 100.0
    assert out.iloc[-1] == 100.0


def test_rsi_pure_fall_is_0():
    # 단조 하락만 있는 시계열 → 상승분이 0 → RSI는 0으로 수렴
    close = pd.Series([float(x) for x in range(40, 0, -1)])  # 40..1
    out = rsi(close, period=config.RSI_PERIOD)
    assert out.iloc[-1] == 0.0


def test_sma_min_periods_warmup_is_nan():
    # window=3 → 앞의 2개는 NaN, 3번째부터 값 존재
    close = pd.Series([10.0, 20.0, 30.0, 40.0])
    out = sma(close, window=3)
    assert pd.isna(out.iloc[0])
    assert pd.isna(out.iloc[1])
    # (10+20+30)/3 = 20.0
    assert out.iloc[2] == 20.0
    # (20+30+40)/3 = 30.0
    assert out.iloc[3] == 30.0


def test_sma_window_longer_than_series_all_nan():
    # 데이터가 window보다 짧으면 전부 NaN (min_periods=window)
    close = pd.Series([10.0, 20.0])
    out = sma(close, window=5)
    assert out.isna().all()


def test_macd_sign_positive_on_uptrend():
    # 충분히 긴 단조 상승 → fast EMA가 slow EMA보다 높음 → macd > 0
    close = pd.Series([float(x) for x in range(1, 101)])  # 1..100
    out = macd(
        close,
        fast=config.MACD_FAST,
        slow=config.MACD_SLOW,
        signal=config.MACD_SIGNAL,
    )
    assert out["macd"].iloc[-1] > 0
    # 컬럼 구조 확인
    assert list(out.columns) == ["macd", "signal", "hist"]


def test_macd_sign_negative_on_downtrend():
    # 단조 하락 → macd < 0
    close = pd.Series([float(x) for x in range(100, 0, -1)])  # 100..1
    out = macd(
        close,
        fast=config.MACD_FAST,
        slow=config.MACD_SLOW,
        signal=config.MACD_SIGNAL,
    )
    assert out["macd"].iloc[-1] < 0


def test_macd_hist_equals_macd_minus_signal():
    # hist = macd - signal 항등식
    close = pd.Series([float(x) for x in range(1, 101)])
    out = macd(close)
    diff = (out["hist"] - (out["macd"] - out["signal"])).abs()
    assert (diff < 1e-9).all()


def _make_ohlcv(closes: list[float]) -> pd.DataFrame:
    # 간단한 합성 OHLCV (지표 계산엔 close/volume만 필요)
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000] * n,
        },
        index=idx,
    )


def test_latest_signals_empty_returns_empty_dict():
    assert latest_signals(pd.DataFrame()) == {}
    assert latest_signals(None) == {}


def test_latest_signals_uptrend_above_sma_and_close():
    # 단조 상승 → 마지막 종가가 sma20/sma60 위
    df = add_indicators(_make_ohlcv([float(x) for x in range(1, 131)]))
    sig = latest_signals(df)
    assert sig["close"] == 130.0
    assert sig["above_sma20"] is True
    assert sig["above_sma60"] is True


def test_latest_signals_rsi_state_overbought():
    # 순상승 → RSI=100 → 과매수(≥70)
    df = add_indicators(_make_ohlcv([float(x) for x in range(1, 41)]))
    sig = latest_signals(df)
    assert sig["rsi_state"] == "과매수(≥70)"


def test_latest_signals_rsi_state_oversold():
    # 순하락 → RSI=0 → 과매도(≤30)
    df = add_indicators(_make_ohlcv([float(x) for x in range(40, 0, -1)]))
    sig = latest_signals(df)
    assert sig["rsi_state"] == "과매도(≤30)"


def test_latest_signals_above_sma_none_when_insufficient():
    # 데이터가 sma60 window(60)보다 짧으면 sma60=NaN → above_sma60=None
    df = add_indicators(_make_ohlcv([float(x) for x in range(1, 31)]))  # 30봉
    sig = latest_signals(df)
    assert sig["above_sma60"] is None
    # sma20은 20봉 이상이므로 계산됨
    assert sig["above_sma20"] is True
