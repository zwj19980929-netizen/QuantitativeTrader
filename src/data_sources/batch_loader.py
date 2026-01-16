import akshare as ak
import pandas as pd
from src.database import MarketDB
from src.market_data import MarketDataLoader
import time
import argparse
from tqdm import tqdm

class AShareBatchLoader:
    def __init__(self):
        self.db = MarketDB()
        self.loader = MarketDataLoader(self.db)

    def get_stock_list(self, scope="hs300"):
        """
        获取股票列表。
        scope: "hs300" (沪深300), "all" (全市场)
        """
        print(f"[批量加载] 正在获取股票列表 ({scope})...")
        try:
            if scope == "hs300":
                # 获取沪深300成分股
                df = ak.index_stock_cons(symbol="000300")
                # akshare 返回列:品种代码,品种名称,纳入日期
                return df["品种代码"].tolist()
            elif scope == "all":
                # 获取全市场 (利用实时行情接口)
                df = ak.stock_zh_a_spot_em()
                return df["代码"].tolist()
            else:
                # 传入的是逗号分隔的代码字符串
                return scope.split(",")
        except Exception as e:
            print(f"[批量加载] 获取股票列表失败: {e}")
            return []

    def run(self, scope="hs300", period="3y"):
        tickers = self.get_stock_list(scope)
        if not tickers:
            print("未找到股票代码。")
            return

        print(f"[批量加载] 准备下载 {len(tickers)} 只股票的历史数据 (周期: {period})...")

        success_count = 0
        fail_count = 0

        # 使用 tqdm 显示进度条
        pbar = tqdm(tickers)
        for ticker in pbar:
            pbar.set_description(f"Processing {ticker}")

            # 检查是否需要增量更新 (Todo: 检查 DB 中最后日期)
            # 这里简单起见，直接调用 fetch_and_store，它会覆盖/合并

            try:
                # 增加一点延时防止被封
                time.sleep(0.5)
                result = self.loader.fetch_and_store(ticker, period=period)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"\n[错误] {ticker}: {e}")
                fail_count += 1

        print(f"\n[批量加载] 完成。成功: {success_count}, 失败: {fail_count}")
        self.db.get_stats()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=str, default="hs300", help="下载范围: hs300, all, 或代码列表(如 600519,000001)")
    parser.add_argument("--period", type=str, default="3y", help="数据周期")
    args = parser.parse_args()

    loader = AShareBatchLoader()
    loader.run(scope=args.scope, period=args.period)
