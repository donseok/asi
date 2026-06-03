"""ui_theme.build_css() 단위 테스트.

build_css()는 부작용 없는 순수 문자열 빌더(네트워크/Streamlit 호출 없음)이므로
'특정 토큰/클래스/문구 포함'을 단언해 디자인 시스템 누락을 잡는다.
design-light.html(비주얼 source of truth)의 핵심 토큰 값을 검증한다.
"""
from __future__ import annotations

import ui_theme


def test_build_css_returns_str():
    css = ui_theme.build_css()
    assert isinstance(css, str)
    assert len(css) > 0


def test_build_css_wrapped_in_style_tag():
    # st.markdown(unsafe_allow_html=True)에 그대로 넣을 수 있도록 <style>로 감싼다.
    css = ui_theme.build_css()
    assert "<style>" in css
    assert "</style>" in css


def test_build_css_loads_pretendard_font():
    # Pretendard CDN <link> 또는 @import가 포함되어야 한국어 폰트 톤이 맞는다.
    css = ui_theme.build_css()
    assert "pretendard" in css.lower()
    assert "cdn.jsdelivr.net" in css


def test_build_css_has_root_color_tokens():
    # design-light.html :root 색 토큰(배경/표면/잉크/브랜드)
    css = ui_theme.build_css()
    assert ":root" in css
    for token in (
        "--bg:#f4f6fa",
        "--surface:#ffffff",
        "--ink:#161b22",
        "--ink-3:#5b6573",
        "--ink-4:#6b7480",
        "--accent:#3182f6",
        "--accent-ink:#1759c2",
        "--accent-weak:#e8f1ff",
    ):
        assert token in css, f"누락된 색 토큰: {token}"


def test_build_css_has_korea_convention_colors():
    # 한국 관습: 상승=빨강 #e74c3c, 하락=파랑 #3498db
    css = ui_theme.build_css()
    assert "--up:#e74c3c" in css
    assert "--down:#3498db" in css


def test_build_css_has_semantic_tokens():
    css = ui_theme.build_css()
    for token in ("--good:#14682b", "--warn:#b45309", "--violet:#6541d6"):
        assert token in css, f"누락된 시맨틱 토큰: {token}"


def test_build_css_has_radius_and_shadow_tokens():
    css = ui_theme.build_css()
    for token in ("--r-card:16px", "--r-md:12px", "--r-sm:9px", "--r-pill:999px", "--r-xl:20px"):
        assert token in css, f"누락된 라운드 토큰: {token}"
    # 그림자 토큰(앰비언트+키 2겹)
    assert "--sh-soft:" in css
    assert "--sh-card:" in css
    assert "--sh-pop:" in css


def test_build_css_has_spacing_tokens():
    css = ui_theme.build_css()
    # 8px 베이스 여백
    for token in ("--s-2:8px", "--s-4:16px", "--s-6:24px", "--s-7:32px"):
        assert token in css, f"누락된 여백 토큰: {token}"


def test_build_css_has_component_classes():
    # 스크리너/종목분석 페이지가 쓰는 공통 컴포넌트 클래스
    css = ui_theme.build_css()
    for cls in (
        ".asi-card",
        ".asi-badge",
        ".asi-summary",
        ".asi-risk",
        ".asi-table",
        ".asi-checklist",
    ):
        assert cls in css, f"누락된 컴포넌트 클래스: {cls}"


def test_build_css_badge_variants_use_korea_and_semantic_colors():
    # 뱃지 변형(저평가/우량/고배당)이 토큰 색을 참조
    css = ui_theme.build_css()
    assert ".asi-badge.value" in css
    assert ".asi-badge.quality" in css
    assert ".asi-badge.income" in css
