import math
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

def _t1() -> str:
    return (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")

def _d130() -> str:
    return (datetime.today() - timedelta(days=130)).strftime("%Y%m%d")


# ── 시세 + 기술지표 ──────────────────────────────────────────

def _find_swings(close_series, window=5):
    highs, lows = [], []
    for i in range(window, len(close_series) - window):
        window_slice = close_series.iloc[i - window:i + window + 1]
        if close_series.iloc[i] == window_slice.max():
            highs.append({"date": close_series.index[i].strftime("%Y-%m-%d"),
                          "price": round(float(close_series.iloc[i]), 2)})
        if close_series.iloc[i] == window_slice.min():
            lows.append({"date": close_series.index[i].strftime("%Y-%m-%d"),
                         "price": round(float(close_series.iloc[i]), 2)})
    return highs[-3:], lows[-3:]


def fetch_price_kr(ticker: str) -> dict:
    """pykrx로 KR 종목 OHLCV + RSI/MA/52주 위치 + 확장 지표 수집."""
    try:
        df = krx.get_market_ohlcv(_d130(), _t1(), ticker)
        if df.empty:
            return {"ticker": ticker, "market": "KR", "price": 0,
                    "price_display": "데이터 없음", "error": "T+1 대기 중 또는 휴장"}

        close  = df["종가"].astype(float)
        high   = df["고가"].astype(float)
        low    = df["저가"].astype(float)
        volume = df["거래량"].astype(float)
        current = float(close.iloc[-1])

        rsi_s = ta.rsi(close, length=14)
        rsi  = round(float(rsi_s.iloc[-1]), 1) if rsi_s is not None and len(rsi_s) > 0 else None
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 0) if len(close) >= 20 else None
        ma60 = round(float(close.rolling(60).mean().iloc[-1]), 0) if len(close) >= 60 else None

        high52 = float(close.max())
        low52  = float(close.min())
        week52_pos = round((current - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50.0

        name = krx.get_market_ticker_name(ticker)

        ma5   = round(float(close.rolling(5).mean().iloc[-1]),   0) if len(close) >= 5   else None
        ma120 = round(float(close.rolling(120).mean().iloc[-1]), 0) if len(close) >= 120 else None

        bb = ta.bbands(close, length=20, std=2)
        bollinger = None
        if bb is not None:
            _bbu = next((c for c in bb.columns if c.startswith("BBU")), None)
            _bbm = next((c for c in bb.columns if c.startswith("BBM")), None)
            _bbl = next((c for c in bb.columns if c.startswith("BBL")), None)
            if _bbu and not bb[_bbu].isna().iloc[-1]:
                bollinger = {
                    "upper":  round(float(bb[_bbu].iloc[-1]), 0),
                    "middle": round(float(bb[_bbm].iloc[-1]), 0),
                    "lower":  round(float(bb[_bbl].iloc[-1]), 0),
                }

        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        macd = None
        if macd_df is not None and not macd_df["MACD_12_26_9"].isna().iloc[-1]:
            macd = {
                "macd":      round(float(macd_df["MACD_12_26_9"].iloc[-1]),  4),
                "signal":    round(float(macd_df["MACDs_12_26_9"].iloc[-1]), 4),
                "histogram": round(float(macd_df["MACDh_12_26_9"].iloc[-1]), 4),
            }

        stoch = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        stochastic = None
        if stoch is not None and not stoch["STOCHk_14_3_3"].isna().iloc[-1]:
            stochastic = {
                "k": round(float(stoch["STOCHk_14_3_3"].iloc[-1]), 1),
                "d": round(float(stoch["STOCHd_14_3_3"].iloc[-1]), 1),
            }

        recent = close.iloc[-60:]
        resistance = round(float(recent.nlargest(3).mean()),  0)
        support    = round(float(recent.nsmallest(3).mean()), 0)

        _vol20 = volume.iloc[-20:].mean() if len(volume) >= 20 else 0
        volume_ratio = round(float(volume.iloc[-5:].mean() / _vol20), 2) if _vol20 > 0 else None
        volume_surge = bool(volume.iloc[-3:].mean() >= _vol20 * 1.5) if _vol20 > 0 else False

        ma20_series = close.rolling(20).mean()
        slope = float(ma20_series.iloc[-1] - ma20_series.iloc[-5])
        trend_direction = "up" if slope > 0 else ("down" if slope < 0 else "sideways")

        swing_highs, swing_lows = _find_swings(close)

        ohlcv_60 = [
            {
                "date":   idx.strftime("%Y-%m-%d"),
                "open":   round(float(row["시가"]),   0),
                "high":   round(float(row["고가"]),   0),
                "low":    round(float(row["저가"]),   0),
                "close":  round(float(row["종가"]),   0),
                "volume": int(row["거래량"]),
            }
            for idx, row in df.iloc[-60:].iterrows()
        ]

        return {
            "ticker": ticker, "market": "KR", "name": name,
            "price": current,
            "price_display": f"{current:,.0f}원",
            "rsi": rsi, "ma20": ma20, "ma60": ma60,
            "week52_high": round(high52, 0), "week52_low": round(low52, 0),
            "week52_pos": week52_pos,
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "error": None,
            "ma5": ma5, "ma120": ma120,
            "bollinger": bollinger, "macd": macd, "stochastic": stochastic,
            "support": support, "resistance": resistance,
            "volume_ratio": volume_ratio, "volume_surge": volume_surge,
            "trend_direction": trend_direction,
            "swing_highs": swing_highs, "swing_lows": swing_lows,
            "ohlcv_60": ohlcv_60,
        }
    except Exception as e:
        return {"ticker": ticker, "market": "KR", "price": 0,
                "price_display": "오류", "error": str(e)}


def fetch_price_us(ticker: str) -> dict:
    """yfinance로 US 종목 OHLCV + RSI/MA/52주 위치 + 확장 지표 수집."""
    try:
        obj  = yf.Ticker(ticker)
        hist = obj.history(period="1y")
        if hist.empty:
            return {"ticker": ticker, "market": "US", "price": 0,
                    "price_display": "데이터 없음", "error": "yfinance 응답 없음"}

        close  = hist["Close"].astype(float)
        high   = hist["High"].astype(float)
        low    = hist["Low"].astype(float)
        volume = hist["Volume"].astype(float)
        current = float(close.iloc[-1])

        rsi_s = ta.rsi(close, length=14)
        rsi  = round(float(rsi_s.iloc[-1]), 1) if rsi_s is not None and len(rsi_s) > 0 else None
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2) if len(close) >= 20 else None
        ma60 = round(float(close.rolling(60).mean().iloc[-1]), 2) if len(close) >= 60 else None

        high52 = float(close.max())
        low52  = float(close.min())
        week52_pos = round((current - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50.0

        ma5   = round(float(close.rolling(5).mean().iloc[-1]),   2) if len(close) >= 5   else None
        ma120 = round(float(close.rolling(120).mean().iloc[-1]), 2) if len(close) >= 120 else None

        bb = ta.bbands(close, length=20, std=2)
        bollinger = None
        if bb is not None:
            _bbu = next((c for c in bb.columns if c.startswith("BBU")), None)
            _bbm = next((c for c in bb.columns if c.startswith("BBM")), None)
            _bbl = next((c for c in bb.columns if c.startswith("BBL")), None)
            if _bbu and not bb[_bbu].isna().iloc[-1]:
                bollinger = {
                    "upper":  round(float(bb[_bbu].iloc[-1]), 2),
                    "middle": round(float(bb[_bbm].iloc[-1]), 2),
                    "lower":  round(float(bb[_bbl].iloc[-1]), 2),
                }

        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        macd = None
        if macd_df is not None and not macd_df["MACD_12_26_9"].isna().iloc[-1]:
            macd = {
                "macd":      round(float(macd_df["MACD_12_26_9"].iloc[-1]),  4),
                "signal":    round(float(macd_df["MACDs_12_26_9"].iloc[-1]), 4),
                "histogram": round(float(macd_df["MACDh_12_26_9"].iloc[-1]), 4),
            }

        stoch = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        stochastic = None
        if stoch is not None and not stoch["STOCHk_14_3_3"].isna().iloc[-1]:
            stochastic = {
                "k": round(float(stoch["STOCHk_14_3_3"].iloc[-1]), 1),
                "d": round(float(stoch["STOCHd_14_3_3"].iloc[-1]), 1),
            }

        recent = close.iloc[-60:]
        resistance = round(float(recent.nlargest(3).mean()),  2)
        support    = round(float(recent.nsmallest(3).mean()), 2)

        _vol20 = volume.iloc[-20:].mean() if len(volume) >= 20 else 0
        volume_ratio = round(float(volume.iloc[-5:].mean() / _vol20), 2) if _vol20 > 0 else None
        volume_surge = bool(volume.iloc[-3:].mean() >= _vol20 * 1.5) if _vol20 > 0 else False

        ma20_series = close.rolling(20).mean()
        slope = float(ma20_series.iloc[-1] - ma20_series.iloc[-5])
        trend_direction = "up" if slope > 0 else ("down" if slope < 0 else "sideways")

        swing_highs, swing_lows = _find_swings(close)

        ohlcv_60 = [
            {
                "date":   idx.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),   2),
                "high":   round(float(row["High"]),   2),
                "low":    round(float(row["Low"]),    2),
                "close":  round(float(row["Close"]),  2),
                "volume": int(row["Volume"]),
            }
            for idx, row in hist.iloc[-60:].iterrows()
        ]

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
            "ma5": ma5, "ma120": ma120,
            "bollinger": bollinger, "macd": macd, "stochastic": stochastic,
            "support": support, "resistance": resistance,
            "volume_ratio": volume_ratio, "volume_surge": volume_surge,
            "trend_direction": trend_direction,
            "swing_highs": swing_highs, "swing_lows": swing_lows,
            "ohlcv_60": ohlcv_60,
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


def fetch_macro_news_raw(max_items: int = 40) -> list[dict]:
    """국내외 경제·증시 뉴스 원본 수집 (AI 큐레이션용). 링크 포함."""
    queries = [
        ("글로벌 증시 경제 금리 주식", "ko", "KR", "KR:ko"),
        ("stock market economy federal reserve interest rate earnings", "en", "US", "US:en"),
    ]
    items: list[dict] = []
    per = max_items // len(queries)
    for q_str, hl, gl, ceid in queries:
        url = (f"https://news.google.com/rss/search"
               f"?q={quote(q_str)}&hl={hl}&gl={gl}&ceid={ceid}")
        feed = _rss_parse(url)
        for e in feed.entries[:per]:
            items.append({
                "title":     e.get("title", ""),
                "source":    (e.get("source") or {}).get("title", ""),
                "published": e.get("published", ""),
                "link":      e.get("link", ""),
                "region":    gl,
            })
    return items


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


# ── 주요 시장 지표 ────────────────────────────────────────────

# ── 재무 정보 ─────────────────────────────────────────────────

def fetch_financials(ticker: str, market: str) -> dict:
    """yfinance로 종목 재무 지표 조회. KR은 .KS suffix."""
    yt = ticker + ".KS" if market == "KR" else ticker
    try:
        info = yf.Ticker(yt).info
        if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
            return {"error": "재무 데이터 없음"}

        def _v(key):
            v = info.get(key)
            if v is None:
                return None
            try:
                r = float(v)
            except (ValueError, TypeError):
                return None
            return None if (math.isnan(r) or math.isinf(r)) else round(r, 4)

        mc = info.get("marketCap")
        try:
            mc = int(mc) if mc is not None and not math.isnan(float(mc)) and not math.isinf(float(mc)) else None
        except (ValueError, TypeError):
            mc = None

        return {
            "market_cap":       mc,
            "per":              _v("trailingPE"),
            "forward_per":      _v("forwardPE"),
            "pbr":              _v("priceToBook"),
            "roe":              _v("returnOnEquity"),
            "eps":              _v("trailingEps"),
            "operating_margin": _v("operatingMargins"),
            "profit_margin":    _v("profitMargins"),
            "debt_to_equity":   _v("debtToEquity"),
            "dividend_yield":   _v("dividendYield"),
            "sector":           info.get("sector", ""),
            "industry":         info.get("industry", ""),
        }
    except Exception as e:
        return {"error": str(e)[:80]}


def fetch_market_indicators() -> dict:
    """주요 시장 지표 수집 — 가격 + 전일 대비 변화율(%)."""
    syms = {
        "sp500":  "^GSPC",
        "nasdaq": "^IXIC",
        "kospi":  "^KS11",
        "vix":    "^VIX",
        "us10y":  "^TNX",
        "gold":   "GC=F",
        "usdkrw": "KRW=X",
        "wti":    "CL=F",
    }
    result: dict = {}
    for key, sym in syms.items():
        try:
            closes = yf.Ticker(sym).history(period="5d")["Close"].dropna()
            if len(closes) >= 2:
                val  = round(float(closes.iloc[-1]), 2)
                prev = float(closes.iloc[-2])
                chg  = round((val - prev) / prev * 100, 2) if prev else None
            elif len(closes) == 1:
                val, chg = round(float(closes.iloc[-1]), 2), None
            else:
                val, chg = None, None
            result[key]           = val
            result[f"{key}_chg"]  = chg
        except Exception:
            result[key]           = None
            result[f"{key}_chg"]  = None
    return result
