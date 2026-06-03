"""기술적 지표 (순수 pandas, 외부 의존 없음 → 단위테스트 용이).

- SMA: 단순이동평균
- RSI: Wilder 방식(EWMA, alpha=1/period)
- MACD: EMA(fast) - EMA(slow), signal = EMA(signal)
"""
from __future__ import annotations

import pandas as pd

import config


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    """Wilder RSI. 상승만 있으면 100, 하락만 있으면 0에 수렴."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # avg_loss == 0 (순상승 구간) → rs=inf → out=100
    out = out.where(avg_loss != 0, 100.0)
    # avg_gain == 0 (순하락 구간) → out=0
    out = out.where(avg_gain != 0, 0.0)
    return out


def macd(
    series: pd.Series,
    fast: int = config.MACD_FAST,
    slow: int = config.MACD_SLOW,
    signal: int = config.MACD_SIGNAL,
) -> pd.DataFrame:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}, index=series.index
    )


def add_indicators(ohlcv: pd.DataFrame, sma_windows=config.SMA_WINDOWS) -> pd.DataFrame:
    """OHLCV에 지표 컬럼을 붙여 반환. 빈 입력은 그대로 반환."""
    if ohlcv is None or ohlcv.empty:
        return ohlcv
    df = ohlcv.copy()
    for w in sma_windows:
        df[f"sma{w}"] = sma(df["close"], w)
    df["rsi"] = rsi(df["close"])
    df = df.join(macd(df["close"]))
    return df


def latest_signals(ohlcv_with_ind: pd.DataFrame) -> dict:
    """마지막 행 기준 기술적 신호 요약(딥다이브 표시용)."""
    if ohlcv_with_ind is None or ohlcv_with_ind.empty:
        return {}
    last = ohlcv_with_ind.iloc[-1]
    close = last.get("close")
    sig = {
        "close": close,
        "rsi": last.get("rsi"),
        "macd_hist": last.get("hist"),
        "above_sma20": bool(close > last["sma20"]) if pd.notna(last.get("sma20")) else None,
        "above_sma60": bool(close > last["sma60"]) if pd.notna(last.get("sma60")) else None,
    }
    rsi_val = last.get("rsi")
    if pd.notna(rsi_val):
        if rsi_val >= 70:
            sig["rsi_state"] = "과매수(≥70)"
        elif rsi_val <= 30:
            sig["rsi_state"] = "과매도(≤30)"
        else:
            sig["rsi_state"] = "중립"
    return sig
