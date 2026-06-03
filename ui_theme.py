"""ASI 다크 모던 디자인 시스템 — CSS 토큰/컴포넌트 + Streamlit 크롬 주입.

딥네이비 다크 배경 + 네온 블루 액센트 + 글래스 카드 톤(Linear/Vercel·증권앱 무드).
디자인 토큰(:root)·공통 컴포넌트 클래스·Streamlit 기본 위젯 스타일을 한 곳에 모아
각 페이지 상단에서 1회 주입한다.

- build_css(): 부작용 없는 순수 문자열 빌더(테스트 대상).
- inject_css(): st.markdown(unsafe_allow_html=True)로 실제 주입(페이지에서 호출).

한국 관습 유지: 주가 상승=빨강(--up #e74c3c) / 하락=파랑(--down #3498db).
"""
from __future__ import annotations

import streamlit as st

# Pretendard 웹폰트(CDN) — 한국어 톤. + JetBrains Mono(숫자 강조용, 선택).
_PRETENDARD_IMPORT = (
    "@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/"
    "dist/web/static/pretendard.css');"
)

# 다크 모던 디자인 토큰. (테스트는 일부 값을 고정 검증한다 — 변경 시 test_ui_theme 동기화)
_ROOT_TOKENS = """
:root{
  /* 배경/표면/라인 (딥네이비 다크) */
  --bg:#0a0e17;
  --bg-2:#0f1320;
  --surface:#141a27;
  --surface-2:#1a2230;
  --surface-3:#212a3a;
  --line:#27313f;
  --line-strong:#34404f;
  --line-hair:#1c2533;

  /* 글래스(반투명 표면) */
  --glass:rgba(255,255,255,.022);
  --glass-2:rgba(255,255,255,.05);
  --hairline:rgba(255,255,255,.06);

  /* 잉크(본문/보조/약한) — 다크 위 밝은 텍스트 */
  --ink:#eaeff7;
  --ink-2:#c4ccda;
  --ink-3:#94a0b3;
  --ink-4:#697587;

  /* 브랜드(네온 블루) */
  --accent:#5b8cff;
  --accent-strong:#7aa2ff;
  --accent-ink:#a9c6ff;
  --accent-weak:rgba(91,140,255,.14);
  --accent-weak-2:rgba(91,140,255,.32);

  /* 한국 관습 — 상승=빨강, 하락=파랑 (다크용 약간 밝게 보정) */
  --up:#e74c3c;
  --up-ink:#ff8079;
  --up-weak:rgba(231,76,60,.15);
  --down:#3498db;
  --down-ink:#5cb3ff;
  --down-weak:rgba(52,152,219,.15);

  /* 시맨틱 (다크 위 가독 밝기) */
  --good:#3fb950;
  --good-bright:#46d160;
  --good-chip:#3fb950;
  --good-weak:rgba(63,185,80,.15);
  --warn:#e3b341;
  --warn-bright:#f0c64e;
  --warn-weak:rgba(227,179,65,.15);
  --warn-line:rgba(227,179,65,.32);
  --violet:#b692f6;
  --violet-weak:rgba(163,113,247,.16);
  --gold-ink:#e3b341;
  --gold-weak:rgba(227,179,65,.14);

  /* 라운드 */
  --r-xl:20px;
  --r-card:16px;
  --r-md:12px;
  --r-sm:9px;
  --r-pill:999px;

  /* 그림자(다크용 깊은 드롭 + 내부 하이라이트) */
  --sh-soft:0 1px 2px rgba(0,0,0,.35), 0 2px 10px rgba(0,0,0,.35);
  --sh-card:0 2px 6px rgba(0,0,0,.4), 0 14px 34px rgba(0,0,0,.5);
  --sh-pop:0 6px 16px rgba(0,0,0,.5), 0 30px 70px rgba(0,0,0,.65);
  --glow:0 0 0 1px rgba(91,140,255,.30), 0 10px 30px rgba(91,140,255,.28);

  /* 여백(8px 베이스) */
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px;
  --s-5:20px; --s-6:24px; --s-7:32px; --s-8:40px; --s-9:48px;
}
"""

