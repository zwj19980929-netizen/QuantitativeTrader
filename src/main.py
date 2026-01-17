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

# 全局变量记录上一次状态，用于减少刷屏
last_state = {}

def run_live_cycle(ticker: str, silent_if_unchanged=False):
    global last_state

    # 1. 初始化基础设施
    market_db = MarketDB()
    data_loader = MarketDataLoader(market_db)
    # Initialize Broker (Paper Trading for Live)
    broker = SimulatedBroker(account_id="live_paper", initial_cash=100000.0, db=market_db)

    # 2. 获取情报 (市场数据)
    # data_loader.fetch_and_store(ticker, period="6mo")
    # 注意: 为了性能，fetch_and_store 内部最好有检查逻辑，或者我们在这里信任 MarketDataLoader 的增量更新能力
    # 目前 MarketDataLoader 每次都会去 fetch。

    try:
        data_loader.fetch_and_store(ticker, period="6mo")
    except Exception as e:
        print(f"[错误] 数据获取失败: {e}")
        return

    df = market_db.load_data(ticker)

    if df.empty:
        print("[错误] 无法加载市场数据。中止。")
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
    parser.add_argument("--loop", action="store_true", help="启用无限循环模式")
    parser.add_argument("--interval", type=int, default=300, help="循环间隔秒数 (默认 300秒)")

    args = parser.parse_args()

    if args.loop:
        print(f"🚀 启动无限循环模式，目标: {args.ticker}，间隔: {args.interval}秒")
        try:
            while True:
                # 在循环模式下，如果状态未变，保持静默
                run_live_cycle(args.ticker, silent_if_unchanged=True)

                # 倒计时显示
                for i in range(args.interval, 0, -1):
                    # 如果不是静默输出（即刚跑完一次完整循环），才显示倒计时
                    # 这里简化处理：总是 sleep
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 用户停止程序。")
            sys.exit(0)
    else:
        run_live_cycle(args.ticker)
