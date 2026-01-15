import yfinance as yf
import pandas as pd
from src.data_sources.base import BaseDataLoader
import time

class YFinanceLoader(BaseDataLoader):
    def get_source_name(self) -> str:
        return "YFinance"

    def fetch_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        带重试机制的 yfinance 获取。
        """
        print(f"[YFinance] 正在获取 {ticker} ...")

        # 简单重试逻辑
        for attempt in range(3):
            try:
                df = yf.download(ticker, period=period, progress=False, multi_level_index=False)
                if not df.empty:
                    return df[["Open", "High", "Low", "Close", "Volume"]]
                time.sleep(2)
            except Exception as e:
                print(f"[YFinance] 错误 (尝试 {attempt+1}): {e}")
                time.sleep(2)

        return pd.DataFrame()
