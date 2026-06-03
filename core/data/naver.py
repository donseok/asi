"""네이버 금융 무키 데이터 소스.

KRX 데이터포털이 수급/밸류에이션 등을 로그인 필수로 잠갔기 때문에(Phase 0a 무키 정책),
키 없이 얻을 수 있는 네이버 금융 공개 페이지를 종목 상세용 보강 소스로 사용한다.

제공:
- get_supply_demand(): 기관/외국인 일별 순매매량 + 외국인 보유율 (frgn 페이지)
- get_overview():      PER/PBR/EPS/BPS/배당수익률/추정/동일업종PER (main 페이지 투자지표)
- get_financials():    기업실적분석(매출·영업이익·순이익·ROE·부채비율·EPS/PER/BPS/PBR·배당 추세)
- get_peers():         동일업종 비교표(외국인 보유율 포함)

설계 원칙(가용성 리스크 완화):
- 표는 '고정 인덱스'가 아니라 **셀 내용**으로 탐지한다(네이버 구조 변경 방어).
- 각 함수는 실패 시 빈 결과를 돌려주고 호출자(화면)가 'N/A'로 graceful degrade 한다.
- ticker별 parquet 캐시(core.data.cache)를 재사용한다.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional

import pandas as pd
import requests

from core.data import cache

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 10
_BASE = "https://finance.naver.com/item"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Referer": "https://finance.naver.com/"})
    return s


def _fetch_tables(url: str, sess: Optional[requests.Session] = None) -> List[pd.DataFrame]:
    """URL의 모든 HTML 표를 DataFrame 리스트로. 실패 시 빈 리스트."""
    try:
        sess = sess or _session()
        resp = sess.get(url, timeout=_TIMEOUT)
        # 네이버 금융 페이지는 meta charset이 UTF-8이다(frgn은 HTTP 헤더가 EUC-KR로
        # 잘못 알려주므로 명시적으로 UTF-8 고정해야 한글 라벨이 깨지지 않는다).
        resp.encoding = "utf-8"
        return pd.read_html(io.StringIO(resp.text))
    except Exception:
        return []


def _to_num(value) -> Optional[float]:
    """'11,500' '+3.30%' '29.14배' '48.11%' '1,338,734' 등 → float. 실패 시 None."""
    if value is None:
        return None
    s = str(value)
    # 부호 추출(상승/하락 한글 표기 대비)
    neg = "-" in s or "하락" in s
    s = s.replace(",", "")
    m = re.search(r"-?\d+\.?\d*", s)
    if not m:
        return None
    try:
        num = float(m.group())
    except ValueError:
        return None
    if neg and num > 0:
        num = -num
    return num


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """MultiIndex 컬럼을 단일 문자열로 평탄화."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " ".join(str(x) for x in tup if str(x) != "nan").strip()
            for tup in df.columns
        ]
    return df


