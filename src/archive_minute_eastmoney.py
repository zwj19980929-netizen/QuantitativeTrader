
import sys
import os
import time
import logging
import pandas as pd
from datetime import datetime, timedelta

# Ensure src is in path
sys.path.append(os.getcwd())

from src.database import MarketDB
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient

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

def get_target_tickers(db: MarketDB):
    """
    Get list of tickers to update.
    Prioritize HS300 or specific active stocks if full list is too large.
    For now, let's try to get all tickers from the instruments table,
    or fall back to a smaller list if empty.
    """
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

    # Fallback: Use AkShare to get A-share list if possible, or just a hardcoded test list
    # Since we don't want to depend on AkShare here strictly (using EM crawler),
    # we can use the EM crawler's secid map keys if we can access them?
    # But secid map is built on demand.

    # Let's use a small hardcoded list for demonstration/initial run if DB is empty
    # In a real full run, we'd populate instruments first (e.g. using archive_daily.py).
    logger.info("Using fallback ticker list (HS300 top constituents).")
    return ["600519", "000858", "601318", "002594", "300750", "000001"]

def archive_minute_data():
    db = MarketDB()
    client = EastmoneyClient()

    tickers = get_target_tickers(db)

    start_date_default = "20160101" # 10 years roughly

    for i, ticker in enumerate(tickers):
        try:
            logger.info(f"[{i+1}/{len(tickers)}] Processing {ticker}...")

            # Check latest date in DB
            latest_dt = db.get_latest_minute_date(ticker)
            start_date = start_date_default

            if latest_dt:
                # Resume from next day
                next_day = latest_dt + timedelta(days=1)
                start_date = next_day.strftime("%Y%m%d")

                # If next day is in future, skip
                if next_day > datetime.now():
                    logger.info(f"Skipping {ticker}, already up to date ({latest_dt}).")
                    continue

            # Fetch data
            # klt=1 for 1 minute
            logger.info(f"Fetching {ticker} from {start_date}...")

            # Note: kline_minute_history handles pagination internally
            df = client.kline_minute_history(
                symbol=ticker,
                klt=1,
                start=start_date,
                end="20991231", # Fetch until now
                lmt=3000 # Max limit per request
            )

            if not df.empty:
                logger.info(f"Fetched {len(df)} records for {ticker}. Saving...")

                # Ensure columns map correctly (MarketDB expects specific names or handles generic)
                # EastMoney crawler returns: datetime, open, close, high, low, volume, amount, turnover...
                # MarketDB.save_minute_data handles case-insensitive match for standard columns.
                # But EM returns "datetime", DB expects "date" or "Date" or "datetime".
                # My DB update added handling for "datetime".

                db.save_minute_data(ticker, df)
                logger.info(f"Saved {ticker}.")
            else:
                logger.info(f"No new data for {ticker}.")

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            # Continue to next ticker
            continue

        # Small sleep to be nice
        time.sleep(0.5)

if __name__ == "__main__":
    archive_minute_data()
