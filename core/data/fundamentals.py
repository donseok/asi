"""밸류에이션 + 시세 스냅샷.

데이터 소스 정책(Phase 0a, 무키):
- KRX 데이터포털(data.krx.co.kr)이 2025년 이후 시장 스냅샷 엔드포인트
  (PER/PBR/EPS/BPS/DIV/시가총액 by-ticker)를 **로그인 필수**로 잠갔다.
  자격증명이 없으면 pykrx 의 get_market_fundamental / get_market_cap 은
  빈 응답을 받아 실패한다(가용성 리스크).
- 따라서 **1차 소스를 FinanceDataReader(StockListing)** 로 둔다. FDR 은 키 없이
  종가·시가총액·거래대금·상장주식수를 한 번에 준다(밸류에이션은 미제공).
- BPS/PER/PBR/EPS/DIV/DPS/ROE 는 KRX 로그인 자격증명(KRX_ID/KRX_PW)이 있을 때만
  pykrx 로 보강하고, 없으면 NaN 으로 둔다(스코어링/화면이 graceful degradation).

주의: pykrx get_market_fundamental 은 BPS/PER/PBR/EPS/DIV/DPS 만 제공한다.
ROE는 직접 제공하지 않으므로 ROE ≈ EPS/BPS 로 근사하고 'ROE_approx'로 명시한다.
정확한 ROE(당기순이익/자본)는 Phase 0b의 DART 재무로 계산한다.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import config
from core.data import cache

_KEY = "fundamental_snapshot"

# 스냅샷이 항상 보장하는 컬럼(밸류에이션은 소스가 없으면 NaN).
_VALUATION_COLS = ["BPS", "PER", "PBR", "EPS", "DIV", "DPS"]
_NUMERIC_COLS = _VALUATION_COLS + ["종가", "시가총액", "거래대금", "상장주식수", "등락률", "ROE_approx"]


def _normalize_listing(raw: pd.DataFrame) -> pd.DataFrame:
    """FDR StockListing('KRX') 결과를 스냅샷 스키마로 정규화.

    FDR 컬럼(버전별 상이 가능): Code, Name, Market, Close, Amount, Marcap, Stocks ...
    → ticker, market, 종가, 거래대금, 시가총액, 상장주식수.
    """
    colmap = {}
    for c in raw.columns:
        cl = str(c).lower()
        if cl in ("code", "symbol"):
            colmap[c] = "ticker"
        elif cl == "market":
            colmap[c] = "market"
        elif cl == "close":
            colmap[c] = "종가"
        elif cl in ("amount", "tradingvalue"):
            colmap[c] = "거래대금"
        elif cl in ("marcap", "marketcap"):
            colmap[c] = "시가총액"
        elif cl in ("stocks", "shares"):
            colmap[c] = "상장주식수"
        elif cl in ("chagesratio", "changesratio", "changeratio", "chg", "fluctuationrate"):
            # FDR 철자 'ChagesRatio'(오타) = 당일 등락률(%)
            colmap[c] = "등락률"
    df = raw.rename(columns=colmap)

    if "ticker" not in df.columns:
        raise ValueError(f"FDR 컬럼 형식이 예상과 다릅니다: {list(raw.columns)}")
    if "market" not in df.columns:
        df["market"] = "UNKNOWN"

    keep = [c for c in ("ticker", "market", "종가", "거래대금", "시가총액", "상장주식수", "등락률") if c in df.columns]
    df = df[keep].copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    # 대상 시장(KOSPI/KOSDAQ)만. market 값이 비표준일 수 있어 대문자 비교.
    df = df[df["market"].astype(str).str.upper().isin(config.MARKETS)]
    return df


def _load_via_fdr() -> pd.DataFrame:
    import FinanceDataReader as fdr  # 지연 import

    raw = fdr.StockListing("KRX")
    df = _normalize_listing(raw)
    if df.empty:
        raise ValueError("FDR가 대상 시장 종목을 반환하지 않았습니다.")
    return df


def _enrich_valuation_via_pykrx(df: pd.DataFrame) -> pd.DataFrame:
    """KRX 로그인 자격증명이 있을 때만 밸류에이션(PER/PBR/...)을 채운다.

    KRX_ID/KRX_PW 가 없거나 호출이 실패하면 조용히 NaN 으로 둔다(무키 동작 보장).
    """
    if not (os.getenv("KRX_ID") and os.getenv("KRX_PW")):
        return df
    try:
        from pykrx import stock

        from core.data.calendar import recent_business_day

        date = recent_business_day()
        frames = []
        for market in config.MARKETS:
            fund = stock.get_market_fundamental(date, market=market)  # BPS PER PBR EPS DIV DPS
            if fund is None or fund.empty:
                continue
            fund = fund.copy()
            fund.index = fund.index.astype(str).str.zfill(6)
            frames.append(fund)
        if not frames:
            return df
        val = pd.concat(frames)
        val.index.name = "ticker"
        val = val.reset_index()
        val["ticker"] = val["ticker"].astype(str).str.zfill(6)
        # 종가/시총은 FDR 값을 신뢰하고, 밸류에이션 컬럼만 병합.
        cols = ["ticker"] + [c for c in _VALUATION_COLS if c in val.columns]
        df = df.merge(val[cols], on="ticker", how="left")
    except Exception:
        # 로그인 만료/엔드포인트 변경 등 — 무키 동작으로 폴백.
        pass
    return df


def get_fundamental_snapshot(force: bool = False) -> pd.DataFrame:
    """전 종목 밸류에이션 + 시세 스냅샷.

    컬럼: ticker, market, BPS, PER, PBR, EPS, DIV, DPS, 종가, 시가총액, 거래대금,
          상장주식수, ROE_approx
    밸류에이션(BPS/PER/PBR/EPS/DIV/DPS/ROE_approx)은 KRX 자격증명이 없으면 NaN.
    """
    if not force:
        cached = cache.load(_KEY) if cache.is_fresh(_KEY) else None
        if cached is not None:
            return cached

    df = _load_via_fdr()
    df = _enrich_valuation_via_pykrx(df)

    # 보장 컬럼 채우기(없으면 NaN). 다운스트림(스코어링/화면)이 .get/NaN 으로 안전 처리.
    for col in _VALUATION_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # ROE 근사 = EPS / BPS * 100 (%). 0/음수 BPS는 무효 처리. (밸류에이션 없으면 NaN)
    bps = df["BPS"].replace(0, np.nan)
    df["ROE_approx"] = (df["EPS"] / bps * 100).replace([np.inf, -np.inf], np.nan)

    # 숫자 컬럼 형변환(FDR 가 문자열로 줄 수 있음).
    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.reset_index(drop=True)
    cache.save(_KEY, df)
    return df


def has_valuation_data(df: pd.DataFrame) -> bool:
    """스냅샷에 밸류에이션(PER) 데이터가 한 건이라도 있는지.

    스크리너/화면에서 '밸류에이션 미제공(무키)' 안내를 띄울지 판단하는 데 쓴다.
    """
    return "PER" in df.columns and bool(df["PER"].notna().any())
