import json
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from analysis.claude_client import analyze_stock as _analyze_stock
from data.fetcher import (
    fetch_fx_rate as _fetch_fx_rate,
    fetch_macro_news as _fetch_macro_news,
    fetch_news as _fetch_news,
    fetch_price as _fetch_price,
)

# ── 페이지 설정 ─────────────────────────────────────────────
st.set_page_config(
    page_title="주식 코크핏",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding-top: 1rem !important; }
  .badge { display:inline-block; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:700; }
  .badge-buy  { background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; }
  .badge-sell { background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }
  .badge-hold { background:#f9fafb; color:#6b7280; border:1px solid #e5e7eb; }
  .badge-wait { background:#fffbeb; color:#d97706; border:1px solid #fde68a; font-style:italic; }
  .brief-card {
    background:#fff; border:1px solid #e5e7eb; border-radius:10px;
    padding:12px 14px; margin-bottom:8px;
  }
  .news-item { padding:5px 0; border-bottom:1px solid #f3f4f6; font-size:13px; }
  .news-item:last-child { border-bottom:none; }
  .error-badge { background:#fef2f2; color:#dc2626; padding:2px 8px; border-radius:5px; font-size:11px; }
</style>
""", unsafe_allow_html=True)


# ── 캐시 래퍼 ────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_price(ticker: str, market: str) -> dict:
    return _fetch_price(ticker, market)


@st.cache_data(ttl=1800)
def fetch_news(ticker: str, market: str, name: str) -> list:
    return _fetch_news(ticker, market, name)


@st.cache_data(ttl=3600)
def fetch_fx_rate() -> float:
    return _fetch_fx_rate()


@st.cache_data(ttl=1800)
def fetch_macro_news() -> list:
    return _fetch_macro_news()


@st.cache_data(ttl=14400)
def analyze_cached(holding_json: str, price_json: str, news_json: str) -> dict:
    """holding/price/news JSON 문자열 기반 캐시 — 데이터 변경 시 자동 무효화."""
    return _analyze_stock(
        json.loads(holding_json),
        json.loads(price_json),
        json.loads(news_json),
    )


# ── 데이터 로드 ──────────────────────────────────────────────

def load_portfolio() -> dict:
    path = os.path.join(os.path.dirname(__file__), "portfolio.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("portfolio.json 파일이 없습니다.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"portfolio.json 형식 오류: {e}")
        st.stop()


def load_watchlist() -> list:
    path = os.path.join(os.path.dirname(__file__), "watchlist.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ── 병렬 전체 브리핑 ─────────────────────────────────────────

def run_full_briefing(holdings: list, progress_cb=None) -> dict:
    """순차 실행 — Gemini 무료 티어 5 RPM 제한 대응."""
    results: dict = {}
    for i, h in enumerate(holdings):
        if progress_cb:
            progress_cb(i, len(holdings), h.get("name", h["ticker"]))
        price = fetch_price(h["ticker"], h["market"])
        news  = fetch_news(h["ticker"], h["market"], h.get("name", h["ticker"]))
        result = analyze_cached(
            json.dumps(h, ensure_ascii=False, sort_keys=True),
            json.dumps(price, ensure_ascii=False, sort_keys=True),
            json.dumps(news, ensure_ascii=False, sort_keys=True),
        )
        results[h["ticker"]] = result
    return results


# ── 헬퍼: 수익/손실 계산 ────────────────────────────────────

def calc_pnl(holding: dict, price_data: dict, fx: float) -> dict:
    qty = holding["quantity"]
    market = holding["market"]
    current_price = price_data.get("price", 0)

    if market == "KR":
        avg = holding["avg_price_krw"]
        eval_krw = current_price * qty
        pnl_krw  = (current_price - avg) * qty
    else:
        avg_usd = holding["avg_price_usd"]
        eval_krw = current_price * fx * qty
        pnl_krw  = (current_price - avg_usd) * fx * qty
        avg = avg_usd

    cost_base = avg * qty * (1 if market == "KR" else fx)
    pnl_pct = (pnl_krw / cost_base * 100) if cost_base else 0
    return {"eval_krw": eval_krw, "pnl_krw": pnl_krw, "pnl_pct": pnl_pct}


def opinion_badge(opinion: str | None) -> str:
    mapping = {
        "매수": ('badge-buy',  '▲ 매수'),
        "매도": ('badge-sell', '▼ 매도'),
        "보유": ('badge-hold', '— 보유'),
    }
    cls, label = mapping.get(opinion, ('badge-wait', '분석 전'))
    return f'<span class="badge {cls}">{label}</span>'


# ── 세션 상태 ────────────────────────────────────────────────
if "page"             not in st.session_state: st.session_state.page = "dashboard"
if "selected_ticker"  not in st.session_state: st.session_state.selected_ticker = None
if "briefing_results" not in st.session_state: st.session_state.briefing_results = {}
if "price_cache"      not in st.session_state: st.session_state.price_cache = {}


# ── 공통 데이터 ──────────────────────────────────────────────
portfolio = load_portfolio()
watchlist = load_watchlist()
fx_rate   = fetch_fx_rate()
holdings  = portfolio.get("holdings", [])
kr_h = [h for h in holdings if h["market"] == "KR"]
us_h = [h for h in holdings if h["market"] == "US"]

# 포트폴리오 요약 (price_cache 사용 — 캐시된 시세 있으면 활용)
def _eval(h: dict) -> float:
    p = st.session_state.price_cache.get(h["ticker"], {})
    price = p.get("price", 0)
    return price * h["quantity"] * (1 if h["market"] == "KR" else fx_rate)

def _cost(h: dict) -> float:
    qty = h["quantity"]
    if h["market"] == "KR":
        return h["avg_price_krw"] * qty
    return h["avg_price_usd"] * qty * fx_rate

total_eval = sum(_eval(h) for h in holdings)
total_cost = sum(_cost(h) for h in holdings)
total_pnl  = total_eval - total_cost
total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
cash   = portfolio.get("cash_krw", 0)
target = portfolio.get("target_return_pct", 15.0)


# ════════════════════════════════════════════════════════════
# 화면 1: 포트폴리오 대시보드
# ════════════════════════════════════════════════════════════
if st.session_state.page == "dashboard":

    # 상단 요약 바
    c1, c2, c3, c4, c_btn = st.columns([2, 2, 2, 2, 2])
    with c1:
        st.metric("총 평가금액",
                  f"₩{total_eval:,.0f}" if total_eval else "조회 필요")
    with c2:
        sign = "+" if total_pnl >= 0 else ""
        st.metric("총 수익/손실",
                  f"{sign}₩{total_pnl:,.0f}" if total_eval else "—",
                  f"{sign}{total_pnl_pct:.2f}%" if total_eval else None)
    with c3:
        st.metric("여유 현금", f"₩{cash:,.0f}")
    with c4:
        st.metric("목표 수익률", f"{target:.1f}%",
                  f"현재 {total_pnl_pct:.1f}%" if total_eval else "시세 조회 후 표시")
    with c_btn:
        st.write("")
        run_briefing = st.button("↻ 전체 브리핑",
                                 use_container_width=True,
                                 type="primary",
                                 help="모든 종목 시세 + AI 분석 (~30초)")

    st.divider()

    left, right = st.columns([6, 4], gap="large")

    # ── 왼쪽: 보유 종목 테이블 ───────────────────────────────
    with left:
        def _render_holdings(group: list, label: str) -> None:
            st.markdown(f"##### {label}")
            if not group:
                st.caption("보유 종목 없음")
                return

            col_headers = st.columns([2.2, 1.8, 1, 1.8, 1.2])
            for h, txt in zip(col_headers, ["종목", "현재가 / 평단", "수량", "수익/손실", "AI 의견"]):
                h.caption(txt)

            for h in group:
                price_data = st.session_state.price_cache.get(h["ticker"], {})
                pnl = calc_pnl(h, price_data, fx_rate)
                opinion = (st.session_state.briefing_results
                           .get(h["ticker"], {}).get("opinion"))

                c1, c2, c3, c4, c5 = st.columns([2.2, 1.8, 1, 1.8, 1.2])
                with c1:
                    btn_label = f"**{h['ticker']}** {h.get('name','')}"
                    if st.button(btn_label, key=f"go_{h['ticker']}",
                                 use_container_width=True):
                        st.session_state.selected_ticker = h["ticker"]
                        st.session_state.page = "detail"
                        st.rerun()
                with c2:
                    price_str = price_data.get("price_display", "—").replace("$", "\\$")
                    avg_str = (f"{h['avg_price_krw']:,.0f}원"
                               if h["market"] == "KR"
                               else f"\\${h['avg_price_usd']:,.2f}")
                    st.markdown(f"{price_str}  \n<small style='color:#aaa'>{avg_str}</small>",
                                unsafe_allow_html=True)
                with c3:
                    st.markdown(f"{h['quantity']}주")
                with c4:
                    if price_data.get("price"):
                        sign = "+" if pnl["pnl_pct"] >= 0 else ""
                        color = "green" if pnl["pnl_pct"] >= 0 else "red"
                        st.markdown(
                            f":{color}[{sign}{pnl['pnl_pct']:.1f}%]  \n"
                            f":{color}[{sign}₩{abs(pnl['pnl_krw']):,.0f}]"
                        )
                    else:
                        st.caption("—")
                with c5:
                    st.markdown(opinion_badge(opinion), unsafe_allow_html=True)

        _render_holdings(kr_h, "🇰🇷 한국주")
        st.write("")
        _render_holdings(us_h, "🇺🇸 미국주")

        st.caption(
            f"USD/KRW {fx_rate:,.2f} · "
            f"데이터: pykrx T-1 · yfinance · "
            f"{datetime.now().strftime('%H:%M')} 기준"
        )

    # ── 오른쪽: AI 브리핑 피드 + 뉴스 ──────────────────────
    with right:
        st.markdown("##### 🤖 AI 브리핑 피드")
        results = st.session_state.briefing_results

        if not results:
            st.info("'전체 브리핑' 버튼으로 분석을 시작하세요.")
        else:
            for h in holdings:
                r = results.get(h["ticker"])
                if not r:
                    continue

                opinion = r.get("opinion")
                err     = r.get("error")

                if err:
                    st.markdown(
                        f'<div class="brief-card">'
                        f'<b>{h["ticker"]}</b> {h.get("name","")}&nbsp;'
                        f'<span class="error-badge">오류: {err}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                badge_cls = {"매수": "badge-buy", "매도": "badge-sell",
                             "보유": "badge-hold"}.get(opinion, "badge-wait")
                arrow = {"매수": "▲", "매도": "▼", "보유": "—"}.get(opinion, "?")
                reasons_html = "".join(
                    f"<li style='margin:2px 0;font-size:12px;color:#444'>{r_}</li>"
                    for r_ in r.get("reasons", [])
                )
                caveat = r.get("counterpoint", "")
                caveat_html = (
                    f"<div style='font-size:11px;color:#aaa;margin-top:6px;"
                    f"border-top:1px solid #f3f4f6;padding-top:6px'>"
                    f"반론: {caveat}</div>"
                    if caveat else ""
                )

                st.markdown(f"""
<div class="brief-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span><b>{h['ticker']}</b>&nbsp;<small style="color:#888">{h.get('name','')}</small></span>
    <span class="badge {badge_cls}">{arrow} {opinion}</span>
  </div>
  <ul style="margin:0;padding-left:16px">{reasons_html}</ul>
  {caveat_html}
</div>""", unsafe_allow_html=True)

        st.divider()

        st.markdown("##### 🌐 세계 매크로 뉴스")
        macro = fetch_macro_news()
        if macro:
            for n in macro:
                src   = n.get("source", "")
                title = n.get("title", "")
                pub   = n.get("published", "")
                src_color = "#3b82f6"
                pub_html = f"&nbsp;<small style='color:#ccc'>{pub}</small>" if pub else ""
                st.markdown(
                    f'<div class="news-item">'
                    f'<span style="color:{src_color};font-size:10px;font-weight:700">{src}</span>{pub_html}<br>'
                    f'{title}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("뉴스 수집 실패 (네트워크 확인)")

    # 전체 브리핑 실행
    if run_briefing:
        total = len(holdings)
        progress_bar = st.progress(0, text="시세 조회 중...")

        # 시세 수집
        price_cache = {}
        for i, h in enumerate(holdings):
            progress_bar.progress((i + 1) / (total * 2),
                                  text=f"시세 조회: {h.get('name', h['ticker'])} ({i+1}/{total})")
            price_cache[h["ticker"]] = fetch_price(h["ticker"], h["market"])
        st.session_state.price_cache = price_cache

        # AI 분석 (순차, 429 재시도 자동)
        def _progress(i, n, name):
            progress_bar.progress(0.5 + (i + 1) / (n * 2),
                                  text=f"AI 분석: {name} ({i+1}/{n}) — 속도 제한 시 자동 재시도")

        st.session_state.briefing_results = run_full_briefing(holdings, _progress)
        progress_bar.empty()
        st.rerun()


# ════════════════════════════════════════════════════════════
# 화면 2: 종목 상세 분석
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "detail":
    ticker = st.session_state.selected_ticker
    if not ticker:
        st.session_state.page = "dashboard"
        st.rerun()

    holding = next((h for h in holdings if h["ticker"] == ticker), None)
    if not holding:
        st.error(f"포트폴리오에 {ticker} 없음")
        st.session_state.page = "dashboard"
        st.rerun()

    if st.button("← 대시보드로"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.header(f"{ticker} — {holding.get('name', '')} 상세 분석")

    col_fetch, _ = st.columns([2, 6])
    with col_fetch:
        do_fetch = st.button("시세 + 뉴스 + AI 분석 실행", type="primary")

    if do_fetch:
        with st.spinner("분석 중..."):
            price_data = fetch_price(ticker, holding["market"])
            news       = fetch_news(ticker, holding["market"], holding.get("name", ticker))
            result     = analyze_cached(
                json.dumps(holding, ensure_ascii=False, sort_keys=True),
                json.dumps(price_data, ensure_ascii=False, sort_keys=True),
                json.dumps(news, ensure_ascii=False, sort_keys=True),
            )
            st.session_state.price_cache[ticker] = price_data
            st.session_state.briefing_results[ticker] = result

    price_data = st.session_state.price_cache.get(ticker, {})
    result     = st.session_state.briefing_results.get(ticker, {})

    if price_data.get("price"):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("현재가",   price_data["price_display"])
        m2.metric("RSI(14)",  f"{price_data.get('rsi','—')}")
        m3.metric("20일 MA",  f"{price_data.get('ma20','—')}")
        m4.metric("60일 MA",  f"{price_data.get('ma60','—')}")
        m5.metric("52주 위치", f"{price_data.get('week52_pos','—')}%")

    if result.get("opinion"):
        st.divider()
        opinion = result["opinion"]
        badge_cls = {"매수": "badge-buy", "매도": "badge-sell",
                     "보유": "badge-hold"}.get(opinion, "badge-wait")
        st.markdown(
            f'<span class="badge {badge_cls}" style="font-size:16px">'
            f'{opinion}</span>',
            unsafe_allow_html=True,
        )
        for r_ in result.get("reasons", []):
            st.markdown(f"- {r_}")
        if result.get("counterpoint"):
            st.warning(f"반론: {result['counterpoint']}")
        st.caption("※ 투자 결정은 본인 책임입니다.")
    elif result.get("error"):
        st.error(result["error"])
    else:
        st.info("위 버튼을 눌러 분석을 실행하세요.")


# ════════════════════════════════════════════════════════════
# 화면 3: DCA 플래너 (뼈대)
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "dca":
    if st.button("← 대시보드로"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.header("DCA 플래너")
    st.info("다음 단계에서 구현됩니다.")
