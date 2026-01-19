from src.graph import build_graph
from src.database import MarketDB, TraderDB
from src.market_data import MarketDataLoader
from src.broker import SimulatedBroker
from src.news import fetch_market_news
from src.semantic import NewsProcessor
import time
import argparse
import sys

# 初始化语义处理器
news_processor = NewsProcessor()

from src.scanner import StockScanner

# 全局变量记录上一次状态，用于减少刷屏
last_state = {}

def run_live_cycle(ticker: str, broker, market_db, silent_if_unchanged=False):
    global last_state

    # 1. 基础设施 (传入)
    data_loader = MarketDataLoader(market_db)

    # 2. 获取情报 (市场数据)
    try:
        # Optimization: In real loop, don't fetch every single second.
        # But for now we rely on loader.
        data_loader.fetch_and_store(ticker, period="6mo")
    except Exception as e:
        print(f"[错误] 数据获取失败: {e}")
        return

    df = market_db.load_data(ticker)

    if df.empty:
        print(f"[错误] 无法加载 {ticker} 市场数据。中止。")
        return

    latest_price = df.iloc[-1]['Close']
    latest_date = df.index[-1]

    # 3. 检查是否需要完整运行 (静默模式)
    state_key = f"{ticker}_{latest_date}_{latest_price}"
    if silent_if_unchanged and last_state.get(ticker) == state_key:
        sys.stdout.write(f"\r[监控中] {ticker} | 价格: {latest_price:.2f} | 日期: {latest_date.date()} | 无变化...")
        sys.stdout.flush()
        return

    print(f"\n\n========== 实盘交易循环: {ticker} ==========")
    print(f"[市场] {ticker} 价格: ${latest_price:.2f} (日期: {latest_date.date()})")

    # 4. 获取情报 (新闻)
    print(f"[系统] 正在扫描 {ticker} 的新闻线...")
    news = fetch_market_news(f"{ticker} stock news")

    # 语义预览
    features = news_processor.process_batch(news)
    print(f"[语义层] 情绪: {features['sentiment_score']:.2f} | 置信度: {features['confidence']:.2f} | 主题: {features['topics']}")

    # 5. 初始化状态
    initial_state = {
        "ticker": ticker,
        "data": df,
        "news": news,
        "analysis": {},
        "signal": None,
        "risk_assessment": None,
        "execution_result": None,
        "critique": None,
        "broker": broker # Inject Broker
    }

    # 6. 启动智能体系统
    app = build_graph()
    final_state = app.invoke(initial_state)

    # 7. 报告
    print("\n========== 循环报告 ==========")
    signal = final_state.get("signal")
    risk = final_state.get("risk_assessment")
    exec_res = final_state.get("execution_result")

    if signal:
        print(f"策略研究员: {signal['action']} | {signal['reason']}")

    if risk:
        print(f"风控官    : {'批准' if risk['approved'] else '拒绝'} | {risk['reason']}")

    if exec_res:
        print(f"交易执行官: 已成交 {exec_res['action']} {exec_res['shares']} 股 @ ${exec_res['price']:.2f}")
    else:
        print(f"交易执行官: 无交易。")

    print("==================================\n")

    # 更新状态缓存
    last_state[ticker] = state_key

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="量化智能体主程序")
    parser.add_argument("--ticker", type=str, default="AAPL", help="股票代码")
    parser.add_argument("--auto-pick", action="store_true", help="自动选股模式")
    parser.add_argument("--loop", action="store_true", help="启用无限循环模式")
    parser.add_argument("--interval", type=int, default=300, help="循环间隔秒数 (默认 300秒)")

    args = parser.parse_args()

    # Init Shared Infrastructure
    market_db = MarketDB()
    broker = SimulatedBroker(account_id="live_paper", initial_cash=100000.0, db=market_db)

    targets = []

    if args.auto_pick:
        print("🔍 启动自动选股 (Scanner)...")
        scanner = StockScanner(market_db)
        targets = scanner.scan_market(top_n=3) # Pick top 3
        if not targets:
            print("⚠️ 未选出合适标的，回退到默认 ticker")
            targets = [args.ticker]
        else:
            print(f"✅ 自动选中: {targets}")
            # Ensure we buy them? The Agent loop will handle BUY signal if Strategist likes them.
            # But Strategist logic is "Trend Following". If Scanner picked them, Strategist should technically like them too.
    else:
        targets = [args.ticker]

    if args.loop:
        print(f"🚀 启动无限循环模式，监控目标: {targets}，间隔: {args.interval}秒")
        try:
            while True:
                for ticker in targets:
                    run_live_cycle(ticker, broker, market_db, silent_if_unchanged=True)
                    time.sleep(1) # Small gap between tickers

                # 倒计时显示
                # Simply sleep
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n🛑 用户停止程序。")
            sys.exit(0)
    else:
        for ticker in targets:
            run_live_cycle(ticker, broker, market_db)
