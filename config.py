"""ASI 전역 설정 (Phase 0a).

상수와 경로만 둔다. 외부 키는 여기 두지 말 것(.env 사용).
"""
from pathlib import Path

# --- 경로 ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- 대상 시장 ---
# ETF/ETN/KONEX는 제외(별도 시장). 보통주 스크리닝 대상만.
MARKETS = ("KOSPI", "KOSDAQ")

# --- 캐시 신선도 ---
# EOD(일봉 마감) 데이터는 하루 단위. 장중 갱신할 필요 없음.
CACHE_TTL_HOURS = 20

# --- 종목 유니버스 제외 규칙 ---
# 우선주는 PER/스코어가 무의미하므로 제외. 스팩/리츠 등도 제외.
EXCLUDE_NAME_KEYWORDS = ("스팩", "기업인수목적", "리츠", "리얼티", "맥쿼리인프라")

# --- 유동성 필터 기본값 (스크리너에서 사용자가 조정 가능) ---
MIN_MARKET_CAP = 30_000_000_000        # 시가총액 하한: 300억
MIN_AVG_TRADING_VALUE = 100_000_000    # 20일 평균 거래대금 하한: 1억/일

# --- 기술적 지표 파라미터 ---
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
SMA_WINDOWS = (5, 20, 60, 120)

# --- 가격 데이터 조회 기본 기간(일) ---
PRICE_LOOKBACK_DAYS = 400

# --- 고지 ---
DISCLAIMER = (
    "본 도구는 공개 데이터를 정리·시각화하는 **분석 보조 도구**이며, "
    "투자 권유나 자문이 아닙니다. 모든 점수는 결정론적 규칙 기반의 상대 지표일 뿐 "
    "수익을 보장하지 않습니다. 투자 판단과 책임은 본인에게 있습니다."
)


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
