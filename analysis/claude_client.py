import os

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
            "raw": None, "error": str(e),
        }
