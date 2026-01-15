import yfinance as yf
from src.database import MarketDB
import pandas as pd

class MarketDataLoader:
    def __init__(self, db: MarketDB):
        self.db = db

    def fetch_and_store(self, ticker: str, period="1y"):
        """
        Fetches data from Yahoo Finance and stores it in DuckDB.
        """
        print(f"Fetching {period} data for {ticker} from Yahoo Finance...")
        # yfinance download
        df = yf.download(ticker, period=period, progress=False, multi_level_index=False)

        if df.empty:
            print(f"No data found for {ticker}.")
            return False

        self.db.save_data(ticker, df)
        return True

    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """
        Retrieves data from DB. If empty, tries to fetch first.
        """
        df = self.db.load_data(ticker)
        if df.empty:
            success = self.fetch_and_store(ticker)
            if success:
                df = self.db.load_data(ticker)
        return df
