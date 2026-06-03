"""스크리너 페이지 — "어떤 주식을 찾으세요?" 목적 선택형 + 카드형 결과.

설계 스펙 §4·§4.5. 이 파일은 UI 조립만 담당한다:
  - 필터/정렬/상위N → core.analytics.screening.apply_screen (순수, 테스트됨)
  - 뱃지/왜추천?/점수색 → core.analytics.labels (순수, 테스트됨)
  - 상위 X% → core.analytics.scoring.percentile_of (순수, 테스트됨)
  - 카드 HTML → ui_components.render_stock_card (순수 HTML 빌더, 테스트됨)
  - 디자인 토큰 → ui_theme.inject_css
  - 스냅샷 로딩 → ui_helpers.load_scored_snapshot (캐시 로더)
비즈니스 로직을 여기서 재구현하지 않는다(SRP / 단일 진실원천).

데이터 계약: scored는 RangeIndex이고 ticker는 '컬럼'(6자리 문자열)이다.
현재가/시총/거래대금 컬럼은 한글(종가/시가총액/거래대금)이다.
"""
from __future__ import annotations

import streamlit as st

import config
import ui_components
import ui_helpers as ui
import ui_theme
from core.analytics import labels, screening
from core.analytics.scoring import percentile_of
from core.data.fundamentals import has_valuation_data

st.set_page_config(page_title="ASI — 스크리너", page_icon="📊", layout="wide")

# 라이트 핀테크 디자인 토큰 1회 주입
ui_theme.inject_css()

# ── 헤더 카피 (§4.1-1) ──────────────────────────────────────────────
st.title("어떤 주식을 찾으세요?")
st.caption("하나만 골라주세요. 복잡한 숫자는 알아서 맞춰드립니다.")

# ── 스냅샷 로딩 + 실패/빈 데이터 안내 (§9) ─────────────────────────────
try:
    scored = ui.load_scored_snapshot()
except Exception as exc:  # 네트워크/pykrx 실패 등 — 앱이 죽지 않게
    st.error(
        "종목 데이터를 불러오지 못했습니다. 홈으로 돌아가 '🔄 데이터 새로 받기'를 "
        f"눌러 다시 시도해 주세요.\n\n(원인: {exc})"
    )
    st.stop()

if scored is None or scored.empty:
    st.warning(
        "표시할 종목 데이터가 비어 있습니다. 홈에서 '🔄 데이터 새로 받기'로 "
        "스냅샷을 먼저 받아 주세요."
    )
    st.stop()

# 밸류에이션(PER/PBR/배당) 미제공 안내 — KRX 포털이 해당 데이터를 로그인 필수로
# 잠가, 무키(FDR) 모드에서는 시가총액 기반 '안정적인 대형주' 위주로만 동작한다.
if not has_valuation_data(scored):
    st.info(
        "ℹ️ 현재 **무키(FDR) 모드**입니다 — KRX가 PER·PBR·ROE·배당 데이터를 로그인 "
        "전용으로 전환해, 가치/배당/종합 프리셋은 결과가 비어 있을 수 있습니다. "
        "**'안정적인 대형주'(시가총액 기준)**는 정상 동작합니다. 전체 지표를 쓰려면 "
        "KRX 무료 계정의 `KRX_ID`/`KRX_PW`를 `.env`에 설정하세요."
    )

# ── 목적 타일 4개 (단일 선택) — §4.1-2, §4.5 가이드 카피 ──────────────
# 타일 라벨/이모지/가이드는 PRESETS에서 가져온다(하드코딩 금지).
preset_keys = list(screening.PRESETS.keys())


def _preset_caption(key: str) -> str:
    p = screening.PRESETS[key]
    return f"{p['emoji']} {p['label']}"


selected_preset = st.radio(
    "목적을 선택하세요",
    options=preset_keys,
    format_func=_preset_caption,
    horizontal=True,
    key="screener_preset",
)
# 선택된 프리셋의 가이드 카피(정적, §4.5) — PRESETS['guide'] 사용
st.markdown(
    f"<div class='preset-guide'>{screening.PRESETS[selected_preset]['guide']}</div>",
    unsafe_allow_html=True,
)

# ── 보조 컨트롤 (시장 · 정렬 · 개수 · 자유검색) ───────────────────────
has_val = has_valuation_data(scored)
c_market, c_sort, c_limit, c_query = st.columns([2, 2, 1, 2])
with c_market:
    market = st.radio(
        "시장",
        options=("전체", "코스피", "코스닥"),
        horizontal=True,
        key="screener_market",
    )
with c_sort:
    sort_choices = ["프리셋 기본"] + list(screening.SORT_OPTIONS.keys())
    sort_by_label = st.selectbox("정렬 기준", options=sort_choices, key="screener_sort")
    sort_by = None if sort_by_label == "프리셋 기본" else sort_by_label
with c_limit:
    limit = st.selectbox(
        "개수",
        options=(20, 30, 50, 100),
        index=(20, 30, 50, 100).index(config.SCREENER_DEFAULT_LIMIT),
        key="screener_limit",
    )
with c_query:
    query = st.text_input(
        "자유 검색 (이름·코드)",
        value="",
        placeholder="예: 삼성전자 또는 005930",
        key="screener_query",
    )

