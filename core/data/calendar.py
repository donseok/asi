"""KRX 영업일 헬퍼.

배치/스냅샷이 주말·공휴일에 빈 데이터를 잡지 않도록 pykrx 영업일을 사용한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pykrx import stock


def recent_business_day(ref: Optional[datetime] = None) -> str:
    """기준일(기본: 오늘)에서 가장 가까운 직전 KRX 영업일을 'YYYYMMDD'로 반환.

    주말/공휴일이면 직전 영업일을 돌려준다(일주일 내).
    """
    ref = ref or datetime.now()
    return stock.get_nearest_business_day_in_a_week(ref.strftime("%Y%m%d"))


def is_business_day(date: datetime) -> bool:
    """해당 날짜가 KRX 영업일인지."""
    ymd = date.strftime("%Y%m%d")
    return stock.get_nearest_business_day_in_a_week(ymd) == ymd
