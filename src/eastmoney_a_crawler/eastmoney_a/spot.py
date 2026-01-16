from __future__ import annotations
from typing import Dict, Any, List
import pandas as pd

from .http import HttpClient
from .parsers import _diff_to_rows

# 全市场沪深京 A 股（来自东财行情中心抓包/AKShare 实现）
FS_A_ALL = "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048"

# 默认字段列表（东财 clist/get 的 fields）
FIELDS_A_SPOT = (
    "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,"
    "f12,f13,f14,f15,f16,f17,f18,"
    "f20,f21,f23,f24,f25,f22,f11,"
    "f62,f128,f136,f115,f152"
)

# 映射到更友好的列名（尽量保持与你在东财页面看到的一致）
COLS = {
    "f12": "代码",
    "f14": "名称",
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f11": "5分钟涨跌",
    "f15": "最高",
    "f16": "最低",
    "f17": "今开",
    "f18": "昨收",
    "f20": "总市值",
    "f21": "流通市值",
    "f23": "市净率",
    "f24": "涨速",
    "f25": "60日涨跌幅",
    "f62": "主力净流入",
    "f115": "年初至今涨跌幅",
}

NUMERIC_COLS = [
    "最新价","涨跌幅","涨跌额","成交量","成交额","振幅","换手率","市盈率-动态","量比",
    "5分钟涨跌","最高","最低","今开","昨收","总市值","流通市值","市净率","涨速",
    "60日涨跌幅","主力净流入","年初至今涨跌幅"
]

def fetch_a_spot(http: HttpClient, pages: int = 200, page_size: int = 200) -> pd.DataFrame:
    """
    抓取沪深京 A 股实时快照（分页拉取直到无数据）。
    pages/page_size 是安全阀，防止无限循环。
    """
    path = "/api/qt/clist/get"
    params: Dict[str, Any] = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "np": "2",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": FS_A_ALL,
        "fields": FIELDS_A_SPOT,
        "_": "0",
    }

    rows_all: List[Dict[str, Any]] = []
    for pn in range(1, pages + 1):
        params["pn"] = str(pn)
        j = http.get_json(path, params)
        data = (j or {}).get("data") or {}
        rows = _diff_to_rows(data.get("diff"))
        if not rows:
            break
        rows_all.extend(rows)

    df = pd.DataFrame(rows_all)

    # 只保留我们关心的列并改名
    keep = [c for c in COLS.keys() if c in df.columns]
    df = df[keep].rename(columns=COLS)

    # 数值列转 numeric
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 给个序号（方便对齐东财表格）
    df.insert(0, "序号", range(1, len(df) + 1))
    return df