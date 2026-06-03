"""checklist.build_checklist 단위 테스트 (순수 로직, 합성 DataFrame 주입).

외부 모듈 함수(labels.verdict_*, price_context.ma_alignment/overheating,
indicators.latest_signals, flags.compute_risk_flags)는 다른 태스크에서 구현된다.
여기서는 checklist가 그 함수들을 '시그니처대로 호출'하는지 검증하기 위해
monkeypatch로 결정론적 더블을 주입한다.
"""
from __future__ import annotations

import pandas as pd
import pytest

from core.analytics import checklist


def _make_ohlcv(n: int = 130) -> pd.DataFrame:
    """완만히 우상향하는 합성 일봉. 지표 계산에 충분한 길이."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = pd.Series(range(1000, 1000 + n), index=idx, dtype="float64")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 5,
            "low": close - 5,
            "close": close,
            "volume": 10_000,
            "value": 1_000_000_000,
        },
        index=idx,
    )


def _patch_externals(monkeypatch, *, ma="정배열", overheat="보통",
                     risk=None, signals=None):
    """checklist가 부르는 외부 함수들을 결정론적 더블로 치환."""
    if risk is None:
        risk = []
    if signals is None:
        signals = {"rsi": 55.0, "rsi_state": "중립", "macd_hist": 1.2,
                   "above_sma20": True}
    monkeypatch.setattr(checklist, "ma_alignment", lambda ohlcv: ma)
    monkeypatch.setattr(
        checklist, "overheating",
        lambda ohlcv: {"level": overheat, "components": {}},
    )
    monkeypatch.setattr(checklist, "compute_risk_flags", lambda ohlcv: list(risk))
    monkeypatch.setattr(checklist, "latest_signals", lambda ohlcv: dict(signals))
    # verdict_*는 (label, tone)을 반환. 등급 산출은 checklist 내부 백분위 로직이 담당.
    monkeypatch.setattr(checklist, "verdict_value", lambda row: ("저평가", "good"))
    monkeypatch.setattr(checklist, "verdict_quality", lambda row: ("우량", "good"))


def _row(value_score=85.0, quality_score=80.0, income_score=50.0):
    return pd.Series(
        {
            "ticker": "005930",
            "name": "삼성전자",
            "value_score": value_score,
            "quality_score": quality_score,
            "income_score": income_score,
            "PER": 8.0,
            "PBR": 1.1,
            "ROE_approx": 14.0,
            "DIV": 2.5,
        }
    )


def test_returns_six_axes_in_order(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    assert [a["axis"] for a in out] == ["가치", "기술", "리스크", "심리", "성장", "수급"]


def test_four_active_two_locked(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    by_axis = {a["axis"]: a for a in out}
    for name in ("가치", "기술", "리스크", "심리"):
        assert by_axis[name]["active"] is True
    for name in ("성장", "수급"):
        assert by_axis[name]["active"] is False
        assert by_axis[name]["grade"] is None
        assert by_axis[name]["locked_reason"]  # 비어있지 않은 잠금 사유


def test_no_aggregate_buy_score_field(monkeypatch):
    """🔴 면책: 6축을 합산한 '매수점수' 필드를 절대 만들지 않는다."""
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    # 결과는 list[Axis]이며 dict 합산 점수 컨테이너가 아니다.
    assert isinstance(out, list)
    forbidden = {"매수점수", "총점", "buy_score", "total", "합산", "종합점수"}
    for axis in out:
        assert forbidden.isdisjoint(axis.keys())
        # 어떤 축에도 '합산'을 암시하는 숫자 점수 키가 없어야 한다.
        assert "score" not in axis


def test_value_axis_grade_high_when_percentiles_high(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(value_score=90.0, quality_score=88.0),
        _make_ohlcv(), [], scored=pd.DataFrame(),
    )
    value = next(a for a in out if a["axis"] == "가치")
    assert value["grade"] == "양호"
    assert any("PER" in f or "PBR" in f or "ROE" in f or "백분위" in f
               for f in value["facts"])


def test_value_axis_grade_caution_when_percentiles_low(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(value_score=20.0, quality_score=15.0),
        _make_ohlcv(), [], scored=pd.DataFrame(),
    )
    value = next(a for a in out if a["axis"] == "가치")
    assert value["grade"] == "주의"


def test_value_axis_grade_normal_in_middle(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(value_score=55.0, quality_score=52.0),
        _make_ohlcv(), [], scored=pd.DataFrame(),
    )
    value = next(a for a in out if a["axis"] == "가치")
    assert value["grade"] == "보통"


def test_tech_axis_uses_ma_and_signals(monkeypatch):
    _patch_externals(
        monkeypatch, ma="정배열",
        signals={"rsi": 58.0, "rsi_state": "중립", "macd_hist": 2.0,
                 "above_sma20": True},
    )
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    tech = next(a for a in out if a["axis"] == "기술")
    assert tech["active"] is True
    joined = " ".join(tech["facts"])
    assert "정배열" in joined
    assert "RSI" in joined
    assert "MACD" in joined


def test_tech_axis_caution_on_reverse_alignment(monkeypatch):
    _patch_externals(
        monkeypatch, ma="역배열",
        signals={"rsi": 25.0, "rsi_state": "과매도(≤30)", "macd_hist": -1.5,
                 "above_sma20": False},
    )
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    tech = next(a for a in out if a["axis"] == "기술")
    assert tech["grade"] == "주의"


def test_risk_axis_lists_flags_and_grade(monkeypatch):
    flags = ["⚠️ 고변동성 — 최근 20일 일간 변동성이 큼"]
    _patch_externals(monkeypatch, risk=flags)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), flags, scored=pd.DataFrame()
    )
    risk = next(a for a in out if a["axis"] == "리스크")
    assert risk["active"] is True
    assert risk["facts"] == flags
    # 플래그가 있으면 '양호'가 아니다.
    assert risk["grade"] in ("보통", "주의")


def test_risk_axis_good_when_no_flags(monkeypatch):
    _patch_externals(monkeypatch, risk=[])
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    risk = next(a for a in out if a["axis"] == "리스크")
    assert risk["grade"] == "양호"
    assert any("정상" in f or "없" in f for f in risk["facts"])


def test_sentiment_axis_follows_overheating(monkeypatch):
    """심리축 = 과열도 프록시 등급 연동(게시판 아님)."""
    _patch_externals(monkeypatch, overheat="과열")
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    sentiment = next(a for a in out if a["axis"] == "심리")
    assert sentiment["active"] is True
    assert sentiment["grade"] == "주의"  # 과열 → 주의
    assert any("과열" in f for f in sentiment["facts"])


def test_sentiment_axis_good_when_low(monkeypatch):
    _patch_externals(monkeypatch, overheat="낮음")
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    sentiment = next(a for a in out if a["axis"] == "심리")
    assert sentiment["grade"] == "양호"


def test_locked_axes_reason_text(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    by_axis = {a["axis"]: a for a in out}
    assert "DART" in by_axis["성장"]["locked_reason"]
    # flows_summary 미전달 → 수급 축은 잠금(데이터 없음 사유 노출)
    assert by_axis["수급"]["active"] is False
    assert by_axis["수급"]["locked_reason"] is not None
    assert "수급" in by_axis["수급"]["locked_reason"]


def test_supply_axis_active_with_flows_summary(monkeypatch):
    # flows_summary가 있으면 수급 축이 활성화되고 등급/사실이 노출된다.
    _patch_externals(monkeypatch)
    summary = {"grade": "양호", "facts": ["기관 20일 순매수 (+1,000주)"]}
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame(), flows_summary=summary
    )
    supply = next(a for a in out if a["axis"] == "수급")
    assert supply["active"] is True
    assert supply["grade"] == "양호"
    assert supply["locked_reason"] is None
    assert any("기관" in f for f in supply["facts"])


def test_active_axes_have_locked_reason_none(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    for axis in out:
        if axis["active"]:
            assert axis["locked_reason"] is None


def test_every_axis_has_full_schema(monkeypatch):
    _patch_externals(monkeypatch)
    out = checklist.build_checklist(
        _row(), _make_ohlcv(), [], scored=pd.DataFrame()
    )
    expected_keys = {"axis", "active", "grade", "facts", "locked_reason"}
    for axis in out:
        assert set(axis.keys()) == expected_keys
        assert isinstance(axis["facts"], list)
