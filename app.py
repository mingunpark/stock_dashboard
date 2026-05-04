import html as _html
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from analysis.claude_client import (
    analyze_stock as _analyze_stock,
    curate_macro_news as _curate_macro_news,
)
from data.fetcher import (
    fetch_fx_rate as _fetch_fx_rate,
    fetch_macro_news_raw as _fetch_macro_news_raw,
    fetch_market_indicators as _fetch_market_indicators,
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

# ── CSS ──────────────────────────────────────────────────────
# var(--text-color) / var(--secondary-background-color) 는 Streamlit이
# 라이트/다크 모드에 맞게 자동 주입하는 CSS 변수 → 하드코딩 색상 불필요
st.markdown("""
<style>
  .block-container { padding-top: 4rem !important; }

  /* ── 배지 ── */
  .badge {
    display:inline-block; padding:3px 10px;
    border-radius:6px; font-size:13px; font-weight:700;
  }
  .badge-buy  { background:rgba(37,99,235,0.12); color:#3b82f6; border:1px solid rgba(37,99,235,0.3); }
  .badge-sell { background:rgba(220,38,38,0.12); color:#f87171; border:1px solid rgba(220,38,38,0.3); }
  .badge-hold { background:rgba(107,114,128,0.12); color:var(--text-color); border:1px solid rgba(107,114,128,0.3); }
  .badge-wait { background:rgba(180,83,9,0.12); color:#f59e0b; border:1px solid rgba(180,83,9,0.3); font-style:italic; }

  /* ── AI 브리핑 카드 ── */
  .brief-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
    margin-bottom: 8px;
  }
  .brief-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 12px;
    padding: 16px 18px;
    transition: box-shadow 0.15s, transform 0.1s;
  }
  .brief-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0,0,0,0.10);
  }
  .brief-hd {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 10px;
    margin-bottom: 10px;
    border-bottom: 1px solid rgba(128,128,128,0.12);
  }
  .brief-ticker {
    font-size: 17px; font-weight: 800;
    color: var(--text-color);
    letter-spacing: -0.3px;
  }
  .brief-name {
    font-size: 12px;
    color: var(--text-color);
    opacity: 0.5;
    margin-top: 2px;
    display: block;
  }
  .brief-list { margin: 0; padding-left: 18px; }
  .brief-list li {
    font-size: 13px;
    line-height: 1.7;
    margin-bottom: 4px;
    color: var(--text-color);
    opacity: 0.85;
  }
  .brief-caveat {
    display: flex; gap: 7px; align-items: flex-start;
    margin-top: 11px; padding: 8px 11px;
    border-radius: 7px;
    border-left: 3px solid #f59e0b;
    background: rgba(245,158,11,0.07);
    font-size: 12px;
    color: var(--text-color);
    opacity: 0.82;
    line-height: 1.5;
  }
  .brief-err {
    font-size: 12px; color: #ef4444;
    padding: 6px 0;
    line-height: 1.6;
    word-break: keep-all;
  }

  /* ── 시장 지표 그리드 ── */
  .ind-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 8px;
    margin: 8px 0 4px 0;
  }
  .ind-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.15);
    border-radius: 9px;
    padding: 10px 13px;
  }
  .ind-label {
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.4px; text-transform: uppercase;
    color: var(--text-color); opacity: 0.5;
    margin-bottom: 3px;
  }
  .ind-val {
    font-size: 16px; font-weight: 700;
    color: var(--text-color);
    margin-bottom: 2px;
  }
  .ind-chg { font-size: 11px; font-weight: 600; margin-bottom: 3px; }
  .ind-desc { font-size: 10px; color: var(--text-color); opacity: 0.45; }

  /* ── 뉴스 카드 ── */
  .news-card {
    padding: 12px 0;
    border-bottom: 1px solid rgba(128,128,128,0.13);
  }
  .news-card:last-child { border-bottom: none; }
  .news-src {
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    text-transform: uppercase; color: #3b82f6;
  }
  .news-link {
    display: block;
    font-size: 14px; font-weight: 600;
    color: var(--text-color);
    text-decoration: none;
    margin: 4px 0 5px 0;
    line-height: 1.45;
  }
  .news-link:hover { text-decoration: underline; }
  .news-sum {
    font-size: 12px;
    color: var(--text-color);
    opacity: 0.65;
    margin: 0;
    line-height: 1.6;
  }
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


@st.cache_data(ttl=600)
def fetch_market_indicators() -> dict:
    return _fetch_market_indicators()


@st.cache_data(ttl=1800)
def fetch_macro_raw() -> list[dict]:
    return _fetch_macro_news_raw()


@st.cache_data(ttl=7200)
def fetch_macro_curated() -> list[dict]:
    raw = _fetch_macro_news_raw()
    return _curate_macro_news(raw) if raw else []


@st.cache_data(ttl=14400)
def analyze_cached(holding_json: str, price_json: str, news_json: str) -> dict:
    return _analyze_stock(
        json.loads(holding_json),
        json.loads(price_json),
        json.loads(news_json),
    )


# ── 데이터 로드 / 저장 ───────────────────────────────────────

PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "portfolio.json")


def load_portfolio() -> dict:
    try:
        with open(PORTFOLIO_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("portfolio.json 파일이 없습니다.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"portfolio.json 형식 오류: {e}")
        st.stop()


def save_portfolio(data: dict) -> None:
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_watchlist() -> list:
    path = os.path.join(os.path.dirname(__file__), "watchlist.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ── 전체 브리핑 ──────────────────────────────────────────────

def run_full_briefing(holdings: list, progress_cb=None) -> dict:
    results: dict = {}
    for i, h in enumerate(holdings):
        if progress_cb:
            progress_cb(i, len(holdings), h.get("name", h["ticker"]))
        price = fetch_price(h["ticker"], h["market"])
        news  = fetch_news(h["ticker"], h["market"], h.get("name", h["ticker"]))
        result = analyze_cached(
            json.dumps(h,     ensure_ascii=False, sort_keys=True),
            json.dumps(price, ensure_ascii=False, sort_keys=True),
            json.dumps(news,  ensure_ascii=False, sort_keys=True),
        )
        results[h["ticker"]] = result
    return results


# ── 헬퍼 ────────────────────────────────────────────────────

def calc_pnl(holding: dict, price_data: dict, fx: float) -> dict:
    qty = holding["quantity"]
    market = holding["market"]
    current_price = price_data.get("price", 0)
    if market == "KR":
        avg = holding["avg_price_krw"]
        eval_krw = current_price * qty
        pnl_krw  = (current_price - avg) * qty
    else:
        avg = holding["avg_price_usd"]
        eval_krw = current_price * fx * qty
        pnl_krw  = (current_price - avg) * fx * qty
    cost_base = avg * qty * (1 if market == "KR" else fx)
    pnl_pct = (pnl_krw / cost_base * 100) if cost_base else 0
    return {"eval_krw": eval_krw, "pnl_krw": pnl_krw, "pnl_pct": pnl_pct}


def opinion_badge(opinion: str | None) -> str:
    m = {
        "매수": ("badge-buy",  "▲ 매수"),
        "매도": ("badge-sell", "▼ 매도"),
        "보유": ("badge-hold", "— 보유"),
    }
    cls, label = m.get(opinion, ("badge-wait", "분석 전"))
    return f'<span class="badge {cls}">{label}</span>'


def _esc(text: str) -> str:
    """HTML 특수문자 + $ 이스케이프 (LaTeX 파싱 방지)."""
    return _html.escape(str(text), quote=False).replace("$", "&#36;")


# ── 시장 지표 메타 ────────────────────────────────────────────
_IND_META: dict[str, tuple] = {
    # key: (표시명, 짧은설명, 해설)
    "sp500":  ("S&P 500",   "미국 대형주",
               "미국 500대 기업 시총 가중 지수. 미국 증시 전체 방향의 핵심 바로미터."),
    "nasdaq": ("NASDAQ",    "기술·성장주",
               "나스닥 상장 기술·성장주 중심. 금리 변화에 민감하게 반응."),
    "kospi":  ("코스피",     "한국 주식",
               "국내 전 상장 종목 시총 가중 지수. 원/달러·수출 경기 영향 큼."),
    "vix":    ("VIX",       "공포 지수",
               "S&P500 옵션 내재변동성 기반. 18↓ 안정 · 18~25 주의 · 25↑ 위험구간."),
    "us10y":  ("미국 10Y",   "장기금리",
               "미국채 10년 수익률. 상승 시 성장주 할인율↑ → 밸류에이션 하락 압력."),
    "gold":   ("금 선물",    "안전자산",
               "불확실성·인플레이션 헤지 수단. 달러와 역상관 관계가 많음."),
    "usdkrw": ("USD/KRW",   "원달러 환율",
               "환율↑ → 미국주식 환차익, 수입물가↑, 외국인 국내주식 매도 압력."),
    "wti":    ("WTI 원유",   "유가·에너지",
               "미국 기준 원유 선물. 유가↑ → 인플레이션↑, 에너지 비용↑."),
}


def _vix_color(vix: float | None) -> str:
    if vix is None: return "var(--text-color)"
    if vix < 18: return "#16a34a"
    if vix < 25: return "#d97706"
    return "#dc2626"


def _ind_card(key: str, val, chg, meta: dict) -> str:
    name, desc_short, _ = meta[key]
    val_str = "—"
    if val is not None:
        if key in ("sp500", "nasdaq", "kospi"):
            val_str = f"{val:,.2f}"
        elif key == "vix":
            val_str = f"{val:.2f}"
        elif key == "us10y":
            val_str = f"{val:.2f}%"
        elif key in ("gold", "wti"):
            val_str = f"USD {val:,.1f}"
        elif key == "usdkrw":
            val_str = f"{val:,.2f}"
        else:
            val_str = str(val)

    val_color = _vix_color(val) if key == "vix" else "var(--text-color)"

    if chg is not None:
        chg_color = "#16a34a" if chg >= 0 else "#ef4444"
        chg_arrow = "▲" if chg >= 0 else "▼"
        chg_html  = (f'<div class="ind-chg" style="color:{chg_color}">'
                     f'{chg_arrow} {abs(chg):.2f}%</div>')
    else:
        chg_html = '<div class="ind-chg" style="opacity:0.3">—</div>'

    return f"""
<div class="ind-card">
  <div class="ind-label">{name}</div>
  <div class="ind-val" style="color:{val_color}">{val_str}</div>
  {chg_html}
  <div class="ind-desc">{desc_short}</div>
</div>"""


# ── 세션 상태 ────────────────────────────────────────────────
if "page"             not in st.session_state: st.session_state.page = "dashboard"
if "selected_ticker"  not in st.session_state: st.session_state.selected_ticker = None
if "briefing_results" not in st.session_state: st.session_state.briefing_results = {}
if "price_cache"      not in st.session_state: st.session_state.price_cache = {}
if "do_briefing"      not in st.session_state: st.session_state.do_briefing = False


# ── 공통 데이터 ──────────────────────────────────────────────
portfolio = load_portfolio()
watchlist = load_watchlist()
fx_rate   = fetch_fx_rate()
holdings  = portfolio.get("holdings", [])
kr_h = [h for h in holdings if h["market"] == "KR"]
us_h = [h for h in holdings if h["market"] == "US"]


def _eval(h: dict) -> float:
    p = st.session_state.price_cache.get(h["ticker"], {})
    return p.get("price", 0) * h["quantity"] * (1 if h["market"] == "KR" else fx_rate)


def _cost(h: dict) -> float:
    qty = h["quantity"]
    if h["market"] == "KR":
        return h["avg_price_krw"] * qty
    return h["avg_price_usd"] * qty * fx_rate


# 국장 계산
kr_eval    = sum(_eval(h) for h in kr_h)
kr_cost    = sum(_cost(h) for h in kr_h)
kr_pnl     = kr_eval - kr_cost
kr_pnl_pct = (kr_pnl / kr_cost * 100) if kr_cost else 0
kr_cash    = portfolio.get("cash_krw", 0)
kr_priced  = (kr_eval > 0) if kr_h else True   # 종목 없으면 조회 불필요
kr_total   = kr_eval + kr_cash                  # 원화

# 미장 계산 (전부 원화 환산)
us_eval    = sum(_eval(h) for h in us_h)
us_cost    = sum(_cost(h) for h in us_h)
us_pnl     = us_eval - us_cost
us_pnl_pct = (us_pnl / us_cost * 100) if us_cost else 0
cash_usd   = portfolio.get("cash_usd", 0.0)
us_priced  = (us_eval > 0) if us_h else True
us_total   = us_eval + cash_usd * fx_rate       # 원화 환산

# 합산
total_eval    = kr_eval + us_eval
total_cost    = kr_cost + us_cost
total_pnl     = total_eval - total_cost
total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
total_capital = kr_total + us_total
target        = portfolio.get("target_return_pct", 15.0)


def _sign(v: float) -> str:
    return "+" if v >= 0 else ""


# ════════════════════════════════════════════════════════════
# 화면 1: 포트폴리오 대시보드
# ════════════════════════════════════════════════════════════
if st.session_state.page == "dashboard":

    # 브리핑을 최상단에서 실행 — 진행바가 컨텐츠 위에 표시됨
    if st.session_state.do_briefing:
        st.session_state.do_briefing = False
        total = len(holdings)
        bar = st.progress(0, text="시세 조회 중...")
        price_cache = {}
        for i, h in enumerate(holdings):
            bar.progress(
                (i + 1) / (total * 2),
                text=f"시세 조회: {h.get('name', h['ticker'])} ({i+1}/{total})"
            )
            price_cache[h["ticker"]] = fetch_price(h["ticker"], h["market"])
        st.session_state.price_cache = price_cache

        def _progress(i, n, name):
            bar.progress(
                0.5 + (i + 1) / (n * 2),
                text=f"AI 분석: {name} ({i+1}/{n}) — 속도 제한 시 자동 재시도"
            )
        st.session_state.briefing_results = run_full_briefing(holdings, _progress)
        bar.empty()
        st.rerun()

    # ── 상단 요약 바 ─────────────────────────────────────────
    c1, c2, c3, c4, c_brief, c_set = st.columns([2, 2, 2, 2, 1.2, 1.2])

    with c1:
        val = f"₩{kr_total:,.0f}" if kr_priced else "조회 필요"
        delta = f"{_sign(kr_pnl_pct)}{kr_pnl_pct:.2f}%" if (kr_priced and kr_h) else None
        st.metric("🇰🇷 국장 총자본", val, delta,
                  help=f"보유평가 + 여유현금 ₩{kr_cash:,.0f}")
    with c2:
        val = f"₩{us_total:,.0f}" if us_priced else "조회 필요"
        delta = f"{_sign(us_pnl_pct)}{us_pnl_pct:.2f}%" if (us_priced and us_h) else None
        st.metric("🇺🇸 미장 총자본", val, delta,
                  help=f"보유평가 + 여유현금 ${cash_usd:,.2f} (환율 ₩{fx_rate:,.0f})")
    with c3:
        both_priced = kr_priced and us_priced
        val = f"₩{total_capital:,.0f}" if both_priced else "조회 필요"
        delta = f"{_sign(total_pnl_pct)}{total_pnl_pct:.2f}%" if (both_priced and total_eval) else None
        st.metric("합산 총자본", val, delta)
    with c4:
        st.metric("목표 수익률", f"{target:.1f}%",
                  f"현재 {_sign(total_pnl_pct)}{total_pnl_pct:.1f}%" if total_eval else "시세 조회 후 표시")
    with c_brief:
        st.write("")
        if st.button("↻ 브리핑", use_container_width=True, type="primary",
                     help="모든 종목 시세 + AI 분석"):
            st.session_state.do_briefing = True
            st.rerun()
    with c_set:
        st.write("")
        if st.button("⚙ 설정", use_container_width=True,
                     help="보유 종목 및 자본금 편집"):
            st.session_state.page = "settings"
            st.rerun()

    # ── 시장 지표 ─────────────────────────────────────────────
    ind = fetch_market_indicators()
    cards_html = "".join(
        _ind_card(key, ind.get(key), ind.get(f"{key}_chg"), _IND_META)
        for key in _IND_META
    )
    st.markdown(f'<div class="ind-grid">{cards_html}</div>', unsafe_allow_html=True)

    with st.expander("📖 지표 해설 보기"):
        ex_cols = st.columns(2)
        for i, (key, (name, short, detail)) in enumerate(_IND_META.items()):
            with ex_cols[i % 2]:
                st.markdown(f"**{name}** — {short}")
                st.caption(detail)

    st.divider()

    # ── 보유 종목 테이블 ──────────────────────────────────────
    def _render_holdings(group: list, label: str) -> None:
        st.markdown(f"##### {label}")
        if not group:
            st.caption("보유 종목 없음")
            return
        hdr = st.columns([2.2, 1.8, 1, 1.8, 1.2])
        for col, txt in zip(hdr, ["종목", "현재가 / 평단", "수량", "수익/손실", "AI 의견"]):
            col.caption(txt)
        for h in group:
            pd_ = st.session_state.price_cache.get(h["ticker"], {})
            pnl = calc_pnl(h, pd_, fx_rate)
            opinion = st.session_state.briefing_results.get(h["ticker"], {}).get("opinion")
            c1, c2, c3, c4, c5 = st.columns([2.2, 1.8, 1, 1.8, 1.2])
            with c1:
                if st.button(f"**{h['ticker']}** {h.get('name','')}",
                             key=f"go_{h['ticker']}", use_container_width=True):
                    st.session_state.selected_ticker = h["ticker"]
                    st.session_state.page = "detail"
                    st.rerun()
            with c2:
                price_str = pd_.get("price_display", "—").replace("$", "\\$")
                avg_str = (f"{h['avg_price_krw']:,.0f}원"
                           if h["market"] == "KR"
                           else f"\\${h['avg_price_usd']:,.2f}")
                st.markdown(f"{price_str}  \n<small style='color:#aaa'>{avg_str}</small>",
                            unsafe_allow_html=True)
            with c3:
                st.markdown(f"{h['quantity']}주")
            with c4:
                if pd_.get("price"):
                    sign  = "+" if pnl["pnl_pct"] >= 0 else ""
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
    st.caption(f"pykrx T-1 · yfinance · {datetime.now().strftime('%H:%M')} 기준")

    st.divider()

    # ── AI 브리핑 피드 ────────────────────────────────────────
    st.markdown("##### 🤖 AI 브리핑 피드")
    results = st.session_state.briefing_results

    if not results:
        st.info("'↻ 브리핑' 버튼으로 AI 분석을 시작하세요.")
    else:
        cards = []
        for h in holdings:
            r = results.get(h["ticker"])
            if not r:
                continue
            err     = r.get("error")
            opinion = r.get("opinion")

            if err:
                cards.append(
                    f'<div class="brief-card">'
                    f'<div class="brief-hd">'
                    f'<div><span class="brief-ticker">{_esc(h["ticker"])}</span>'
                    f'<span class="brief-name">{_esc(h.get("name",""))}</span></div>'
                    f'</div>'
                    f'<div class="brief-err">⚠ {_esc(err)}</div>'
                    f'</div>'
                )
                continue

            badge_cls = {"매수": "badge-buy", "매도": "badge-sell",
                         "보유": "badge-hold"}.get(opinion, "badge-wait")
            arrow     = {"매수": "▲", "매도": "▼", "보유": "—"}.get(opinion, "?")
            label     = opinion or "분석 전"
            items_html = "".join(
                f"<li>{_esc(item)}</li>" for item in r.get("reasons", [])
            )
            caveat = r.get("counterpoint", "")
            caveat_html = (
                f'<div class="brief-caveat"><span>⚠</span><span>{_esc(caveat)}</span></div>'
                if caveat else ""
            )
            cards.append(f"""
<div class="brief-card">
  <div class="brief-hd">
    <div>
      <span class="brief-ticker">{_esc(h['ticker'])}</span>
      <span class="brief-name">{_esc(h.get('name',''))}</span>
    </div>
    <span class="badge {badge_cls}">{arrow}&nbsp;{label}</span>
  </div>
  <ol class="brief-list">{items_html}</ol>
  {caveat_html}
</div>""")

        st.markdown(
            f'<div class="brief-grid">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── 주요 경제 뉴스 (AI 큐레이션) ─────────────────────────
    st.markdown("##### 🌐 주요 경제 뉴스 (AI 선별)")

    with st.spinner("최신 뉴스 AI 큐레이션 중… (최초 1회 약 10초)"):
        curated = fetch_macro_curated()

    if curated:
        news_cards = []
        for n in curated:
            title   = _esc(n.get("title", ""))
            summary = _esc(n.get("summary", ""))
            source  = _esc(n.get("source", ""))
            link    = _html.escape(n.get("link", "#"), quote=True)
            news_cards.append(f"""
<div class="news-card">
  <span class="news-src">{source}</span>
  <a href="{link}" class="news-link" target="_blank" rel="noopener noreferrer">{title}</a>
  <div class="news-sum">{summary}</div>
</div>""")
        st.markdown("".join(news_cards), unsafe_allow_html=True)
    else:
        # 큐레이션 실패 시 raw 뉴스로 폴백
        raw_news = fetch_macro_raw()
        if raw_news:
            for n in raw_news[:6]:
                src   = _esc(n.get("source", ""))
                title = _esc(n.get("title", ""))
                link  = _html.escape(n.get("link", "#"), quote=True)
                st.markdown(
                    f'<div class="news-card">'
                    f'<span class="news-src">{src}</span>'
                    f'<a href="{link}" class="news-link" target="_blank" '
                    f'rel="noopener noreferrer">{title}</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("뉴스 수집 실패 (네트워크 확인)")


# ════════════════════════════════════════════════════════════
# 화면 2: 종목 상세 분석
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "detail":
    ticker = st.session_state.selected_ticker
    if not ticker:
        st.session_state.page = "dashboard"; st.rerun()

    holding = next((h for h in holdings if h["ticker"] == ticker), None)
    if not holding:
        st.error(f"포트폴리오에 {ticker} 없음")
        st.session_state.page = "dashboard"; st.rerun()

    if st.button("← 대시보드로"):
        st.session_state.page = "dashboard"; st.rerun()

    st.header(f"{ticker} — {holding.get('name', '')} 상세 분석")

    col_fetch, _ = st.columns([2, 6])
    with col_fetch:
        do_fetch = st.button("시세 + 뉴스 + AI 분석 실행", type="primary")

    if do_fetch:
        with st.spinner("분석 중..."):
            price_data = fetch_price(ticker, holding["market"])
            news       = fetch_news(ticker, holding["market"], holding.get("name", ticker))
            result     = analyze_cached(
                json.dumps(holding,     ensure_ascii=False, sort_keys=True),
                json.dumps(price_data,  ensure_ascii=False, sort_keys=True),
                json.dumps(news,        ensure_ascii=False, sort_keys=True),
            )
            st.session_state.price_cache[ticker]     = price_data
            st.session_state.briefing_results[ticker] = result

    price_data = st.session_state.price_cache.get(ticker, {})
    result     = st.session_state.briefing_results.get(ticker, {})

    if price_data.get("price"):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("현재가",    price_data["price_display"])
        m2.metric("RSI(14)",   f"{price_data.get('rsi','—')}")
        m3.metric("20일 MA",   f"{price_data.get('ma20','—')}")
        m4.metric("60일 MA",   f"{price_data.get('ma60','—')}")
        m5.metric("52주 위치", f"{price_data.get('week52_pos','—')}%")

    if result.get("opinion"):
        st.divider()
        opinion   = result["opinion"]
        badge_cls = {"매수": "badge-buy", "매도": "badge-sell",
                     "보유": "badge-hold"}.get(opinion, "badge-wait")
        st.markdown(
            f'<span class="badge {badge_cls}" style="font-size:15px">{opinion}</span>',
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
        st.session_state.page = "dashboard"; st.rerun()
    st.header("DCA 플래너")
    st.info("다음 단계에서 구현됩니다.")


# ════════════════════════════════════════════════════════════
# 화면 4: 포트폴리오 설정
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "settings":
    if st.button("← 대시보드로"):
        st.session_state.page = "dashboard"; st.rerun()

    st.header("⚙ 포트폴리오 설정")

    st.subheader("자본금 정보")
    st.caption("총자본은 보유종목 평가액 + 여유현금으로 자동 계산됩니다.")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        new_cash_krw = st.number_input(
            "🇰🇷 국장 여유현금 (원)", value=int(portfolio.get("cash_krw", 0)),
            step=100000, min_value=0, format="%d",
        )
    with col_b:
        new_cash_usd = st.number_input(
            "🇺🇸 미장 여유현금 (USD)", value=float(portfolio.get("cash_usd", 0.0)),
            step=100.0, min_value=0.0, format="%.2f",
        )
    with col_c:
        new_target = st.number_input(
            "목표 수익률 (%)", value=float(portfolio.get("target_return_pct", 15.0)),
            step=0.5, min_value=0.0, max_value=200.0, format="%.1f",
        )

    st.divider()
    st.subheader("보유 종목")
    st.caption("행 클릭 → 수정 | 하단 + → 추가 | 행 선택 후 Delete → 삭제")

    holdings_df = pd.DataFrame([
        {
            "ticker":        h["ticker"],
            "name":          h.get("name", ""),
            "market":        h["market"],
            "quantity":      h["quantity"],
            "avg_price_krw": h.get("avg_price_krw", 0),
            "avg_price_usd": h.get("avg_price_usd", 0.0),
        }
        for h in portfolio.get("holdings", [])
    ])

    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        column_config={
            "ticker":        st.column_config.TextColumn("종목코드", width="small"),
            "name":          st.column_config.TextColumn("종목명", width="medium"),
            "market":        st.column_config.SelectboxColumn(
                                 "시장", options=["KR", "US"], width="small"),
            "quantity":      st.column_config.NumberColumn(
                                 "수량(주)", min_value=0, step=1, format="%d"),
            "avg_price_krw": st.column_config.NumberColumn(
                                 "평균단가(원, KR)", min_value=0, step=100, format="%d"),
            "avg_price_usd": st.column_config.NumberColumn(
                                 "평균단가(USD, US)", min_value=0.0, step=0.01, format="%.2f"),
        },
        use_container_width=True,
        key="holdings_editor",
    )

    st.divider()

    if st.button("💾 저장", type="primary"):
        new_holdings = []
        for _, row in edited_df.iterrows():
            t = row.get("ticker")
            if not t or pd.isna(t):
                continue
            market = str(row.get("market") or "KR")
            h: dict = {
                "ticker":   str(t).strip().upper(),
                "name":     str(row.get("name") or ""),
                "market":   market,
                "quantity": int(row["quantity"]) if pd.notna(row.get("quantity")) else 0,
            }
            if market == "KR":
                h["avg_price_krw"] = (
                    int(row["avg_price_krw"]) if pd.notna(row.get("avg_price_krw")) else 0
                )
            else:
                h["avg_price_usd"] = (
                    float(row["avg_price_usd"]) if pd.notna(row.get("avg_price_usd")) else 0.0
                )
            new_holdings.append(h)

        save_portfolio({
            **portfolio,
            "cash_krw":          int(new_cash_krw),
            "cash_usd":          float(new_cash_usd),
            "target_return_pct": float(new_target),
            "holdings":          new_holdings,
        })
        st.session_state.price_cache      = {}
        st.session_state.briefing_results = {}
        st.success("저장 완료! 대시보드로 돌아가면 변경사항이 반영됩니다.")
