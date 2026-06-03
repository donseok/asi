"""순수 HTML 문자열 빌더 (라이트 핀테크 디자인).

ui_theme.inject_css가 주입하는 CSS 클래스명과 동일한 클래스를 두른 HTML 문자열만
만든다(로직·계산·Streamlit/네트워크 호출 없음).

인자로 받는 row/badges/axes/pos/returns 등은 모두 '이미 계산된 산출물'이다
(core/analytics의 순수 함수가 만든다). row는 load_scored_snapshot()의 한 행과
동일한 컬럼 계약을 따른다 — 현재가=종가, 시가총액=시가총액(모두 한글 컬럼).
색 결정은 한국 관습(상승=빨강/하락=파랑)을 유지한다.
"""
from __future__ import annotations

import html as _html
from typing import Optional, Sequence

from ui_helpers import fmt_won  # 재정의 금지 — import해 사용

# 색 뱃지 라벨 → CSS 클래스 매핑(저평가/우량/고배당)
_BADGE_CLASS = {
    "저평가": ("b-value", "💎"),
    "우량": ("b-quality", "🛡️"),
    "고배당": ("b-div", "💰"),
}

# 점수 tier → 색 클래스(점수 숫자 색). good/warn/muted.
_TIER_CLASS = {"good": "tier-good", "warn": "tier-warn", "muted": "tier-muted"}

# verdict tone → 칩 클래스(v-good/v-strong/v-mid)
_VERDICT_CLASS = {"good": "v-good", "strong": "v-strong", "mid": "v-mid"}


def _esc(text) -> str:
    """HTML 본문에 넣을 문자열 이스케이프(None/숫자 안전)."""
    if text is None:
        return ""
    return _html.escape(str(text))


def _market_class(market) -> str:
    """시장명 → 뱃지 클래스(KOSPI→kospi, KOSDAQ→kosdaq)."""
    m = str(market or "").upper()
    return "kosdaq" if "KOSDAQ" in m else "kospi"


def _market_label(market) -> str:
    return "코스닥" if _market_class(market) == "kosdaq" else "코스피"


def _get(row, key):
    """row(dict/Series)에서 값을 안전하게 꺼낸다. 없으면 None."""
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        try:
            val = row.get(key)
        except AttributeError:
            return None
    return val


def _badge_html(label: str) -> str:
    cls, emoji = _BADGE_CLASS.get(label, ("b-value", ""))
    return (
        f'<span class="badge {cls}">'
        f'<span aria-hidden="true">{emoji}</span> {_esc(label)}</span>'
    )


