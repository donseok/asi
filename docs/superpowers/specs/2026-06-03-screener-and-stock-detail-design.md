# ASI Phase 0a 완성 — 스크리너 · 종목분석 페이지 설계

- 작성일: 2026-06-03
- 대상: ASI (Antigravity Stock Insight) · Streamlit · 한국 개인투자자(초보자)
- 목표: 홈(`app.py`)이 안내하지만 아직 없는 **스크리너 / 종목분석** 멀티페이지를 추가해 Phase 0a MVP를 end-to-end로 사용 가능하게 한다.
- 시각 언어: **① 라이트 핀테크(토스풍)** — 확정 시안 `.superpowers/brainstorm/108-1780460381/content/design-light.html`이 비주얼 source of truth.

---

## 1. 배경 & 현황

기존 코드(완성됨):
- `core/data/` — 유니버스(FDR→pykrx 폴백), 밸류에이션 스냅샷(PER/PBR/EPS/BPS/DIV/시총/ROE_approx), 일봉 OHLCV, Parquet 캐시, 영업일 헬퍼, 리스크 플래그
- `core/analytics/` — 기술지표(SMA/RSI/MACD), 결정론적 백분위 스코어링(value/quality/income/score)
- `ui_helpers.py` — 캐시 로더(`load_scored_snapshot`, `load_ohlcv_with_indicators`), `make_price_figure`, `fmt_won`, `asof_text`
- `app.py` — 홈(데이터 신선도 + 갱신)

빠진 것: `pages/`(스크리너·종목분석), 디자인 시스템 적용, 신규 순수 로직(프리셋/뱃지/설명)과 그 테스트.

---

## 2. 범위

**In scope**
- 스크리너 페이지: "목적 선택형" 필터 + **카드형** 결과
- 종목분석 페이지: 종목 선택 → 한눈에 요약 → 리스크 → 가격 차트(간단) → 상세 숫자
- 두 페이지 간 네비게이션(스크리너 카드 → 상세 핸드오프 **및** 상세에서 직접 종목 선택, 둘 다)
- 라이트 핀테크 디자인 시스템 적용(테마 + CSS 주입 + 커스텀 HTML 카드)
- 신규 순수 로직(프리셋 필터/정렬, 뱃지, "왜 추천?" 설명, 평가/신호 문구) + 단위 테스트
- **정보 풍부화 / 교육 레이어**(점진적 노출): 안전·정직 캡션 + 📖초보 이해 + 📊점수 분해 + 📈가격 맥락 + 🔬중급 심화(펼침) — §4.5 / §5.7
- (사용자 채택) **판단 체크리스트**(가치·기술·리스크·심리 4축 활성, 성장·수급 잠금) · **과열도 프록시**(적법·외부수집 0) · **손절/익절 이탈 감시**(가격만) — §5.8 ~ §5.10

**Out of scope (YAGNI / 후속)**
- CSV 내보내기, 표시 컬럼 커스터마이즈, 표형 결과, 워치리스트/즐겨찾기
- RSI·MACD 기본 노출(차트는 "간단(A)" 모드로 접어둠)
- 정확 ROE·재무제표(DART), 관리종목/투자경고 "지정" 상태(시장경보), AI 요약, 수급·심리·실시간 시세 → **후속 단계, §12 로드맵에서 검증·정리**

---

## 3. 사용자 흐름

```
홈(app.py) ──► [사이드바] 스크리너 ──► 목적 선택 ──► 카드 결과 ──"자세히 보기"──► 종목분석
                         [사이드바] 종목분석 ──► 검색/선택으로 직접 종목 지정 ──► 동일 상세
```

- 스크리너 카드의 "자세히 보기"는 `st.session_state["selected_ticker"] = ticker` 설정 후 `st.switch_page("pages/2_🔍_종목분석.py")`.
- 종목분석은 `st.session_state.get("selected_ticker")`를 종목 선택 박스의 기본값으로 사용. 핸드오프가 없으면(직접 진입) 검색/선택 박스로 지정.
- 홈은 현행 유지(데이터 신선도·갱신 버튼). 단, 새 디자인 CSS를 홈에도 1회 주입해 톤 일치.

---

## 4. 화면 1 — 스크리너

### 4.1 레이아웃(위→아래)
1. 헤더 카피: **"어떤 주식을 찾으세요?"** + 보조 문구("하나만 골라주세요. 복잡한 숫자는 알아서 맞춰드립니다.")
2. **목적 타일 4개**(단일 선택, 1개 선택 상태 유지)
3. 보조 컨트롤 한 줄: 시장 토글(전체/코스피/코스닥) · 보여줄 개수(20/30/50, 기본 30) · 종목명 검색 · "▸ 고급 설정"(접힘)
4. 결과 헤더: "✅ 조건에 맞는 N종목 — {정렬기준} 순"
5. **결과 카드 목록**(카드형)

### 4.2 목적 프리셋 정의 (핵심)

