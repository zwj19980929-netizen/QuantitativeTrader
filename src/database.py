import pandas as pd
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Text, JSON
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
        """初始化行情表，增加索引以优化查询"""
        # 注意: 使用 SQLAlchemy Core DDL 或 raw SQL
        # 这里使用 raw SQL 以保持对 PG 特性的精细控制 (如索引)
        with self.engine.connect() as conn:
            # 兼容 SQLite (降级模式) 和 PostgreSQL
            is_sqlite = "sqlite" in self.db_url

            if is_sqlite:
                # SQLite 语法 (分开执行)
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
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv (date)"))
            else:
                # PostgreSQL 语法 (分开执行)
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
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv (date)"))
            conn.commit()

    def save_data(self, ticker: str, df: pd.DataFrame):
        """保存数据，处理 Upsert (先删后插策略)"""
        if df.empty:
            return

        df_copy = df.copy()
        if "Date" not in df_copy.columns:
            df_copy.reset_index(inplace=True)

        df_copy["ticker"] = ticker

        # 标准化列名
        rename_map = {
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        }
        df_copy = df_copy.rename(columns=rename_map)

        # 选出入库列
        df_to_save = df_copy[["ticker", "date", "open", "high", "low", "close", "volume"]]

        # 确保日期类型
        df_to_save["date"] = pd.to_datetime(df_to_save["date"])

        # 转换为 Python datetime 对象以兼容 SQLite
        min_date = df_to_save["date"].min().to_pydatetime()
        max_date = df_to_save["date"].max().to_pydatetime()

        # 事务处理: 先删除该时间段内的数据，防止主键冲突
        with self.engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM ohlcv WHERE ticker = :ticker AND date >= :min_date AND date <= :max_date"
            ), {"ticker": ticker, "min_date": min_date, "max_date": max_date})

            # 使用 Pandas 高效写入
            # chunksize 对 RDS 很重要
            df_to_save.to_sql('ohlcv', conn, if_exists='append', index=False, method='multi', chunksize=500)

        print(f"[MarketDB] 已存储 {len(df_to_save)} 行 {ticker} 数据。")

    def load_data(self, ticker: str, limit: int = 100) -> pd.DataFrame:
        """从数据库调取历史数据"""
        query = text(f"SELECT * FROM ohlcv WHERE ticker = :ticker ORDER BY date DESC LIMIT :limit")

        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker, "limit": limit})

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            # 兼容回测工具类 (恢复大写)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

    def get_existing_tickers(self):
        """获取数据库中已有的所有股票代码"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT ticker FROM ohlcv")).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            print(f"[MarketDB] 获取代码列表失败: {e}")
            return []

    def get_stats(self):
        """打印数据库统计信息"""
        try:
            with self.engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM ohlcv")).fetchone()[0]
                tickers = conn.execute(text("SELECT COUNT(DISTINCT ticker) FROM ohlcv")).fetchone()[0]
            print(f"[MarketDB 统计] 覆盖股票: {tickers} 只, 总数据行数: {count}")
        except Exception as e:
            print(f"[MarketDB] 统计失败: {e}")

# --- 交易数据 (SQLite via SQLAlchemy) - 保持不变 ---
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
        print(f"交易已记录: {action} {ticker} @ {price}")

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
