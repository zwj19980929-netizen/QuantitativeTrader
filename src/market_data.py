import yfinance as yf
from src.database import MarketDB
import pandas as pd

class MarketDataLoader:
    def __init__(self, db: MarketDB):
        self.db = db

    def fetch_and_store(self, ticker: str, period="1y"):
        """
        从 Yahoo Finance 获取数据并存储到 DuckDB。
        """
        print(f"正在从 Yahoo Finance 获取 {ticker} 的 {period} 数据...")
        # yfinance 下载
        df = yf.download(ticker, period=period, progress=False, multi_level_index=False)

        if df.empty:
            print(f"未找到 {ticker} 的数据。")
            return False

        self.db.save_data(ticker, df)
        return True

    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """
        从数据库检索数据。如果为空，则先尝试获取。
        """
        df = self.db.load_data(ticker)
        if df.empty:
            success = self.fetch_and_store(ticker)
            if success:
                df = self.db.load_data(ticker)
        return df
