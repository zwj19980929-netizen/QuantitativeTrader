import yfinance as yf
from src.database import MarketDB
import pandas as pd
import time
import requests

class MarketDataLoader:
    def __init__(self, db: MarketDB):
        self.db = db

    def fetch_and_store(self, ticker: str, period="1y", retries=3):
        """
        从 Yahoo Finance 获取数据并存储到 DuckDB。
        包含重试机制和 User-Agent 伪装以规避速率限制。
        """
        print(f"正在从 Yahoo Finance 获取 {ticker} 的 {period} 数据...")

        # 配置 Session 以伪装成浏览器 (注意: yfinance 新版建议不要手动传递 session，除非使用兼容的 session 对象)
        # 我们暂时移除 session 传递，依靠重试机制。

        for attempt in range(retries):
            try:
                # yfinance 下载
                df = yf.download(ticker, period=period, progress=False, multi_level_index=False)

                if df.empty:
                    print(f"警报: 第 {attempt + 1} 次尝试未找到 {ticker} 的数据。")
                    if attempt < retries - 1:
                        sleep_time = 2 * (attempt + 1)
                        print(f"等待 {sleep_time} 秒后重试...")
                        time.sleep(sleep_time)
                        continue
                    return False

                self.db.save_data(ticker, df)
                return True

            except Exception as e:
                print(f"API 错误 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    return False
        return False

    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """
        从数据库检索数据。如果为空，则先尝试获取。
        如果获取失败，但数据库中有旧数据，则返回旧数据（降级模式）。
        """
        # 1. 尝试更新数据
        success = self.fetch_and_store(ticker)

        # 2. 从 DB 加载
        df = self.db.load_data(ticker)

        if not success:
            if not df.empty:
                print(f"警告: 无法获取最新实时数据。正在使用数据库中的缓存数据 (最新日期: {df.index[-1]})。")
            else:
                print("严重错误: 无法获取数据且本地缓存为空。")

        return df
