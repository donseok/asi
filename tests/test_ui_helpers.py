"""ui_helpers 차트 빌더 단위테스트.

plotly figure 빌더는 순수(streamlit/네트워크 호출 없음)하므로
작은 합성 DataFrame을 주입해 반환 trace 수·이름·색을 검증한다.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from ui_helpers import make_overview_figure, make_indicator_figure


def _sample_ohlcv() -> pd.DataFrame:
    """SMA/RSI/MACD 컬럼을 포함한 작은 합성 일봉 DataFrame."""
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 102.0, 101.0, 103.0, 105.0],
            "high": [103.0, 104.0, 103.0, 106.0, 107.0],
            "low": [99.0, 100.0, 100.0, 102.0, 104.0],
            "close": [102.0, 101.0, 103.0, 105.0, 106.0],
            "volume": [1000, 1200, 900, 1500, 1300],
            "sma20": [101.0, 101.2, 101.5, 102.0, 103.0],
            "sma60": [100.5, 100.7, 100.9, 101.2, 101.6],
            "sma120": [100.0, 100.1, 100.2, 100.3, 100.4],
            "rsi": [45.0, 40.0, 55.0, 60.0, 58.0],
            "macd": [0.1, 0.2, 0.3, 0.4, 0.5],
            "signal": [0.05, 0.1, 0.2, 0.3, 0.45],
            "hist": [0.05, 0.1, 0.1, 0.1, 0.05],
        },
        index=idx,
    )


def test_make_overview_figure_traces():
    """개요 차트는 캔들 + SMA20 + 거래량 = 3 trace."""
    fig = make_overview_figure(_sample_ohlcv(), "테스트")
    names = [t.name for t in fig.data]
    assert names.count("가격") == 1
    assert "SMA20" in names
    assert any(t.name == "거래량" for t in fig.data)
    # RSI/MACD는 개요 차트에 없어야 한다(지표 차트로 분리)
    assert "RSI" not in names
    assert "MACD" not in names
    assert len(fig.data) == 3


def test_make_overview_figure_korean_colors():
    """한국 관습: 상승=빨강(#e74c3c), 하락=파랑(#3498db)."""
    fig = make_overview_figure(_sample_ohlcv(), "테스트")
    candle = next(t for t in fig.data if t.name == "가격")
    assert candle.increasing.line.color == "#e74c3c"
    assert candle.decreasing.line.color == "#3498db"


def test_make_overview_figure_empty_df():
    """빈 df면 trace 없는 빈 figure를 반환(앱이 죽지 않게)."""
    fig = make_overview_figure(pd.DataFrame(), "테스트")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_make_indicator_figure_traces():
    """지표 차트는 RSI + MACD + Signal + Hist = 4 trace."""
    fig = make_indicator_figure(_sample_ohlcv())
    names = [t.name for t in fig.data]
    assert "RSI" in names
    assert "MACD" in names
    assert "Signal" in names
    assert "Hist" in names
    # 가격/거래량은 지표 차트에 없어야 한다(개요 차트로 분리)
    assert "가격" not in names
    assert "거래량" not in names
    assert len(fig.data) == 4


def test_make_indicator_figure_empty_df():
    """빈 df면 trace 없는 빈 figure를 반환."""
    fig = make_indicator_figure(pd.DataFrame())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_make_indicator_figure_missing_rsi():
    """rsi 컬럼이 없으면 RSI trace는 빠지고 MACD 3종만 남는다."""
    df = _sample_ohlcv().drop(columns=["rsi"])
    fig = make_indicator_figure(df)
    names = [t.name for t in fig.data]
    assert "RSI" not in names
    assert "MACD" in names
    assert len(fig.data) == 3