# 본문 폰트/타이포 + Streamlit 컨테이너 다크 배경.
_BASE = """
html, body, [class*="css"], .stApp, .stMarkdown, .stMarkdown p{
  font-family:'Pretendard',-apple-system,'Apple SD Gothic Neo',
    'Malgun Gothic',system-ui,sans-serif;
  letter-spacing:-.011em;
}
.stApp{
  color:var(--ink);
  background:
    radial-gradient(1100px 620px at 78% -8%, rgba(91,140,255,.10), transparent 60%),
    radial-gradient(900px 560px at 8% 4%, rgba(163,113,247,.07), transparent 55%),
    var(--bg);
  background-attachment:fixed;
}
.asi-num,.num{ font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1; }

/* 메인 컨테이너 폭/여백 */
.block-container{ padding-top:3.0rem; padding-bottom:4rem; max-width:1180px; }

/* 헤딩/본문 */
h1,h2,h3,h4{ color:var(--ink); letter-spacing:-.03em; font-weight:800; }
h1{ font-size:2.0rem; }
.stApp h1, .stApp h2, .stApp h3{ font-weight:850; }
.stMarkdown, .stMarkdown p, .stText{ color:var(--ink-2); }
[data-testid="stCaptionContainer"], .stCaption, small{ color:var(--ink-4) !important; }

/* 상단 헤더바/툴바 투명 */
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stToolbar"]{ right:8px; }

/* 구분선 */
hr, [data-testid="stDivider"]{ border-color:var(--line) !important; }
.stApp hr{ border:none; height:1px; background:linear-gradient(90deg,transparent,var(--line),transparent); }

/* ── 사이드바 ─────────────────────────────────────────── */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg, #0d1220, #0b0f1a);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] *{ color:var(--ink-2); }
[data-testid="stSidebar"] a{ color:var(--ink-2) !important; border-radius:var(--r-sm); }
[data-testid="stSidebarNav"] a:hover{ background:var(--glass-2); }
[data-testid="stSidebarNav"] a[aria-current="page"]{
  background:var(--accent-weak); color:var(--accent-ink) !important;
}

/* ── 버튼 ─────────────────────────────────────────────── */
.stButton>button, .stDownloadButton>button{
  background:var(--surface-2);
  color:var(--ink);
  border:1px solid var(--line-strong);
  border-radius:var(--r-pill);
  font-weight:700; letter-spacing:-.01em;
  padding:.5rem 1.1rem;
  transition:transform .12s ease, box-shadow .15s ease, border-color .15s, background .15s;
}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:var(--accent);
  color:#fff;
  transform:translateY(-1px);
  box-shadow:0 6px 18px rgba(0,0,0,.45);
}
.stButton>button:active{ transform:translateY(0); }
.stButton>button:focus{ box-shadow:none !important; }
/* 강조(primary) 버튼 — 그라데이션 + 글로우 */
.stButton>button[kind="primary"], .stButton>button[data-testid="baseButton-primary"]{
  background:linear-gradient(135deg, var(--accent), #6f63ff);
  border:none; color:#fff; box-shadow:var(--glow);
}
.stButton>button[kind="primary"]:hover{ filter:brightness(1.06); }

/* ── 라디오: 세그먼트형 칩 ─────────────────────────────── */
.stRadio > label, .stSelectbox > label, .stTextInput > label,
.stNumberInput > label, .stSlider > label, .stMultiSelect > label{
  color:var(--ink-3) !important; font-weight:700; font-size:.82rem;
}
.stRadio [role="radiogroup"]{ gap:8px; flex-wrap:wrap; }
.stRadio [role="radiogroup"] > label{
  background:var(--surface-2);
  border:1px solid var(--line);
  border-radius:var(--r-pill);
  padding:7px 15px; margin:0;
  cursor:pointer; transition:all .15s ease;
}
.stRadio [role="radiogroup"] > label:hover{ border-color:var(--accent); background:var(--surface-3); }
/* 실제 라디오 원 숨김 */
.stRadio [role="radiogroup"] > label > div:first-child{ display:none; }
.stRadio [role="radiogroup"] > label p{ color:var(--ink-2); font-weight:700; }
/* 선택 상태 */
.stRadio [role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(135deg, var(--accent), #6f63ff);
  border-color:transparent; box-shadow:var(--glow);
}
.stRadio [role="radiogroup"] > label:has(input:checked) p{ color:#fff; }

/* ── 입력/셀렉트/넘버 ─────────────────────────────────── */
.stTextInput input, .stNumberInput input, textarea{
  background:var(--surface-2) !important;
  color:var(--ink) !important;
  border:1px solid var(--line-strong) !important;
  border-radius:var(--r-md) !important;
}
.stTextInput input::placeholder{ color:var(--ink-4); }
.stTextInput input:focus, .stNumberInput input:focus{
  border-color:var(--accent) !important;
  box-shadow:0 0 0 3px var(--accent-weak) !important;
}
[data-baseweb="select"] > div{
  background:var(--surface-2) !important;
  border:1px solid var(--line-strong) !important;
  border-radius:var(--r-md) !important;
  color:var(--ink) !important;
}
[data-baseweb="select"] svg{ color:var(--ink-3); }
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"]{
  background:var(--surface-2) !important; border:1px solid var(--line-strong) !important;
}
[data-baseweb="menu"] li{ color:var(--ink-2) !important; }
[data-baseweb="menu"] li:hover{ background:var(--accent-weak) !important; }
/* 넘버 입력 스텝 버튼 */
.stNumberInput button{ background:var(--surface-3) !important; border-color:var(--line-strong) !important; color:var(--ink-2) !important; }

/* ── 익스팬더 ─────────────────────────────────────────── */
[data-testid="stExpander"]{
  background:var(--glass);
  border:1px solid var(--line) !important;
  border-radius:var(--r-card) !important;
  box-shadow:var(--sh-soft);
  overflow:hidden;
}
[data-testid="stExpander"] summary{ color:var(--ink-2); font-weight:700; }
[data-testid="stExpander"] summary:hover{ color:var(--accent-ink); }

/* ── 메트릭 ───────────────────────────────────────────── */
[data-testid="stMetric"]{
  background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);
  border-radius:var(--r-card);
  padding:14px 16px;
  box-shadow:var(--sh-soft);
}
[data-testid="stMetricLabel"]{ color:var(--ink-4) !important; font-weight:700; }
[data-testid="stMetricValue"]{ color:var(--ink) !important; font-weight:850; letter-spacing:-.03em; }

/* ── 표(st.table) ─────────────────────────────────────── */
[data-testid="stTable"], .stTable{ color:var(--ink-2); }
[data-testid="stTable"] table{
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r-card); overflow:hidden; border-collapse:separate; border-spacing:0;
}
[data-testid="stTable"] th{
  background:var(--surface-2) !important; color:var(--ink-3) !important;
  border-bottom:1px solid var(--line) !important; font-weight:700;
}
[data-testid="stTable"] td{
  background:transparent !important; color:var(--ink) !important;
  border-bottom:1px solid var(--line-hair) !important; font-variant-numeric:tabular-nums;
}
[data-testid="stTable"] tr:last-child td{ border-bottom:none !important; }

/* DataFrame(glide grid) 다크 톤 보정 */
[data-testid="stDataFrame"]{ border:1px solid var(--line); border-radius:var(--r-card); }

/* ── 알림(st.info/success/warning/error) ──────────────── */
[data-testid="stAlert"], .stAlert{
  background:var(--surface-2);
  border:1px solid var(--line-strong);
  border-left:4px solid var(--accent);
  border-radius:var(--r-md);
  color:var(--ink-2);
  box-shadow:var(--sh-soft);
}
[data-testid="stAlert"] p{ color:var(--ink-2); }
/* 종류별 좌측 바 색(베스트에포트: data-baseweb kind 미노출 → 일반 액센트 유지) */

/* ── 탭 ───────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{ border-bottom:1px solid var(--line); gap:4px; }
.stTabs [data-baseweb="tab"]{ color:var(--ink-3); }
.stTabs [aria-selected="true"]{ color:var(--accent-ink) !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--accent) !important; }

/* ── 스크롤바 ─────────────────────────────────────────── */
*::-webkit-scrollbar{ width:11px; height:11px; }
*::-webkit-scrollbar-track{ background:transparent; }
*::-webkit-scrollbar-thumb{ background:var(--surface-3); border-radius:99px; border:3px solid transparent; background-clip:padding-box; }
*::-webkit-scrollbar-thumb:hover{ background:var(--line-strong); background-clip:padding-box; }

/* 링크 */
a, .stMarkdown a{ color:var(--accent-ink); text-decoration:none; }
a:hover{ text-decoration:underline; }

/* 마크다운 표(GFM) 다크 */
.stMarkdown table{
  border-collapse:separate; border-spacing:0; width:100%;
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r-card); overflow:hidden;
}
.stMarkdown thead th{
  background:var(--surface-2); color:var(--ink-3); font-weight:700;
  border-bottom:1px solid var(--line) !important; text-align:left; padding:10px 14px;
}
.stMarkdown tbody td{
  color:var(--ink-2); border-bottom:1px solid var(--line-hair) !important; padding:10px 14px;
}
.stMarkdown tbody tr:last-child td{ border-bottom:none !important; }
.stMarkdown tbody tr:hover td{ background:var(--glass); }
.stMarkdown code{
  background:var(--surface-2); color:var(--accent-ink);
  border:1px solid var(--line); border-radius:6px; padding:1px 6px; font-size:.85em;
}
"""

