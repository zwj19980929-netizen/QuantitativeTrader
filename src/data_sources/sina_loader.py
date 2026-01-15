import requests
import pandas as pd
from src.data_sources.base import BaseDataLoader
import re
import time

class SinaDirectLoader(BaseDataLoader):
    def get_source_name(self) -> str:
        return "SinaDirect"

    def fetch_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        # 仅针对美股演示 (A股通常 AKShare 很稳)
        if re.match(r"^\d{6}$", ticker):
            return pd.DataFrame()

        print(f"[SinaDirect] 正在直接请求新浪接口: {ticker} ...")

        # 新浪美股 K 线接口 (日线)
        # 这里的 ticker 需要小写，例如 aapl
        symbol = ticker.lower()
        timestamp = int(time.time() * 1000)
        url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/IO.XRV2.CallbackList['{symbol}']/US_MinKService.getDailyK?symbol={symbol}&_={timestamp}"

        try:
            headers = {
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": "Mozilla/5.0"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            text = resp.text

            # 解析 JSONP
            # 格式: IO.XRV2.CallbackList['aapl'](([{...},{...}]));
            start = text.find("(") + 1
            end = text.rfind(")")
            json_str = text[start:end]

            # 有时多一层括号
            if json_str.startswith("(") and json_str.endswith(")"):
                json_str = json_str[1:-1]

            import json
            data = json.loads(json_str)

            # 解析数据
            # data 是一个 list of dict: {d: "2020-01-01", o: "100", h: "101", l: "99", c: "100", v: "1000"}
            df = pd.DataFrame(data)
            df = df.rename(columns={
                "d": "Date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"
            })

            df["Date"] = pd.to_datetime(df["Date"])
            df = df.astype({"Open": float, "High": float, "Low": float, "Close": float, "Volume": float})

            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)

            # 过滤周期 (简单起见，返回所有或切片)
            if not df.empty:
                return df[["Open", "High", "Low", "Close", "Volume"]]

        except Exception as e:
            print(f"[SinaDirect] 失败: {e}")

        return pd.DataFrame()
