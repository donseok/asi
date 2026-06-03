"""스크리너용 결합 스냅샷.

유니버스(제외규칙 적용) + 밸류에이션/시총을 ticker 기준으로 결합한다.
'어느 날짜 기준인가'를 명확히 하기 위해 fundamental 스냅샷의 갱신 시각을 함께 노출.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from core.data import cache
from core.data.fundamentals import get_fundamental_snapshot
from core.data.universe import load_universe

_FUND_KEY = "fundamental_snapshot"


def build_snapshot(force: bool = False) -> pd.DataFrame:
    """제외 종목을 거른 결합 스냅샷을 반환."""
    uni = load_universe(force=force)
    fund = get_fundamental_snapshot(force=force)

    # market은 유니버스 쪽을 신뢰(중복 컬럼 제거)
    fund_cols = [c for c in fund.columns if c != "market"]
    df = uni.merge(fund[fund_cols], on="ticker", how="left")

    # 제외 종목(우선주/스팩/리츠) 제거
    df = df[~df["is_excluded"]].copy().reset_index(drop=True)
    return df


def snapshot_asof() -> Optional[datetime]:
    """스냅샷 데이터의 마지막 성공 갱신 시각."""
    return cache.last_updated(_FUND_KEY)
