"""Streamlit UI 레이어 헬퍼.

여기서만 streamlit/plotly에 의존한다(core는 순수 로직). st.cache_data로
세션 내 재실행 시 네트워크 호출을 줄인다(디스크 Parquet 캐시와 별개의 메모리 캐시).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core.analytics.indicators import add_indicators
from core.analytics.scoring import compute_scores
from core.data.prices import get_ohlcv
from core.data.snapshot import build_snapshot, snapshot_asof


@st.cache_data(ttl=3600, show_spinner="종목 스냅샷을 불러오는 중...")
def load_scored_snapshot() -> pd.DataFrame:
    return compute_scores(build_snapshot())


@st.cache_data(ttl=3600, show_spinner="가격 데이터를 불러오는 중...")
def load_ohlcv_with_indicators(ticker: str) -> pd.DataFrame:
    return add_indicators(get_ohlcv(ticker))


def refresh_all_caches() -> None:
    """디스크 캐시까지 강제 재수집 후 메모리 캐시 비움."""
    build_snapshot(force=True)
    st.cache_data.clear()


def asof_text() -> str:
    ts = snapshot_asof()
    return ts.strftime("%Y-%m-%d %H:%M") if ts else "갱신 이력 없음"


def fmt_won(value) -> str:
    """원 단위 금액을 조/억 단위 한글로."""
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    if abs(value) >= 1e12:
        return f"{value / 1e12:,.2f}조"
    if abs(value) >= 1e8:
        return f"{value / 1e8:,.0f}억"
    return f"{value:,.0f}"


def make_overview_figure(df: pd.DataFrame, title: str) -> go.Figure:
    """개요 차트: 캔들 + 20일 이동평균 + 거래량(2단). 한국 색 유지."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.74, 0.26],
        subplot_titles=("가격 + 20일 이동평균선", "거래량"),
    )

    # 빈 df 방어: trace 없이 빈 figure만 반환(앱이 죽지 않게)
    if df is None or df.empty:
        fig.update_layout(
            title=title,
            height=480,
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=60, b=10),
        )
        return fig

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="가격",
            increasing_line_color="#e74c3c",  # 한국 관습: 상승=빨강
            decreasing_line_color="#3498db",  # 하락=파랑
        ),
        row=1,
        col=1,
    )

    # 간단(A) 모드: 20일선만 노출(60/120선은 중급 영역으로 분리)
    if "sma20" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["sma20"], name="SMA20", line=dict(width=1, color="#f1c40f")),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="거래량", marker_color="#7f8c8d"),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=title,
        height=480,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


def make_indicator_figure(df: pd.DataFrame) -> go.Figure:
    """기술 지표 차트: RSI(14) + MACD(2단). 중급 펼침 영역에서 사용."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.5, 0.5],
        subplot_titles=("RSI(14)", "MACD"),
    )

    # 빈 df 방어: trace 없이 빈 figure만 반환
    if df is None or df.empty:
        fig.update_layout(
            height=420,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
        )
        return fig

    if "rsi" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#e67e22")),
            row=1,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_color="#e74c3c", row=1, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#3498db", row=1, col=1)

    if "macd" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="#2980b9")),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["signal"], name="Signal", line=dict(color="#e67e22")),
            row=2,
            col=1,
        )
        # 히스토그램: 양수=빨강/음수=파랑(한국 관습)
        colors = ["#e74c3c" if v >= 0 else "#3498db" for v in df["hist"].fillna(0)]
        fig.add_trace(
            go.Bar(x=df.index, y=df["hist"], name="Hist", marker_color=colors),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=420,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
