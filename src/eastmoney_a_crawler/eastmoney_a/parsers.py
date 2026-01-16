from __future__ import annotations
from typing import Any, Dict, List, Tuple
import pandas as pd
from datetime import timedelta

KLINE_COLS = [
    "datetime",   # f51
    "open",       # f52
    "close",      # f53
    "high",       # f54
    "low",        # f55
    "volume",     # f56
    "amount",     # f57
    "amplitude",  # f58
    "pct_chg",    # f59
    "chg",        # f60
    "turnover",   # f61
]

def _diff_to_rows(diff: Any) -> List[Dict[str, Any]]:
    """Eastmoney diff 可能是 list 或 dict（key 为字符串数字）"""
    if diff is None:
        return []
    if isinstance(diff, list):
        return [x for x in diff if isinstance(x, dict)]
    if isinstance(diff, dict):
        # 按 key 排序拼成 list
        items = []
        for k in sorted(diff.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
            v = diff[k]
            if isinstance(v, dict):
                items.append(v)
        return items
    return []

def to_df_spot(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return df



def parse_klines_to_df(klines: list[str]) -> pd.DataFrame:
    """
    东方财富 kline/get: data.klines 里每个元素形如：
    "2023-03-06,14.30,13.85,14.30,13.72,1455824,2023954547.20,4.06,-3.08,-0.44,0.75"
    其中 f51 是日期/日期时间，f52~f61 对应开收高低量额等。:contentReference[oaicite:1]{index=1}
    """
    if not klines:
        return pd.DataFrame(columns=KLINE_COLS)

    rows = [x.split(",") for x in klines]
    df = pd.DataFrame(rows, columns=KLINE_COLS[: len(rows[0])])

    # datetime（分钟线通常是 YYYY-MM-DD HH:MM；日线是 YYYY-MM-DD）
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    # 其余列转数值
    for c in df.columns:
        if c != "datetime":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

def yyyymmdd_of(dt) -> str:
    """把 datetime/时间字符串 转成 'YYYYMMDD'"""
    ts = pd.to_datetime(dt, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"bad datetime: {dt}")
    return ts.strftime("%Y%m%d")

def end_minus_one_day_yyyymmdd(dt) -> str:
    """把某个时间点往前挪一天，返回 'YYYYMMDD'（用于分钟线翻页 end=...）"""
    ts = pd.to_datetime(dt, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"bad datetime: {dt}")
    ts = ts - timedelta(days=1)
    return ts.strftime("%Y%m%d")
