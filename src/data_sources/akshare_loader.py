import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from src.data_sources.base import BaseDataLoader
import re

class AKShareLoader(BaseDataLoader):
    def get_source_name(self) -> str:
        return "AKShare"

    def fetch_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        根据 ticker 格式自动选择 A股或美股接口。
        """
        try:
            # 1. 判断是否为 A股 (6位数字)
            if re.match(r"^\d{6}$", ticker):
                return self._fetch_ashare(ticker, period)
            else:
                return self._fetch_us_stock(ticker, period)
        except Exception as e:
            print(f"[AKShare] 获取 {ticker} 失败: {e}")
            return pd.DataFrame()

    def _calculate_start_date(self, period: str) -> str:
        today = datetime.now()
        if "d" in period:
            days = int(period.replace("d", ""))
            start = today - timedelta(days=days)
        elif "mo" in period:
            months = int(period.replace("mo", ""))
            start = today - timedelta(days=months*30)
        elif "y" in period:
            years = int(period.replace("y", ""))
            start = today - timedelta(days=years*365)
        else:
            start = today - timedelta(days=365)
        return start.strftime("%Y%m%d")

    def _fetch_ashare(self, ticker: str, period: str) -> pd.DataFrame:
        print(f"[AKShare] 正在获取 A股数据: {ticker} ...")
        start_date = self._calculate_start_date(period)
        end_date = datetime.now().strftime("%Y%m%d")

        # 东方财富接口
        df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

        # 标准化
        # akshare 返回: 日期, 开盘, 收盘, 最高, 最低, 成交量 ...
        df = df.rename(columns={
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume"
        })
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def _fetch_us_stock(self, ticker: str, period: str) -> pd.DataFrame:
        print(f"[AKShare] 正在获取美股数据: {ticker} ...")
        # 东方财富美股接口
        # 注意: akshare 的美股 symbol 可能需要特定格式，如 "105.AAPL" 或直接 "AAPL" 取决于具体函数
        # stock_us_hist 通常可用

        # 尝试 stock_us_daily (新浪) 或 stock_us_hist (东财)
        # 东财通常更稳定: stock_us_hist(symbol='105.AAPL') -> 105 是纳斯达克, 106 纽交所?
        # 为了通用性，先试用 stock_us_daily (新浪源，直接用 symbol)

        start_date = self._calculate_start_date(period)

        # 新浪接口 (有时不稳定，但 symbol 简单)
        # df = ak.stock_us_daily(symbol=ticker.lower(), adjust="qfq")

        # 换用 东方财富: stock_us_hist, 但需要知道 market id
        # 让我们使用 ak.stock_us_spot_em() 来查找市场 ID，但这太慢。
        # 简单起见，我们尝试 ak.stock_us_hist
        # 实际上 AKShare 的美股接口变动频繁。
        # 既然我们保留了 yfinance 作为备用，AKShare 这里可以尽量尝试。

        # 尝试使用 stock_us_spot_em 搜索 (太复杂)
        # 让我们使用 `stock_us_daily` (基于新浪)，如果失败则依赖 fallback。

        df = ak.stock_us_daily(symbol=ticker.lower(), adjust="qfq")

        # 过滤日期
        df["date"] = pd.to_datetime(df["date"])
        start_dt = pd.to_datetime(start_date)
        df = df[df["date"] >= start_dt]

        df = df.rename(columns={
            "date": "Date", "open": "Open", "close": "Close",
            "high": "High", "low": "Low", "volume": "Volume"
        })
        df.set_index("Date", inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]]
