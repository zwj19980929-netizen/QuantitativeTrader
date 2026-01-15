from __future__ import annotations
from typing import Any, Dict, List, Tuple
import pandas as pd

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
