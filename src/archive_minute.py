import baostock as bs
import pandas as pd
from tqdm import tqdm
from src.database import MarketDB
import akshare as ak
import datetime
import argparse

def get_stock_list():
    try:
        df = ak.stock_zh_a_spot_em()
        return df["代码"].tolist()
    except:
        return []

def archive_minute(test_mode=False):
    db = MarketDB()
    print("[Archive Minute] Fetching stock list via Akshare (loading pages)...", flush=True)
    tickers = get_stock_list()
    if not tickers:
        print("[Archive Minute] Failed to get stock list.")
        return

    if test_mode:
        tickers = ["600519"] # Test with Moutai

    print("[Archive Minute] Logging into Baostock...", flush=True)
    lg = bs.login()
    if lg.error_code != '0':
        print(f"[Archive Minute] Login failed: {lg.error_msg}")
        return

    # Baostock 5-min data usually available from ~2019/2020
    # We try from 2019 to now
    default_start_year = 2024
    current_year = datetime.datetime.now().year

    print(f"[Archive Minute] Starting 5-min archive for {len(tickers)} stocks...", flush=True)

    pbar = tqdm(tickers)
    for ticker in pbar:
        pbar.set_description(f"Processing {ticker}")

        # Check resume point
        latest_date = db.get_latest_minute_date(ticker)
        start_year = default_start_year

        if latest_date:
            # If data is up-to-date (e.g., yesterday or today), skip
            if (datetime.datetime.now() - latest_date).days < 2:
                # pbar.set_description(f"Skipping {ticker} (Up-to-date)")
                continue
            start_year = latest_date.year

        # Convert to Baostock format
        if ticker.startswith("6"):
            code = f"sh.{ticker}"
        elif ticker.startswith("0") or ticker.startswith("3"):
            code = f"sz.{ticker}"
        else:
            continue

        all_dfs = []
        for year in range(start_year, current_year + 1):
            start_dt = f"{year}-01-01"
            end_dt = f"{year}-12-31"

            # If resuming in the same year, adjust start date
            if latest_date and year == latest_date.year:
                start_dt = (latest_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                # If start_dt > end_dt (e.g. latest was Dec 31), loop continues to next year effectively or returns empty
                if start_dt > end_dt:
                    continue

            try:
                # Using adjustflag="2" (qfq)
                rs = bs.query_history_k_data_plus(code,
                    "date,time,open,high,low,close,volume",
                    start_date=start_dt, end_date=end_dt,
                    frequency="5", adjustflag="2")

                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())

                if data_list:
                    df_year = pd.DataFrame(data_list, columns=rs.fields)
                    all_dfs.append(df_year)
            except Exception as e:
                pass

        if all_dfs:
            full_df = pd.concat(all_dfs)
            # Drop duplicates based on time
            full_df = full_df.drop_duplicates(subset=["time"])

            # Baostock time format: YYYYMMDDHHMMSSsss
            full_df["date"] = pd.to_datetime(full_df["time"], format="%Y%m%d%H%M%S000")

            rename_map = {
                "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
            }
            full_df = full_df.rename(columns=rename_map)

            full_df = full_df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

            db.save_minute_data(ticker, full_df)

    bs.logout()
    print("[Archive Minute] Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    args = parser.parse_args()
    archive_minute(args.test)