모든 프리셋에 **공통 적용**되는 필터:
- 시장 선택(전체/KOSPI/KOSDAQ)
- 유동성 하한: `시가총액 ≥ MIN_MARKET_CAP`(300억) **AND** `당일 거래대금 ≥ MIN_AVG_TRADING_VALUE`(1억) — 고급 설정에서 완화 가능
- 종목명 검색어 포함(있을 때)
- 해당 프리셋의 **정렬 키가 NaN인 행 제외**
- 정렬 후 상위 `SCREENER_DEFAULT_LIMIT`(30) 표시

프리셋별 추가 필터/정렬(정렬은 내림차순):

| 프리셋 | 추가 필터 | 정렬 키 | 근거 |
|---|---|---|---|
| 💎 저평가 우량주 | `PER>0 & PBR>0` | `(value_score + quality_score)/2` | 싸면서(낮은 PER/PBR) 돈 잘 버는(높은 ROE) 회사 |
| 💰 배당 잘 주는 주식 | `DIV>0` | `income_score` | 배당수익률 백분위 상위 |
| 🛡️ 안정적인 대형주 | `시가총액 ≥ 시총 80번째 백분위` | `시가총액` | 시총 상위(대형). ※ 변동성은 미반영 — §8 참조 |
| ⭐ 종합 추천 | (없음) | `score` | 가치+품질+배당 종합 |

> `value_score / quality_score / income_score / score`는 기존 `core/analytics/scoring.compute_scores`가 만드는 컬럼을 그대로 사용한다(백분위 순위 평균, 0~100).

> 처리 순서: **공통 필터(시장·유동성·검색) → 프리셋 추가 필터 → 정렬 → 상위 N**. "안정적인 대형주"의 시총 80번째 백분위는 **공통 필터 적용 후 집합** 기준으로 계산한다(자격 종목 중 시총 상위 ~20%).

### 4.3 결과 카드 구성

각 카드(좌→우):
- 좌: 종목명(굵게) + 시장 뱃지(코스피/코스닥) + 현재가, 아래에 **색 뱃지** + **"왜 추천?" 한 줄**
- 우: **종합점수**(큰 숫자) + "상위 X%" + 점수 막대 + "자세히 보기 →"

**뱃지 규칙**(프리셋과 무관, 행마다 계산. 임계 `BADGE_PERCENTILE=70`):
- `저평가` ← `value_score ≥ 70`
- `우량` ← `quality_score ≥ 70`
- `고배당` ← `income_score ≥ 70` (그리고 `DIV>0`)
- 0~3개 표시 가능. 없으면 뱃지 생략.

**점수 색**:
- `≥ 75` → green(`--good`)
- `50–74` → amber(`--warn`)
- `< 50` → muted(`--ink-4`)

**"상위 X%"**: `scoring.percentile_of(scored, ticker)` 사용.

**"왜 추천?" 문구**(결정론적, `labels.explain_row`): 아래 문구 중 sub-score가 높은 순으로 **상위 2개**를 `, `로 연결. 모두 60 미만이면 `"종합점수 기준 상위 후보"`.
- `value_score ≥ 60` & PER/PBR 유효 → `"PER {per:.1f}배·PBR {pbr:.2f}배로 저렴"`
- `quality_score ≥ 60` & ROE 유효 → `"ROE(근사) {roe:.0f}%로 수익성 양호"`
- `income_score ≥ 60` & `DIV>0` → `"배당수익률 {div:.1f}%로 배당 넉넉"`

### 4.4 고급 설정(접힘, `st.expander`)
유동성 하한(시총/거래대금) 직접 조정. 기본은 접혀 있어 초보자에겐 보이지 않음. (PER/PBR 직접 범위 같은 추가 항목은 후속.)

### 4.5 스크리너 정보 풍부화 (채택 — 점진적 노출)

| 요소 | 노출 | 위치 | 계산/데이터 |
|---|---|---|---|
| 점수 막대 색 범례 | 기본 | 카드 목록 상단 1회 | 정적("🟢상위 · 🟠중간 · ⚪하위 = 상대 순위") |
| 프리셋 가이드 카피 | 기본 | 목적 타일 | 정적(예: 고배당 = "꾸준한 현금흐름을 원하면") |
| "왜 추천?"에 근거 숫자 | 기본 | 카드 설명 줄 | `explain_row`가 PER/PBR/ROE/배당 수치 포함(§4.3) |
| "안정적 대형주 = 덩치만" 한계 캡션 | 기본 | 해당 프리셋 결과 헤더 | 정적 고지(§8 정직 원칙) |
| 적자 PER "−" 설명 | 펼침/툴팁 | 빈 PER 자리 | `PER` NaN/≤0 → "적자라 PER 계산 불가(오류 아님)" |

---

## 5. 화면 2 — 종목분석

### 5.1 종목 선택
- `st.selectbox`(종목명+티커, 스냅샷 기준) — 검색 가능. 기본값 = 핸드오프 ticker(있으면).
- 선택된 종목으로 아래 전부 렌더.

