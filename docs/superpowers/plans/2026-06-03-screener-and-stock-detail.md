# 스크리너 · 종목분석 (Phase 0a) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ASI Phase 0a를 완성한다 — 스크리너·종목분석 두 페이지와 그 순수 로직·라이트 핀테크 디자인을 구현해 MVP를 end-to-end로 사용 가능하게 한다.

**Architecture:** 순수 로직(`core/analytics`: screening/labels/price_context/checklist + scoring 확장)과 Streamlit UI(`ui_theme`/`ui_components`/`ui_helpers` + `pages/`)를 분리한다. 데이터는 기존 pykrx 전종목 스냅샷·일봉 OHLCV + Parquet 캐시를 재사용한다. 정보는 점진적 노출(초보 기본 / 중급 "더 알아보기" 펼침)이며, 모든 정량 항목은 결정론적 순수 함수로 계산한다.

**Tech Stack:** Python 3, Streamlit, pandas/numpy, Plotly, pykrx/FinanceDataReader, pytest, Pretendard(CDN).

**Spec(단일 진실원천):** `docs/superpowers/specs/2026-06-03-screener-and-stock-detail-design.md`

---

## 파일 구조 (책임 분리)

| 파일 | 책임 | 상태 |
|---|---|---|
| `config.py` | 신규 상수(임계·윈도우) | 수정 |
| `core/analytics/scoring.py` | `metric_percentile`(임의 컬럼 백분위, 백분위 칩용) | 수정 |
| `core/analytics/price_context.py` | OHLCV 파생: 52주위치·기간수익률·이격도·MDD·거래량배수·변동성등급·과열도·이탈감시 | 신규(순수) |
| `core/analytics/labels.py` | 뱃지·설명·평가·신호·용어(GLOSSARY)·직관배지·말풀이·정적 캡션 | 신규(순수) |
| `core/analytics/screening.py` | 프리셋 레지스트리 + `apply_screen` | 신규(순수) |
| `core/analytics/checklist.py` | 판단 체크리스트 6축(합산 매수점수 없음) | 신규(순수) |
| `.streamlit/config.toml` | 라이트 핀테크 테마 | 신규 |
| `ui_theme.py` | 디자인 토큰 CSS 1회 주입 | 신규 |
| `ui_components.py` | 카드/요약/리스크/체크리스트 HTML 빌더(순수) | 신규 |
| `ui_helpers.py` | 차트 분리(overview/indicator) + 기존 로더 유지 | 수정 |
| `pages/1_📊_스크리너.py` | 스크리너 페이지(조립) | 신규 |
| `pages/2_🔍_종목분석.py` | 종목분석 페이지(조립) | 신규 |
| `app.py` | 테마 주입 호출 추가 | 수정 |
| `tests/test_*.py` | 순수 로직 단위 테스트 | 신규 |

순수 로직(Task 2~6, 9)은 **TDD**(실패 테스트 → 구현 → 통과 → 커밋). UI 조립(Task 7·8·10·11)은 테스트된 함수/컴포넌트를 호출해 구성하고 `streamlit run`으로 **수동 검증**한다.

> **실행 전제:** 구현은 새 feature 브랜치에서 진행한다 — `git checkout -b feature/phase0a-pages`. 테스트는 프로젝트 루트에서 `python -m pytest`로 실행한다(루트가 `sys.path`에 오름).

---

## 태스크


### Task 1: config 신규 상수

스펙 §7의 "신규 `config.py` 상수" 9개(`SCREENER_DEFAULT_LIMIT`, `BADGE_PERCENTILE`, `STABLE_CAP_PERCENTILE`, `EXPLAIN_MIN_SUBSCORE`, `WEEK52_WINDOW`, `PERIOD_RETURN_WINDOWS`, `VOLATILITY_GRADE_BOUNDS`, `DIVIDEND_PRINCIPAL`, `OVERHEAT_VOLUME_SPIKE`, `OVERHEAT_RSI`)를 기존 `config.py` 끝에 추가한다. 상수만 추가하므로 TDD 사이클 대신 import·값·타입을 확인하는 스모크 테스트 1개로 회귀를 막는다.

- [ ] 기존 `config.py` 끝(파일 마지막 줄 `DISCLAIMER` 정의 다음)에 스펙 §7의 신규 상수 블록을 추가한다. 아래 코드 블록을 `config.py` 맨 끝에 그대로 덧붙인다(기존 내용은 수정하지 않음).

```python


# --- 스크리너 / 종목분석 신규 상수 (Phase 0a 완성) ---

# 스크리너 결과 기본 표시 개수(정렬 후 상위 N).
SCREENER_DEFAULT_LIMIT = 30

# 색 뱃지(저평가/우량/고배당) 부여 백분위 임계. sub-score가 이 값 이상이면 뱃지 표시.
BADGE_PERCENTILE = 70

# "안정적인 대형주" 프리셋의 시가총액 하한 백분위(공통 필터 적용 후 집합 기준 상위 ~20%).
STABLE_CAP_PERCENTILE = 80

# "왜 추천?" 설명 문구에 근거를 노출할 sub-score 최소값. 미만이면 해당 근거 생략.
EXPLAIN_MIN_SUBSCORE = 60

# 52주 범위 계산에 사용할 거래일 수(약 1년).
WEEK52_WINDOW = 252

# 기간 수익률 계산 윈도우(거래일 수). 라벨: 거래일.
PERIOD_RETURN_WINDOWS = {"1개월": 21, "3개월": 63, "6개월": 126, "12개월": 252}

# 일간 변동성(%) 등급 경계. (하한, 상한) 미만=낮음 / 사이=보통 / 초과=높음.
VOLATILITY_GRADE_BOUNDS = (1.5, 3.0)

# 배당 환산 기준금액(원). "100만원당 연 ~N원" 표시에 사용.
DIVIDEND_PRINCIPAL = 1_000_000

# 과열도 프록시: 거래대금 급증으로 판단하는 평균 대비 배수.
OVERHEAT_VOLUME_SPIKE = 2.0

# 과열도 프록시: RSI 과매도/과매수 경계. (하한, 상한).
OVERHEAT_RSI = (30, 70)
```

- [ ] 스모크 테스트 파일 `tests/test_config.py`를 새로 작성한다. 신규 상수 9개의 import 가능 여부·값·타입을 확인한다. 아래 코드 블록 전체로 파일을 생성한다.

```python
"""config.py 신규 상수 스모크 테스트.

상수만 추가하므로 import·값·타입 회귀만 막는다(순수 검증, 네트워크 없음).
"""
from __future__ import annotations

import config


def test_screener_default_limit():
    assert config.SCREENER_DEFAULT_LIMIT == 30
    assert isinstance(config.SCREENER_DEFAULT_LIMIT, int)


def test_badge_percentile():
    assert config.BADGE_PERCENTILE == 70
    assert isinstance(config.BADGE_PERCENTILE, int)


def test_stable_cap_percentile():
    assert config.STABLE_CAP_PERCENTILE == 80
    assert isinstance(config.STABLE_CAP_PERCENTILE, int)


def test_explain_min_subscore():
    assert config.EXPLAIN_MIN_SUBSCORE == 60
    assert isinstance(config.EXPLAIN_MIN_SUBSCORE, int)


def test_week52_window():
    assert config.WEEK52_WINDOW == 252
    assert isinstance(config.WEEK52_WINDOW, int)


def test_period_return_windows():
    assert config.PERIOD_RETURN_WINDOWS == {
        "1개월": 21,
        "3개월": 63,
        "6개월": 126,
        "12개월": 252,
    }
    assert isinstance(config.PERIOD_RETURN_WINDOWS, dict)
    # 모든 값은 양의 정수(거래일 수).
    assert all(isinstance(v, int) and v > 0 for v in config.PERIOD_RETURN_WINDOWS.values())


def test_volatility_grade_bounds():
    assert config.VOLATILITY_GRADE_BOUNDS == (1.5, 3.0)
    assert isinstance(config.VOLATILITY_GRADE_BOUNDS, tuple)
    assert len(config.VOLATILITY_GRADE_BOUNDS) == 2
    # 하한 < 상한.
    assert config.VOLATILITY_GRADE_BOUNDS[0] < config.VOLATILITY_GRADE_BOUNDS[1]


def test_dividend_principal():
    assert config.DIVIDEND_PRINCIPAL == 1_000_000
    assert isinstance(config.DIVIDEND_PRINCIPAL, int)


def test_overheat_volume_spike():
    assert config.OVERHEAT_VOLUME_SPIKE == 2.0
    assert isinstance(config.OVERHEAT_VOLUME_SPIKE, float)


def test_overheat_rsi():
    assert config.OVERHEAT_RSI == (30, 70)
    assert isinstance(config.OVERHEAT_RSI, tuple)
    assert len(config.OVERHEAT_RSI) == 2
    # 과매도 하한 < 과매수 상한.
    assert config.OVERHEAT_RSI[0] < config.OVERHEAT_RSI[1]
```

- [ ] 프로젝트 루트에서 스모크 테스트를 실행해 통과를 확인한다.
  - Run: `python -m pytest tests/test_config.py -v`
  - Expected: PASS (10개 테스트 모두 통과 — 신규 상수가 정확한 값/타입으로 추가됨)

- [ ] 소스와 테스트를 함께 커밋한다.
  - `git add config.py tests/test_config.py`
  - `git commit -m "feat: 스크리너·종목분석 신규 config 상수 9개 추가 + 스모크 테스트"`


### Task 2: scoring.metric_percentile (수정)

`core/analytics/scoring.py`에 `percentile_of` 패턴을 일반화한 `metric_percentile(scored, ticker, column, lower_is_better=False) -> float|None`을 추가한다. 백분위 칩(§5.7)용으로, `lower_is_better=True`이면 저값이 "하위 X%(저렴)"가 되도록 `100 - 백분위`로 해석한다. NaN/없는 티커/없는 컬럼은 `None`을 반환한다. 기존 `core/analytics/scoring.py`의 스타일(한국어 주석, `from __future__ import annotations`, `ticker.zfill(6)`)을 그대로 따른다.

- [ ] 1. `tests/test_scoring.py`에 `metric_percentile`의 실패하는 테스트를 추가한다. 파일이 없으면 새로 만들고, 있으면 함수를 추가한다(아래는 파일 전체 — 기존 `percentile_of` 백필 테스트 + 신규 `metric_percentile` 테스트를 함께 둔다).

```python
"""scoring 순수 로직 단위 테스트 (합성 DataFrame 주입, 네트워크 없음)."""
from __future__ import annotations

import pandas as pd

from core.analytics.scoring import metric_percentile, percentile_of


def _sample_scored() -> pd.DataFrame:
    """6종목 합성 스냅샷. ticker는 6자리 문자열, 컬럼은 실제 스냅샷 형태."""
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004", "000005", "000006"],
            "score": [10.0, 30.0, 50.0, 70.0, 90.0, float("nan")],
            "PER": [5.0, 8.0, 12.0, 20.0, 40.0, float("nan")],
            "DIV": [6.0, 4.0, 3.0, 2.0, 1.0, 0.0],
        }
    )


def test_percentile_of_basic():
    """percentile_of: 값 이하 비율 × 100 (백필)."""
    df = _sample_scored()
    # score=50.0 인 000003: 50 이하인 값(10,30,50)=3개 / 유효 5개 → 60%
    assert percentile_of(df, "000003", "score") == 60.0


def test_metric_percentile_higher_is_better():
    """lower_is_better=False: 큰 값일수록 높은 백분위."""
    df = _sample_scored()
    # DIV=6.0 인 000001: 6 이하인 값(전부 6개) → 100%
    assert metric_percentile(df, "000001", "DIV") == 100.0
    # DIV=3.0 인 000003: 3 이하(0,1,2,3)=4개 / 6개 → 66.67%
    assert metric_percentile(df, "000003", "DIV") == round(4 / 6 * 100, 10) or \
        abs(metric_percentile(df, "000003", "DIV") - (4 / 6 * 100)) < 1e-9


def test_metric_percentile_lower_is_better():
    """lower_is_better=True: 저PER이 '하위 X%(저렴)'로 100-백분위가 되어 높게 나온다."""
    df = _sample_scored()
    # PER 유효값: [5,8,12,20,40]. PER=5.0(000001)은 최저 → 가장 저렴 → 100에 가까움.
    p_low = metric_percentile(df, "000001", "PER", lower_is_better=True)
    p_high = metric_percentile(df, "000005", "PER", lower_is_better=True)
    # 저PER이 고PER보다 더 높은(저렴) 백분위
    assert p_low > p_high
    # PER=5는 최저값 → 100 - (5 이하 비율=1/5×100=20) = 80
    assert p_low == 80.0
    # PER=40은 최고값 → 100 - (40 이하 비율=5/5×100=100) = 0
    assert p_high == 0.0


def test_metric_percentile_lower_is_better_ignores_nonpositive():
    """lower_is_better=True는 0 이하(적자/무효) PER을 분포에서 제외한다."""
    df = _sample_scored()
    df.loc[df["ticker"] == "000006", "PER"] = -3.0  # 적자
    # 적자 종목 자신은 None (분포에서 제외 → 값 없음)
    assert metric_percentile(df, "000006", "PER", lower_is_better=True) is None
    # 정상 종목 PER=5: 유효분포 여전히 [5,8,12,20,40] → 80.0 유지
    assert metric_percentile(df, "000001", "PER", lower_is_better=True) == 80.0


def test_metric_percentile_none_cases():
    """NaN 값 / 없는 티커 / 없는 컬럼 / ticker 컬럼 부재 → None."""
    df = _sample_scored()
    # NaN score (000006)
    assert metric_percentile(df, "000006", "score") is None
    # 없는 티커
    assert metric_percentile(df, "999999", "score") is None
    # 없는 컬럼
    assert metric_percentile(df, "000001", "NOPE") is None
    # ticker 컬럼 자체가 없음
    no_ticker = df.drop(columns=["ticker"])
    assert metric_percentile(no_ticker, "000001", "score") is None


def test_metric_percentile_ticker_zfill():
    """티커는 zfill(6)로 정규화되어 정수형 입력도 매칭된다."""
    df = _sample_scored()
    # "1" → "000001"
    assert metric_percentile(df, "1", "DIV") == 100.0
```

- [ ] 2. 실패를 확인한다.
  Run: `python -m pytest tests/test_scoring.py -v`
  Expected: FAIL (`ImportError: cannot import name 'metric_percentile' from 'core.analytics.scoring'` — 함수 미구현)

- [ ] 3. `core/analytics/scoring.py` 파일 끝(`percentile_of` 함수 뒤)에 `metric_percentile`를 최소 구현으로 추가한다.

```python
def metric_percentile(
    scored: pd.DataFrame,
    ticker: str,
    column: str,
    lower_is_better: bool = False,
) -> float | None:
    """특정 종목의 임의 지표가 전체 분포에서 차지하는 백분위(0~100).

    백분위 칩(중급 펼침)용으로 `percentile_of`를 임의 컬럼으로 일반화한다.
    - lower_is_better=False: 값이 클수록 높은 백분위(예: DIV/ROE/시총).
    - lower_is_better=True : 값이 작을수록 '저렴(하위 %)' 해석 → 100 - 백분위로 뒤집는다.
      이때 0 이하(적자/무효)는 분포·대상값 모두에서 제외한다(PER/PBR 관습).
    NaN 값 / 없는 티커 / 없는 컬럼 / ticker 컬럼 부재 → None.
    """
    ticker = str(ticker).zfill(6)
    if column not in scored.columns or "ticker" not in scored.columns:
        return None

    series = scored[column]
    if lower_is_better:
        # 0 이하(적자/무효)는 유효 분포에서 제외
        series = series.where(series > 0)
    series = series.dropna()
    if series.empty:
        return None

    row = scored.loc[scored["ticker"] == ticker, column]
    if row.empty or pd.isna(row.iloc[0]):
        return None
    val = row.iloc[0]
    if lower_is_better and not (val > 0):
        # 대상 종목 자신이 적자/무효면 백분위 산출 불가
        return None

    pct = float((series <= val).mean() * 100)
    return 100.0 - pct if lower_is_better else pct
```

- [ ] 4. 통과를 확인한다.
  Run: `python -m pytest tests/test_scoring.py -v`
  Expected: PASS (모든 테스트 통과 — higher/lower is better, 적자 제외, None 케이스, zfill)

- [ ] 5. 커밋한다.
  `git add core/analytics/scoring.py tests/test_scoring.py`
  `git commit -m "feat: scoring.metric_percentile 추가 (임의 지표 백분위, lower_is_better 처리) + 테스트"`


### Task 3: price_context.py (신규)

가격 맥락 순수 함수 9개를 `core/analytics/price_context.py`에 구현한다. 모든 함수는 OHLCV(`open/high/low/close/volume/value`, index=date) 합성 DataFrame을 주입해 TDD로 검증한다. 지표 계산은 `core.analytics.indicators`(sma/rsi)와 직접 pandas를 사용한다. 임계값/윈도우는 `config`의 상수(`WEEK52_WINDOW`, `PERIOD_RETURN_WINDOWS`, `VOLATILITY_GRADE_BOUNDS`, `OVERHEAT_VOLUME_SPIKE`, `OVERHEAT_RSI`)를 그대로 사용한다.

전제: 본 태스크는 `config.py`에 §7의 신규 상수가 이미 존재한다고 가정한다(다른 태스크에서 추가). 만약 아래 상수가 없다면 첫 스텝에서 추가한다.

- [ ] **Step 1**: `config.py`에 price_context가 쓰는 상수가 있는지 확인하고 없으면 추가. `Read config.py`로 확인 후, 아래 블록이 없으면 `# --- 기술적 지표 파라미터 ---` 위 또는 `DISCLAIMER` 위에 추가한다(이미 있으면 이 스텝은 건너뛴다).

```python
# --- 가격 맥락(price_context) 파라미터 ---
WEEK52_WINDOW = 252  # 52주 ≈ 영업일 252봉
PERIOD_RETURN_WINDOWS = {"1개월": 21, "3개월": 63, "6개월": 126, "12개월": 252}
VOLATILITY_GRADE_BOUNDS = (1.5, 3.0)  # 일간 변동성%: <1.5 낮음, <3.0 보통, ≥3.0 높음
DIVIDEND_PRINCIPAL = 1_000_000  # 배당 환산 기준금액
OVERHEAT_VOLUME_SPIKE = 2.0  # 거래대금 급증 배수 임계
OVERHEAT_RSI = (30, 70)  # (과매도, 과매수) RSI 임계
```

- [ ] **Step 2 (week52_position — 실패 테스트)**: `tests/test_price_context.py`에 52주 위치 테스트 작성.

```python
"""price_context 순수 함수 테스트 — 합성 OHLCV 주입(네트워크/pykrx 없음)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.analytics import price_context as pc


def _ohlcv(closes, *, highs=None, lows=None, volumes=None, values=None):
    """종가 리스트로 합성 OHLCV(index=영업일)를 만든다. 미지정 컬럼은 종가/기본값 파생."""
    closes = list(closes)
    n = len(closes)
    idx = pd.bdate_range("2024-01-01", periods=n)
    highs = list(highs) if highs is not None else [c * 1.0 for c in closes]
    lows = list(lows) if lows is not None else [c * 1.0 for c in closes]
    volumes = list(volumes) if volumes is not None else [1000] * n
    values = list(values) if values is not None else [c * v for c, v in zip(closes, volumes)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "value": values,
        },
        index=idx,
    )
    df.index.name = "date"
    return df


def test_week52_position_current_equals_high():
    # 현재가가 52주 최고가 → 위치 100%, 낙폭 0%
    df = _ohlcv([100, 90, 80, 110], highs=[100, 90, 80, 110], lows=[100, 90, 80, 110])
    res = pc.week52_position(df)
    assert res["high"] == 110
    assert res["low"] == 80
    assert res["pos_pct"] == 100.0
    assert res["drawdown_pct"] == 0.0


def test_week52_position_midpoint():
    # 고가 200, 저가 100, 현재가 150 → 위치 50%, 낙폭 -25%
    df = _ohlcv([100, 200, 150], highs=[100, 200, 150], lows=[100, 200, 150])
    res = pc.week52_position(df)
    assert res["high"] == 200
    assert res["low"] == 100
    assert res["pos_pct"] == 50.0
    assert res["drawdown_pct"] == -25.0


def test_week52_position_empty():
    df = _ohlcv([])
    res = pc.week52_position(df)
    assert res["pos_pct"] is None
    assert res["drawdown_pct"] is None
```