def _clamp_pct(value) -> float:
    """막대 폭(%)을 0~100으로 제한."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN 방어
        return 0.0
    return max(0.0, min(100.0, v))


def render_stock_card(
    row,
    badges: Sequence[str],
    explain: str,
    tier: str,
    rank_pct: Optional[float] = None,
) -> str:
    """스크리너 결과 카드(§4.3).

    row는 스냅샷 한 행. 현재가는 한글 컬럼 '종가'에서 읽는다(영문 close 없음).
    """
    name = _esc(_get(row, "name"))
    mkt_cls = _market_class(_get(row, "market"))
    mkt_label = _market_label(_get(row, "market"))

    close = _get(row, "종가")  # 실제 스냅샷 컬럼명
    try:
        price_txt = "-" if close is None else f"{float(close):,.0f}원"
        if close is not None and float(close) != float(close):  # NaN
            price_txt = "-"
    except (TypeError, ValueError):
        price_txt = "-"

    # 당일 등락률(있을 때만): 상승=빨강/하락=파랑(한국 관습). 컬럼 없거나 NaN이면 생략.
    change = _get(row, "등락률")
    change_block = ""
    try:
        if change is not None and float(change) == float(change):
            cv = float(change)
            ccls = "chg-up" if cv > 0 else ("chg-down" if cv < 0 else "chg-flat")
            sign = "+" if cv > 0 else ""
            change_block = f'<span class="scard-chg {ccls} num">{sign}{cv:.2f}%</span>'
    except (TypeError, ValueError):
        change_block = ""

    score = _get(row, "score")
    try:
        score_txt = "-" if score is None else f"{float(score):.0f}"
        if score is not None and float(score) != float(score):
            score_txt = "-"
    except (TypeError, ValueError):
        score_txt = "-"
    bar_pct = _clamp_pct(score)
    tier_cls = _TIER_CLASS.get(tier, "tier-muted")

    badge_block = ""
    if badges:
        chips = "".join(_badge_html(b) for b in badges)
        badge_block = f'<div class="badge-row">{chips}</div>'

    rank_block = ""
    if rank_pct is not None:
        try:
            rank_block = f'<div class="score-rank">상위 {float(rank_pct):.0f}%</div>'
        except (TypeError, ValueError):
            rank_block = ""

    return (
        '<article class="scard">'
        '<div class="scard-top">'
        '<div class="stock-id">'
        f'<span class="stock-name">{name}</span>'
        f'<span class="mkt {mkt_cls}">{mkt_label}</span>'
        "</div>"
        '<div class="price-wrap">'
        f'<div class="price num">{_esc(price_txt)}</div>'
        f"{change_block}"
        "</div>"
        "</div>"
        f"{badge_block}"
        f'<div class="why"><span class="q">왜 추천?</span>{_esc(explain)}</div>'
        '<div class="score-row">'
        '<div class="score-block">'
        f'<div class="score-num num {tier_cls}">{score_txt}<span class="u">점</span></div>'
        f"{rank_block}"
        "</div>"
        '<div class="bar-wrap">'
        '<div class="bar-label"><span class="lv">종합점수</span>'
        f'<span class="num">{score_txt} / 100</span></div>'
        f'<div class="bar"><i style="width:{bar_pct:.0f}%"></i></div>'
        "</div>"
        "</div>"
        '<div class="scard-foot">'
        '<span class="detail-link">자세히 보기 <span class="arr" aria-hidden="true">→</span></span>'
        "</div>"
        "</article>"
    )


def _metric_line(key: str, value: str) -> str:
    return (
        '<div class="metric-line">'
        f'<span class="k">{_esc(key)}</span>'
        f'<span class="v num">{_esc(value)}</span>'
        "</div>"
    )


def _score_bar(score) -> str:
    """sub-score(0~100) → 점수 막대. 결측이면 폭 0%."""
    width = _clamp_pct(score)
    return f'<div class="bar"><i style="width:{width:.0f}%"></i></div>'


def _sumcard_html(verdict: dict) -> str:
    tone_cls = _VERDICT_CLASS.get(verdict.get("tone"), "v-mid")
    intuition = verdict.get("intuition")
    intuition_block = ""
    if intuition:
        intuition_block = f'<div class="intuition">{_esc(intuition)}</div>'
    metrics = "".join(_metric_line(k, v) for k, v in verdict.get("metrics", []))
    return (
        '<div class="sumcard">'
        '<div class="head">'
        f'<span class="cat"><span aria-hidden="true">{verdict.get("emoji", "")}</span> '
        f'{_esc(verdict.get("cat"))}</span>'
        f'<span class="verdict {tone_cls}">{_esc(verdict.get("label"))}</span>'
        "</div>"
        f'<div class="word">{_esc(verdict.get("word"))}</div>'
        f"{intuition_block}"
        f"{metrics}"
        f'{_score_bar(verdict.get("score"))}'
        "</div>"
    )


def render_summary_cards(verdicts: Sequence[dict]) -> str:
    """한눈에 요약 3카드(§5.3) + 직관 배지(§5.7) + sub-score 막대.

    verdicts는 페이지가 labels.verdict_*/value_badge/dividend_won 산출물을 묶은
    dict 리스트다(키: cat/emoji/label/tone/word/intuition/metrics/score).
    """
    cards = "".join(_sumcard_html(v) for v in verdicts)
    return f'<div class="sum3">{cards}</div>'


def _subscore_bar(label: str, score) -> str:
    if score is None:
        val_txt, width = "-", 0.0
    else:
        try:
            width = _clamp_pct(score)
            val_txt = "-" if float(score) != float(score) else f"{float(score):.0f}"
        except (TypeError, ValueError):
            val_txt, width = "-", 0.0
    return (
        '<div class="bar-wrap">'
        '<div class="bar-label">'
        f'<span class="lv">{_esc(label)}</span>'
        f'<span class="num">{val_txt}</span></div>'
        f'<div class="bar"><i style="width:{width:.0f}%"></i></div>'
        "</div>"
    )


def render_subscore_bars(row) -> str:
    """가치/수익성/배당 3점수 막대(§5.7 기본 노출). row의 *_score를 막대로."""
    bars = "".join(
        [
            _subscore_bar("가치", _get(row, "value_score")),
            _subscore_bar("수익성", _get(row, "quality_score")),
            _subscore_bar("배당", _get(row, "income_score")),
        ]
    )
    return f'<div class="subscores">{bars}</div>'


def _risk_item(flag: str) -> str:
    # 위험 플래그는 주의(amber) dot/state
    return (
        '<div class="risk-item">'
        '<div class="rk-head">'
        '<span class="rk-dot mid" aria-hidden="true"></span>'
        f'<span class="rk-name">{_esc(flag)}</span>'
        '<span class="rk-state mid">주의</span>'
        "</div>"
        "</div>"
    )


def render_risk(flags: Sequence[str], caption: str) -> str:
    """리스크 체크(§5.4). 플래그 0건이면 긍정 라인, 미확인 고지는 항상 노출."""
    if flags:
        items = "".join(_risk_item(f) for f in flags)
    else:
        items = (
            '<div class="risk-item">'
            '<div class="rk-head">'
            '<span class="rk-dot ok" aria-hidden="true"></span>'
            '<span class="rk-name">특이 위험 신호 없음(최근 정상 거래)</span>'
            '<span class="rk-state ok">정상</span>'
            "</div>"
            "</div>"
        )
    note = (
        '<div class="risk-note">'
        '<span class="ic" aria-hidden="true">ℹ️</span>'
        f"<span>{_esc(caption)}</span>"
        "</div>"
    )
    return f'<div class="risk-card"><div class="risk-grid">{items}</div>{note}</div>'


# 체크리스트 축 등급 → 색 클래스
_GRADE_CLASS = {"양호": "grade-good", "보통": "grade-mid", "주의": "grade-warn"}


def _axis_cell(axis: dict) -> str:
    name = _esc(axis.get("axis"))
    if not axis.get("active"):
        reason = _esc(axis.get("locked_reason") or "후속 단계에서 활성화")
        return (
            '<div class="axis-cell locked">'
            f'<div class="axis-name">{name} <span aria-hidden="true">🔒</span></div>'
            f'<div class="axis-lock">{reason}</div>'
            "</div>"
        )
    grade = axis.get("grade") or "보통"
    grade_cls = _GRADE_CLASS.get(grade, "grade-mid")
    facts = "".join(f'<li>{_esc(f)}</li>' for f in axis.get("facts", []))
    return (
        '<div class="axis-cell active">'
        '<div class="axis-head">'
        f'<span class="axis-name">{name}</span>'
        f'<span class="axis-grade {grade_cls}">{_esc(grade)}</span>'
        "</div>"
        f'<ul class="axis-facts">{facts}</ul>'
        "</div>"
    )


def render_checklist(axes: Sequence[dict]) -> str:
    """판단 체크리스트 6축(§5.8). 잠금 축은 회색. 합산 매수점수는 만들지 않는다(면책)."""
    cells = "".join(_axis_cell(a) for a in axes)
    return f'<div class="checklist-grid">{cells}</div>'


def render_week52(pos: Optional[dict]) -> str:
    """52주 범위 바 + 현재가 위치 + 고점 대비 낙폭(§5.7).

    pos는 price_context.week52_position 산출물(dict). 빈 OHLCV면 값이 모두 None →
    안내 문구로 대체(깨지지 않음).
    """
    if not pos or pos.get("pos_pct") is None:
        return '<div class="week52 empty">가격 데이터 없음</div>'
    low = pos.get("low")
    high = pos.get("high")
    pos_pct = _clamp_pct(pos.get("pos_pct"))
    drawdown = pos.get("drawdown_pct")
    low_txt = "-" if low is None else f"{float(low):,.0f}"
    high_txt = "-" if high is None else f"{float(high):,.0f}"
    dd_txt = "-" if drawdown is None else f"{float(drawdown):.1f}%"
    return (
        '<div class="week52">'
        '<div class="week52-bar">'
        f'<i class="week52-marker" style="left:{pos_pct:.0f}%"></i>'
        "</div>"
        '<div class="week52-ends">'
        f'<span class="lo num">{low_txt}</span>'
        f'<span class="hi num">{high_txt}</span>'
        "</div>"
        f'<div class="week52-dd">고점 대비 <b class="num">{dd_txt}</b></div>'
        "</div>"
    )


def _return_chip(label: str, value) -> str:
    if value is None:
        cls, txt = "ret-flat", "-"
    else:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = None
        if v is None or v != v:  # None/NaN
            cls, txt = "ret-flat", "-"
        elif v > 0:
            cls, txt = "ret-up", f"+{v:.1f}%"  # 상승=빨강(한국 관습)
        elif v < 0:
            cls, txt = "ret-down", f"{v:.1f}%"  # 하락=파랑
        else:
            cls, txt = "ret-flat", "0.0%"
    return (
        f'<span class="ret-chip {cls}">'
        f'<span class="ret-k">{_esc(label)}</span>'
        f'<span class="ret-v num">{txt}</span>'
        "</span>"
    )


def render_returns(returns: dict) -> str:
    """기간 수익률 칩(§5.7). 상승=빨강/하락=파랑(한국 관습)."""
    chips = "".join(_return_chip(k, v) for k, v in (returns or {}).items())
    return f'<div class="returns">{chips}</div>'


# 과열도 등급 → 색 클래스
_OVERHEAT_CLASS = {"낮음": "oh-low", "보통": "oh-mid", "높음": "oh-high", "과열": "oh-hot"}


def render_overheat(level: Optional[str]) -> str:
    """과열도(§5.9) — 가격·거래량 기반 프록시. 필수 고지 상시 동반.

    level은 price_context.overheating(...)["level"](빈 OHLCV면 None).
    """
    cls = _OVERHEAT_CLASS.get(level, "oh-mid")
    level_txt = _esc(level) if level else "-"
    return (
        '<div class="overheat">'
        '<div class="oh-head">'
        '<span class="oh-title">가격·거래량 기반 과열도'
        '<span class="oh-note-inline">(게시판 심리 아님)</span></span>'
        f'<span class="oh-level {cls}">{level_txt}</span>'
        "</div>"
        '<div class="oh-disc">보조지표 · 단독 판단 근거로 사용하지 마세요.</div>'
        "</div>"
    )


def _pctile_chip(label: str, pct, hint: Optional[str]) -> str:
    if pct is None:
        rank_txt = "-"
    else:
        try:
            p = float(pct)
            rank_txt = "-" if p != p else (
                f"하위 {p:.0f}%" if hint == "저렴" else f"상위 {p:.0f}%"
            )
        except (TypeError, ValueError):
            rank_txt = "-"
    hint_block = f'<span class="pc-hint">{_esc(hint)}</span>' if hint else ""
    return (
        '<span class="pctile-chip">'
        f'<span class="pc-k">{_esc(label)}</span>'
        f'<span class="pc-v num">{rank_txt}</span>'
        f"{hint_block}"
        "</span>"
    )


def render_percentile_chips(chips: Sequence[tuple]) -> str:
    """지표별 시장 백분위 칩(§5.7 중급). (label, pct, hint) 튜플 리스트."""
    body = "".join(_pctile_chip(label, pct, hint) for label, pct, hint in chips)
    return f'<div class="pctile-chips">{body}</div>'


def render_glossary_tooltip(term: str) -> str:
    """용어 ⓘ 툴팁(§5.7). labels.GLOSSARY 정의를 title 속성으로 노출."""
    # labels.GLOSSARY는 다른 모듈에서 구현 — 재정의하지 않고 참조한다.
    from core.analytics import labels

    definition = labels.GLOSSARY.get(term)
    label = _esc(term)
    if not definition:
        return f'<span class="glossary-term">{label}</span>'
    return (
        f'<span class="glossary-term" title="{_esc(definition)}">'
        f'{label} <span class="gl-ic" aria-hidden="true">ⓘ</span></span>'
    )
