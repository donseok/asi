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
        explain="종합점수 기준 후보",
        tier="warn",
        rank_pct=None,
    )
    # 뱃지 없으면 badge-row 자체를 생략(빈 뱃지 영역 없음)
    assert "badge b-value" not in html
    # rank None → 상위표시(score-rank 요소) 숨김, 카드는 깨지지 않음
    assert "scard" in html
    assert "score-rank" not in html


def test_render_stock_card_종가없음_대시():
    row = _sample_row()
    row["종가"] = None
    html = uc.render_stock_card(row, badges=[], explain="-", tier="muted", rank_pct=None)
    # 현재가 결측이면 '-' 표기(깨지지 않음)
    assert "scard" in html
    assert ">-<" in html or "-원" not in html  # 가격 영역이 '-'로 안전 처리


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
