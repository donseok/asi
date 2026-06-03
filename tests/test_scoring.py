"""scoring 순수 로직 단위 테스트 (합성 DataFrame 주입, 네트워크 없음)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.analytics.scoring import (
    _lower_is_better,
    compute_scores,
    metric_percentile,
    percentile_of,
)


def _sample_scored() -> pd.DataFrame:
    """6종목 합성 스냅샷. ticker는 6자리 문자열, 컬럼은 실제 스냅샷 형태."""
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004", "000005", "000006"],
            "score": [10.0, 30.0, 50.0, 70.0, 90.0, float("nan")],
            "PER": [5.0, 8.0, 12.0, 20.0, 40.0, float("nan")],
            "DIV": [6.0, 4.0, 3.0, 2.0, 1.0, 0.0],
        }
    )


def test_percentile_of_basic():
    """percentile_of: 값 이하 비율 × 100 (백필)."""
    df = _sample_scored()
    # score=50.0 인 000003: 50 이하인 값(10,30,50)=3개 / 유효 5개 → 60%
    assert percentile_of(df, "000003", "score") == 60.0


def test_metric_percentile_higher_is_better():
    """lower_is_better=False: 큰 값일수록 높은 백분위."""
    df = _sample_scored()
    # DIV=6.0 인 000001: 6 이하인 값(전부 6개) → 100%
    assert metric_percentile(df, "000001", "DIV") == 100.0
    # DIV=3.0 인 000003: 3 이하(0,1,2,3)=4개 / 6개 → 66.67%
    assert metric_percentile(df, "000003", "DIV") == round(4 / 6 * 100, 10) or \
        abs(metric_percentile(df, "000003", "DIV") - (4 / 6 * 100)) < 1e-9


def test_metric_percentile_lower_is_better():
    """lower_is_better=True: 저PER이 '하위 X%(저렴)'로 100-백분위가 되어 높게 나온다."""
    df = _sample_scored()
    # PER 유효값: [5,8,12,20,40]. PER=5.0(000001)은 최저 → 가장 저렴 → 100에 가까움.
    p_low = metric_percentile(df, "000001", "PER", lower_is_better=True)
    p_high = metric_percentile(df, "000005", "PER", lower_is_better=True)
    # 저PER이 고PER보다 더 높은(저렴) 백분위
    assert p_low > p_high
    # PER=5는 최저값 → 100 - (5 이하 비율=1/5×100=20) = 80
    assert p_low == 80.0
    # PER=40은 최고값 → 100 - (40 이하 비율=5/5×100=100) = 0
    assert p_high == 0.0


def test_metric_percentile_lower_is_better_ignores_nonpositive():
    """lower_is_better=True는 0 이하(적자/무효) PER을 분포에서 제외한다."""
    df = _sample_scored()
    df.loc[df["ticker"] == "000006", "PER"] = -3.0  # 적자
    # 적자 종목 자신은 None (분포에서 제외 → 값 없음)
    assert metric_percentile(df, "000006", "PER", lower_is_better=True) is None
    # 정상 종목 PER=5: 유효분포 여전히 [5,8,12,20,40] → 80.0 유지
    assert metric_percentile(df, "000001", "PER", lower_is_better=True) == 80.0


def test_metric_percentile_none_cases():
    """NaN 값 / 없는 티커 / 없는 컬럼 / ticker 컬럼 부재 → None."""
    df = _sample_scored()
    # NaN score (000006)
    assert metric_percentile(df, "000006", "score") is None
    # 없는 티커
    assert metric_percentile(df, "999999", "score") is None
    # 없는 컬럼
    assert metric_percentile(df, "000001", "NOPE") is None
    # ticker 컬럼 자체가 없음
    no_ticker = df.drop(columns=["ticker"])
    assert metric_percentile(no_ticker, "000001", "score") is None


def test_metric_percentile_ticker_zfill():
    """티커는 zfill(6)로 정규화되어 정수형 입력도 매칭된다."""
    df = _sample_scored()
    # "1" → "000001"
    assert metric_percentile(df, "1", "DIV") == 100.0


# ── 백필(Task 12): _lower_is_better / compute_scores / percentile_of ──
def test_lower_is_better_excludes_non_positive():
    # 0과 음수(적자/무효)는 제외되어 NaN
    s = pd.Series([10.0, 20.0, 0.0, -5.0])
    out = _lower_is_better(s)
    assert pd.isna(out.iloc[2])  # 0.0 제외
    assert pd.isna(out.iloc[3])  # -5.0 제외
    # 양수는 점수 존재
    assert pd.notna(out.iloc[0])
    assert pd.notna(out.iloc[1])


def test_lower_is_better_lower_value_higher_score():
    # 낮을수록 좋음 → 가장 낮은 양수가 가장 높은 점수
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = _lower_is_better(s)
    # 단조 감소: 값이 커질수록 점수는 낮아진다
    assert out.iloc[0] > out.iloc[1] > out.iloc[2] > out.iloc[3]
    # 백분위 평균 형태이므로 모두 0~100 범위
    assert (out.dropna() >= 0).all()
    assert (out.dropna() <= 100).all()


def _make_snapshot() -> pd.DataFrame:
    # 합성 스냅샷: PER/PBR/ROE_approx/DIV (일부는 적자/무배당)
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004"],
            "PER": [5.0, 10.0, -2.0, 20.0],     # 세 번째는 적자
            "PBR": [0.5, 1.0, 2.0, 3.0],
            "ROE_approx": [15.0, 10.0, 5.0, 1.0],
            "DIV": [4.0, 0.0, 2.0, 1.0],        # 두 번째는 무배당
        }
    )


def test_compute_scores_adds_expected_columns():
    out = compute_scores(_make_snapshot())
    for col in ("value_score", "quality_score", "income_score", "score"):
        assert col in out.columns


def test_compute_scores_does_not_mutate_input():
    snap = _make_snapshot()
    before = snap.copy(deep=True)
    compute_scores(snap)
    # 원본 비파괴: 컬럼/값 동일
    pd.testing.assert_frame_equal(snap, before)


def test_compute_scores_value_nan_for_negative_per_only_pbr():
    # 세 번째 종목: PER<0(제외) BUT PBR>0 → value_score는 PBR 단독 평균(NaN 아님)
    out = compute_scores(_make_snapshot())
    v3 = out.loc[out["ticker"] == "000003", "value_score"].iloc[0]
    assert pd.notna(v3)


def test_compute_scores_income_nan_for_zero_div():
    # 두 번째 종목: DIV=0 → income_score는 NaN
    out = compute_scores(_make_snapshot())
    i2 = out.loc[out["ticker"] == "000002", "income_score"].iloc[0]
    assert pd.isna(i2)


def test_compute_scores_missing_columns_safe():
    # 일부 컬럼(ROE_approx/DIV)이 없어도 깨지지 않고 score 컬럼이 생성됨
    snap = pd.DataFrame(
        {
            "ticker": ["000001", "000002"],
            "PER": [5.0, 10.0],
            "PBR": [0.5, 1.0],
        }
    )
    out = compute_scores(snap)
    assert "score" in out.columns
    # value_score는 존재(PER/PBR 있음)
    assert pd.notna(out["value_score"]).any()


def _scored_for_percentile() -> pd.DataFrame:
    # score 값이 명확한 4종목 (백분위 계산 검증용)
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004"],
            "score": [10.0, 20.0, 30.0, 40.0],
        }
    )


def test_percentile_of_top_is_100():
    scored = _scored_for_percentile()
    # 가장 높은 score(40) 종목 → (모든 값 <= 40) → 100%
    assert percentile_of(scored, "000004") == 100.0


def test_percentile_of_bottom_ratio():
    scored = _scored_for_percentile()
    # 가장 낮은 score(10) → (1/4 값이 <=10) → 25%
    assert percentile_of(scored, "000001") == 25.0


def test_percentile_of_zfills_ticker():
    scored = _scored_for_percentile()
    # 정수형/짧은 티커도 zfill(6)로 매칭되어야 함
    assert percentile_of(scored, "1") == 25.0
    assert percentile_of(scored, 1) == 25.0


def test_percentile_of_custom_column():
    scored = pd.DataFrame(
        {
            "ticker": ["000001", "000002"],
            "value_score": [10.0, 90.0],
        }
    )
    assert percentile_of(scored, "000002", column="value_score") == 100.0


def test_percentile_of_missing_column_returns_none():
    scored = _scored_for_percentile()
    assert percentile_of(scored, "000001", column="없는컬럼") is None


def test_percentile_of_unknown_ticker_returns_none():
    scored = _scored_for_percentile()
    assert percentile_of(scored, "999999") is None


def test_percentile_of_nan_value_returns_none():
    scored = pd.DataFrame(
        {
            "ticker": ["000001", "000002"],
            "score": [np.nan, 50.0],
        }
    )
    # 해당 종목 score가 NaN → None
    assert percentile_of(scored, "000001") is None