### 5.2 헤더
- 종목명 · 시장 뱃지 · 현재가 · 등락(▲빨강/▼파랑) + 우측 **종합점수 박스**("84 · 상위 5%").

### 5.3 📌 한눈에 요약 (3카드, `labels.verdict_*`)
| 카드 | 기준 | 표시 |
|---|---|---|
| 가치 (싼가?) | `value_score` ≥70 "저평가"·40~69 "보통"·<40 "비싼 편" | PER·PBR |
| 수익성 (잘 버나?) | `quality_score` ≥70 "우량"·40~69 "보통"·<40 "수익성 낮음" | ROE(근사) |
| 배당 (주주환원) | `income_score` ≥70 "고배당"·40~69 "보통"·DIV없음/0 "배당 적음" | 배당수익률 |

### 5.4 ⚠️ 리스크 체크
- `core/data/flags.compute_risk_flags(ohlcv)` 결과를 그대로 표시(거래정지/저유동성/고변동성/가격데이터없음).
- 플래그가 없으면 긍정 라인: "특이 위험 신호 없음(최근 정상 거래)".
- **항상** 미확인 고지 한 줄: "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정".

### 5.5 📈 가격 차트 — 간단(A) 모드
- 기본: **캔들 + 20일 이동평균 + 거래량**(2단). 한국 색(상승 빨강/하락 파랑) 유지.
- 차트 위 **"신호 한 줄"**(`labels.signal_text(latest_signals)`): 예) "20일선 위 · RSI 58(중립) · MACD 상승".
- **"▸ 기술적 지표 자세히(RSI·MACD)"** `st.expander` 안에서만 RSI·MACD 표시.
- 구현: 기존 `make_price_figure`(4단)를 SRP에 맞게 분리 권장 —
  - `make_overview_figure(df, title)` → 가격+20일선+거래량(기본)
  - `make_indicator_figure(df)` → RSI+MACD(expander)
  - (기존 `make_price_figure`는 제거 또는 `make_overview_figure`로 대체. 외부 사용처는 `ui_helpers` 내부뿐.)
- OHLCV가 비어 있으면(거래정지/상폐) 차트 생략 + 리스크 플래그로 안내.

### 5.6 🔢 상세 숫자 (표)
PER · PBR · ROE(근사) · EPS · BPS · 배당수익률 · 시가총액 · 주당배당금(DPS). `fmt_won` 등으로 포맷.

### 5.7 종목분석 정보 풍부화 (채택 — 점진적 노출)

원칙: **오해 방지 · 생존(리스크) · 핵심 요약 = 기본 노출(초보)** / **정량 심화 · 기술 지표 = "더 알아보기" 펼침(중급)**. 정보를 더 얹어도 기본 화면은 단순 유지.

**기본 노출 (초보)**

| 요소 | 위치 | 계산/데이터 |
|---|---|---|
| "상대 순위 · 매수 신호 아님" 캡션 | 종합점수 박스 아래 | 정적 |
| 직관 배지 — "시장 평균보다 싼 편" | 한눈에 요약-가치 | `labels.value_badge`(스냅샷 PER/PBR 분포 또는 value_score) |
| 배당 환산 "100만원당 연 ~N원" + 중앙값 대비 | 한눈에 요약-배당 | `labels.dividend_won`(DIV/DPS/종가) + 전체 DIV 분포 |
| 가치/수익성/배당 3점수 막대 | 한눈에 요약 하단 | 기존 value/quality/income_score |
| 52주 범위 바 + 현재가 위치 · 고점낙폭 | 가격 맥락 | `price_context.week52_position`(OHLCV ~252봉) |
| 기간 수익률 1·3개월 | 가격 맥락 | `price_context.period_returns` |
| 추세 한 줄(정배열/역배열/혼조) | 차트 위 신호 줄 | `price_context.ma_alignment`(SMA20/60/120) → `signal_text` 보강 |
| 변동성 등급(낮음/보통/높음) | 리스크(§5.4) | `price_context.volatility_grade`(daily_ret.std×100) |
| 리스크 쉬운말 번역 + 미확인 고지 | 리스크(§5.4) | `compute_risk_flags` 라벨 매핑 + 정적 고지 |
| 용어 ⓘ 툴팁 | 숫자 라벨 옆 | `labels.GLOSSARY`(정적), `st.popover`/`help`/`title` |

**"더 알아보기" 펼침 (중급, `st.expander` 기본 접힘 — §5.5의 RSI·MACD 차트도 이 영역으로 통합)**

