"""종목 유니버스(마스터) 로더 + 제외 규칙.

설계안 §2: 종목 리스트는 FinanceDataReader(StockListing)가 한 번에 빠르지만,
KRX 페이지 구조 변경으로 컬럼이 자주 바뀐다(가용성 리스크). 따라서:
  1차) FDR StockListing → 컬럼 방어적 정규화
  폴백) pykrx 티커 목록 + 종목명 루프
둘 중 하나는 동작하도록 한다(graceful degradation).
"""
from __future__ import annotations

import pandas as pd

import config
from core.data import cache
from core.data.calendar import recent_business_day

_KEY = "universe"


def _is_preferred(ticker: str, name: str) -> bool:
    """우선주 여부. 보통주 코드는 보통 '0'으로 끝나고, 우선주는 5/7/9/K/L/M 등으로 끝난다.
    이름 끝의 '우'/'우B'도 함께 본다.
    """
    if not ticker.endswith("0"):
        return True
    if name.endswith("우") or name.endswith("우B") or "우선주" in name:
        return True
    return False


def _is_excluded_name(name: str) -> bool:
    return any(kw in name for kw in config.EXCLUDE_NAME_KEYWORDS)


def _normalize_fdr(df: pd.DataFrame) -> pd.DataFrame:
    """FDR StockListing 결과의 컬럼명을 버전 무관하게 ticker/name/market으로 정규화."""
    colmap = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("code", "symbol"):
            colmap[c] = "ticker"
        elif cl == "name":
            colmap[c] = "name"
        elif cl == "market":
            colmap[c] = "market"
        elif cl in ("marcap", "marketcap"):
            colmap[c] = "marcap"
    df = df.rename(columns=colmap)
    if not {"ticker", "name"}.issubset(df.columns):
        raise ValueError(f"FDR 컬럼 형식이 예상과 다릅니다: {list(df.columns)}")
    df = df.copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    if "market" not in df.columns:
        df["market"] = "UNKNOWN"
    keep = [c for c in ("ticker", "name", "market") if c in df.columns]
    return df[keep]


def _load_via_fdr() -> pd.DataFrame:
    import FinanceDataReader as fdr  # 지연 import: 미설치 시 폴백 가능

    raw = fdr.StockListing("KRX")
    df = _normalize_fdr(raw)
    # 대상 시장만 (KONEX 제외). market 값이 비표준일 수 있어 대문자 비교.
    df = df[df["market"].astype(str).str.upper().isin(config.MARKETS)]
    if df.empty:
        raise ValueError("FDR가 대상 시장 종목을 반환하지 않았습니다.")
    return df


def _load_via_pykrx() -> pd.DataFrame:
    from pykrx import stock

    date = recent_business_day()
    rows = []
    for market in config.MARKETS:
        for tk in stock.get_market_ticker_list(date, market=market):
            rows.append(
                {"ticker": tk, "name": stock.get_market_ticker_name(tk), "market": market}
            )
    return pd.DataFrame(rows)


def load_universe(force: bool = False) -> pd.DataFrame:
    """종목 마스터를 반환.

    컬럼: ticker, name, market, is_preferred, is_excluded
    """
    if not force:
        cached = cache.load(_KEY) if cache.is_fresh(_KEY) else None
        if cached is not None:
            return cached

    try:
        df = _load_via_fdr()
    except Exception:
        # FDR 실패(컬럼 변경/미설치/네트워크) → pykrx 폴백
        df = _load_via_pykrx()

    df = df.drop_duplicates(subset="ticker").reset_index(drop=True)
    df["is_preferred"] = [_is_preferred(t, n) for t, n in zip(df["ticker"], df["name"])]
    df["is_excluded"] = df["name"].map(_is_excluded_name) | df["is_preferred"]
    cache.save(_KEY, df)
    return df
