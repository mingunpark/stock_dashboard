import yfinance as yf
from pykrx import stock
from datetime import datetime, timedelta

TICKER_KR = "005930"  # 삼성전자
TODAY = datetime.today().strftime("%Y%m%d")
YESTERDAY = (datetime.today() - timedelta(days=5)).strftime("%Y%m%d")  # 주말 포함 여유


def fetch_kr_price():
    print("=" * 50)
    print("[pykrx] 삼성전자 시세")
    print("=" * 50)

    df = stock.get_market_ohlcv(YESTERDAY, TODAY, TICKER_KR)
    if df.empty:
        print("데이터 없음 (장 마감 전이거나 휴장일)")
        return None

    latest = df.iloc[-1]
    print(f"날짜:       {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"시가:       {latest['시가']:,.0f} 원")
    print(f"고가:       {latest['고가']:,.0f} 원")
    print(f"저가:       {latest['저가']:,.0f} 원")
    print(f"종가:       {latest['종가']:,.0f} 원")
    print(f"거래량:     {latest['거래량']:,} 주")
    return float(latest["종가"])


def fetch_kr_fundamentals():
    print("\n" + "=" * 50)
    print("[pykrx] 삼성전자 펀더멘털 (PER, PBR, DIV)")
    print("=" * 50)

    df = stock.get_market_fundamental(YESTERDAY, TODAY, TICKER_KR)
    if df.empty:
        print("데이터 없음")
        return

    latest = df.iloc[-1]
    print(f"날짜:       {df.index[-1].strftime('%Y-%m-%d')}")
    for col in df.columns:
        print(f"{col}:  {latest[col]}")


def fetch_us_for_fx():
    print("\n" + "=" * 50)
    print("[yfinance] USD/KRW 환율")
    print("=" * 50)

    ticker = yf.Ticker("KRW=X")
    hist = ticker.history(period="2d")
    if hist.empty:
        print("환율 데이터 없음")
        return None

    rate = float(hist["Close"].iloc[-1])
    print(f"현재 환율:  {rate:,.2f} 원/달러")
    return rate


def fetch_kr_name():
    print("\n" + "=" * 50)
    print("[pykrx] 종목명 조회")
    print("=" * 50)

    name = stock.get_market_ticker_name(TICKER_KR)
    print(f"종목코드:   {TICKER_KR}")
    print(f"종목명:     {name}")


if __name__ == "__main__":
    print(f"수집 기준일: {TODAY}\n")

    price = fetch_kr_price()
    fetch_kr_fundamentals()
    fetch_kr_name()
    rate = fetch_us_for_fx()

    if price and rate:
        print("\n" + "=" * 50)
        print("[통합] 원화 기준 평가")
        print("=" * 50)
        print(f"삼성전자 종가:  {price:,.0f} 원")
        print(f"USD/KRW:       {rate:,.2f}")
        print(f"(참고) 100주 평가액: {price * 100:,.0f} 원")

    print("\n✅ 테스트 완료")
