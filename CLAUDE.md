# 주식 분석 대시보드

## 프로젝트 개요
개인 투자자(본인)가 보유한 종목의 매수/매도/보유 의견 제시 및 신규 종목 추천.
뉴스 + 기술지표 + AI 분석을 조합한 개인용 주식 코크핏.

---

## 확정된 기술 스택

| 역할 | 선택 |
|------|------|
| 프레임워크 | Streamlit (Python) |
| AI 분석 | Gemini 2.5 Flash (`google-genai`) |
| AI 재시도 | tenacity (retry, wait_exponential) |
| 국내 시세 | pykrx |
| 해외 시세·환율 | yfinance |
| 기술지표 | pandas-ta (RSI, MA20, MA60) |
| 뉴스 수집 | Google News RSS (feedparser + requests) |
| 환경 변수 | python-dotenv (`.env` 파일, `.gitignore` 등록) |
| 배포 | 미결정 (로컬 실행 중) |

---

## 디자인 방향

- **단일 세로 스크롤** 레이아웃 (좌우 분할 없음)
- **다크/라이트 모드 완전 대응**: CSS는 `var(--text-color)`, `var(--secondary-background-color)`, `rgba()` 반투명 배경만 사용. 하드코딩 hex 색상 금지
- **4개 화면**: 대시보드 / AI 브리핑 피드 / 관심 종목 / 설정
- 숫자·배지 폰트: 고정폭 계열 (`font-variant-numeric: tabular-nums`)
- 의견 배지: 매수(파랑) / 매도(빨강) / 보유(회색) / 분석 전(노랑) — 모두 `rgba()` 배경

---

## 파일 구조

```
stock dashboard/
├── app.py                  # Streamlit 앱 진입점 (전체 UI)
├── analysis/
│   └── claude_client.py    # Gemini API 호출·파싱·뉴스 큐레이션
├── data/
│   └── fetcher.py          # 시세·뉴스·환율·시장지표 수집
├── portfolio.json          # 보유 종목 + 자본금 (사용자가 설정 화면에서 편집)
├── watchlist.json          # 관심 종목 목록
├── requirements.txt
└── .env                    # GEMINI_API_KEY (gitignore 등록)
```

---

## 데이터 소스

| 데이터 | 소스 | 비고 |
|--------|------|------|
| 국내 OHLCV | pykrx | T-1 딜레이, 130일치 |
| 해외 OHLCV | yfinance (1y) | |
| 국내 종목 뉴스 | Google News RSS | 종목명 + "주식" 검색 |
| 해외 종목 뉴스 | yfinance `.news` | |
| 매크로 뉴스 원본 | Google News RSS | 국내·해외 각 20건 수집 |
| 매크로 뉴스 큐레이션 | Gemini API | 6개 선별 + 한국어 요약 + 링크 |
| 시장 지표 8개 | yfinance | S&P500/NASDAQ/코스피/VIX/미국10Y/금/WTI/USD/KRW |
| 환율 (USD/KRW) | yfinance `KRW=X` | 폴백: 1400.0 |

---

## portfolio.json 구조

```json
{
  "capital_krw": 10000000,
  "target_return_pct": 15.0,
  "cash_krw": 5000000,
  "holdings": [
    {
      "ticker": "005930",
      "market": "KR",
      "name": "삼성전자",
      "sector": "반도체",
      "quantity": 100,
      "avg_price_krw": 72000
    },
    {
      "ticker": "NVDA",
      "market": "US",
      "name": "엔비디아",
      "sector": "반도체",
      "quantity": 10,
      "avg_price_usd": 850.00
    }
  ]
}
```

- KR 종목: `avg_price_krw` 필드 사용
- US 종목: `avg_price_usd` 필드 사용
- 앱 설정 화면(화면 4)에서 `st.data_editor`로 직접 편집 가능

---

## 구현 완료

- [x] 4개 화면 네비게이션 (상단 탭)
- [x] 대시보드 — 보유 종목 카드 (현재가·수익률·RSI·MA·52주 위치)
- [x] 대시보드 — 시장 지표 바 (8개 지표 + 전일 대비 변화율 + 설명 expander)
- [x] AI 브리핑 피드 — 전체 종목 일괄 분석, 의견 배지, 근거 목록, 반론
- [x] AI 브리핑 피드 — 진행률 바 (페이지 상단에서 표시)
- [x] 매크로 뉴스 — Gemini AI 큐레이션 (6개 선별, 한국어 요약, 원문 링크)
- [x] 관심 종목 화면 — 가격·기술지표 표시
- [x] 설정 화면 — 포트폴리오 편집 (data_editor)
- [x] 다크/라이트 모드 완전 대응
- [x] Gemini API 에러 한국어 안내 메시지 (429/503/500/401 구분)
- [x] HTML/LaTeX 이스케이프 (`_esc()` 헬퍼, `$` → `&#36;`)

## 미결정 / 진행 중

- [ ] 배포 방식 (Streamlit Cloud / 로컬 전용)
- [ ] 신규 종목 추천 기능 (자본금 기반)
- [ ] Gemini 유료 플랜 전환 (현재 무료 20회/일 제한)

---

## 절대 변경하지 말아야 할 것

1. **CSS 색상**: 커스텀 HTML/CSS에서 하드코딩 hex 배경색 사용 금지. 반드시 `var(--text-color)`, `var(--secondary-background-color)`, `rgba()` 사용
2. **`_esc()` 헬퍼**: HTML 인젝션·LaTeX 파싱 방지용. 사용자 데이터를 HTML에 삽입할 때 반드시 거칠 것
3. **`_t1()` / `_d130()` 함수**: 날짜를 모듈 로드 시가 아닌 호출 시에 계산. 상수로 교체 금지
4. **`portfolio.json` 스키마**: `market` 필드 값은 반드시 `"KR"` 또는 `"US"`. KR은 `avg_price_krw`, US는 `avg_price_usd` 사용
5. **`.env` 파일**: `.gitignore` 등록 유지. 절대 커밋 금지

---

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

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