with st.expander("▸ 자유 필터 (유동성·시총·등락률·밸류에이션 범위)", expanded=False):
    st.caption(
        "초보자라면 기본값 그대로 두셔도 됩니다. 조건을 조절하면 원하는 종목군을 좁힐 수 있습니다."
    )
    fa, fb = st.columns(2)
    with fa:
        min_cap_eok = st.number_input(
            "시가총액 하한 (억원)", min_value=0,
            value=int(config.MIN_MARKET_CAP / 1e8), step=50, key="screener_min_cap",
        )
        min_value_eok = st.number_input(
            "당일 거래대금 하한 (억원)", min_value=0,
            value=int(config.MIN_AVG_TRADING_VALUE / 1e8), step=1, key="screener_min_value",
        )
        max_cap_eok = st.number_input(
            "시가총액 상한 (억원, 0=무제한)", min_value=0, value=0, step=100,
            key="screener_max_cap",
        )
    with fb:
        chg_lo, chg_hi = st.slider(
            "당일 등락률 범위 (%)", min_value=-30.0, max_value=30.0,
            value=(-30.0, 30.0), step=0.5, key="screener_chg",
        )
        if has_val:
            max_per = st.number_input("PER 상한 (0=무제한)", min_value=0.0, value=0.0,
                                      step=1.0, key="screener_max_per")
            max_pbr = st.number_input("PBR 상한 (0=무제한)", min_value=0.0, value=0.0,
                                      step=0.1, key="screener_max_pbr")
        else:
            max_per = max_pbr = 0.0
            st.caption("PER/PBR 필터는 밸류에이션 데이터(KRX 로그인)가 있을 때 활성화됩니다.")

min_cap = float(min_cap_eok) * 1e8
min_value = float(min_value_eok) * 1e8
max_cap = float(max_cap_eok) * 1e8 if max_cap_eok > 0 else None
change_min = None if chg_lo <= -30.0 else float(chg_lo)
change_max = None if chg_hi >= 30.0 else float(chg_hi)
max_per_v = float(max_per) if max_per and max_per > 0 else None
max_pbr_v = float(max_pbr) if max_pbr and max_pbr > 0 else None

# ── 스크리닝 실행 (순수 함수에 위임) ──────────────────────────────────
result = screening.apply_screen(
    scored,
    selected_preset,
    market=market,
    query=query,
    limit=int(limit),
    min_cap=min_cap,
    min_value=min_value,
    max_cap=max_cap,
    change_min=change_min,
    change_max=change_max,
    max_per=max_per_v,
    max_pbr=max_pbr_v,
    sort_by=sort_by,
)

# ── 결과 헤더 + "안정적 대형주" 한계 캡션 (§4.1-4, §4.5, §8) ─────────────
preset_label = screening.PRESETS[selected_preset]["label"]
order_label = sort_by if sort_by else f"{preset_label} 순"
st.subheader(f"✅ 조건에 맞는 {len(result)}종목 — {order_label}")
if selected_preset == "stable" and not sort_by:
    st.caption(
        "ℹ️ '안정적인 대형주'는 시가총액(덩치) 기준만 반영합니다. "
        "주가 변동성·역사적 안정성은 아직 반영하지 않습니다(정직 고지)."
    )

# 0건 안내 (§9)
if result.empty:
    st.info(
        "조건에 맞는 종목이 없습니다 — 시장을 '전체'로 넓히거나 "
        "고급 설정에서 유동성 하한을 완화해 보세요."
    )
    st.stop()

# ── 색 범례 1회 (§4.5) ──────────────────────────────────────────────
st.markdown(
    "<div class='score-legend'>점수 막대: "
    "<span class='legend-good'>🟢 상위</span> · "
    "<span class='legend-warn'>🟠 중간</span> · "
    "<span class='legend-muted'>⚪ 하위</span> "
    "= 전체 종목 대비 상대 순위(매수 신호 아님)</div>",
    unsafe_allow_html=True,
)

# ── 카드 목록 (§4.3) ────────────────────────────────────────────────
# 결과는 ticker '컬럼'으로 순회한다(index는 RangeIndex).
for _, row in result.iterrows():
    ticker = str(row["ticker"]).zfill(6)
    score = row.get("score")
    # 상위 X% = 100 - 백분위(percentile_of는 ticker '컬럼' 기준 조회).
    pct = percentile_of(scored, ticker, "score")
    rank_pct = None if pct is None else (100.0 - pct)

    card_html = ui_components.render_stock_card(
        row,
        badges=labels.badges(row),
        explain=labels.explain_row(row),
        tier=labels.score_tier(score),
        rank_pct=rank_pct,
    )
    st.markdown(card_html, unsafe_allow_html=True)

    # 카드 HTML 안의 "자세히 보기 →"는 정적이라 클릭 이벤트가 없으므로,
    # 실제 네비게이션은 아래 st.button이 담당한다(핸드오프).
    if st.button("자세히 보기 →", key=f"detail_{ticker}", use_container_width=False):
        st.session_state["selected_ticker"] = ticker
        st.switch_page("pages/2_🔍_종목분석.py")
