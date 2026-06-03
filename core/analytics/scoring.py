"""결정론적 룰베이스 스코어링 (횡단면 백분위 순위 평균).

설계안 §3 확장 권고 반영:
- z-score 가중합이 아니라 **백분위 순위(percentile rank) 평균** → 이상치에 강건하고
  자의적 가중치 튜닝(과최적화 원천)을 피한다.
- 점수는 '상대 지표'일 뿐 매수 신호가 아니다(UI에 디스클레이머).

서브스코어:
- value  : 저PER, 저PBR (낮을수록 좋음 → 100 - rank)
- quality: ROE_approx (높을수록 좋음)
- income : 배당수익률 DIV (높을수록 좋음)
종합점수 = 존재하는 서브스코어들의 평균.
"""
from __future__ import annotations

import pandas as pd


def _pct_rank(s: pd.Series) -> pd.Series:
    """오름차순 백분위(0~100). 값이 클수록 높은 점수. NaN은 NaN 유지."""
    return s.rank(pct=True) * 100


def _lower_is_better(s: pd.Series) -> pd.Series:
    """낮을수록 좋은 지표(PER/PBR). 0 이하(적자/무효)는 제외."""
    valid = s.where(s > 0)
    return 100 - _pct_rank(valid)


def compute_scores(snapshot: pd.DataFrame) -> pd.DataFrame:
    """스냅샷에 value_score/quality_score/income_score/score 컬럼을 추가해 반환."""
    df = snapshot.copy()

    comp = pd.DataFrame(index=df.index)
    comp["val_PER"] = _lower_is_better(df["PER"]) if "PER" in df else pd.NA
    comp["val_PBR"] = _lower_is_better(df["PBR"]) if "PBR" in df else pd.NA
    comp["qual_ROE"] = _pct_rank(df["ROE_approx"]) if "ROE_approx" in df else pd.NA
    comp["inc_DIV"] = _pct_rank(df["DIV"].where(df["DIV"] > 0)) if "DIV" in df else pd.NA

    df["value_score"] = comp[["val_PER", "val_PBR"]].mean(axis=1)
    df["quality_score"] = comp[["qual_ROE"]].mean(axis=1)
    df["income_score"] = comp[["inc_DIV"]].mean(axis=1)
    df["score"] = df[["value_score", "quality_score", "income_score"]].mean(axis=1)

    return df


def percentile_of(scored: pd.DataFrame, ticker: str, column: str = "score") -> float | None:
    """특정 종목의 점수가 전체에서 차지하는 백분위(0~100)."""
    ticker = str(ticker).zfill(6)
    if column not in scored.columns or "ticker" not in scored.columns:
        return None
    row = scored.loc[scored["ticker"] == ticker, column]
    if row.empty or pd.isna(row.iloc[0]):
        return None
    val = row.iloc[0]
    series = scored[column].dropna()
    return float((series <= val).mean() * 100)
