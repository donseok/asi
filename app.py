"""ASI — Antigravity Stock Insight (Phase 0a MVP)

홈 화면: 소개 + 데이터 신선도 + 갱신 버튼 + 디스클레이머.
실제 기능은 사이드바의 멀티페이지(스크리너 / 종목분석)에 있다.

실행:  streamlit run app.py   (프로젝트 루트에서)
"""
from __future__ import annotations

import streamlit as st

import config
import ui_helpers as ui
import ui_theme

st.set_page_config(page_title="ASI — 한국 주식 분석", page_icon="📈", layout="wide")

# 라이트 핀테크 디자인 토큰/컴포넌트 CSS를 1회 주입(홈도 페이지 톤 일치 — 스펙 §3).
ui_theme.inject_css()

st.title("📈 ASI — Antigravity Stock Insight")
st.caption("Phase 0a MVP · 무료 공개 데이터(KRX/pykrx) 기반 · 실거래 기능 없음")

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(
        """
        ### 무엇을 하는 도구인가요?
        - **📊 스크리너**: 프리셋 + 자유 검색(이름·코드)·필터(시총/거래대금/등락률)·정렬로
          수천 종목 중 후보를 좁힙니다.
        - **🔍 종목분석**: 한 종목을 **요약 · 수급 주체(기관·외국인) · 밸류/재무 · 기술/리스크**
          4개 탭으로 깊게 들여다봅니다.

        왼쪽 사이드바에서 페이지를 선택하세요. 스크리너 결과에서 종목을 고르면
        종목분석 페이지로 이어집니다.
        """
    )
with col2:
    st.metric("데이터 마지막 갱신", ui.asof_text())
    if st.button("🔄 데이터 새로 받기", use_container_width=True):
        with st.spinner("KRX에서 전 종목 데이터를 다시 받는 중... (수십 초)"):
            ui.refresh_all_caches()
        st.success("갱신 완료")
        st.rerun()

st.divider()

st.subheader("데이터 출처")
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
