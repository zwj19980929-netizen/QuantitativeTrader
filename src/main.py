from src.graph import build_graph
from src.database import MarketDB, TraderDB
from src.market_data import MarketDataLoader
from src.news import fetch_market_news
import time

def run_live_cycle(ticker: str):
    print(f"\n========== LIVE TRADING CYCLE: {ticker} ==========")

    # 1. Initialize Infrastructure
    print("[System] Connecting to The Vault...")
    market_db = MarketDB() # duckdb
    # trader_db = TraderDB() # sqlite (instantiated inside agents, or here if we want to query)
    data_loader = MarketDataLoader(market_db)

    # 2. Acquire Intel (Market Data)
    print(f"[System] Fetching market data for {ticker}...")
    # Fetch ample data for technical analysis (e.g., 6 months)
    data_loader.fetch_and_store(ticker, period="6mo")
    df = market_db.load_data(ticker)

    if df.empty:
        print("[Error] Failed to load market data. Aborting.")
        return

    latest_price = df.iloc[-1]['Close']
    print(f"[Market] {ticker} Price: ${latest_price:.2f}")

    # 3. Acquire Intel (News)
    print(f"[System] Scanning news wires for {ticker}...")
    news = fetch_market_news(f"{ticker} stock news")
    print(f"[News] Found {len(news)} recent articles.")

    # 4. Initialize State
    initial_state = {
        "ticker": ticker,
        "data": df,
        "news": news,
        "analysis": {},
        "signal": None,
        "risk_assessment": None,
        "execution_result": None,
        "critique": None
    }

    # 5. Ignite the Agent System
    print("[System] Waking up Agents...")
    app = build_graph()
    final_state = app.invoke(initial_state)

    # 6. Report
    print("\n========== CYCLE REPORT ==========")
    signal = final_state.get("signal")
    risk = final_state.get("risk_assessment")
    exec_res = final_state.get("execution_result")
    critique = final_state.get("critique")

    if signal:
        print(f"STRATEGIST: {signal['action']} | {signal['reason']}")

    if risk:
        print(f"RISK MGR  : {'APPROVED' if risk['approved'] else 'REJECTED'} | {risk['reason']}")

    if exec_res:
        print(f"EXECUTOR  : FILLED {exec_res['action']} {exec_res['shares']} @ ${exec_res['price']:.2f}")
    else:
        print(f"EXECUTOR  : No Trade.")

    if critique:
        print(f"CRITIC    : {critique['feedback']}")

    print("==================================\n")

if __name__ == "__main__":
    # In a real deployed environment, this would loop:
    # while True:
    #   run_live_cycle("AAPL")
    #   time.sleep(3600)

    # For demo, run once
    run_live_cycle("AAPL")
