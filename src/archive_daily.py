import akshare as ak
import pandas as pd
from tqdm import tqdm
from src.database import MarketDB
import time
import argparse

def archive_daily(test_mode=False):
    db = MarketDB()
    print("[Archive Daily] Fetching stock list via Akshare...", flush=True)

    # 获取实时行情以得到所有代码
    spot_df = ak.stock_zh_a_spot_em()
    if spot_df.empty:
        print("[Archive Daily] Failed to fetch stock list.")
        return

    # 保存股票基础信息
    print(f"[Archive Daily] Updating info for {len(spot_df)} stocks...", flush=True)
    db.save_stock_info(spot_df)

    tickers = spot_df["代码"].tolist()
    if test_mode:
        tickers = tickers[:2] # Test with 2 stocks

    # 10年数据
    start_date = "20140101"
    end_date = "20251231"

    print(f"[Archive Daily] Starting history archive from {start_date}...", flush=True)

    pbar = tqdm(tickers)
    for ticker in pbar:
        pbar.set_description(f"Processing {ticker}")
        try:
            # 前复权数据
            df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if not df.empty:
                # rename columns to standard
                # Akshare returns: 日期, 开盘, 收盘, 最高, 最低, 成交量, ...
                rename_map = {
                    "日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume"
                }
                df = df.rename(columns=rename_map)
                db.save_data(ticker, df)

            # Rate limit politeness
            time.sleep(0.1)

        except Exception as e:
            # print(f"Error {ticker}: {e}")
            pass

    print("[Archive Daily] Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode (first 2 stocks)")
    args = parser.parse_args()
    archive_daily(args.test)