| 요소 | 계산/데이터 |
|---|---|
| 지표별 시장 백분위 칩(PER/PBR/DIV/ROE/시총/거래대금) | `scoring.metric_percentile`(저PER=하위%가 저렴 → `lower_is_better` 처리) |
| 20·60일선 이격도 | `price_context.disparity`((close/sma−1)×100) |
| 최대낙폭 MDD(1년) | `price_context.max_drawdown` |
| RSI·MACD 말풀이 + 과매수/과매도 캡션 | `labels.indicator_plain(latest_signals)`(RSI≥70/≤30만 주의 캡션) |
| 거래량 배수(평소 20일 대비) | `price_context.volume_ratio` |
| 이익수익률(1/PER) | `labels.earnings_yield`(PER≤0이면 "적자") |
| 6·12개월 수익률 | `price_context.period_returns` |
| RSI·MACD 차트 | `make_indicator_figure`(§5.5) |

모든 항목은 현재 데이터(스냅샷·OHLCV·기존 파생)만으로 계산한다. 섹터 평균·재무제표·뉴스·수급·배당이력은 데이터가 없어 **§12 로드맵(후속)**으로 분리.

### 5.8 🧭 판단 체크리스트 (참고용 · 사용자 채택)

6축 그리드. **활성 4축**(가치·기술·리스크·심리) + **잠금 2축**(성장 🔒 = 2단계 DART, 수급 🔒 = 4단계 키움). 점진적 노출·정직 원칙.

| 축 | 등급 산출(사실 기반) |
|---|---|
| 가치 | `value_score`/`quality_score` 백분위(저PER·저PBR·ROE) |
| 기술 | 이동평균 정배열 여부 · RSI 구간 · MACD 시그널 — '사실'만 |
| 리스크 | `compute_risk_flags` 충족 목록 |
| 심리 | §5.9 과열도 프록시 등급(가격·거래량 기반, 게시판 아님) |
| 성장 🔒 | 잠금 — 2단계 DART(EPS·매출 추세) |
| 수급 🔒 | 잠금 — 4단계 키움(투자자별 순매수) |

각 축은 **양호/보통/주의** 서열 + 근거 사실. 🔴 **면책 핵심(§12.4)**: ① 6축을 합산한 '매수점수'를 만들지 않는다(=신호화 금지), 축별 분리 표시. ② 라벨 정합. ③ "추천/매수신호" 아닌 **"체크리스트/판단 보조"** + "단독 판단 근거 금지·투자권유 아님" 상시 고지. ④ 점수는 서열/백분위. 순수: `core/analytics/checklist.py`.

### 5.9 🌡️ 과열도 (가격·거래량 기반 보조지표 · 사용자 채택)

게시판 심리가 아니라 **가격·거래량 기반 과열도 프록시**(외부수집 0, 적법 — §12.2 A). 구성: RSI 과매수/과매도 + 거래대금 급증 배수(평균 대비) + 단기 급등락·이격도 + 변동성 확대 → 등급(낮음/보통/높음/과열).
- 표기: **"가격·거래량 기반 과열도(게시판 심리 아님)"** + 필수 고지 "보조지표 · 단독 판단 금지".
- 위치: 가격 맥락/리스크 인근 또는 체크리스트 심리축. 순수: `price_context.overheating(ohlcv)`.

### 5.10 🎯 손절/익절 이탈 감시 (가격만 · 사용자 채택)

사용자가 손절가·익절가(선택: 보유 평단)를 입력 → **최신 종가와 비교해 "익절가 도달 / 손절가 이탈 / 범위 내" 사실만 고지**. 주문·자동매매 없음(투자일임 아님).
- 표현: "지금 파세요"가 아니라 **"입력하신 손절가 ₩X 이탈"** 사실만.
- 입력은 세션 상태(Phase 0a 미영속). 순수: `price_context.monitor_targets(close, stop, target)`.

---

## 6. 디자인 시스템 (라이트 핀테크)

`design-light.html`이 source of truth. 핵심 토큰(요약):

- 배경 `--bg #f4f6fa`, 표면 `--surface #ffffff`
- 잉크: `--ink #161b22`(본문), `--ink-3 #5b6573`(보조), `--ink-4 #6b7480`(약한)
- 브랜드: `--accent #3182f6`, `--accent-ink #1759c2`(텍스트), `--accent-weak #e8f1ff`
- 한국 관습: 상승 `--up #e74c3c`/`--up-ink #c92a1e`, 하락 `--down #3498db`/`--down-ink #1f7fc9`
- 시맨틱: `--good #14682b`, `--good-chip #0c7a34`(흰글자 칩), `--warn #b45309`, `--violet #6541d6`
- 라운드: card 16 · md 12 · sm 9 · pill 999 · xl 20
- 그림자: `--sh-soft / --sh-card / --sh-pop`(앰비언트+키 2겹)
- 여백: 8px 베이스(4/8/12/16/20/24/32/40/48)
- 폰트: Pretendard(CDN) → fallback `-apple-system,'Apple SD Gothic Neo','Malgun Gothic',system-ui`

