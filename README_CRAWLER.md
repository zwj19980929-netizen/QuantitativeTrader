
# A-Share Minute Data Crawler (EastMoney Source)

This module allows you to fetch and store historical minute-level (1-minute) data for the entire A-share market (SH/SZ/BJ) using the EastMoney API.

## Features
- **Full Market Coverage**: Fetches 5000+ A-share tickers.
- **Adjustable Window**: Defaults to the last 3 months (approx 90 days), but configurable.
- **Resume Capability**: Skips already up-to-date stocks to enable resuming interrupted runs.
- **Rich Data**: Stores Open, High, Low, Close, Volume, Amount (成交额), and Turnover (换手率).
- **Database Storage**: Saves to PostgreSQL (production) or SQLite (local test).

## Prerequisites
1. Ensure dependencies are installed:
   ```bash
   pip install pandas requests sqlalchemy psycopg2-binary
   ```
2. (Optional) Set up your database URL environment variable. If not set, it defaults to `sqlite:///market_data_local.db`.
   ```bash
   export DB_URL="postgresql+psycopg2://user:pass@host:port/dbname"
   ```

## Usage

### 1. Fetch 3 Months of 1-Minute Data for ALL A-Shares
To execute the crawl for the entire market for the last 3 months:

```bash
python src/archive_minute_eastmoney.py --all --months 3
```

- `--all`: Tells the script to fetch the dynamic full list of A-shares from EastMoney (instead of using a small test list).
- `--months 3`: Sets the start date to 3 months ago.

### 2. Fetch for a Test List (HS300 Top Constituents)
If you just want to test the connection or setup without downloading everything:

```bash
python src/archive_minute_eastmoney.py --months 3
```
(Omit `--all`)

### 3. Fetch Longer History (e.g., 12 Months)
```bash
python src/archive_minute_eastmoney.py --all --months 12
```

## Storage
Data is stored in the `ohlcv_minute` table in your database.
Schema:
- `ticker` (VARCHAR)
- `date` (TIMESTAMP)
- `open`, `high`, `low`, `close` (DOUBLE)
- `volume` (DOUBLE)
- `amount` (DOUBLE) - 成交额
- `turnover` (DOUBLE) - 换手率

## Notes
- The script handles pagination automatically (EastMoney limits 3000 bars per request).
- It is single-threaded to avoid aggressive rate limiting. A full run for 5000 stocks * 3 months may take several hours.
- Logs are written to `archive_minute_eastmoney.log`.
