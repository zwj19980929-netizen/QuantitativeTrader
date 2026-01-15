from __future__ import annotations
from functools import lru_cache
from typing import Dict, List
import pandas as pd

from .http import HttpClient
from .parsers import _diff_to_rows

# 这些 fs 组合对应沪/深/京的股票列表（来自东财行情中心抓包/AKShare 适配逻辑）
FS_SH = "m:1 t:2,m:1 t:23"          # 沪A + 科创板等
FS_SZ = "m:0 t:6,m:0 t:80"          # 深A + 创业板等
FS_BJ = "m:0 t:81 s:2048"           # 北交所（示例组合）

@lru_cache()
def code_id_map(http: HttpClient) -> Dict[str, int]:
    """构造 symbol -> market_id 映射，供 secid=market_id.symbol 使用。"""
    mapping: Dict[str, int] = {}

    def fetch(fs: str, market_id: int, max_pages: int) -> None:
        path = "/api/qt/clist/get"
        # 只要 f12(代码) 就够了
        params = {
            "pn": "1",
            "pz": "200",
            "po": "1",
            "np": "2",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": fs,
            "fields": "f12",
            "_": "0",
        }
        for pn in range(1, max_pages + 1):
            params["pn"] = str(pn)
            j = http.get_json(path, params)
            data = (j or {}).get("data") or {}
            rows = _diff_to_rows(data.get("diff"))
            if not rows:
                break
            for r in rows:
                code = str(r.get("f12") or "").strip()
                if code:
                    mapping[code] = market_id

    # 沪市 market_id=1，深/北常见为 0（东财 secid 规则）
    fetch(FS_SH, 1, max_pages=60)
    fetch(FS_SZ, 0, max_pages=60)
    fetch(FS_BJ, 0, max_pages=30)
    return mapping

def secid_of(symbol: str, http: HttpClient) -> str:
    mp = code_id_map(http)
    mid = mp.get(symbol)
    if mid is None:
        raise KeyError(f"Unknown symbol: {symbol}. Try calling a_spot() first to refresh code list.")
    return f"{mid}.{symbol}"
