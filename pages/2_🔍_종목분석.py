"""종목분석 페이지 — 탭 기반(요약·수급·밸류/재무·기술/리스크).

KRX가 상세 데이터를 로그인 잠금했기 때문에, 수급(기관·외국인)·밸류에이션·재무·동일업종은
무키 네이버 금융(core.data.naver)으로 보강한다. 가격/지표는 pykrx 일봉(무키)을 쓴다.

설계 원칙(유지): 순수 로직(labels/price_context/checklist/scoring/flags/supply)과
HTML 빌더(ui_components)·차트(ui_helpers)를 조립만 한다. 표시 지표는 모두 상대/사실 지표이며
매수 신호가 아니다(상시 고지). 네트워크 실패 시 각 섹션은 '데이터 없음'으로 degrade 한다.
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
from core.analytics.supply import summarize_flows
from core.data.flags import compute_risk_flags
from ui_theme import inject_css

st.set_page_config(page_title="ASI — 종목분석", page_icon="🔍", layout="wide")
inject_css()

_RISK_UNKNOWN_CAPTION = labels.CAPTIONS.get(
    "alert_unknown",
    "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정",
)


def _fmt_pct(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.1f}%"


def _fmt_num(value, suffix: str = "", digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}{suffix}"


def _fmt_shares(value) -> str:
    """순매매량(주) 포맷. 부호 포함 천단위. 결측은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+,.0f}"


# ── 데이터 로드 (스냅샷) ───────────────────────────────────────────────
try:
    scored = ui.load_scored_snapshot()
except Exception as exc:
    st.error("종목 데이터를 불러오지 못했습니다. 홈에서 '데이터 새로 받기'를 눌러 주세요.")
    st.caption(f"({type(exc).__name__})")
    st.stop()

if scored is None or scored.empty:
    st.warning("표시할 종목 데이터가 없습니다. 홈에서 데이터를 먼저 갱신해 주세요.")
    st.stop()

# ── 종목 선택 ──────────────────────────────────────────────────────────
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

row = scored.loc[scored["ticker"] == selected].iloc[0]
ohlcv = ui.load_ohlcv_with_indicators(selected)
has_price = ohlcv is not None and not ohlcv.empty
name = row.get("name", selected)

# 네이버 보강 데이터(캐시) — 종목 상세 전반에서 사용
overview = ui.load_overview(selected) or {}
flows = ui.load_supply_demand(selected, days=60)
flows_summary = summarize_flows(flows) if flows is not None and not flows.empty else None

# ── 헤더 (종합점수 + 상대 순위) ────────────────────────────────────────
score = row.get("score")
head_l, head_m, head_r = st.columns([3, 2, 1])
with head_l:
    st.subheader(f"{name}  ·  {selected}")
    market = row.get("market", "")
    if market:
        st.caption(f"{market}")
with head_m:
    close = row.get("종가")
    chg = row.get("등락률")
    if close is not None and not pd.isna(close):
        # delta_color='inverse' → 상승=빨강/하락=파랑(한국 관습)
        st.metric("현재가(종가)", f"{float(close):,.0f}원",
                  delta=None if (chg is None or pd.isna(chg)) else f"{float(chg):+.2f}%",
                  delta_color="inverse")
with head_r:
    st.metric("종합점수", _fmt_num(score, digits=0))
    pct = percentile_of(scored, selected)
    if pct is not None and not pd.isna(pct):
        st.caption(f"상위 {100 - pct:.0f}% · 상대 순위")

tab_sum, tab_flow, tab_val, tab_tech = st.tabs(
    ["📌 요약", "💰 수급 주체", "📊 밸류·재무", "📈 기술·리스크"]
)

