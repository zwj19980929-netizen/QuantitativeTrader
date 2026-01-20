from src.database import MarketDB
from src.tools import calculate_technical_indicators
from tqdm import tqdm
import pandas as pd

class StockScanner:
    def __init__(self, db: MarketDB):
        self.db = db

    def scan_market(self, top_n=5, limit=5000):
        print(f"[Scanner] Scanning up to {limit} stocks for opportunities...")
        tickers = self.db.get_existing_tickers()
        if not tickers:
            print("[Scanner] No tickers in DB. Please run data ingestion first.")
            return []

        # Limit scope if needed
        tickers = tickers[:limit]

        scored_stocks = []

        print("[Scanner] Analyzing market data...")
        for ticker in tqdm(tickers):
            # Load recent daily data
            df = self.db.load_data(ticker, limit=100)
            if df.empty or len(df) < 50:
                continue

            try:
                # Calculate indicators
                analysis = calculate_technical_indicators(df)
                if not analysis: continue

                # Scoring Logic (Simple Alpha Model)
                # 1. Trend: Price > SMA_50 (Bullish Context)
                # 2. Reversion: RSI < 40 (Short-term Oversold) -> Buy dip
                # 3. Momentum: Recent positive return?

                current_price = analysis.get("current_price", 0)
                rsi = analysis.get("rsi_14", 50)
                sma_20 = analysis.get("sma_20", 0)

                score = 0

                # Strategy: Buy Dip in Uptrend
                if current_price > sma_20:
                    score += 10 # Uptrend

                if rsi < 40:
                    score += 5 # Oversold
                elif rsi > 70:
                    score -= 5 # Overbought

                # Recent return (momentum)
                if len(df) > 5:
                    ret_5d = (current_price - df.iloc[-5]["Close"]) / df.iloc[-5]["Close"]
                    score += ret_5d * 100 # Add percentage return points

                if score > 10: # Minimum threshold
                    scored_stocks.append({
                        "ticker": ticker,
                        "score": score,
                        "price": current_price,
                        "rsi": rsi,
                        "reason": f"Score {score:.1f} (RSI={rsi:.1f})"
                    })
            except Exception as e:
                continue

        # Sort by score descending
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)

        results = scored_stocks[:top_n]
        print(f"\n[Scanner] Top {len(results)} Picks:")
        for res in results:
            print(f"  - {res['ticker']}: {res['reason']}")

        return [res["ticker"] for res in results]

if __name__ == "__main__":
    db = MarketDB()
    scanner = StockScanner(db)
    scanner.scan_market()