**Streamlit 재현 방식**
- `.streamlit/config.toml` `[theme]`: `primaryColor="#3182f6"`, `backgroundColor="#f4f6fa"`, `secondaryBackgroundColor="#ffffff"`, `textColor="#161b22"`, `font="sans serif"`(Pretendard는 CSS로 로드).
- 페이지 상단에서 **CSS 1회 주입**(`st.markdown(unsafe_allow_html=True)`): Pretendard `<link>` + `:root` 토큰 + 카드/뱃지/요약/리스크/표 클래스.
- 카드·뱃지·요약·리스크 박스는 `st.markdown`으로 동일 클래스 HTML 렌더, 그리드는 `st.columns`.
- 시안의 `sticky appbar + backdrop-filter blur`, `:hover transform` 등은 **장식 전용** → Streamlit에선 일반 컨테이너/정적 상태로 대체(룩 영향 미미, 디렉터 폴리시의 `streamlit_feasibility` 노트 반영).
- 라디오/토글의 **실제 동작은 Streamlit 위젯**(`st.radio`/`st.segmented_control`)으로, 타일 비주얼만 CSS로 입힌다.

---

## 7. 아키텍처 / 파일 구조

순수 로직(core)과 Streamlit UI 분리 원칙 유지.

```
.streamlit/config.toml          # 신규 — 테마
app.py                          # 수정 — 테마 CSS 주입 호출 추가
pages/
  1_📊_스크리너.py               # 신규
  2_🔍_종목분석.py               # 신규
core/analytics/
  screening.py                  # 신규(순수) — 프리셋 레지스트리 + apply_screen()
  labels.py                     # 신규(순수) — 뱃지/설명/평가/신호 + 풍부화 문구(용어/배지/말풀이)
  price_context.py              # 신규(순수) — 52주위치/기간수익률/이격도/MDD/거래량배수/변동성등급 + overheating(과열도)/monitor_targets(이탈감시)
  checklist.py                  # 신규(순수) — 판단 체크리스트 6축(가치/기술/리스크/심리 활성, 성장/수급 잠금). 합산 매수점수 없음.
  scoring.py                    # 수정 — percentile_of + metric_percentile(임의 컬럼 일반화)
  indicators.py                 # 기존 재사용(latest_signals 등)
ui_theme.py                     # 신규 — inject_css() (디자인 토큰 주입)
ui_components.py                # 신규 — render_stock_card / summary / risk 등 HTML 빌더
ui_helpers.py                   # 수정 — 로더 유지 + 차트 함수 분리(overview/indicator)
config.py                       # 수정 — 신규 상수
tests/
  test_screening.py             # 신규
  test_labels.py                # 신규 (뱃지/설명/평가/신호 + 풍부화 문구)
  test_price_context.py         # 신규 — 52주위치/기간수익률/MDD/거래량배수/변동성등급 + 과열도/이탈감시
  test_checklist.py             # 신규 — 6축 등급·활성/잠금, 합산점수 부재 단언
  test_indicators.py            # 신규(기존 로직 백필, 권장)
  test_scoring.py               # 신규(기존 로직 백필, 권장 + metric_percentile)
```

**신규 `config.py` 상수**
- `SCREENER_DEFAULT_LIMIT = 30`
- `BADGE_PERCENTILE = 70`
- `STABLE_CAP_PERCENTILE = 80` (안정적 대형주 시총 하한 백분위)
- `EXPLAIN_MIN_SUBSCORE = 60`
- `WEEK52_WINDOW = 252` · `PERIOD_RETURN_WINDOWS = {"1개월":21, "3개월":63, "6개월":126, "12개월":252}`
- `VOLATILITY_GRADE_BOUNDS = (1.5, 3.0)` (일간 변동성% → 낮음/보통/높음)
- `DIVIDEND_PRINCIPAL = 1_000_000` (배당 환산 기준금액)
- `OVERHEAT_VOLUME_SPIKE = 2.0` · `OVERHEAT_RSI = (30, 70)` (과열도 구성 임계)

**`core/analytics/screening.py` (순수)**
- `PRESETS`: `{key: {label, emoji, desc, extra_filter, sort_key}}` 레지스트리
- `apply_screen(scored_df, preset_key, *, market="전체", query="", limit=30, min_cap, min_value) -> DataFrame`
  - 공통 필터 + 프리셋 필터/정렬 + 상위 N. 부작용 없음. 입력 비파괴.

**`core/analytics/labels.py` (순수, 결정론적)**
- `badges(row) -> list[str]` ("저평가"/"우량"/"고배당")
- `explain_row(row) -> str` (§4.3 규칙, 근거 숫자 포함)
- `score_tier(score) -> "good"|"warn"|"muted"`
- `verdict_value/quality/income(row) -> (label, tone)`
- `signal_text(latest_signals, ma_alignment=None) -> str` (추세 한 줄 보강)
- 풍부화: `GLOSSARY: dict[str,str]`(용어 정의), `value_badge(row)`("시장 평균보다 싼 편" 등), `dividend_won(row, principal=DIVIDEND_PRINCIPAL)`, `indicator_plain(latest_signals)`(RSI/MACD 말풀이 + 과매수/과매도), `earnings_yield(row)`(1/PER), `CAPTIONS`(정적 고지/캡션 모음)

