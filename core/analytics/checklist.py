"""판단 체크리스트 6축 (순수 로직, §5.8 / §12.4).

6축: 가치 · 기술 · 리스크 · 심리(활성 4축) + 성장 🔒 · 수급 🔒(잠금 2축).
각 축은 양호/보통/주의 '서열'과 근거 '사실'만 제공한다.

🔴 면책 핵심(§12.4):
  1. 6축을 합산한 '매수점수'를 절대 만들지 않는다(=신호화 금지). 축별 분리 표시.
  2. 라벨 정합 — 가격 모멘텀을 '성장'으로, 거래대금을 '수급'으로 라벨하지 않는다.
  3. '추천/매수신호'가 아닌 '체크리스트/판단 보조'이며 단독 판단 근거가 될 수 없다.
  4. 점수는 서열(양호/보통/주의)·백분위로만 표현한다(정밀 착시 회피).

다른 모듈 함수(verdict_*, ma_alignment, overheating, latest_signals,
compute_risk_flags)는 시그니처대로 import해 사용한다(여기서 재정의하지 않음).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from core.analytics.indicators import latest_signals
from core.analytics.labels import verdict_quality, verdict_value
from core.analytics.price_context import ma_alignment, overheating
from core.data.flags import compute_risk_flags

# 잠금 축 사유(점진적 노출·정직 원칙). 후속 단계에서 활성화된다.
GROWTH_LOCK_REASON = "🔒 성장 — 2단계(DART 재무: EPS·매출 추세) 연동 후 활성화"
SUPPLY_LOCK_REASON = "🔒 수급 — 4단계(키움 투자자별 순매수) 연동 후 활성화"

Axis = Dict[str, Any]


def _grade_from_score(score: Optional[float]) -> Optional[str]:
    """백분위(0~100)를 양호/보통/주의 서열로 변환. 결측은 None."""
    if score is None or pd.isna(score):
        return None
    if score >= 70:
        return "양호"
    if score >= 40:
        return "보통"
    return "주의"


def _mean_of_present(*values: Optional[float]) -> Optional[float]:
    """결측이 아닌 값들의 평균. 모두 결측이면 None."""
    present = [v for v in values if v is not None and not pd.isna(v)]
    if not present:
        return None
    return sum(present) / len(present)


def _make_axis(
    axis: str,
    *,
    active: bool,
    grade: Optional[str],
    facts: List[str],
    locked_reason: Optional[str],
) -> Axis:
    return {
        "axis": axis,
        "active": active,
        "grade": grade,
        "facts": facts,
        "locked_reason": locked_reason,
    }


def _value_axis(row: pd.Series) -> Axis:
    """가치 = value_score/quality_score 백분위(저PER·저PBR·ROE)."""
    value_score = row.get("value_score")
    quality_score = row.get("quality_score")
    combined = _mean_of_present(value_score, quality_score)
    grade = _grade_from_score(combined)

    facts: List[str] = []
    # verdict_*는 (label, tone)을 반환. 라벨 정합을 위해 함께 노출.
    v_label, _ = verdict_value(row)
    q_label, _ = verdict_quality(row)
    if value_score is not None and not pd.isna(value_score):
        facts.append(f"가치 백분위 {value_score:.0f} ({v_label})")
    if quality_score is not None and not pd.isna(quality_score):
        facts.append(f"수익성 백분위 {quality_score:.0f} ({q_label})")
    per = row.get("PER")
    pbr = row.get("PBR")
    if per is not None and not pd.isna(per) and per > 0 and \
            pbr is not None and not pd.isna(pbr) and pbr > 0:
        facts.append(f"PER {per:.1f}배 · PBR {pbr:.2f}배")
    if not facts:
        facts.append("가치 지표 데이터 부족")

    return _make_axis("가치", active=True, grade=grade, facts=facts,
                      locked_reason=None)


def _tech_axis(ohlcv: Optional[pd.DataFrame]) -> Axis:
    """기술 = 이동평균 정배열/역배열/혼조 · RSI 구간 · MACD 시그널 ('사실'만)."""
    alignment = ma_alignment(ohlcv)
    signals = latest_signals(ohlcv) if ohlcv is not None else {}

    facts: List[str] = [f"이동평균 {alignment}"]

    rsi_val = signals.get("rsi")
    rsi_state = signals.get("rsi_state")
    if rsi_val is not None and not pd.isna(rsi_val):
        state = f"({rsi_state})" if rsi_state else ""
        facts.append(f"RSI {rsi_val:.0f}{state}")

    macd_hist = signals.get("macd_hist")
    if macd_hist is not None and not pd.isna(macd_hist):
        trend = "상승" if macd_hist > 0 else "하락"
        facts.append(f"MACD 히스토그램 {trend}")

    # 서열: 정배열+MACD상승=양호 / 역배열=주의 / 그 외=보통 (사실 조합, 합산점수 아님)
    macd_up = macd_hist is not None and not pd.isna(macd_hist) and macd_hist > 0
    if alignment == "정배열" and macd_up:
        grade = "양호"
    elif alignment == "역배열":
        grade = "주의"
    else:
        grade = "보통"

    return _make_axis("기술", active=True, grade=grade, facts=facts,
                      locked_reason=None)


def _risk_axis(flags: List[str]) -> Axis:
    """리스크 = compute_risk_flags 충족 목록."""
    flags = list(flags) if flags else []
    if not flags:
        return _make_axis(
            "리스크", active=True, grade="양호",
            facts=["특이 위험 신호 없음(최근 정상 거래)"], locked_reason=None,
        )
    # ⛔(거래정지/데이터없음) 포함 시 '주의', 경고(⚠️)만이면 '보통'.
    grade = "주의" if any("⛔" in f for f in flags) else "보통"
    return _make_axis("리스크", active=True, grade=grade, facts=flags,
                      locked_reason=None)


def _sentiment_axis(ohlcv: Optional[pd.DataFrame]) -> Axis:
    """심리 = §5.9 과열도 프록시 등급(가격·거래량 기반, 게시판 아님)."""
    result = overheating(ohlcv)
    level = result.get("level") if result else None

    # 과열도 등급 → 체크리스트 서열. '과열/높음'은 추격매수 주의 신호이므로 '주의'.
    mapping = {"낮음": "양호", "보통": "보통", "높음": "주의", "과열": "주의"}
    grade = mapping.get(level)

    facts: List[str] = []
    if level:
        facts.append(f"가격·거래량 기반 과열도: {level} (게시판 심리 아님)")
    else:
        facts.append("과열도 산출 불가 — 가격 데이터 부족")
    facts.append("보조지표 · 단독 판단 금지")

    return _make_axis("심리", active=True, grade=grade, facts=facts,
                      locked_reason=None)


def build_checklist(
    row: pd.Series,
    ohlcv: Optional[pd.DataFrame],
    flags: List[str],
    *,
    scored: pd.DataFrame,
) -> List[Axis]:
    """6축 판단 체크리스트를 축별로 분리해 반환.

    활성 4축(가치·기술·리스크·심리) + 잠금 2축(성장·수급).
    🔴 6축을 합산한 '매수점수' 필드는 만들지 않는다(축별 분리 — §12.4).

    Args:
        row: 스코어링된 단일 종목 행(value/quality/income_score, PER/PBR 등 포함).
        ohlcv: 해당 종목 일봉(없으면 기술/심리 축은 데이터 부족 처리).
        flags: compute_risk_flags(ohlcv) 결과(이미 계산된 위험 플래그 목록).
        scored: 전체 스코어 스냅샷(백분위 참조용, 현재 등급은 row 백분위로 충분).
    """
    # scored는 향후 백분위 칩 확장을 위한 슬롯. 현재 등급은 row 백분위로 산출한다.
    _ = scored
    return [
        _value_axis(row),
        _tech_axis(ohlcv),
        _risk_axis(flags),
        _sentiment_axis(ohlcv),
        _make_axis("성장", active=False, grade=None, facts=[],
                   locked_reason=GROWTH_LOCK_REASON),
        _make_axis("수급", active=False, grade=None, facts=[],
                   locked_reason=SUPPLY_LOCK_REASON),
    ]