# 공통 컴포넌트 클래스(예약 .asi-*) — 다크 글래스 톤.
_COMPONENTS = """
/* 카드 */
.asi-card{
  background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line); border-radius:var(--r-xl);
  box-shadow:var(--sh-card); padding:20px 20px 18px; margin-bottom:var(--s-4);
  backdrop-filter:blur(8px);
}
.asi-card .name{font-size:17.5px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.asi-card .price{font-size:18px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}

/* 뱃지 */
.asi-badge{
  font-size:11.5px;font-weight:800;padding:4px 10px;border-radius:var(--r-pill);
  display:inline-flex;align-items:center;gap:4px;letter-spacing:-.01em;line-height:1.5;
  border:1px solid transparent;margin-right:6px;
}
.asi-badge.value{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.asi-badge.quality{background:var(--good-weak);color:var(--good);border-color:rgba(63,185,80,.35);}
.asi-badge.income{background:var(--violet-weak);color:var(--violet);border-color:rgba(163,113,247,.35);}
.asi-badge.mkt-kospi{background:var(--down-weak);color:var(--down-ink);border-color:rgba(52,152,219,.32);}
.asi-badge.mkt-kosdaq{background:rgba(214,113,177,.16);color:#e08cc4;border-color:rgba(214,113,177,.34);}

.asi-why{
  font-size:13px;color:var(--ink-2);background:var(--surface-2);
  border:1px solid var(--line);border-radius:var(--r-md);
  padding:11px 13px;line-height:1.55;letter-spacing:-.012em;
}
.asi-why b{color:var(--ink);font-weight:800;}

.asi-bar{height:8px;border-radius:var(--r-pill);background:var(--surface-3);overflow:hidden;}
.asi-bar > i{display:block;height:100%;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--accent),#7aa2ff);box-shadow:0 0 12px rgba(91,140,255,.5);}
.asi-score.good{color:var(--good);}
.asi-score.warn{color:var(--warn);}
.asi-score.muted{color:var(--ink-4);}

.asi-summary{
  background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:20px 20px 18px;backdrop-filter:blur(8px);
}
.asi-summary .cat{font-size:12.5px;font-weight:700;color:var(--ink-3);}
.asi-summary .word{font-size:25px;font-weight:900;letter-spacing:-.04em;color:var(--ink);line-height:1.1;margin:10px 0;}
.asi-summary .verdict{font-size:11.5px;font-weight:800;padding:4px 11px;border-radius:var(--r-pill);border:1px solid transparent;}
.asi-summary .verdict.good{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.asi-summary .verdict.strong{background:var(--good-weak);color:var(--good);border-color:rgba(63,185,80,.35);}
.asi-summary .verdict.mid{background:var(--gold-weak);color:var(--gold-ink);border-color:var(--warn-line);}

.asi-risk{
  background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px;
}
.asi-risk .rk-name{font-size:14px;font-weight:800;color:var(--ink);}
.asi-risk .rk-state.ok{background:var(--good-weak);color:var(--good);}
.asi-risk .rk-state.mid{background:var(--warn-weak);color:var(--warn);}
.asi-risk .rk-state{font-size:11px;font-weight:800;padding:2px 9px;border-radius:var(--r-pill);}
.asi-risk .rk-note{background:var(--warn-weak);color:var(--warn);font-weight:600;
  font-size:12.5px;line-height:1.55;border-radius:var(--r-md);padding:12px 14px;margin-top:12px;}

.asi-table{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);overflow:hidden;
}
.asi-table .k{font-size:11.5px;color:var(--ink-4);font-weight:700;text-transform:uppercase;letter-spacing:.01em;}
.asi-table .v{font-size:19px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}

.asi-checklist{
  background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px;
}
.asi-checklist .axis{font-size:14px;font-weight:800;color:var(--ink);}
.asi-checklist .grade.good{color:var(--good);}
.asi-checklist .grade.mid{color:var(--gold-ink);}
.asi-checklist .grade.warn{color:var(--warn);}
.asi-checklist .locked{color:var(--ink-4);font-weight:700;}
.asi-checklist .fact{font-size:12.5px;color:var(--ink-3);line-height:1.55;}
"""

