import sys
import os
import time
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 确保能找到 src 模块
sys.path.append(os.getcwd())

from src.database import MarketDB
from src.eastmoney_a_crawler.eastmoney_a.client import EastmoneyClient
from src.eastmoney_a_crawler.eastmoney_a.secid import code_id_map

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("archive_minute_eastmoney.log", encoding='utf-8')]
)
logger = logging.getLogger("ArchiveMinuteEM")


def get_target_tickers(db: MarketDB, client: EastmoneyClient, fetch_all: bool = False):
    if fetch_all:
        print("[-] 正在从东财获取全量 A 股列表...")
        try:
            full_map = code_id_map(client.http)
            tickers = list(full_map.keys())
            print(f"[+] 获取到 {len(tickers)} 只股票。")
            return tickers
        except Exception as e:
            logger.error(f"Failed to fetch full ticker list: {e}")
            return []

    # 默认从本地 instruments 表取
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            res = conn.execute(text("SELECT ticker FROM instruments WHERE is_active=1")).fetchall()
        return [r[0] for r in res]
    except:
        return ["600519", "300391", "688380"]


def process_single_ticker(ticker, db, client, cutoff_date_str, klt=5):
    """
    处理单只股票。
    注意：client.kline_minute_history 内部已有翻页逻辑。
    """
    try:
        # 随机休眠
        time.sleep(random.uniform(0.1, 0.5))

        # 1. 检查断点
        latest_dt = db.get_latest_minute_date(ticker)
        start_date = cutoff_date_str

        if latest_dt:
            # 如果已有数据是 1 天内的，跳过
            # 注意：如果 klt 变更了，可能需要重新校验逻辑，这里暂时简单处理
            if (datetime.now() - latest_dt).days < 1:
                return "Up-to-date"

            # 增量抓取起点：数据库最新日期
            db_dt_str = latest_dt.strftime("%Y%m%d")
            if db_dt_str > start_date:
                start_date = db_dt_str

        # 2. 调用底层 Client 获取历史（内部带分页）
        df = client.kline_minute_history(
            symbol=ticker,
            klt=klt,
            start=start_date,
            end="20991231"
        )

        if df is None or df.empty:
            return "No data"

        # 3. 数据处理与数值校正
        # 映射列名以匹配数据库字段
        rename_map = {
            "datetime": "date",
            "open": "open", "high": "high", "low": "low", "close": "close",
            "volume": "volume", "amount": "amount", "turnover": "turnover"
        }
        df = df.rename(columns=rename_map)

        # 【核心修复】东财原始数据 amount(成交额) 和 turnover(换手率) 放大了一百倍
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce') / 100.0
        if 'turnover' in df.columns:
            df['turnover'] = pd.to_numeric(df['turnover'], errors='coerce') / 100.0

        # 时间标准化
        df['date'] = pd.to_datetime(df['date'])

        # 增量过滤：只保留比数据库里更晚的数据
        if latest_dt:
            df = df[df['date'] > latest_dt]

        if df.empty:
            return "No new rows"

        # 确保其他数值列也是 float
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. 写入数据库
        db.save_minute_data(ticker, df)
        return f"Saved {len(df)} rows"

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return f"Error: {str(e)}"


def archive_minute_data(months: int, fetch_all: bool, workers: int, klt: int = 5):
    db = MarketDB()
    client_main = EastmoneyClient()

    tickers = get_target_tickers(db, client_main, fetch_all=fetch_all)
    if not tickers:
        print("[!] 没有待处理的股票。")
        return

    # 计算起始时间
    cutoff_date = datetime.now() - timedelta(days=months * 30)
    cutoff_date_str = cutoff_date.strftime("%Y%m%d")

    print(f"[-] 任务启动 | 起始日期: {cutoff_date_str} | 线程数: {workers} | K线周期: {klt}")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # 【修复】这里传递参数匹配 process_single_ticker 的定义
        futures = {
            executor.submit(process_single_ticker, t, db, client_main, cutoff_date_str, klt): t
            for t in tickers
        }

        pbar = tqdm(as_completed(futures), total=len(tickers), unit="stk")
        for future in pbar:
            ticker = futures[future]
            try:
                res = future.result()
                pbar.set_description(f"[{ticker}] {res}")
            except Exception as e:
                logger.error(f"Thread fatal error {ticker}: {e}")

    print("[√] 全部归档任务已结束。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="抓取全量股票")
    parser.add_argument("--months", type=int, default=12, help="获取历史月数")
    parser.add_argument("--workers", type=int, default=8, help="并发线程数")
    parser.add_argument("--klt", type=int, default=5, help="K线周期 (1=1分钟, 5=5分钟)")

    args = parser.parse_args()

    archive_minute_data(months=args.months, fetch_all=args.all, workers=args.workers, klt=args.klt)