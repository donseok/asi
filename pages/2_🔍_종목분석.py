"""종목분석 페이지 — 종목 하나를 한눈에 요약·리스크·가격맥락·체크리스트로 본다.

스펙 §5. 순수 로직(labels/price_context/checklist/scoring/flags)과 HTML 빌더
(ui_components), 차트(ui_helpers)를 조립만 한다. 이 파일에는 비즈니스 로직이 없다.
표시 점수는 모두 횡단면 상대 지표이며 매수 신호가 아니다(상시 고지).

데이터 계약: scored는 RangeIndex, ticker는 '컬럼'(6자리). 한 행은 ticker 컬럼으로
조회한다. 현재가/시총/거래대금 컬럼은 한글(종가/시가총액/거래대금)이다.
OHLCV는 비어 있을 수 있다(거래정지/상폐) → 차트·가격맥락·과열도·이탈감시 생략.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import ui_components as uc
import ui_helpers as ui
from core.analytics import labels, price_context
from core.analytics.checklist import build_checklist
from core.analytics.indicators import latest_signals
from core.analytics.scoring import metric_percentile, percentile_of
from core.data.flags import compute_risk_flags
from ui_theme import inject_css

st.set_page_config(page_title="ASI — 종목분석", page_icon="🔍", layout="wide")
inject_css()

# 정적 미확인 고지(리스크 카드용). labels.CAPTIONS가 있으면 그것을 우선 사용.
_RISK_UNKNOWN_CAPTION = labels.CAPTIONS.get(
    "alert_unknown",
    "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정",
)


def _fmt_pct(value) -> str:
    """수익률 등 퍼센트 포맷. None/NaN은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.1f}%"


