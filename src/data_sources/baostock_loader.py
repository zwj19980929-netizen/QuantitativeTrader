import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from src.data_sources.base import BaseDataLoader
import re

class BaostockLoader(BaseDataLoader):
    def get_source_name(self) -> str:
        return "Baostock"

    def fetch_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        # Baostock 只支持 A股
        if not re.match(r"^\d{6}$", ticker):
            print("[Baostock] 仅支持 A股代码。")
            return pd.DataFrame()

        print(f"[Baostock] 正在获取 {ticker} ...")

        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            print(f"[Baostock] 登录失败: {lg.error_msg}")
            return pd.DataFrame()

        try:
            # 转换 ticker 格式: 600519 -> sh.600519
            if ticker.startswith("6"):
                code = f"sh.{ticker}"
            else:
                code = f"sz.{ticker}"

            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")

            rs = bs.query_history_k_data_plus(code,
                "date,open,high,low,close,volume",
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="3")

            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 类型转换
            df["date"] = pd.to_datetime(df["date"])
            df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

            df = df.rename(columns={
                "date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
            })
            df.set_index("Date", inplace=True)
            return df

        finally:
            bs.logout()