**`core/analytics/price_context.py` (순수, OHLCV 기반)**
- `week52_position(ohlcv) -> {low, high, pos_pct, drawdown_pct}`
- `period_returns(ohlcv, windows=PERIOD_RETURN_WINDOWS) -> dict[str, float]`
- `ma_alignment(ohlcv) -> "정배열"|"역배열"|"혼조"` (SMA20/60/120)
- `disparity(ohlcv, windows=(20, 60)) -> dict[int, float]`
- `max_drawdown(ohlcv, window=WEEK52_WINDOW) -> float`
- `volume_ratio(ohlcv, window=20) -> float`
- `volatility_grade(ohlcv, window=20) -> (등급, daily_pct)`
- `overheating(ohlcv) -> {level: "낮음"|"보통"|"높음"|"과열", components}` (RSI+거래대금배수+이격도+변동성, 가격기반 프록시)
- `monitor_targets(close, stop=None, target=None) -> {status: "익절도달"|"손절이탈"|"범위내", ...}`

**`core/analytics/checklist.py` (순수)**
- `build_checklist(row, ohlcv, flags, *, scored) -> list[Axis]` — 6축(가치/기술/리스크/심리 활성 + 성장/수급 잠금). 각 축 `{axis, active, grade("양호"|"보통"|"주의"), facts: list[str], locked_reason}`.
- **합산 '매수점수'를 만들지 않는다**(축별 분리 — §12.4 면책 4원칙).

**`core/analytics/scoring.py` (수정)**
- `metric_percentile(scored, ticker, column, lower_is_better=False) -> float|None` — `percentile_of`를 임의 컬럼으로 일반화(백분위 칩용; 저PER은 "하위 X%(저렴)"로 해석).

UI 레이어(`ui_components.py`)는 위 순수 함수의 산출물을 받아 HTML 문자열만 만든다(로직 없음). 용어 툴팁은 `st.popover`(우선) 또는 위젯 `help=` / HTML `title=`로 구현.

---

## 8. 데이터 / 정확성 주의 (정직 고지)

- **스크리너 거래대금 = 당일값**(전 종목 일괄 조회 가능한 스냅샷 컬럼). 코드 주석의 "20일 평균 거래대금"은 종목별 OHLCV가 필요하므로 **상세 페이지 리스크 플래그**에서만 계산한다. 스크리너 유동성 필터는 당일 거래대금 기준임을 UI/문서에 명시.
- **ROE는 근사치**(`EPS/BPS`, `ROE_approx`). 정확 ROE는 Phase 0b(DART).
- **"안정적인 대형주"는 시총(대형) 기준만** 반영. 일간/역사적 변동성은 bulk 스냅샷에 없어 미반영 → 카피에서 "덩치 큰 회사" 수준으로만 약속하고 과약속 금지.
- 모든 점수는 **횡단면 상대 지표**이지 매수 신호 아님(`config.DISCLAIMER` 유지·노출).

---

## 9. 에러 / 엣지 케이스

- 스냅샷 비었음/네트워크 실패 → 친절한 안내 + 홈 갱신 유도. 앱이 죽지 않게.
- 프리셋 결과 0건 → "조건에 맞는 종목이 없습니다 — 시장을 넓히거나 고급 설정을 완화해 보세요."
- 종목 OHLCV 없음(거래정지/상폐) → 차트 생략, 리스크에 "가격 데이터 없음" 표시(기존 플래그).
- 상세 직접 진입 + 미선택 → "왼쪽에서 종목을 선택하세요" 안내.
- `percentile_of`/sub-score가 `None`/`NaN` → 해당 표시 숨김(빈칸 "-"), 카드/요약은 깨지지 않게.

---

## 10. 테스트 (순수 core)

- `test_screening.py`: 각 프리셋의 필터 충족(PER>0 등)·정렬 단조성·유동성 하한 적용·NaN 정렬키 제외·상위 N 제한·빈 입력/0건.
- `test_labels.py`: 뱃지 임계 경계(69/70), `explain_row` 결정론·문구 포함·전부 저score 시 fallback, `score_tier` 경계(49/50/74/75), verdict 매핑, `signal_text`의 None/정상 처리; 풍부화 — `value_badge`/`dividend_won`/`indicator_plain`(RSI 70·30 경계)/`earnings_yield`(PER≤0="적자")/`GLOSSARY` 키 존재.
- `test_price_context.py`: `week52_position` 경계(현재가=고가 → pos 100·낙폭 0), `period_returns` 부호·길이·데이터 부족 처리, `max_drawdown ≤ 0`, `volume_ratio` 평균 대비, `volatility_grade` 경계(1.5/3.0), `ma_alignment` 정/역/혼조; `overheating` 등급 경계(RSI 70·거래대금 2배), `monitor_targets`(익절도달/손절이탈/범위내).
- `test_checklist.py`: 4 활성축 등급 산출, 성장·수급 잠금 표기, **합산 '매수점수' 필드 부재 단언**, 심리축 = 과열도 연동.
- `test_indicators.py` / `test_scoring.py`(권장 백필): RSI 순상승=100·순하락=0, SMA min_periods, `percentile_of`/`metric_percentile`(lower_is_better) 정확성, `compute_scores` 컬럼/NaN 처리.
- 네트워크 의존 함수(pykrx)는 테스트 대상 아님 — 순수 로직에 작은 합성 DataFrame을 주입해 검증.