# ──────────────────────────────────────────────────────────────────────
# 수급 (기관/외국인 일별 순매매 + 외국인 보유율)
# ──────────────────────────────────────────────────────────────────────
def get_supply_demand(ticker: str, days: int = 60, force: bool = False) -> pd.DataFrame:
    """기관/외국인 일별 순매매량 + 외국인 보유율.

    컬럼: close, volume, inst_net(기관 순매매량), foreign_net(외국인 순매매량),
          foreign_hold_pct(외국인 보유율 %), retail_net(개인 근사 = -(기관+외국인)).
    index=date(datetime). 데이터 없으면 빈 DataFrame.
    """
    ticker = str(ticker).zfill(6)
    key = f"naver_flows_{ticker}"
    if not force:
        cached = cache.load(key) if cache.is_fresh(key) else None
        if cached is not None:
            return cached

    sess = _session()
    pages = max(1, min(5, days // 18 + 1))
    frames = []
    for p in range(1, pages + 1):
        url = f"{_BASE}/frgn.naver?code={ticker}&page={p}"
        tables = _fetch_tables(url, sess)
        target = None
        for t in tables:
            if t.shape[0] > 3 and t.shape[1] >= 8:
                target = t
                break
        if target is None:
            continue
        frames.append(target)

    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    # 컬럼은 보통 [날짜, 종가, 전일비, 등락률, 거래량, 기관(순매매량),
    #             외국인(순매매량), 외국인(보유주수), 외국인(보유율)] (MultiIndex)
    cols = list(raw.columns)
    try:
        out = pd.DataFrame({
            "date": raw[cols[0]],
            "close": raw[cols[1]].map(_to_num),
            "volume": raw[cols[4]].map(_to_num),
            "inst_net": raw[cols[5]].map(_to_num),
            "foreign_net": raw[cols[6]].map(_to_num),
            "foreign_hold_pct": raw[cols[8]].map(_to_num),
        })
    except (IndexError, KeyError):
        return pd.DataFrame()

    out["date"] = pd.to_datetime(out["date"], format="%Y.%m.%d", errors="coerce")
    out = out.dropna(subset=["date"]).drop_duplicates(subset="date")
    out = out.set_index("date").sort_index()
    # 개인 근사(기타법인 제외) = -(기관 + 외국인)
    out["retail_net"] = -(out["inst_net"].fillna(0) + out["foreign_net"].fillna(0))
    out = out.tail(days)

    if not out.empty:
        cache.save(key, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# overview (투자지표: PER/PBR/EPS/BPS/배당/추정/동일업종PER + 외국인보유율)
# ──────────────────────────────────────────────────────────────────────
def _parse_pair(text: str) -> tuple[Optional[float], Optional[float]]:
    """'29.14배 l 12,372원' 같은 'A l B' 쌍에서 (A, B) 추출."""
    parts = re.split(r"[lℓ|]", str(text))
    a = _to_num(parts[0]) if len(parts) >= 1 else None
    b = _to_num(parts[1]) if len(parts) >= 2 else None
    return a, b


def get_overview(ticker: str, force: bool = False) -> dict:
    """투자지표 요약 dict.

    키: per, eps, est_per, est_eps, pbr, bps, div_yield, sector_per, foreign_hold_pct.
    값이 없으면 해당 키는 None. 전부 실패하면 빈 dict.
    """
    ticker = str(ticker).zfill(6)
    key = f"naver_overview_{ticker}"
    if not force:
        cached = cache.load(key) if cache.is_fresh(key) else None
        if cached is not None and not cached.empty:
            return {k: (None if pd.isna(v) else v) for k, v in cached.iloc[0].to_dict().items()}

    tables = _fetch_tables(f"{_BASE}/main.naver?code={ticker}")
    info: dict = {
        "per": None, "eps": None, "est_per": None, "est_eps": None,
        "pbr": None, "bps": None, "div_yield": None,
        "sector_per": None, "foreign_hold_pct": None,
    }

    # 투자지표 블록: 첫 셀에 'PER'와 'EPS'가 함께 있는 작은 2열 표
    for t in tables:
        if t.shape[1] != 2:
            continue
        s = t.astype(str)
        joined = " ".join(s.iloc[:, 0].tolist())
        if "PER" in joined and "EPS" in joined:
            for _, rowv in t.iterrows():
                label, val = str(rowv.iloc[0]), rowv.iloc[1]
                if "추정" in label and "PER" in label:
                    info["est_per"], info["est_eps"] = _parse_pair(val)
                elif "PER" in label and "EPS" in label:
                    info["per"], info["eps"] = _parse_pair(val)
                elif "PBR" in label and "BPS" in label:
                    info["pbr"], info["bps"] = _parse_pair(val)
                elif "배당수익률" in label:
                    info["div_yield"] = _to_num(val)
            break

    # 동일업종 PER (별도 2열 표)
    for t in tables:
        s = t.astype(str)
        flat = " ".join(s.values.ravel().tolist())
        if "동일업종 PER" in flat:
            for _, rowv in t.iterrows():
                if "동일업종 PER" in str(rowv.iloc[0]):
                    info["sector_per"] = _to_num(rowv.iloc[1])
            break

    # 외국인 보유율: 동일업종 비교표 첫 종목 컬럼의 '외국인비율' 행
    peers = get_peers(ticker, force=force)
    if not peers.empty and "외국인비율" in peers.columns:
        try:
            info["foreign_hold_pct"] = _to_num(peers.iloc[0]["외국인비율"])
        except Exception:
            pass

    if any(v is not None for v in info.values()):
        cache.save(key, pd.DataFrame([info]))
    return info


# ──────────────────────────────────────────────────────────────────────
# 기업실적분석 (재무 추세)
# ──────────────────────────────────────────────────────────────────────
def get_financials(ticker: str, force: bool = False) -> pd.DataFrame:
    """기업실적분석 표 → index=재무항목, columns=기간(연간+분기, (E)=추정).

    행: 매출액·영업이익·당기순이익·영업이익률·순이익률·ROE·부채비율·EPS·PER·BPS·PBR·
        주당배당금·시가배당률·배당성향 등(네이버 제공분). 데이터 없으면 빈 DataFrame.
    """
    ticker = str(ticker).zfill(6)
    key = f"naver_financials_{ticker}"
    if not force:
        cached = cache.load(key) if cache.is_fresh(key) else None
        if cached is not None:
            return cached

    tables = _fetch_tables(f"{_BASE}/main.naver?code={ticker}")
    target = None
    for t in tables:
        s = t.astype(str)
        flat = " ".join(s.values.ravel()[:40].tolist())
        if ("매출액" in flat and "영업이익" in flat) or ("주요재무정보" in flat):
            target = t
            break
    if target is None:
        return pd.DataFrame()

    df = _flatten_cols(target)
    # 첫 컬럼 = 재무항목 라벨 → 인덱스
    first = df.columns[0]
    df = df.rename(columns={first: "항목"})
    df["항목"] = df["항목"].astype(str).str.strip()
    df = df[df["항목"] != "nan"].set_index("항목")

    # 기간 컬럼 라벨 간결화: '최근 연간 실적 2023.12 IFRS연결' → '연 2023.12',
    # '최근 분기 실적 2025.03 ...' → '분 2025.03'. (E)=추정 표기는 보존.
    def _short(col: str) -> str:
        period = ""
        m = re.search(r"\d{4}\.\d{2}(\(E\))?", str(col))
        if m:
            period = m.group()
        prefix = "연 " if "연간" in str(col) else ("분 " if "분기" in str(col) else "")
        return (prefix + period).strip() or str(col)

    df.columns = [_short(c) for c in df.columns]
    # 숫자화(표시는 호출자가 포맷)
    for c in df.columns:
        df[c] = df[c].map(_to_num)
    df = df.dropna(how="all")

    if not df.empty:
        cache.save(key, df)
    return df


# ──────────────────────────────────────────────────────────────────────
# 동일업종 비교
# ──────────────────────────────────────────────────────────────────────
def get_peers(ticker: str, force: bool = False) -> pd.DataFrame:
    """동일업종 비교표 → index=종목(이름*코드), columns=지표(현재가/등락률/시총/외국인비율/...).

    데이터 없으면 빈 DataFrame.
    """
    ticker = str(ticker).zfill(6)
    key = f"naver_peers_{ticker}"
    if not force:
        cached = cache.load(key) if cache.is_fresh(key) else None
        if cached is not None:
            return cached

    tables = _fetch_tables(f"{_BASE}/main.naver?code={ticker}")
    target = None
    for t in tables:
        s = t.astype(str)
        first_col = " ".join(s.iloc[:, 0].tolist())
        # 동일업종 비교표는 첫 열에 '현재가/외국인비율' 같은 지표 라벨이 온다
        if "현재가" in first_col and ("외국인비율" in first_col or "시가총액" in first_col):
            target = t
            break
    if target is None:
        return pd.DataFrame()

    df = _flatten_cols(target)
    label_col = df.columns[0]
    df = df.rename(columns={label_col: "_metric"})
    df["_metric"] = (
        df["_metric"].astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)  # '시가총액(억)' → '시가총액'
        .str.replace(r"\s+", "", regex=True)
    )
    df = df[df["_metric"] != "nan"].set_index("_metric")
    # 종목(컬럼) × 지표(행) → 전치: 종목이 행
    out = df.T
    out.index.name = "종목"

    if not out.empty:
        cache.save(key, out)
    return out