# ══════════════════════════════════════════════════════════════════════
# TAB 1 — 요약
# ══════════════════════════════════════════════════════════════════════
with tab_sum:
    st.markdown("#### 📌 한눈에 요약")
    v_label, v_tone = labels.verdict_value(row)
    q_label, q_tone = labels.verdict_quality(row)
    i_label, i_tone = labels.verdict_income(row)
    div_won = labels.dividend_won(row, principal=config.DIVIDEND_PRINCIPAL)
    income_intuition = f"100만원당 연 ~{div_won:,}원" if div_won > 0 else None

    # 네이버 PER/PBR이 있으면 우선 사용(무키 모드에서도 실제 값 노출)
    per_disp = overview.get("per") if overview.get("per") is not None else row.get("PER")
    pbr_disp = overview.get("pbr") if overview.get("pbr") is not None else row.get("PBR")

    verdicts = [
        {"cat": "가치 (싼가?)", "emoji": "💎", "label": v_label, "tone": v_tone,
         "word": v_label, "intuition": labels.value_badge(row),
         "metrics": [("PER", _fmt_num(per_disp, "배", 1)), ("PBR", _fmt_num(pbr_disp, "배", 2))],
         "score": row.get("value_score")},
        {"cat": "수익성 (잘 버나?)", "emoji": "🛡️", "label": q_label, "tone": q_tone,
         "word": q_label, "intuition": "EPS/BPS 기반 근사치(정확 ROE는 후속 단계)",
         "metrics": [("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 0)),
                     ("EPS", ui.fmt_won(overview.get("eps") or row.get("EPS")))],
         "score": row.get("quality_score")},
        {"cat": "배당 (주주환원)", "emoji": "💰", "label": i_label, "tone": i_tone,
         "word": i_label, "intuition": income_intuition,
         "metrics": [("배당수익률", _fmt_num(overview.get("div_yield") or row.get("DIV"), "%", 2)),
                     ("주당배당금", ui.fmt_won(row.get("DPS")))],
         "score": row.get("income_score")},
    ]
    st.markdown(uc.render_summary_cards(verdicts), unsafe_allow_html=True)

    st.markdown("**📊 점수 분해**")
    st.markdown(uc.render_subscore_bars(row), unsafe_allow_html=True)
    st.caption("점수 막대는 전체 종목 대비 상대 순위입니다. 매수 신호가 아닙니다.")

    with st.expander("📖 용어 쉽게 보기 (PER·PBR·ROE 등)", expanded=False):
        st.markdown(
            "\n".join(
                f"- {uc.render_glossary_tooltip(term)} {labels.GLOSSARY[term]}"
                for term in labels.GLOSSARY
            ),
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("#### 📈 가격 맥락")
    if has_price:
        w52 = price_context.week52_position(ohlcv)
        rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)
        alignment = price_context.ma_alignment(ohlcv)
        st.markdown(uc.render_week52(w52), unsafe_allow_html=True)
        st.markdown(uc.render_returns(rets), unsafe_allow_html=True)
        st.caption(f"추세: {alignment} (SMA20/60/120 배열 기준)")
        st.markdown("**📉 가격 차트**")
        sig = latest_signals(ohlcv)
        st.caption(labels.signal_text(sig, ma_alignment=alignment))
        st.plotly_chart(ui.make_overview_figure(ohlcv, f"{name} 가격"),
                        use_container_width=True)
    else:
        st.info("가격 데이터가 없어 가격 맥락을 표시할 수 없습니다(거래정지/상장폐지 가능).")

# ══════════════════════════════════════════════════════════════════════
# TAB 2 — 수급 주체 (기관·외국인 / 네이버 무키)
# ══════════════════════════════════════════════════════════════════════
with tab_flow:
    st.markdown("#### 💰 수급 주체 — 기관·외국인 일별 순매매")
    if flows is None or flows.empty:
        st.info("수급 데이터를 불러오지 못했습니다(네이버 일시 오류 가능). 잠시 후 다시 시도해 주세요.")
    else:
        s = flows_summary
        # 누적 순매수 요약 표(투자자 × 기간)
        win = s["windows"]
        rows_disp = []
        for inv in ("기관", "외국인", "개인"):
            rows_disp.append({
                "투자자": inv,
                "5일": _fmt_shares(win.get(5, {}).get(inv)),
                "20일": _fmt_shares(win.get(20, {}).get(inv)),
                "60일": _fmt_shares(win.get(60, {}).get(inv)),
            })
        st.table(pd.DataFrame(rows_disp).set_index("투자자"))

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("기관 (최근 5일)", _fmt_shares(win.get(5, {}).get("기관")) + " 주",
                      delta=s["inst_trend"])
        with m2:
            st.metric("외국인 (최근 5일)", _fmt_shares(win.get(5, {}).get("외국인")) + " 주",
                      delta=s["foreign_trend"])
        with m3:
            fh = s.get("foreign_hold_pct")
            fc = s.get("foreign_hold_change")
            st.metric("외국인 보유율", "-" if fh is None else f"{fh:.2f}%",
                      delta=None if fc is None else f"{fc:+.2f}%p")

        st.plotly_chart(ui.make_supply_figure(flows), use_container_width=True)
        st.caption(
            "기관·외국인 일별 순매매량(주)과 외국인 보유율. 개인은 −(기관+외국인) 근사치(기타법인 제외). "
            "수급은 '누가 샀나'는 사실일 뿐 매수 신호가 아닙니다."
        )

# ══════════════════════════════════════════════════════════════════════
# TAB 3 — 밸류·재무 (네이버 무키)
# ══════════════════════════════════════════════════════════════════════
with tab_val:
    st.markdown("#### 📊 투자지표 (네이버)")
    if not overview or all(v is None for v in overview.values()):
        st.info("투자지표를 불러오지 못했습니다(네이버 일시 오류 가능).")
    else:
        vcols = st.columns(4)
        vcols[0].metric("PER", _fmt_num(overview.get("per"), "배", 2))
        vcols[1].metric("PBR", _fmt_num(overview.get("pbr"), "배", 2))
        vcols[2].metric("EPS", ui.fmt_won(overview.get("eps")))
        vcols[3].metric("BPS", ui.fmt_won(overview.get("bps")))
        vcols2 = st.columns(4)
        vcols2[0].metric("추정 PER", _fmt_num(overview.get("est_per"), "배", 2))
        vcols2[1].metric("배당수익률", _fmt_num(overview.get("div_yield"), "%", 2))
        vcols2[2].metric("동일업종 PER", _fmt_num(overview.get("sector_per"), "배", 2))
        vcols2[3].metric("외국인 보유율", _fmt_num(overview.get("foreign_hold_pct"), "%", 2))
        st.caption("추정(E)은 증권사 컨센서스 기반 추정치입니다.")

    st.divider()
    st.markdown("#### 🏢 기업실적분석 (매출·영업이익·순이익 추세)")
    fin = ui.load_financials(selected)
    if fin is None or fin.empty:
        st.info("재무 데이터를 불러오지 못했습니다.")
    else:
        st.plotly_chart(ui.make_financials_figure(fin), use_container_width=True)
        with st.expander("📋 상세 재무표 (연간+분기, (E)=추정)", expanded=False):
            st.dataframe(fin, use_container_width=True)

    st.divider()
    st.markdown("#### ⚖️ 동일업종 비교")
    peers = ui.load_peers(selected)
    if peers is None or peers.empty:
        st.info("동일업종 비교 데이터를 불러오지 못했습니다.")
    else:
        st.dataframe(peers, use_container_width=True)

    st.divider()
    st.markdown("#### 🔢 상세 숫자")
    detail_rows = [
        ("PER", _fmt_num(overview.get("per") or row.get("PER"), "배", 2)),
        ("PBR", _fmt_num(overview.get("pbr") or row.get("PBR"), "배", 2)),
        ("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 1)),
        ("EPS", ui.fmt_won(overview.get("eps") or row.get("EPS"))),
        ("BPS", ui.fmt_won(overview.get("bps") or row.get("BPS"))),
        ("배당수익률", _fmt_num(overview.get("div_yield") or row.get("DIV"), "%", 2)),
        ("시가총액", ui.fmt_won(row.get("시가총액"))),
        ("거래대금(당일)", ui.fmt_won(row.get("거래대금"))),
        ("현재가(종가)", _fmt_num(row.get("종가"), "원", 0)),
    ]
    st.table(pd.DataFrame(detail_rows, columns=["항목", "값"]).set_index("항목"))

# ══════════════════════════════════════════════════════════════════════
# TAB 4 — 기술·리스크
# ══════════════════════════════════════════════════════════════════════
with tab_tech:
    risk_flags = compute_risk_flags(ohlcv if has_price else None)

    st.markdown("#### ⚠️ 리스크 체크")
    st.markdown(uc.render_risk(risk_flags, _RISK_UNKNOWN_CAPTION), unsafe_allow_html=True)
    if has_price:
        grade, daily_pct = price_context.volatility_grade(ohlcv, window=20)
        if grade is not None:
            st.caption(f"변동성 등급: {grade} (최근 일간 변동성 {_fmt_num(daily_pct, '%', 2)})")

    st.divider()
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
    st.markdown("#### 🧭 판단 체크리스트 (참고용)")
    axes = build_checklist(row, ohlcv if has_price else None, risk_flags,
                           scored=scored, flows_summary=flows_summary)
    st.markdown(uc.render_checklist(axes), unsafe_allow_html=True)
    st.caption(
        "체크리스트는 축별 사실을 분리 표시한 판단 보조입니다. 합산 매수점수가 아니며, "
        "단독 판단 근거로 삼지 마세요(투자 권유 아님)."
    )

    st.divider()
    with st.expander("🔬 기술적 지표 자세히 (RSI·MACD·이격도)", expanded=False):
        if has_price:
            st.markdown("**지표별 시장 백분위**")
            metric_specs = [
                ("PER", "PER", True, "저렴"), ("PBR", "PBR", True, "저렴"),
                ("DIV", "배당수익률", False, "상위"), ("ROE_approx", "ROE(근사)", False, "상위"),
                ("시가총액", "시가총액", False, "상위"), ("거래대금", "거래대금", False, "상위"),
            ]
            chips = []
            for col, label, lower_better, hint in metric_specs:
                if col not in scored.columns:
                    continue
                p = metric_percentile(scored, selected, col, lower_is_better=lower_better)
                chips.append((label, None if p is None or pd.isna(p) else p, hint))
            st.markdown(uc.render_percentile_chips(chips), unsafe_allow_html=True)

            disp = price_context.disparity(ohlcv, windows=(20, 60))
            mdd = price_context.max_drawdown(ohlcv, window=config.WEEK52_WINDOW)
            vol_ratio = price_context.volume_ratio(ohlcv, window=20)
            rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)
            dcols = st.columns(3)
            with dcols[0]:
                st.metric("20일선 이격도", _fmt_num(disp.get(20), "%", 1))
                st.metric("최대낙폭(MDD)", _fmt_num(mdd, "%", 1))
            with dcols[1]:
                st.metric("60일선 이격도", _fmt_num(disp.get(60), "%", 1))
                st.metric("거래량 배수", _fmt_num(vol_ratio, "배", 1))
            with dcols[2]:
                st.metric("이익수익률(1/PER)", labels.earnings_yield(row))
                st.metric("12개월 수익률", _fmt_pct(rets.get("12개월")))

            st.markdown("**기술적 지표 풀이 (RSI·MACD)**")
            st.write(labels.indicator_plain(latest_signals(ohlcv)))
            st.plotly_chart(ui.make_indicator_figure(ohlcv), use_container_width=True)
        else:
            st.info("가격 데이터가 없어 기술 지표를 표시할 수 없습니다.")

    st.divider()
    st.markdown("#### 🎯 손절/익절 이탈 감시")
    latest_close = float(ohlcv["close"].iloc[-1]) if has_price else None
    mcols = st.columns(2)
    with mcols[0]:
        stop_in = st.number_input("손절가 (₩)", min_value=0.0, value=0.0, step=100.0,
                                  key="monitor_stop")
    with mcols[1]:
        target_in = st.number_input("익절가 (₩)", min_value=0.0, value=0.0, step=100.0,
                                    key="monitor_target")
    if latest_close is None:
        st.info("가격 데이터가 없어 이탈 감시를 할 수 없습니다.")
    else:
        stop = stop_in if stop_in > 0 else None
        target = target_in if target_in > 0 else None
        if stop is None and target is None:
            st.caption("손절가/익절가를 입력하면 최신 종가와 비교해 도달·이탈 사실을 알려드립니다.")
        else:
            res = price_context.monitor_targets(latest_close, stop=stop, target=target)
            status = res.get("status", "범위내")
            msg = f"최신 종가 ₩{latest_close:,.0f} — "
            if status == "익절도달":
                st.success(msg + f"입력하신 익절가 ₩{target:,.0f} 도달")
            elif status == "손절이탈":
                st.warning(msg + f"입력하신 손절가 ₩{stop:,.0f} 이탈")
            else:
                st.info(msg + "입력 범위 내")
            st.caption("사실 고지일 뿐 주문·자동매매는 하지 않습니다(투자일임 아님).")

st.divider()
st.info(config.DISCLAIMER, icon="⚠️")
