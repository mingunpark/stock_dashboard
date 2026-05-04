import json
import os
import re

from google import genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_MODEL = "gemini-2.5-flash"


# ── 프롬프트 빌드 ─────────────────────────────────────────────

def build_prompt(holding: dict, price_data: dict, news: list[dict]) -> str:
    ticker = holding["ticker"]
    name   = holding.get("name", ticker)
    market = holding["market"]
    qty    = holding["quantity"]

    if market == "KR":
        avg_display = f"{holding['avg_price_krw']:,.0f}원"
    else:
        avg_display = f"${holding['avg_price_usd']:,.2f}"

    price_display = price_data.get("price_display", "N/A")
    rsi        = price_data.get("rsi") or "N/A"
    ma20       = price_data.get("ma20") or "N/A"
    ma60       = price_data.get("ma60") or "N/A"
    week52_pos = price_data.get("week52_pos") or "N/A"
    week52_hi  = price_data.get("week52_high") or "N/A"
    week52_lo  = price_data.get("week52_low") or "N/A"

    ma5         = price_data.get("ma5") or "N/A"
    ma120       = price_data.get("ma120") or "N/A"
    bb          = price_data.get("bollinger") or {}
    macd_d      = price_data.get("macd") or {}
    stoch       = price_data.get("stochastic") or {}
    support     = price_data.get("support") or "N/A"
    resistance  = price_data.get("resistance") or "N/A"
    vol_ratio   = price_data.get("volume_ratio") or "N/A"
    vol_surge   = price_data.get("volume_surge", False)
    trend_dir   = price_data.get("trend_direction", "N/A")
    swing_highs = price_data.get("swing_highs", [])
    swing_lows  = price_data.get("swing_lows", [])
    ohlcv_60    = price_data.get("ohlcv_60", [])

    def _fmt_swings(swings):
        if not swings:
            return "데이터 부족"
        return " → ".join(f"{s['date']}({s['price']:,.0f})" for s in swings)

    _pfmt = ",.0f" if market == "KR" else ",.2f"
    ohlcv_text = "\n".join(
        f"  {c['date']}: O={format(c['open'], _pfmt)} H={format(c['high'], _pfmt)} "
        f"L={format(c['low'], _pfmt)} C={format(c['close'], _pfmt)} V={c['volume']:,}"
        for c in ohlcv_60[-20:]
    ) or "  데이터 없음"

    news_text = "\n".join(
        f"- [{n.get('source', '')}] {n.get('title', '')}"
        for n in news if n.get("title")
    ) or "- 수집된 뉴스 없음 (기술지표 기반으로만 분석)"

    return f"""당신은 개인 투자자를 위한 주식 기술적 분석 AI입니다.
제공된 기술지표, 가격 패턴, 뉴스를 종합하여 객관적이고 구체적인 분석을 제공하세요.

종목 정보:
- 종목코드: {ticker} ({name}) | 시장: {market}
- 현재가: {price_display} | 평균단가: {avg_display} | 보유 수량: {qty}주

기술지표:
- RSI(14): {rsi} (30↓ 과매도 / 70↑ 과매수)
- MA5: {ma5} | MA20: {ma20} | MA60: {ma60} | MA120: {ma120}
- 볼린저밴드: 상단 {bb.get('upper','N/A')} / 중단 {bb.get('middle','N/A')} / 하단 {bb.get('lower','N/A')}
- MACD: {macd_d.get('macd','N/A')} / Signal: {macd_d.get('signal','N/A')} / Histogram: {macd_d.get('histogram','N/A')}
- 스토캐스틱 %K: {stoch.get('k','N/A')} / %D: {stoch.get('d','N/A')}
- 52주 범위: {week52_lo} ~ {week52_hi} | 52주 위치: {week52_pos}%
- 지지선: {support} | 저항선: {resistance}
- 거래량 비율(5일/20일): {vol_ratio}배 | 거래량 급증: {"있음" if vol_surge else "없음"}

추세 및 파동 분석:
- 중기 추세 방향: {trend_dir} (MA20 기울기 기반)
- 스윙 고점 시퀀스 (오래된→최근): {_fmt_swings(swing_highs)}
- 스윙 저점 시퀀스 (오래된→최근): {_fmt_swings(swing_lows)}

최근 20봉 OHLCV:
{ohlcv_text}

최근 뉴스:
{news_text}

위 데이터를 종합 분석하여 반드시 아래 형식으로만 답변하세요.
다른 설명 없이 이 형식만 출력하세요:

[의견: 매수/매도/보유]
근거 1: (RSI/MA/볼린저/MACD/스토캐스틱 등 기술지표 기반 — 수치 명시)
근거 2: (캔들/차트 패턴 기반 — 패턴명과 위치 명시)
근거 3: (다우이론/엘리어트/추세 기반 — 현재 국면 판단)
근거 4: (뉴스/거래량/매크로 기반)
엘리어트 파동 판단: (스윙 고점/저점 시퀀스를 보고 현재 몇 파에 위치하는지 추정. 상승 5파 구조인지 조정 ABC인지 명시. 확신 없으면 "판단 어려움" 기재)
차트 패턴 판단: (최근 20봉 OHLCV에서 감지되는 패턴 명시. 헤드앤숄더/이중천장·바닥/삼각수렴/컵앤핸들/깃발형 등. 없으면 "뚜렷한 패턴 없음" 기재)
다우 이론 국면: (스윙 고저점 흐름으로 현재 추세 국면 판단. "고점·저점 모두 상승 → 상승추세 확인" 형식으로 기재. 분산/축적 국면이면 명시)
주의할 반론: (반대 신호 또는 위험 요소)
※ 투자 결정은 본인 책임입니다."""


