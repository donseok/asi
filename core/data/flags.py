"""단일 종목 리스크 플래그.

Phase 0a에서 '계산 가능한' 위험 신호만 구현한다:
  - 거래정지 의심(최근 거래 없음)
  - 저유동성(평균 거래대금 낮음)
  - 고변동성(일간 수익률 표준편차 큼)

관리종목/투자경고 같은 시장조치 '지정' 상태는 전용 KRX 소스가 필요하므로
Phase 2(pykrx 시장경보/공시)에서 추가한다. 여기서는 거짓 안전감을 주지 않도록
'미확인' 항목을 명시적으로 알린다.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

import config


def compute_risk_flags(ohlcv: Optional[pd.DataFrame]) -> List[str]:
    flags: List[str] = []

    if ohlcv is None or ohlcv.empty:
        return ["⛔ 가격 데이터 없음 — 상장폐지/거래정지 가능"]

    recent = ohlcv.tail(5)
    if "volume" in recent.columns and (recent["volume"].fillna(0) == 0).all():
        flags.append("⛔ 최근 5거래일 거래 없음 — 거래정지 가능")

    if "value" in ohlcv.columns:
        avg_value = ohlcv["value"].tail(20).mean()
        if pd.notna(avg_value) and avg_value < config.MIN_AVG_TRADING_VALUE:
            flags.append("⚠️ 저유동성 — 20일 평균 거래대금이 기준 미만")

    daily_ret = ohlcv["close"].pct_change().tail(20)
    if daily_ret.std() is not None and daily_ret.std() * 100 > 10:
        flags.append("⚠️ 고변동성 — 최근 20일 일간 변동성이 큼")

    return flags
