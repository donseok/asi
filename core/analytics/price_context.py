"""가격 맥락 순수 함수 (OHLCV 기반, 외부 의존 없음 → 단위테스트 용이).

OHLCV 컬럼: open/high/low/close/volume/value, index=date.
모든 함수는 입력 비파괴(부작용 없음)이며, 데이터 부족 시 None 또는 안전값을 반환한다.
지표(SMA/RSI)는 core.analytics.indicators를 재사용한다.
"""
from __future__ import annotations

import pandas as pd

import config
from core.analytics import indicators


def _is_empty(ohlcv: pd.DataFrame) -> bool:
    return ohlcv is None or len(ohlcv) == 0


def week52_position(ohlcv: pd.DataFrame) -> dict:
    """최근 WEEK52_WINDOW 봉 기준 52주 고/저 대비 현재가 위치와 고점 낙폭.

    - pos_pct: (현재가-저가)/(고가-저가)*100, 0~100
    - drawdown_pct: (현재가/고가-1)*100, ≤0 (고점 대비 낙폭)
    빈 입력이면 모든 수치는 None.
    """
    if _is_empty(ohlcv):
        return {"low": None, "high": None, "pos_pct": None, "drawdown_pct": None}
    window = ohlcv.tail(config.WEEK52_WINDOW)
    high = float(window["high"].max())
    low = float(window["low"].min())
    close = float(window["close"].iloc[-1])
    if high == low:
        pos_pct = 100.0
    else:
        pos_pct = (close - low) / (high - low) * 100.0
    drawdown_pct = (close / high - 1.0) * 100.0 if high else None
    return {
        "low": low,
        "high": high,
        "pos_pct": round(pos_pct, 1),
        "drawdown_pct": round(drawdown_pct, 1),
    }


def period_returns(ohlcv: pd.DataFrame, windows=config.PERIOD_RETURN_WINDOWS) -> dict:
    """각 윈도우(영업일) 전 종가 대비 현재 종가 수익률(%). 데이터 부족 시 None."""
    result = {label: None for label in windows}
    if _is_empty(ohlcv):
        return result
    closes = ohlcv["close"]
    last = float(closes.iloc[-1])
    n = len(closes)
    for label, w in windows.items():
        if n > w:
            past = float(closes.iloc[-1 - w])
            if past:
                result[label] = round((last / past - 1.0) * 100.0, 1)
    return result


def ma_alignment(ohlcv: pd.DataFrame) -> str:
    """SMA20/60/120 정렬 상태. 정배열(20>60>120)/역배열(20<60<120)/혼조.

    데이터 부족(120봉 미만)이거나 어느 쪽도 아니면 '혼조'.
    """
    if _is_empty(ohlcv) or len(ohlcv) < 120:
        return "혼조"
    close = ohlcv["close"]
    s20 = indicators.sma(close, 20).iloc[-1]
    s60 = indicators.sma(close, 60).iloc[-1]
    s120 = indicators.sma(close, 120).iloc[-1]
    if pd.isna(s20) or pd.isna(s60) or pd.isna(s120):
        return "혼조"
    if s20 > s60 > s120:
        return "정배열"
    if s20 < s60 < s120:
        return "역배열"
    return "혼조"


def disparity(ohlcv: pd.DataFrame, windows=(20, 60)) -> dict:
    """이격도 = (종가/이동평균 - 1)*100. 윈도우별 dict. 데이터 부족 시 None."""
    result = {w: None for w in windows}
    if _is_empty(ohlcv):
        return result
    close = ohlcv["close"]
    last = float(close.iloc[-1])
    for w in windows:
        ma = indicators.sma(close, w).iloc[-1]
        if pd.notna(ma) and ma:
            result[w] = round((last / float(ma) - 1.0) * 100.0, 2)
    return result


def max_drawdown(ohlcv: pd.DataFrame, window=config.WEEK52_WINDOW) -> float:
    """최근 window 봉 종가 기준 최대낙폭(%). 누적 최고점 대비 최저 하락폭, ≤0.

    빈 입력이면 None.
    """
    if _is_empty(ohlcv):
        return None
    close = ohlcv["close"].tail(window)
    running_max = close.cummax()
    drawdown = close / running_max - 1.0
    return round(float(drawdown.min()) * 100.0, 1)


