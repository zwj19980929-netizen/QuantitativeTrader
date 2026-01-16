import duckdb
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os

# --- 市场数据 (DuckDB) ---
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
        保存 OHLCV 数据框到 DuckDB。
        期望索引为 Date/Timestamp 或包含名为 'Date' 的列。
        """
        # 确保日期是一列
        df_copy = df.copy()
        if "Date" not in df_copy.columns:
            df_copy.reset_index(inplace=True)

        # 添加代码列
        df_copy["ticker"] = ticker

        # 标准化列名
        df_copy = df_copy.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })

        # 仅选择相关列以避免架构不匹配
        df_copy = df_copy[["ticker", "date", "open", "high", "low", "close", "volume"]]

        # 更新插入 (Upsert)
        # DuckDB 旧版本 Python API 没有简单的 UPSERT。
        # 为了简单和速度：删除现有范围然后插入。

        min_date = df_copy["date"].min()
        max_date = df_copy["date"].max()

        self.conn.execute(
            "DELETE FROM ohlcv WHERE ticker = ? AND date >= ? AND date <= ?",
            [ticker, min_date, max_date]
        )

        self.conn.register("df_view", df_copy)
        self.conn.execute("INSERT INTO ohlcv SELECT * FROM df_view")
        self.conn.unregister("df_view")
        print(f"已在 MarketDB 中存储 {len(df_copy)} 行数据 ({ticker})。")

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
            # 重命名回首字母大写，以兼容工具函数
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        return df

    def get_existing_tickers(self):
        """获取数据库中已有的所有股票代码"""
        try:
            return [row[0] for row in self.conn.execute("SELECT DISTINCT ticker FROM ohlcv").fetchall()]
        except:
            return []

    def get_stats(self):
        """打印数据库统计信息"""
        try:
            count = self.conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
            tickers = self.conn.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv").fetchone()[0]
            print(f"[MarketDB 统计] 覆盖股票: {tickers} 只, 总数据行数: {count}")
        except Exception as e:
            print(f"[MarketDB] 统计失败: {e}")

# --- 交易数据 (SQLite via SQLAlchemy) ---
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
