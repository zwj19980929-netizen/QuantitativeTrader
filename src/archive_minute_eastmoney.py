
import sys
import os
import time
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta

# Ensure src is in path
sys.path.append(os.getcwd())

from src.database import MarketDB
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient
from src.eastmoney_a_crawler.eastmoney_a.secid import code_id_map

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("archive_minute_eastmoney.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ArchiveMinuteEM")

def get_target_tickers(db: MarketDB, client: EastmoneyClient, fetch_all: bool = False):
    """
    Get list of tickers to update.
    If fetch_all is True, retrieves ALL A-share tickers from EastMoney.
    Otherwise, tries DB or fallback list.
    """
    if fetch_all:
        logger.info("Fetching ALL A-share tickers from EastMoney (this may take a moment)...")
        # code_id_map returns dict {code: market_id}
        # It handles pagination internally to get the full list
        try:
            full_map = code_id_map(client.http)
            tickers = list(full_map.keys())
            logger.info(f"Retrieved {len(tickers)} tickers from EastMoney.")
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch full ticker list: {e}")
            # Fall through to DB check

    # Try getting from DB instruments
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # Prefer active stocks
            res = conn.execute(text("SELECT ticker FROM instruments WHERE is_active=1")).fetchall()
        tickers = [r[0] for r in res]
        if tickers:
            logger.info(f"Found {len(tickers)} active tickers in DB.")
            return tickers
    except Exception as e:
        logger.warning(f"Could not fetch from instruments: {e}")

    logger.info("Using fallback ticker list (HS300 top constituents).")
    return ["600519", "000858", "601318", "002594", "300750", "000001"]

def archive_minute_data(months: int, fetch_all: bool):
    db = MarketDB()
    client = EastmoneyClient()

    tickers = get_target_tickers(db, client, fetch_all=fetch_all)

    # Calculate start date: 30 days * months ago
    days_back = months * 30
    cutoff_date = datetime.now() - timedelta(days=days_back)
    cutoff_date_str = cutoff_date.strftime("%Y%m%d")

    logger.info(f"Targeting data from {cutoff_date_str} (Last {months} months)")

    for i, ticker in enumerate(tickers):
        try:
            logger.info(f"[{i+1}/{len(tickers)}] Processing {ticker}...")

            # Check latest date in DB to support resume
            latest_dt = db.get_latest_minute_date(ticker)
            start_date = cutoff_date_str

            if latest_dt:
                # If we have data, we resume from the next day of the latest data
                # BUT, if the latest data is OLDER than our cutoff, we might still want the cutoff?
                # Actually, usually 'resume' means fill the gap.
                # If latest_dt < cutoff_date, we have a gap or just old data.
                # If we want "last 3 months", we should ensure we cover [cutoff, now].
                # If latest_dt is > cutoff, we start from latest_dt + 1.
                # If latest_dt is < cutoff, we start from latest_dt + 1? Or cutoff?
                # If we want to ensure "last 3 months" exists, and we have data from 2 years ago but stopped,
                # we should probably fetch from latest_dt to fill the history, OR just fetch the last 3 months if we don't care about the gap.
                # Given the user said "Get 3 months data", let's prioritize the 3 month window.
                # But filling gaps is better. Let's start from max(latest_dt+1, cutoff).

                next_day = latest_dt + timedelta(days=1)

                # If next_day is AFTER today, we are done.
                if next_day > datetime.now():
                    logger.info(f"Skipping {ticker}, already up to date ({latest_dt}).")
                    continue

                # If next_day is before cutoff, should we fill the long gap?
                # The user asked for "3 months". Fetching 10 years gap might take too long.
                # Let's enforce the 3-month window constraint strictly if the user explicitly asked for it.
                # If next_day is older than cutoff, we jump to cutoff?
                # If we have data up to 2020, and want 2023, leaving a gap is messy but fulfills the request "Get 3 months".
                # However, cleaner is to use max(cutoff, next_day) logic.

                if next_day < cutoff_date:
                    logger.info(f"Data in DB (ends {latest_dt}) is older than request window ({cutoff_date_str}). Filling gap/starting from cutoff.")
                    # Use cutoff to save time, unless we want full history.
                    # Given the explicit "3 months" request, let's start from cutoff.
                    start_date = cutoff_date_str
                else:
                    start_date = next_day.strftime("%Y%m%d")

            # Fetch data
            logger.info(f"Fetching {ticker} from {start_date}...")

            df = client.kline_minute_history(
                symbol=ticker,
                klt=1,
                start=start_date,
                end="20991231",
                lmt=3000
            )

            if not df.empty:
                logger.info(f"Fetched {len(df)} records for {ticker}. Saving...")
                db.save_minute_data(ticker, df)
                logger.info(f"Saved {ticker}.")
            else:
                logger.info(f"No new data for {ticker}.")

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            continue

        # Small sleep to be nice
        time.sleep(0.2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and archive EastMoney minute data.")
    parser.add_argument("--all", action="store_true", help="Fetch ALL A-share tickers.")
    parser.add_argument("--months", type=int, default=3, help="Number of months of history to fetch (default: 3).")

    args = parser.parse_args()

    archive_minute_data(months=args.months, fetch_all=args.all)
