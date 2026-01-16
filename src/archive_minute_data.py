import argparse
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient
from src.database import MarketDB
import time

def archive_minute_data(ticker: str, period: str = "15"):
    """
    抓取分钟线数据并存入数据库。
    period: 1, 5, 15, 30, 60
    """
    print(f"[归档] 正在启动 {ticker} 的 {period} 分钟线数据归档...")

    client = EastmoneyClient()
    db = MarketDB()

    # 尝试抓取尽可能多的数据 (例如 50000 条，覆盖数年)
    # 东财 API 可能有上限，我们尽力而为
    # 50000 可能过大被拒，尝试 2000
    df = client.fetch_kline_data(ticker, period=period, limit=2000)

    if not df.empty:
        # 去重
        df = df.drop_duplicates(subset=["Date"])

        # 存入数据库
        print(f"[归档] 准备存储 {len(df)} 行数据...")
        print(f"[调试] 数据预览:\n{df.head(2)}")
        db.save_minute_data(ticker, df)

        # 验证读取
        check = db.load_minute_data(ticker, limit=5)
        print("[验证] 最新 5 条数据:")
        print(check)
    else:
        print("[错误] 未获取到数据。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default="600519", help="股票代码")
    parser.add_argument("--period", type=str, default="15", help="分钟周期 (1/5/15/30/60)")
    args = parser.parse_args()

    archive_minute_data(args.ticker, args.period)
