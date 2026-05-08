# analysis/ — Gemini AI 분석 모듈

## 파일

- `claude_client.py`: Gemini API 호출·응답 파싱·매크로 뉴스 큐레이션 전담

---

## AI 스택

| 항목 | 내용 |
|------|------|
| 모델 | Gemini 2.5 Flash (`gemini-2.5-flash-preview-05-20`) |
| 클라이언트 | `google-genai` SDK |
| 재시도 | `tenacity` — `retry`, `wait_exponential`, `stop_after_attempt` |
| API 키 | `.env` → `GEMINI_API_KEY` (dotenv 로드) |

---

## 주요 함수 역할

### `analyze_stock(holding, price_data, news, financials)`
- 단일 종목 매수/매도/보유 의견 생성
- 반환 구조: `{"opinion": "매수"|"매도"|"보유", "reasons": [...], "counterpoint": "...", ...}`
- 응답은 JSON 파싱 후 반환. 파싱 실패 시 `{"error": "..."}` 반환

### `curate_macro_news(kr_news, us_news)`
- 국내 20건 + 해외 20건 뉴스 → Gemini에 전달
- 반환: 6개 선별 기사 (한국어 요약 + 원문 링크)
- 반환 구조: `[{"title": "...", "summary": "...", "link": "...", "source": "..."}, ...]`

---

## Gemini 에러 처리 규칙

사용자에게 **한국어로** 에러 안내. 에러 코드별 메시지:

| 코드 | 표시 메시지 |
|------|------------|
| 429 | "API 요청 한도 초과 (무료 플랜 20회/일). 내일 다시 시도하거나 유료 플랜으로 전환하세요." |
| 503 | "Gemini 서버가 일시적으로 응답하지 않습니다. 잠시 후 재시도하세요." |
| 500 | "Gemini 내부 오류입니다. 잠시 후 재시도하세요." |
| 401 | "API 키가 유효하지 않습니다. `.env`의 `GEMINI_API_KEY`를 확인하세요." |

---

## HTML/LaTeX 이스케이프 필수

- Gemini 응답 텍스트를 Streamlit HTML에 삽입할 때 **반드시** `_esc()` 통과
- `$` 기호 → `&#36;` (LaTeX 파싱 방지)
- `_esc()`는 `app.py`에 정의됨. 이 모듈에서 직접 HTML 렌더링 시 동일 처리 필요

---

## 주의사항

- `tenacity` 재시도는 **네트워크/일시적 오류**에만 적용. 401·429는 재시도하지 않음
- 응답 JSON이 마크다운 코드블록으로 감싸진 경우 (`\`\`\`json ... \`\`\``) 제거 후 파싱
- Gemini 호출은 `app.py`의 `@st.cache_data(ttl=14400)` 래퍼(`analyze_cached`)를 통해서만 호출됨. 이 모듈에서 직접 캐싱 금지
