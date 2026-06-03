"""ASI 핵심 로직 패키지 (Streamlit 비의존 — UI와 분리).

Phase 1에서 FastAPI 백엔드로 그대로 이식할 수 있도록, 이 패키지는
streamlit을 import 하지 않는다. 캐싱(st.cache_data)은 UI 레이어에서만 한다.
"""
