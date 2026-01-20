import pandas as pd
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Numeric, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
import os
import logging

# 配置日志，方便追踪生产环境中的错误
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# --- 市场数据 (PostgreSQL) ---
class MarketDB:
    def __init__(self):
        self.db_url = os.getenv("DB_URL")
        if not self.db_url:
            print("[MarketDB] 警告: 未检测到环境变量 DB_URL。")
            print("[MarketDB] 降级模式: 使用本地 SQLite (market_data_local.db) 进行测试。")
            self.db_url = "sqlite:///market_data_local.db"
        else:
            safe_url = self.db_url.split("@")[-1] if "@" in self.db_url else "..."
            print(f"[MarketDB] 已连接到外部数据库: {safe_url}")

        # 优化连接池参数
        # pool_pre_ping: 每次从池中取连接前先发个 'select 1'，解决 "server closed connection"
        # pool_recycle: 阿里云 RDS 默认会清理空闲长连接，这里设为 1 小时自动回收
        self.engine = create_engine(
            self.db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self._init_tables()

    def _init_tables(self):
        """初始化资管级表结构"""
        try:
            with self.engine.begin() as conn:
                # 1. 证券元数据表
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS instruments (
                        ticker VARCHAR(20) PRIMARY KEY,
                        name VARCHAR(100),
                        market VARCHAR(10),
                        type VARCHAR(10),
                        lot_size INT DEFAULT 100,
                        fee_rate NUMERIC(10, 6),
                        is_active BOOLEAN DEFAULT TRUE,
                        listing_date TIMESTAMP,
                        sector VARCHAR(50)
                    )
                """))

                # 2. 改进的行情表 (日线)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS market_data_daily (
                        ticker VARCHAR(20),
                        date TIMESTAMP,
                        open DOUBLE PRECISION,
                        high DOUBLE PRECISION,
                        low DOUBLE PRECISION,
                        close DOUBLE PRECISION,
                        volume DOUBLE PRECISION,
                        amount DOUBLE PRECISION,
                        turnover DOUBLE PRECISION,
                        adj_factor DOUBLE PRECISION,
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
                        amount DOUBLE PRECISION,
                        turnover DOUBLE PRECISION,
                        PRIMARY KEY (ticker, date)
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ohlcv_minute_date ON ohlcv_minute (date)"))

                # Legacy support for ohlcv table
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

                # Schema Migration (仅在 PostgreSQL 下执行)
                if "postgresql" in self.db_url:
                    for table in ["market_data_daily", "ohlcv_minute"]:
                        for col in ["amount", "turnover"]:
                            try:
                                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} DOUBLE PRECISION"))
                            except Exception:
                                pass  # 忽略列已存在的错误

        except SQLAlchemyError as e:
            logging.error(f"[MarketDB] 初始化表失败: {e}")
            # 注意：此处不 raise，允许程序尝试运行，除非你希望建表失败直接退出

    def save_instruments(self, df: pd.DataFrame):
        """保存证券元数据"""
        if df.empty: return
        try:
            df = df.copy()
            if "Date" not in df.columns and "date" not in df.columns and "日期" not in df.columns:
                df.reset_index(inplace=True)

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
                if col not in df.columns: df[col] = None

            df_to_save = df[["ticker", "name", "market", "type", "lot_size", "fee_rate", "is_active", "listing_date", "sector"]]
            if "listing_date" in df_to_save.columns:
                df_to_save["listing_date"] = pd.to_datetime(df_to_save["listing_date"], errors="coerce")

            with self.engine.begin() as conn:
                tickers = df_to_save["ticker"].tolist()
                chunk_size = 500
                for i in range(0, len(tickers), chunk_size):
                    chunk = tickers[i:i + chunk_size]
                    bind_params = {f"t{k}": t for k, t in enumerate(chunk)}
                    bind_names = [f":t{k}" for k in range(len(chunk))]
                    query = text(f"DELETE FROM instruments WHERE ticker IN ({','.join(bind_names)})")
                    conn.execute(query, bind_params)
                df_to_save.to_sql('instruments', conn, if_exists='append', index=False, method='multi', chunksize=500)
            print(f"[MarketDB] Updated {len(df_to_save)} instruments.")
        except Exception as e:
            logging.error(f"Failed to save instruments: {e}")

    def save_daily_data(self, ticker: str, df: pd.DataFrame):
        """保存日线行情"""
        if df.empty: return
        try:
            df = df.copy()
            if "Date" not in df.columns and "date" not in df.columns and "日期" not in df.columns:
                df.reset_index(inplace=True)

            rename_map = {
                "Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
                "Amount": "amount", "Turnover": "turnover", "日期": "date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount", "换手率": "turnover",
                "adj_factor": "adj_factor"
            }
            df = df.rename(columns=rename_map)
            df["ticker"] = ticker
            if "adj_factor" not in df.columns: df["adj_factor"] = 1.0
            for col in ["amount", "turnover"]:
                if col not in df.columns: df[col] = None

            df["date"] = pd.to_datetime(df["date"])
            cols = ["ticker", "date", "open", "high", "low", "close", "volume", "amount", "turnover", "adj_factor"]
            df_to_save = df[cols]
            min_date, max_date = df_to_save["date"].min().to_pydatetime(), df_to_save["date"].max().to_pydatetime()

            with self.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM market_data_daily WHERE ticker = :ticker AND date >= :min_date AND date <= :max_date"
                ), {"ticker": ticker, "min_date": min_date, "max_date": max_date})
                df_to_save.to_sql('market_data_daily', conn, if_exists='append', index=False, method='multi', chunksize=1000)
        except Exception as e:
            logging.error(f"Failed to save daily data for {ticker}: {e}")

    def save_minute_data(self, ticker: str, df: pd.DataFrame):
        """保存分钟行情 (ohlcv_minute)"""
        if df.empty: return
        try:
            df = df.copy()
            rename_map = {
                "Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
                "Amount": "amount", "Turnover": "turnover", "datetime": "date"
            }
            df = df.rename(columns=rename_map)
            df["ticker"] = ticker
            for col in ["amount", "turnover"]:
                if col not in df.columns: df[col] = None

            df["date"] = pd.to_datetime(df["date"])
            df_to_save = df[["ticker", "date", "open", "high", "low", "close", "volume", "amount", "turnover"]]
            min_date, max_date = df_to_save["date"].min().to_pydatetime(), df_to_save["date"].max().to_pydatetime()

            # 使用 engine.begin() 确保事务原子性
            with self.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM ohlcv_minute WHERE ticker = :ticker AND date >= :min_date AND date <= :max_date"
                ), {"ticker": ticker, "min_date": min_date, "max_date": max_date})
                df_to_save.to_sql('ohlcv_minute', conn, if_exists='append', index=False, method='multi', chunksize=1000)
        except Exception as e:
            logging.error(f"Failed to save minute data for {ticker}: {e}")

    def load_data(self, ticker: str, limit: int = 100) -> pd.DataFrame:
        query = text(f"SELECT * FROM market_data_daily WHERE ticker = :ticker ORDER BY date DESC LIMIT :limit")
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker, "limit": limit})

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

    def get_latest_minute_date(self, ticker: str) -> datetime:
        query = text("SELECT MAX(date) FROM ohlcv_minute WHERE ticker = :ticker")
        try:
            with self.engine.connect() as conn:
                res = conn.execute(query, {"ticker": ticker}).scalar()
            return pd.to_datetime(res) if res else None
        except:
            return None

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

    def get_account_state(self, account_id: str):
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM account_states WHERE account_id = :aid"), {"aid": account_id}).mappings().fetchone()
        return dict(row) if row else None

    def update_account_state(self, account_id, total, available, frozen, currency="CNY"):
        with self.engine.begin() as conn:
            now = datetime.now()
            conn.execute(text("""
                INSERT INTO account_states (account_id, total_cash, available_cash, frozen_cash, currency, updated_at)
                VALUES (:aid, :t, :a, :f, :c, :u)
                ON CONFLICT (account_id) DO UPDATE SET
                total_cash=EXCLUDED.total_cash, available_cash=EXCLUDED.available_cash, 
                frozen_cash=EXCLUDED.frozen_cash, updated_at=EXCLUDED.updated_at
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
                conn.execute(text("""
                    INSERT INTO positions (account_id, ticker, quantity, available_quantity, avg_cost, current_price, last_update)
                    VALUES (:aid, :t, :q, :aq, :c, :p, :u)
                    ON CONFLICT (account_id, ticker) DO UPDATE SET
                    quantity=EXCLUDED.quantity, available_quantity=EXCLUDED.available_quantity,
                    avg_cost=EXCLUDED.avg_cost, current_price=EXCLUDED.current_price, last_update=EXCLUDED.last_update
                """), {"aid": account_id, "t": ticker, "q": qty, "aq": avail, "c": cost, "p": price, "u": now})

    def get_existing_tickers(self):
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT ticker FROM market_data_daily")).fetchall()
            return [row[0] for row in result]
        except:
            return []

    # Legacy Support
    def save_data(self, ticker, df):
        self.save_daily_data(ticker, df)

    def save_stock_info(self, df):
        self.save_instruments(df)


# --- Trade & Reflection Classes ---
Base = declarative_base()


class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    action = Column(String)
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
        with self.Session() as session:
            trade = Trade(ticker=ticker, action=action, price=price, shares=shares, strategy_reason=reason)
            session.add(trade)
            session.commit()

    def add_reflection(self, content, rating, meta=None):
        with self.Session() as session:
            ref = Reflection(content=content, rating=rating, metadata_json=meta or {})
            session.add(ref)
            session.commit()

    def get_latest_reflections(self, limit=5):
        with self.Session() as session:
            results = session.query(Reflection).order_by(Reflection.timestamp.desc()).limit(limit).all()
            return [{"content": r.content, "rating": r.rating} for r in results]