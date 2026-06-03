"""supply.summarize_flows 단위 테스트 (순수 로직, 합성 DataFrame).

네트워크/네이버 호출 없이 수급 요약 규칙을 검증한다.
"""
from __future__ import annotations

import pandas as pd
import pytest

from core.analytics.supply import summarize_flows


def _flows(inst, foreign, hold=None):
    """일별 순매매 합성 DataFrame. inst/foreign는 리스트(오래된→최신)."""
    n = len(inst)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    data = {
        "inst_net": inst,
        "foreign_net": foreign,
        "retail_net": [-(i + f) for i, f in zip(inst, foreign)],
    }
    if hold is not None:
        data["foreign_hold_pct"] = hold
    return pd.DataFrame(data, index=idx)


def test_empty_returns_locked_shape():
    out = summarize_flows(None)
    assert out["grade"] is None
    assert out["windows"] == {}
    assert out["facts"] == ["수급 데이터 없음"]

    out2 = summarize_flows(pd.DataFrame())
    assert out2["grade"] is None


def test_both_buying_is_good():
    # 기관·외국인 모두 20일 순매수 → 양호
    flows = _flows([100] * 20, [200] * 20)
    out = summarize_flows(flows, windows=(5, 20, 60))
    assert out["both_buying"] is True
    assert out["both_selling"] is False
    assert out["grade"] == "양호"


def test_both_selling_is_caution():
    flows = _flows([-100] * 20, [-200] * 20)
    out = summarize_flows(flows, windows=(5, 20, 60))
    assert out["both_selling"] is True
    assert out["grade"] == "주의"


def test_mixed_is_normal():
    flows = _flows([100] * 20, [-200] * 20)
    out = summarize_flows(flows, windows=(5, 20, 60))
    assert out["both_buying"] is False
    assert out["both_selling"] is False
    assert out["grade"] == "보통"


def test_window_sums_use_last_n():
    # 25일치: 마지막 5일 기관합 = 5*10, 20일합 = 20*10
    flows = _flows([10] * 25, [5] * 25)
    out = summarize_flows(flows, windows=(5, 20))
    assert out["windows"][5]["기관"] == pytest.approx(50)
    assert out["windows"][20]["기관"] == pytest.approx(200)
    assert out["windows"][5]["외국인"] == pytest.approx(25)


def test_foreign_hold_change_computed():
    flows = _flows([1] * 10, [1] * 10, hold=[40.0 + i * 0.1 for i in range(10)])
    out = summarize_flows(flows, windows=(5, 20, 60))
    assert out["foreign_hold_pct"] == pytest.approx(40.9)
    # 최장 윈도우(60>10 → 전체) 구간 변화 = 마지막 - 처음
    assert out["foreign_hold_change"] == pytest.approx(0.9)


def test_trend_labels():
    assert summarize_flows(_flows([5] * 5, [5] * 5), windows=(5,))["inst_trend"] == "순매수"
    assert summarize_flows(_flows([-5] * 5, [5] * 5), windows=(5,))["inst_trend"] == "순매도"
    assert summarize_flows(_flows([0] * 5, [5] * 5), windows=(5,))["inst_trend"] == "중립"


def test_facts_are_strings():
    out = summarize_flows(_flows([100] * 20, [200] * 20, hold=[48.0] * 20))
    assert all(isinstance(f, str) for f in out["facts"])
    assert any("기관" in f for f in out["facts"])
    assert any("외국인 보유율" in f for f in out["facts"])
