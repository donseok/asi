"""ASI — Antigravity Stock Insight (Phase 0a MVP) · 홈

ASI Quietude+ 재설계(디자인 패널 만장일치 채택안).
5섹션 세로 흐름: 히어로 / 데이터 신선도+KPI / WHAT IS THIS / HOW IT WORKS /
데이터 출처+면책. 모두 순수 st.markdown(HTML) + Streamlit 위젯(외부 라이브러리 없음).

기존 기능 보존:
  - ui.asof_text()           : 데이터 마지막 갱신 시각
  - '데이터 새로 받기' 버튼  : ui.refresh_all_caches() + 스피너 + st.rerun()
  - 데이터 출처 표           : 마크다운 표 유지
  - config.DISCLAIMER        : st.info 유지(스타일은 테마가 처리)

CTA/네비는 '시각=HTML + 동작=page_link' 2단 핸드오프(스크리너가 쓰는 검증 패턴).

실행:  streamlit run app.py   (프로젝트 루트에서)
"""
from __future__ import annotations

import streamlit as st

import config
import ui_helpers as ui
import ui_theme

st.set_page_config(page_title="ASI — 한국 주식 분석", page_icon="📈", layout="wide")

# 디자인 토큰/컴포넌트 CSS + 사이드바 브랜드 1회 주입(홈도 페이지 톤 일치).
ui_theme.inject_css()

# 페이지 경로 상수(switch_page 핸드오프와 동일 계약 — 이모지 포함 파일명 유지).
PAGE_SCREENER = "pages/1_📊_스크리너.py"
PAGE_ANALYZER = "pages/2_🔍_종목분석.py"

asof = ui.asof_text()

# ════════════════════════════════════════════════════════════════
# [1] HERO
# ════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="asi-hero">'
    '<div class="asi-eyebrow">KOREAN EQUITY INSIGHT · PHASE 0a</div>'
    '<div class="asi-hero-title">수천 종목 중,<br>'
    '<em>당신의 기준</em>에 맞는 곳으로.</div>'
    '<p class="asi-hero-sub">복잡한 숫자는 도구가 맞춰드립니다. '
    '목적을 하나 고르면 후보를 좁히고, 한 종목을 4개 축으로 깊게 봅니다.</p>'
    '<div style="margin-top:18px">'
    '<span class="asi-hero-aside"><span class="asi-dot" aria-hidden="true"></span>'
    '<span class="k">데이터 마지막 갱신</span>'
    f'<span class="v num">{asof}</span>'
    "</span></div>"
    "</div>",
    unsafe_allow_html=True,
)

# HERO CTA — 시각은 위 HTML, 동작은 page_link.
c1, c2, _ = st.columns([1, 1, 4])
with c1:
    st.page_link(PAGE_SCREENER, label="스크리너 시작", icon="📊")
with c2:
    st.page_link(PAGE_ANALYZER, label="종목분석", icon="🔍")

# ════════════════════════════════════════════════════════════════
# [2] DATA FRESHNESS + 갱신 + KPI 스트립
# ════════════════════════════════════════════════════════════════
st.markdown('<div class="asi-section"></div>', unsafe_allow_html=True)

fb, btn = st.columns([3, 1])
with fb:
    st.markdown(
        '<div class="asi-freshbar">'
        '<span class="asi-dot" aria-hidden="true"></span>'
        '<span class="lbl">데이터 신선도</span>'
        f'<span class="asof num">{asof}</span>'
        "</div>",
        unsafe_allow_html=True,
    )
with btn:
    if st.button("🔄 데이터 새로 받기", use_container_width=True):
        with st.spinner("KRX에서 전 종목 데이터를 다시 받는 중... (수십 초)"):
            ui.refresh_all_caches()
        st.success("갱신 완료")
        st.rerun()

# KPI 스트립 — 스냅샷 로드 실패해도 홈은 죽지 않게 방어.
try:
    _snap = ui.load_scored_snapshot()
    n_stocks = f"{len(_snap):,}"
except Exception:
    n_stocks = "—"

