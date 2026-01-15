from __future__ import annotations
from typing import Any, Dict, Optional

import pandas as pd

from .http import HttpClient, HttpConfig
from .spot import fetch_a_spot
from .quote import fetch_stock_quote

class EastmoneyClient:
    def __init__(self, timeout: float = 15.0, min_interval: float = 0.25):
        cfg = HttpConfig(timeout=timeout, min_interval=min_interval)
        self.http = HttpClient(config=cfg)

    def a_spot(self, pages: int = 200, page_size: int = 200) -> pd.DataFrame:
        return fetch_a_spot(self.http, pages=pages, page_size=page_size)

    def stock_quote(self, symbol: str) -> Dict[str, Any]:
        # 为了 secid 映射可用，建议先跑一次 a_spot() 或者让 secid.py 自己去拉 code list
        return fetch_stock_quote(self.http, symbol=symbol)