# ui_components.py 빌더가 '실제로' emit하는 클래스 — 다크 모던 톤.
_BUILDERS = """
.num{font-variant-numeric:tabular-nums;}
.preset-guide{font-size:14px;color:var(--ink-2);background:var(--accent-weak);
  border:1px solid var(--accent-weak-2);border-radius:var(--r-md);padding:10px 14px;margin:8px 0 4px;}
.score-legend{font-size:12.5px;color:var(--ink-3);margin:4px 0 12px;}
.score-legend .legend-good{color:var(--good);font-weight:700;}
.score-legend .legend-warn{color:var(--warn);font-weight:700;}
.score-legend .legend-muted{color:var(--ink-4);font-weight:700;}

/* ── 스크리너 카드 (글래스 + 호버 리프트) ── */
.scard{position:relative;background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:18px 20px 14px;margin-bottom:var(--s-3);
  backdrop-filter:blur(8px);transition:transform .15s ease, border-color .15s ease, box-shadow .15s ease;}
.scard::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;border-radius:var(--r-xl) var(--r-xl) 0 0;
  background:linear-gradient(90deg,transparent,var(--hairline),transparent);}
.scard:hover{transform:translateY(-2px);border-color:var(--line-strong);
  box-shadow:var(--sh-pop);}
.scard-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;}
.scard .stock-id{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.scard .stock-name{font-size:17px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.scard .price{font-size:17px;font-weight:800;letter-spacing:-.03em;color:var(--ink);}
.mkt{font-size:11px;font-weight:800;padding:2px 8px;border-radius:var(--r-pill);}
.mkt.kospi{background:var(--down-weak);color:var(--down-ink);border:1px solid rgba(52,152,219,.32);}
.mkt.kosdaq{background:rgba(214,113,177,.16);color:#e08cc4;border:1px solid rgba(214,113,177,.34);}
.badge-row{margin:10px 0 8px;display:flex;flex-wrap:wrap;gap:6px;}
.badge{font-size:11.5px;font-weight:800;padding:3px 10px;border-radius:var(--r-pill);
  display:inline-flex;align-items:center;gap:4px;border:1px solid transparent;}
.badge.b-value{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.badge.b-quality{background:var(--good-weak);color:var(--good);border-color:rgba(63,185,80,.35);}
.badge.b-div{background:var(--violet-weak);color:var(--violet);border-color:rgba(163,113,247,.35);}
.why{font-size:13px;color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);
  border-radius:var(--r-md);padding:10px 12px;line-height:1.5;margin-bottom:10px;}
.why .q{font-weight:800;color:var(--accent-ink);margin-right:6px;}
.score-row{display:flex;align-items:center;gap:16px;}
.score-block{text-align:center;min-width:84px;}
.score-num{font-size:30px;font-weight:900;letter-spacing:-.04em;line-height:1;}
.score-num .u{font-size:13px;font-weight:700;margin-left:2px;}
.score-num.tier-good{color:var(--good);text-shadow:0 0 18px rgba(63,185,80,.45);}
.score-num.tier-warn{color:var(--warn);text-shadow:0 0 18px rgba(227,179,65,.4);}
.score-num.tier-muted{color:var(--ink-3);}
.score-rank{font-size:11.5px;color:var(--ink-4);font-weight:700;margin-top:2px;}
.bar-wrap{flex:1;}
.bar-label{display:flex;justify-content:space-between;font-size:11.5px;color:var(--ink-3);margin-bottom:5px;}
.bar{height:8px;border-radius:var(--r-pill);background:var(--surface-3);overflow:hidden;}
.bar>i{display:block;height:100%;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--accent),#7aa2ff);box-shadow:0 0 12px rgba(91,140,255,.55);}
.price-wrap{text-align:right;}
.scard-chg{display:inline-block;font-size:12.5px;font-weight:800;margin-top:3px;padding:1px 8px;border-radius:var(--r-pill);}
.scard-chg.chg-up{background:var(--up-weak);color:var(--up-ink);}
.scard-chg.chg-down{background:var(--down-weak);color:var(--down-ink);}
.scard-chg.chg-flat{background:var(--surface-3);color:var(--ink-4);}
.scard-foot{margin-top:12px;border-top:1px solid var(--line-hair);padding-top:10px;}
.scard .detail-link{font-size:13px;font-weight:700;color:var(--accent-ink);}

/* ── 한눈에 요약 ── */
.sum3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
@media(max-width:760px){.sum3{grid-template-columns:1fr;}}
.sumcard{background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:16px 18px;backdrop-filter:blur(8px);}
.sumcard .head{display:flex;justify-content:space-between;align-items:center;}
.sumcard .cat{font-size:12.5px;font-weight:700;color:var(--ink-3);}
.sumcard .verdict{font-size:11.5px;font-weight:800;padding:3px 10px;border-radius:var(--r-pill);border:1px solid transparent;}
.verdict.v-good{background:var(--accent-weak);color:var(--accent-ink);border-color:var(--accent-weak-2);}
.verdict.v-strong{background:var(--good-weak);color:var(--good);border-color:rgba(63,185,80,.35);}
.verdict.v-mid{background:var(--gold-weak);color:var(--gold-ink);border-color:var(--warn-line);}
.sumcard .word{font-size:24px;font-weight:900;letter-spacing:-.04em;color:var(--ink);margin:10px 0 6px;line-height:1.1;}
.sumcard .intuition{font-size:12px;font-weight:700;color:var(--accent-ink);background:var(--accent-weak);
  display:inline-block;padding:3px 9px;border-radius:var(--r-pill);margin-bottom:8px;border:1px solid var(--accent-weak-2);}
.metric-line{display:flex;justify-content:space-between;font-size:12.5px;color:var(--ink-3);
  border-top:1px solid var(--line-hair);padding:5px 0;}
.metric-line .v{color:var(--ink);font-weight:700;}
.subscores{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-card);
  box-shadow:var(--sh-soft);padding:12px 16px;}

/* ── 리스크 카드 ── */
.risk-card{background:linear-gradient(180deg, var(--glass-2), var(--glass)), var(--surface);
  border:1px solid var(--line);border-radius:var(--r-xl);
  box-shadow:var(--sh-card);padding:14px 18px;}
.risk-item{padding:6px 0;}
.rk-head{display:flex;align-items:center;gap:8px;}
.rk-dot{width:9px;height:9px;border-radius:50%;display:inline-block;}
.rk-dot.ok{background:var(--good-bright);box-shadow:0 0 10px rgba(70,209,96,.7);}
.rk-dot.mid{background:var(--warn-bright);box-shadow:0 0 10px rgba(240,198,78,.6);}
.rk-name{font-size:13.5px;color:var(--ink-2);font-weight:600;flex:1;}
.rk-state{font-size:11px;font-weight:800;padding:2px 9px;border-radius:var(--r-pill);}
.rk-state.ok{background:var(--good-weak);color:var(--good);}
.rk-state.mid{background:var(--warn-weak);color:var(--warn);}
.risk-note{background:var(--warn-weak);color:var(--warn);font-size:12.5px;line-height:1.5;
  border-radius:var(--r-md);padding:10px 13px;margin-top:10px;display:flex;gap:8px;border:1px solid var(--warn-line);}

/* ── 판단 체크리스트 ── */
.checklist-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
@media(max-width:760px){.checklist-grid{grid-template-columns:1fr;}}
.axis-cell{border:1px solid var(--line);border-radius:var(--r-card);padding:12px 14px;background:var(--surface-2);}
.axis-cell.locked{background:var(--surface);border-style:dashed;border-color:var(--line);}
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

/* ── 52주 바 ── */
.week52{margin:6px 0;}
.week52.empty{font-size:13px;color:var(--ink-4);}
.week52-bar{position:relative;height:8px;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--down),var(--surface-3),var(--up));}
.week52-marker{position:absolute;top:-4px;width:4px;height:16px;border-radius:2px;background:var(--ink);
  transform:translateX(-50%);box-shadow:0 0 10px rgba(234,239,247,.6);}
.week52-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--ink-4);margin-top:8px;}
.week52-dd{font-size:12.5px;color:var(--ink-3);margin-top:4px;}
.week52-dd b{color:var(--down-ink);}

/* ── 기간 수익률 칩 (상승=빨강/하락=파랑) ── */
.returns{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;}
.ret-chip{display:inline-flex;flex-direction:column;align-items:center;border:1px solid var(--line);
  border-radius:var(--r-md);padding:6px 12px;background:var(--surface-2);min-width:64px;}
.ret-chip .ret-k{font-size:11px;color:var(--ink-4);}
.ret-chip .ret-v{font-size:14px;font-weight:800;}
.ret-up{background:var(--up-weak);border-color:rgba(231,76,60,.3);}
.ret-up .ret-v{color:var(--up-ink);}
.ret-down{background:var(--down-weak);border-color:rgba(52,152,219,.3);}
.ret-down .ret-v{color:var(--down-ink);}
.ret-flat .ret-v{color:var(--ink-4);}

/* ── 과열도 ── */
.overheat{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-card);
  box-shadow:var(--sh-soft);padding:12px 16px;}
.oh-head{display:flex;justify-content:space-between;align-items:center;gap:10px;}
.oh-title{font-size:13.5px;font-weight:700;color:var(--ink);}
.oh-note-inline{font-size:11px;color:var(--ink-4);margin-left:6px;font-weight:600;}
.oh-level{font-size:12.5px;font-weight:800;padding:3px 11px;border-radius:var(--r-pill);}
.oh-level.oh-low{background:var(--good-weak);color:var(--good);}
.oh-level.oh-mid{background:var(--accent-weak);color:var(--accent-ink);}
.oh-level.oh-high{background:var(--warn-weak);color:var(--warn);}
.oh-level.oh-hot{background:var(--up-weak);color:var(--up-ink);box-shadow:0 0 14px rgba(231,76,60,.35);}
.oh-disc{font-size:11.5px;color:var(--ink-4);margin-top:8px;}

/* ── 백분위 칩 ── */
.pctile-chips{display:flex;flex-wrap:wrap;gap:8px;}
.pctile-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:var(--r-pill);padding:4px 12px;background:var(--surface-2);font-size:12px;}
.pctile-chip .pc-k{color:var(--ink-3);font-weight:700;}
.pctile-chip .pc-v{color:var(--ink);font-weight:800;}
.pctile-chip .pc-hint{color:var(--good);font-weight:700;font-size:11px;}

/* ── 용어 툴팁 ── */
.glossary-term{font-weight:700;color:var(--ink-2);}
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
    """다크 모던 디자인 토큰/컴포넌트/Streamlit 크롬 CSS를 페이지에 1회 주입한다.

    각 페이지(app.py, pages/*) 상단에서 호출한다.
    st.markdown(unsafe_allow_html=True)로 <style>을 그대로 삽입.
    """
    st.markdown(build_css(), unsafe_allow_html=True)