def _fmt_num(value, suffix: str = "", digits: int = 2) -> str:
    """일반 수치 포맷. None/NaN은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}{suffix}"


# ── 데이터 로드 (스냅샷) ───────────────────────────────────────────────
try:
    scored = ui.load_scored_snapshot()
except Exception as exc:  # 네트워크/스냅샷 실패 → 앱이 죽지 않게 안내
    st.error("종목 데이터를 불러오지 못했습니다. 홈에서 '데이터 새로 받기'를 눌러 주세요.")
    st.caption(f"({type(exc).__name__})")
    st.stop()

if scored is None or scored.empty:
    st.warning("표시할 종목 데이터가 없습니다. 홈에서 데이터를 먼저 갱신해 주세요.")
    st.stop()

# ── 종목 선택 박스 (기본값 = 핸드오프 selected_ticker) ────────────────
# ticker는 '컬럼'이다(index 아님). 티커 → 표시 라벨 매핑.
st.title("🔍 종목분석")

scored = scored.copy()
scored["ticker"] = scored["ticker"].astype(str).str.zfill(6)
tickers = list(scored["ticker"])
name_by_ticker = dict(zip(scored["ticker"], scored["name"]))
labels_by_ticker = {t: f"{name_by_ticker.get(t, t)} ({t})" for t in tickers}

default_ticker = str(st.session_state.get("selected_ticker", "")).zfill(6)
default_index = tickers.index(default_ticker) if default_ticker in tickers else 0

selected = st.selectbox(
    "종목 선택 (이름·코드로 검색)",
    options=tickers,
    index=default_index,
    format_func=lambda t: labels_by_ticker.get(t, t),
)
st.session_state["selected_ticker"] = selected

# 한 종목 row = ticker 컬럼으로 조회(Series).
row = scored.loc[scored["ticker"] == selected].iloc[0]
ohlcv = ui.load_ohlcv_with_indicators(selected)
has_price = ohlcv is not None and not ohlcv.empty
name = row.get("name", selected)

# ── 헤더 (종합점수 + 상대 순위 캡션) ──────────────────────────────────
score = row.get("score")
head_l, head_r = st.columns([3, 1])
with head_l:
    market = row.get("market", "")
    st.subheader(f"{name}  ·  {selected}")
    if market:
        st.caption(f"{market}")
with head_r:
    st.metric("종합점수", _fmt_num(score, digits=0))
    pct = percentile_of(scored, selected)
    if pct is not None and not pd.isna(pct):
        st.caption(f"상위 {100 - pct:.0f}% · 상대 순위일 뿐 매수 신호가 아닙니다")

st.divider()

# ── 📌 한눈에 요약 (3카드: verdict + 직관 배지 + sub-score 막대) ────────
st.markdown("#### 📌 한눈에 요약")
v_label, v_tone = labels.verdict_value(row)
q_label, q_tone = labels.verdict_quality(row)
i_label, i_tone = labels.verdict_income(row)

# 배당 환산액(정수) → "100만원당 연 ~N원" 포맷.
div_won = labels.dividend_won(row, principal=config.DIVIDEND_PRINCIPAL)
income_intuition = f"100만원당 연 ~{div_won:,}원" if div_won > 0 else None

verdicts = [
    {
        "cat": "가치 (싼가?)",
        "emoji": "💎",
        "label": v_label,
        "tone": v_tone,
        "word": v_label,
        "intuition": labels.value_badge(row),
        "metrics": [
            ("PER", _fmt_num(row.get("PER"), "배", 1)),
            ("PBR", _fmt_num(row.get("PBR"), "배", 2)),
        ],
        "score": row.get("value_score"),
    },
    {
        "cat": "수익성 (잘 버나?)",
        "emoji": "🛡️",
        "label": q_label,
        "tone": q_tone,
        "word": q_label,
        "intuition": "EPS/BPS 기반 근사치(정확 ROE는 후속 단계)",
        "metrics": [
            ("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 0)),
            ("EPS", ui.fmt_won(row.get("EPS"))),
        ],
        "score": row.get("quality_score"),
    },
    {
        "cat": "배당 (주주환원)",
        "emoji": "💰",
        "label": i_label,
        "tone": i_tone,
        "word": i_label,
        "intuition": income_intuition,
        "metrics": [
            ("배당수익률", _fmt_num(row.get("DIV"), "%", 2)),
            ("주당배당금", ui.fmt_won(row.get("DPS"))),
        ],
        "score": row.get("income_score"),
    },
]
st.markdown(uc.render_summary_cards(verdicts), unsafe_allow_html=True)

# 📊 점수 분해 (가치·수익성·배당 3막대) — §5.7 기본 노출
st.markdown("**📊 점수 분해**")
st.markdown(uc.render_subscore_bars(row), unsafe_allow_html=True)
st.caption("점수 막대는 전체 종목 대비 상대 순위입니다. 매수 신호가 아닙니다.")

# 📖 용어 ⓘ 툴팁 — §5.7 기본 노출. 라벨 옆 ⓘ에 마우스를 올리면 한 줄 정의.
with st.expander("📖 용어 쉽게 보기 (PER·PBR·ROE 등)", expanded=False):
    st.markdown(
        "\n".join(
            f"- {uc.render_glossary_tooltip(term)} {labels.GLOSSARY[term]}"
            for term in labels.GLOSSARY
        ),
        unsafe_allow_html=True,
    )
st.divider()

# ── 📈 가격 맥락 (52주 바 · 기간수익률 칩 · 추세 한 줄) ─────────────────
st.markdown("#### 📈 가격 맥락")
if has_price:
    w52 = price_context.week52_position(ohlcv)
    rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)
    alignment = price_context.ma_alignment(ohlcv)

    st.markdown(uc.render_week52(w52), unsafe_allow_html=True)
    st.markdown(uc.render_returns(rets), unsafe_allow_html=True)
    st.caption(f"추세: {alignment} (SMA20/60/120 배열 기준)")
else:
    st.info("가격 데이터가 없어 가격 맥락을 표시할 수 없습니다(거래정지/상장폐지 가능).")

st.divider()

# ── ⚠️ 리스크 체크 (쉬운말 + 변동성 등급 + 미확인 고지) ───────────────
st.markdown("#### ⚠️ 리스크 체크")
risk_flags = compute_risk_flags(ohlcv if has_price else None)
st.markdown(uc.render_risk(risk_flags, _RISK_UNKNOWN_CAPTION), unsafe_allow_html=True)

if has_price:
    grade, daily_pct = price_context.volatility_grade(ohlcv, window=20)
    if grade is not None:
        st.caption(
            f"변동성 등급: {grade} (최근 일간 변동성 {_fmt_num(daily_pct, '%', 2)})"
        )

st.divider()

# ── 📉 간단 차트 (overview + 신호 한 줄) ──────────────────────────────
st.markdown("#### 📉 가격 차트 (간단)")
if has_price:
    sig = latest_signals(ohlcv)
    alignment = price_context.ma_alignment(ohlcv)
    st.caption(labels.signal_text(sig, ma_alignment=alignment))
    st.plotly_chart(
        ui.make_overview_figure(ohlcv, f"{name} 가격"),
        use_container_width=True,
    )
else:
    st.info("가격 데이터가 없어 차트를 표시할 수 없습니다. 위 리스크 체크를 참고하세요.")

st.divider()

# ── 🧭 판단 체크리스트 (참고용 · 합산 매수점수 없음) ──────────────────
st.markdown("#### 🧭 판단 체크리스트 (참고용)")
axes = build_checklist(row, ohlcv if has_price else None, risk_flags, scored=scored)
st.markdown(uc.render_checklist(axes), unsafe_allow_html=True)
st.caption(
    "체크리스트는 축별 사실을 분리 표시한 판단 보조입니다. 합산 매수점수가 아니며, "
    "단독 판단 근거로 삼지 마세요(투자 권유 아님)."
)
st.divider()

# ── 🔬 더 알아보기 (중급, 기본 접힘) ──────────────────────────────────
with st.expander("🔬 더 알아보기 (중급 심화)", expanded=False):
    st.markdown("**지표별 시장 백분위**")
    # (컬럼명, 표시라벨, lower_is_better, hint). 컬럼은 실제 스냅샷 한글/영문 그대로.
    metric_specs = [
        ("PER", "PER", True, "저렴"),
        ("PBR", "PBR", True, "저렴"),
        ("DIV", "배당수익률", False, "상위"),
        ("ROE_approx", "ROE(근사)", False, "상위"),
        ("시가총액", "시가총액", False, "상위"),
        ("거래대금", "거래대금", False, "상위"),
    ]
    chips = []
    for col, label, lower_better, hint in metric_specs:
        if col not in scored.columns:
            continue
        p = metric_percentile(scored, selected, col, lower_is_better=lower_better)
        chips.append((label, None if p is None or pd.isna(p) else p, hint))
    st.markdown(uc.render_percentile_chips(chips), unsafe_allow_html=True)

    if has_price:
        st.markdown("**가격 심화 지표**")
        disp = price_context.disparity(ohlcv, windows=(20, 60))
        mdd = price_context.max_drawdown(ohlcv, window=config.WEEK52_WINDOW)
        vol_ratio = price_context.volume_ratio(ohlcv, window=20)
        ey = labels.earnings_yield(row)
        rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)

        dcols = st.columns(3)
        with dcols[0]:
            st.metric("20일선 이격도", _fmt_num(disp.get(20), "%", 1))
            st.metric("최대낙폭(MDD)", _fmt_num(mdd, "%", 1))
        with dcols[1]:
            st.metric("60일선 이격도", _fmt_num(disp.get(60), "%", 1))
            st.metric("거래량 배수", _fmt_num(vol_ratio, "배", 1))
        with dcols[2]:
            st.metric("이익수익률(1/PER)", ey)
            st.metric("6개월 수익률", _fmt_pct(rets.get("6개월")))
        st.metric("12개월 수익률", _fmt_pct(rets.get("12개월")))

        st.markdown("**기술적 지표 풀이 (RSI·MACD)**")
        sig = latest_signals(ohlcv)
        st.write(labels.indicator_plain(sig))
        st.plotly_chart(ui.make_indicator_figure(ohlcv), use_container_width=True)
    else:
        st.info("가격 데이터가 없어 가격 심화 지표를 표시할 수 없습니다.")

st.divider()

# ── 🌡️ 과열도 (가격·거래량 기반 프록시) ──────────────────────────────
st.markdown("#### 🌡️ 과열도 (가격·거래량 기반)")
if has_price:
    heat = price_context.overheating(ohlcv)
    st.markdown(uc.render_overheat(heat.get("level")), unsafe_allow_html=True)
    comps = heat.get("components") or {}
    if comps:
        st.caption(" · ".join(f"{k}: {v}" for k, v in comps.items()))
else:
    st.info("가격 데이터가 없어 과열도를 계산할 수 없습니다.")
st.divider()

# ── 🎯 손절/익절 이탈 감시 (가격만) ───────────────────────────────────
st.markdown("#### 🎯 손절/익절 이탈 감시")
latest_close = float(ohlcv["close"].iloc[-1]) if has_price else None
mcols = st.columns(2)
with mcols[0]:
    stop_in = st.number_input(
        "손절가 (₩)", min_value=0.0, value=0.0, step=100.0, key="monitor_stop"
    )
with mcols[1]:
    target_in = st.number_input(
        "익절가 (₩)", min_value=0.0, value=0.0, step=100.0, key="monitor_target"
    )
if latest_close is None:
    st.info("가격 데이터가 없어 이탈 감시를 할 수 없습니다.")
else:
    stop = stop_in if stop_in > 0 else None
    target = target_in if target_in > 0 else None
    if stop is None and target is None:
        st.caption("손절가/익절가를 입력하면 최신 종가와 비교해 도달·이탈 사실을 알려드립니다.")
    else:
        result = price_context.monitor_targets(latest_close, stop=stop, target=target)
        status = result.get("status", "범위내")
        msg = f"최신 종가 ₩{latest_close:,.0f} — "
        if status == "익절도달":
            st.success(msg + f"입력하신 익절가 ₩{target:,.0f} 도달")
        elif status == "손절이탈":
            st.warning(msg + f"입력하신 손절가 ₩{stop:,.0f} 이탈")
        else:
            st.info(msg + "입력 범위 내")
        st.caption("사실 고지일 뿐 주문·자동매매는 하지 않습니다(투자일임 아님).")

st.divider()

# ── 🔢 상세 숫자 (표) ─────────────────────────────────────────────────
st.markdown("#### 🔢 상세 숫자")
detail_rows = [
    ("PER", _fmt_num(row.get("PER"), "배", 2)),
    ("PBR", _fmt_num(row.get("PBR"), "배", 2)),
    ("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 1)),
    ("EPS", ui.fmt_won(row.get("EPS"))),
    ("BPS", ui.fmt_won(row.get("BPS"))),
    ("배당수익률", _fmt_num(row.get("DIV"), "%", 2)),
    ("시가총액", ui.fmt_won(row.get("시가총액"))),
    ("거래대금(당일)", ui.fmt_won(row.get("거래대금"))),
    ("주당배당금(DPS)", ui.fmt_won(row.get("DPS"))),
    ("현재가(종가)", _fmt_num(row.get("종가"), "원", 0)),
]
st.table(pd.DataFrame(detail_rows, columns=["항목", "값"]).set_index("항목"))

st.info(config.DISCLAIMER, icon="⚠️")
