from __future__ import annotations
from typing import Any, Dict, Optional

import pandas as pd

from .http import HttpClient, HttpConfig
from .parsers import parse_klines_to_df, yyyymmdd_of, end_minus_one_day_yyyymmdd
from .secid import secid_of
from .spot import fetch_a_spot
from .quote import fetch_stock_quote



class EastmoneyClient:
    def __init__(self, timeout: float = 15.0, min_interval: float = 0.25):
        cfg = HttpConfig(timeout=timeout, min_interval=min_interval)
        self.http = HttpClient(config=cfg)

        # 新增：历史K线专用 host
        self.http_his = HttpClient(
            base_hosts=[
                "https://push2his.eastmoney.com",
                "https://50.push2his.eastmoney.com",
                "https://80.push2his.eastmoney.com",
            ],
            config=cfg
        )

    def a_spot(self, pages: int = 200, page_size: int = 200) -> pd.DataFrame:
        return fetch_a_spot(self.http, pages=pages, page_size=page_size)

    def stock_quote(self, symbol: str) -> Dict[str, Any]:
        # 为了 secid 映射可用，建议先跑一次 a_spot() 或者让 secid.py 自己去拉 code list
        return fetch_stock_quote(self.http, symbol=symbol)

    def kline_daily(self, symbol: str, beg="20160101", end="29991010", fqt=1, lmt=10000) -> pd.DataFrame:
        path = "/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "beg": beg,
            "end": end,
            "rtntype": "6",
            "secid": secid_of(symbol, self.http),  # 复用你现有的secid映射
            "klt": "101",  # 日线
            "fqt": str(fqt),  # 0不复权/1前复权/2后复权
            "lmt": str(lmt),
        }

        j = self.http_his.get_json(path, params)
        data = (j or {}).get("data") or {}
        kl = data.get("klines") or []
        if not kl:
            return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover"])

        rows = [x.split(",") for x in kl]
        df = pd.DataFrame(rows, columns=[
            "date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover"
        ])
        for c in df.columns[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    def kline_minute_history(
            self,
            symbol: str,
            klt: int = 1,  # 1/5/15/30/60
            fqt: int = 1,  # 0不复权 1前复权 2后复权
            start: str = "20160101",  # 近10年你就传 20160101
            end: str = "29991010",
            lmt: int = 3000,
    ):
        """
        分钟线历史：用 push2his 的 /api/qt/stock/kline/get
        klt: 1/5/15/30/60 分钟；101/102/103 是日/周/月。:contentReference[oaicite:3]{index=3}
        注意：lmt 默认 120，最大 3000，且 beg/end/lmt 典型是“三选二”。:contentReference[oaicite:4]{index=4}
        """
        if klt not in (1, 5, 15, 30, 60):
            raise ValueError("klt must be one of 1,5,15,30,60 for minute bars")

        path = "/api/qt/stock/kline/get"
        secid = secid_of(symbol, self.http)  # 复用你已有 secid 映射

        cur_end = end
        chunks = []

        while True:
            params = {
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "rtntype": "6",
                "secid": secid,
                "klt": str(klt),
                "fqt": str(fqt),
                "end": cur_end,
                "lmt": str(min(int(lmt), 3000)),  # 上限 3000 :contentReference[oaicite:5]{index=5}
            }

            j = self.http_his.get_json(path, params)
            data = (j or {}).get("data") or {}
            klines = data.get("klines") or []
            if not klines:
                break

            df = parse_klines_to_df(klines)
            if df.empty:
                break

            chunks.append(df)

            earliest = df["datetime"].min()
            if yyyymmdd_of(earliest) <= start:
                break

            # 往前翻页：下一次的 end 设为当前最早时间的前一天（避免重复）
            cur_end = end_minus_one_day_yyyymmdd(earliest)

        if not chunks:
            import pandas as pd
            return pd.DataFrame(columns=["datetime", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover"])

        import pandas as pd
        out = pd.concat(chunks, ignore_index=True)
        out = out.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
        return out


if __name__ == "__main__":
    cli = EastmoneyClient(min_interval=0.4)
    df_60 = cli.kline_minute_history("000001", klt=60, start="20160101", fqt=1)
    print(df_60)
