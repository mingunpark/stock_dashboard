# 주식 분석 대시보드

개인 투자자용 주식 코크핏. 뉴스 + 기술지표 + Gemini AI 분석으로 매수/매도/보유 의견 제시.

**응답 언어: 항상 한국어**

---

## 파일 구조

```
stock dashboard/
├── app.py                  # Streamlit 앱 진입점 — 전체 UI, 화면 라우팅, 캐시 래퍼
├── analysis/
│   └── claude_client.py    # Gemini API 호출·파싱·뉴스 큐레이션 → analysis/CLAUDE.md
├── data/
│   └── fetcher.py          # 시세·뉴스·환율·시장지표 수집 → data/CLAUDE.md
├── portfolio.json          # 보유 종목 + 자본금 (스키마 → PORTFOLIO_SCHEMA.md)
├── watchlist.json          # 관심 종목 목록
├── tests/
│   └── test_core.py        # 순수 로직 단위 테스트 (네트워크·Streamlit 없음)
├── requirements.txt
└── .env                    # GEMINI_API_KEY (gitignore 등록, 절대 커밋 금지)
```

---

## 기술 스택

| 역할 | 선택 |
|------|------|
| 프레임워크 | Streamlit (Python) |
| AI 분석 | Gemini 2.5 Flash (`google-genai`) + tenacity retry |
| 국내 시세 | pykrx |
| 해외 시세·환율 | yfinance |
| 기술지표 | pandas-ta (RSI, MA20, MA60) |
| 뉴스 수집 | Google News RSS (feedparser) |
| 환경 변수 | python-dotenv (`.env`) |

---

## 디자인 원칙

- **단일 세로 스크롤** 레이아웃 (좌우 분할 없음)
- **다크/라이트 모드 대응**: CSS는 `var(--text-color)`, `var(--secondary-background-color)`, `rgba()`만 사용
- 의견 배지: 매수(파랑) / 매도(빨강) / 보유(회색) / 분석 전(노랑) — 모두 `rgba()` 배경

---

## 절대 변경 금지

1. **CSS 색상**: 커스텀 HTML/CSS에 하드코딩 hex 배경색 금지. `var(--text-color)`, `var(--secondary-background-color)`, `rgba()`만 사용
2. **`_esc()` 헬퍼**: 사용자 데이터를 HTML에 삽입할 때 반드시 통과시킬 것. HTML 인젝션·LaTeX 파싱 방지
3. **`_t1()` / `_d130()` 함수**: 날짜를 모듈 로드 시가 아닌 **호출 시**에 계산. 상수로 교체 금지
4. **`portfolio.json` 스키마**: `market`은 `"KR"` 또는 `"US"` 고정. 스키마 상세 → PORTFOLIO_SCHEMA.md
5. **`.env` 파일**: `.gitignore` 등록 유지. 절대 커밋 금지

---

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
