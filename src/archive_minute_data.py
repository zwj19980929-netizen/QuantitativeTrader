import argparse
import time
import pandas as pd
from tqdm import tqdm
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient
from src.eastmoney_a_crawler.eastmoney_a.parsers import parse_klines_to_df
from src.eastmoney_a_crawler.eastmoney_a.secid import secid_of
from src.database import MarketDB

def fetch_minute_history_safe(client: EastmoneyClient, symbol: str, start: str = "20140101"):
    """
    Safely fetch minute history.
    Note: EastMoney API currently restricts public minute-level data (klt=1, 5, 15, 30, 60)
    to approximately 1.5 months (31 trading days).
    Deep history (10 years) is not available via this endpoint.
    We fetch the maximum available 5-minute data (klt=5) as it offers the best balance of
    granularity and retention (approx 1500 records) compared to 1-minute data (only 1 day).
    """
    path = "/api/qt/stock/kline/get"
    secid = secid_of(symbol, client.http)

    # Use parameters found to maximize return (approx 1.5 months)
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "rtntype": "6",
        "secid": secid,
        "klt": "5",       # 5-minute data
        "fqt": "1",       # qfq
        "beg": "0",       # Start from beginning available
        "end": "20500000", # Get up to future
        "ut": "7eea3edcaed734bea9cbfc24409ed989", # Token required for extended history
        # "lmt" is implicitly handled or capped by API at ~1500
    }

    try:
        j = client.http_his.get_json(path, params)
        data = (j or {}).get("data") or {}
        klines = data.get("klines") or []

        if not klines:
            return pd.DataFrame()

        df = parse_klines_to_df(klines)

        if not df.empty:
            # Drop duplicates and sort just in case
            df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)

            # Filter by start date if user requested (though API retention is likely shorter than start request)
            # df = df[df["datetime"].dt.strftime("%Y%m%d") >= start]

        return df

    except Exception as e:
        print(f"[Archive] API Error for {symbol}: {e}")
        return pd.DataFrame()

def fetch_and_store_history(client: EastmoneyClient, db: MarketDB, ticker: str, start_date: str = "20140101"):
    try:
        # Use our safe function
        df = fetch_minute_history_safe(client, ticker, start=start_date)

        if df.empty:
            # print(f"[Archive] No data found for {ticker}")
            return False

        if "datetime" in df.columns:
            df.rename(columns={"datetime": "date"}, inplace=True)

        df["date"] = pd.to_datetime(df["date"])

        db.save_minute_data(ticker, df)
        return True

    except Exception as e:
        print(f"[Archive] Error processing {ticker}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Archive EastMoney minute data")
    parser.add_argument("--ticker", type=str, help="Specific ticker to archive (e.g., 600519)")
    parser.add_argument("--all", action="store_true", help="Archive all A-share stocks")
    parser.add_argument("--start", type=str, default="20140101", help="Start date (YYYYMMDD), default 20140101")

    args = parser.parse_args()

    client = EastmoneyClient()
    db = MarketDB()

    tickers = []

    if args.ticker:
        tickers = [args.ticker]
    elif args.all:
        print("[Archive] Fetching full stock list...")
        spot_df = client.a_spot()
        if not spot_df.empty and "代码" in spot_df.columns:
            tickers = spot_df["代码"].tolist()
            print(f"[Archive] Found {len(tickers)} tickers.")
        else:
            print("[Archive] Failed to fetch stock list.")
            return
    else:
        print("[Archive] Please specify --ticker or --all")
        return

    print(f"[Archive] Starting archive process for {len(tickers)} tickers...")
    print(f"[Archive] Note: API limits minute data to approx 1.5 months history.")

    success_count = 0

    pbar = tqdm(tickers)
    for ticker in pbar:
        pbar.set_description(f"Processing {ticker}")
        if fetch_and_store_history(client, db, ticker, args.start):
            success_count += 1

        time.sleep(0.5)

    print(f"[Archive] Completed. Successfully archived {success_count}/{len(tickers)} tickers.")

if __name__ == "__main__":
    main()
