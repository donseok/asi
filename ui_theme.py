"""ASI 라이트 핀테크 디자인 시스템 — CSS 토큰/컴포넌트 주입.

`design-light.html`(비주얼 source of truth)의 :root 디자인 토큰과
공통 컴포넌트 클래스를 한 곳에 모아 Streamlit 페이지 상단에서 1회 주입한다.

- build_css(): 부작용 없는 순수 문자열 빌더(테스트 대상).
- inject_css(): st.markdown(unsafe_allow_html=True)로 실제 주입(페이지에서 호출).

한국 관습 유지: 주가 상승=빨강(--up #e74c3c) / 하락=파랑(--down #3498db).
"""
from __future__ import annotations

import streamlit as st

# Pretendard 웹폰트(CDN). design-light.html과 동일한 출처를 사용한다.
_PRETENDARD_IMPORT = (
    "@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/"
    "dist/web/static/pretendard.css');"
)

# design-light.html :root에서 가져온 디자인 토큰(색/라운드/그림자/여백) 요약.
_ROOT_TOKENS = """
:root{
  /* 배경/표면/라인 */
  --bg:#f4f6fa;
  --bg-2:#eef1f7;
  --surface:#ffffff;
  --surface-2:#f8fafc;
  --surface-3:#f2f5f9;
  --line:#e9edf3;
  --line-strong:#dde3ec;
  --line-hair:#f0f3f7;

  /* 잉크(본문/보조/약한) */
  --ink:#161b22;
  --ink-2:#3f4854;
  --ink-3:#5b6573;
  --ink-4:#6b7480;

  /* 브랜드 */
  --accent:#3182f6;
  --accent-strong:#1f6fe5;
  --accent-ink:#1759c2;
  --accent-weak:#e8f1ff;
  --accent-weak-2:#dceaff;

  /* 한국 관습 — 상승=빨강, 하락=파랑 */
  --up:#e74c3c;
  --up-ink:#c92a1e;
  --up-weak:#fdecea;
  --down:#3498db;
  --down-ink:#1f7fc9;
  --down-weak:#e9f3fb;

  /* 시맨틱 */
  --good:#14682b;
  --good-bright:#16a34a;
  --good-chip:#0c7a34;
  --good-weak:#e7f6ec;
  --warn:#b45309;
  --warn-bright:#d97706;
  --warn-weak:#fdf2e3;
  --warn-line:#f5e3c4;
  --violet:#6541d6;
  --violet-weak:#efeaff;
  --gold-ink:#8a5a12;
  --gold-weak:#fbf2dd;

  /* 라운드 */
  --r-xl:20px;
  --r-card:16px;
  --r-md:12px;
  --r-sm:9px;
  --r-pill:999px;

  /* 그림자(앰비언트+키 2겹) */
  --sh-soft:0 1px 2px rgba(20,28,44,.04), 0 2px 6px rgba(20,28,44,.05);
  --sh-card:0 1px 2px rgba(20,28,44,.04), 0 4px 14px rgba(20,28,44,.055);
  --sh-pop:0 2px 6px rgba(20,28,44,.06), 0 14px 32px rgba(20,28,44,.10);

  /* 여백(8px 베이스) */
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px;
  --s-5:20px; --s-6:24px; --s-7:32px; --s-8:40px; --s-9:48px;
}
"""

# 본문 폰트/타이포 베이스. Streamlit 컨테이너에 Pretendard와 톤을 입힌다.
_BASE = """
html, body, [class*="css"], .stApp, .stMarkdown, .stMarkdown p{
  font-family:'Pretendard',-apple-system,'Apple SD Gothic Neo',
    'Malgun Gothic',system-ui,sans-serif;
  letter-spacing:-.011em;
}
.stApp{ background:var(--bg); color:var(--ink); }
.asi-num{ font-variant-numeric:tabular-nums; }
"""

