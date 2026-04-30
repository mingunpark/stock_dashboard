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

    news_text = "\n".join(
        f"- [{n.get('source', '')}] {n.get('title', '')}"
        for n in news if n.get("title")
    ) or "- 수집된 뉴스 없음 (기술지표 기반으로만 분석)"

    return f"""당신은 개인 투자자를 위한 주식 분석 AI입니다. 최신 뉴스와 기술지표를 바탕으로 객관적이고 구체적인 분석을 제공하세요.

종목 정보:
- 종목코드: {ticker} ({name}) | 시장: {market}
- 현재가: {price_display} | 평균단가: {avg_display} | 보유 수량: {qty}주
- RSI(14): {rsi} (30 이하=과매도, 70 이상=과매수)
- 20일 이동평균: {ma20} | 60일 이동평균: {ma60}
- 52주 범위: {week52_lo} ~ {week52_hi}
- 52주 위치: {week52_pos}% (0%=52주 저점, 100%=52주 고점)

최근 뉴스:
{news_text}

위 데이터를 종합 분석하여 반드시 아래 형식으로만 답변하세요. 다른 설명 없이 이 형식만 출력하세요:

[의견: 매수/매도/보유]
근거 1: (뉴스 또는 지표 기반 구체적 근거)
근거 2: (뉴스 또는 지표 기반 구체적 근거)
근거 3: (뉴스 또는 지표 기반 구체적 근거)
주의할 반론: (반대 의견 또는 위험 요소)
※ 투자 결정은 본인 책임입니다."""


# ── 응답 파싱 ─────────────────────────────────────────────────

def parse_response(raw: str) -> dict:
    opinion = None
    reasons = []
    counterpoint = None

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

    return {
        "opinion": opinion,
        "reasons": reasons,
        "counterpoint": counterpoint,
        "raw": raw,
        "error": None,
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
