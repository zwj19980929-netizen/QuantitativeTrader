import argparse
import time
import pandas as pd
from tqdm import tqdm
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient
from src.eastmoney_a_crawler.eastmoney_a.parsers import parse_klines_to_df, yyyymmdd_of, end_minus_one_day_yyyymmdd
from src.eastmoney_a_crawler.eastmoney_a.secid import secid_of
from src.database import MarketDB

def fetch_minute_history_safe(client: EastmoneyClient, symbol: str, start: str = "20140101"):
    """
    Safely fetch minute history, handling API limitations (infinite loop prevention).
    Based on client.kline_minute_history logic but with loop protection.
    """
    klt = 1
    fqt = 1
    lmt = 3000
    end = "29991010"

    path = "/api/qt/stock/kline/get"
    # Reuse the client's http session and secid logic
    secid = secid_of(symbol, client.http)

    cur_end = end
    chunks = []
    last_earliest = None

    while True:
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "rtntype": "6",
            "secid": secid,
            "klt": str(klt),
            "fqt": str(fqt),
            "end": cur_end,
            "lmt": str(min(int(lmt), 3000)),
        }

        # Use client.http_his to make the request
        j = client.http_his.get_json(path, params)
        data = (j or {}).get("data") or {}
        klines = data.get("klines") or []
        if not klines:
            break

        df = parse_klines_to_df(klines)
        if df.empty:
            break

        earliest = df["datetime"].min()

        # Safety check: if we are not moving backwards, break to avoid infinite loop
        # This handles the case where API ignores 'end' and returns the same latest data
        if last_earliest is not None and earliest >= last_earliest:
            # print(f"[Archive] Detected infinite loop for {symbol} at {earliest}. Stopping.")
            break
        last_earliest = earliest

        chunks.append(df)

        if yyyymmdd_of(earliest) <= start:
            break

        # Move backwards
        cur_end = end_minus_one_day_yyyymmdd(earliest)

    if not chunks:
        return pd.DataFrame()

    out = pd.concat(chunks, ignore_index=True)
    out = out.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return out

def fetch_and_store_history(client: EastmoneyClient, db: MarketDB, ticker: str, start_date: str = "20140101"):
    try:
        # Use our safe function instead of client.kline_minute_history
        df = fetch_minute_history_safe(client, ticker, start=start_date)

        if df.empty:
            print(f"[Archive] No data found for {ticker}")
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

    print(f"[Archive] Starting archive process for {len(tickers)} tickers from {args.start}...")

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
