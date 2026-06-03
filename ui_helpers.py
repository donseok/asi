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


@st.cache_data(ttl=3600, show_spinner="수급(기관·외국인) 데이터를 불러오는 중...")
def load_supply_demand(ticker: str, days: int = 60) -> pd.DataFrame:
    from core.data import naver
    return naver.get_supply_demand(ticker, days=days)


@st.cache_data(ttl=3600, show_spinner="투자지표를 불러오는 중...")
def load_overview(ticker: str) -> dict:
    from core.data import naver
    return naver.get_overview(ticker)


@st.cache_data(ttl=3600, show_spinner="재무 데이터를 불러오는 중...")
def load_financials(ticker: str) -> pd.DataFrame:
    from core.data import naver
    return naver.get_financials(ticker)


@st.cache_data(ttl=3600, show_spinner="동일업종 비교를 불러오는 중...")
def load_peers(ticker: str) -> pd.DataFrame:
    from core.data import naver
    return naver.get_peers(ticker)


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


def make_supply_figure(flows: pd.DataFrame) -> go.Figure:
    """수급 차트: 기관·외국인 일별 순매매(그룹 막대) + 외국인 보유율(보조축 선).

    flows: core.data.naver.get_supply_demand 산출물(index=date,
    cols: inst_net/foreign_net/foreign_hold_pct). 빈 입력이면 빈 figure.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if flows is None or flows.empty:
        fig.update_layout(height=360, template="plotly_dark",
                          margin=dict(l=10, r=10, t=30, b=10))
        return fig

    x = flows.index
    # 기관/외국인은 '주체'가 다르므로 색을 분리(부호로 매수/매도 구분은 보조축 0선으로 읽음).
    fig.add_trace(
        go.Bar(x=x, y=flows.get("foreign_net"), name="외국인 순매매",
               marker_color="#5b8cff"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=x, y=flows.get("inst_net"), name="기관 순매매",
               marker_color="#e3b341"),
        secondary_y=False,
    )
    if "foreign_hold_pct" in flows.columns:
        fig.add_trace(
            go.Scatter(x=x, y=flows["foreign_hold_pct"], name="외국인 보유율(%)",
                       line=dict(color="#b692f6", width=2)),
            secondary_y=True,
        )
    fig.add_hline(y=0, line_width=1, line_color="#3a4456", secondary_y=False)
    fig.update_layout(
        height=380, template="plotly_dark", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_yaxes(title_text="순매매(주)", secondary_y=False)
    fig.update_yaxes(title_text="외국인 보유율(%)", secondary_y=True, showgrid=False)
    return fig


def make_financials_figure(fin: pd.DataFrame, annual_only: bool = True) -> go.Figure:
    """재무 추세: 매출액·영업이익(막대) + 영업이익률(보조축 선).

    fin: core.data.naver.get_financials 산출물(index=항목, columns=기간).
    '연 '로 시작하는 연간 컬럼만 기본 사용. 빈/항목부족 시 빈 figure.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if fin is None or fin.empty:
        fig.update_layout(height=320, template="plotly_dark",
                          margin=dict(l=10, r=10, t=30, b=10))
        return fig

    cols = [c for c in fin.columns if (not annual_only) or str(c).startswith("연")]
    if not cols:
        cols = list(fin.columns)

    def _row(name_contains):
        for idx in fin.index:
            if name_contains in str(idx):
                return [fin.loc[idx, c] for c in cols]
        return None

    rev = _row("매출액")
    op = _row("영업이익")
    op_margin = _row("영업이익률")
    labels = [str(c).replace("연 ", "") for c in cols]

    if rev is not None:
        fig.add_trace(go.Bar(x=labels, y=rev, name="매출액(억)", marker_color="#3a6fd8"),
                      secondary_y=False)
    if op is not None:
        fig.add_trace(go.Bar(x=labels, y=op, name="영업이익(억)", marker_color="#3fb950"),
                      secondary_y=False)
    if op_margin is not None:
        fig.add_trace(go.Scatter(x=labels, y=op_margin, name="영업이익률(%)",
                                 line=dict(color="#e3b341", width=2)), secondary_y=True)
    fig.update_layout(
        height=340, template="plotly_dark", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_yaxes(title_text="금액(억원)", secondary_y=False)
    fig.update_yaxes(title_text="영업이익률(%)", secondary_y=True, showgrid=False)
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
