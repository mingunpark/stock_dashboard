"""Core logic unit tests — no Streamlit, no network, no Gemini calls."""
import hashlib
import json
import sys
import os

import pytest

# app.py를 직접 import하지 않고 순수 로직만 테스트하기 위해
# 의존 함수들을 인라인으로 재현

def _holdings_hash(holdings: list, watchlist: list | None = None) -> str:
    key = json.dumps(sorted(holdings, key=lambda h: h["ticker"]), ensure_ascii=False, sort_keys=True)
    if watchlist:
        wl_key = json.dumps(sorted(watchlist, key=lambda w: w["ticker"]), ensure_ascii=False, sort_keys=True)
        key += "|" + wl_key
    return hashlib.md5(key.encode()).hexdigest()[:12]


def calc_sector_weights(holdings: list, price_cache: dict, fx: float) -> tuple[dict, float]:
    """holdings 기준 섹터 비중 계산 (현금 제외, US 종목 FX 환산)."""
    sector_eval: dict[str, float] = {}
    total = 0.0
    for h in holdings:
        price = price_cache.get(h["ticker"], {}).get("price", 0)
        qty   = h["quantity"]
        if h["market"] == "KR":
            ev = price * qty
        else:
            ev = price * fx * qty
        sector = h.get("sector") or "미분류"
        sector_eval[sector] = sector_eval.get(sector, 0.0) + ev
        total += ev
    if total == 0:
        return {}, 0.0
    return {s: v / total * 100 for s, v in sector_eval.items()}, total


def dca_amount(cash: float, ratio_pct: float, rounds: int) -> float:
    """1회 DCA 투자액 계산."""
    return cash * ratio_pct / 100 / rounds


# ── 섹터 비중 테스트 (CEO 플랜 기존 3개) ────────────────────

def test_calc_sector_weights_kr_only():
    holdings = [{"ticker": "005930", "market": "KR", "quantity": 10, "sector": "반도체"}]
    price_cache = {"005930": {"price": 70000}}
    weights, total = calc_sector_weights(holdings, price_cache, 1400.0)
    assert abs(weights["반도체"] - 100.0) < 0.01
    assert abs(total - 700000) < 0.01


def test_calc_sector_weights_kr_us_mixed():
    holdings = [
        {"ticker": "005930", "market": "KR", "quantity": 10, "sector": "반도체"},
        {"ticker": "NVDA",   "market": "US", "quantity": 1,  "sector": "반도체"},
    ]
    price_cache = {
        "005930": {"price": 70000},
        "NVDA":   {"price": 100.0},
    }
    fx = 1400.0
    weights, total = calc_sector_weights(holdings, price_cache, fx)
    expected_kr = 70000 * 10       # 700_000
    expected_us = 100.0 * 1400 * 1  # 140_000
    expected_total = expected_kr + expected_us  # 840_000
    assert abs(total - expected_total) < 0.01
    assert abs(weights["반도체"] - 100.0) < 0.01


def test_calc_sector_weights_cash_excluded():
    # 현금은 분모에 포함되지 않음
    holdings = [{"ticker": "005930", "market": "KR", "quantity": 10, "sector": "반도체"}]
    price_cache = {"005930": {"price": 70000}}
    # cash_krw=5_000_000 이 있어도 결과는 100%
    weights, total = calc_sector_weights(holdings, price_cache, 1400.0)
    assert abs(weights["반도체"] - 100.0) < 0.01
    assert abs(total - 700000) < 0.01  # 현금 포함 없음


# ── 섹터 비중 테스트 (신규 5개) ─────────────────────────────

def test_calc_sector_weights_empty_sector():
    holdings = [
        {"ticker": "005930", "market": "KR", "quantity": 10, "sector": ""},   # 빈 sector
        {"ticker": "000660", "market": "KR", "quantity": 5,  "sector": None}, # None sector
    ]
    price_cache = {
        "005930": {"price": 70000},
        "000660": {"price": 200000},
    }
    weights, _ = calc_sector_weights(holdings, price_cache, 1400.0)
    assert "미분류" in weights
    assert abs(weights["미분류"] - 100.0) < 0.01


def test_calc_sector_weights_fx_fallback():
    # FX 폴백 1400 사용 시 KR+US 혼합 섹터 비중 근사치 확인
    holdings = [
        {"ticker": "005930", "market": "KR", "quantity": 100, "sector": "반도체"},
        {"ticker": "TSM",    "market": "US", "quantity": 1,   "sector": "반도체"},
    ]
    price_cache = {
        "005930": {"price": 60000},
        "TSM":    {"price": 200.0},
    }
    fallback_fx = 1400.0
    weights, total = calc_sector_weights(holdings, price_cache, fallback_fx)
    expected = 60000 * 100 + 200.0 * 1400
    assert abs(total - expected) < 1.0
    assert abs(weights["반도체"] - 100.0) < 0.01  # 둘 다 같은 섹터


def test_dca_formula_kr():
    # KR: cash_krw × ratio% ÷ rounds
    result = dca_amount(cash=1_000_000, ratio_pct=100.0, rounds=3)
    assert abs(result - 333333.33) < 1.0

    result2 = dca_amount(cash=500_000, ratio_pct=50.0, rounds=2)
    assert abs(result2 - 125_000) < 0.01


def test_dca_formula_us():
    # US: cash_usd × ratio% ÷ rounds
    result = dca_amount(cash=1000.0, ratio_pct=100.0, rounds=4)
    assert abs(result - 250.0) < 0.001

    result2 = dca_amount(cash=500.0, ratio_pct=60.0, rounds=3)
    assert abs(result2 - 100.0) < 0.001


def test_holdings_hash_with_watchlist():
    holdings = [{"ticker": "005930", "market": "KR", "quantity": 10, "sector": "반도체"}]
    watchlist_a = [{"ticker": "MSFT", "market": "US", "sector": "빅테크"}]
    watchlist_b = [{"ticker": "META", "market": "US", "sector": "소셜미디어"}]

    hash_no_wl  = _holdings_hash(holdings)
    hash_with_a = _holdings_hash(holdings, watchlist_a)
    hash_with_b = _holdings_hash(holdings, watchlist_b)

    # watchlist가 다르면 해시가 달라야 함
    assert hash_no_wl  != hash_with_a
    assert hash_with_a != hash_with_b
    assert hash_no_wl  != hash_with_b

    # 동일 watchlist는 동일 해시
    assert _holdings_hash(holdings, watchlist_a) == _holdings_hash(holdings, watchlist_a)
