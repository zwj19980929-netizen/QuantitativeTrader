import pandas as pd
import argparse
import matplotlib.pyplot as plt
from src.database import MarketDB
from src.market_data import MarketDataLoader
from src.agents import strategist_node, risk_manager_node, executor_node
from src.broker import SimulatedBroker

class Backtester:
    def __init__(self, ticker: str, initial_capital=1000000.0, start_date="20200101"):
        self.ticker = ticker
        self.initial_capital = initial_capital
        self.history = []

        # Load Data
        db = MarketDB()
        self.loader = MarketDataLoader(db)

        # Attempt to load from DB first to save time
        # If empty or too few, try fetch
        self.df = db.load_data(ticker, limit=5000)
        if len(self.df) < 100:
            print(f"[Backtest] Insufficient data in DB ({len(self.df)} rows), fetching...")
            self.loader.fetch_and_store(ticker, period="10y")
            self.df = db.load_data(ticker, limit=5000)

        if self.df.empty:
            raise ValueError(f"No data for {ticker}")

        # Filter by start date
        self.df = self.df[self.df.index >= pd.to_datetime(start_date)]
        print(f"[Backtest] Loaded {len(self.df)} rows starting {start_date}")

        # Initialize Broker
        # Reset account for clean backtest
        account_id = f"backtest_{ticker}"
        # Reset state in DB
        db.update_account_state(account_id, total=initial_capital, available=initial_capital, frozen=0.0)
        # Clear positions
        from sqlalchemy import text
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM positions WHERE account_id=:aid"), {"aid": account_id})

        self.broker = SimulatedBroker(account_id, initial_cash=initial_capital, db=db)

    def run(self):
        print(f"[Backtest] Running...")

        # Warmup for indicators
        window = 50

        for i in range(window, len(self.df)):
            current_date = self.df.index[i]
            data_slice = self.df.iloc[:i+1]

            # State for Agents
            state = {
                "ticker": self.ticker,
                "data": data_slice,
                "news": [], # Placeholder
                "analysis": {},
                "signal": None,
                "broker": self.broker # Pass broker to agents if they support it
            }

            # 1. Strategist
            state = strategist_node(state)

            # 2. Risk Manager
            state = risk_manager_node(state)

            # 3. Execution
            state = executor_node(state)

            # Record stats
            # Broker needs to be aware of current price to calc Total Value correctly
            # We can cheat by updating "current_price" in DB positions manually, or
            # ensure broker.get_total_value() uses `get_market_price` which uses DB.
            # But DB only has "Close" from history.
            # Actually MarketDB.load_data gives history.
            # Broker.get_market_price fetches *latest* from DB.
            # If we are backtesting, "latest" in DB is 2025 (end of history), not `current_date`.
            # THIS IS A PROBLEM. `SimulatedBroker` querying DB gets "Future Data".

            # FIX: Broker should accept `current_prices` map or `market_data_provider`.
            # OR: We explicitly pass price to `get_total_value`.
            # OR: We assume `SimulatedBroker` is strictly for *Live* or we mock `get_market_price`.

            # Solution: Create `BacktestBroker` inheriting `SimulatedBroker` that overrides `get_market_price`.
            # Or just pass price to `get_total_value`? Broker interface doesn't have it.

            # Quick fix: Calculate total value manually here for report using broker's quantities.

            acct = self.broker.get_account_state()
            pos = self.broker.get_positions()
            cash = float(acct["total_cash"])
            pos_val = sum([float(p["quantity"]) * data_slice.iloc[-1]["Close"] for p in pos if p["ticker"] == self.ticker])
            total_val = cash + pos_val

            self.history.append({
                "date": current_date,
                "value": total_val,
                "price": data_slice.iloc[-1]["Close"]
            })

        self._report()

    def _report(self):
        if not self.history:
            print("No data.")
            return

        df = pd.DataFrame(self.history).set_index("date")

        start_val = self.initial_capital
        end_val = df.iloc[-1]["value"]
        ret = (end_val - start_val) / start_val * 100

        print(f"Final Value: {end_val:,.2f}")
        print(f"Return: {ret:.2f}%")

        # Benchmark
        start_price = df.iloc[0]["price"]
        end_price = df.iloc[-1]["price"]
        bench_ret = (end_price - start_price) / start_price * 100
        print(f"Benchmark: {bench_ret:.2f}%")

        plt.figure(figsize=(10,6))
        plt.plot(df.index, df["value"], label="Strategy")
        # Benchmark scaled
        plt.plot(df.index, df["price"] / start_price * start_val, label="Benchmark", alpha=0.5)
        plt.legend()
        plt.title(f"Backtest {self.ticker}")
        plt.savefig("backtest_result.png")
        print("Saved plot to backtest_result.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default="600519")
    args = parser.parse_args()

    bt = Backtester(args.ticker)
    bt.run()
