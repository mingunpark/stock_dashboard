# data/ — 시세·뉴스·환율·시장지표 수집 모듈

## 파일

- `fetcher.py`: 모든 외부 데이터 수집 전담. `app.py`가 `@st.cache_data` 래퍼로 감싸서 호출

---

## 데이터 소스

| 데이터 | 소스 | 비고 |
|--------|------|------|
| 국내 OHLCV | pykrx | T-1 딜레이, 130일치 (`_d130()` 기준) |
| 해외 OHLCV | yfinance `1y` | |
| 국내 종목 뉴스 | Google News RSS | 종목명 + "주식" 검색 |
| 해외 종목 뉴스 | yfinance `.news` | |
| 매크로 뉴스 원본 | Google News RSS | 국내·해외 각 20건 수집 |
| 시장 지표 8개 | yfinance | S&P500 / NASDAQ / 코스피 / VIX / 미국10Y / 금 선물 / WTI 원유 / USD/KRW |
| 환율 (USD/KRW) | yfinance `KRW=X` | 실패 시 폴백 **1400.0** |
| 재무 지표 | yfinance `.info` | PER/PBR/ROE/영업이익률 등 |

---

## 날짜 계산 함수 — 절대 상수 교체 금지

```python
def _t1() -> str:   # 전일(T-1) 날짜 문자열 반환 — 호출 시점에 계산
def _d130() -> str: # 130일 전 날짜 문자열 반환 — 호출 시점에 계산
```

- **호출 시**마다 `datetime.now()`를 기준으로 계산
- 모듈 로드 시 고정되는 **상수로 교체 절대 금지** (새벽 자정 넘기면 날짜가 틀어짐)

---

## 환율 폴백 규칙

```python
fx = 1400.0  # yfinance KRW=X 조회 실패 시 기본값
```

- `fetch_fx_rate()` 실패 시 앱 전체가 이 값으로 동작
- DCA 섹터 비중 계산에서 US 종목 원화 환산에 사용

---

## 재무 지표 (`fetch_financials`)

KR과 US를 분리 처리:

### KR — `_fetch_financials_kr(ticker)`
- **네이버 금융 모바일 API** (`https://m.stock.naver.com/api/stock/{ticker}/finance/annual`) 우선 사용
  - `financeInfo.trTitleList` 에서 `isConsensus: "N"` 인 가장 최근 연도 key 선택
  - `financeInfo.rowList` 에서 PER, PBR, ROE, EPS, 주당배당금 추출
- **yfinance** (`.KS` → `.KQ` fallback) 로 시가총액·마진·부채·섹터 보완
- 배당수익률: 주당배당금(원) ÷ 현재가 → 비율 변환; 0.5 초과 시 None
- 네이버 값 있으면 네이버 우선, 없으면 yfinance fallback (`per`, `pbr`, `roe`, `eps`)

### US — `_fetch_financials_us(ticker)`
- yfinance만 사용 (기존 로직 동일)
- `dividendYield > 0.5` → `None` (KR yfinance 오류 필터와 동일 규칙)

### 공통 반환 키
`market_cap`, `per`, `forward_per`, `pbr`, `roe`, `eps`, `operating_margin`, `profit_margin`, `debt_to_equity`, `dividend_yield`, `sector`, `industry`

---

## 시장 지표 8개 티커

| 지표 | yfinance 티커 |
|------|--------------|
| S&P 500 | `^GSPC` |
| NASDAQ | `^IXIC` |
| 코스피 | `^KS11` |
| VIX | `^VIX` |
| 미국 10Y 국채 | `^TNX` |
| 금 선물 | `GC=F` |
| WTI 원유 | `CL=F` |
| USD/KRW | `KRW=X` |

---

## 주의사항

- 이 모듈은 **순수 데이터 수집**만 담당. Streamlit import 금지
- 캐싱은 `app.py`의 `@st.cache_data` 래퍼에서 처리 (`ttl` 값은 `app.py` 참조)
- pykrx는 장 마감 후 T-1 데이터만 제공. 장 중에는 전일 종가 기준으로 표시됨
