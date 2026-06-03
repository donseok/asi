"""밸류에이션 스냅샷 (pykrx).

주의: pykrx get_market_fundamental 은 BPS/PER/PBR/EPS/DIV/DPS 만 제공한다.
ROE는 직접 제공하지 않으므로 ROE ≈ EPS/BPS 로 근사하고 'ROE_approx'로 명시한다.
정확한 ROE(당기순이익/자본)는 Phase 0b의 DART 재무로 계산한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pykrx import stock

import config
from core.data import cache
from core.data.calendar import recent_business_day

_KEY = "fundamental_snapshot"


def get_fundamental_snapshot(force: bool = False) -> pd.DataFrame:
    """전 종목 밸류에이션 + 시가총액 스냅샷.

    컬럼: ticker, market, BPS, PER, PBR, EPS, DIV, DPS, 종가, 시가총액, 거래대금,
          상장주식수, ROE_approx
    """
    if not force:
        cached = cache.load(_KEY) if cache.is_fresh(_KEY) else None
        if cached is not None:
            return cached

    date = recent_business_day()
    frames = []
    for market in config.MARKETS:
        fund = stock.get_market_fundamental(date, market=market)   # BPS PER PBR EPS DIV DPS
        capdf = stock.get_market_cap(date, market=market)          # 종가 시가총액 거래량 거래대금 상장주식수
        merged = fund.join(capdf, how="outer")
        merged["market"] = market
        frames.append(merged)

    df = pd.concat(frames)
    df.index.name = "ticker"
    df = df.reset_index()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)

    # ROE 근사 = EPS / BPS * 100 (%). 0/음수 BPS는 무효 처리.
    bps = df["BPS"].replace(0, np.nan)
    df["ROE_approx"] = (df["EPS"] / bps * 100).replace([np.inf, -np.inf], np.nan)

    cache.save(_KEY, df)
    return df
