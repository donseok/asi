"""KRX 영업일 헬퍼.

배치/스냅샷이 주말·공휴일에 빈 데이터를 잡지 않도록 가장 가까운 직전 영업일을 구한다.

주의(2025~): pykrx 의 get_nearest_business_day_in_a_week 는 KRX **인덱스** 엔드포인트에
의존하는데, KRX 포털 변경으로 이 엔드포인트가 빈 응답을 돌려주며 깨졌다.
반면 **단일 종목 일봉**(get_market_ohlcv)은 여전히 동작한다. 따라서 유동성 높은
기준 종목(삼성전자)의 최근 일봉 마지막 날짜로 영업일을 추정하고, 그마저 실패하면
요일 기반(주말→직전 금요일) 폴백으로 절대 죽지 않게 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

_REF_TICKER = "005930"  # 삼성전자: 상장 유지·고유동성 기준 종목


def _weekday_fallback(ref: datetime) -> str:
    """요일 기반 직전 영업일(공휴일 미반영). 토/일이면 직전 금요일로."""
    d = ref
    while d.weekday() >= 5:  # 5=토, 6=일
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def recent_business_day(ref: Optional[datetime] = None) -> str:
    """기준일(기본: 오늘)에서 가장 가까운 직전 KRX 영업일을 'YYYYMMDD'로 반환."""
    ref = ref or datetime.now()
    try:
        from pykrx import stock

        start = (ref - timedelta(days=10)).strftime("%Y%m%d")
        end = ref.strftime("%Y%m%d")
        df = stock.get_market_ohlcv(start, end, _REF_TICKER)
        if df is not None and not df.empty:
            return df.index[-1].strftime("%Y%m%d")
    except Exception:
        pass
    return _weekday_fallback(ref)


def is_business_day(date: datetime) -> bool:
    """해당 날짜가 KRX 영업일인지(기준 종목 일봉에 해당 날짜가 있으면 영업일)."""
    ymd = date.strftime("%Y%m%d")
    try:
        from pykrx import stock

        df = stock.get_market_ohlcv(ymd, ymd, _REF_TICKER)
        return df is not None and not df.empty
    except Exception:
        return date.weekday() < 5
