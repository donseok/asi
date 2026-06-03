"""일봉 OHLCV 조회 (pykrx).

수정주가(adjusted=True)로 단일 통일. 거래정지/상장폐지 종목은 빈 DataFrame을
반환할 수 있으며, 호출자가 그 경우를 처리한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock

import config
from core.data import cache

_RENAME = {
    "시가": "open",
    "고가": "high",
    "저가": "low",
    "종가": "close",
    "거래량": "volume",
    "거래대금": "value",
    "등락률": "change_pct",
}


def get_ohlcv(ticker: str, days: int = config.PRICE_LOOKBACK_DAYS, force: bool = False) -> pd.DataFrame:
    """단일 종목 일봉. 컬럼: open/high/low/close/volume(+value/change_pct), index=date."""
    ticker = str(ticker).zfill(6)
    key = f"ohlcv_{ticker}"

    if not force:
        cached = cache.load(key) if cache.is_fresh(key) else None
        if cached is not None:
            return cached

    end = datetime.now()
    start = end - timedelta(days=days)
    df = stock.get_market_ohlcv(
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
        ticker,
        adjusted=True,
    )

    if df is None or df.empty:
        # 거래정지/상장폐지 등 — 빈 프레임을 캐시하지 않고 그대로 반환
        return pd.DataFrame(columns=list(_RENAME.values()))

    df = df.rename(columns={k: v for k, v in _RENAME.items() if k in df.columns})
    df.index.name = "date"
    # 거래량 0(거래정지일)은 지표 왜곡을 막기 위해 종가는 유지하되 그대로 둔다.
    cache.save(key, df)
    return df