- [ ] **Step 3 (week52_position — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -v`
  Expected: FAIL (`core.analytics.price_context` 모듈 또는 `week52_position` 미구현 → ImportError/AttributeError)

- [ ] **Step 4 (week52_position — 최소 구현)**: `core/analytics/price_context.py` 신규 생성.

```python
"""가격 맥락 순수 함수 (OHLCV 기반, 외부 의존 없음 → 단위테스트 용이).

OHLCV 컬럼: open/high/low/close/volume/value, index=date.
모든 함수는 입력 비파괴(부작용 없음)이며, 데이터 부족 시 None 또는 안전값을 반환한다.
지표(SMA/RSI)는 core.analytics.indicators를 재사용한다.
"""
from __future__ import annotations

import pandas as pd

import config
from core.analytics import indicators


def _is_empty(ohlcv: pd.DataFrame) -> bool:
    return ohlcv is None or len(ohlcv) == 0


def week52_position(ohlcv: pd.DataFrame) -> dict:
    """최근 WEEK52_WINDOW 봉 기준 52주 고/저 대비 현재가 위치와 고점 낙폭.

    - pos_pct: (현재가-저가)/(고가-저가)*100, 0~100
    - drawdown_pct: (현재가/고가-1)*100, ≤0 (고점 대비 낙폭)
    빈 입력이면 모든 수치는 None.
    """
    if _is_empty(ohlcv):
        return {"low": None, "high": None, "pos_pct": None, "drawdown_pct": None}
    window = ohlcv.tail(config.WEEK52_WINDOW)
    high = float(window["high"].max())
    low = float(window["low"].min())
    close = float(window["close"].iloc[-1])
    if high == low:
        pos_pct = 100.0
    else:
        pos_pct = (close - low) / (high - low) * 100.0
    drawdown_pct = (close / high - 1.0) * 100.0 if high else None
    return {
        "low": low,
        "high": high,
        "pos_pct": round(pos_pct, 1),
        "drawdown_pct": round(drawdown_pct, 1),
    }
```

- [ ] **Step 5 (week52_position — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -v`
  Expected: PASS (3개 week52 테스트 통과)

- [ ] **Step 6 (week52_position — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py config.py`
  `git commit -m "feat: price_context 52주 위치/낙폭(week52_position) 추가"`

- [ ] **Step 7 (period_returns — 실패 테스트)**: `tests/test_price_context.py`에 기간 수익률 테스트 추가.

```python
def test_period_returns_sign_and_keys():
    # 21봉 전 100 → 현재 110: 1개월 +10%. 63봉 등 데이터 부족분은 None.
    closes = [100] * 21 + [110]  # 길이 22, 인덱스 -22가 100, 마지막 110
    df = _ohlcv(closes)
    res = pc.period_returns(df)
    # 키는 PERIOD_RETURN_WINDOWS와 동일
    assert set(res.keys()) == set(["1개월", "3개월", "6개월", "12개월"])
    assert res["1개월"] == 10.0  # (110/100 - 1)*100
    # 3·6·12개월은 데이터 부족 → None
    assert res["3개월"] is None
    assert res["12개월"] is None


def test_period_returns_negative():
    closes = [200] * 21 + [150]
    df = _ohlcv(closes)
    res = pc.period_returns(df)
    assert res["1개월"] == -25.0


def test_period_returns_empty():
    res = pc.period_returns(_ohlcv([]))
    assert res == {"1개월": None, "3개월": None, "6개월": None, "12개월": None}
```

- [ ] **Step 8 (period_returns — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k period_returns -v`
  Expected: FAIL (`period_returns` 미구현 → AttributeError)

- [ ] **Step 9 (period_returns — 최소 구현)**: `price_context.py`에 함수 추가.

```python
def period_returns(ohlcv: pd.DataFrame, windows=config.PERIOD_RETURN_WINDOWS) -> dict:
    """각 윈도우(영업일) 전 종가 대비 현재 종가 수익률(%). 데이터 부족 시 None."""
    result = {label: None for label in windows}
    if _is_empty(ohlcv):
        return result
    closes = ohlcv["close"]
    last = float(closes.iloc[-1])
    n = len(closes)
    for label, w in windows.items():
        if n > w:
            past = float(closes.iloc[-1 - w])
            if past:
                result[label] = round((last / past - 1.0) * 100.0, 1)
    return result
```

- [ ] **Step 10 (period_returns — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k period_returns -v`
  Expected: PASS

- [ ] **Step 11 (period_returns — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 기간 수익률(period_returns) 추가"`

- [ ] **Step 12 (ma_alignment — 실패 테스트)**: `tests/test_price_context.py`에 이동평균 배열 테스트 추가.

```python
def test_ma_alignment_bullish():
    # 꾸준히 상승 → SMA20 > SMA60 > SMA120 → 정배열
    closes = list(range(1, 201))  # 1..200 단조 증가, 200봉
    df = _ohlcv([float(c) for c in closes])
    assert pc.ma_alignment(df) == "정배열"


def test_ma_alignment_bearish():
    # 꾸준히 하락 → SMA20 < SMA60 < SMA120 → 역배열
    closes = list(range(200, 0, -1))  # 200..1 단조 감소
    df = _ohlcv([float(c) for c in closes])
    assert pc.ma_alignment(df) == "역배열"


def test_ma_alignment_mixed():
    # V자 반등: 하락 후 급반등 → 정/역배열 아님 → 혼조
    closes = list(range(120, 0, -1)) + list(range(1, 81))  # 200봉, 골 V
    df = _ohlcv([float(c) for c in closes])
    assert pc.ma_alignment(df) == "혼조"


def test_ma_alignment_insufficient():
    # 120봉 미만 → 혼조(판정 불가 안전값)
    df = _ohlcv([float(c) for c in range(1, 50)])
    assert pc.ma_alignment(df) == "혼조"
```

- [ ] **Step 13 (ma_alignment — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k ma_alignment -v`
  Expected: FAIL (`ma_alignment` 미구현 → AttributeError)

- [ ] **Step 14 (ma_alignment — 최소 구현)**: `price_context.py`에 함수 추가(SMA는 `indicators.sma` 재사용).

```python
def ma_alignment(ohlcv: pd.DataFrame) -> str:
    """SMA20/60/120 정렬 상태. 정배열(20>60>120)/역배열(20<60<120)/혼조.

    데이터 부족(120봉 미만)이거나 어느 쪽도 아니면 '혼조'.
    """
    if _is_empty(ohlcv) or len(ohlcv) < 120:
        return "혼조"
    close = ohlcv["close"]
    s20 = indicators.sma(close, 20).iloc[-1]
    s60 = indicators.sma(close, 60).iloc[-1]
    s120 = indicators.sma(close, 120).iloc[-1]
    if pd.isna(s20) or pd.isna(s60) or pd.isna(s120):
        return "혼조"
    if s20 > s60 > s120:
        return "정배열"
    if s20 < s60 < s120:
        return "역배열"
    return "혼조"
```

- [ ] **Step 15 (ma_alignment — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k ma_alignment -v`
  Expected: PASS

- [ ] **Step 16 (ma_alignment — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 이동평균 배열(ma_alignment) 추가"`

- [ ] **Step 17 (disparity — 실패 테스트)**: `tests/test_price_context.py`에 이격도 테스트 추가.

```python
def test_disparity_above_ma():
    # 60봉 동일가 100 후 마지막 110 → 종가>이동평균 → 이격도 양수
    closes = [100.0] * 60 + [110.0]
    df = _ohlcv(closes)
    res = pc.disparity(df, windows=(20, 60))
    assert set(res.keys()) == {20, 60}
    # 20일선은 (19*100+110)/20=100.5 → (110/100.5-1)*100 ≈ 9.45
    assert res[20] > 0
    assert res[60] > 0
    # 20일 이격도 > 60일 이격도(짧은 평균이 현재가에 더 가까움)
    assert res[20] < res[60]


def test_disparity_insufficient_window():
    # 30봉뿐 → 60일선 미산출 → None, 20일선은 산출
    closes = [100.0] * 30
    df = _ohlcv(closes)
    res = pc.disparity(df, windows=(20, 60))
    assert res[20] == 0.0  # 전부 동일가 → 종가=이동평균 → 0%
    assert res[60] is None


def test_disparity_empty():
    res = pc.disparity(_ohlcv([]), windows=(20, 60))
    assert res == {20: None, 60: None}
```

- [ ] **Step 18 (disparity — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k disparity -v`
  Expected: FAIL (`disparity` 미구현 → AttributeError)

- [ ] **Step 19 (disparity — 최소 구현)**: `price_context.py`에 함수 추가.

```python
def disparity(ohlcv: pd.DataFrame, windows=(20, 60)) -> dict:
    """이격도 = (종가/이동평균 - 1)*100. 윈도우별 dict. 데이터 부족 시 None."""
    result = {w: None for w in windows}
    if _is_empty(ohlcv):
        return result
    close = ohlcv["close"]
    last = float(close.iloc[-1])
    for w in windows:
        ma = indicators.sma(close, w).iloc[-1]
        if pd.notna(ma) and ma:
            result[w] = round((last / float(ma) - 1.0) * 100.0, 2)
    return result
```

- [ ] **Step 20 (disparity — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k disparity -v`
  Expected: PASS

- [ ] **Step 21 (disparity — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 이격도(disparity) 추가"`

- [ ] **Step 22 (max_drawdown — 실패 테스트)**: `tests/test_price_context.py`에 최대낙폭 테스트 추가.

```python
def test_max_drawdown_basic():
    # 100 → 200(고점) → 100(반토막) → MDD = -50%
    closes = [100.0, 200.0, 100.0, 150.0]
    df = _ohlcv(closes)
    mdd = pc.max_drawdown(df)
    assert mdd == -50.0


def test_max_drawdown_monotonic_up_is_zero():
    # 단조 상승 → 낙폭 없음 → 0%
    closes = [100.0, 110.0, 120.0, 130.0]
    df = _ohlcv(closes)
    assert pc.max_drawdown(df) == 0.0


def test_max_drawdown_non_positive():
    closes = [100.0, 80.0, 120.0, 60.0, 90.0]
    df = _ohlcv(closes)
    mdd = pc.max_drawdown(df)
    assert mdd <= 0.0


def test_max_drawdown_empty():
    assert pc.max_drawdown(_ohlcv([])) is None
```

- [ ] **Step 23 (max_drawdown — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k max_drawdown -v`
  Expected: FAIL (`max_drawdown` 미구현 → AttributeError)

- [ ] **Step 24 (max_drawdown — 최소 구현)**: `price_context.py`에 함수 추가.

```python
def max_drawdown(ohlcv: pd.DataFrame, window=config.WEEK52_WINDOW) -> float:
    """최근 window 봉 종가 기준 최대낙폭(%). 누적 최고점 대비 최저 하락폭, ≤0.

    빈 입력이면 None.
    """
    if _is_empty(ohlcv):
        return None
    close = ohlcv["close"].tail(window)
    running_max = close.cummax()
    drawdown = close / running_max - 1.0
    return round(float(drawdown.min()) * 100.0, 1)
```

- [ ] **Step 25 (max_drawdown — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k max_drawdown -v`
  Expected: PASS

- [ ] **Step 26 (max_drawdown — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 최대낙폭(max_drawdown) 추가"`

- [ ] **Step 27 (volume_ratio — 실패 테스트)**: `tests/test_price_context.py`에 거래량 배수 테스트 추가.

```python
def test_volume_ratio_double():
    # 직전 20일 거래량 1000, 마지막날 2000 → 배수 2.0
    # 비교 기준은 '직전 window일 평균'(마지막날 제외)
    volumes = [1000] * 20 + [2000]
    df = _ohlcv([100.0] * 21, volumes=volumes)
    ratio = pc.volume_ratio(df, window=20)
    assert ratio == 2.0


def test_volume_ratio_normal():
    volumes = [1000] * 21
    df = _ohlcv([100.0] * 21, volumes=volumes)
    assert pc.volume_ratio(df, window=20) == 1.0


def test_volume_ratio_insufficient():
    # window+1 봉 미만 → None
    df = _ohlcv([100.0] * 10, volumes=[1000] * 10)
    assert pc.volume_ratio(df, window=20) is None


def test_volume_ratio_empty():
    assert pc.volume_ratio(_ohlcv([]), window=20) is None
```

- [ ] **Step 28 (volume_ratio — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k volume_ratio -v`
  Expected: FAIL (`volume_ratio` 미구현 → AttributeError)

- [ ] **Step 29 (volume_ratio — 최소 구현)**: `price_context.py`에 함수 추가.

```python
def volume_ratio(ohlcv: pd.DataFrame, window: int = 20) -> float:
    """마지막날 거래량 / 직전 window일 평균 거래량(마지막날 제외). 데이터 부족 시 None."""
    if _is_empty(ohlcv) or len(ohlcv) <= window:
        return None
    volumes = ohlcv["volume"]
    last = float(volumes.iloc[-1])
    base = float(volumes.iloc[-1 - window : -1].mean())
    if not base:
        return None
    return round(last / base, 2)
```

- [ ] **Step 30 (volume_ratio — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k volume_ratio -v`
  Expected: PASS

- [ ] **Step 31 (volume_ratio — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 거래량 배수(volume_ratio) 추가"`

- [ ] **Step 32 (volatility_grade — 실패 테스트)**: `tests/test_price_context.py`에 변동성 등급 테스트 추가. 경계는 `VOLATILITY_GRADE_BOUNDS=(1.5, 3.0)`(일간 수익률 표준편차 %).

```python
def _closes_for_daily_std(target_pct, n=21):
    """일간 수익률이 +target%/-target% 교대가 되도록 종가열 생성.
    표준편차(모집단? 표본?)는 구현이 pandas std(ddof=1)를 쓰므로 근사로만 사용.
    경계 테스트는 명확히 낮음/보통/높음 구간에 들도록 여유를 둔다."""
    closes = [100.0]
    up = 1 + target_pct / 100.0
    down = 1 - target_pct / 100.0
    for i in range(n):
        closes.append(closes[-1] * (up if i % 2 == 0 else down))
    return closes


def test_volatility_grade_low():
    # 일간 변동 ±0.5% → 표준편차 < 1.5 → 낮음
    df = _ohlcv(_closes_for_daily_std(0.5))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "낮음"
    assert pct < 1.5


def test_volatility_grade_mid():
    # 일간 변동 ±2% → 1.5 ≤ std < 3.0 → 보통
    df = _ohlcv(_closes_for_daily_std(2.0))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "보통"
    assert 1.5 <= pct < 3.0


def test_volatility_grade_high():
    # 일간 변동 ±5% → std ≥ 3.0 → 높음
    df = _ohlcv(_closes_for_daily_std(5.0))
    grade, pct = pc.volatility_grade(df, window=20)
    assert grade == "높음"
    assert pct >= 3.0


def test_volatility_grade_empty():
    grade, pct = pc.volatility_grade(_ohlcv([]), window=20)
    assert grade is None
    assert pct is None
```

- [ ] **Step 33 (volatility_grade — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k volatility_grade -v`
  Expected: FAIL (`volatility_grade` 미구현 → AttributeError)

- [ ] **Step 34 (volatility_grade — 최소 구현)**: `price_context.py`에 함수 추가. 경계 규칙: `pct < low → 낮음`, `low ≤ pct < high → 보통`, `pct ≥ high → 높음`.

```python
def volatility_grade(ohlcv: pd.DataFrame, window: int = 20) -> tuple:
    """최근 window일 일간 수익률 표준편차(%)로 변동성 등급.

    경계 config.VOLATILITY_GRADE_BOUNDS=(low, high):
      pct < low → 낮음, low ≤ pct < high → 보통, pct ≥ high → 높음.
    반환 (등급, daily_pct). 데이터 부족이면 (None, None).
    """
    low, high = config.VOLATILITY_GRADE_BOUNDS
    if _is_empty(ohlcv) or len(ohlcv) <= window:
        return (None, None)
    rets = ohlcv["close"].pct_change().tail(window).dropna()
    if rets.empty:
        return (None, None)
    pct = float(rets.std()) * 100.0
    if pct < low:
        grade = "낮음"
    elif pct < high:
        grade = "보통"
    else:
        grade = "높음"
    return (grade, round(pct, 2))
```

- [ ] **Step 35 (volatility_grade — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k volatility_grade -v`
  Expected: PASS

- [ ] **Step 36 (volatility_grade — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 변동성 등급(volatility_grade) 추가"`

- [ ] **Step 37 (overheating — 실패 테스트)**: `tests/test_price_context.py`에 과열도 프록시 테스트 추가. 구성: RSI 과매수/과매도(`OVERHEAT_RSI`) + 거래대금 급증 배수(`OVERHEAT_VOLUME_SPIKE`) + 이격도 + 변동성 → 충족 신호 수로 등급(낮음/보통/높음/과열).

```python
def test_overheating_calm_is_low():
    # 동일가·동일거래량 → RSI 미산출/중립·급증 없음·이격도 0·저변동 → 낮음
    df = _ohlcv([100.0] * 130, volumes=[1000] * 130)
    res = pc.overheating(df)
    assert res["level"] == "낮음"
    assert "components" in res
    # 어떤 신호도 켜지지 않음
    assert res["components"]["volume_spike"] is False


def test_overheating_high_when_overbought_and_spike():
    # 강한 단조 상승(RSI 과매수) + 마지막날 거래대금 급증 + 큰 이격도
    closes = [float(c) for c in range(1, 131)]  # 1..130 단조 상승 → RSI 100, 이격도 큼
    volumes = [1000] * 129 + [5000]  # 마지막날 5배 급증
    df = _ohlcv(closes, volumes=volumes)
    res = pc.overheating(df)
    # RSI 과매수 + 거래대금 급증 + 이격도 신호 → 다수 충족
    assert res["components"]["rsi_overbought"] is True
    assert res["components"]["volume_spike"] is True
    assert res["level"] in ("높음", "과열")


def test_overheating_empty():
    res = pc.overheating(_ohlcv([]))
    assert res["level"] is None
    assert res["components"] == {}
```

- [ ] **Step 38 (overheating — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k overheating -v`
  Expected: FAIL (`overheating` 미구현 → AttributeError)

- [ ] **Step 39 (overheating — 최소 구현)**: `price_context.py`에 함수 추가. RSI는 `indicators.rsi`, 거래대금 급증은 `volume_ratio`(value 기반 별도 계산), 이격도는 `disparity`, 변동성은 `volatility_grade` 재사용. 충족 신호 수: 0→낮음, 1→보통, 2→높음, 3+→과열.

```python
def overheating(ohlcv: pd.DataFrame) -> dict:
    """가격·거래량 기반 과열도 프록시(게시판 심리 아님).

    구성 신호(불리언):
      - rsi_overbought: RSI ≥ OVERHEAT_RSI[1]
      - rsi_oversold: RSI ≤ OVERHEAT_RSI[0] (참고용, 과열 가산에는 미포함)
      - volume_spike: 마지막날 거래대금 / 직전 20일 평균 ≥ OVERHEAT_VOLUME_SPIKE
      - disparity_high: 20일 이격도 ≥ 10%
      - volatility_high: 변동성 등급 '높음'
    충족 신호 수 → 등급: 0 낮음 · 1 보통 · 2 높음 · 3+ 과열.
    빈 입력이면 level=None, components={}.
    """
    if _is_empty(ohlcv):
        return {"level": None, "components": {}}

    low_rsi, high_rsi = config.OVERHEAT_RSI

    rsi_series = indicators.rsi(ohlcv["close"])
    rsi_last = rsi_series.iloc[-1] if len(rsi_series) else None
    rsi_overbought = bool(pd.notna(rsi_last) and rsi_last >= high_rsi)
    rsi_oversold = bool(pd.notna(rsi_last) and rsi_last <= low_rsi)

    # 거래대금(value) 급증 배수: 마지막날 / 직전 20일 평균(마지막날 제외)
    volume_spike = False
    if len(ohlcv) > 20:
        val = ohlcv["value"]
        base = float(val.iloc[-21:-1].mean())
        if base:
            volume_spike = bool(float(val.iloc[-1]) / base >= config.OVERHEAT_VOLUME_SPIKE)

    disp = disparity(ohlcv, windows=(20,)).get(20)
    disparity_high = bool(disp is not None and disp >= 10.0)

    grade, _ = volatility_grade(ohlcv, window=20)
    volatility_high = bool(grade == "높음")

    components = {
        "rsi": float(rsi_last) if pd.notna(rsi_last) else None,
        "rsi_overbought": rsi_overbought,
        "rsi_oversold": rsi_oversold,
        "volume_spike": volume_spike,
        "disparity_high": disparity_high,
        "volatility_high": volatility_high,
    }
    hits = sum([rsi_overbought, volume_spike, disparity_high, volatility_high])
    if hits == 0:
        level = "낮음"
    elif hits == 1:
        level = "보통"
    elif hits == 2:
        level = "높음"
    else:
        level = "과열"
    return {"level": level, "components": components}
```

- [ ] **Step 40 (overheating — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k overheating -v`
  Expected: PASS

- [ ] **Step 41 (overheating — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 과열도 프록시(overheating) 추가"`

- [ ] **Step 42 (monitor_targets — 실패 테스트)**: `tests/test_price_context.py`에 손절/익절 이탈 감시 테스트 추가(가격만, 주문 없음).

```python
def test_monitor_targets_take_profit_reached():
    # 종가 ≥ 익절가 → 익절도달
    res = pc.monitor_targets(close=11000, stop=9000, target=10500)
    assert res["status"] == "익절도달"


def test_monitor_targets_stop_breached():
    # 종가 ≤ 손절가 → 손절이탈
    res = pc.monitor_targets(close=8900, stop=9000, target=10500)
    assert res["status"] == "손절이탈"


def test_monitor_targets_in_range():
    res = pc.monitor_targets(close=10000, stop=9000, target=10500)
    assert res["status"] == "범위내"


def test_monitor_targets_only_stop():
    # 익절가 미입력 → 손절만 감시
    assert pc.monitor_targets(close=9500, stop=9000, target=None)["status"] == "범위내"
    assert pc.monitor_targets(close=8500, stop=9000, target=None)["status"] == "손절이탈"


def test_monitor_targets_no_inputs():
    # 둘 다 없음 → 범위내(감시 대상 없음), close는 보존
    res = pc.monitor_targets(close=10000, stop=None, target=None)
    assert res["status"] == "범위내"
    assert res["close"] == 10000
```

- [ ] **Step 43 (monitor_targets — 실패 확인)**: Run: `python -m pytest tests/test_price_context.py -k monitor_targets -v`
  Expected: FAIL (`monitor_targets` 미구현 → AttributeError)

- [ ] **Step 44 (monitor_targets — 최소 구현)**: `price_context.py`에 함수 추가. 익절 우선 판정(둘 다 충족 시 익절도달 우선은 비현실적이므로 손절을 먼저 확인하는 것이 안전 — 손절 우선).

```python
def monitor_targets(close, stop=None, target=None) -> dict:
    """최신 종가 대비 손절가/익절가 이탈 '사실'만 고지(주문·자동매매 없음).

    판정 우선순위: 손절 이탈(생존 우선) → 익절 도달 → 범위내.
      - close ≤ stop → 손절이탈
      - close ≥ target → 익절도달
      - 그 외 → 범위내
    stop/target가 None이면 해당 조건은 건너뛴다.
    """
    status = "범위내"
    if stop is not None and close <= stop:
        status = "손절이탈"
    elif target is not None and close >= target:
        status = "익절도달"
    return {"status": status, "close": close, "stop": stop, "target": target}
```

- [ ] **Step 45 (monitor_targets — 통과 확인)**: Run: `python -m pytest tests/test_price_context.py -k monitor_targets -v`
  Expected: PASS

- [ ] **Step 46 (monitor_targets — 커밋)**:
  `git add core/analytics/price_context.py tests/test_price_context.py`
  `git commit -m "feat: price_context 손절/익절 이탈 감시(monitor_targets) 추가"`

- [ ] **Step 47 (전체 회귀 확인)**: 9개 함수 전체 테스트가 모두 통과하는지 확인.
  Run: `python -m pytest tests/test_price_context.py -v`
  Expected: PASS (week52_position·period_returns·ma_alignment·disparity·max_drawdown·volume_ratio·volatility_grade·overheating·monitor_targets 전부 통과)


### Task 4: labels.py (신규)

`core/analytics/labels.py`를 신규 작성한다. 모두 순수·결정론적 함수이며 `row`(스냅샷 1행: dict 또는 pandas Series)와 `latest_signals`(dict)만 입력받는다. 네트워크/Streamlit 호출 없음. 기존 관습(`from __future__ import annotations`, 한국어 주석, 절대 import)을 따른다. 임계값/상수는 `config`에서 가져온다(`config.BADGE_PERCENTILE`, `config.EXPLAIN_MIN_SUBSCORE`, `config.DIVIDEND_PRINCIPAL`).

먼저 `config.py`에 이 태스크가 의존하는 상수(`BADGE_PERCENTILE`, `EXPLAIN_MIN_SUBSCORE`, `DIVIDEND_PRINCIPAL`)가 없으면 추가한다. 그다음 함수별로 TDD 사이클을 반복한다: `badges` → `score_tier` → `verdict_*` → `explain_row` → `value_badge` → `dividend_won` → `earnings_yield` → `indicator_plain` → `signal_text` → `GLOSSARY`/`CAPTIONS`.

**준비 스텝 — config 상수 + 빈 모듈 골격**

- [ ] `config.py`에 이 태스크가 쓰는 상수가 정의돼 있는지 확인한다.
  Run: `python -c "import config; print(config.BADGE_PERCENTILE, config.EXPLAIN_MIN_SUBSCORE, config.DIVIDEND_PRINCIPAL)"`
  Expected: FAIL (`AttributeError: module 'config' has no attribute 'BADGE_PERCENTILE'` — 스펙 §7 신규 상수가 아직 없음)

- [ ] `config.py` 끝에 신규 상수를 추가한다(스펙 §7). 기존 `MIN_AVG_TRADING_VALUE` 정의 블록 아래, `# --- 기술적 지표 파라미터 ---` 위에 삽입한다.
```python
# --- 스크리너 / 라벨 임계값 (Phase 0a) ---
SCREENER_DEFAULT_LIMIT = 30            # 결과 카드 기본 표시 개수
BADGE_PERCENTILE = 70                  # 색 뱃지(저평가/우량/고배당) 임계 백분위
STABLE_CAP_PERCENTILE = 80            # 안정적 대형주 시총 하한 백분위
EXPLAIN_MIN_SUBSCORE = 60            # "왜 추천?" 근거 문구 노출 최소 서브스코어
DIVIDEND_PRINCIPAL = 1_000_000        # 배당 환산 기준금액(100만원)
```

- [ ] config 상수가 정상 로드되는지 재확인한다.
  Run: `python -c "import config; print(config.BADGE_PERCENTILE, config.EXPLAIN_MIN_SUBSCORE, config.DIVIDEND_PRINCIPAL)"`
  Expected: PASS (`70 60 1000000` 출력)

- [ ] 커밋한다.
  `git add config.py`
  `git commit -m "feat: 스크리너·라벨 임계 상수 config 추가"`

**함수 1 — `badges(row)`**

- [ ] 실패하는 테스트를 작성한다. `tests/test_labels.py`를 신규 생성한다.
```python
"""labels.py 순수 함수 단위 테스트 (합성 입력 주입, 네트워크/Streamlit 없음)."""
from __future__ import annotations

import pandas as pd

import config
from core.analytics import labels


def test_badges_all_three_when_subscores_high():
    """세 서브스코어가 모두 임계 이상이고 DIV>0이면 뱃지 3개."""
    row = {
        "value_score": 80.0,
        "quality_score": 75.0,
        "income_score": 90.0,
        "DIV": 3.2,
    }
    assert labels.badges(row) == ["저평가", "우량", "고배당"]


def test_badges_boundary_70_included_69_excluded():
    """경계: 70은 포함, 69는 제외(BADGE_PERCENTILE=70)."""
    assert config.BADGE_PERCENTILE == 70
    row_70 = {"value_score": 70.0, "quality_score": 70.0, "income_score": 70.0, "DIV": 1.0}
    assert labels.badges(row_70) == ["저평가", "우량", "고배당"]
    row_69 = {"value_score": 69.0, "quality_score": 69.0, "income_score": 69.0, "DIV": 1.0}
    assert labels.badges(row_69) == []


def test_badges_high_income_but_no_dividend_excluded():
    """income_score는 높지만 DIV<=0이면 고배당 뱃지 제외."""
    row = {"value_score": 10.0, "quality_score": 10.0, "income_score": 95.0, "DIV": 0.0}
    assert labels.badges(row) == []


def test_badges_nan_subscores_yield_empty():
    """서브스코어가 NaN이면 해당 뱃지 없음(깨지지 않음)."""
    row = {"value_score": float("nan"), "quality_score": float("nan"),
           "income_score": float("nan"), "DIV": float("nan")}
    assert labels.badges(row) == []


def test_badges_accepts_series():
    """pandas Series 입력도 dict와 동일하게 동작."""
    row = pd.Series({"value_score": 72.0, "quality_score": 10.0,
                     "income_score": 10.0, "DIV": 0.0})
    assert labels.badges(row) == ["저평가"]
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_badges_all_three_when_subscores_high -v`
  Expected: FAIL (`ModuleNotFoundError: No module named 'core.analytics.labels'` — 모듈 미생성)

- [ ] 최소 구현한다. `core/analytics/labels.py`를 신규 생성하고 공통 헬퍼 `_get`와 `badges`를 작성한다.
```python
"""결정론적 라벨/뱃지/설명/평가 문구 (순수 함수, 외부 의존 없음).

입력 `row`는 스냅샷 1행(dict 또는 pandas Series). 컬럼:
PER, PBR, EPS, BPS, DIV, DPS, ROE_approx, value_score, quality_score,
income_score, score, 종가, 시가총액.

모든 임계값/상수는 config에서 가져온다(단일 진실원천).
숫자 결측(None/NaN)은 안전하게 건너뛴다 — UI가 깨지지 않게.
"""
from __future__ import annotations

import math
from typing import Any

import config


def _get(row: Any, key: str) -> float | None:
    """row(dict/Series)에서 숫자값을 안전하게 꺼낸다. 결측/비숫자는 None."""
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        try:
            val = row.get(key)  # dict.get / Series.get
        except AttributeError:
            return None
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def badges(row: Any) -> list[str]:
    """행별 색 뱃지 목록(프리셋과 무관). 임계 config.BADGE_PERCENTILE.

    - 저평가  ← value_score   >= 임계
    - 우량    ← quality_score >= 임계
    - 고배당  ← income_score  >= 임계  AND  DIV > 0
    0~3개. 없으면 빈 리스트.
    """
    th = config.BADGE_PERCENTILE
    out: list[str] = []
    vs = _get(row, "value_score")
    qs = _get(row, "quality_score")
    isc = _get(row, "income_score")
    div = _get(row, "DIV")
    if vs is not None and vs >= th:
        out.append("저평가")
    if qs is not None and qs >= th:
        out.append("우량")
    if isc is not None and isc >= th and div is not None and div > 0:
        out.append("고배당")
    return out
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k badges`
  Expected: PASS (badges 관련 5개 테스트 통과)

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.badges 색 뱃지 규칙 구현"`

**함수 2 — `score_tier(score)`**

- [ ] 실패하는 테스트를 `tests/test_labels.py`에 추가한다.
```python
def test_score_tier_boundaries():
    """경계: >=75 good / 50~74 warn / <50 muted."""
    assert labels.score_tier(75) == "good"
    assert labels.score_tier(74.9) == "warn"
    assert labels.score_tier(50) == "warn"
    assert labels.score_tier(49.9) == "muted"
    assert labels.score_tier(0) == "muted"
    assert labels.score_tier(100) == "good"


def test_score_tier_none_or_nan_muted():
    """결측 점수는 muted로 폴백(UI 안전)."""
    assert labels.score_tier(None) == "muted"
    assert labels.score_tier(float("nan")) == "muted"
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_score_tier_boundaries -v`
  Expected: FAIL (`AttributeError: module 'core.analytics.labels' has no attribute 'score_tier'`)

- [ ] 최소 구현한다. `badges` 함수 아래에 `score_tier`를 추가한다.
```python
def score_tier(score: float | None) -> str:
    """종합점수 색 등급: >=75 good · 50~74 warn · <50 muted. 결측은 muted."""
    if score is None:
        return "muted"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "muted"
    if math.isnan(s):
        return "muted"
    if s >= 75:
        return "good"
    if s >= 50:
        return "warn"
    return "muted"
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k score_tier`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.score_tier 점수 색 등급 구현"`

**함수 3 — `verdict_value` / `verdict_quality` / `verdict_income`**

- [ ] 실패하는 테스트를 추가한다(§5.3 매핑: ≥70 / 40~69 / <40).
```python
def test_verdict_value_mapping():
    """가치: >=70 저평가 / 40~69 보통 / <40 비싼 편."""
    assert labels.verdict_value({"value_score": 70.0}) == ("저평가", "good")
    assert labels.verdict_value({"value_score": 69.9}) == ("보통", "warn")
    assert labels.verdict_value({"value_score": 40.0}) == ("보통", "warn")
    assert labels.verdict_value({"value_score": 39.9}) == ("비싼 편", "muted")


def test_verdict_quality_mapping():
    """수익성: >=70 우량 / 40~69 보통 / <40 수익성 낮음."""
    assert labels.verdict_quality({"quality_score": 88.0}) == ("우량", "good")
    assert labels.verdict_quality({"quality_score": 55.0}) == ("보통", "warn")
    assert labels.verdict_quality({"quality_score": 12.0}) == ("수익성 낮음", "muted")


def test_verdict_income_mapping_and_no_dividend():
    """배당: >=70 고배당 / 40~69 보통 / DIV없음·0 배당 적음."""
    assert labels.verdict_income({"income_score": 80.0, "DIV": 4.0}) == ("고배당", "good")
    assert labels.verdict_income({"income_score": 50.0, "DIV": 1.0}) == ("보통", "warn")
    # DIV가 0이면 income_score와 무관하게 "배당 적음"
    assert labels.verdict_income({"income_score": 80.0, "DIV": 0.0}) == ("배당 적음", "muted")
    # DIV 결측도 "배당 적음"
    assert labels.verdict_income({"income_score": 80.0}) == ("배당 적음", "muted")


def test_verdict_none_score_muted():
    """서브스코어 결측 시 안전 폴백(보통/muted 계열로 깨지지 않음)."""
    assert labels.verdict_value({}) == ("정보 없음", "muted")
    assert labels.verdict_quality({}) == ("정보 없음", "muted")
    assert labels.verdict_income({}) == ("배당 적음", "muted")
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_verdict_value_mapping -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'verdict_value'`)

- [ ] 최소 구현한다. `score_tier` 아래에 공통 헬퍼와 3개 verdict 함수를 추가한다.
```python
def _tier3(score: float | None, labels3: tuple[str, str, str]) -> tuple[str, str]:
    """>=70 → (labels3[0], good) · 40~69 → (labels3[1], warn) · <40 → (labels3[2], muted).
    결측이면 ("정보 없음", muted).
    """
    if score is None:
        return ("정보 없음", "muted")
    if score >= 70:
        return (labels3[0], "good")
    if score >= 40:
        return (labels3[1], "warn")
    return (labels3[2], "muted")


def verdict_value(row: Any) -> tuple[str, str]:
    """가치 평가: (라벨, 톤). value_score 기준."""
    return _tier3(_get(row, "value_score"), ("저평가", "보통", "비싼 편"))


def verdict_quality(row: Any) -> tuple[str, str]:
    """수익성 평가: (라벨, 톤). quality_score 기준."""
    return _tier3(_get(row, "quality_score"), ("우량", "보통", "수익성 낮음"))


def verdict_income(row: Any) -> tuple[str, str]:
    """배당 평가: (라벨, 톤). DIV가 없거나 0이면 income_score와 무관하게 "배당 적음"."""
    div = _get(row, "DIV")
    if div is None or div <= 0:
        return ("배당 적음", "muted")
    return _tier3(_get(row, "income_score"), ("고배당", "보통", "보통"))
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k verdict`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.verdict 가치/수익성/배당 평가 매핑 구현"`

**함수 4 — `explain_row(row)`**

- [ ] 실패하는 테스트를 추가한다(§4.3: 상위 2개, 근거 숫자 포함, 모두 미만이면 fallback).
```python
def test_explain_row_top2_by_subscore_descending():
    """서브스코어 높은 순 상위 2개를 ', '로 연결, 근거 숫자 포함."""
    row = {
        "value_score": 90.0, "quality_score": 80.0, "income_score": 65.0,
        "PER": 8.0, "PBR": 0.9, "ROE_approx": 15.0, "DIV": 3.0,
    }
    text = labels.explain_row(row)
    # value(90) > quality(80) > income(65) → 상위 2 = 가치, 수익성
    assert text == "PER 8.0배·PBR 0.9배로 저렴, ROE(근사) 15%로 수익성 양호"


def test_explain_row_boundary_60_included():
    """경계: 서브스코어 60(EXPLAIN_MIN_SUBSCORE)은 포함."""
    assert config.EXPLAIN_MIN_SUBSCORE == 60
    row = {
        "value_score": 60.0, "quality_score": 10.0, "income_score": 10.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    assert labels.explain_row(row) == "PER 12.0배·PBR 1.5배로 저렴"


def test_explain_row_fallback_when_all_below_60():
    """모든 서브스코어가 60 미만이면 fallback 문구."""
    row = {
        "value_score": 59.9, "quality_score": 30.0, "income_score": 10.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    assert labels.explain_row(row) == "종합점수 기준 상위 후보"


def test_explain_row_skips_when_underlying_number_invalid():
    """서브스코어는 높아도 근거 숫자가 무효면 해당 문구 제외."""
    # value_score 높지만 PER<=0(적자) → 가치 문구 제외, income으로 대체
    row = {
        "value_score": 90.0, "quality_score": 10.0, "income_score": 75.0,
        "PER": -3.0, "PBR": 0.8, "ROE_approx": 5.0, "DIV": 4.0,
    }
    assert labels.explain_row(row) == "배당수익률 4.0%로 배당 넉넉"


def test_explain_row_income_requires_positive_div():
    """배당 문구는 DIV>0일 때만."""
    row = {
        "value_score": 10.0, "quality_score": 10.0, "income_score": 95.0,
        "PER": 12.0, "PBR": 1.5, "ROE_approx": 5.0, "DIV": 0.0,
    }
    # income_score 높지만 DIV=0 → 배당 문구 불가, 나머지도 60 미만 → fallback
    assert labels.explain_row(row) == "종합점수 기준 상위 후보"
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_explain_row_top2_by_subscore_descending -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'explain_row'`)

- [ ] 최소 구현한다. verdict 함수 아래에 `explain_row`를 추가한다.
```python
def explain_row(row: Any) -> str:
    """"왜 추천?" 결정론적 한 줄(§4.3).

    각 후보 문구는 (서브스코어 >= EXPLAIN_MIN_SUBSCORE) AND (근거 숫자 유효)일 때만 후보.
    서브스코어가 높은 순으로 상위 2개를 ', '로 연결.
    유효 후보가 없으면 "종합점수 기준 상위 후보".
    """
    th = config.EXPLAIN_MIN_SUBSCORE
    per = _get(row, "PER")
    pbr = _get(row, "PBR")
    roe = _get(row, "ROE_approx")
    div = _get(row, "DIV")
    vs = _get(row, "value_score")
    qs = _get(row, "quality_score")
    isc = _get(row, "income_score")

    candidates: list[tuple[float, str]] = []
    # 가치: value_score >= th AND PER>0 AND PBR>0
    if vs is not None and vs >= th and per is not None and per > 0 and pbr is not None and pbr > 0:
        candidates.append((vs, f"PER {per:.1f}배·PBR {pbr:.2f}배로 저렴"))
    # 수익성: quality_score >= th AND ROE 유효
    if qs is not None and qs >= th and roe is not None:
        candidates.append((qs, f"ROE(근사) {roe:.0f}%로 수익성 양호"))
    # 배당: income_score >= th AND DIV>0
    if isc is not None and isc >= th and div is not None and div > 0:
        candidates.append((isc, f"배당수익률 {div:.1f}%로 배당 넉넉"))

    if not candidates:
        return "종합점수 기준 상위 후보"
    candidates.sort(key=lambda x: x[0], reverse=True)
    return ", ".join(text for _, text in candidates[:2])
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k explain_row`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.explain_row 왜 추천 근거 문구 구현"`

**함수 5 — `value_badge(row)`**

- [ ] 실패하는 테스트를 추가한다(§5.7 직관 배지, value_score 분포 기반).
```python
def test_value_badge_cheap_normal_expensive():
    """value_score 기준 직관 배지: 높음=싼 편 / 중간=평균 수준 / 낮음=비싼 편."""
    assert labels.value_badge({"value_score": 75.0}) == "시장 평균보다 싼 편"
    assert labels.value_badge({"value_score": 50.0}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 20.0}) == "시장 평균보다 비싼 편"


def test_value_badge_boundaries():
    """경계: >=66 싼 편 / 34~65 평균 수준 / <34 비싼 편."""
    assert labels.value_badge({"value_score": 66.0}) == "시장 평균보다 싼 편"
    assert labels.value_badge({"value_score": 65.9}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 34.0}) == "시장 평균 수준"
    assert labels.value_badge({"value_score": 33.9}) == "시장 평균보다 비싼 편"


def test_value_badge_none():
    """value_score 결측이면 None 반환(배지 숨김)."""
    assert labels.value_badge({}) is None
    assert labels.value_badge({"value_score": float("nan")}) is None
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_value_badge_cheap_normal_expensive -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'value_badge'`)

- [ ] 최소 구현한다. `explain_row` 아래에 `value_badge`를 추가한다.
```python
def value_badge(row: Any) -> str | None:
    """직관 배지(§5.7): value_score(가치 백분위) 기준 한 줄. 결측이면 None.

    >=66 → 싼 편 · 34~65 → 평균 수준 · <34 → 비싼 편 (백분위 3분할).
    """
    vs = _get(row, "value_score")
    if vs is None:
        return None
    if vs >= 66:
        return "시장 평균보다 싼 편"
    if vs >= 34:
        return "시장 평균 수준"
    return "시장 평균보다 비싼 편"
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k value_badge`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.value_badge 직관 가치 배지 구현"`

**함수 6 — `dividend_won(row, principal)`**

- [ ] 실패하는 테스트를 추가한다(§5.7 배당 환산 "100만원당 연 ~N원").
```python
def test_dividend_won_from_div_rate():
    """DIV(배당수익률 %)로 기준금액당 연 배당액 환산: 100만원 × DIV%."""
    # DIV 3.0% → 100만원당 30,000원
    assert labels.dividend_won({"DIV": 3.0}) == 30000


def test_dividend_won_custom_principal():
    """principal 인자 적용."""
    assert labels.dividend_won({"DIV": 2.5}, principal=2_000_000) == 50000


def test_dividend_won_default_principal_from_config():
    """기본 principal은 config.DIVIDEND_PRINCIPAL(100만원)."""
    assert config.DIVIDEND_PRINCIPAL == 1_000_000
    assert labels.dividend_won({"DIV": 1.0}) == 10000


def test_dividend_won_zero_or_missing():
    """DIV 없음/0이면 0 반환(배당 없음)."""
    assert labels.dividend_won({"DIV": 0.0}) == 0
    assert labels.dividend_won({}) == 0
    assert labels.dividend_won({"DIV": float("nan")}) == 0
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_dividend_won_from_div_rate -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'dividend_won'`)

- [ ] 최소 구현한다. `value_badge` 아래에 `dividend_won`을 추가한다.
```python
def dividend_won(row: Any, principal: int = config.DIVIDEND_PRINCIPAL) -> int:
    """기준금액(principal) 투자 시 연 배당액(원) 환산(§5.7).

    DIV는 배당수익률(%) → principal × DIV / 100. 정수 원 단위로 반올림.
    DIV 없음/0/음수면 0.
    """
    div = _get(row, "DIV")
    if div is None or div <= 0:
        return 0
    return int(round(principal * div / 100.0))
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k dividend_won`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.dividend_won 배당 환산액 구현"`

**함수 7 — `earnings_yield(row)`**

- [ ] 실패하는 테스트를 추가한다(§5.7 이익수익률 1/PER, PER≤0="적자").
```python
def test_earnings_yield_from_per():
    """이익수익률 = 1/PER × 100 (%). PER 10 → 10.0%."""
    assert labels.earnings_yield({"PER": 10.0}) == "10.0%"
    assert labels.earnings_yield({"PER": 8.0}) == "12.5%"


def test_earnings_yield_negative_or_zero_per():
    """PER<=0(적자)이면 '적자'."""
    assert labels.earnings_yield({"PER": 0.0}) == "적자"
    assert labels.earnings_yield({"PER": -5.0}) == "적자"


def test_earnings_yield_missing_per():
    """PER 결측이면 '적자' 아님 — 정보 없음 표기."""
    assert labels.earnings_yield({}) == "정보 없음"
    assert labels.earnings_yield({"PER": float("nan")}) == "정보 없음"
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_earnings_yield_from_per -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'earnings_yield'`)

- [ ] 최소 구현한다. `dividend_won` 아래에 `earnings_yield`를 추가한다.
```python
def earnings_yield(row: Any) -> str:
    """이익수익률(1/PER, §5.7). PER<=0이면 "적자", PER 결측이면 "정보 없음".

    표기는 백분율 문자열(예: "10.0%").
    """
    per = _get(row, "PER")
    if per is None:
        return "정보 없음"
    if per <= 0:
        return "적자"
    return f"{100.0 / per:.1f}%"
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k earnings_yield`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.earnings_yield 이익수익률 구현"`

**함수 8 — `indicator_plain(latest_signals)`**

- [ ] 실패하는 테스트를 추가한다(§5.7 RSI/MACD 말풀이 + RSI≥70/≤30만 주의 캡션). `latest_signals` 형태는 `indicators.latest_signals` 산출물(`rsi`, `macd_hist`, `rsi_state` 등)을 따른다.
```python
def test_indicator_plain_overbought_caption():
    """RSI>=70이면 과매수 주의 캡션 포함."""
    sig = {"rsi": 72.0, "macd_hist": 0.5, "rsi_state": "과매수(≥70)"}
    text = labels.indicator_plain(sig)
    assert "RSI 72" in text
    assert "과매수" in text
    assert "주의" in text


def test_indicator_plain_oversold_caption():
    """RSI<=30이면 과매도 주의 캡션 포함."""
    sig = {"rsi": 28.0, "macd_hist": -0.3, "rsi_state": "과매도(≤30)"}
    text = labels.indicator_plain(sig)
    assert "RSI 28" in text
    assert "과매도" in text
    assert "주의" in text


def test_indicator_plain_neutral_no_caution():
    """RSI 30~70(경계 70/30 제외 구간)에서는 주의 캡션 없음."""
    sig = {"rsi": 55.0, "macd_hist": 0.1, "rsi_state": "중립"}
    text = labels.indicator_plain(sig)
    assert "RSI 55" in text
    assert "주의" not in text


def test_indicator_plain_boundary_70_and_30():
    """경계: RSI 정확히 70/30은 주의 대상."""
    assert "주의" in labels.indicator_plain({"rsi": 70.0})
    assert "주의" in labels.indicator_plain({"rsi": 30.0})
    assert "주의" not in labels.indicator_plain({"rsi": 69.9})
    assert "주의" not in labels.indicator_plain({"rsi": 30.1})


def test_indicator_plain_macd_direction():
    """MACD 히스토그램 부호로 상승/하락 모멘텀 말풀이."""
    assert "상승" in labels.indicator_plain({"rsi": 50.0, "macd_hist": 0.4})
    assert "하락" in labels.indicator_plain({"rsi": 50.0, "macd_hist": -0.4})


def test_indicator_plain_empty():
    """빈 신호면 안내 문구(깨지지 않음)."""
    assert labels.indicator_plain({}) == "지표 데이터가 없습니다."
    assert labels.indicator_plain(None) == "지표 데이터가 없습니다."
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_indicator_plain_overbought_caption -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'indicator_plain'`)

- [ ] 최소 구현한다. `earnings_yield` 아래에 `indicator_plain`을 추가한다.
```python
def indicator_plain(latest_signals: dict | None) -> str:
    """RSI·MACD 말풀이 + 과매수/과매도 주의 캡션(§5.7).

    주의 캡션은 RSI>=70(과매수) 또는 RSI<=30(과매도)일 때만 붙인다.
    그 외 구간은 사실 설명만(주의 없음).
    """
    if not latest_signals:
        return "지표 데이터가 없습니다."

    parts: list[str] = []
    rsi_val = latest_signals.get("rsi")
    rsi_f: float | None
    try:
        rsi_f = float(rsi_val) if rsi_val is not None else None
        if rsi_f is not None and math.isnan(rsi_f):
            rsi_f = None
    except (TypeError, ValueError):
        rsi_f = None

    if rsi_f is not None:
        if rsi_f >= 70:
            parts.append(f"RSI {rsi_f:.0f} — 과매수 구간, 단기 과열 주의")
        elif rsi_f <= 30:
            parts.append(f"RSI {rsi_f:.0f} — 과매도 구간, 단기 낙폭 주의")
        else:
            parts.append(f"RSI {rsi_f:.0f} — 중립 구간")

    hist = latest_signals.get("macd_hist")
    try:
        hist_f = float(hist) if hist is not None else None
        if hist_f is not None and math.isnan(hist_f):
            hist_f = None
    except (TypeError, ValueError):
        hist_f = None
    if hist_f is not None:
        if hist_f > 0:
            parts.append("MACD 상승 모멘텀")
        elif hist_f < 0:
            parts.append("MACD 하락 모멘텀")
        else:
            parts.append("MACD 모멘텀 중립")

    if not parts:
        return "지표 데이터가 없습니다."
    return " · ".join(parts)
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k indicator_plain`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.indicator_plain RSI/MACD 말풀이 구현"`

**함수 9 — `signal_text(latest_signals, ma_alignment=None)`**

- [ ] 실패하는 테스트를 추가한다(§5.5/§5.7 차트 위 "신호 한 줄", ma_alignment 보강).
```python
def test_signal_text_basic():
    """20일선 위/RSI/MACD를 한 줄로 요약."""
    sig = {
        "above_sma20": True, "rsi": 58.0, "rsi_state": "중립", "macd_hist": 0.2,
    }
    text = labels.signal_text(sig)
    assert "20일선 위" in text
    assert "RSI 58" in text
    assert "MACD 상승" in text


def test_signal_text_below_sma20():
    """20일선 아래 표기."""
    sig = {"above_sma20": False, "rsi": 45.0, "rsi_state": "중립", "macd_hist": -0.1}
    text = labels.signal_text(sig)
    assert "20일선 아래" in text
    assert "MACD 하락" in text


def test_signal_text_with_ma_alignment():
    """ma_alignment 인자가 주어지면 추세 한 줄로 보강(맨 앞)."""
    sig = {"above_sma20": True, "rsi": 60.0, "rsi_state": "중립", "macd_hist": 0.1}
    text = labels.signal_text(sig, ma_alignment="정배열")
    assert "정배열" in text
    assert "20일선 위" in text


def test_signal_text_none_and_empty():
    """빈 신호 / None 안전 처리."""
    assert labels.signal_text({}) == "신호 데이터가 없습니다."
    assert labels.signal_text(None) == "신호 데이터가 없습니다."
    # ma_alignment만 있고 신호 비었으면 추세만이라도 표기
    assert labels.signal_text(None, ma_alignment="역배열") == "역배열"


def test_signal_text_handles_missing_fields():
    """일부 필드 결측 시 가능한 항목만 표기(깨지지 않음)."""
    sig = {"rsi": 50.0, "rsi_state": "중립"}  # above_sma20/macd 없음
    text = labels.signal_text(sig)
    assert "RSI 50" in text
    assert "20일선" not in text
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_signal_text_basic -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'signal_text'`)

- [ ] 최소 구현한다. `indicator_plain` 아래에 `signal_text`를 추가한다.
```python
def signal_text(latest_signals: dict | None, ma_alignment: str | None = None) -> str:
    """차트 위 "신호 한 줄"(§5.5). 추세(ma_alignment) → 20일선 위치 → RSI → MACD.

    각 항목은 데이터가 있을 때만 포함한다. 모두 없으면 안내 문구.
    """
    parts: list[str] = []
    if ma_alignment:
        parts.append(str(ma_alignment))

    sig = latest_signals or {}

    above20 = sig.get("above_sma20")
    if above20 is True:
        parts.append("20일선 위")
    elif above20 is False:
        parts.append("20일선 아래")

    rsi_val = sig.get("rsi")
    try:
        rsi_f = float(rsi_val) if rsi_val is not None else None
        if rsi_f is not None and math.isnan(rsi_f):
            rsi_f = None
    except (TypeError, ValueError):
        rsi_f = None
    if rsi_f is not None:
        state = sig.get("rsi_state")
        if state == "중립" or state is None:
            parts.append(f"RSI {rsi_f:.0f}(중립)")
        elif "과매수" in str(state):
            parts.append(f"RSI {rsi_f:.0f}(과매수)")
        elif "과매도" in str(state):
            parts.append(f"RSI {rsi_f:.0f}(과매도)")
        else:
            parts.append(f"RSI {rsi_f:.0f}")

    hist = sig.get("macd_hist")
    try:
        hist_f = float(hist) if hist is not None else None
        if hist_f is not None and math.isnan(hist_f):
            hist_f = None
    except (TypeError, ValueError):
        hist_f = None
    if hist_f is not None:
        if hist_f > 0:
            parts.append("MACD 상승")
        elif hist_f < 0:
            parts.append("MACD 하락")
        else:
            parts.append("MACD 보합")

    if not parts:
        return "신호 데이터가 없습니다."
    return " · ".join(parts)
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k signal_text`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.signal_text 신호 한 줄 + 추세 보강 구현"`

**정적 데이터 — `GLOSSARY` / `CAPTIONS`**

- [ ] 실패하는 테스트를 추가한다(§5.7 용어 정의, §4.5/§5.4/§8 정적 고지).
```python
def test_glossary_has_required_terms():
    """GLOSSARY는 dict이며 필수 용어 키를 모두 포함하고, 값은 비지 않은 한 줄 정의."""
    assert isinstance(labels.GLOSSARY, dict)
    required = ["PER", "PBR", "ROE_approx", "DIV", "시가총액",
                "EPS", "BPS", "DPS", "RSI", "이동평균", "MACD"]
    for term in required:
        assert term in labels.GLOSSARY, f"용어 누락: {term}"
        assert isinstance(labels.GLOSSARY[term], str)
        assert labels.GLOSSARY[term].strip() != ""


def test_captions_static_disclosures_present():
    """CAPTIONS는 dict이며 핵심 정적 고지(상대순위·대형주 한계·적자 PER) 포함."""
    assert isinstance(labels.CAPTIONS, dict)
    for key in ["relative_rank", "stable_cap_limit", "negative_per"]:
        assert key in labels.CAPTIONS
        assert isinstance(labels.CAPTIONS[key], str)
        assert labels.CAPTIONS[key].strip() != ""
    # 의미 단언: 상대순위 캡션은 매수신호가 아님을 명시
    assert "매수 신호" in labels.CAPTIONS["relative_rank"]
    # 적자 PER 캡션은 "오류 아님" 명시(§4.5)
    assert "오류" in labels.CAPTIONS["negative_per"]
```

- [ ] 실패를 확인한다.
  Run: `python -m pytest tests/test_labels.py::test_glossary_has_required_terms -v`
  Expected: FAIL (`AttributeError: ... has no attribute 'GLOSSARY'`)

- [ ] 최소 구현한다. `labels.py` 하단(함수 정의 아래)에 `GLOSSARY`와 `CAPTIONS`를 추가한다.
```python
# --- 정적 용어 사전(§5.7 용어 ⓘ 툴팁) ---
GLOSSARY: dict[str, str] = {
    "PER": "주가수익비율 — 주가가 주당순이익(EPS)의 몇 배인지. 낮을수록 이익 대비 저렴.",
    "PBR": "주가순자산비율 — 주가가 주당순자산(BPS)의 몇 배인지. 낮을수록 자산 대비 저렴.",
    "ROE_approx": "자기자본이익률(근사, EPS÷BPS) — 자본으로 얼마나 버는지. 높을수록 수익성 양호.",
    "DIV": "배당수익률(%) — 주가 대비 1년 배당금 비율. 높을수록 현금 환원이 큼.",
    "시가총액": "주가 × 발행주식수 — 회사의 시장가치(덩치). 클수록 대형주.",
    "EPS": "주당순이익 — 1주가 1년간 벌어들인 순이익.",
    "BPS": "주당순자산 — 1주에 해당하는 회사 순자산(자본).",
    "DPS": "주당배당금 — 1주당 지급되는 연 배당금(원).",
    "RSI": "상대강도지수(0~100) — 70 이상이면 과매수, 30 이하면 과매도로 본다.",
    "이동평균": "최근 일정 기간 종가의 평균선 — 추세 방향을 가늠하는 기준선.",
    "MACD": "단기·장기 이동평균의 차이 — 0선 위/아래와 시그널 교차로 모멘텀을 본다.",
}

# --- 정적 고지/캡션(§4.5 · §5.4 · §8 정직 원칙) ---
CAPTIONS: dict[str, str] = {
    "relative_rank": (
        "점수와 막대는 전체 종목 중 상대 순위(백분위)이며, 매수 신호가 아닙니다. "
        "🟢상위 · 🟠중간 · ⚪하위는 같은 시점 다른 종목 대비 위치입니다."
    ),
    "stable_cap_limit": (
        "‘안정적인 대형주’는 시가총액(덩치)만 기준입니다. "
        "주가 변동성·재무 안정성은 반영하지 않으므로 ‘덩치 큰 회사’ 정도로만 해석하세요."
    ),
    "negative_per": (
        "PER가 ‘−’로 비어 있으면 최근 적자라 PER 계산이 불가한 경우이며 오류가 아닙니다."
    ),
    "buy_signal_not": (
        "본 화면의 모든 지표는 판단 보조용 참고 자료이며 단독 투자 판단 근거가 될 수 없습니다. "
        "투자 권유가 아닙니다."
    ),
    "roe_approx": (
        "ROE는 EPS÷BPS 근사치입니다. 정확한 ROE(당기순이익÷자본총계)는 다음 단계에서 제공됩니다."
    ),
    "alert_unknown": (
        "관리종목·투자경고 ‘지정’ 여부는 아직 미확인이며, 다음 단계(시장경보)에서 추가될 예정입니다."
    ),
}
```

- [ ] 통과를 확인한다.
  Run: `python -m pytest tests/test_labels.py -v -k "glossary or captions"`
  Expected: PASS

- [ ] 커밋한다.
  `git add core/analytics/labels.py tests/test_labels.py`
  `git commit -m "feat: labels.GLOSSARY/CAPTIONS 정적 용어·고지 추가"`

**전체 회귀 — labels.py 테스트 일괄 통과**

- [ ] `labels.py`의 모든 테스트가 함께 통과하는지 확인한다.
  Run: `python -m pytest tests/test_labels.py -v`
  Expected: PASS (모든 테스트 통과 — 뱃지/등급/평가/설명/풍부화 문구/용어·고지 전부)

- [ ] 다른 모듈에 회귀가 없는지 전체 스위트를 확인한다(존재 시).
  Run: `python -m pytest -q`
  Expected: PASS (labels 관련 신규 테스트 포함 전체 통과; 미구현 형제 모듈 테스트가 아직 없다면 labels만 통과)

- [ ] 최종 커밋한다(변경이 남아 있을 경우).
  `git add core/analytics/labels.py tests/test_labels.py config.py`
  `git commit -m "test: labels 전체 회귀 통과 확인"`

---

산출 파일(절대경로):
- 신규 소스: `C:/Users/donse/asi/core/analytics/labels.py`
- 신규 테스트: `C:/Users/donse/asi/tests/test_labels.py`
- 수정: `C:/Users/donse/asi/config.py` (`SCREENER_DEFAULT_LIMIT`/`BADGE_PERCENTILE`/`STABLE_CAP_PERCENTILE`/`EXPLAIN_MIN_SUBSCORE`/`DIVIDEND_PRINCIPAL` 추가)

참고(다른 태스크 소유): `signal_text`/`indicator_plain`이 받는 `latest_signals`는 `core/analytics/indicators.latest_signals`(키: `close`,`rsi`,`macd_hist`,`above_sma20`,`above_sma60`,`rsi_state`) 산출물을 그대로 사용한다. `ma_alignment` 문자열("정배열"/"역배열"/"혼조")은 `core/analytics/price_context.ma_alignment`(Task에서 별도 구현)에서 전달된다 — 본 태스크는 재정의하지 않고 인자로만 받는다.


### Task 5: screening.py (신규)

`core/analytics/screening.py`는 스크리너의 **순수 로직**이다. 4개 목적 프리셋 레지스트리(`PRESETS`)와 `apply_screen()`(공통 필터 → 프리셋 필터 → 정렬 → 상위 N)을 구현한다. 입력 DataFrame은 절대 변형하지 않는다(비파괴). 네트워크/pykrx/Streamlit 호출 없음 — 합성 pandas DataFrame을 주입해 TDD로 검증한다.

전제(스펙 §4.2, 기존 코드 확인):
- `scored_df`는 `core.analytics.scoring.compute_scores`가 만든 결과로, 컬럼에 `ticker, name, market, PER, PBR, DIV, 시가총액, 거래대금, value_score, quality_score, income_score, score`를 포함한다(시장값은 `"KOSPI"`/`"KOSDAQ"`).
- 신규 상수는 Task 1(config 수정)에서 추가되므로 여기서는 `config.SCREENER_DEFAULT_LIMIT`, `config.STABLE_CAP_PERCENTILE`, `config.MIN_MARKET_CAP`, `config.MIN_AVG_TRADING_VALUE`를 import해서 사용한다.

**함수 1 — `apply_screen` (공통 필터 + 종합 추천 프리셋 + 비파괴)**

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_screening.py`를 생성하고, 공통 유동성 필터·시장 필터·이름검색·비파괴·종합추천(score 내림차순/상위 N) 테스트를 작성한다.

```python
"""screening.apply_screen 단위 테스트 (합성 DataFrame 주입, 네트워크 없음)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from core.analytics import screening


def _make_scored() -> pd.DataFrame:
    """프리셋/필터 검증용 작은 합성 scored 스냅샷.

    유동성 통과(시총·거래대금 충분)와 탈락을 섞고,
    PER/PBR/DIV/각 sub-score를 의도적으로 배치한다.
    """
    return pd.DataFrame(
        {
            "ticker": ["000001", "000002", "000003", "000004", "000005", "000006"],
            "name": ["우량가치", "고배당주", "대형안정", "적자종목", "소형주", "코스닥A"],
            "market": ["KOSPI", "KOSPI", "KOSPI", "KOSPI", "KOSPI", "KOSDAQ"],
            "PER": [8.0, 12.0, 15.0, -5.0, 9.0, 7.0],
            "PBR": [0.8, 1.5, 1.2, 2.0, 1.1, 0.9],
            "DIV": [1.0, 5.0, 2.0, 0.0, 3.0, 4.0],
            "시가총액": [
                5_000_000_000_000,   # 5조 - 대형
                3_000_000_000_000,   # 3조
                8_000_000_000_000,   # 8조 - 최대형
                2_000_000_000_000,   # 2조
                10_000_000_000,      # 100억 - 시총 하한 미달(300억 < )
                1_000_000_000_000,   # 1조
            ],
            "거래대금": [
                10_000_000_000,
                8_000_000_000,
                12_000_000_000,
                5_000_000_000,
                500_000_000,
                50_000_000,          # 5천만 - 거래대금 하한(1억) 미달
            ],
            "value_score": [90.0, 40.0, 55.0, np.nan, 75.0, 85.0],
            "quality_score": [80.0, 50.0, 60.0, 30.0, 45.0, 70.0],
            "income_score": [20.0, 95.0, 50.0, np.nan, 70.0, 80.0],
            "score": [63.3, 61.7, 55.0, 30.0, 63.3, 78.3],
        }
    )


def test_공통필터_유동성하한_적용():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive")
    # 005(시총 미달)·006(거래대금 미달)은 공통 유동성 필터에서 탈락
    assert "000005" not in out["ticker"].values
    assert "000006" not in out["ticker"].values


def test_시장필터_코스닥만():
    df = _make_scored()
    # 코스닥 종목(006)은 거래대금 미달이라 0건이어야 함 → 시장 필터 동작 확인용으로
    # 거래대금을 충분히 올린 변형
    df = df.copy()
    df.loc[df["ticker"] == "000006", "거래대금"] = 9_000_000_000
    df.loc[df["ticker"] == "000006", "시가총액"] = 1_000_000_000_000
    out = screening.apply_screen(df, "comprehensive", market="코스닥")
    assert set(out["market"].unique()) == {"KOSDAQ"}
    assert "000006" in out["ticker"].values


def test_이름검색_부분일치():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive", query="고배당")
    assert list(out["ticker"].values) == ["000002"]


def test_종합추천_score_내림차순_정렬():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive")
    scores = list(out["score"].values)
    assert scores == sorted(scores, reverse=True)


def test_상위_limit_제한():
    df = _make_scored()
    out = screening.apply_screen(df, "comprehensive", limit=2)
    assert len(out) == 2


def test_입력_비파괴():
    df = _make_scored()
    before = df.copy(deep=True)
    screening.apply_screen(df, "comprehensive")
    pd.testing.assert_frame_equal(df, before)


def test_알수없는_프리셋_키_에러():
    df = _make_scored()
    with pytest.raises(KeyError):
        screening.apply_screen(df, "없는프리셋")
```

- [ ] **Step 2: 실패 확인**
  - Run: `python -m pytest tests/test_screening.py::test_종합추천_score_내림차순_정렬 -v`
  - Expected: FAIL (`core.analytics.screening` 모듈이 아직 없어 `ModuleNotFoundError`/`ImportError`)

- [ ] **Step 3: 최소 구현** — `core/analytics/screening.py`를 생성하고 공통 필터 헬퍼·`PRESETS` 레지스트리·`apply_screen`을 구현한다. (4개 프리셋 전부 포함해 한 번에 작성한다.)

```python
"""스크리너 순수 로직 — 목적 프리셋 레지스트리 + apply_screen().

설계 §4.2:
- 모든 프리셋에 공통 필터(시장·유동성·이름검색)를 먼저 적용한다.
- 그 다음 프리셋별 추가 필터를 적용하고, 정렬 키 내림차순으로 정렬한다.
- 정렬 키가 NaN인 행은 제외하고 상위 N개만 반환한다.
- 입력 DataFrame은 변형하지 않는다(비파괴).
- 네트워크/Streamlit 호출 없음. 합성 DataFrame으로 테스트 가능한 순수 함수.
"""
from __future__ import annotations

import pandas as pd

import config

# 시장 토글 표기(UI) → 스냅샷의 market 값 매핑
_MARKET_MAP = {"코스피": "KOSPI", "코스닥": "KOSDAQ"}


def _value_quality_avg(df: pd.DataFrame) -> pd.Series:
    """저평가 우량주 정렬 키: (value_score + quality_score) / 2."""
    return df[["value_score", "quality_score"]].mean(axis=1)


def _filter_value(df: pd.DataFrame) -> pd.Series:
    """저평가 우량주 추가 필터: PER>0 & PBR>0 (적자/무효 제외)."""
    return (df["PER"] > 0) & (df["PBR"] > 0)


def _filter_income(df: pd.DataFrame) -> pd.Series:
    """배당 프리셋 추가 필터: DIV>0 (배당 있는 종목만)."""
    return df["DIV"] > 0


def _filter_stable_cap(df: pd.DataFrame) -> pd.Series:
    """안정적 대형주 추가 필터: 공통 필터 후 집합에서 시총 STABLE_CAP_PERCENTILE 백분위 이상.

    자격 종목 중 시총 상위 ~20%(기본 80번째 백분위)만 남긴다.
    빈 집합/단일 종목은 quantile이 NaN/단일값이 되므로 안전하게 처리.
    """
    cap = df["시가총액"]
    if cap.dropna().empty:
        return pd.Series(False, index=df.index)
    threshold = cap.quantile(config.STABLE_CAP_PERCENTILE / 100.0)
    return cap >= threshold


def _no_filter(df: pd.DataFrame) -> pd.Series:
    """종합 추천: 추가 필터 없음(모두 통과)."""
    return pd.Series(True, index=df.index)


# 프리셋 레지스트리.
# extra_filter: (df) -> bool Series  /  sort_key: (df) -> 정렬용 Series (내림차순)
PRESETS: dict[str, dict] = {
    "value": {
        "emoji": "💎",
        "label": "저평가 우량주",
        "desc": "싸면서 돈 잘 버는 회사",
        "guide": "낮은 가격에 좋은 회사를 사고 싶다면",
        "extra_filter": _filter_value,
        "sort_key": _value_quality_avg,
    },
    "income": {
        "emoji": "💰",
        "label": "배당 잘 주는 주식",
        "desc": "배당수익률이 높은 회사",
        "guide": "꾸준한 현금흐름을 원한다면",
        "extra_filter": _filter_income,
        "sort_key": lambda df: df["income_score"],
    },
    "stable": {
        "emoji": "🛡️",
        "label": "안정적인 대형주",
        "desc": "덩치 큰 회사(시가총액 상위)",
        "guide": "흔들림이 덜한 큰 회사를 원한다면 (※ 덩치 기준, 변동성 미반영)",
        "extra_filter": _filter_stable_cap,
        "sort_key": lambda df: df["시가총액"],
    },
    "comprehensive": {
        "emoji": "⭐",
        "label": "종합 추천",
        "desc": "가치+품질+배당 종합 점수 상위",
        "guide": "뭘 골라야 할지 모르겠다면",
        "extra_filter": _no_filter,
        "sort_key": lambda df: df["score"],
    },
}


def _apply_common_filters(
    df: pd.DataFrame,
    *,
    market: str,
    query: str,
    min_cap: float,
    min_value: float,
) -> pd.DataFrame:
    """공통 필터: 시장 → 유동성(시총·거래대금) → 이름검색.

    스펙 §8: 거래대금은 '당일값'(스냅샷 컬럼) 기준이다.
    """
    mask = pd.Series(True, index=df.index)

    # 시장 토글(전체면 통과)
    krx_market = _MARKET_MAP.get(market)
    if krx_market is not None:
        mask &= df["market"] == krx_market

    # 유동성 하한(NaN은 미충족으로 간주 → False)
    mask &= df["시가총액"].fillna(-1) >= min_cap
    mask &= df["거래대금"].fillna(-1) >= min_value

    # 이름검색(부분 일치, 공백 제거). 빈 문자열이면 전체 통과.
    q = (query or "").strip()
    if q:
        mask &= df["name"].astype(str).str.contains(q, regex=False, na=False)

    return df[mask]


def apply_screen(
    scored_df: pd.DataFrame,
    preset_key: str,
    *,
    market: str = "전체",
    query: str = "",
    limit: int = config.SCREENER_DEFAULT_LIMIT,
    min_cap: float = config.MIN_MARKET_CAP,
    min_value: float = config.MIN_AVG_TRADING_VALUE,
) -> pd.DataFrame:
    """프리셋 조건으로 스크리닝한 결과를 반환.

    처리 순서(스펙 §4.2):
      1) 공통 필터(시장·유동성·이름검색)
      2) 프리셋 추가 필터
      3) 정렬 키 내림차순 정렬 + 정렬 키 NaN 행 제외
      4) 상위 limit개

    입력은 변형하지 않는다(비파괴). 빈 결과는 0행 DataFrame으로 반환.
    """
    if preset_key not in PRESETS:
        raise KeyError(f"알 수 없는 프리셋 키: {preset_key}")
    preset = PRESETS[preset_key]

    # 비파괴: 원본을 복사한 뒤에만 다룬다.
    df = scored_df.copy()

    # 1) 공통 필터
    df = _apply_common_filters(
        df, market=market, query=query, min_cap=min_cap, min_value=min_value
    )

    # 2) 프리셋 추가 필터 (공통 필터 후 집합 기준 — 안정대형주 백분위 포함)
    if not df.empty:
        df = df[preset["extra_filter"](df)]

    if df.empty:
        return df.reset_index(drop=True)

    # 3) 정렬 키 계산 → NaN 제외 → 내림차순
    sort_values = preset["sort_key"](df)
    df = df.assign(_sort_key=sort_values)
    df = df[df["_sort_key"].notna()]
    df = df.sort_values("_sort_key", ascending=False, kind="mergesort")
    df = df.drop(columns="_sort_key")

    # 4) 상위 limit개
    df = df.head(limit)
    return df.reset_index(drop=True)
```

- [ ] **Step 4: 통과 확인**
  - Run: `python -m pytest tests/test_screening.py::test_종합추천_score_내림차순_정렬 -v`
  - Expected: PASS
  - 추가로 공통 필터/시장/검색/limit/비파괴/에러 테스트도 함께 통과: `python -m pytest tests/test_screening.py -v`

- [ ] **Step 5: 커밋**
  - `git add core/analytics/screening.py tests/test_screening.py`
  - `git commit -m "feat: 스크리너 순수 로직 추가 — 공통 필터·종합추천 프리셋·apply_screen 비파괴 구현"`

**함수 2 — 저평가 우량주 프리셋(`value`) 필터/정렬 검증**

- [ ] **Step 6: 실패하는 테스트 추가** — `tests/test_screening.py`에 저평가 프리셋의 PER>0&PBR>0 필터, `(value+quality)/2` 내림차순, 적자종목 제외 테스트를 추가한다.

```python
def test_저평가_프리셋_per_pbr_양수만():
    df = _make_scored()
    # 적자종목(004, PER=-5)은 PER>0 조건에서 탈락. 단 공통 필터(시총·거래대금)는 통과시킴.
    out = screening.apply_screen(df, "value")
    assert (out["PER"] > 0).all()
    assert (out["PBR"] > 0).all()
    assert "000004" not in out["ticker"].values


def test_저평가_프리셋_value_quality_평균_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "value")
    key = (out["value_score"] + out["quality_score"]) / 2
    assert list(key.values) == sorted(key.values, reverse=True)
    # value_score 90·quality 80 인 001이 선두
    assert out.iloc[0]["ticker"] == "000001"
```

- [ ] **Step 7: 실패 확인**
  - Run: `python -m pytest tests/test_screening.py::test_저평가_프리셋_value_quality_평균_내림차순 -v`
  - Expected: PASS (이미 Step 3에서 `value` 프리셋을 구현했으므로 통과한다. 만약 FAIL이면 `_filter_value`/`_value_quality_avg` 로직을 점검)

> 참고: Step 3에서 4개 프리셋을 모두 구현했으므로 이 사이클은 구현 추가 없이 검증·고정용이다. 회귀 방지 테스트를 분리 커밋한다.

- [ ] **Step 8: 커밋**
  - `git add tests/test_screening.py`
  - `git commit -m "test: 저평가 우량주 프리셋 필터(PER·PBR 양수)·정렬 회귀 테스트 추가"`

**함수 3 — 배당(`income`) 프리셋 검증**

- [ ] **Step 9: 실패하는 테스트 추가** — DIV>0 필터와 `income_score` 내림차순 정렬을 검증한다.

```python
def test_배당_프리셋_div_양수만():
    df = _make_scored()
    out = screening.apply_screen(df, "income")
    assert (out["DIV"] > 0).all()
    # DIV=0 인 적자종목(004)은 제외
    assert "000004" not in out["ticker"].values


def test_배당_프리셋_income_score_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "income")
    inc = list(out["income_score"].values)
    assert inc == sorted(inc, reverse=True)
    # income_score 95 인 고배당주(002)가 선두
    assert out.iloc[0]["ticker"] == "000002"
```

- [ ] **Step 10: 실패 확인**
  - Run: `python -m pytest tests/test_screening.py::test_배당_프리셋_income_score_내림차순 -v`
  - Expected: PASS (Step 3에서 `income` 프리셋 구현 완료. FAIL 시 `_filter_income`/sort_key 점검)

- [ ] **Step 11: 커밋**
  - `git add tests/test_screening.py`
  - `git commit -m "test: 배당 프리셋 필터(DIV 양수)·income_score 정렬 회귀 테스트 추가"`

**함수 4 — 안정적 대형주(`stable`) 백분위 필터 + 정렬 키 NaN 제외 + 0건**

- [ ] **Step 12: 실패하는 테스트 추가** — 시총 백분위(공통 필터 후 집합 기준) 필터, 시가총액 내림차순, 정렬 키 NaN 제외, 0건 케이스를 검증한다.

```python
def test_안정대형주_시총_백분위_하한(monkeypatch):
    # STABLE_CAP_PERCENTILE 을 50으로 낮춰 상위 절반만 남는지 확인(공통 필터 후 4종목 기준).
    monkeypatch.setattr(config, "STABLE_CAP_PERCENTILE", 50)
    df = _make_scored()
    out = screening.apply_screen(df, "stable")
    # 공통 필터 통과 집합(001,002,003,004) 중 시총 상위 절반 → 003(8조),001(5조)
    assert set(out["ticker"].values) == {"000001", "000003"}


def test_안정대형주_시가총액_내림차순():
    df = _make_scored()
    out = screening.apply_screen(df, "stable")
    caps = list(out["시가총액"].values)
    assert caps == sorted(caps, reverse=True)


def test_정렬키_NaN_제외():
    # 정렬 키(score)가 NaN 인 행은 결과에서 빠진다.
    df = _make_scored()
    df = df.copy()
    df.loc[df["ticker"] == "000001", "score"] = np.nan
    out = screening.apply_screen(df, "comprehensive")
    assert "000001" not in out["ticker"].values


def test_결과_0건_빈_DataFrame():
    df = _make_scored()
    # 시총 하한을 비현실적으로 높여 모두 탈락
    out = screening.apply_screen(df, "comprehensive", min_cap=1e18)
    assert isinstance(out, pd.DataFrame)
    assert len(out) == 0
    # 컬럼 구조는 보존되어 UI가 깨지지 않게 한다.
    assert "ticker" in out.columns
```

- [ ] **Step 13: 실패 확인**
  - Run: `python -m pytest tests/test_screening.py::test_안정대형주_시총_백분위_하한 -v`
  - Expected: PASS (Step 3에서 `_filter_stable_cap`·NaN 제외·빈 결과 컬럼 보존을 모두 구현. FAIL 시 `_filter_stable_cap`의 `quantile` 경계나 `_apply_common_filters`의 빈 결과 컬럼 보존을 점검)

- [ ] **Step 14: 전체 테스트 통과 확인**
  - Run: `python -m pytest tests/test_screening.py -v`
  - Expected: PASS (모든 프리셋 필터·정렬·유동성·NaN 제외·0건·비파괴·에러 케이스)

- [ ] **Step 15: 커밋**
  - `git add tests/test_screening.py`
  - `git commit -m "test: 안정대형주 시총 백분위·정렬키 NaN 제외·0건 회귀 테스트 추가"`


### Task 6: checklist.py (신규) — 판단 체크리스트 6축(합산 매수점수 없음)

이 태스크는 `core/analytics/checklist.py`를 신규 작성한다. 스펙 §5.8 / §12.4를 단일 진실원천으로 한다. 6축 중 가치·기술·리스크·심리는 활성, 성장·수급은 잠금이다. 🔴 면책 핵심: **6축을 합산한 '매수점수'를 절대 만들지 않는다(축별 분리 표시)**. 다른 모듈 함수(`labels.verdict_*`, `price_context.ma_alignment/overheating`, `indicators.latest_signals`, `flags.compute_risk_flags`)는 스펙 시그니처대로 import만 하고 재정의하지 않는다(각각 다른 태스크에서 구현). 테스트는 작은 합성 pandas DataFrame을 직접 주입한다.

- [ ] **Step 1 — 실패하는 테스트 작성: 4 활성축 등급/사실 + 2 잠금축 표기 + 합산점수 부재 + 심리=과열도 연동**

  `tests/test_checklist.py`를 새로 만든다. 다른 태스크에서 구현될 `labels`/`price_context` 함수에 의존하지 않도록, 테스트 안에서 `build_checklist`가 호출하는 외부 함수들을 `monkeypatch`로 결정론적 더블로 치환한다(checklist.py가 그 함수들을 import해서 부르는지를 검증). 아래 전체 테스트 코드 블록을 그대로 작성한다.

  ```python
  """checklist.build_checklist 단위 테스트 (순수 로직, 합성 DataFrame 주입).

  외부 모듈 함수(labels.verdict_*, price_context.ma_alignment/overheating,
  indicators.latest_signals, flags.compute_risk_flags)는 다른 태스크에서 구현된다.
  여기서는 checklist가 그 함수들을 '시그니처대로 호출'하는지 검증하기 위해
  monkeypatch로 결정론적 더블을 주입한다.
  """
  from __future__ import annotations

  import pandas as pd
  import pytest

  from core.analytics import checklist


  def _make_ohlcv(n: int = 130) -> pd.DataFrame:
      """완만히 우상향하는 합성 일봉. 지표 계산에 충분한 길이."""
      idx = pd.date_range("2025-01-01", periods=n, freq="D")
      close = pd.Series(range(1000, 1000 + n), index=idx, dtype="float64")
      return pd.DataFrame(
          {
              "open": close,
              "high": close + 5,
              "low": close - 5,
              "close": close,
              "volume": 10_000,
              "value": 1_000_000_000,
          },
          index=idx,
      )


  def _patch_externals(monkeypatch, *, ma="정배열", overheat="보통",
                       risk=None, signals=None):
      """checklist가 부르는 외부 함수들을 결정론적 더블로 치환."""
      if risk is None:
          risk = []
      if signals is None:
          signals = {"rsi": 55.0, "rsi_state": "중립", "macd_hist": 1.2,
                     "above_sma20": True}
      monkeypatch.setattr(checklist, "ma_alignment", lambda ohlcv: ma)
      monkeypatch.setattr(
          checklist, "overheating",
          lambda ohlcv: {"level": overheat, "components": {}},
      )
      monkeypatch.setattr(checklist, "compute_risk_flags", lambda ohlcv: list(risk))
      monkeypatch.setattr(checklist, "latest_signals", lambda ohlcv: dict(signals))
      # verdict_*는 (label, tone)을 반환. 등급 산출은 checklist 내부 백분위 로직이 담당.
      monkeypatch.setattr(checklist, "verdict_value", lambda row: ("저평가", "good"))
      monkeypatch.setattr(checklist, "verdict_quality", lambda row: ("우량", "good"))


  def _row(value_score=85.0, quality_score=80.0, income_score=50.0):
      return pd.Series(
          {
              "ticker": "005930",
              "name": "삼성전자",
              "value_score": value_score,
              "quality_score": quality_score,
              "income_score": income_score,
              "PER": 8.0,
              "PBR": 1.1,
              "ROE_approx": 14.0,
              "DIV": 2.5,
          }
      )


  def test_returns_six_axes_in_order(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      assert [a["axis"] for a in out] == ["가치", "기술", "리스크", "심리", "성장", "수급"]


  def test_four_active_two_locked(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      by_axis = {a["axis"]: a for a in out}
      for name in ("가치", "기술", "리스크", "심리"):
          assert by_axis[name]["active"] is True
      for name in ("성장", "수급"):
          assert by_axis[name]["active"] is False
          assert by_axis[name]["grade"] is None
          assert by_axis[name]["locked_reason"]  # 비어있지 않은 잠금 사유


  def test_no_aggregate_buy_score_field(monkeypatch):
      """🔴 면책: 6축을 합산한 '매수점수' 필드를 절대 만들지 않는다."""
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      # 결과는 list[Axis]이며 dict 합산 점수 컨테이너가 아니다.
      assert isinstance(out, list)
      forbidden = {"매수점수", "총점", "buy_score", "total", "합산", "종합점수"}
      for axis in out:
          assert forbidden.isdisjoint(axis.keys())
          # 어떤 축에도 '합산'을 암시하는 숫자 점수 키가 없어야 한다.
          assert "score" not in axis


  def test_value_axis_grade_high_when_percentiles_high(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(value_score=90.0, quality_score=88.0),
          _make_ohlcv(), [], scored=pd.DataFrame(),
      )
      value = next(a for a in out if a["axis"] == "가치")
      assert value["grade"] == "양호"
      assert any("PER" in f or "PBR" in f or "ROE" in f or "백분위" in f
                 for f in value["facts"])


  def test_value_axis_grade_caution_when_percentiles_low(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(value_score=20.0, quality_score=15.0),
          _make_ohlcv(), [], scored=pd.DataFrame(),
      )
      value = next(a for a in out if a["axis"] == "가치")
      assert value["grade"] == "주의"


  def test_value_axis_grade_normal_in_middle(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(value_score=55.0, quality_score=52.0),
          _make_ohlcv(), [], scored=pd.DataFrame(),
      )
      value = next(a for a in out if a["axis"] == "가치")
      assert value["grade"] == "보통"


  def test_tech_axis_uses_ma_and_signals(monkeypatch):
      _patch_externals(
          monkeypatch, ma="정배열",
          signals={"rsi": 58.0, "rsi_state": "중립", "macd_hist": 2.0,
                   "above_sma20": True},
      )
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      tech = next(a for a in out if a["axis"] == "기술")
      assert tech["active"] is True
      joined = " ".join(tech["facts"])
      assert "정배열" in joined
      assert "RSI" in joined
      assert "MACD" in joined


  def test_tech_axis_caution_on_reverse_alignment(monkeypatch):
      _patch_externals(
          monkeypatch, ma="역배열",
          signals={"rsi": 25.0, "rsi_state": "과매도(≤30)", "macd_hist": -1.5,
                   "above_sma20": False},
      )
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      tech = next(a for a in out if a["axis"] == "기술")
      assert tech["grade"] == "주의"


  def test_risk_axis_lists_flags_and_grade(monkeypatch):
      flags = ["⚠️ 고변동성 — 최근 20일 일간 변동성이 큼"]
      _patch_externals(monkeypatch, risk=flags)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), flags, scored=pd.DataFrame()
      )
      risk = next(a for a in out if a["axis"] == "리스크")
      assert risk["active"] is True
      assert risk["facts"] == flags
      # 플래그가 있으면 '양호'가 아니다.
      assert risk["grade"] in ("보통", "주의")


  def test_risk_axis_good_when_no_flags(monkeypatch):
      _patch_externals(monkeypatch, risk=[])
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      risk = next(a for a in out if a["axis"] == "리스크")
      assert risk["grade"] == "양호"
      assert any("정상" in f or "없" in f for f in risk["facts"])


  def test_sentiment_axis_follows_overheating(monkeypatch):
      """심리축 = 과열도 프록시 등급 연동(게시판 아님)."""
      _patch_externals(monkeypatch, overheat="과열")
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      sentiment = next(a for a in out if a["axis"] == "심리")
      assert sentiment["active"] is True
      assert sentiment["grade"] == "주의"  # 과열 → 주의
      assert any("과열" in f for f in sentiment["facts"])


  def test_sentiment_axis_good_when_low(monkeypatch):
      _patch_externals(monkeypatch, overheat="낮음")
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      sentiment = next(a for a in out if a["axis"] == "심리")
      assert sentiment["grade"] == "양호"


  def test_locked_axes_reason_text(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      by_axis = {a["axis"]: a for a in out}
      assert "DART" in by_axis["성장"]["locked_reason"]
      assert "키움" in by_axis["수급"]["locked_reason"]


  def test_active_axes_have_locked_reason_none(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      for axis in out:
          if axis["active"]:
              assert axis["locked_reason"] is None


  def test_every_axis_has_full_schema(monkeypatch):
      _patch_externals(monkeypatch)
      out = checklist.build_checklist(
          _row(), _make_ohlcv(), [], scored=pd.DataFrame()
      )
      expected_keys = {"axis", "active", "grade", "facts", "locked_reason"}
      for axis in out:
          assert set(axis.keys()) == expected_keys
          assert isinstance(axis["facts"], list)
  ```

- [ ] **Step 2 — 실패 확인**

  Run: `python -m pytest tests/test_checklist.py -v`
  Expected: FAIL (`core/analytics/checklist.py`가 아직 없어 `ModuleNotFoundError: No module named 'core.analytics.checklist'` 발생, 모든 테스트 수집 실패)

- [ ] **Step 3 — 최소 구현: checklist.py 작성**

  `core/analytics/checklist.py`를 새로 만든다. 다른 모듈 함수는 스펙 시그니처대로 import만 한다(재정의 금지). 6축을 분리 표시하며 합산 '매수점수' 필드를 만들지 않는다. 활성축 등급은 양호/보통/주의 서열, 잠금축은 `grade=None` + `locked_reason`. 아래 전체 구현 코드 블록을 그대로 작성한다.

  ```python
  """판단 체크리스트 6축 (순수 로직, §5.8 / §12.4).

  6축: 가치 · 기술 · 리스크 · 심리(활성 4축) + 성장 🔒 · 수급 🔒(잠금 2축).
  각 축은 양호/보통/주의 '서열'과 근거 '사실'만 제공한다.

  🔴 면책 핵심(§12.4):
    1. 6축을 합산한 '매수점수'를 절대 만들지 않는다(=신호화 금지). 축별 분리 표시.
    2. 라벨 정합 — 가격 모멘텀을 '성장'으로, 거래대금을 '수급'으로 라벨하지 않는다.
    3. '추천/매수신호'가 아닌 '체크리스트/판단 보조'이며 단독 판단 근거가 될 수 없다.
    4. 점수는 서열(양호/보통/주의)·백분위로만 표현한다(정밀 착시 회피).

  다른 모듈 함수(verdict_*, ma_alignment, overheating, latest_signals,
  compute_risk_flags)는 시그니처대로 import해 사용한다(여기서 재정의하지 않음).
  """
  from __future__ import annotations

  from typing import Any, Dict, List, Optional

  import pandas as pd

  from core.analytics.indicators import latest_signals
  from core.analytics.labels import verdict_quality, verdict_value
  from core.analytics.price_context import ma_alignment, overheating
  from core.data.flags import compute_risk_flags

  # 잠금 축 사유(점진적 노출·정직 원칙). 후속 단계에서 활성화된다.
  GROWTH_LOCK_REASON = "🔒 성장 — 2단계(DART 재무: EPS·매출 추세) 연동 후 활성화"
  SUPPLY_LOCK_REASON = "🔒 수급 — 4단계(키움 투자자별 순매수) 연동 후 활성화"

  Axis = Dict[str, Any]


  def _grade_from_score(score: Optional[float]) -> Optional[str]:
      """백분위(0~100)를 양호/보통/주의 서열로 변환. 결측은 None."""
      if score is None or pd.isna(score):
          return None
      if score >= 70:
          return "양호"
      if score >= 40:
          return "보통"
      return "주의"


  def _mean_of_present(*values: Optional[float]) -> Optional[float]:
      """결측이 아닌 값들의 평균. 모두 결측이면 None."""
      present = [v for v in values if v is not None and not pd.isna(v)]
      if not present:
          return None
      return sum(present) / len(present)


  def _make_axis(
      axis: str,
      *,
      active: bool,
      grade: Optional[str],
      facts: List[str],
      locked_reason: Optional[str],
  ) -> Axis:
      return {
          "axis": axis,
          "active": active,
          "grade": grade,
          "facts": facts,
          "locked_reason": locked_reason,
      }


  def _value_axis(row: pd.Series) -> Axis:
      """가치 = value_score/quality_score 백분위(저PER·저PBR·ROE)."""
      value_score = row.get("value_score")
      quality_score = row.get("quality_score")
      combined = _mean_of_present(value_score, quality_score)
      grade = _grade_from_score(combined)

      facts: List[str] = []
      # verdict_*는 (label, tone)을 반환. 라벨 정합을 위해 함께 노출.
      v_label, _ = verdict_value(row)
      q_label, _ = verdict_quality(row)
      if value_score is not None and not pd.isna(value_score):
          facts.append(f"가치 백분위 {value_score:.0f} ({v_label})")
      if quality_score is not None and not pd.isna(quality_score):
          facts.append(f"수익성 백분위 {quality_score:.0f} ({q_label})")
      per = row.get("PER")
      pbr = row.get("PBR")
      if per is not None and not pd.isna(per) and per > 0 and \
              pbr is not None and not pd.isna(pbr) and pbr > 0:
          facts.append(f"PER {per:.1f}배 · PBR {pbr:.2f}배")
      if not facts:
          facts.append("가치 지표 데이터 부족")

      return _make_axis("가치", active=True, grade=grade, facts=facts,
                        locked_reason=None)


  def _tech_axis(ohlcv: Optional[pd.DataFrame]) -> Axis:
      """기술 = 이동평균 정배열/역배열/혼조 · RSI 구간 · MACD 시그널 ('사실'만)."""
      alignment = ma_alignment(ohlcv)
      signals = latest_signals(ohlcv) if ohlcv is not None else {}

      facts: List[str] = [f"이동평균 {alignment}"]

      rsi_val = signals.get("rsi")
      rsi_state = signals.get("rsi_state")
      if rsi_val is not None and not pd.isna(rsi_val):
          state = f"({rsi_state})" if rsi_state else ""
          facts.append(f"RSI {rsi_val:.0f}{state}")

      macd_hist = signals.get("macd_hist")
      if macd_hist is not None and not pd.isna(macd_hist):
          trend = "상승" if macd_hist > 0 else "하락"
          facts.append(f"MACD 히스토그램 {trend}")

      # 서열: 정배열+MACD상승=양호 / 역배열=주의 / 그 외=보통 (사실 조합, 합산점수 아님)
      macd_up = macd_hist is not None and not pd.isna(macd_hist) and macd_hist > 0
      if alignment == "정배열" and macd_up:
          grade = "양호"
      elif alignment == "역배열":
          grade = "주의"
      else:
          grade = "보통"

      return _make_axis("기술", active=True, grade=grade, facts=facts,
                        locked_reason=None)


  def _risk_axis(flags: List[str]) -> Axis:
      """리스크 = compute_risk_flags 충족 목록."""
      flags = list(flags) if flags else []
      if not flags:
          return _make_axis(
              "리스크", active=True, grade="양호",
              facts=["특이 위험 신호 없음(최근 정상 거래)"], locked_reason=None,
          )
      # ⛔(거래정지/데이터없음) 포함 시 '주의', 경고(⚠️)만이면 '보통'.
      grade = "주의" if any("⛔" in f for f in flags) else "보통"
      return _make_axis("리스크", active=True, grade=grade, facts=flags,
                        locked_reason=None)


  def _sentiment_axis(ohlcv: Optional[pd.DataFrame]) -> Axis:
      """심리 = §5.9 과열도 프록시 등급(가격·거래량 기반, 게시판 아님)."""
      result = overheating(ohlcv)
      level = result.get("level") if result else None

      # 과열도 등급 → 체크리스트 서열. '과열/높음'은 추격매수 주의 신호이므로 '주의'.
      mapping = {"낮음": "양호", "보통": "보통", "높음": "주의", "과열": "주의"}
      grade = mapping.get(level)

      facts: List[str] = []
      if level:
          facts.append(f"가격·거래량 기반 과열도: {level} (게시판 심리 아님)")
      else:
          facts.append("과열도 산출 불가 — 가격 데이터 부족")
      facts.append("보조지표 · 단독 판단 금지")

      return _make_axis("심리", active=True, grade=grade, facts=facts,
                        locked_reason=None)


  def build_checklist(
      row: pd.Series,
      ohlcv: Optional[pd.DataFrame],
      flags: List[str],
      *,
      scored: pd.DataFrame,
  ) -> List[Axis]:
      """6축 판단 체크리스트를 축별로 분리해 반환.

      활성 4축(가치·기술·리스크·심리) + 잠금 2축(성장·수급).
      🔴 6축을 합산한 '매수점수' 필드는 만들지 않는다(축별 분리 — §12.4).

      Args:
          row: 스코어링된 단일 종목 행(value/quality/income_score, PER/PBR 등 포함).
          ohlcv: 해당 종목 일봉(없으면 기술/심리 축은 데이터 부족 처리).
          flags: compute_risk_flags(ohlcv) 결과(이미 계산된 위험 플래그 목록).
          scored: 전체 스코어 스냅샷(백분위 참조용, 현재 등급은 row 백분위로 충분).
      """
      # scored는 향후 백분위 칩 확장을 위한 슬롯. 현재 등급은 row 백분위로 산출한다.
      _ = scored
      return [
          _value_axis(row),
          _tech_axis(ohlcv),
          _risk_axis(flags),
          _sentiment_axis(ohlcv),
          _make_axis("성장", active=False, grade=None, facts=[],
                     locked_reason=GROWTH_LOCK_REASON),
          _make_axis("수급", active=False, grade=None, facts=[],
                     locked_reason=SUPPLY_LOCK_REASON),
      ]
  ```

- [ ] **Step 4 — 통과 확인**

  Run: `python -m pytest tests/test_checklist.py -v`
  Expected: PASS (16개 테스트 모두 통과 — 6축 순서/활성·잠금, 합산점수 필드 부재, 가치/기술/리스크/심리 등급 산출, 심리=과열도 연동, 잠금 사유 문구)

- [ ] **Step 5 — 커밋**

  `git add core/analytics/checklist.py tests/test_checklist.py`
  `git commit -m "feat: 판단 체크리스트 6축 checklist.py 추가(합산 매수점수 없이 축별 분리)"`


### Task 7: 테마: .streamlit/config.toml + ui_theme.py + app.py 주입

이 태스크는 스펙 §6의 라이트 핀테크 디자인 시스템을 Streamlit에 재현한다. `design-light.html`의 디자인 토큰(`:root` 변수)과 공통 컴포넌트 클래스(카드/뱃지/요약/리스크/표/체크리스트)를 `ui_theme.inject_css()` 한 함수로 모아 `st.markdown(unsafe_allow_html=True)`로 1회 주입한다. CSS 빌더 자체는 순수 문자열 함수이므로 "특정 토큰·클래스·문구 포함"을 단언하는 TDD가 가능하다. 그 후 `.streamlit/config.toml`(테마)과 `app.py`(주입 호출)는 UI라 `streamlit run`으로 톤을 확인하고 커밋한다.

읽을 기존 코드: `app.py`, `.superpowers/brainstorm/108-1780460381/content/design-light.html`(토큰/클래스의 source of truth), `config.py`(import 관습).

스펙 참조: §6 디자인 시스템, 아키텍처 §7(`ui_theme.py` 신규).

#### 함수 1: `ui_theme.build_css()` + `ui_theme.inject_css()` (순수 CSS 빌더 + 주입)

- [ ] 실패하는 테스트 작성. `tests/test_ui_theme.py`를 새로 만들어 `build_css()`가 반환하는 CSS 문자열에 핵심 디자인 토큰·Pretendard 로드·공통 클래스·한국 색이 모두 포함되는지 단언한다. 아래 전체 코드를 그대로 작성한다.

```python
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
```

- [ ] 실패 확인. Run: `python -m pytest tests/test_ui_theme.py -v` · Expected: FAIL (`ui_theme` 모듈이 아직 없어 `ModuleNotFoundError: No module named 'ui_theme'`).

- [ ] 최소 구현. `ui_theme.py`를 프로젝트 루트에 새로 만들어 `build_css()`(순수 CSS 문자열 빌더)와 `inject_css()`(Streamlit 주입)를 구현한다. 토큰 값은 `design-light.html`의 `:root`에서 가져오고, 공통 컴포넌트 클래스(`.asi-card`/`.asi-badge`/`.asi-summary`/`.asi-risk`/`.asi-table`/`.asi-checklist`)를 추가한다. 아래 전체 코드를 그대로 작성한다.

```python
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


def build_css() -> str:
    """주입할 전체 CSS를 <style>로 감싼 문자열로 반환(순수, 부작용 없음)."""
    return (
        "<style>\n"
        + _PRETENDARD_IMPORT
        + "\n"
        + _ROOT_TOKENS
        + _BASE
        + _COMPONENTS
        + "\n</style>"
    )


def inject_css() -> None:
    """라이트 핀테크 디자인 토큰/컴포넌트 CSS를 페이지에 1회 주입한다.

    각 페이지(app.py, pages/*) 상단에서 호출한다.
    st.markdown(unsafe_allow_html=True)로 <style>을 그대로 삽입.
    """
    st.markdown(build_css(), unsafe_allow_html=True)
```

- [ ] 통과 확인. Run: `python -m pytest tests/test_ui_theme.py -v` · Expected: PASS (모든 토큰/클래스/한국 색 단언 통과).

- [ ] 커밋. Run: `git add ui_theme.py tests/test_ui_theme.py` 후 `git commit -m "feat: 라이트 핀테크 디자인 토큰 CSS 빌더(ui_theme.build_css/inject_css) 추가"`.

#### 컴포넌트 2: `.streamlit/config.toml` 테마 (Streamlit 네이티브 테마)

- [ ] `.streamlit/config.toml`을 새로 만들어 스펙 §6의 `[theme]` 값을 그대로 작성한다. Pretendard는 CSS(`ui_theme`)로 로드하므로 여기 `font`은 `"sans serif"`로 둔다. 아래 전체 내용을 그대로 작성한다.

```toml
# ASI 라이트 핀테크 테마 (Streamlit 네이티브 테마)
# 디자인 source of truth: .superpowers/brainstorm/108-1780460381/content/design-light.html
# 세부 토큰/컴포넌트 색은 ui_theme.inject_css()가 CSS로 추가 주입한다.
# Pretendard 웹폰트도 ui_theme의 CSS @import로 로드하므로 여기 font은 sans serif.

[theme]
primaryColor = "#3182f6"
backgroundColor = "#f4f6fa"
secondaryBackgroundColor = "#ffffff"
textColor = "#161b22"
font = "sans serif"
```

- [ ] 검증. Run: `streamlit run app.py` 후 브라우저에서 홈 화면을 연다. 확인할 것: (1) 페이지 배경이 흰색이 아니라 연한 회색(`#f4f6fa`) 톤으로 바뀌었는지, (2) 버튼·링크 등 강조색(primary)이 파란색(`#3182f6`)으로 보이는지, (3) 본문 텍스트가 짙은 잉크색(`#161b22`)으로 보이는지. 콘솔에 config 파싱 에러가 없어야 한다.

- [ ] 커밋. Run: `git add .streamlit/config.toml` 후 `git commit -m "chore: 라이트 핀테크 Streamlit 네이티브 테마(.streamlit/config.toml) 추가"`.

#### 컴포넌트 3: `app.py`에 `inject_css()` 주입 (기존 내용 유지)

- [ ] `app.py` 상단(`st.set_page_config(...)` 직후, `st.title(...)` 이전)에 디자인 CSS 주입 호출을 추가한다. 기존 import/홈 콘텐츠는 그대로 두고, import 줄과 주입 호출만 더한다.

  먼저 import 블록에 `ui_theme`를 추가한다. 기존:

```python
import config
import ui_helpers as ui
```

  를 다음으로 교체한다.

```python
import config
import ui_helpers as ui
import ui_theme
```

- [ ] 이어서 `st.set_page_config(...)` 호출 직후에 주입 호출을 한 줄 추가한다. 기존:

```python
st.set_page_config(page_title="ASI — 한국 주식 분석", page_icon="📈", layout="wide")

st.title("📈 ASI — Antigravity Stock Insight")
```

  를 다음으로 교체한다(중간에 `ui_theme.inject_css()` 한 줄 삽입, 나머지는 동일).

```python
st.set_page_config(page_title="ASI — 한국 주식 분석", page_icon="📈", layout="wide")

# 라이트 핀테크 디자인 토큰/컴포넌트 CSS를 1회 주입(홈도 페이지 톤 일치 — 스펙 §3).
ui_theme.inject_css()

st.title("📈 ASI — Antigravity Stock Insight")
```

- [ ] 검증. Run: `streamlit run app.py` 후 홈 화면을 다시 연다. 확인할 것: (1) 네이티브 테마(이전 스텝)에 더해 본문 폰트가 Pretendard로 바뀌어 한글 자간/굵기 톤이 시안과 비슷해졌는지(폰트가 로드되며 살짝 리플로우가 보일 수 있음), (2) 페이지 상단에 `<style>` 원문이 텍스트로 노출되지 않는지(노출되면 `unsafe_allow_html=True` 누락 신호 — 정상이면 안 보여야 함), (3) 기존 홈 콘텐츠(소개·데이터 마지막 갱신 메트릭·데이터 출처 표·디스클레이머)가 모두 그대로 보이는지. 브라우저 개발자도구 콘솔/네트워크에서 `pretendard.css` 요청이 200으로 로드되는지 확인.

- [ ] 커밋. Run: `git add app.py` 후 `git commit -m "feat: 홈(app.py)에 ui_theme.inject_css() 주입해 디자인 톤 일치"`.


### Task 8: ui_helpers.py 차트 분리 (수정)

기존 `make_price_figure`(4단)를 SRP에 맞게 두 함수로 분리한다(스펙 §5.5). `make_overview_figure(df, title)`는 캔들+20일 이동평균+거래량(2단, 한국색)을 그리고, `make_indicator_figure(df)`는 RSI+MACD(2단)를 그린다. 기존 `make_price_figure`는 `make_overview_figure`로 대체(제거)한다. 두 함수 모두 빈 df를 방어한다. 외부 사용처는 `ui_helpers`/페이지 내부뿐이라 안전하게 교체 가능하다.

순수 plotly 빌더(streamlit 호출 없음·네트워크 없음)이므로, 반환된 `go.Figure`의 trace 수·이름·서브플롯 행 수를 단언하는 단위테스트로 TDD 가능하다.

---

**함수 1: `make_overview_figure(df, title)`**

- [ ] 1. 실패하는 테스트 작성 — `tests/test_ui_helpers.py` 신규 생성. 작은 합성 OHLCV DataFrame을 직접 만들어 주입하고, 반환 figure에 캔들 1개 + SMA20 1개 + 거래량 1개 = 총 3 trace가 있고 한국색(상승 빨강/하락 파랑)이 적용됐는지, 빈 df면 빈 figure(0 trace)인지 단언한다.

```python
"""ui_helpers 차트 빌더 단위테스트.

plotly figure 빌더는 순수(streamlit/네트워크 호출 없음)하므로
작은 합성 DataFrame을 주입해 반환 trace 수·이름·색을 검증한다.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from ui_helpers import make_overview_figure, make_indicator_figure


def _sample_ohlcv() -> pd.DataFrame:
    """SMA/RSI/MACD 컬럼을 포함한 작은 합성 일봉 DataFrame."""
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 102.0, 101.0, 103.0, 105.0],
            "high": [103.0, 104.0, 103.0, 106.0, 107.0],
            "low": [99.0, 100.0, 100.0, 102.0, 104.0],
            "close": [102.0, 101.0, 103.0, 105.0, 106.0],
            "volume": [1000, 1200, 900, 1500, 1300],
            "sma20": [101.0, 101.2, 101.5, 102.0, 103.0],
            "sma60": [100.5, 100.7, 100.9, 101.2, 101.6],
            "sma120": [100.0, 100.1, 100.2, 100.3, 100.4],
            "rsi": [45.0, 40.0, 55.0, 60.0, 58.0],
            "macd": [0.1, 0.2, 0.3, 0.4, 0.5],
            "signal": [0.05, 0.1, 0.2, 0.3, 0.45],
            "hist": [0.05, 0.1, 0.1, 0.1, 0.05],
        },
        index=idx,
    )


def test_make_overview_figure_traces():
    """개요 차트는 캔들 + SMA20 + 거래량 = 3 trace."""
    fig = make_overview_figure(_sample_ohlcv(), "테스트")
    names = [t.name for t in fig.data]
    assert names.count("가격") == 1
    assert "SMA20" in names
    assert any(t.name == "거래량" for t in fig.data)
    # RSI/MACD는 개요 차트에 없어야 한다(지표 차트로 분리)
    assert "RSI" not in names
    assert "MACD" not in names
    assert len(fig.data) == 3


def test_make_overview_figure_korean_colors():
    """한국 관습: 상승=빨강(#e74c3c), 하락=파랑(#3498db)."""
    fig = make_overview_figure(_sample_ohlcv(), "테스트")
    candle = next(t for t in fig.data if t.name == "가격")
    assert candle.increasing.line.color == "#e74c3c"
    assert candle.decreasing.line.color == "#3498db"


def test_make_overview_figure_empty_df():
    """빈 df면 trace 없는 빈 figure를 반환(앱이 죽지 않게)."""
    fig = make_overview_figure(pd.DataFrame(), "테스트")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
```

- [ ] 2. 실패 확인.
  Run: `python -m pytest tests/test_ui_helpers.py::test_make_overview_figure_traces -v`
  Expected: FAIL (`ImportError: cannot import name 'make_overview_figure' from 'ui_helpers'` — 아직 함수가 없음)

- [ ] 3. 최소 구현 — `ui_helpers.py`의 기존 `make_price_figure` 함수 전체(52~107행)를 아래 `make_overview_figure`로 교체한다(제거+대체).

```python
def make_overview_figure(df: pd.DataFrame, title: str) -> go.Figure:
    """개요 차트: 캔들 + 20일 이동평균 + 거래량(2단). 한국 색 유지."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.74, 0.26],
        subplot_titles=("가격 + 20일 이동평균선", "거래량"),
    )

    # 빈 df 방어: trace 없이 빈 figure만 반환(앱이 죽지 않게)
    if df is None or df.empty:
        fig.update_layout(
            title=title,
            height=480,
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=60, b=10),
        )
        return fig

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="가격",
            increasing_line_color="#e74c3c",  # 한국 관습: 상승=빨강
            decreasing_line_color="#3498db",  # 하락=파랑
        ),
        row=1,
        col=1,
    )

    # 간단(A) 모드: 20일선만 노출(60/120선은 중급 영역으로 분리)
    if "sma20" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["sma20"], name="SMA20", line=dict(width=1, color="#f1c40f")),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="거래량", marker_color="#7f8c8d"),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=title,
        height=480,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig
```

- [ ] 4. 통과 확인.
  Run: `python -m pytest tests/test_ui_helpers.py::test_make_overview_figure_traces tests/test_ui_helpers.py::test_make_overview_figure_korean_colors tests/test_ui_helpers.py::test_make_overview_figure_empty_df -v`
  Expected: PASS (3 passed)

- [ ] 5. 커밋.
  `git add ui_helpers.py tests/test_ui_helpers.py`
  `git commit -m "feat: make_overview_figure 추가(가격+20일선+거래량 2단, 한국색)"`

---

**함수 2: `make_indicator_figure(df)`**

- [ ] 6. 실패하는 테스트 작성 — `tests/test_ui_helpers.py`에 아래 테스트 함수들을 파일 끝에 추가한다. 합성 df를 주입해 RSI 1개 + MACD/Signal/Hist 3개 = 총 4 trace인지, 빈 df면 빈 figure인지, RSI 컬럼이 없으면 RSI trace가 빠지는지 단언한다.

```python
def test_make_indicator_figure_traces():
    """지표 차트는 RSI + MACD + Signal + Hist = 4 trace."""
    fig = make_indicator_figure(_sample_ohlcv())
    names = [t.name for t in fig.data]
    assert "RSI" in names
    assert "MACD" in names
    assert "Signal" in names
    assert "Hist" in names
    # 가격/거래량은 지표 차트에 없어야 한다(개요 차트로 분리)
    assert "가격" not in names
    assert "거래량" not in names
    assert len(fig.data) == 4


def test_make_indicator_figure_empty_df():
    """빈 df면 trace 없는 빈 figure를 반환."""
    fig = make_indicator_figure(pd.DataFrame())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_make_indicator_figure_missing_rsi():
    """rsi 컬럼이 없으면 RSI trace는 빠지고 MACD 3종만 남는다."""
    df = _sample_ohlcv().drop(columns=["rsi"])
    fig = make_indicator_figure(df)
    names = [t.name for t in fig.data]
    assert "RSI" not in names
    assert "MACD" in names
    assert len(fig.data) == 3
```

- [ ] 7. 실패 확인.
  Run: `python -m pytest tests/test_ui_helpers.py::test_make_indicator_figure_traces -v`
  Expected: FAIL (`ImportError: cannot import name 'make_indicator_figure' from 'ui_helpers'` — 아직 함수가 없음)

- [ ] 8. 최소 구현 — `ui_helpers.py`의 `make_overview_figure` 함수 정의 바로 아래에 `make_indicator_figure`를 추가한다.

```python
def make_indicator_figure(df: pd.DataFrame) -> go.Figure:
    """기술 지표 차트: RSI(14) + MACD(2단). 중급 펼침 영역에서 사용."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.5, 0.5],
        subplot_titles=("RSI(14)", "MACD"),
    )

    # 빈 df 방어: trace 없이 빈 figure만 반환
    if df is None or df.empty:
        fig.update_layout(
            height=420,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
        )
        return fig

    if "rsi" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#e67e22")),
            row=1,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_color="#e74c3c", row=1, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#3498db", row=1, col=1)

    if "macd" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="#2980b9")),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["signal"], name="Signal", line=dict(color="#e67e22")),
            row=2,
            col=1,
        )
        # 히스토그램: 양수=빨강/음수=파랑(한국 관습)
        colors = ["#e74c3c" if v >= 0 else "#3498db" for v in df["hist"].fillna(0)]
        fig.add_trace(
            go.Bar(x=df.index, y=df["hist"], name="Hist", marker_color=colors),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=420,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
```

- [ ] 9. 통과 확인.
  Run: `python -m pytest tests/test_ui_helpers.py -v`
  Expected: PASS (6 passed — overview 3 + indicator 3)

- [ ] 10. 커밋.
  `git add ui_helpers.py tests/test_ui_helpers.py`
  `git commit -m "feat: make_indicator_figure 추가(RSI·MACD 2단, 중급 펼침용)"`

---

**기존 `make_price_figure` 참조 정리 확인**

- [ ] 11. 프로젝트 전역에서 옛 이름이 남아있지 않은지 확인한다(스펙상 외부 사용처는 `ui_helpers` 내부뿐이지만, app.py 등에 잔존 import가 없는지 안전 검증).
  Run: `python -c "import ui_helpers; assert not hasattr(ui_helpers, 'make_price_figure'), 'make_price_figure가 아직 남아있음'; print('OK: make_price_figure 제거됨')"`
  Expected: PASS (`OK: make_price_figure 제거됨` 출력 — 함수가 `make_overview_figure`로 완전히 대체되었음)

- [ ] 12. 차트 분리가 실제 페이지에서 렌더되는지 수동 확인(종목분석 페이지는 후속 태스크에서 `make_overview_figure`/`make_indicator_figure`를 조립).
  Run: `streamlit run app.py`
  확인: 앱이 import 에러 없이 기동되는지(사이드바·홈 정상 표시). 종목분석 페이지가 아직 없다면 import 단계 무결성만 확인하고, 페이지 구현 태스크 완료 후 개요 차트(가격+20일선+거래량)와 "기술적 지표 자세히" 펼침 안의 RSI·MACD 차트를 다시 확인한다.


### Task 9: ui_components.py (신규)

`ui_components.py`는 **순수 HTML 문자열 빌더**다. 다른 태스크에서 구현되는 순수 함수(`labels.*`)와 페이지(`price_context`/`checklist`)의 산출물(`row`/`badges`/`verdicts`/`axes`/`pos`/`returns` 등)을 인자로 받아, `ui_theme.inject_css`가 주입하는 CSS 클래스명과 동일한 HTML 문자열만 생성한다. 로직·계산·Streamlit/네트워크 호출 없음. 한국 관습(상승=빨강 `#e74c3c`/하락=파랑 `#3498db`)을 색 결정에 유지한다.

**🔴 데이터 계약(실제 스냅샷 진실원천 — 반드시 준수):**
- `row`는 `ui_helpers.load_scored_snapshot()`의 한 행(pandas Series 또는 dict 호환)이다. 컬럼은 **한글**이다: 현재가=`종가`, 시가총액=`시가총액`, 거래대금=`거래대금`. `close`/`market_cap`/`marcap` 같은 영문 컬럼은 **존재하지 않는다**. 밸류 컬럼은 `PER/PBR/EPS/BPS/DIV/DPS/ROE_approx`, 점수 컬럼은 `value_score/quality_score/income_score/score`, 식별 컬럼은 `ticker(6자리 문자열)/name/market("KOSPI"/"KOSDAQ")`.
- 따라서 카드 빌더 `render_stock_card`는 현재가를 `row["종가"]`에서 읽는다.

이 태스크는 **두 페이지(스크리너·종목분석)가 실제로 호출하는 컴포넌트 집합만** 정의한다(YAGNI — 페이지가 쓰지 않는 빌더는 만들지 않는다). 정의 집합과 정확한 시그니처:
- `render_stock_card(row, badges, explain, tier, rank_pct=None) -> str` — 스크리너 카드(Task 10이 호출).
- `render_summary_cards(verdicts) -> str` — 종목분석 한눈에 요약 3카드(Task 11이 호출).
- `render_subscore_bars(row) -> str` — 가치/수익성/배당 3점수 막대(Task 11이 호출).
- `render_risk(flags, caption) -> str` — 리스크 체크(Task 11이 호출).
- `render_checklist(axes) -> str` — 판단 체크리스트 6축(Task 11이 호출).
- `render_week52(pos) -> str` — 52주 범위 바(Task 11이 호출).
- `render_returns(returns) -> str` — 기간 수익률 칩(Task 11이 호출).
- `render_overheat(level) -> str` — 과열도 등급+고지(Task 11이 호출).
- `render_percentile_chips(chips) -> str` — 지표별 시장 백분위 칩(Task 11이 호출).
- `render_glossary_tooltip(term) -> str` — 용어 ⓘ 툴팁(Task 11이 호출).

> 의존: `ui_helpers.fmt_won`, `labels.GLOSSARY`는 **재정의하지 않고 import**해 사용한다. `ui_components`는 인자로 받은 "이미 계산된 값"만 HTML로 감싸므로, 테스트는 합성 dict로 충분하다. 테스트의 `row`는 실제 스냅샷 컬럼명(`종가`/`시가총액` 등)을 그대로 쓴다.

- [ ] **Step 1 — 실패 테스트: `tests/test_ui_components.py` 생성 + `render_stock_card` 테스트.** 카드 HTML이 핵심 클래스/문구를 포함하는지 단언한다. 샘플 row는 실제 한글 컬럼명을 사용한다.

```python
"""ui_components.py 순수 HTML 빌더 테스트.

모든 함수는 '이미 계산된 산출물'(dict/list/스칼라)을 받아 ui_theme가 주입하는
CSS 클래스를 가진 HTML 문자열만 만든다. 네트워크/Streamlit 호출 없음.
row는 실제 스냅샷 컬럼명(한글: 종가/시가총액/거래대금)을 그대로 쓴다.
"""
from __future__ import annotations

import ui_components as uc


def _sample_row():
    # 실제 load_scored_snapshot() 한 행과 동일한 컬럼 계약(한글 컬럼 포함).
    return {
        "ticker": "005930",
        "name": "○○전자",
        "market": "KOSPI",
        "종가": 71800.0,
        "PER": 8.5,
        "PBR": 0.7,
        "ROE_approx": 12.0,
        "DIV": 2.1,
        "DPS": 1500.0,
        "EPS": 8450.0,
        "BPS": 102600.0,
        "시가총액": 4_300_000_000_000.0,
        "거래대금": 50_000_000_000.0,
        "value_score": 88.0,
        "quality_score": 82.0,
        "income_score": 55.0,
        "score": 84.0,
    }


def test_render_stock_card_포함_요소():
    html = uc.render_stock_card(
        _sample_row(),
        badges=["저평가", "우량"],
        explain="PER 8.5배·PBR 0.70배로 저렴, ROE(근사) 12%로 수익성 양호",
        tier="good",
        rank_pct=5.0,
    )
    # 카드 루트 클래스
    assert "scard" in html
    # 종목명/시장 뱃지
    assert "○○전자" in html
    assert "stock-name" in html
    assert "mkt kospi" in html  # 코스피 → kospi 클래스(소문자)
    assert "코스피" in html
    # 현재가(종가 컬럼에서 읽음)
    assert "71,800원" in html
    # 색 뱃지(저평가→b-value, 우량→b-quality)
    assert "badge b-value" in html
    assert "badge b-quality" in html
    assert "저평가" in html and "우량" in html
    # '왜 추천?' 설명 줄
    assert "why" in html
    assert "왜 추천?" in html
    assert "ROE(근사) 12%로 수익성 양호" in html
    # 종합점수 + 상위 X% + 막대
    assert "score-num" in html
    assert "84" in html
    assert "상위 5%" in html
    assert 'style="width:84%"' in html  # 점수 막대 폭
    # 자세히 보기 링크 문구
    assert "자세히 보기" in html


def test_render_stock_card_뱃지없음_랭크없음():
    html = uc.render_stock_card(
        _sample_row(),
        badges=[],
        explain="종합점수 기준 상위 후보",
        tier="warn",
        rank_pct=None,
    )
    # 뱃지 없으면 badge-row 자체를 생략(빈 뱃지 영역 없음)
    assert "badge b-value" not in html
    # rank None → 상위표시 숨김, 카드는 깨지지 않음
    assert "scard" in html
    assert "상위" not in html


def test_render_stock_card_종가없음_대시():
    row = _sample_row()
    row["종가"] = None
    html = uc.render_stock_card(row, badges=[], explain="-", tier="muted", rank_pct=None)
    # 현재가 결측이면 '-' 표기(깨지지 않음)
    assert "scard" in html
    assert ">-<" in html or "-원" not in html  # 가격 영역이 '-'로 안전 처리
```

- [ ] **Step 2 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -v` · `Expected: FAIL (ui_components 모듈/함수 미존재 → ImportError)`.

- [ ] **Step 3 — 최소 구현: `ui_components.py` 생성 + `render_stock_card`.** 색/뱃지 클래스 매핑 헬퍼와 카드 빌더를 작성한다. 현재가는 실제 컬럼 `종가`에서 읽는다.

```python
"""순수 HTML 문자열 빌더 (라이트 핀테크 디자인).

ui_theme.inject_css가 주입하는 CSS 클래스명과 동일한 클래스를 두른 HTML 문자열만
만든다(로직·계산·Streamlit/네트워크 호출 없음).

인자로 받는 row/badges/axes/pos/returns 등은 모두 '이미 계산된 산출물'이다
(core/analytics의 순수 함수가 만든다). row는 load_scored_snapshot()의 한 행과
동일한 컬럼 계약을 따른다 — 현재가=종가, 시가총액=시가총액(모두 한글 컬럼).
색 결정은 한국 관습(상승=빨강/하락=파랑)을 유지한다.
"""
from __future__ import annotations

import html as _html
from typing import Optional, Sequence

from ui_helpers import fmt_won  # 재정의 금지 — import해 사용

# 색 뱃지 라벨 → CSS 클래스 매핑(저평가/우량/고배당)
_BADGE_CLASS = {
    "저평가": ("b-value", "💎"),
    "우량": ("b-quality", "🛡️"),
    "고배당": ("b-div", "💰"),
}

# 점수 tier → 색 클래스(점수 숫자 색). good/warn/muted.
_TIER_CLASS = {"good": "tier-good", "warn": "tier-warn", "muted": "tier-muted"}

# verdict tone → 칩 클래스(v-good/v-strong/v-mid)
_VERDICT_CLASS = {"good": "v-good", "strong": "v-strong", "mid": "v-mid"}


def _esc(text) -> str:
    """HTML 본문에 넣을 문자열 이스케이프(None/숫자 안전)."""
    if text is None:
        return ""
    return _html.escape(str(text))


def _market_class(market) -> str:
    """시장명 → 뱃지 클래스(KOSPI→kospi, KOSDAQ→kosdaq)."""
    m = str(market or "").upper()
    return "kosdaq" if "KOSDAQ" in m else "kospi"


def _market_label(market) -> str:
    return "코스닥" if _market_class(market) == "kosdaq" else "코스피"


def _get(row, key):
    """row(dict/Series)에서 값을 안전하게 꺼낸다. 없으면 None."""
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        try:
            val = row.get(key)
        except AttributeError:
            return None
    return val


def _badge_html(label: str) -> str:
    cls, emoji = _BADGE_CLASS.get(label, ("b-value", ""))
    return (
        f'<span class="badge {cls}">'
        f'<span aria-hidden="true">{emoji}</span> {_esc(label)}</span>'
    )


def _clamp_pct(value) -> float:
    """막대 폭(%)을 0~100으로 제한."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN 방어
        return 0.0
    return max(0.0, min(100.0, v))


def render_stock_card(
    row,
    badges: Sequence[str],
    explain: str,
    tier: str,
    rank_pct: Optional[float] = None,
) -> str:
    """스크리너 결과 카드(§4.3).

    row는 스냅샷 한 행. 현재가는 한글 컬럼 '종가'에서 읽는다(영문 close 없음).
    """
    name = _esc(_get(row, "name"))
    mkt_cls = _market_class(_get(row, "market"))
    mkt_label = _market_label(_get(row, "market"))

    close = _get(row, "종가")  # 실제 스냅샷 컬럼명
    try:
        price_txt = "-" if close is None else f"{float(close):,.0f}원"
        if close is not None and float(close) != float(close):  # NaN
            price_txt = "-"
    except (TypeError, ValueError):
        price_txt = "-"

    score = _get(row, "score")
    try:
        score_txt = "-" if score is None else f"{float(score):.0f}"
        if score is not None and float(score) != float(score):
            score_txt = "-"
    except (TypeError, ValueError):
        score_txt = "-"
    bar_pct = _clamp_pct(score)
    tier_cls = _TIER_CLASS.get(tier, "tier-muted")

    badge_block = ""
    if badges:
        chips = "".join(_badge_html(b) for b in badges)
        badge_block = f'<div class="badge-row">{chips}</div>'

    rank_block = ""
    if rank_pct is not None:
        try:
            rank_block = f'<div class="score-rank">상위 {float(rank_pct):.0f}%</div>'
        except (TypeError, ValueError):
            rank_block = ""

    return (
        '<article class="scard">'
        '<div class="scard-top">'
        '<div class="stock-id">'
        f'<span class="stock-name">{name}</span>'
        f'<span class="mkt {mkt_cls}">{mkt_label}</span>'
        "</div>"
        '<div class="price-wrap">'
        f'<div class="price num">{_esc(price_txt)}</div>'
        "</div>"
        "</div>"
        f"{badge_block}"
        f'<div class="why"><span class="q">왜 추천?</span>{_esc(explain)}</div>'
        '<div class="score-row">'
        '<div class="score-block">'
        f'<div class="score-num num {tier_cls}">{score_txt}<span class="u">점</span></div>'
        f"{rank_block}"
        "</div>"
        '<div class="bar-wrap">'
        '<div class="bar-label"><span class="lv">종합점수</span>'
        f'<span class="num">{score_txt} / 100</span></div>'
        f'<div class="bar"><i style="width:{bar_pct:.0f}%"></i></div>'
        "</div>"
        "</div>"
        '<div class="scard-foot">'
        '<span class="detail-link">자세히 보기 <span class="arr" aria-hidden="true">→</span></span>'
        "</div>"
        "</article>"
    )
```

- [ ] **Step 4 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -v` · `Expected: PASS`.

- [ ] **Step 5 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 스크리너 카드 HTML 빌더 render_stock_card 추가(종가 컬럼·한국색)"`.

- [ ] **Step 6 — 실패 테스트: `render_summary_cards` (한눈에 요약 3카드 + 직관 배지).** 페이지가 묶어 전달하는 verdict dict 리스트를 받아 3개 sumcard와 직관 배지/지표 줄/sub-score 막대를 단언한다. `tests/test_ui_components.py`에 추가.

```python
def _sample_verdicts():
    # Task 11이 labels.verdict_*/value_badge/dividend_won 산출물을 묶어 전달하는 형태.
    return [
        {
            "cat": "가치",
            "emoji": "💎",
            "label": "저평가",
            "tone": "good",
            "word": "싸다",
            "intuition": "시장 평균보다 싼 편",
            "metrics": [("PER", "8.5배"), ("PBR", "0.70배")],
            "score": 88.0,
        },
        {
            "cat": "수익성",
            "emoji": "🛡️",
            "label": "우량",
            "tone": "strong",
            "word": "잘 번다",
            "intuition": None,
            "metrics": [("ROE(근사)", "12%"), ("EPS", "8,450원")],
            "score": 82.0,
        },
        {
            "cat": "배당",
            "emoji": "💰",
            "label": "보통",
            "tone": "mid",
            "word": "2.1%",
            "intuition": "100만원당 연 ~21,000원",
            "metrics": [("배당수익률", "2.1%"), ("주당배당금", "1,500원")],
            "score": 55.0,
        },
    ]


def test_render_summary_cards_3카드_배지_지표():
    html = uc.render_summary_cards(_sample_verdicts())
    # 3개 sumcard
    assert html.count('class="sumcard"') == 3
    # 카테고리 + verdict 칩(tone→클래스 매핑)
    assert "가치" in html and "수익성" in html and "배당" in html
    assert "v-good" in html  # 가치 good
    assert "v-strong" in html  # 수익성 strong
    assert "v-mid" in html  # 배당 mid
    assert "저평가" in html and "우량" in html
    # 큰 평가 단어
    assert "싸다" in html and "잘 번다" in html
    # 직관 배지(있을 때만 노출)
    assert "시장 평균보다 싼 편" in html
    assert "100만원당 연 ~21,000원" in html
    # 지표 줄
    assert "PER" in html and "8.5배" in html
    assert "주당배당금" in html and "1,500원" in html
    # sub-score 막대(score → width%)
    assert 'style="width:88%"' in html
    assert 'style="width:82%"' in html
    assert 'style="width:55%"' in html
    # 직관 None인 카드는 직관 배지 미노출 → 직관 있는 카드 2개만
    assert html.count("intuition") == 2


def test_render_summary_cards_score_none_막대0():
    verdicts = _sample_verdicts()
    verdicts[2]["score"] = None  # 배당 점수 없음
    html = uc.render_summary_cards(verdicts)
    assert 'style="width:0%"' in html  # 결측 점수는 폭 0(깨지지 않음)
```

- [ ] **Step 7 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py::test_render_summary_cards_3카드_배지_지표 -v` · `Expected: FAIL (render_summary_cards 미구현 → AttributeError)`.

- [ ] **Step 8 — 최소 구현: `render_summary_cards`.** sub-score 막대를 카드에 포함한다. `ui_components.py`에 추가.

```python
def _metric_line(key: str, value: str) -> str:
    return (
        '<div class="metric-line">'
        f'<span class="k">{_esc(key)}</span>'
        f'<span class="v num">{_esc(value)}</span>'
        "</div>"
    )


def _score_bar(score) -> str:
    """sub-score(0~100) → 점수 막대. 결측이면 폭 0%."""
    width = _clamp_pct(score)
    return f'<div class="bar"><i style="width:{width:.0f}%"></i></div>'


def _sumcard_html(verdict: dict) -> str:
    tone_cls = _VERDICT_CLASS.get(verdict.get("tone"), "v-mid")
    intuition = verdict.get("intuition")
    intuition_block = ""
    if intuition:
        intuition_block = f'<div class="intuition">{_esc(intuition)}</div>'
    metrics = "".join(_metric_line(k, v) for k, v in verdict.get("metrics", []))
    return (
        '<div class="sumcard">'
        '<div class="head">'
        f'<span class="cat"><span aria-hidden="true">{verdict.get("emoji", "")}</span> '
        f'{_esc(verdict.get("cat"))}</span>'
        f'<span class="verdict {tone_cls}">{_esc(verdict.get("label"))}</span>'
        "</div>"
        f'<div class="word">{_esc(verdict.get("word"))}</div>'
        f"{intuition_block}"
        f"{metrics}"
        f'{_score_bar(verdict.get("score"))}'
        "</div>"
    )


def render_summary_cards(verdicts: Sequence[dict]) -> str:
    """한눈에 요약 3카드(§5.3) + 직관 배지(§5.7) + sub-score 막대.

    verdicts는 페이지가 labels.verdict_*/value_badge/dividend_won 산출물을 묶은
    dict 리스트다(키: cat/emoji/label/tone/word/intuition/metrics/score).
    """
    cards = "".join(_sumcard_html(v) for v in verdicts)
    return f'<div class="sum3">{cards}</div>'
```

- [ ] **Step 9 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_summary_cards -v` · `Expected: PASS`.

- [ ] **Step 10 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 한눈에 요약 3카드 빌더 render_summary_cards 추가(직관 배지·sub-score 막대)"`.

- [ ] **Step 11 — 실패 테스트: `render_subscore_bars` (가치/수익성/배당 3점수 막대).** row의 sub-score 3개를 막대로 그린다. `tests/test_ui_components.py`에 추가.

```python
def test_render_subscore_bars_3막대_폭():
    html = uc.render_subscore_bars(_sample_row())
    # 3개 라벨
    assert "가치" in html and "수익성" in html and "배당" in html
    # value_score 88 → width 88%
    assert 'style="width:88%"' in html
    assert 'style="width:82%"' in html
    assert 'style="width:55%"' in html
    # 막대 컨테이너 클래스
    assert html.count('class="bar"') == 3


def test_render_subscore_bars_NaN_숨김():
    row = _sample_row()
    row["income_score"] = None  # 배당 점수 없음
    html = uc.render_subscore_bars(row)
    # None인 배당 막대는 폭 0으로 안전 처리(깨지지 않음), '-' 표기
    assert 'style="width:0%"' in html
    assert "-" in html
```

- [ ] **Step 12 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py::test_render_subscore_bars_3막대_폭 -v` · `Expected: FAIL (render_subscore_bars 미구현)`.

- [ ] **Step 13 — 최소 구현: `render_subscore_bars`.** `ui_components.py`에 추가.

```python
def _subscore_bar(label: str, score) -> str:
    if score is None:
        val_txt, width = "-", 0.0
    else:
        try:
            width = _clamp_pct(score)
            val_txt = "-" if float(score) != float(score) else f"{float(score):.0f}"
        except (TypeError, ValueError):
            val_txt, width = "-", 0.0
    return (
        '<div class="bar-wrap">'
        '<div class="bar-label">'
        f'<span class="lv">{_esc(label)}</span>'
        f'<span class="num">{val_txt}</span></div>'
        f'<div class="bar"><i style="width:{width:.0f}%"></i></div>'
        "</div>"
    )


def render_subscore_bars(row) -> str:
    """가치/수익성/배당 3점수 막대(§5.7 기본 노출). row의 *_score를 막대로."""
    bars = "".join(
        [
            _subscore_bar("가치", _get(row, "value_score")),
            _subscore_bar("수익성", _get(row, "quality_score")),
            _subscore_bar("배당", _get(row, "income_score")),
        ]
    )
    return f'<div class="subscores">{bars}</div>'
```

- [ ] **Step 14 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_subscore_bars -v` · `Expected: PASS`.

- [ ] **Step 15 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 서브스코어 막대 빌더 render_subscore_bars 추가"`.

- [ ] **Step 16 — 실패 테스트: `render_risk` (리스크 체크 + 미확인 고지 캡션).** `compute_risk_flags` 결과 리스트와 정적 고지 캡션을 받아 렌더. `tests/test_ui_components.py`에 추가.

```python
def test_render_risk_플래그_표시():
    flags = [
        "⚠️ 저유동성 — 20일 평균 거래대금이 기준 미만",
        "⚠️ 고변동성 — 최근 20일 일간 변동성이 큼",
    ]
    caption = "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정"
    html = uc.render_risk(flags, caption)
    # 리스크 카드 컨테이너
    assert "risk-card" in html
    # 각 플래그가 risk-item으로 표시
    assert html.count('class="risk-item"') == 2
    assert "저유동성" in html
    assert "고변동성" in html
    # 미확인 고지 캡션(항상)
    assert "risk-note" in html
    assert "관리종목" in html and "미확인" in html


def test_render_risk_플래그없음_긍정라인():
    caption = "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정"
    html = uc.render_risk([], caption)
    # 플래그 0건 → 긍정 라인
    assert "특이 위험 신호 없음" in html
    assert "rk-dot ok" in html  # 정상(녹색 dot)
    # 고지 캡션은 여전히 노출
    assert "미확인" in html
```

- [ ] **Step 17 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_risk -v` · `Expected: FAIL (render_risk 미구현)`.

- [ ] **Step 18 — 최소 구현: `render_risk`.** 위험 플래그를 항목으로, 0건이면 긍정 라인. 미확인 고지는 항상. `ui_components.py`에 추가.

```python
def _risk_item(flag: str) -> str:
    # 위험 플래그는 주의(amber) dot/state
    return (
        '<div class="risk-item">'
        '<div class="rk-head">'
        '<span class="rk-dot mid" aria-hidden="true"></span>'
        f'<span class="rk-name">{_esc(flag)}</span>'
        '<span class="rk-state mid">주의</span>'
        "</div>"
        "</div>"
    )


def render_risk(flags: Sequence[str], caption: str) -> str:
    """리스크 체크(§5.4). 플래그 0건이면 긍정 라인, 미확인 고지는 항상 노출."""
    if flags:
        items = "".join(_risk_item(f) for f in flags)
    else:
        items = (
            '<div class="risk-item">'
            '<div class="rk-head">'
            '<span class="rk-dot ok" aria-hidden="true"></span>'
            '<span class="rk-name">특이 위험 신호 없음(최근 정상 거래)</span>'
            '<span class="rk-state ok">정상</span>'
            "</div>"
            "</div>"
        )
    note = (
        '<div class="risk-note">'
        '<span class="ic" aria-hidden="true">ℹ️</span>'
        f"<span>{_esc(caption)}</span>"
        "</div>"
    )
    return f'<div class="risk-card"><div class="risk-grid">{items}</div>{note}</div>'
```

- [ ] **Step 19 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_risk -v` · `Expected: PASS`.

- [ ] **Step 20 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 리스크 체크 빌더 render_risk 추가(미확인 고지 상시)"`.

- [ ] **Step 21 — 실패 테스트: `render_checklist` (6축, 잠금 회색).** `checklist.build_checklist`가 만든 축 리스트(키: `axis/active/grade/facts/locked_reason`)를 받아 6축 그리드. 잠금 축은 회색·잠금 사유, **합산 매수점수 없음**. `tests/test_ui_components.py`에 추가.

```python
def _sample_axes():
    # checklist.build_checklist의 실제 산출 스키마와 동일.
    return [
        {"axis": "가치", "active": True, "grade": "양호", "facts": ["가치 백분위 88 (저평가)", "PER 8.5배 · PBR 0.70배"], "locked_reason": None},
        {"axis": "기술", "active": True, "grade": "보통", "facts": ["이동평균 혼조", "RSI 58(중립)"], "locked_reason": None},
        {"axis": "리스크", "active": True, "grade": "주의", "facts": ["⚠️ 저유동성 — 20일 평균 거래대금이 기준 미만"], "locked_reason": None},
        {"axis": "심리", "active": True, "grade": "보통", "facts": ["가격·거래량 기반 과열도: 보통 (게시판 심리 아님)"], "locked_reason": None},
        {"axis": "성장", "active": False, "grade": None, "facts": [], "locked_reason": "🔒 성장 — 2단계(DART 재무: EPS·매출 추세) 연동 후 활성화"},
        {"axis": "수급", "active": False, "grade": None, "facts": [], "locked_reason": "🔒 수급 — 4단계(키움 투자자별 순매수) 연동 후 활성화"},
    ]


def test_render_checklist_6축_잠금():
    html = uc.render_checklist(_sample_axes())
    # 6축 셀
    assert html.count('class="axis-cell') == 6
    # 활성 축 등급
    assert "가치" in html and "양호" in html
    assert "리스크" in html and "주의" in html
    # 잠금 축은 회색 클래스 + 자물쇠 + 사유
    assert "axis-cell locked" in html
    assert "🔒" in html
    assert "DART" in html
    assert "키움" in html
    # 합산 '매수점수' 만들지 않음(면책 §12.4) — 매수점수/총점 문구 부재
    assert "매수점수" not in html
    assert "총점" not in html


def test_render_checklist_등급_색매핑():
    html = uc.render_checklist(_sample_axes())
    # 양호=good, 보통=mid, 주의=warn 색 클래스
    assert "grade-good" in html
    assert "grade-mid" in html
    assert "grade-warn" in html
```

- [ ] **Step 22 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_checklist -v` · `Expected: FAIL (render_checklist 미구현)`.

- [ ] **Step 23 — 최소 구현: `render_checklist`.** 등급→색 매핑, 잠금 축 회색 처리. **합산 점수 미생성**. `ui_components.py`에 추가.

```python
# 체크리스트 축 등급 → 색 클래스
_GRADE_CLASS = {"양호": "grade-good", "보통": "grade-mid", "주의": "grade-warn"}


def _axis_cell(axis: dict) -> str:
    name = _esc(axis.get("axis"))
    if not axis.get("active"):
        reason = _esc(axis.get("locked_reason") or "후속 단계에서 활성화")
        return (
            '<div class="axis-cell locked">'
            f'<div class="axis-name">{name} <span aria-hidden="true">🔒</span></div>'
            f'<div class="axis-lock">{reason}</div>'
            "</div>"
        )
    grade = axis.get("grade") or "보통"
    grade_cls = _GRADE_CLASS.get(grade, "grade-mid")
    facts = "".join(f'<li>{_esc(f)}</li>' for f in axis.get("facts", []))
    return (
        '<div class="axis-cell active">'
        '<div class="axis-head">'
        f'<span class="axis-name">{name}</span>'
        f'<span class="axis-grade {grade_cls}">{_esc(grade)}</span>'
        "</div>"
        f'<ul class="axis-facts">{facts}</ul>'
        "</div>"
    )


def render_checklist(axes: Sequence[dict]) -> str:
    """판단 체크리스트 6축(§5.8). 잠금 축은 회색. 합산 매수점수는 만들지 않는다(면책)."""
    cells = "".join(_axis_cell(a) for a in axes)
    return f'<div class="checklist-grid">{cells}</div>'
```

- [ ] **Step 24 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_checklist -v` · `Expected: PASS`.

- [ ] **Step 25 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 판단 체크리스트 6축 빌더 render_checklist 추가(잠금 회색·합산점수 없음)"`.

- [ ] **Step 26 — 실패 테스트: `render_week52` (52주 범위 바 + 현재가 위치 + 고점낙폭).** `price_context.week52_position` 산출물 dict(`{low,high,pos_pct,drawdown_pct}`)를 받아 위치 바를 그린다. `tests/test_ui_components.py`에 추가.

```python
def test_render_week52_위치_낙폭():
    pos = {"low": 60000.0, "high": 80000.0, "pos_pct": 59.0, "drawdown_pct": -10.3}
    html = uc.render_week52(pos)
    assert "week52" in html
    # 저가/고가 표기
    assert "60,000" in html and "80,000" in html
    # 현재가 위치 마커(59%)
    assert 'style="left:59%"' in html
    # 고점 대비 낙폭
    assert "고점 대비" in html
    assert "-10.3%" in html


def test_render_week52_데이터없음():
    # week52_position이 빈 OHLCV에 반환하는 형태({...: None}) 또는 None
    assert "가격 데이터 없음" in uc.render_week52(None)
    pos_empty = {"low": None, "high": None, "pos_pct": None, "drawdown_pct": None}
    assert "가격 데이터 없음" in uc.render_week52(pos_empty)
```

- [ ] **Step 27 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_week52 -v` · `Expected: FAIL (render_week52 미구현)`.

- [ ] **Step 28 — 최소 구현: `render_week52`.** `week52_position`이 빈 입력에 `{low:None,...}`을 주므로 그 경우도 안내로 처리한다. `ui_components.py`에 추가.

```python
def render_week52(pos: Optional[dict]) -> str:
    """52주 범위 바 + 현재가 위치 + 고점 대비 낙폭(§5.7).

    pos는 price_context.week52_position 산출물(dict). 빈 OHLCV면 값이 모두 None →
    안내 문구로 대체(깨지지 않음).
    """
    if not pos or pos.get("pos_pct") is None:
        return '<div class="week52 empty">가격 데이터 없음</div>'
    low = pos.get("low")
    high = pos.get("high")
    pos_pct = _clamp_pct(pos.get("pos_pct"))
    drawdown = pos.get("drawdown_pct")
    low_txt = "-" if low is None else f"{float(low):,.0f}"
    high_txt = "-" if high is None else f"{float(high):,.0f}"
    dd_txt = "-" if drawdown is None else f"{float(drawdown):.1f}%"
    return (
        '<div class="week52">'
        '<div class="week52-bar">'
        f'<i class="week52-marker" style="left:{pos_pct:.0f}%"></i>'
        "</div>"
        '<div class="week52-ends">'
        f'<span class="lo num">{low_txt}</span>'
        f'<span class="hi num">{high_txt}</span>'
        "</div>"
        f'<div class="week52-dd">고점 대비 <b class="num">{dd_txt}</b></div>'
        "</div>"
    )
```

- [ ] **Step 29 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_week52 -v` · `Expected: PASS`.

- [ ] **Step 30 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 52주 범위 바 빌더 render_week52 추가"`.

- [ ] **Step 31 — 실패 테스트: `render_returns` (기간 수익률 칩).** `price_context.period_returns` 산출물 dict(`{"1개월": 3.2, ...}`)를 받아 부호색 칩. 상승=빨강/하락=파랑(한국 관습). `tests/test_ui_components.py`에 추가.

```python
def test_render_returns_부호색():
    returns = {"1개월": 3.2, "3개월": -5.1, "6개월": None}
    html = uc.render_returns(returns)
    # 라벨 + 값
    assert "1개월" in html and "3개월" in html
    assert "+3.2%" in html
    assert "-5.1%" in html
    # 한국 관습: 상승=빨강(up), 하락=파랑(down)
    assert "ret-up" in html  # +3.2% → up(빨강)
    assert "ret-down" in html  # -5.1% → down(파랑)
    # None 기간은 '-' 표기(중립)
    assert "ret-flat" in html


def test_render_returns_빈입력():
    html = uc.render_returns({})
    assert "returns" in html  # 컨테이너는 존재(깨지지 않음)
```

- [ ] **Step 32 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_returns -v` · `Expected: FAIL (render_returns 미구현)`.

- [ ] **Step 33 — 최소 구현: `render_returns`.** 부호색 클래스(up=빨강/down=파랑). `ui_components.py`에 추가.

```python
def _return_chip(label: str, value) -> str:
    if value is None:
        cls, txt = "ret-flat", "-"
    else:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = None
        if v is None or v != v:  # None/NaN
            cls, txt = "ret-flat", "-"
        elif v > 0:
            cls, txt = "ret-up", f"+{v:.1f}%"  # 상승=빨강(한국 관습)
        elif v < 0:
            cls, txt = "ret-down", f"{v:.1f}%"  # 하락=파랑
        else:
            cls, txt = "ret-flat", "0.0%"
    return (
        f'<span class="ret-chip {cls}">'
        f'<span class="ret-k">{_esc(label)}</span>'
        f'<span class="ret-v num">{txt}</span>'
        "</span>"
    )


def render_returns(returns: dict) -> str:
    """기간 수익률 칩(§5.7). 상승=빨강/하락=파랑(한국 관습)."""
    chips = "".join(_return_chip(k, v) for k, v in (returns or {}).items())
    return f'<div class="returns">{chips}</div>'
```

- [ ] **Step 34 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_returns -v` · `Expected: PASS`.

- [ ] **Step 35 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 기간 수익률 칩 빌더 render_returns 추가(상승 빨강/하락 파랑)"`.

- [ ] **Step 36 — 실패 테스트: `render_overheat` (과열도 등급 + 필수 고지).** `price_context.overheating`의 `level`(낮음/보통/높음/과열, 빈 OHLCV면 None)을 받아 게이지+고지. `tests/test_ui_components.py`에 추가.

```python
def test_render_overheat_등급_고지():
    html = uc.render_overheat("과열")
    assert "overheat" in html
    assert "과열" in html
    # 등급별 색 클래스(과열→hot)
    assert "oh-hot" in html
    # 필수 표기 + 고지(§5.9)
    assert "가격·거래량 기반" in html
    assert "게시판 심리" in html  # '게시판 심리 아님' 명시
    assert "보조지표" in html and "단독 판단" in html


def test_render_overheat_낮음_과_None():
    low = uc.render_overheat("낮음")
    assert "oh-low" in low
    assert "낮음" in low
    assert "단독 판단" in low  # 고지는 항상
    # level None(가격 데이터 없음)도 깨지지 않고 고지 유지
    none_html = uc.render_overheat(None)
    assert "단독 판단" in none_html
```

- [ ] **Step 37 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_overheat -v` · `Expected: FAIL (render_overheat 미구현)`.

- [ ] **Step 38 — 최소 구현: `render_overheat`.** 등급→색 매핑, 필수 고지 상시. `level`이 None이면 '-' 표기. `ui_components.py`에 추가.

```python
# 과열도 등급 → 색 클래스
_OVERHEAT_CLASS = {"낮음": "oh-low", "보통": "oh-mid", "높음": "oh-high", "과열": "oh-hot"}


def render_overheat(level: Optional[str]) -> str:
    """과열도(§5.9) — 가격·거래량 기반 프록시. 필수 고지 상시 동반.

    level은 price_context.overheating(...)["level"](빈 OHLCV면 None).
    """
    cls = _OVERHEAT_CLASS.get(level, "oh-mid")
    level_txt = _esc(level) if level else "-"
    return (
        '<div class="overheat">'
        '<div class="oh-head">'
        '<span class="oh-title">가격·거래량 기반 과열도'
        '<span class="oh-note-inline">(게시판 심리 아님)</span></span>'
        f'<span class="oh-level {cls}">{level_txt}</span>'
        "</div>"
        '<div class="oh-disc">보조지표 · 단독 판단 근거로 사용하지 마세요.</div>'
        "</div>"
    )
```

- [ ] **Step 39 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_overheat -v` · `Expected: PASS`.

- [ ] **Step 40 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 과열도 빌더 render_overheat 추가(게시판 아님·단독판단 금지 고지)"`.

- [ ] **Step 41 — 실패 테스트: `render_percentile_chips` (지표별 시장 백분위 칩).** 페이지가 `scoring.metric_percentile` 산출물을 묶은 리스트(`[(label, pct, hint)]`)를 받아 칩. `tests/test_ui_components.py`에 추가.

```python
def test_render_percentile_chips():
    chips = [
        ("PER", 12.0, "저렴"),
        ("PBR", 20.0, "저렴"),
        ("배당수익률", 75.0, "상위"),
        ("ROE(근사)", None, None),  # 값 없음
    ]
    html = uc.render_percentile_chips(chips)
    assert "pctile-chips" in html
    assert "PER" in html and "하위 12%" in html  # 저PER=하위%가 저렴
    assert "저렴" in html
    assert "배당수익률" in html and "상위 75%" in html
    # None 값은 '-' 처리, 깨지지 않음
    assert "ROE(근사)" in html
    assert "-" in html
```

- [ ] **Step 42 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_percentile_chips -v` · `Expected: FAIL (render_percentile_chips 미구현)`.

- [ ] **Step 43 — 최소 구현: `render_percentile_chips`.** 칩은 `(label, pct, hint)` 3-튜플. hint가 "저렴"(저PER/저PBR)이면 "하위 X%", 아니면 "상위 X%". `ui_components.py`에 추가.

```python
def _pctile_chip(label: str, pct, hint: Optional[str]) -> str:
    if pct is None:
        rank_txt = "-"
    else:
        try:
            p = float(pct)
            rank_txt = "-" if p != p else (
                f"하위 {p:.0f}%" if hint == "저렴" else f"상위 {p:.0f}%"
            )
        except (TypeError, ValueError):
            rank_txt = "-"
    hint_block = f'<span class="pc-hint">{_esc(hint)}</span>' if hint else ""
    return (
        '<span class="pctile-chip">'
        f'<span class="pc-k">{_esc(label)}</span>'
        f'<span class="pc-v num">{rank_txt}</span>'
        f"{hint_block}"
        "</span>"
    )


def render_percentile_chips(chips: Sequence[tuple]) -> str:
    """지표별 시장 백분위 칩(§5.7 중급). (label, pct, hint) 튜플 리스트."""
    body = "".join(_pctile_chip(label, pct, hint) for label, pct, hint in chips)
    return f'<div class="pctile-chips">{body}</div>'
```

- [ ] **Step 44 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_percentile_chips -v` · `Expected: PASS`.

- [ ] **Step 45 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 지표 백분위 칩 빌더 render_percentile_chips 추가"`.

- [ ] **Step 46 — 실패 테스트: `render_glossary_tooltip` (용어 ⓘ 툴팁).** `labels.GLOSSARY`의 정의를 HTML `title=` 속성 툴팁으로 감싼다. `labels.GLOSSARY`는 다른 태스크에서 구현되므로 **import해서 사용**. `tests/test_ui_components.py`에 추가. (테스트는 monkeypatch로 합성 사전 주입.)

```python
def test_render_glossary_tooltip(monkeypatch):
    # labels.GLOSSARY는 다른 태스크가 구현 → 테스트에선 합성 사전 주입
    import core.analytics.labels as labels
    monkeypatch.setattr(
        labels, "GLOSSARY",
        {"PER": "주가수익비율. 주가를 주당순이익(EPS)으로 나눈 값."},
        raising=False,
    )
    html = uc.render_glossary_tooltip("PER")
    # ⓘ 아이콘 + title 속성에 정의 포함
    assert "glossary-term" in html
    assert "PER" in html
    assert 'title="주가수익비율' in html
    assert "ⓘ" in html


def test_render_glossary_tooltip_미등록(monkeypatch):
    import core.analytics.labels as labels
    monkeypatch.setattr(labels, "GLOSSARY", {}, raising=False)
    # 정의 없는 용어는 툴팁 없이 라벨만(깨지지 않음)
    html = uc.render_glossary_tooltip("미등록용어")
    assert "미등록용어" in html
    assert "title=" not in html
```

- [ ] **Step 47 — 실패 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_glossary_tooltip -v` · `Expected: FAIL (render_glossary_tooltip 미구현)`.

- [ ] **Step 48 — 최소 구현: `render_glossary_tooltip`.** `labels.GLOSSARY`를 함수 내부에서 import해 조회(테스트 monkeypatch가 적용되도록 모듈 객체 경유). `ui_components.py`에 추가.

```python
def render_glossary_tooltip(term: str) -> str:
    """용어 ⓘ 툴팁(§5.7). labels.GLOSSARY 정의를 title 속성으로 노출."""
    # labels.GLOSSARY는 다른 모듈에서 구현 — 재정의하지 않고 참조한다.
    from core.analytics import labels

    definition = labels.GLOSSARY.get(term)
    label = _esc(term)
    if not definition:
        return f'<span class="glossary-term">{label}</span>'
    return (
        f'<span class="glossary-term" title="{_esc(definition)}">'
        f'{label} <span class="gl-ic" aria-hidden="true">ⓘ</span></span>'
    )
```

- [ ] **Step 49 — 통과 확인.** `Run: python -m pytest tests/test_ui_components.py -k render_glossary_tooltip -v` · `Expected: PASS`.

- [ ] **Step 50 — 커밋.** `git add ui_components.py tests/test_ui_components.py` · `git commit -m "feat: 용어 툴팁 빌더 render_glossary_tooltip 추가(labels.GLOSSARY 참조)"`.

- [ ] **Step 51 — 전체 회귀 + 커밋.** 모듈 전체 테스트를 한 번에 돌려 10개 빌더가 모두 통과하는지 확인한다. `Run: python -m pytest tests/test_ui_components.py -v` · `Expected: PASS (render_stock_card / render_summary_cards / render_subscore_bars / render_risk / render_checklist / render_week52 / render_returns / render_overheat / render_percentile_chips / render_glossary_tooltip 전부 통과)`. 변경 사항이 없으면 추가 커밋은 생략한다(이미 각 빌더 커밋 완료).


### Task 10: pages/1_📊_스크리너.py (신규)

스펙 §4·§4.5 구현. 이 태스크는 **UI 조립 태스크**다 — 이미 다른 태스크에서 단위테스트된 순수 함수/컴포넌트(`ui_theme.inject_css`, `ui_components.render_stock_card`, `screening.apply_screen`, `screening.PRESETS`, `labels.badges/explain_row/score_tier`, `scoring.percentile_of`)와 캐시 로더(`ui_helpers.load_scored_snapshot`)를 import해서 페이지를 조립한다. 페이지/위젯/세션 흐름은 단위테스트가 어려우므로 검증은 `streamlit run app.py` 후 사이드바에서 직접 확인한다.

이 태스크가 의존하는 함수는 **재정의하지 않고 import만** 한다. 본 페이지가 사용하는 **정확한 시그니처와 데이터 계약**:
- `ui_helpers.load_scored_snapshot() -> DataFrame` — **RangeIndex(0..N-1)**, `ticker`는 **컬럼**(6자리 문자열). index를 티커로 쓰면 안 된다. 결과 한 행은 `row["ticker"]`로 식별한다.
- 결과 컬럼은 **한글**: 현재가=`종가`, 시가총액=`시가총액`, 거래대금=`거래대금`(`close`/`market_cap`/`trading_value` 같은 영문 컬럼은 없음).
- `screening.PRESETS: dict[str, {emoji, label, desc, guide, extra_filter, sort_key}]` — 키는 `"value"/"income"/"stable"/"comprehensive"`. 타일 라벨/이모지/가이드 카피는 `PRESETS`에서 가져온다(하드코딩 금지).
- `screening.apply_screen(scored_df, preset_key, *, market="전체", query="", limit=config.SCREENER_DEFAULT_LIMIT, min_cap=config.MIN_MARKET_CAP, min_value=config.MIN_AVG_TRADING_VALUE) -> DataFrame` — 결과도 위 컬럼 계약을 따른다(`ticker` 컬럼·한글 컬럼).
- `labels.badges(row) -> list[str]`, `labels.explain_row(row) -> str`, `labels.score_tier(score) -> "good"|"warn"|"muted"`.
- `scoring.percentile_of(scored, ticker, column="score") -> float|None` — **`ticker` 컬럼** 기준으로 조회한다.
- `ui_components.render_stock_card(row, badges, explain, tier, rank_pct=None) -> str` — Task 9 정의와 일치(첫 인자는 스냅샷 한 행, 현재가는 빌더가 `row["종가"]`에서 읽음). 페이지는 `rank_pct`에 "상위 X%"용 값(`100 - percentile_of`)을 넘긴다.
- `ui_theme.inject_css() -> None`.

#### 선행 확인 (이 태스크 시작 전 다른 태스크 산출물이 존재하는지 점검)

- [ ] 의존 모듈 존재/시그니처 점검. Run: `python -c "import config, ui_theme, ui_components; from core.analytics import screening, labels; from core.analytics.scoring import percentile_of; import ui_helpers; print(list(screening.PRESETS.keys())); print(hasattr(ui_components,'render_stock_card'), hasattr(ui_theme,'inject_css'), hasattr(labels,'badges'), hasattr(labels,'explain_row'), hasattr(labels,'score_tier')); print(config.SCREENER_DEFAULT_LIMIT, config.MIN_MARKET_CAP, config.MIN_AVG_TRADING_VALUE)"`
  - Expected: PRESETS 키 `['value', 'income', 'stable', 'comprehensive']` 출력 + 모든 `hasattr` True + 상수 3개(`30 30000000000 100000000`) 출력. ImportError/AttributeError면 해당 의존 태스크를 먼저 완료한 뒤 재개.

#### pages 디렉터리 준비

- [ ] `pages/` 디렉터리가 없으면 생성. Run: `python -c "import os; os.makedirs('pages', exist_ok=True); print('ok')"`
  - Expected: `ok` 출력. (Streamlit은 `pages/` 하위 `.py`를 멀티페이지로 자동 인식.)

#### 페이지 파일 작성 (조립)

- [ ] `pages/1_📊_스크리너.py` 생성. 아래 **완전한 코드**를 그대로 작성한다. (필터/정렬/뱃지/설명/백분위는 이미 테스트된 순수 함수에, 카드 HTML은 이미 테스트된 컴포넌트에 위임 — 이 파일에는 비즈니스 로직을 두지 않는다.)

```python
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

# ── 보조 컨트롤 한 줄 (시장 토글 · 개수 · 검색) — §4.1-3 ─────────────────
c_market, c_limit, c_query = st.columns([2, 1, 2])
with c_market:
    market = st.radio(
        "시장",
        options=("전체", "코스피", "코스닥"),
        horizontal=True,
        key="screener_market",
    )
with c_limit:
    limit = st.selectbox(
        "보여줄 개수",
        options=(20, 30, 50),
        index=(20, 30, 50).index(config.SCREENER_DEFAULT_LIMIT),
        key="screener_limit",
    )
with c_query:
    query = st.text_input(
        "종목명 검색",
        value="",
        placeholder="예: 삼성전자",
        key="screener_query",
    )

with st.expander("▸ 고급 설정 (유동성 하한 조정)", expanded=False):
    st.caption(
        "초보자라면 기본값 그대로 두셔도 됩니다. "
        "값을 낮추면 더 작은 회사·거래가 적은 종목까지 포함됩니다."
    )
    min_cap_eok = st.number_input(
        "시가총액 하한 (억원)",
        min_value=0,
        value=int(config.MIN_MARKET_CAP / 1e8),
        step=50,
        key="screener_min_cap",
    )
    min_value_eok = st.number_input(
        "당일 거래대금 하한 (억원) — 스크리너는 당일값 기준입니다",
        min_value=0,
        value=int(config.MIN_AVG_TRADING_VALUE / 1e8),
        step=1,
        key="screener_min_value",
    )

min_cap = float(min_cap_eok) * 1e8
min_value = float(min_value_eok) * 1e8

# ── 스크리닝 실행 (순수 함수에 위임) — §4.2 ───────────────────────────
result = screening.apply_screen(
    scored,
    selected_preset,
    market=market,
    query=query,
    limit=int(limit),
    min_cap=min_cap,
    min_value=min_value,
)

# ── 결과 헤더 + "안정적 대형주" 한계 캡션 (§4.1-4, §4.5, §8) ─────────────
preset_label = screening.PRESETS[selected_preset]["label"]
st.subheader(f"✅ 조건에 맞는 {len(result)}종목 — {preset_label} 순")
if selected_preset == "stable":
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
```

  - 비고: `render_stock_card`는 Task 9 정의대로 `(row, badges, explain, tier, rank_pct)` 시그니처를 받는다(첫 인자가 스냅샷 한 행). 현재가는 빌더가 `row["종가"]`에서, 시장/이름/점수도 row에서 직접 읽으므로 페이지는 키워드 전개를 하지 않는다. 실제 핸드오프는 `st.session_state["selected_ticker"]` 설정 + `st.switch_page("pages/2_🔍_종목분석.py")` 흐름이 충족한다.

#### 정적 검증 (문법/구문)

- [ ] 파일이 파이썬 문법상 유효한지 컴파일만 확인(Streamlit 런타임 없이). Run: `python -m py_compile "pages/1_📊_스크리너.py"`
  - Expected: 출력 없이 종료 코드 0 (구문 오류 없음). ImportError는 발생하지 않음(py_compile은 import를 실행하지 않음).

#### 수동 검증 (streamlit run — UI 조립 태스크 규칙)

- [ ] 앱 실행. Run: `streamlit run app.py`
  - 확인 1 (페이지 등장): 사이드바에 "📊 스크리너" 페이지가 나타나는지. 클릭해 페이지 진입.
  - 확인 2 (헤더): 상단에 "어떤 주식을 찾으세요?" 제목과 보조 카피, 라이트 핀테크 톤(밝은 배경 `#f4f6fa`, 흰 카드, 파란 액센트)이 적용됐는지.
  - 확인 3 (프리셋 전환): 목적 라디오를 💎 저평가 우량주(value) → 💰 배당 잘 주는 주식(income) → 🛡️ 안정적인 대형주(stable) → ⭐ 종합 추천(comprehensive) 순서로 바꿀 때마다 결과 헤더의 종목 수·정렬 기준 문구와 카드 목록(뱃지/왜추천?/점수)이 그에 맞게 바뀌는지. 'stable' 선택 시 한계 캡션(시총 기준만)이 보이는지.
  - 확인 4 (보조 컨트롤): 시장 토글을 '코스피'/'코스닥'으로 바꾸면 결과가 좁혀지는지. 개수를 20/30/50으로 바꾸면 카드 수가 바뀌는지. 검색창에 "삼성" 입력 시 종목명에 '삼성' 포함 종목만 남는지.
  - 확인 5 (색 범례): 카드 목록 위에 "🟢 상위 · 🟠 중간 · ⚪ 하위" 범례가 1회만 보이는지.
  - 확인 6 (카드 내용): 각 카드에 종목명·시장 뱃지·현재가(종가)·색 뱃지·"왜 추천?" 한 줄·종합점수와 "상위 X%"·점수 막대가 모두 정상 표기되는지(현재가가 빈 종목은 '-'로만 표시되고 카드는 깨지지 않는지).
  - 확인 7 (고급 설정): "▸ 고급 설정" expander가 기본 접힘 상태이고, 펼쳐 시총/거래대금 하한을 0으로 낮추면 결과 종목 수가 늘어나는지. 하한을 매우 크게(예: 시총 10000억) 올리면 "조건에 맞는 종목이 없습니다" 안내가 뜨는지.
  - 확인 8 (카드 이동): 임의 카드의 "자세히 보기 →" 버튼을 누르면 종목분석 페이지로 전환되고 해당 종목이 열리는지(`st.session_state["selected_ticker"]`를 기본 선택으로 사용). ※ 종목분석 페이지(Task 11)가 아직 없으면 이 항목만 보류.
  - 종료: 터미널에서 Ctrl+C로 streamlit 중지.

#### 커밋

- [ ] 변경 파일 스테이징 후 커밋. Run:
  - `git add "pages/1_📊_스크리너.py"`
  - `git commit -m "feat: 스크리너 페이지 추가 — 목적 선택형 프리셋 + 카드형 결과(§4·§4.5)"`
  - Expected: 1개 파일이 커밋됨(이 태스크는 순수 로직을 재정의하지 않고 조립만 하므로 테스트 파일 동반 없음 — 의존 순수 함수의 테스트는 각 해당 태스크에 존재).


### Task 11: pages/2_🔍_종목분석.py (신규)

이 태스크는 스펙 §5·§5.7·§5.8·§5.9·§5.10의 종목분석 페이지를 조립한다. 이미 단위테스트된 순수 함수(`labels.*`, `price_context.*`, `checklist.build_checklist`, `scoring.percentile_of`/`metric_percentile`, `flags.compute_risk_flags`)와 HTML 빌더(`ui_components.*`), 테마(`ui_theme.inject_css`), 차트(`ui_helpers.make_overview_figure`/`make_indicator_figure`), 로더(`ui_helpers.load_scored_snapshot`/`load_ohlcv_with_indicators`)를 **호출해 조립**한다. 페이지/테마/차트 조립은 단위테스트 대상이 아니므로 `streamlit run`으로 실제 화면을 열어 검증한다.

**🔴 데이터 계약(반드시 준수):**
- `scored = ui_helpers.load_scored_snapshot()`는 **RangeIndex(0..N-1)**, `ticker`는 **컬럼**(6자리 문자열)이다. **index를 티커로 쓰지 않는다.** 한 종목 row = `scored.loc[scored["ticker"] == t].iloc[0]`(Series).
- 컬럼은 **한글**: 현재가=`종가`, 시가총액=`시가총액`, 거래대금=`거래대금`. `close`/`market_cap`/`trading_value` 영문 컬럼은 없다.
- `scoring.percentile_of(scored, ticker)` / `scoring.metric_percentile(scored, ticker, column, lower_is_better=False)`는 `ticker` '컬럼'을 사용한다. 백분위 칩의 column 인자는 실제 컬럼명(`PER`,`PBR`,`DIV`,`ROE_approx`,`시가총액`,`거래대금`).
- `ohlcv = ui_helpers.load_ohlcv_with_indicators(ticker)`는 date 인덱스 DataFrame(`open,high,low,close,volume,value,change_pct` + `sma5,sma20,sma60,sma120,rsi,macd,signal,hist`). **비어 있을 수 있다**(거래정지/상폐) → 차트·가격맥락·과열도·이탈감시 생략하고 안내.

**고정 시그니처(페이지는 여기에 맞춘다):**
- `labels`: `verdict_value/quality/income(row)->(label,tone)`, `value_badge(row)->str|None`, `dividend_won(row, principal=config.DIVIDEND_PRINCIPAL)->int`(연 배당 환산액 '정수' → 페이지에서 `f"100만원당 연 ~{값:,}원"`으로 포맷), `signal_text(latest_signals, ma_alignment=None)->str`, `indicator_plain(latest_signals)->str`, `earnings_yield(row)->str`.
- `price_context`: `week52_position(ohlcv)->{low,high,pos_pct,drawdown_pct}`, `period_returns(ohlcv,windows)->dict`, `ma_alignment(ohlcv)->str`, `disparity(ohlcv,windows=(20,60))->dict`, `max_drawdown(ohlcv,window)->float|None`, `volume_ratio(ohlcv,window=20)->float|None`, `volatility_grade(ohlcv,window=20)->(grade,daily_pct)`, `overheating(ohlcv)->{level,components}`, `monitor_targets(close,stop=None,target=None)->{status,...}`.
- `checklist.build_checklist(row, ohlcv, flags, *, scored)->list[dict]`(`axis,active,grade,facts,locked_reason`).
- `ui_components`: `render_summary_cards(verdicts)`, `render_week52(pos)`, `render_returns(returns)`, `render_risk(flags, caption)`, `render_checklist(axes)`, `render_overheat(level)`, `render_percentile_chips(chips)`.
- `ui_helpers`: `make_overview_figure(df,title)`, `make_indicator_figure(df)`, `fmt_won(v)`.

- [ ] **Step 1**: `pages/` 디렉터리 존재 보장(없으면 생성). Streamlit 멀티페이지 규약상 `pages/` 하위 파일이 사이드바에 자동 노출된다.

Run: `python -c "import pathlib; pathlib.Path('pages').mkdir(exist_ok=True); print('ok')"`
Expected: `ok` 출력, 루트에 `pages/` 디렉터리 존재.

- [ ] **Step 2**: 종목분석 페이지 파일을 작성한다. 아래 전체 코드를 `pages/2_🔍_종목분석.py`로 저장한다. 모든 섹션(헤더·요약 3카드·가격 맥락·리스크·간단 차트·체크리스트·더 알아보기·과열도·이탈 감시·상세 표)을 고정 시그니처대로 순수 함수를 호출해 조립하며, OHLCV가 비면 차트를 생략하고 안내한다.

```python
"""종목분석 페이지 — 종목 하나를 한눈에 요약·리스크·가격맥락·체크리스트로 본다.

스펙 §5. 순수 로직(labels/price_context/checklist/scoring/flags)과 HTML 빌더
(ui_components), 차트(ui_helpers)를 조립만 한다. 이 파일에는 비즈니스 로직이 없다.
표시 점수는 모두 횡단면 상대 지표이며 매수 신호가 아니다(상시 고지).

데이터 계약: scored는 RangeIndex, ticker는 '컬럼'(6자리). 한 행은 ticker 컬럼으로
조회한다. 현재가/시총/거래대금 컬럼은 한글(종가/시가총액/거래대금)이다.
OHLCV는 비어 있을 수 있다(거래정지/상폐) → 차트·가격맥락·과열도·이탈감시 생략.
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
from core.data.flags import compute_risk_flags
from ui_theme import inject_css

st.set_page_config(page_title="ASI — 종목분석", page_icon="🔍", layout="wide")
inject_css()

# 정적 미확인 고지(리스크 카드용). labels.CAPTIONS가 있으면 그것을 우선 사용.
_RISK_UNKNOWN_CAPTION = labels.CAPTIONS.get(
    "alert_unknown",
    "관리종목·투자경고 '지정' 여부는 아직 미확인 — 다음 단계(시장경보)에서 추가 예정",
)


def _fmt_pct(value) -> str:
    """수익률 등 퍼센트 포맷. None/NaN은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.1f}%"


def _fmt_num(value, suffix: str = "", digits: int = 2) -> str:
    """일반 수치 포맷. None/NaN은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}{suffix}"


# ── 데이터 로드 (스냅샷) ───────────────────────────────────────────────
try:
    scored = ui.load_scored_snapshot()
except Exception as exc:  # 네트워크/스냅샷 실패 → 앱이 죽지 않게 안내
    st.error("종목 데이터를 불러오지 못했습니다. 홈에서 '데이터 새로 받기'를 눌러 주세요.")
    st.caption(f"({type(exc).__name__})")
    st.stop()

if scored is None or scored.empty:
    st.warning("표시할 종목 데이터가 없습니다. 홈에서 데이터를 먼저 갱신해 주세요.")
    st.stop()

# ── 종목 선택 박스 (기본값 = 핸드오프 selected_ticker) ────────────────
# ticker는 '컬럼'이다(index 아님). 티커 → 표시 라벨 매핑.
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

# 한 종목 row = ticker 컬럼으로 조회(Series).
row = scored.loc[scored["ticker"] == selected].iloc[0]
ohlcv = ui.load_ohlcv_with_indicators(selected)
has_price = ohlcv is not None and not ohlcv.empty
name = row.get("name", selected)

# ── 헤더 (종합점수 + 상대 순위 캡션) ──────────────────────────────────
score = row.get("score")
head_l, head_r = st.columns([3, 1])
with head_l:
    market = row.get("market", "")
    st.subheader(f"{name}  ·  {selected}")
    if market:
        st.caption(f"{market}")
with head_r:
    st.metric("종합점수", _fmt_num(score, digits=0))
    pct = percentile_of(scored, selected)
    if pct is not None and not pd.isna(pct):
        st.caption(f"상위 {100 - pct:.0f}% · 상대 순위일 뿐 매수 신호가 아닙니다")

st.divider()

# ── 📌 한눈에 요약 (3카드: verdict + 직관 배지 + sub-score 막대) ────────
st.markdown("#### 📌 한눈에 요약")
v_label, v_tone = labels.verdict_value(row)
q_label, q_tone = labels.verdict_quality(row)
i_label, i_tone = labels.verdict_income(row)

# 배당 환산액(정수) → "100만원당 연 ~N원" 포맷.
div_won = labels.dividend_won(row, principal=config.DIVIDEND_PRINCIPAL)
income_intuition = f"100만원당 연 ~{div_won:,}원" if div_won > 0 else None

verdicts = [
    {
        "cat": "가치 (싼가?)",
        "emoji": "💎",
        "label": v_label,
        "tone": v_tone,
        "word": v_label,
        "intuition": labels.value_badge(row),
        "metrics": [
            ("PER", _fmt_num(row.get("PER"), "배", 1)),
            ("PBR", _fmt_num(row.get("PBR"), "배", 2)),
        ],
        "score": row.get("value_score"),
    },
    {
        "cat": "수익성 (잘 버나?)",
        "emoji": "🛡️",
        "label": q_label,
        "tone": q_tone,
        "word": q_label,
        "intuition": "EPS/BPS 기반 근사치(정확 ROE는 후속 단계)",
        "metrics": [
            ("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 0)),
            ("EPS", ui.fmt_won(row.get("EPS"))),
        ],
        "score": row.get("quality_score"),
    },
    {
        "cat": "배당 (주주환원)",
        "emoji": "💰",
        "label": i_label,
        "tone": i_tone,
        "word": i_label,
        "intuition": income_intuition,
        "metrics": [
            ("배당수익률", _fmt_num(row.get("DIV"), "%", 2)),
            ("주당배당금", ui.fmt_won(row.get("DPS"))),
        ],
        "score": row.get("income_score"),
    },
]
st.markdown(uc.render_summary_cards(verdicts), unsafe_allow_html=True)

# 📊 점수 분해 (가치·수익성·배당 3막대) — §5.7 기본 노출
st.markdown("**📊 점수 분해**")
st.markdown(uc.render_subscore_bars(row), unsafe_allow_html=True)
st.caption("점수 막대는 전체 종목 대비 상대 순위입니다. 매수 신호가 아닙니다.")

# 📖 용어 ⓘ 툴팁 — §5.7 기본 노출. 라벨 옆 ⓘ에 마우스를 올리면 한 줄 정의.
with st.expander("📖 용어 쉽게 보기 (PER·PBR·ROE 등)", expanded=False):
    st.markdown(
        "\n".join(
            f"- {uc.render_glossary_tooltip(term)} {labels.GLOSSARY[term]}"
            for term in labels.GLOSSARY
        ),
        unsafe_allow_html=True,
    )
st.divider()

# ── 📈 가격 맥락 (52주 바 · 기간수익률 칩 · 추세 한 줄) ─────────────────
st.markdown("#### 📈 가격 맥락")
if has_price:
    w52 = price_context.week52_position(ohlcv)
    rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)
    alignment = price_context.ma_alignment(ohlcv)

    st.markdown(uc.render_week52(w52), unsafe_allow_html=True)
    st.markdown(uc.render_returns(rets), unsafe_allow_html=True)
    st.caption(f"추세: {alignment} (SMA20/60/120 배열 기준)")
else:
    st.info("가격 데이터가 없어 가격 맥락을 표시할 수 없습니다(거래정지/상장폐지 가능).")

st.divider()

# ── ⚠️ 리스크 체크 (쉬운말 + 변동성 등급 + 미확인 고지) ───────────────
st.markdown("#### ⚠️ 리스크 체크")
risk_flags = compute_risk_flags(ohlcv if has_price else None)
st.markdown(uc.render_risk(risk_flags, _RISK_UNKNOWN_CAPTION), unsafe_allow_html=True)

if has_price:
    grade, daily_pct = price_context.volatility_grade(ohlcv, window=20)
    if grade is not None:
        st.caption(
            f"변동성 등급: {grade} (최근 일간 변동성 {_fmt_num(daily_pct, '%', 2)})"
        )

st.divider()

# ── 📉 간단 차트 (overview + 신호 한 줄) ──────────────────────────────
st.markdown("#### 📉 가격 차트 (간단)")
if has_price:
    sig = latest_signals(ohlcv)
    alignment = price_context.ma_alignment(ohlcv)
    st.caption(labels.signal_text(sig, ma_alignment=alignment))
    st.plotly_chart(
        ui.make_overview_figure(ohlcv, f"{name} 가격"),
        use_container_width=True,
    )
else:
    st.info("가격 데이터가 없어 차트를 표시할 수 없습니다. 위 리스크 체크를 참고하세요.")

st.divider()

# ── 🧭 판단 체크리스트 (참고용 · 합산 매수점수 없음) ──────────────────
st.markdown("#### 🧭 판단 체크리스트 (참고용)")
axes = build_checklist(row, ohlcv if has_price else None, risk_flags, scored=scored)
st.markdown(uc.render_checklist(axes), unsafe_allow_html=True)
st.caption(
    "체크리스트는 축별 사실을 분리 표시한 판단 보조입니다. 합산 매수점수가 아니며, "
    "단독 판단 근거로 삼지 마세요(투자 권유 아님)."
)
st.divider()

# ── 🔬 더 알아보기 (중급, 기본 접힘) ──────────────────────────────────
with st.expander("🔬 더 알아보기 (중급 심화)", expanded=False):
    st.markdown("**지표별 시장 백분위**")
    # (컬럼명, 표시라벨, lower_is_better, hint). 컬럼은 실제 스냅샷 한글/영문 그대로.
    metric_specs = [
        ("PER", "PER", True, "저렴"),
        ("PBR", "PBR", True, "저렴"),
        ("DIV", "배당수익률", False, "상위"),
        ("ROE_approx", "ROE(근사)", False, "상위"),
        ("시가총액", "시가총액", False, "상위"),
        ("거래대금", "거래대금", False, "상위"),
    ]
    chips = []
    for col, label, lower_better, hint in metric_specs:
        if col not in scored.columns:
            continue
        p = metric_percentile(scored, selected, col, lower_is_better=lower_better)
        chips.append((label, None if p is None or pd.isna(p) else p, hint))
    st.markdown(uc.render_percentile_chips(chips), unsafe_allow_html=True)

    if has_price:
        st.markdown("**가격 심화 지표**")
        disp = price_context.disparity(ohlcv, windows=(20, 60))
        mdd = price_context.max_drawdown(ohlcv, window=config.WEEK52_WINDOW)
        vol_ratio = price_context.volume_ratio(ohlcv, window=20)
        ey = labels.earnings_yield(row)
        rets = price_context.period_returns(ohlcv, windows=config.PERIOD_RETURN_WINDOWS)

        dcols = st.columns(3)
        with dcols[0]:
            st.metric("20일선 이격도", _fmt_num(disp.get(20), "%", 1))
            st.metric("최대낙폭(MDD)", _fmt_num(mdd, "%", 1))
        with dcols[1]:
            st.metric("60일선 이격도", _fmt_num(disp.get(60), "%", 1))
            st.metric("거래량 배수", _fmt_num(vol_ratio, "배", 1))
        with dcols[2]:
            st.metric("이익수익률(1/PER)", ey)
            st.metric("6개월 수익률", _fmt_pct(rets.get("6개월")))
        st.metric("12개월 수익률", _fmt_pct(rets.get("12개월")))

        st.markdown("**기술적 지표 풀이 (RSI·MACD)**")
        sig = latest_signals(ohlcv)
        st.write(labels.indicator_plain(sig))
        st.plotly_chart(ui.make_indicator_figure(ohlcv), use_container_width=True)
    else:
        st.info("가격 데이터가 없어 가격 심화 지표를 표시할 수 없습니다.")

st.divider()

# ── 🌡️ 과열도 (가격·거래량 기반 프록시) ──────────────────────────────
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

# ── 🎯 손절/익절 이탈 감시 (가격만) ───────────────────────────────────
st.markdown("#### 🎯 손절/익절 이탈 감시")
latest_close = float(ohlcv["close"].iloc[-1]) if has_price else None
mcols = st.columns(2)
with mcols[0]:
    stop_in = st.number_input(
        "손절가 (₩)", min_value=0.0, value=0.0, step=100.0, key="monitor_stop"
    )
with mcols[1]:
    target_in = st.number_input(
        "익절가 (₩)", min_value=0.0, value=0.0, step=100.0, key="monitor_target"
    )
if latest_close is None:
    st.info("가격 데이터가 없어 이탈 감시를 할 수 없습니다.")
else:
    stop = stop_in if stop_in > 0 else None
    target = target_in if target_in > 0 else None
    if stop is None and target is None:
        st.caption("손절가/익절가를 입력하면 최신 종가와 비교해 도달·이탈 사실을 알려드립니다.")
    else:
        result = price_context.monitor_targets(latest_close, stop=stop, target=target)
        status = result.get("status", "범위내")
        msg = f"최신 종가 ₩{latest_close:,.0f} — "
        if status == "익절도달":
            st.success(msg + f"입력하신 익절가 ₩{target:,.0f} 도달")
        elif status == "손절이탈":
            st.warning(msg + f"입력하신 손절가 ₩{stop:,.0f} 이탈")
        else:
            st.info(msg + "입력 범위 내")
        st.caption("사실 고지일 뿐 주문·자동매매는 하지 않습니다(투자일임 아님).")

st.divider()

# ── 🔢 상세 숫자 (표) ─────────────────────────────────────────────────
st.markdown("#### 🔢 상세 숫자")
detail_rows = [
    ("PER", _fmt_num(row.get("PER"), "배", 2)),
    ("PBR", _fmt_num(row.get("PBR"), "배", 2)),
    ("ROE(근사)", _fmt_num(row.get("ROE_approx"), "%", 1)),
    ("EPS", ui.fmt_won(row.get("EPS"))),
    ("BPS", ui.fmt_won(row.get("BPS"))),
    ("배당수익률", _fmt_num(row.get("DIV"), "%", 2)),
    ("시가총액", ui.fmt_won(row.get("시가총액"))),
    ("거래대금(당일)", ui.fmt_won(row.get("거래대금"))),
    ("주당배당금(DPS)", ui.fmt_won(row.get("DPS"))),
    ("현재가(종가)", _fmt_num(row.get("종가"), "원", 0)),
]
st.table(pd.DataFrame(detail_rows, columns=["항목", "값"]).set_index("항목"))

st.info(config.DISCLAIMER, icon="⚠️")
```

- [ ] **Step 3**: 파일이 파이썬 문법상 유효한지 정적 확인(Streamlit 런타임 없이). Run: `python -c "import ast; ast.parse(open('pages/2_🔍_종목분석.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok` 출력(문법 오류 없음).

- [ ] **Step 4**: 앱을 띄워 핸드오프 경로를 검증한다. 스크리너에서 "자세히 보기"를 누르면 `selected_ticker`가 세션에 세팅되어 종목분석이 그 종목으로 열린다.

Run: `streamlit run app.py`
Expected: 사이드바에 "🔍 종목분석" 페이지가 보인다. 스크리너 페이지에서 임의 카드의 "자세히 보기 →"를 누르면 종목분석으로 전환되고, 상단 종목 selectbox 기본값이 그 종목으로 선택되어 있으며, 헤더에 종합점수와 "상위 X% · 상대 순위일 뿐 매수 신호가 아닙니다" 캡션이 표시된다.

- [ ] **Step 5**: 직접 선택·요약·가격 맥락·리스크·차트를 검증한다.

Run: (위 `streamlit run app.py` 세션 유지) 사이드바에서 "🔍 종목분석"을 직접 연다.
Expected: 종목 selectbox에서 다른 종목(이름/코드 검색)을 고르면 화면 전체가 갱신된다. "📌 한눈에 요약" 3카드(가치/수익성/배당)에 직관 배지·PER/PBR·ROE·배당수익률(배당 카드 직관은 "100만원당 연 ~N원")·sub-score 막대가 보인다. "📈 가격 맥락"에 52주 바·기간 수익률 칩(상승 빨강/하락 파랑)·추세 한 줄이, "⚠️ 리스크 체크"에 플래그(또는 "특이 위험 신호 없음")·변동성 등급·"관리종목·투자경고 … 미확인" 고지가, "📉 가격 차트"에 신호 한 줄과 캔들+20일선+거래량 차트가 보인다.

- [ ] **Step 6**: 펼침(더 알아보기)·체크리스트·과열도·이탈 감시를 검증한다.

Run: (같은 세션) "🔬 더 알아보기 (중급 심화)" expander를 펼친다. 이어 "🎯 손절/익절 이탈 감시"에 손절가/익절가를 입력한다.
Expected: expander 안에 지표별 시장 백분위 칩(PER/PBR/DIV/ROE/시가총액/거래대금 — 실제 컬럼 기준), 이격도(20·60)·MDD·거래량 배수·이익수익률·6·12개월 수익률, RSI·MACD 말풀이와 보조 지표 차트가 보인다. "🧭 판단 체크리스트"가 축별로 분리 표시되고 합산 매수점수가 없음을 캡션이 고지한다. "🌡️ 과열도"에 등급과 "게시판 심리 아님 · 보조지표 · 단독 판단 금지" 고지가 보인다. 익절가를 종가보다 낮게 입력하면 "익절가 … 도달", 손절가를 종가보다 높게 입력하면 "손절가 … 이탈"이 사실로만 고지된다. 맨 아래 "🔢 상세 숫자" 표(시가총액·거래대금 한글 컬럼 값)와 디스클레이머가 보인다.

- [ ] **Step 7**: OHLCV 빈 경우(거래정지/상폐) 차트 생략 동작을 확인한다. selectbox에서 가격 데이터가 없는 종목을 고른다.

Run: (같은 세션) 거래정지/상폐로 OHLCV가 비는 종목을 선택(없으면 이 스텝은 "해당 없음"으로 기록).
Expected: 가격 차트·가격 맥락·과열도·이탈 감시 섹션이 "가격 데이터가 없어 … 표시할 수 없습니다" 안내로 대체되고 앱이 죽지 않으며, 리스크 체크에 "⛔ 가격 데이터 없음" 플래그가 표시된다. 요약 3카드·상세 표·체크리스트는 스냅샷만으로 정상 렌더된다(체크리스트의 기술·심리 축은 데이터 부족 처리).

- [ ] **Step 8**: 변경 사항을 커밋한다.

Run: `git add "pages/2_🔍_종목분석.py"`
Run: `git commit -m "feat: 종목분석 페이지 추가 — 요약 3카드·가격맥락·리스크·차트·체크리스트·과열도·이탈감시·상세표 조립"`
Expected: 커밋 성공(종목분석 페이지 파일 1개 추가).


### Task 12: tests 백필: test_indicators.py + test_scoring.py(기존부)

이 태스크는 이미 구현된 순수 로직(`core/analytics/indicators.py`, `core/analytics/scoring.py`)에 대한 회귀 테스트를 백필한다. 함수가 이미 존재하므로 TDD 사이클의 핵심은 "테스트 작성 → 통과 확인"이며, 만약 테스트가 기대와 다르게 실패하면 그 자체로 버그 발견을 의미하므로 명시한다. 테스트는 네트워크/pykrx 호출 없이 작은 합성 `pandas.DataFrame`/`Series`만 주입한다. 프로젝트 루트에서 `python -m pytest tests/...`로 실행하여 루트가 `sys.path`에 오르게 한다(`import config`, `from core.analytics.x import ...` 절대 경로 import 사용).

`scoring.py`의 `metric_percentile`는 Task 2에서 구현·테스트되므로 여기서는 다루지 않는다. 본 태스크는 `test_scoring.py`에 `percentile_of` / `compute_scores` / `_lower_is_better`만 추가하며, Task 2의 `metric_percentile` 테스트 함수와 이름이 충돌하지 않도록 별도 함수명을 사용한다(같은 파일이면 함수만 추가).

#### 사전 준비: tests 패키지 디렉터리

- [ ] `tests/` 디렉터리가 import 시 충돌 없게 빈 `tests/__init__.py`를 생성한다(루트가 sys.path에 오르고 `tests`가 패키지가 되도록).

  파일: `tests/__init__.py`
  ```python
  ```
  (빈 파일 — 내용 없음)

---

#### 함수 1: `indicators.rsi` — 순상승=100·순하락=0

- [ ] **(1) 실패하는 테스트 작성**: `tests/test_indicators.py`에 RSI 경계 동작 테스트를 작성한다.

  파일: `tests/test_indicators.py`
  ```python
  """기존 순수 기술지표 로직 백필 회귀 테스트.

  네트워크/pykrx 호출 없이 작은 합성 Series/DataFrame만 주입한다.
  실행: 프로젝트 루트에서 python -m pytest tests/test_indicators.py -v
  """
  from __future__ import annotations

  import numpy as np
  import pandas as pd

  import config
  from core.analytics.indicators import (
      add_indicators,
      latest_signals,
      macd,
      rsi,
      sma,
  )


  def test_rsi_pure_rise_is_100():
      # 단조 상승만 있는 시계열 → 하락분이 0 → RSI는 100으로 수렴
      close = pd.Series([float(x) for x in range(1, 41)])  # 1..40
      out = rsi(close, period=config.RSI_PERIOD)
      # 워밍업 구간(period 미만) 이후 마지막 값은 정확히 100.0
      assert out.iloc[-1] == 100.0


  def test_rsi_pure_fall_is_0():
      # 단조 하락만 있는 시계열 → 상승분이 0 → RSI는 0으로 수렴
      close = pd.Series([float(x) for x in range(40, 0, -1)])  # 40..1
      out = rsi(close, period=config.RSI_PERIOD)
      assert out.iloc[-1] == 0.0
  ```

- [ ] **(2) 실패 확인**: `Run: python -m pytest tests/test_indicators.py::test_rsi_pure_rise_is_100 tests/test_indicators.py::test_rsi_pure_fall_is_0 -v`
  Expected: PASS (구현이 이미 존재하고 정확하면 통과). 만약 FAIL이면 `rsi`의 순상승/순하락 분기(`out.where(avg_loss != 0, 100.0)` / `out.where(avg_gain != 0, 0.0)`)에 회귀 버그가 있는 것이므로 그 사실을 기록하고 멈춰서 원인 조사.

- [ ] **(3) 최소 구현**: `rsi`는 이미 `core/analytics/indicators.py`에 구현되어 있으므로 신규 코드 작성 없음. (이 단계는 백필이므로 구현 변경 불필요 — 테스트가 기존 동작을 고정한다.)

- [ ] **(4) 통과 확인**: `Run: python -m pytest tests/test_indicators.py::test_rsi_pure_rise_is_100 tests/test_indicators.py::test_rsi_pure_fall_is_0 -v`
  Expected: PASS (RSI 순상승=100, 순하락=0 고정).

- [ ] **(5) 커밋**:
  `git add tests/__init__.py tests/test_indicators.py`
  `git commit -m "test: RSI 순상승=100·순하락=0 회귀 테스트 백필"`

---

#### 함수 2: `indicators.sma` — min_periods

- [ ] **(6) 실패하는 테스트 작성**: `tests/test_indicators.py`에 SMA의 `min_periods=window` 동작(워밍업 구간 NaN, 이후 정확한 평균) 테스트를 추가한다.

  파일: `tests/test_indicators.py` (함수 추가)
  ```python
  def test_sma_min_periods_warmup_is_nan():
      # window=3 → 앞의 2개는 NaN, 3번째부터 값 존재
      close = pd.Series([10.0, 20.0, 30.0, 40.0])
      out = sma(close, window=3)
      assert pd.isna(out.iloc[0])
      assert pd.isna(out.iloc[1])
      # (10+20+30)/3 = 20.0
      assert out.iloc[2] == 20.0
      # (20+30+40)/3 = 30.0
      assert out.iloc[3] == 30.0


  def test_sma_window_longer_than_series_all_nan():
      # 데이터가 window보다 짧으면 전부 NaN (min_periods=window)
      close = pd.Series([10.0, 20.0])
      out = sma(close, window=5)
      assert out.isna().all()
  ```

- [ ] **(7) 실패 확인**: `Run: python -m pytest tests/test_indicators.py::test_sma_min_periods_warmup_is_nan tests/test_indicators.py::test_sma_window_longer_than_series_all_nan -v`
  Expected: PASS (`sma`는 `rolling(window=window, min_periods=window).mean()`로 이미 구현됨). FAIL이면 `min_periods` 회귀로 보고 조사.

- [ ] **(8) 최소 구현**: `sma`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(9) 통과 확인**: `Run: python -m pytest tests/test_indicators.py::test_sma_min_periods_warmup_is_nan tests/test_indicators.py::test_sma_window_longer_than_series_all_nan -v`
  Expected: PASS.

- [ ] **(10) 커밋**:
  `git add tests/test_indicators.py`
  `git commit -m "test: SMA min_periods 워밍업 NaN·평균값 회귀 테스트 백필"`

---

#### 함수 3: `indicators.macd` — 부호

- [ ] **(11) 실패하는 테스트 작성**: `tests/test_indicators.py`에 MACD 부호 테스트를 추가한다(지속 상승이면 fast EMA > slow EMA → macd 라인 양수, 지속 하락이면 음수).

  파일: `tests/test_indicators.py` (함수 추가)
  ```python
  def test_macd_sign_positive_on_uptrend():
      # 충분히 긴 단조 상승 → fast EMA가 slow EMA보다 높음 → macd > 0
      close = pd.Series([float(x) for x in range(1, 101)])  # 1..100
      out = macd(
          close,
          fast=config.MACD_FAST,
          slow=config.MACD_SLOW,
          signal=config.MACD_SIGNAL,
      )
      assert out["macd"].iloc[-1] > 0
      # 컬럼 구조 확인
      assert list(out.columns) == ["macd", "signal", "hist"]


  def test_macd_sign_negative_on_downtrend():
      # 단조 하락 → macd < 0
      close = pd.Series([float(x) for x in range(100, 0, -1)])  # 100..1
      out = macd(
          close,
          fast=config.MACD_FAST,
          slow=config.MACD_SLOW,
          signal=config.MACD_SIGNAL,
      )
      assert out["macd"].iloc[-1] < 0


  def test_macd_hist_equals_macd_minus_signal():
      # hist = macd - signal 항등식
      close = pd.Series([float(x) for x in range(1, 101)])
      out = macd(close)
      diff = (out["hist"] - (out["macd"] - out["signal"])).abs()
      assert (diff < 1e-9).all()
  ```

- [ ] **(12) 실패 확인**: `Run: python -m pytest tests/test_indicators.py::test_macd_sign_positive_on_uptrend tests/test_indicators.py::test_macd_sign_negative_on_downtrend tests/test_indicators.py::test_macd_hist_equals_macd_minus_signal -v`
  Expected: PASS (`macd`는 EMA(fast)-EMA(slow), hist=macd-signal로 이미 구현됨). FAIL이면 부호/항등식 회귀로 보고 조사.

- [ ] **(13) 최소 구현**: `macd`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(14) 통과 확인**: `Run: python -m pytest tests/test_indicators.py::test_macd_sign_positive_on_uptrend tests/test_indicators.py::test_macd_sign_negative_on_downtrend tests/test_indicators.py::test_macd_hist_equals_macd_minus_signal -v`
  Expected: PASS.

- [ ] **(15) 커밋**:
  `git add tests/test_indicators.py`
  `git commit -m "test: MACD 부호(상승 양수·하락 음수)·hist 항등식 회귀 테스트 백필"`

---

#### 함수 4: `indicators.latest_signals` — 빈 입력·신호 요약·RSI 상태

- [ ] **(16) 실패하는 테스트 작성**: `tests/test_indicators.py`에 `latest_signals`의 빈 입력(`{}`), 마지막 행 요약(`close`/`above_sma20`/`above_sma60`), RSI 상태 경계(70/30/중립) 테스트를 추가한다. `add_indicators`로 합성 OHLCV에 지표를 붙여 통합 검증한다.

  파일: `tests/test_indicators.py` (함수 추가)
  ```python
  def _make_ohlcv(closes: list[float]) -> pd.DataFrame:
      # 간단한 합성 OHLCV (지표 계산엔 close/volume만 필요)
      n = len(closes)
      idx = pd.date_range("2024-01-01", periods=n, freq="D")
      return pd.DataFrame(
          {
              "open": closes,
              "high": [c + 1 for c in closes],
              "low": [c - 1 for c in closes],
              "close": closes,
              "volume": [1000] * n,
          },
          index=idx,
      )


  def test_latest_signals_empty_returns_empty_dict():
      assert latest_signals(pd.DataFrame()) == {}
      assert latest_signals(None) == {}


  def test_latest_signals_uptrend_above_sma_and_close():
      # 단조 상승 → 마지막 종가가 sma20/sma60 위
      df = add_indicators(_make_ohlcv([float(x) for x in range(1, 131)]))
      sig = latest_signals(df)
      assert sig["close"] == 130.0
      assert sig["above_sma20"] is True
      assert sig["above_sma60"] is True


  def test_latest_signals_rsi_state_overbought():
      # 순상승 → RSI=100 → 과매수(≥70)
      df = add_indicators(_make_ohlcv([float(x) for x in range(1, 41)]))
      sig = latest_signals(df)
      assert sig["rsi_state"] == "과매수(≥70)"


  def test_latest_signals_rsi_state_oversold():
      # 순하락 → RSI=0 → 과매도(≤30)
      df = add_indicators(_make_ohlcv([float(x) for x in range(40, 0, -1)]))
      sig = latest_signals(df)
      assert sig["rsi_state"] == "과매도(≤30)"


  def test_latest_signals_above_sma_none_when_insufficient():
      # 데이터가 sma60 window(60)보다 짧으면 sma60=NaN → above_sma60=None
      df = add_indicators(_make_ohlcv([float(x) for x in range(1, 31)]))  # 30봉
      sig = latest_signals(df)
      assert sig["above_sma60"] is None
      # sma20은 20봉 이상이므로 계산됨
      assert sig["above_sma20"] is True
  ```

- [ ] **(17) 실패 확인**: `Run: python -m pytest tests/test_indicators.py -k latest_signals -v`
  Expected: PASS (`latest_signals`는 빈 입력 `{}`, 마지막 행 요약, RSI 70/30 분기로 이미 구현됨). FAIL이면 신호 요약 회귀로 보고 조사.

- [ ] **(18) 최소 구현**: `latest_signals`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(19) 통과 확인**: `Run: python -m pytest tests/test_indicators.py -v`
  Expected: PASS (test_indicators.py 전체 통과).

- [ ] **(20) 커밋**:
  `git add tests/test_indicators.py`
  `git commit -m "test: latest_signals 빈입력·신호요약·RSI 상태 경계 회귀 테스트 백필"`

---

#### 함수 5: `scoring._lower_is_better` — 0 이하 제외

- [ ] **(21) 실패하는 테스트 작성**: `tests/test_scoring.py`에 `_lower_is_better`가 0 이하(적자/무효)를 제외(NaN)하고, 양수 중 낮을수록 높은 점수(100 - 백분위)를 주는지 테스트를 작성한다.

  파일: `tests/test_scoring.py`
  ```python
  """기존 순수 스코어링 로직 백필 회귀 테스트.

  metric_percentile은 별도 태스크에서 다룬다(여기서는 백필 함수만 추가).
  네트워크/pykrx 호출 없이 작은 합성 DataFrame만 주입한다.
  실행: 프로젝트 루트에서 python -m pytest tests/test_scoring.py -v
  """
  from __future__ import annotations

  import numpy as np
  import pandas as pd

  from core.analytics.scoring import (
      _lower_is_better,
      compute_scores,
      percentile_of,
  )


  def test_lower_is_better_excludes_non_positive():
      # 0과 음수(적자/무효)는 제외되어 NaN
      s = pd.Series([10.0, 20.0, 0.0, -5.0])
      out = _lower_is_better(s)
      assert pd.isna(out.iloc[2])  # 0.0 제외
      assert pd.isna(out.iloc[3])  # -5.0 제외
      # 양수는 점수 존재
      assert pd.notna(out.iloc[0])
      assert pd.notna(out.iloc[1])


  def test_lower_is_better_lower_value_higher_score():
      # 낮을수록 좋음 → 가장 낮은 양수가 가장 높은 점수
      s = pd.Series([1.0, 2.0, 3.0, 4.0])
      out = _lower_is_better(s)
      # 단조 감소: 값이 커질수록 점수는 낮아진다
      assert out.iloc[0] > out.iloc[1] > out.iloc[2] > out.iloc[3]
      # 백분위 평균 형태이므로 모두 0~100 범위
      assert (out.dropna() >= 0).all()
      assert (out.dropna() <= 100).all()
  ```

- [ ] **(22) 실패 확인**: `Run: python -m pytest tests/test_scoring.py::test_lower_is_better_excludes_non_positive tests/test_scoring.py::test_lower_is_better_lower_value_higher_score -v`
  Expected: PASS (`_lower_is_better`는 `s.where(s > 0)`로 0 이하 제외 후 `100 - _pct_rank`로 이미 구현됨). FAIL이면 0 이하 제외 회귀로 보고 조사.

- [ ] **(23) 최소 구현**: `_lower_is_better`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(24) 통과 확인**: `Run: python -m pytest tests/test_scoring.py::test_lower_is_better_excludes_non_positive tests/test_scoring.py::test_lower_is_better_lower_value_higher_score -v`
  Expected: PASS.

- [ ] **(25) 커밋**:
  `git add tests/test_scoring.py`
  `git commit -m "test: _lower_is_better 0이하 제외·역순 점수 회귀 테스트 백필"`

---

#### 함수 6: `scoring.compute_scores` — 컬럼·NaN 처리

- [ ] **(26) 실패하는 테스트 작성**: `tests/test_scoring.py`에 `compute_scores`가 `value_score`/`quality_score`/`income_score`/`score` 컬럼을 추가하고, 적자(PER≤0) 행과 배당 없음(DIV≤0) 행에서 해당 서브스코어가 NaN 처리되며, 입력을 비파괴(원본 컬럼 보존)하는지 테스트를 추가한다.

  파일: `tests/test_scoring.py` (함수 추가)
  ```python
  def _make_snapshot() -> pd.DataFrame:
      # 합성 스냅샷: PER/PBR/ROE_approx/DIV (일부는 적자/무배당)
      return pd.DataFrame(
          {
              "ticker": ["000001", "000002", "000003", "000004"],
              "PER": [5.0, 10.0, -2.0, 20.0],     # 세 번째는 적자
              "PBR": [0.5, 1.0, 2.0, 3.0],
              "ROE_approx": [15.0, 10.0, 5.0, 1.0],
              "DIV": [4.0, 0.0, 2.0, 1.0],        # 두 번째는 무배당
          }
      )


  def test_compute_scores_adds_expected_columns():
      out = compute_scores(_make_snapshot())
      for col in ("value_score", "quality_score", "income_score", "score"):
          assert col in out.columns


  def test_compute_scores_does_not_mutate_input():
      snap = _make_snapshot()
      before = snap.copy(deep=True)
      compute_scores(snap)
      # 원본 비파괴: 컬럼/값 동일
      pd.testing.assert_frame_equal(snap, before)


  def test_compute_scores_value_nan_for_negative_per_only_pbr():
      # 세 번째 종목: PER<0(제외) BUT PBR>0 → value_score는 PBR 단독 평균(NaN 아님)
      out = compute_scores(_make_snapshot())
      v3 = out.loc[out["ticker"] == "000003", "value_score"].iloc[0]
      assert pd.notna(v3)


  def test_compute_scores_income_nan_for_zero_div():
      # 두 번째 종목: DIV=0 → income_score는 NaN
      out = compute_scores(_make_snapshot())
      i2 = out.loc[out["ticker"] == "000002", "income_score"].iloc[0]
      assert pd.isna(i2)


  def test_compute_scores_missing_columns_safe():
      # 일부 컬럼(ROE_approx/DIV)이 없어도 깨지지 않고 score 컬럼이 생성됨
      snap = pd.DataFrame(
          {
              "ticker": ["000001", "000002"],
              "PER": [5.0, 10.0],
              "PBR": [0.5, 1.0],
          }
      )
      out = compute_scores(snap)
      assert "score" in out.columns
      # value_score는 존재(PER/PBR 있음)
      assert pd.notna(out["value_score"]).any()
  ```

- [ ] **(27) 실패 확인**: `Run: python -m pytest tests/test_scoring.py -k compute_scores -v`
  Expected: PASS (`compute_scores`는 4개 서브스코어 컬럼을 `df.copy()` 위에 추가하고, `_lower_is_better`/`DIV>0` 마스킹으로 NaN을 만들며, 누락 컬럼은 `pd.NA` 폴백으로 이미 구현됨). FAIL이면 컬럼/NaN/비파괴 회귀로 보고 조사.

- [ ] **(28) 최소 구현**: `compute_scores`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(29) 통과 확인**: `Run: python -m pytest tests/test_scoring.py -k compute_scores -v`
  Expected: PASS.

- [ ] **(30) 커밋**:
  `git add tests/test_scoring.py`
  `git commit -m "test: compute_scores 컬럼생성·NaN처리·비파괴·누락컬럼 회귀 테스트 백필"`

---

#### 함수 7: `scoring.percentile_of` — 정확성

- [ ] **(31) 실패하는 테스트 작성**: `tests/test_scoring.py`에 `percentile_of`의 정확성(티커 zfill, `(series <= val).mean()*100`, 최댓값=100·최솟값 비율, 없는 컬럼/티커/NaN → None) 테스트를 추가한다. Task 2의 `metric_percentile` 테스트와 충돌하지 않게 `percentile_of` 전용 함수명만 사용한다.

  파일: `tests/test_scoring.py` (함수 추가)
  ```python
  def _scored_for_percentile() -> pd.DataFrame:
      # score 값이 명확한 4종목 (백분위 계산 검증용)
      return pd.DataFrame(
          {
              "ticker": ["000001", "000002", "000003", "000004"],
              "score": [10.0, 20.0, 30.0, 40.0],
          }
      )


  def test_percentile_of_top_is_100():
      scored = _scored_for_percentile()
      # 가장 높은 score(40) 종목 → (모든 값 <= 40) → 100%
      assert percentile_of(scored, "000004") == 100.0


  def test_percentile_of_bottom_ratio():
      scored = _scored_for_percentile()
      # 가장 낮은 score(10) → (1/4 값이 <=10) → 25%
      assert percentile_of(scored, "000001") == 25.0


  def test_percentile_of_zfills_ticker():
      scored = _scored_for_percentile()
      # 정수형/짧은 티커도 zfill(6)로 매칭되어야 함
      assert percentile_of(scored, "1") == 25.0
      assert percentile_of(scored, 1) == 25.0


  def test_percentile_of_custom_column():
      scored = pd.DataFrame(
          {
              "ticker": ["000001", "000002"],
              "value_score": [10.0, 90.0],
          }
      )
      assert percentile_of(scored, "000002", column="value_score") == 100.0


  def test_percentile_of_missing_column_returns_none():
      scored = _scored_for_percentile()
      assert percentile_of(scored, "000001", column="없는컬럼") is None


  def test_percentile_of_unknown_ticker_returns_none():
      scored = _scored_for_percentile()
      assert percentile_of(scored, "999999") is None


  def test_percentile_of_nan_value_returns_none():
      scored = pd.DataFrame(
          {
              "ticker": ["000001", "000002"],
              "score": [np.nan, 50.0],
          }
      )
      # 해당 종목 score가 NaN → None
      assert percentile_of(scored, "000001") is None
  ```

- [ ] **(32) 실패 확인**: `Run: python -m pytest tests/test_scoring.py -k percentile_of -v`
  Expected: PASS (`percentile_of`는 `str(ticker).zfill(6)` 매칭, `(series <= val).mean()*100`, 누락 컬럼/티커/NaN → None으로 이미 구현됨). FAIL이면 백분위 정확성 회귀로 보고 조사.

- [ ] **(33) 최소 구현**: `percentile_of`는 이미 구현되어 있으므로 신규 코드 없음(백필).

- [ ] **(34) 통과 확인**: `Run: python -m pytest tests/test_scoring.py -v`
  Expected: PASS (test_scoring.py 전체 통과).

- [ ] **(35) 커밋**:
  `git add tests/test_scoring.py`
  `git commit -m "test: percentile_of 정확성·zfill·None 경계 회귀 테스트 백필"`

---

#### 최종 검증

- [ ] **(36) 전체 백필 테스트 실행**: `Run: python -m pytest tests/test_indicators.py tests/test_scoring.py -v`
  Expected: PASS (indicators·scoring 기존 로직 회귀 테스트 전부 통과). 하나라도 FAIL이면 해당 함수의 회귀 버그이므로 멈춰서 원인 조사 후 보고.


---

## 완료 기준 (Definition of Done — 스펙 §11)

- [ ] 1. `streamlit run app.py` 후 사이드바에 **스크리너·종목분석** 두 페이지가 보인다.
- [ ] 2. 스크리너에서 목적 4개 전환 시 카드 결과(뱃지·설명·점수)가 바뀐다.
- [ ] 3. 카드 "자세히 보기" → 종목분석으로 해당 종목이 열린다(직접 선택도 가능).
- [ ] 4. 종목분석에 요약 3카드·리스크·간단 차트(+신호, RSI/MACD 접힘)·상세 표가 보인다.
- [ ] 5. 두 페이지에 라이트 핀테크 톤(토큰/카드/뱃지/색)이 적용된다.
- [ ] 6. 신규 순수 로직 단위 테스트가 모두 통과한다(`python -m pytest`).
- [ ] 7. §8 정확성 한계(거래대금=당일·ROE 근사·대형주 한계 등)가 UI에 정직하게 표기된다.
- [ ] 8. 판단 체크리스트(6축, 4활성·2잠금)가 **합산 매수점수 없이** 축별로 분리 표시된다.
- [ ] 9. 과열도는 가격·거래량 기반 프록시로 표기되고 "보조지표·단독 판단 금지" 고지가 동반된다.
- [ ] 10. 손절/익절가 입력 시 종가 대비 도달/이탈 "사실"만 고지된다(주문·자동매매 없음).
