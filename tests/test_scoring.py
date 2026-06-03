"""scoring 순수 로직 단위 테스트 (합성 DataFrame 주입, 네트워크 없음)."""
from __future__ import annotations

import pandas as pd

from core.analytics.scoring import metric_percentile, percentile_of


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