def volume_ratio(ohlcv: pd.DataFrame, window: int = 20) -> float:
    """마지막날 거래량 / 직전 window일 평균 거래량(마지막날 제외). 데이터 부족 시 None."""
    if _is_empty(ohlcv) or len(ohlcv) <= window:
        return None
    volumes = ohlcv["volume"]
    last = float(volumes.iloc[-1])
    base = float(volumes.iloc[-1 - window : -1].mean())
    if not base:
        return None
    return round(last / base, 2)


def volatility_grade(ohlcv: pd.DataFrame, window: int = 20) -> tuple:
    """최근 window일 일간 수익률 표준편차(%)로 변동성 등급.

    경계 config.VOLATILITY_GRADE_BOUNDS=(low, high):
      pct < low → 낮음, low ≤ pct < high → 보통, pct ≥ high → 높음.
    반환 (등급, daily_pct). 데이터 부족이면 (None, None).
    """
    low, high = config.VOLATILITY_GRADE_BOUNDS
    if _is_empty(ohlcv) or len(ohlcv) <= window:
        return (None, None)
    rets = ohlcv["close"].pct_change().tail(window).dropna()
    if rets.empty:
        return (None, None)
    pct = float(rets.std()) * 100.0
    if pct < low:
        grade = "낮음"
    elif pct < high:
        grade = "보통"
    else:
        grade = "높음"
    return (grade, round(pct, 2))


def overheating(ohlcv: pd.DataFrame) -> dict:
    """가격·거래량 기반 과열도 프록시(게시판 심리 아님).

    구성 신호(불리언):
      - rsi_overbought: RSI ≥ OVERHEAT_RSI[1]
      - rsi_oversold: RSI ≤ OVERHEAT_RSI[0] (참고용, 과열 가산에는 미포함)
      - volume_spike: 마지막날 거래대금 / 직전 20일 평균 ≥ OVERHEAT_VOLUME_SPIKE
      - disparity_high: 20일 이격도 ≥ 10%
      - volatility_high: 변동성 등급 '높음'
    충족 신호 수 → 등급: 0 낮음 · 1 보통 · 2 높음 · 3+ 과열.
    빈 입력이면 level=None, components={}.
    """
    if _is_empty(ohlcv):
        return {"level": None, "components": {}}

    low_rsi, high_rsi = config.OVERHEAT_RSI

    rsi_series = indicators.rsi(ohlcv["close"])
    rsi_last = rsi_series.iloc[-1] if len(rsi_series) else None
    rsi_overbought = bool(pd.notna(rsi_last) and rsi_last >= high_rsi)
    rsi_oversold = bool(pd.notna(rsi_last) and rsi_last <= low_rsi)

    # 거래대금(value) 급증 배수: 마지막날 / 직전 20일 평균(마지막날 제외)
    volume_spike = False
    if len(ohlcv) > 20:
        val = ohlcv["value"]
        base = float(val.iloc[-21:-1].mean())
        if base:
            volume_spike = bool(float(val.iloc[-1]) / base >= config.OVERHEAT_VOLUME_SPIKE)

    disp = disparity(ohlcv, windows=(20,)).get(20)
    disparity_high = bool(disp is not None and disp >= 10.0)

    grade, _ = volatility_grade(ohlcv, window=20)
    volatility_high = bool(grade == "높음")

    components = {
        "rsi": float(rsi_last) if pd.notna(rsi_last) else None,
        "rsi_overbought": rsi_overbought,
        "rsi_oversold": rsi_oversold,
        "volume_spike": volume_spike,
        "disparity_high": disparity_high,
        "volatility_high": volatility_high,
    }
    hits = sum([rsi_overbought, volume_spike, disparity_high, volatility_high])
    if hits == 0:
        level = "낮음"
    elif hits == 1:
        level = "보통"
    elif hits == 2:
        level = "높음"
    else:
        level = "과열"
    return {"level": level, "components": components}


def monitor_targets(close, stop=None, target=None) -> dict:
    """최신 종가 대비 손절가/익절가 이탈 '사실'만 고지(주문·자동매매 없음).

    판정 우선순위: 손절 이탈(생존 우선) → 익절 도달 → 범위내.
      - close ≤ stop → 손절이탈
      - close ≥ target → 익절도달
      - 그 외 → 범위내
    stop/target가 None이면 해당 조건은 건너뛴다.
    """
    status = "범위내"
    if stop is not None and close <= stop:
        status = "손절이탈"
    elif target is not None and close >= target:
        status = "익절도달"
    return {"status": status, "close": close, "stop": stop, "target": target}
