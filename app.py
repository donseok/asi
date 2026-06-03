"""ASI — Antigravity Stock Insight (Phase 0a MVP)

홈 화면: 소개 + 데이터 신선도 + 갱신 버튼 + 디스클레이머.
실제 기능은 사이드바의 멀티페이지(스크리너 / 종목분석)에 있다.

실행:  streamlit run app.py   (프로젝트 루트에서)
"""
from __future__ import annotations

import streamlit as st

import config
import ui_helpers as ui

st.set_page_config(page_title="ASI — 한국 주식 분석", page_icon="📈", layout="wide")

st.title("📈 ASI — Antigravity Stock Insight")
st.caption("Phase 0a MVP · 무료 공개 데이터(KRX/pykrx) 기반 · 실거래 기능 없음")

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(
        """
        ### 무엇을 하는 도구인가요?
        - **📊 스크리너**: 밸류에이션·재무·기술 조건으로 수천 종목 중 후보를 좁힙니다.
        - **🔍 종목분석**: 특정 종목 하나를 차트·지표·밸류에이션·리스크로 깊게 들여다봅니다.

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

st.subheader("데이터 출처 (Phase 0a)")
st.markdown(
    """
    | 데이터 | 출처 | 비고 |
    |---|---|---|
    | 종목 마스터 | FinanceDataReader (실패 시 pykrx 폴백) | 우선주·스팩·리츠 제외 |
    | PER/PBR/EPS/BPS/DIV/시총 | pykrx `get_market_fundamental` + `get_market_cap` | KRX 기준 |
    | ROE | **EPS/BPS 근사치** (`ROE_approx`) | 정확한 ROE는 Phase 0b의 DART로 |
    | 일봉 OHLCV | pykrx (수정주가) | 400일 |
    """
)

st.info(config.DISCLAIMER, icon="⚠️")