---

## 11. 완료 기준 (Acceptance)

1. `streamlit run app.py` 후 사이드바에 **스크리너 · 종목분석** 두 페이지가 보인다.
2. 스크리너에서 목적 4개를 바꾸면 카드 결과(뱃지·설명·점수)가 그에 맞게 바뀐다.
3. 카드 "자세히 보기" → 종목분석으로 해당 종목이 열린다. 종목분석에서 직접 다른 종목도 선택 가능.
4. 종목분석에 요약 3카드·리스크·간단 차트(+신호 한 줄, RSI/MACD 접힘)·상세 표가 보인다.
5. 두 페이지 모두 라이트 핀테크 톤(토큰/카드/뱃지/색)이 적용된다.
6. 신규 순수 로직 단위 테스트가 통과한다(`pytest`).
7. §8의 정확성 한계가 UI/문서에 정직하게 표기된다.
8. 판단 체크리스트(6축, 4활성·2잠금)가 **합산 매수점수 없이** 축별로 분리 표시된다.
9. 과열도는 가격·거래량 기반 프록시로 표기되고(게시판 아님) "보조지표·단독 판단 금지" 고지가 동반된다.
10. 손절/익절가 입력 시 종가 대비 도달/이탈 "사실"만 고지된다(주문·자동매매 없음).

---

## 12. 로드맵 & 후속 데이터 소스 (공식 출처 검증 완료)

첨부 로드맵을 공식 출처로 검증함(DART 가이드·네이버 robots.txt 원문·키움 REST 가이드·자본시장법/판례). **Phase 0a(본 스펙)는 그대로 1단계.** 아래는 후속 단계의 정직한 실현가능성·적법성 판정과 ASI 아키텍처의 전방호환 설계.

| 단계 | 기능 | 실현 | 적법성 | 핵심 |
|---|---|---|---|---|
| **1 (현재)** | 스크리너·종목분석 pages + 풍부화 | 가능 | 적법 | 본 스펙 |
| **2** | DART 재무(정확 ROE·부채비율 등) + 시장경보/관리종목 리스크 | 가능 | 적법 | 무료키·분기 배치 |
| **3** | 적법 "과열도/심리" 보조지표 | 가능 | 적법 | 외부수집 0(가격·거래량) / 사용자 붙여넣기 로컬분석 |
| **4** | 키움 REST(개인 연동·조회 전용) | 조건부 | 주의 | 본인 키·세션한정·주문 보류 |
| (누적) | 판단 체크리스트(6축) + 손절/익절 이탈 감시 | 조건부 | 해당없음 | 합산 "매수점수" 금지·축 분리 |

### 12.1 DART 재무제표 (2단계) — ✅ 가능 · 적법
- `2019016`(단일회사 주요계정): **정확 ROE = 당기순이익/자본총계**, 영업이익률, 부채비율, 전기대비 성장률 도출 가능 → 현재 `ROE_approx`(EPS/BPS 근사) 대체.
- 현금흐름은 `2019020`(전체 재무제표) 추가 필요(동일 무료키).
- 무료 인증키(40자, `.env`의 `DART_API_KEY` 자리 보유), 2015~, `fs_div` 연결/별도, `reprt_code` 분기/반기/사업.
- 주의: **금융업(은행·보험·증권) 제외** → 해당 종목은 `ROE_approx` 폴백 + "미제공" 명시. `corp_code`(8자) 매핑 1회 구축, `account_id` 우선 매칭, 일 ~2만건 한도 → 분기 발표 시즌(3·5·8·11월) 배치+캐시, **후행지표** 면책.
- 아키텍처: `core/data/dart.py` + 캐시. 중급 펼침에 "실제 ROE·부채비율" 추가, 체크리스트 "성장축" 활성화.

### 12.2 "심리/과열도" — ⚠️ 네이버 크롤링 불가, 적법 대안만 채택
- **정직 고지: 네이버 종목토론 자동 수집은 채택하지 않는다.** `finance.naver.com/robots.txt` 원문이 `Allow: /item/board.naver?code=*`(첫 화면만) **+ `Disallow: /item/board.naver?code=*&page=*`(페이지네이션 금지)**. 심리지표는 다수 글(여러 페이지) 수집이 전제 → **robots.txt 위반**. 추가로 이용약관·저작권법상 DB제작자 권리·부정경쟁방지법 리스크(판례: 잡코리아 v 사람인 DB권 침해 인정). 헤더 위장·페이지네이션 우회 등 비준수 기법은 설계에서 **배제**.
- **적법 대안(채택):**
  - (A) **과열도 프록시(외부수집 0)** — RSI 과매수/과매도 + 거래대금 급증(평균 대비 배수) + 단기 급등락·이격도 + 변동성 확대를 결합한 상대지표. **지금 데이터(OHLCV/거래대금)로 구현 가능** → §12.6 후보.
  - (B) **사용자 붙여넣기 텍스트 로컬 감성분석(선택)** — 사용자가 직접 복사한 글만 로컬 분석(수집·저장·재배포 없음).