# 공통 컴포넌트 클래스 — 카드/뱃지/요약/리스크/표/체크리스트.
# ui_components.py의 HTML 빌더가 이 클래스를 사용한다.
_COMPONENTS = """
/* 카드 */
.asi-card{
  background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-xl);box-shadow:var(--sh-card);
  padding:20px 20px 18px;margin-bottom:var(--s-4);
}
.asi-card .name{font-size:17.5px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.asi-card .price{font-size:18px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}

/* 뱃지(저평가/우량/고배당 + 시장) */
.asi-badge{
  font-size:11.5px;font-weight:800;padding:4px 10px;border-radius:var(--r-pill);
  display:inline-flex;align-items:center;gap:4px;letter-spacing:-.01em;line-height:1.5;
  border:1px solid transparent;margin-right:6px;
}
.asi-badge.value{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.asi-badge.quality{background:var(--good-weak);color:var(--good);border-color:#d3eedd;}
.asi-badge.income{background:var(--violet-weak);color:var(--violet);border-color:#e2d9ff;}
.asi-badge.mkt-kospi{background:#eaf1ff;color:#2a52b8;border-color:#dbe7ff;}
.asi-badge.mkt-kosdaq{background:#fdeef5;color:#b03478;border-color:#fbdcea;}

/* "왜 추천?" 설명 줄 */
.asi-why{
  font-size:13px;color:var(--ink-2);background:var(--surface-2);
  border:1px solid var(--line);border-radius:var(--r-md);
  padding:11px 13px;line-height:1.55;letter-spacing:-.012em;
}
.asi-why b{color:var(--ink);font-weight:800;}

/* 점수 바 */
.asi-bar{height:8px;border-radius:var(--r-pill);background:var(--bg-2);overflow:hidden;}
.asi-bar > i{display:block;height:100%;border-radius:var(--r-pill);
  background:linear-gradient(90deg,#2f78f0,#62a0ff);}
.asi-score.good{color:var(--good);}
.asi-score.warn{color:var(--warn);}
.asi-score.muted{color:var(--ink-4);}

/* 한눈에 요약 카드 */
.asi-summary{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:20px 20px 18px;
}
.asi-summary .cat{font-size:12.5px;font-weight:700;color:var(--ink-3);}
.asi-summary .word{font-size:25px;font-weight:900;letter-spacing:-.04em;color:var(--ink);line-height:1.1;margin:10px 0;}
.asi-summary .verdict{font-size:11.5px;font-weight:800;padding:4px 11px;border-radius:var(--r-pill);border:1px solid transparent;}
.asi-summary .verdict.good{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.asi-summary .verdict.strong{background:var(--good-weak);color:var(--good);border-color:#d3eedd;}
.asi-summary .verdict.mid{background:var(--gold-weak);color:var(--gold-ink);border-color:#f0e2c0;}

/* 리스크 박스 */
.asi-risk{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px;
}
.asi-risk .rk-name{font-size:14px;font-weight:800;color:var(--ink);}
.asi-risk .rk-state.ok{background:var(--good-weak);color:var(--good);}
.asi-risk .rk-state.mid{background:var(--warn-weak);color:var(--warn);}
.asi-risk .rk-state{font-size:11px;font-weight:800;padding:2px 9px;border-radius:var(--r-pill);}
.asi-risk .rk-note{background:var(--warn-weak);color:var(--warn);font-weight:600;
  font-size:12.5px;line-height:1.55;border-radius:var(--r-md);padding:12px 14px;margin-top:12px;}

/* 상세 숫자 표 */
.asi-table{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);overflow:hidden;
}
.asi-table .k{font-size:11.5px;color:var(--ink-4);font-weight:700;text-transform:uppercase;letter-spacing:.01em;}
.asi-table .v{font-size:19px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}

/* 판단 체크리스트 6축 */
.asi-checklist{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px;
}
.asi-checklist .axis{font-size:14px;font-weight:800;color:var(--ink);}
.asi-checklist .grade.good{color:var(--good);}
.asi-checklist .grade.mid{color:var(--gold-ink);}
.asi-checklist .grade.warn{color:var(--warn);}
.asi-checklist .locked{color:var(--ink-4);font-weight:700;}
.asi-checklist .fact{font-size:12.5px;color:var(--ink-3);line-height:1.55;}
"""

