from src.database import MarketDB
from src.data_sources.akshare_loader import AKShareLoader
from src.data_sources.yfinance_loader import YFinanceLoader
from src.data_sources.baostock_loader import BaostockLoader
from src.data_sources.sina_loader import SinaDirectLoader
import pandas as pd
import re

class MarketDataLoader:
    def __init__(self, db: MarketDB):
        self.db = db
        # 优先级: AKShare -> Baostock (A股) -> SinaDirect (美股二备) -> YFinance (美股兜底)
        self.loaders = [
            AKShareLoader(),
            BaostockLoader(),
            SinaDirectLoader(),
            YFinanceLoader()
        ]

    def fetch_and_store(self, ticker: str, period="1y") -> bool:
        """
        尝试所有数据源获取数据。
        """
        print(f"[数据中心] 正在调度资源获取 {ticker} ...")

        # 针对 A股 (6位数字) 优化加载顺序
        is_ashare = bool(re.match(r"^\d{6}$", ticker))

        # 如果是 A股，优先 AKShare -> Baostock
        # 如果是 美股，优先 AKShare -> YFinance

        fetched_df = pd.DataFrame()
        used_source = ""

        for loader in self.loaders:
            source_name = loader.get_source_name()

            # 简单的路由优化
            if is_ashare and source_name == "YFinance":
                continue # yfinance A股支持不好，跳过
            if not is_ashare and source_name == "Baostock":
                continue # baostock 不支持美股

            try:
                fetched_df = loader.fetch_data(ticker, period)
                if not fetched_df.empty:
                    used_source = source_name
                    break
            except Exception as e:
                print(f"[{source_name}] 异常: {e}")
                continue

        if fetched_df.empty:
            print(f"[数据中心] 严重: 所有渠道均无法获取 {ticker} 数据。")
            return False

        print(f"[数据中心] 成功从 [{used_source}] 获取数据 ({len(fetched_df)} 行)。")
        self.db.save_data(ticker, fetched_df)
        return True

    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """
        从数据库加载，如果过旧或为空则更新。
        """
        # 1. 尝试更新
        self.fetch_and_store(ticker)

        # 2. 从 DB 加载
        return self.db.load_data(ticker)

    def import_external_data(self, ticker: str, df: pd.DataFrame):
        """
        导入外部数据（例如用户自定义爬虫的数据）。
        df 必须包含 Open, High, Low, Close, Volume 列，索引为 Date。
        """
        print(f"[数据中心] 正在导入 {ticker} 的外部数据...")
        if df.empty:
            print("警告: 导入的数据为空。")
            return

        # 简单的列名标准化尝试
        rename_map = {
            "date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
            "日期": "Date", "开盘": "Open", "最高": "High", "最低": "Low", "收盘": "Close", "成交量": "Volume"
        }
        df = df.rename(columns=rename_map)

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

        required = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in df.columns for col in required):
            print(f"错误: 数据缺少必要的列。需要: {required}, 实际: {df.columns}")
            return

        self.db.save_data(ticker, df)
        print(f"[数据中心] 成功导入 {len(df)} 行数据到数据库。")