- 필수 고지: "게시판 심리·과열도는 단독 판단 근거가 될 수 없는 보조지표 …".

### 12.3 키움 REST API (4단계) — 🟡 조건부 · 개인 연동 한정
- REST는 OCX 미설치·크로스플랫폼·파이썬 가능 → ASI 적합(기존 OpenAPI+는 Windows OCX 종속, 부적합).
- 그러나 **사용자별 앱키/계좌가 필요** → 무료 다중사용자 앱이 "모두의 시세"를 키움으로 당기는 구조는 비현실적. 공통 데이터는 **pykrx 유지**(외부키 불필요 철학 보존), 키움은 **"본인 키 입력 시 켜지는 개인 보조 패널"**(세션 한정·서버 미저장).
- 조회 우선: 순위(거래대금/체결강도 근사)·투자자별 수급(`ka10061`)·현재가/호가 단발·본인 잔고. 실시간 WebSocket은 Streamlit과 충돌 → 백그라운드 워커 필요(고급).
- 규제: **자본시장법 §17/§101** — 불특정다수에 매수/매도 "신호·추천" 제공은 유사투자자문 소지 → **신호 생성 금지, 조회·판단보조만**. 조건검색도 ASI가 신호화하지 말고 "본인 결과 표시"만.
- **주문은 보류.** 도입해도 모의투자(`mockapi.kiwoom.com`) 우선, 실거래는 최후·명시 옵트인·강한 면책. **자동매매 금지**(통신·시스템 오류 손실 전가 위험).

### 12.4 판단 체크리스트 / 시나리오 (2~4단계 누적) — ✅ 설계 채택, 면책이 핵심
- 6축: 가치·성장·수급·기술·심리·리스크.
  - **Phase 0a 가동 축**: 가치(value/quality 백분위), 기술(정배열/RSI/MACD "사실"만), 리스크(`compute_risk_flags`), **심리(§5.9 과열도 프록시 — 0a 채택)**.
  - 성장 = 0b DART · 수급 = 키움(4단계). **미가동 축(성장·수급)은 🔒 잠금 표기**(점진적 노출·정직).
- **손절/익절 이탈 감시(가격만, 지금 가능)**: 사용자가 손절가/익절가 입력 → 최신 종가와 비교해 "도달/이탈 사실"만 고지(주문·자동매매 없음) → §12.6 후보.
- **🔴 면책 핵심 제약(반드시 준수):**
  1. 6축을 하나의 합산 "매수점수"로 만들지 않는다(=신호화 금지). 축별 **분리 표시**.
  2. 라벨 정합 — 가격 모멘텀을 "성장"으로, 거래대금을 "수급"으로 라벨 금지.
  3. "추천/매수신호"가 아닌 **"체크리스트/판단 보조"** 표현 + "단독 판단 근거 금지·투자권유 아님" 상시 고지.
  4. 점수는 서열(양호/보통/주의)·백분위로(정밀 착시 회피).

### 12.5 아키텍처 전방호환 (지금 설계에 심는 씨앗)
- 데이터 소스는 `core/data/*` 모듈 + 캐시로 추상화되어 있어 DART/키움을 **같은 패턴으로 추가** 가능(스냅샷/상세에 컬럼 합류). 본 Phase의 순수 로직 분리(`labels`/`price_context`/`screening`)는 풍부한 데이터가 들어와도 그대로 확장.
- 종목분석 "더 알아보기(중급)" 영역과 체크리스트 6축(잠금 포함)은 후속 데이터가 채워지는 **"슬롯"** 역할.
- `.env` 자리(`DART`/`ANTHROPIC`/`KIWOOM`)는 단계별 키 주입점.

### 12.6 Phase 0a에 추가 검토할 "지금 가능" 후보 (사용자 결정)
검증 결과 다음은 **새 데이터 없이 지금도 가능**. 본 Phase에 포함할지 결정 요청:
- (a) **손절/익절 목표 입력 → 이탈 감시**(가격만). 작고 유용, 자동매매 아님.
- (b) **과열도 프록시**(RSI+거래대금 배수+이격도+변동성) 보조지표 — §12.2(A).
- (c) **가치·기술·리스크 3축 "판단 체크리스트" 카드**(종목분석 요약을 체크리스트로 재구성) — §12.4.

→ **결정: (a)(b)(c) 모두 Phase 0a에 포함**(§5.8 ~ §5.10). 심리축은 (b) 과열도 프록시로 연동(게시판 수집 없음).
