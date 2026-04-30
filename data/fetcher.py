from datetime import datetime, timedelta
from urllib.parse import quote

import feedparser
import pandas_ta as ta
import requests
import yfinance as yf
from pykrx import stock as krx

_RSS_HEADERS = {"User-Agent": "Mozilla/5.0 StockCockpit/1.0"}

def _rss_parse(url: str) -> feedparser.FeedParserDict:
    """SSL 인증서 문제 우회: requests로 받아서 feedparser에 전달."""
    try:
        resp = requests.get(url, headers=_RSS_HEADERS, timeout=10)
        return feedparser.parse(resp.content)
    except Exception:
        return feedparser.parse("")

_TODAY = datetime.today()
_T1 = (_TODAY - timedelta(days=1)).strftime("%Y%m%d")    # T-1 (pykrx 기준일)
_D90 = (_TODAY - timedelta(days=130)).strftime("%Y%m%d")  # 60일 MA 확보용 여유


# ── 시세 + 기술지표 ──────────────────────────────────────────

def fetch_price_kr(ticker: str) -> dict:
    """pykrx로 KR 종목 OHLCV + RSI/MA/52주 위치 수집."""
    try:
        df = krx.get_market_ohlcv(_D90, _T1, ticker)
        if df.empty:
            return {"ticker": ticker, "market": "KR", "price": 0,
                    "price_display": "데이터 없음", "error": "T+1 대기 중 또는 휴장"}

        close = df["종가"].astype(float)
        current = float(close.iloc[-1])

        rsi_s = ta.rsi(close, length=14)
        rsi = round(float(rsi_s.iloc[-1]), 1) if rsi_s is not None and len(rsi_s) > 0 else None
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 0) if len(close) >= 20 else None
        ma60 = round(float(close.rolling(60).mean().iloc[-1]), 0) if len(close) >= 60 else None

        high52 = float(close.max())
        low52  = float(close.min())
        week52_pos = round((current - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50.0

        name = krx.get_market_ticker_name(ticker)

        return {
            "ticker": ticker, "market": "KR", "name": name,
            "price": current,
            "price_display": f"{current:,.0f}원",
            "rsi": rsi, "ma20": ma20, "ma60": ma60,
            "week52_high": round(high52, 0), "week52_low": round(low52, 0),
            "week52_pos": week52_pos,
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "error": None,
        }
    except Exception as e:
        return {"ticker": ticker, "market": "KR", "price": 0,
                "price_display": "오류", "error": str(e)}


def fetch_price_us(ticker: str) -> dict:
    """yfinance로 US 종목 OHLCV + RSI/MA/52주 위치 수집."""
    try:
        obj  = yf.Ticker(ticker)
        hist = obj.history(period="6mo")
        if hist.empty:
            return {"ticker": ticker, "market": "US", "price": 0,
                    "price_display": "데이터 없음", "error": "yfinance 응답 없음"}

        close = hist["Close"].astype(float)
        current = float(close.iloc[-1])

        rsi_s = ta.rsi(close, length=14)
        rsi = round(float(rsi_s.iloc[-1]), 1) if rsi_s is not None and len(rsi_s) > 0 else None
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2) if len(close) >= 20 else None
        ma60 = round(float(close.rolling(60).mean().iloc[-1]), 2) if len(close) >= 60 else None

        hist1y = obj.history(period="1y")
        close1y = hist1y["Close"].astype(float)
        high52 = float(close1y.max())
        low52  = float(close1y.min())
        week52_pos = round((current - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50.0

        return {
            "ticker": ticker, "market": "US",
            "price": current,
            "price_display": f"${current:,.2f}",
            "price_usd": current,
            "rsi": rsi, "ma20": ma20, "ma60": ma60,
            "week52_high": round(high52, 2), "week52_low": round(low52, 2),
            "week52_pos": week52_pos,
            "date": hist.index[-1].strftime("%Y-%m-%d"),
            "error": None,
        }
    except Exception as e:
        return {"ticker": ticker, "market": "US", "price": 0,
                "price_display": "오류", "error": str(e)}


def fetch_price(ticker: str, market: str) -> dict:
    return fetch_price_kr(ticker) if market == "KR" else fetch_price_us(ticker)


# ── 뉴스 수집 ────────────────────────────────────────────────

def fetch_news_kr(name: str, max_items: int = 5) -> list[dict]:
    """Google News RSS로 KR 종목 뉴스 수집."""
    query = quote(f"{name} 주식")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = _rss_parse(url)
        return [
            {
                "title": e.get("title", ""),
                "source": (e.get("source") or {}).get("title", ""),
                "published": e.get("published", ""),
            }
            for e in feed.entries[:max_items]
        ]
    except Exception:
        return []


def fetch_news_us(ticker: str, max_items: int = 5) -> list[dict]:
    """yfinance .news로 US 종목 뉴스 수집."""
    try:
        raw = yf.Ticker(ticker).news or []
        results = []
        for n in raw[:max_items]:
            # yfinance 1.3+ 중첩 구조 대응
            content = n.get("content") or {}
            title = content.get("title") or n.get("title", "")
            source = (content.get("provider") or {}).get("displayName", "")
            results.append({"title": title, "source": source, "published": ""})
        return results
    except Exception:
        return []


def fetch_news(ticker: str, market: str, name: str) -> list[dict]:
    return fetch_news_kr(name) if market == "KR" else fetch_news_us(ticker)


def fetch_macro_news(max_items: int = 6) -> list[dict]:
    """세계 경제 매크로 뉴스 (Google News RSS)."""
    query = quote("글로벌 증시 경제")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = _rss_parse(url)
        return [
            {
                "title": e.get("title", ""),
                "source": (e.get("source") or {}).get("title", ""),
                "published": e.get("published", ""),
            }
            for e in feed.entries[:max_items]
        ]
    except Exception:
        return []


# ── 환율 ─────────────────────────────────────────────────────

def fetch_fx_rate() -> float:
    """USD/KRW 실시간 환율 (yfinance KRW=X)."""
    try:
        hist = yf.Ticker("KRW=X").history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 1400.0  # fallback