# ── 응답 파싱 ─────────────────────────────────────────────────

def parse_response(raw: str) -> dict:
    opinion       = None
    reasons       = []
    counterpoint  = None
    elliott_wave  = None
    chart_pattern = None
    dow_phase     = None

    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[의견:"):
            inner = line.strip("[]").replace("의견:", "").strip()
            if "매수" in inner:   opinion = "매수"
            elif "매도" in inner: opinion = "매도"
            elif "보유" in inner: opinion = "보유"
        elif line.startswith("근거") and ":" in line:
            _, body = line.split(":", 1)
            if body.strip():
                reasons.append(body.strip())
        elif line.startswith("주의할 반론") and ":" in line:
            _, body = line.split(":", 1)
            counterpoint = body.strip()
        elif line.startswith("엘리어트 파동 판단") and ":" in line:
            _, body = line.split(":", 1)
            elliott_wave = body.strip()
        elif line.startswith("차트 패턴 판단") and ":" in line:
            _, body = line.split(":", 1)
            chart_pattern = body.strip()
        elif line.startswith("다우 이론 국면") and ":" in line:
            _, body = line.split(":", 1)
            dow_phase = body.strip()

    return {
        "opinion":       opinion,
        "reasons":       reasons,
        "counterpoint":  counterpoint,
        "elliott_wave":  elliott_wave,
        "chart_pattern": chart_pattern,
        "dow_phase":     dow_phase,
        "raw":           raw,
        "error":         None,
    }


# ── Gemini API 호출 (tenacity retry) ─────────────────────────

@retry(
    stop=stop_after_attempt(5),
    # 429/503 모두 대기 후 재시도: 첫 실패 15s, 이후 최대 60s
    wait=wait_exponential(multiplier=2, min=15, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_gemini(prompt: str) -> str:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(model=_MODEL, contents=prompt)
    return response.text


# ── 매크로 뉴스 큐레이션 ─────────────────────────────────────

def _parse_curated_news(raw: str) -> list[dict]:
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    text = m.group(1) if m else raw.strip()
    try:
        items = json.loads(text)
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)][:6]
    except Exception:
        pass
    return []


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=5, max=15),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_gemini_curate(prompt: str) -> str:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(model=_MODEL, contents=prompt)
    return response.text


def curate_macro_news(raw_items: list[dict]) -> list[dict]:
    """국내외 뉴스 원본을 Gemini로 큐레이션: 증시 중요 뉴스 6개 선별 + 요약."""
    if not os.environ.get("GEMINI_API_KEY") or not raw_items:
        return []

    news_list = "\n".join(
        f"[{i+1}] [{item.get('source','')}] {item['title']} | LINK:{item.get('link','')}"
        for i, item in enumerate(raw_items)
        if item.get("title")
    )

    prompt = f"""아래는 최근 수집된 국내외 경제·증시 뉴스 목록입니다.
주식 투자자 관점에서 증시에 가장 중요한 뉴스 6개를 선별하고, JSON 배열 형식으로만 출력하세요.
다른 텍스트나 설명은 절대 포함하지 마세요. LINK는 목록에서 그대로 복사하세요.

뉴스 목록:
{news_list}

출력 형식 (JSON 배열만):
[
  {{
    "title": "뉴스 제목 (한국어. 원문이 영어면 번역)",
    "summary": "2-3문장 요약. 이 뉴스가 증시에 어떤 영향을 미치는지 포함.",
    "source": "출처명",
    "link": "원문 링크 (목록의 LINK: 이후 값 그대로)"
  }}
]"""

    try:
        raw = _call_gemini_curate(prompt)
        return _parse_curated_news(raw)
    except Exception:
        return []


def analyze_stock(holding: dict, price_data: dict, news: list[dict]) -> dict:
    if price_data.get("error"):
        return {
            "opinion": None, "reasons": [], "counterpoint": None,
            "raw": None, "error": f"시세 오류: {price_data['error']}",
        }
    if not os.environ.get("GEMINI_API_KEY"):
        return {
            "opinion": None, "reasons": [], "counterpoint": None,
            "raw": None, "error": "GEMINI_API_KEY 미설정 (.env 확인)",
        }
    try:
        prompt = build_prompt(holding, price_data, news)
        raw    = _call_gemini(prompt)
        return parse_response(raw)
    except Exception as e:
        return {
            "opinion": None, "reasons": [], "counterpoint": None,
            "raw": None, "error": _friendly_error(e),
        }


def _friendly_error(e: Exception) -> str:
    s = str(e)
    if "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower():
        return "Gemini API 무료 할당량 초과 — 내일 재시도하거나 유료 플랜으로 업그레이드하세요 (일 20회 제한)"
    if "503" in s or "UNAVAILABLE" in s:
        return "Gemini API 일시 과부하 — 잠시 후 새로고침하세요 (503)"
    if "500" in s or "INTERNAL" in s:
        return "Gemini API 내부 오류 — 잠시 후 재시도하세요 (500)"
    if "401" in s or "API_KEY" in s or "UNAUTHENTICATED" in s:
        return "Gemini API 키 인증 실패 — .env의 GEMINI_API_KEY를 확인하세요"
    return f"AI 분석 오류: {s[:120]}"
