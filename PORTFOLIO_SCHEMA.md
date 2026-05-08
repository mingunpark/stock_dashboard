# 포트폴리오 스키마 참조

## portfolio.json

### 전체 구조

```json
{
  "target_return_pct": 15.0,
  "cash_krw": 1000000,
  "cash_usd": 0.0,
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

### 필드 규칙

| 필드 | 타입 | 규칙 |
|------|------|------|
| `market` | string | **`"KR"` 또는 `"US"` 고정** — 다른 값 허용 안 됨 |
| `avg_price_krw` | number | KR 종목 전용. US 종목에 사용 금지 |
| `avg_price_usd` | number | US 종목 전용. KR 종목에 사용 금지 |
| `sector` | string | 비어있으면 `""`. 앱이 DCA 섹터 비중 계산에 사용. 비어있으면 "미분류"로 집계 |
| `quantity` | int | 보유 수량. 0이면 미보유(워치리스트 더미용) |
| `cash_krw` | number | 원화 여유현금. DCA 플래너 계산 기준 |
| `cash_usd` | number | 달러 여유현금. DCA 플래너 계산 기준 |

### `load_portfolio()` 동작

- 파일 없으면 기본값 반환
- `sector` 필드 없는 종목에 `""` 자동 삽입 (`setdefault`)
- `IOError` 발생 시 `st.error()`로 사용자에게 안내

---

## watchlist.json

### 구조

```json
[
  {
    "ticker": "035420",
    "market": "KR",
    "name": "NAVER",
    "sector": "인터넷"
  },
  {
    "ticker": "MSFT",
    "market": "US",
    "name": "마이크로소프트",
    "sector": "Technology"
  }
]
```

### 용도

- DCA 플래너: 섹터 비중이 5% 미만인 섹터의 워치리스트 종목 우선 추천
- AI 브리핑: 워치리스트 변경 시 `_holdings_hash(holdings, watchlist)` 달라져 캐시 무효화
- "↻ 섹터 새로고침 (US)" 버튼: US 종목의 `sector`를 yfinance에서 가져와 이 파일에 저장

### `save_watchlist()` 동작

- `watchlist.json` 덮어쓰기
- `IOError` 발생 시 `st.error()`로 사용자에게 안내

---

## st.data_editor 편집 가능 항목 (설정 화면)

보유 종목에 한해 다음 필드를 UI에서 직접 편집할 수 있음:

| 컬럼명 | 필드 | 비고 |
|--------|------|------|
| 티커 | `ticker` | |
| 시장 | `market` | `"KR"` / `"US"` |
| 종목명 | `name` | |
| 섹터 | `sector` | 비워두면 "미분류" |
| 수량 | `quantity` | |
| 평단(KRW) | `avg_price_krw` | KR 종목만 유효 |
| 평단(USD) | `avg_price_usd` | US 종목만 유효 |

저장 버튼 클릭 시 `save_portfolio()` 호출 → `portfolio.json` 즉시 덮어쓰기.