# ui_components.py의 HTML 빌더가 '실제로' emit하는 클래스에 대한 스타일.
# (위 .asi-* 는 예약 클래스. 페이지/컴포넌트는 아래 클래스를 사용한다.)
_BUILDERS = """
.num{font-variant-numeric:tabular-nums;}
.preset-guide{font-size:14px;color:var(--ink-3);background:var(--surface-2);border:1px solid var(--line);
  border-radius:var(--r-md);padding:9px 13px;margin:6px 0 4px;}
.score-legend{font-size:12.5px;color:var(--ink-3);margin:4px 0 12px;}
.score-legend .legend-good{color:var(--good);font-weight:700;}
.score-legend .legend-warn{color:var(--warn);font-weight:700;}
.score-legend .legend-muted{color:var(--ink-4);font-weight:700;}

/* 스크리너 카드 */
.scard{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px 14px;margin-bottom:var(--s-3);}
.scard-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;}
.scard .stock-id{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.scard .stock-name{font-size:17px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.scard .price{font-size:17px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.mkt{font-size:11px;font-weight:800;padding:2px 8px;border-radius:var(--r-pill);}
.mkt.kospi{background:#eaf1ff;color:#2a52b8;}
.mkt.kosdaq{background:#fdeef5;color:#b03478;}
.badge-row{margin:10px 0 8px;display:flex;flex-wrap:wrap;gap:6px;}
.badge{font-size:11.5px;font-weight:800;padding:3px 10px;border-radius:var(--r-pill);
  display:inline-flex;align-items:center;gap:4px;border:1px solid transparent;}
.badge.b-value{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.badge.b-quality{background:var(--good-weak);color:var(--good);border-color:#d3eedd;}
.badge.b-div{background:var(--violet-weak);color:var(--violet);border-color:#e2d9ff;}
.why{font-size:13px;color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);
  border-radius:var(--r-md);padding:10px 12px;line-height:1.5;margin-bottom:10px;}
.why .q{font-weight:800;color:var(--ink);margin-right:6px;}
.score-row{display:flex;align-items:center;gap:16px;}
.score-block{text-align:center;min-width:84px;}
.score-num{font-size:30px;font-weight:900;letter-spacing:-.04em;line-height:1;}
.score-num .u{font-size:13px;font-weight:700;margin-left:2px;}
.score-num.tier-good{color:var(--good);}
.score-num.tier-warn{color:var(--warn);}
.score-num.tier-muted{color:var(--ink-4);}
.score-rank{font-size:11.5px;color:var(--ink-4);font-weight:700;margin-top:2px;}
.bar-wrap{flex:1;}
.bar-label{display:flex;justify-content:space-between;font-size:11.5px;color:var(--ink-3);margin-bottom:5px;}
.bar{height:8px;border-radius:var(--r-pill);background:var(--bg-2);overflow:hidden;}
.bar>i{display:block;height:100%;border-radius:var(--r-pill);background:linear-gradient(90deg,#2f78f0,#62a0ff);}
.scard-foot{margin-top:12px;border-top:1px solid var(--line-hair);padding-top:10px;}
.scard .detail-link{font-size:13px;font-weight:700;color:var(--accent-ink);}

/* 한눈에 요약 */
.sum3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
@media(max-width:760px){.sum3{grid-template-columns:1fr;}}
.sumcard{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:16px 18px;}
.sumcard .head{display:flex;justify-content:space-between;align-items:center;}
.sumcard .cat{font-size:12.5px;font-weight:700;color:var(--ink-3);}
.sumcard .verdict{font-size:11.5px;font-weight:800;padding:3px 10px;border-radius:var(--r-pill);border:1px solid transparent;}
.verdict.v-good{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.verdict.v-strong{background:var(--good-weak);color:var(--good);border-color:#d3eedd;}
.verdict.v-mid{background:var(--gold-weak);color:var(--gold-ink);border-color:#f0e2c0;}
.sumcard .word{font-size:24px;font-weight:900;letter-spacing:-.04em;color:var(--ink);margin:10px 0 6px;line-height:1.1;}
.sumcard .intuition{font-size:12px;font-weight:700;color:var(--accent-ink);background:var(--accent-weak);
  display:inline-block;padding:3px 9px;border-radius:var(--r-pill);margin-bottom:8px;}
.metric-line{display:flex;justify-content:space-between;font-size:12.5px;color:var(--ink-3);
  border-top:1px solid var(--line-hair);padding:5px 0;}
.metric-line .v{color:var(--ink);font-weight:700;}
.subscores{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);
  box-shadow:var(--sh-soft);padding:12px 16px;}

/* 리스크 카드 */
.risk-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:14px 18px;}
.risk-item{padding:6px 0;}
.rk-head{display:flex;align-items:center;gap:8px;}
.rk-dot{width:9px;height:9px;border-radius:50%;display:inline-block;}
.rk-dot.ok{background:var(--good-bright);}
.rk-dot.mid{background:var(--warn-bright);}
.rk-name{font-size:13.5px;color:var(--ink);font-weight:600;flex:1;}
.rk-state{font-size:11px;font-weight:800;padding:2px 9px;border-radius:var(--r-pill);}
.rk-state.ok{background:var(--good-weak);color:var(--good);}
.rk-state.mid{background:var(--warn-weak);color:var(--warn);}
.risk-note{background:var(--warn-weak);color:var(--warn);font-size:12.5px;line-height:1.5;
  border-radius:var(--r-md);padding:10px 13px;margin-top:10px;display:flex;gap:8px;}

/* 판단 체크리스트 */
.checklist-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
@media(max-width:760px){.checklist-grid{grid-template-columns:1fr;}}
.axis-cell{border:1px solid var(--line);border-radius:var(--r-card);padding:12px 14px;background:var(--surface);}
.axis-cell.locked{background:var(--surface-3);border-style:dashed;}
.axis-head{display:flex;justify-content:space-between;align-items:center;}
.axis-name{font-size:14px;font-weight:800;color:var(--ink);}
.axis-cell.locked .axis-name{color:var(--ink-4);}
.axis-grade{font-size:12px;font-weight:800;}
.axis-grade.grade-good{color:var(--good);}
.axis-grade.grade-mid{color:var(--gold-ink);}
.axis-grade.grade-warn{color:var(--warn);}
.axis-facts{margin:8px 0 0;padding-left:16px;}
.axis-facts li{font-size:12px;color:var(--ink-3);line-height:1.5;}
.axis-lock{font-size:11.5px;color:var(--ink-4);margin-top:6px;}

/* 52주 바 */
.week52{margin:6px 0;}
.week52.empty{font-size:13px;color:var(--ink-4);}
.week52-bar{position:relative;height:8px;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--down-weak),var(--surface-3),var(--up-weak));}
.week52-marker{position:absolute;top:-4px;width:4px;height:16px;border-radius:2px;background:var(--ink);transform:translateX(-50%);}
.week52-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--ink-4);margin-top:8px;}
.week52-dd{font-size:12.5px;color:var(--ink-3);margin-top:4px;}
.week52-dd b{color:var(--down-ink);}

/* 기간 수익률 칩 (상승=빨강/하락=파랑) */
.returns{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;}
.ret-chip{display:inline-flex;flex-direction:column;align-items:center;border:1px solid var(--line);
  border-radius:var(--r-md);padding:6px 12px;background:var(--surface);min-width:64px;}
.ret-chip .ret-k{font-size:11px;color:var(--ink-4);}
.ret-chip .ret-v{font-size:14px;font-weight:800;}
.ret-up .ret-v{color:var(--up-ink);}
.ret-down .ret-v{color:var(--down-ink);}
.ret-flat .ret-v{color:var(--ink-4);}

/* 과열도 */
.overheat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);
  box-shadow:var(--sh-soft);padding:12px 16px;}
.oh-head{display:flex;justify-content:space-between;align-items:center;gap:10px;}
.oh-title{font-size:13.5px;font-weight:700;color:var(--ink);}
.oh-note-inline{font-size:11px;color:var(--ink-4);margin-left:6px;font-weight:600;}
.oh-level{font-size:12.5px;font-weight:800;padding:3px 11px;border-radius:var(--r-pill);}
.oh-level.oh-low{background:var(--good-weak);color:var(--good);}
.oh-level.oh-mid{background:var(--accent-weak);color:var(--accent-ink);}
.oh-level.oh-high{background:var(--warn-weak);color:var(--warn);}
.oh-level.oh-hot{background:var(--up-weak);color:var(--up-ink);}
.oh-disc{font-size:11.5px;color:var(--ink-4);margin-top:8px;}

/* 백분위 칩 */
.pctile-chips{display:flex;flex-wrap:wrap;gap:8px;}
.pctile-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:var(--r-pill);padding:4px 12px;background:var(--surface-2);font-size:12px;}
.pctile-chip .pc-k{color:var(--ink-3);font-weight:700;}
.pctile-chip .pc-v{color:var(--ink);font-weight:800;}
.pctile-chip .pc-hint{color:var(--good);font-weight:700;font-size:11px;}

/* 용어 툴팁 */
.glossary-term{font-weight:700;color:var(--ink);}
.glossary-term .gl-ic{color:var(--accent);font-size:11px;cursor:help;}
"""


def build_css() -> str:
    """주입할 전체 CSS를 <style>로 감싼 문자열로 반환(순수, 부작용 없음)."""
    return (
        "<style>\n"
        + _PRETENDARD_IMPORT
        + "\n"
        + _ROOT_TOKENS
        + _BASE
        + _COMPONENTS
        + _BUILDERS
        + "\n</style>"
    )


def inject_css() -> None:
    """라이트 핀테크 디자인 토큰/컴포넌트 CSS를 페이지에 1회 주입한다.

    각 페이지(app.py, pages/*) 상단에서 호출한다.
    st.markdown(unsafe_allow_html=True)로 <style>을 그대로 삽입.
    """
    st.markdown(build_css(), unsafe_allow_html=True)
