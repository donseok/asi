"""수급(투자자별 매매) 분석 — 순수 로직.

core.data.naver.get_supply_demand()가 만든 일별 순매매 DataFrame을 받아
기관/외국인/개인(근사) N일 누적 순매수, 추세, 외국인 보유율 변화를 요약한다.
네트워크/Streamlit 호출 없음 — 합성 DataFrame으로 테스트 가능한 순수 함수.

🔴 면책: 수급은 '사실'(누가 얼마나 샀나)일 뿐 매수신호가 아니다. 합산 점수 만들지 않는다.
한국 관습 색은 호출(UI) 측에서 적용한다(순매수=빨강/순매도=파랑).
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import pandas as pd

# 수급 DataFrame이 가져야 하는 순매매 컬럼(기관/외국인/개인 근사).
_NET_COLS = {"inst_net": "기관", "foreign_net": "외국인", "retail_net": "개인"}


def _sum_window(df: pd.DataFrame, col: str, n: int) -> Optional[float]:
    if col not in df.columns or df.empty:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna().tail(n)
    if vals.empty:
        return None
    return float(vals.sum())


def _trend(value: Optional[float]) -> str:
    """누적 순매수 부호 → '순매수'/'순매도'/'중립'."""
    if value is None:
        return "중립"
    if value > 0:
        return "순매수"
    if value < 0:
        return "순매도"
    return "중립"


def summarize_flows(
    flows: Optional[pd.DataFrame],
    windows: Sequence[int] = (5, 20, 60),
) -> Dict:
    """수급 요약.

    반환 dict:
      - windows: {n: {"기관": float|None, "외국인": float|None, "개인": float|None}}
      - foreign_hold_pct: 최근 외국인 보유율(%) 또는 None
      - foreign_hold_change: 가장 긴 윈도우 동안 보유율 변화(%p) 또는 None
      - inst_trend / foreign_trend: 가장 짧은 윈도우(기본 5일) 기준 순매수/순매도/중립
      - both_buying / both_selling: 20일(없으면 최장 윈도우) 기관·외국인 동반 여부
      - grade: 양호/보통/주의 (체크리스트 서열용, 합산점수 아님)
      - facts: 사람이 읽는 사실 문자열 리스트
    빈 입력이면 grade=None, facts=['수급 데이터 없음'].
    """
    if flows is None or getattr(flows, "empty", True):
        return {
            "windows": {}, "foreign_hold_pct": None, "foreign_hold_change": None,
            "inst_trend": "중립", "foreign_trend": "중립",
            "both_buying": False, "both_selling": False,
            "grade": None, "facts": ["수급 데이터 없음"],
        }

    win_out: Dict[int, Dict[str, Optional[float]]] = {}
    for n in windows:
        win_out[n] = {
            kor: _sum_window(flows, col, n) for col, kor in _NET_COLS.items()
        }

    short_n = min(windows)
    ref_n = 20 if 20 in windows else max(windows)

    inst_short = win_out[short_n]["기관"]
    foreign_short = win_out[short_n]["외국인"]
    inst_ref = win_out[ref_n]["기관"]
    foreign_ref = win_out[ref_n]["외국인"]

    # 외국인 보유율 최근값 + 변화(최장 윈도우 구간)
    hold = None
    hold_change = None
    if "foreign_hold_pct" in flows.columns:
        hp = pd.to_numeric(flows["foreign_hold_pct"], errors="coerce").dropna()
        if not hp.empty:
            hold = float(hp.iloc[-1])
            tail = hp.tail(max(windows))
            if len(tail) >= 2:
                hold_change = float(tail.iloc[-1] - tail.iloc[0])

    both_buying = (inst_ref or 0) > 0 and (foreign_ref or 0) > 0
    both_selling = (inst_ref or 0) < 0 and (foreign_ref or 0) < 0

    # 서열(사실 조합): 동반 순매수=양호 / 동반 순매도=주의 / 그 외=보통.
    if both_buying:
        grade = "양호"
    elif both_selling:
        grade = "주의"
    elif inst_ref is None and foreign_ref is None:
        grade = None
    else:
        grade = "보통"

    facts = []
    if inst_ref is not None:
        facts.append(f"기관 {ref_n}일 {_trend(inst_ref)} ({inst_ref:+,.0f}주)")
    if foreign_ref is not None:
        facts.append(f"외국인 {ref_n}일 {_trend(foreign_ref)} ({foreign_ref:+,.0f}주)")
    if hold is not None:
        chg = f" ({hold_change:+.2f}%p)" if hold_change is not None else ""
        facts.append(f"외국인 보유율 {hold:.2f}%{chg}")
    if not facts:
        facts.append("수급 데이터 부족")

    return {
        "windows": win_out,
        "foreign_hold_pct": hold,
        "foreign_hold_change": hold_change,
        "inst_trend": _trend(inst_short),
        "foreign_trend": _trend(foreign_short),
        "both_buying": both_buying,
        "both_selling": both_selling,
        "grade": grade,
        "facts": facts,
    }
