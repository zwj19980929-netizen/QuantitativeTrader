from abc import ABC, abstractmethod
import pandas as pd

class BaseDataLoader(ABC):
    """
    数据加载器抽象基类
    """
    @abstractmethod
    def fetch_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        获取数据并返回标准的 DataFrame (Index: Date, Columns: Open, High, Low, Close, Volume)
        如果获取失败，返回空的 DataFrame。
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        pass

    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名
        """
        if df.empty:
            return df

        # 尝试统一列名
        rename_map = {
            "date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
            "日期": "Date", "开盘": "Open", "最高": "High", "最低": "Low", "收盘": "Close", "成交量": "Volume"
        }

        # 很多接口列名千奇百怪，这里做一个简单的模糊匹配或重命名
        new_cols = {}
        for col in df.columns:
            lower_col = col.lower()
            if lower_col in rename_map:
                new_cols[col] = rename_map[lower_col]
            else:
                # 尝试中文匹配
                for k, v in rename_map.items():
                    if k in col: # 比如 "收盘价" 包含 "收盘"
                        new_cols[col] = v
                        break

        if new_cols:
            df = df.rename(columns=new_cols)

        # 确保包含核心列
        required = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in df.columns for col in required):
            # 如果缺少，可能需要进一步处理，这里简单打印警告
            pass
            # print(f"警告: 数据源可能缺少核心列。现有列: {df.columns}")

        return df
