"""screening.apply_screen 단위 테스트 (합성 DataFrame 주입, 네트워크 없음)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from core.analytics import screening


def _make_scored() -> pd.DataFrame:
    """프리셋/필터 검증용 작은 합성 scored 스냅샷.

    유동성 통과(시총·거래대금 충분)와 탈락을 섞고,
    PER/PBR/DIV/각 sub-score를 의도적으로 배치한다.
    """
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004", "000005", "000006"],
            "name": ["우량가치", "고배당주", "대형안정", "적자종목", "소형주", "코스닥A"],
            "market": ["KOSPI", "KOSPI", "KOSPI", "KOSPI", "KOSPI", "KOSDAQ"],
            "PER": [8.0, 12.0, 15.0, -5.0, 9.0, 7.0],
            "PBR": [0.8, 1.5, 1.2, 2.0, 1.1, 0.9],
            "DIV": [1.0, 5.0, 2.0, 0.0, 3.0, 4.0],
            "시가총액": [
                5_000_000_000_000,   # 5조 - 대형
                3_000_000_000_000,   # 3조
                8_000_000_000_000,   # 8조 - 최대형
                2_000_000_000_000,   # 2조
                10_000_000_000,      # 100억 - 시총 하한 미달(300억 < )
                1_000_000_000_000,   # 1조
            ],
            "거래대금": [
                10_000_000_000,
                8_000_000_000,
                12_000_000_000,
                5_000_000_000,
                500_000_000,
                50_000_000,          # 5천만 - 거래대금 하한(1억) 미달
            ],
            "value_score": [90.0, 40.0, 55.0, np.nan, 75.0, 85.0],
            "quality_score": [80.0, 50.0, 60.0, 30.0, 45.0, 70.0],
            "income_score": [20.0, 95.0, 50.0, np.nan, 70.0, 80.0],
            "score": [63.3, 61.7, 55.0, 30.0, 63.3, 78.3],
        }
    )


def test_공통필터_유동성하한_적용():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive")
    # 005(시총 미달)·006(거래대금 미달)은 공통 유동성 필터에서 탈락
    assert "000005" not in out["ticker"].values
    assert "000006" not in out["ticker"].values


def test_시장필터_코스닥만():
    df = _make_scored()
    # 코스닥 종목(006)은 거래대금 미달이라 0건이어야 함 → 시장 필터 동작 확인용으로
    # 거래대금을 충분히 올린 변형
    df = df.copy()
    df.loc[df["ticker"] == "000006", "거래대금"] = 9_000_000_000
    df.loc[df["ticker"] == "000006", "시가총액"] = 1_000_000_000_000
    out = screening.apply_screen(df, "comprehensive", market="코스닥")
    assert set(out["market"].unique()) == {"KOSDAQ"}
    assert "000006" in out["ticker"].values


def test_이름검색_부분일치():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive", query="고배당")
    assert list(out["ticker"].values) == ["000002"]


def test_종합추천_score_내림차순_정렬():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive")
    scores = list(out["score"].values)
    assert scores == sorted(scores, reverse=True)


def test_상위_limit_제한():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive", limit=2)
    assert len(out) == 2


def test_입력_비파괴():
    df = _make_scored()
    before = df.copy(deep=True)
    screening.apply_screen(df, "comprehensive")
    pd.testing.assert_frame_equal(df, before)


def test_알수없는_프리셋_키_에러():
    df = _make_scored()
    with pytest.raises(KeyError):
        screening.apply_screen(df, "없는프리셋")


def test_저평가_프리셋_per_pbr_양수만():
    df = _make_scored()
    # 적자종목(004, PER=-5)은 PER>0 조건에서 탈락. 단 공통 필터(시총·거래대금)는 통과시킴.
    out = screening.apply_screen(df, "value")
    assert (out["PER"] > 0).all()
    assert (out["PBR"] > 0).all()
    assert "000004" not in out["ticker"].values


def test_저평가_프리셋_value_quality_평균_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "value")
    key = (out["value_score"] + out["quality_score"]) / 2
    assert list(key.values) == sorted(key.values, reverse=True)
    # value_score 90·quality 80 인 001이 선두
    assert out.iloc[0]["ticker"] == "000001"


def test_배당_프리셋_div_양수만():
    df = _make_scored()
    out = screening.apply_screen(df, "income")
    assert (out["DIV"] > 0).all()
    # DIV=0 인 적자종목(004)은 제외
    assert "000004" not in out["ticker"].values


def test_배당_프리셋_income_score_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "income")
    inc = list(out["income_score"].values)
    assert inc == sorted(inc, reverse=True)
    # income_score 95 인 고배당주(002)가 선두
    assert out.iloc[0]["ticker"] == "000002"


def test_안정대형주_시총_백분위_하한(monkeypatch):
    # STABLE_CAP_PERCENTILE 을 50으로 낮춰 상위 절반만 남는지 확인(공통 필터 후 4종목 기준).
    monkeypatch.setattr(config, "STABLE_CAP_PERCENTILE", 50)
    df = _make_scored()
    out = screening.apply_screen(df, "stable")
    # 공통 필터 통과 집합(001,002,003,004) 중 시총 상위 절반 → 003(8조),001(5조)
    assert set(out["ticker"].values) == {"000001", "000003"}


def test_안정대형주_시가총액_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "stable")
    caps = list(out["시가총액"].values)
    assert caps == sorted(caps, reverse=True)


def test_정렬키_NaN_제외():
    # 정렬 키(score)가 NaN 인 행은 결과에서 빠진다.
    df = _make_scored()
    df = df.copy()
    df.loc[df["ticker"] == "000001", "score"] = np.nan
    out = screening.apply_screen(df, "comprehensive")
    assert "000001" not in out["ticker"].values


def test_결과_0건_빈_DataFrame():
    df = _make_scored()
    # 시총 하한을 비현실적으로 높여 모두 탈락
    out = screening.apply_screen(df, "comprehensive", min_cap=1e18)
    assert isinstance(out, pd.DataFrame)
    assert len(out) == 0
    # 컬럼 구조는 보존되어 UI가 깨지지 않게 한다.
    assert "ticker" in out.columns
