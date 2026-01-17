import pandas as pd
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Numeric, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os

# --- 市场数据 (PostgreSQL) ---
class MarketDB:
    def __init__(self):
        # 从环境变量读取连接串
        # 格式: postgresql+psycopg2://user:password@host:port/dbname
        self.db_url = os.getenv("DB_URL")
        if not self.db_url:
            print("[MarketDB] 警告: 未检测到环境变量 DB_URL。")
            print("[MarketDB] 降级模式: 使用本地 SQLite (market_data_local.db) 进行测试。")
            self.db_url = "sqlite:///market_data_local.db"

        # pool_size 控制连接池
        self.engine = create_engine(self.db_url, pool_size=5, max_overflow=10)
        self._init_tables()

    def _init_tables(self):
        """初始化资管级表结构"""
        with self.engine.connect() as conn:
            # 1. 证券元数据表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS instruments (
                    ticker VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100),
                    market VARCHAR(10),      -- SH/SZ/BJ/US
                    type VARCHAR(10),        -- STOCK/ETF/INDEX
                    lot_size INT DEFAULT 100, -- 最小交易单位
                    fee_rate NUMERIC(10, 6),  -- 预设费率
                    is_active BOOLEAN DEFAULT TRUE,
                    listing_date TIMESTAMP,
                    sector VARCHAR(50)
                )
            """))

            # 2. 改进的行情表 (日线)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_data_daily (
                    ticker VARCHAR(20),
                    date TIMESTAMP,  -- SQLite doesn't support DATE type strictly, uses TEXT/NUMERIC
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    adj_factor DOUBLE PRECISION, -- 复权因子
                    PRIMARY KEY (ticker, date)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_market_daily_date ON market_data_daily (date)"))

            # 3. 账户状态表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS account_states (
                    account_id VARCHAR(50) PRIMARY KEY,
                    total_cash DOUBLE PRECISION,
                    available_cash DOUBLE PRECISION,
                    frozen_cash DOUBLE PRECISION,
                    currency VARCHAR(10) DEFAULT 'CNY',
                    updated_at TIMESTAMP
                )
            """))

            # 4. 持仓明细表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS positions (
                    account_id VARCHAR(50),
                    ticker VARCHAR(20),
                    quantity DOUBLE PRECISION,
                    available_quantity DOUBLE PRECISION,
                    avg_cost DOUBLE PRECISION,
                    current_price DOUBLE PRECISION,
                    last_update TIMESTAMP,
                    PRIMARY KEY (account_id, ticker)
                )
            """))

            # 5. 绩效评价表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_daily_stats (
                    date TIMESTAMP,
                    account_id VARCHAR(50),
                    total_value DOUBLE PRECISION,
                    daily_return DOUBLE PRECISION,
                    sharpe_ratio DOUBLE PRECISION,
                    max_drawdown DOUBLE PRECISION,
                    PRIMARY KEY (date, account_id)
                )
            """))

            # 6. 分钟线表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ohlcv_minute (
                    ticker VARCHAR(20),
                    date TIMESTAMP,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    PRIMARY KEY (ticker, date)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ohlcv_minute_date ON ohlcv_minute (date)"))

            # Legacy support for ohlcv table if needed by other tools
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    ticker VARCHAR(20),
                    date TIMESTAMP,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    PRIMARY KEY (ticker, date)
                )
            """))

            conn.commit()

    def save_instruments(self, df: pd.DataFrame):
        """保存证券元数据"""
        if df.empty: return
        df = df.copy()

        # Ensure date is a column
        if "Date" not in df.columns and "date" not in df.columns and "日期" not in df.columns:
            df.reset_index(inplace=True)

        print(f"DEBUG: save_daily_data cols: {df.columns} index name: {df.index.name}", flush=True)

        rename_map = {
            "代码": "ticker", "name": "name", "名称": "name",
            "sector": "sector", "listing_date": "listing_date", "上市日期": "listing_date"
        }
        df = df.rename(columns=rename_map)
        if "ticker" not in df.columns: return

        if "market" not in df.columns:
            df["market"] = df["ticker"].apply(lambda x: "SH" if x.startswith("6") else ("SZ" if x.startswith(("0", "3")) else "BJ"))
        if "type" not in df.columns: df["type"] = "STOCK"
        if "lot_size" not in df.columns: df["lot_size"] = 100
        if "fee_rate" not in df.columns: df["fee_rate"] = 0.0003
        if "is_active" not in df.columns: df["is_active"] = True

        for col in ["listing_date", "sector"]:
            if col not in df.columns:
                df[col] = None

        df_to_save = df[["ticker", "name", "market", "type", "lot_size", "fee_rate", "is_active", "listing_date", "sector"]]

        if "listing_date" in df_to_save.columns:
            df_to_save["listing_date"] = pd.to_datetime(df_to_save["listing_date"], errors="coerce")

        with self.engine.begin() as conn:
            tickers = df_to_save["ticker"].tolist()
            chunk_size = 500
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i:i+chunk_size]
                if not chunk: continue
                bind_names = [f":t{k}" for k in range(len(chunk))]
                bind_params = {f"t{k}": t for k, t in enumerate(chunk)}
                query = text(f"DELETE FROM instruments WHERE ticker IN ({','.join(bind_names)})")
                conn.execute(query, bind_params)

            df_to_save.to_sql('instruments', conn, if_exists='append', index=False, method='multi', chunksize=500)

        print(f"[MarketDB] Updated {len(df_to_save)} instruments.")

    def save_daily_data(self, ticker: str, df: pd.DataFrame):
        """保存日线行情 (market_data_daily)"""
        if df.empty: return
        df = df.copy()

        # Ensure date is a column
        if "Date" not in df.columns and "date" not in df.columns and "日期" not in df.columns:
            df.reset_index(inplace=True)

        rename_map = {
            "Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
            "日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume",
            "adj_factor": "adj_factor"
        }
        df = df.rename(columns=rename_map)
        df["ticker"] = ticker

        if "adj_factor" not in df.columns:
            df["adj_factor"] = 1.0

        df["date"] = pd.to_datetime(df["date"])

        cols = ["ticker", "date", "open", "high", "low", "close", "volume", "adj_factor"]
        df_to_save = df[cols]

        min_date = df_to_save["date"].min().to_pydatetime()
        max_date = df_to_save["date"].max().to_pydatetime()

        with self.engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM market_data_daily WHERE ticker = :ticker AND date >= :min_date AND date <= :max_date"
            ), {"ticker": ticker, "min_date": min_date, "max_date": max_date})

            df_to_save.to_sql('market_data_daily', conn, if_exists='append', index=False, method='multi', chunksize=1000)

            # Also save to legacy ohlcv for compatibility? No, load_data handles fallback.
            # But let's populate it just in case some other script queries it directly.
            # conn.execute(text("DELETE FROM ohlcv WHERE ticker=:ticker AND date>=:min_date AND date<=:max_date"), ...)
            # df_to_save.drop(columns=["adj_factor"]).to_sql('ohlcv', conn, if_exists='append', index=False, method='multi')

    def save_minute_data(self, ticker: str, df: pd.DataFrame):
        """保存分钟行情 (ohlcv_minute)"""
        if df.empty: return
        df = df.copy()
        rename_map = {"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        df = df.rename(columns=rename_map)
        df["ticker"] = ticker

        cols = ["ticker", "date", "open", "high", "low", "close", "volume"]
        df["date"] = pd.to_datetime(df["date"])
        df_to_save = df[cols]

        min_date = df_to_save["date"].min().to_pydatetime()
        max_date = df_to_save["date"].max().to_pydatetime()

        with self.engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM ohlcv_minute WHERE ticker = :ticker AND date >= :min_date AND date <= :max_date"
            ), {"ticker": ticker, "min_date": min_date, "max_date": max_date})
            df_to_save.to_sql('ohlcv_minute', conn, if_exists='append', index=False, method='multi', chunksize=1000)

    def load_data(self, ticker: str, limit: int = 100) -> pd.DataFrame:
        """从数据库调取历史数据"""
        # Try new table
        query = text(f"SELECT * FROM market_data_daily WHERE ticker = :ticker ORDER BY date DESC LIMIT :limit")
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker, "limit": limit})

        if df.empty:
            # Fallback
            try:
                query_old = text(f"SELECT * FROM ohlcv WHERE ticker = :ticker ORDER BY date DESC LIMIT :limit")
                with self.engine.connect() as conn:
                    df = pd.read_sql(query_old, conn, params={"ticker": ticker, "limit": limit})
            except:
                pass

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

    def load_minute_data(self, ticker: str, limit: int = 1000) -> pd.DataFrame:
        query = text(f"SELECT * FROM ohlcv_minute WHERE ticker = :ticker ORDER BY date DESC LIMIT :limit")
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker, "limit": limit})

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

    # --- Broker Support Methods ---
    def get_account_state(self, account_id: str):
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM account_states WHERE account_id = :aid"), {"aid": account_id}).mappings().fetchone()
        return dict(row) if row else None

    def update_account_state(self, account_id, total, available, frozen, currency="CNY"):
        with self.engine.begin() as conn:
            exists = conn.execute(text("SELECT 1 FROM account_states WHERE account_id=:aid"), {"aid": account_id}).scalar()
            now = datetime.now()
            if exists:
                conn.execute(text("""
                    UPDATE account_states
                    SET total_cash=:t, available_cash=:a, frozen_cash=:f, updated_at=:u
                    WHERE account_id=:aid
                """), {"t": total, "a": available, "f": frozen, "u": now, "aid": account_id})
            else:
                conn.execute(text("""
                    INSERT INTO account_states (account_id, total_cash, available_cash, frozen_cash, currency, updated_at)
                    VALUES (:aid, :t, :a, :f, :c, :u)
                """), {"aid": account_id, "t": total, "a": available, "f": frozen, "c": currency, "u": now})

    def get_positions(self, account_id: str):
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM positions WHERE account_id = :aid"), {"aid": account_id}).mappings().all()
        return [dict(r) for r in rows]

    def update_position(self, account_id, ticker, qty, avail, cost, price):
        with self.engine.begin() as conn:
            now = datetime.now()
            if qty <= 1e-6:
                conn.execute(text("DELETE FROM positions WHERE account_id=:aid AND ticker=:t"), {"aid": account_id, "t": ticker})
            else:
                exists = conn.execute(text("SELECT 1 FROM positions WHERE account_id=:aid AND ticker=:t"), {"aid": account_id, "t": ticker}).scalar()
                if exists:
                    conn.execute(text("""
                        UPDATE positions
                        SET quantity=:q, available_quantity=:aq, avg_cost=:c, current_price=:p, last_update=:u
                        WHERE account_id=:aid AND ticker=:t
                    """), {"q": qty, "aq": avail, "c": cost, "p": price, "u": now, "aid": account_id, "t": ticker})
                else:
                    conn.execute(text("""
                        INSERT INTO positions (account_id, ticker, quantity, available_quantity, avg_cost, current_price, last_update)
                        VALUES (:aid, :t, :q, :aq, :c, :p, :u)
                    """), {"aid": account_id, "t": ticker, "q": qty, "aq": avail, "c": cost, "p": price, "u": now})

    # --- Legacy Support ---
    def save_data(self, ticker, df):
        self.save_daily_data(ticker, df)

    def save_stock_info(self, df):
        self.save_instruments(df)

    def get_existing_tickers(self):
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT ticker FROM market_data_daily")).fetchall()
            return [row[0] for row in result]
        except:
            return []

# --- Trade & Reflection Classes (Restored) ---
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
