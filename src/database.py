import duckdb
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os

# --- Market Data (DuckDB) ---
class MarketDB:
    def __init__(self, db_path="market_data.ddb"):
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                PRIMARY KEY (ticker, date)
            )
        """)

    def save_data(self, ticker: str, df: pd.DataFrame):
        """
        Saves OHLCV dataframe to DuckDB.
        Expects index to be Date/Timestamp or a column named 'Date'.
        """
        # Ensure date is a column
        df_copy = df.copy()
        if "Date" not in df_copy.columns:
            df_copy.reset_index(inplace=True)

        # Add ticker column
        df_copy["ticker"] = ticker

        # Standardize columns
        df_copy = df_copy.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })

        # Select only relevant columns to avoid schema mismatch
        df_copy = df_copy[["ticker", "date", "open", "high", "low", "close", "volume"]]

        # Upsert (DuckDB doesn't have simple UPSERT for batch insert easily via Python API in older versions,
        # but INSERT OR REPLACE or DELETE+INSERT works).
        # For simplicity and speed in this project: Delete existing range then insert.

        min_date = df_copy["date"].min()
        max_date = df_copy["date"].max()

        self.conn.execute(
            "DELETE FROM ohlcv WHERE ticker = ? AND date >= ? AND date <= ?",
            [ticker, min_date, max_date]
        )

        self.conn.register("df_view", df_copy)
        self.conn.execute("INSERT INTO ohlcv SELECT * FROM df_view")
        self.conn.unregister("df_view")
        print(f"Stored {len(df_copy)} rows for {ticker} in MarketDB.")

    def load_data(self, ticker: str, limit: int = 100) -> pd.DataFrame:
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE ticker = '{ticker}'
            ORDER BY date DESC
            LIMIT {limit}
        """
        df = self.conn.execute(query).df()
        if not df.empty:
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            # Rename back to capitalized for compatibility with tools
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

# --- Trader Data (SQLite via SQLAlchemy) ---
Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    action = Column(String) # BUY/SELL
    price = Column(Float)
    shares = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    strategy_reason = Column(String)

class Reflection(Base):
    __tablename__ = 'reflections'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    content = Column(Text)
    rating = Column(Integer)
    metadata_json = Column(JSON)

class TraderDB:
    def __init__(self, db_path="trader_data.db"):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def log_trade(self, ticker, action, price, shares, reason):
        session = self.Session()
        trade = Trade(ticker=ticker, action=action, price=price, shares=shares, strategy_reason=reason)
        session.add(trade)
        session.commit()
        session.close()
        print(f"Trade logged: {action} {ticker} @ {price}")

    def add_reflection(self, content, rating, meta=None):
        session = self.Session()
        ref = Reflection(content=content, rating=rating, metadata_json=meta or {})
        session.add(ref)
        session.commit()
        session.close()

    def get_latest_reflections(self, limit=5):
        session = self.Session()
        results = session.query(Reflection).order_by(Reflection.timestamp.desc()).limit(limit).all()
        session.close()
        return [{"content": r.content, "rating": r.rating} for r in results]