st.markdown(
    '<div class="asi-kpis" style="margin-top:12px">'
    '<div class="asi-kpi"><div class="k">분석 종목 수</div>'
    f'<div class="v num">{n_stocks}</div></div>'
    '<div class="asi-kpi"><div class="k">마지막 갱신</div>'
    f'<div class="v num">{asof}</div></div>'
    '<div class="asi-kpi"><div class="k">데이터 모드</div>'
    '<div class="v">무료 공개데이터</div></div>'
    "</div>",
    unsafe_allow_html=True,
)

# ════════════════════════════════════════════════════════════════
# [3] WHAT IS THIS — 2 feature 카드
# ════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="asi-section"><div class="asi-eyebrow">WHAT IS THIS</div></div>',
    unsafe_allow_html=True,
)
f1, f2 = st.columns(2)
with f1:
    st.markdown(
        '<div class="asi-feature">'
        '<div class="idx num">01</div>'
        '<div class="ttl">📊 스크리너</div>'
        '<div class="desc">목적을 하나 고르면 프리셋·필터·정렬로 '
        '수천 종목 중 후보를 좁힙니다. 복잡한 숫자는 알아서 맞춰드립니다.</div>'
        '<div class="ft-foot"></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.page_link(PAGE_SCREENER, label="스크리너 시작 →", icon="📊")
with f2:
    st.markdown(
        '<div class="asi-feature">'
        '<div class="idx num">02</div>'
        '<div class="ttl">🔍 종목분석</div>'
        '<div class="desc">한 종목을 요약 · 수급(기관·외국인) · 밸류/재무 · '
        '기술/리스크 4개 탭으로 깊게 들여다봅니다.</div>'
        '<div class="ft-foot"></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.page_link(PAGE_ANALYZER, label="종목분석 열기 →", icon="🔍")

# ════════════════════════════════════════════════════════════════
# [4] HOW IT WORKS — 3 스텝
# ════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="asi-section"><div class="asi-eyebrow">HOW IT WORKS</div>'
    '<div class="asi-steps">'
    '<div class="asi-step"><div class="n num">01</div>'
    '<div class="t">목적 선택</div>'
    '<div class="d">저평가·우량·고배당 등 찾는 방향을 하나만 고릅니다.</div></div>'
    '<div class="asi-step"><div class="n num">02</div>'
    '<div class="t">후보 압축</div>'
    '<div class="d">필터·정렬로 수천 종목을 읽기 쉬운 카드 후보로 좁힙니다.</div></div>'
    '<div class="asi-step"><div class="n num">03</div>'
    '<div class="t">4축 심층분석</div>'
    '<div class="d">고른 한 종목을 요약·수급·밸류·기술 4탭으로 깊게 봅니다.</div></div>'
    "</div></div>",
    unsafe_allow_html=True,
)

# ════════════════════════════════════════════════════════════════
# [5] DATA SOURCES + DISCLAIMER
# ════════════════════════════════════════════════════════════════
st.markdown(
    '<div class="asi-section"><div class="asi-eyebrow">DATA SOURCES</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    | 데이터 | 출처 | 비고 |
    |---|---|---|
    | 종목 마스터·종가·시총·거래대금·등락률 | FinanceDataReader (KRX) | 무키 |
    | 일봉 OHLCV | pykrx (수정주가) | 무키, 400일 |
    | **수급(기관·외국인)·외국인 보유율** | **네이버 금융** | 무키, 종목 상세 '수급' 탭 |
    | **PER/PBR/EPS/BPS/배당·추정·동일업종·재무실적** | **네이버 금융** | 무키, '밸류·재무' 탭 |
    | 전 종목 PER/PBR·수급 랭킹 | pykrx (KRX 로그인 시) | `KRX_ID`/`KRX_PW` 있으면 자동 강화 |

    > KRX 데이터포털이 시장 스냅샷을 로그인 전용으로 전환해, 무키 환경에서는 위 네이버 소스로
    > 종목 상세 정보를 보강합니다. 전 종목 밸류/수급 랭킹이 필요하면 KRX 무료 계정을 `.env`에 설정하세요.
    """
)

st.info(config.DISCLAIMER, icon="⚠️")

st.markdown(
    '<div class="asi-foot">'
    '<span class="mark" aria-hidden="true"></span>'
    '<span><b>ASI</b> — Antigravity Stock Insight</span>'
    '<span class="sep">·</span><span>Not investment advice</span>'
    '<span class="sep">·</span><span>Phase 0a</span>'
    "</div>",
    unsafe_allow_html=True,
)
