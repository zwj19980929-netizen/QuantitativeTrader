from __future__ import annotations
from pathlib import Path
import pandas as pd

def save_df(df: pd.DataFrame, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()

    if suffix == ".csv":
        df.to_csv(out, index=False, encoding="utf-8-sig")
    elif suffix in (".parquet", ".pq"):
        df.to_parquet(out, index=False)
    else:
        raise ValueError("out 必须以 .csv / .parquet 结尾")
    return out