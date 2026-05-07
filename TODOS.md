# TODOS

아래 항목은 현재 구현 범위에서 제외된 작업입니다.

---

## P1 — 배포 (Streamlit Cloud)

**배경**: DCA 플래너 완성 후 다음 단계. CEO 플랜 2026-05-07에서 DEFERRED.

- [ ] `portfolio.json` → Streamlit Secrets 관리 방식으로 전환
- [ ] `watchlist.json` → Secrets 또는 환경변수 방식 검토
- [ ] `GEMINI_API_KEY` → Streamlit Cloud Secrets 등록
- [ ] `.env` 의존성 제거 (배포 환경에서 `python-dotenv` 불필요)
- [ ] Streamlit Cloud 배포 테스트 (로컬 데이터 파일 경로 이슈 확인)

---

## P2 — DCA 섹터 비중 계산 테스트

**배경**: 섹터 비중 공식(`섹터_평가액_KRW / 전체_주식_평가액_KRW × 100`)은 FX 환산 + 현금 제외 로직을 포함. CEO 플랜 2026-05-07에서 tests/test_core.py에 추가 예정이나 DCA 전용 테스트는 별도.

- [ ] `calc_sector_weights()` 함수 단위 테스트
  - KR/US 혼합 포트폴리오 + FX 환산 검증
  - 현금 제외 확인
  - 섹터 미분류("") 종목이 "미분류" 그룹으로 집계되는지 확인
  - FX 폴백(1400) 시 섹터 비중 근사치 동작 확인

---

## P3 — app.py → pages/ 모듈화 (Eng Review 결정 반영)

**배경**: Eng Review 2026-05-07에서 D1=B 결정 — DCA 구현 이후 별도 PR로 진행. Stage 1 모듈화는 DCA의 기술적 선행 조건이 아님.

**주의사항 (구현 시 필독)**:
- `@st.cache_data` 스코프: 함수를 다른 모듈로 이동하면 Streamlit 인메모리 캐시가 무효화됨 (한 번만 발생, 허용됨)
- `st.session_state` 재실행 버그: 모듈 레벨 초기화 코드가 pages/ 구조에서 재실행 타이밍 버그 가능 → 모듈화 후 기존 5개 화면 전수 검증 필수
- 라우터 패턴: `if/elif` 유지, 각 분기에서 `pages/xxx.render()` 호출 패턴 권장

체크리스트:
- [ ] pages/dashboard.py, pages/briefing.py, pages/search.py, pages/dca.py, pages/settings.py
- [ ] pages/utils.py — UI 헬퍼, 계산, 데이터 IO, 캐시, fetch 래퍼 이동
- [ ] app.py 라우터 + set_page_config + CSS + session_state 초기화만 유지
- [ ] 모듈화 완료 후 5개 화면 동작 검증 (리그레션 테스트 필수)

---

## P4 — analyze_cached 캐시 키 충돌 (워치리스트+포트폴리오 겹칠 때)

**배경**: Eng Review D9. 현재 포트폴리오(9 KR 종목)와 watchlist(NAVER/LG화학/MSFT/META/TSM)에 겹치는 종목 없음. 나중에 워치리스트 종목을 매수하면 `results[ticker]`가 quantity=0 분석과 quantity>0 분석을 동일 키로 공유함.

**해결 방향**: 캐시 키에 quantity 포함 (`ticker_q0` / `ticker_q100`), 또는 워치리스트 결과를 별도 `watchlist_results` 딕셔너리로 분리.
- `portfolio briefing` 중에 quantity>0 결과가 자연히 덮어쓰므로 실질 피해는 없음.

---

## P5 — Gemini 유료 플랜 또는 대안 AI

**배경**: 현재 무료 20회/일 제한. watchlist 분석 추가 시 하루 15회 사용으로 여유 5회만 남음.

- [ ] Gemini Pay-as-you-go 전환 검토 (AI Studio → 유료)
- [ ] 또는 대안 AI(Claude API / OpenAI) 통합 검토
- [ ] `GOOGLE_API_KEY` 환경변수 폴백 지원 추가 (1줄 수정, Gemini CLI auth 전체 구현 없이)

---

## 메모

- **Gemini CLI auth (ADC)**: 배포 전까지 불필요 (YAGNI). 배포 시 재검토.
- **실시간 알림 (RSI 임계값)**: 12개월 이상 목표. 로컬 앱에서는 Streamlit Cloud + st.caching으로 구현 가능.
- **DCA 슬라이더 session_state**: `st.slider(key="dca_rounds")`, `st.number_input(key="dca_ratio")` 형태로 key= 파라미터 명시 필수. 없으면 페이지 이동 시 값 초기화됨.
