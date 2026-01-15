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
        start_date = self._calculate_start_date(period)
        end_date = datetime.now().strftime("%Y%m%d")

        # 优先尝试东方财富接口 (stock_us_hist)，数据质量更高
        # 需要猜测市场代码: 105 (Nasdaq), 106 (NYSE), 107 (AMEX)
        prefixes = ["105", "106", "107"]

        for prefix in prefixes:
            symbol = f"{prefix}.{ticker}"
            try:
                # print(f"尝试东财接口: {symbol}")
                df = ak.stock_us_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                if not df.empty:
                    df = df.rename(columns={
                        "日期": "Date", "开盘": "Open", "收盘": "Close",
                        "最高": "High", "最低": "Low", "成交量": "Volume"
                    })
                    df["Date"] = pd.to_datetime(df["Date"])
                    df.set_index("Date", inplace=True)
                    return df[["Open", "High", "Low", "Close", "Volume"]]
            except:
                continue

        # 如果东财全部失败，回退到新浪 (stock_us_daily)
        print("[AKShare] 东财接口未命中，尝试新浪接口...")
        try:
            df = ak.stock_us_daily(symbol=ticker.upper(), adjust="qfq") # 新浪可能需要大写? 之前试的是小写
            df["date"] = pd.to_datetime(df["date"])
            start_dt = pd.to_datetime(start_date)
            df = df[df["date"] >= start_dt]

            df = df.rename(columns={
                "date": "Date", "open": "Open", "close": "Close",
                "high": "High", "low": "Low", "volume": "Volume"
            })
            df.set_index("Date", inplace=True)
            return df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            print(f"[AKShare] 美股获取失败: {e}")

        return pd.DataFrame()
