from src.graph import build_graph
from src.database import MarketDB, TraderDB
from src.market_data import MarketDataLoader
from src.news import fetch_market_news
from src.semantic import NewsProcessor
import time

# 初始化语义处理器
news_processor = NewsProcessor()

def run_live_cycle(ticker: str):
    print(f"\n========== 实盘交易循环: {ticker} ==========")

    # 1. 初始化基础设施
    print("[系统] 正在连接数据金库 (The Vault)...")
    market_db = MarketDB() # duckdb
    # trader_db = TraderDB() # sqlite (在 agents 内部实例化，或者如果想查询可以在这里实例化)
    data_loader = MarketDataLoader(market_db)

    # 2. 获取情报 (市场数据)
    print(f"[系统] 正在获取 {ticker} 的市场数据...")
    # 获取足够的数据用于技术分析 (例如 6 个月)
    data_loader.fetch_and_store(ticker, period="6mo")
    df = market_db.load_data(ticker)

    if df.empty:
        print("[错误] 无法加载市场数据。中止。")
        return

    latest_price = df.iloc[-1]['Close']
    print(f"[市场] {ticker} 价格: ${latest_price:.2f}")

    # 3. 获取情报 (新闻)
    print(f"[系统] 正在扫描 {ticker} 的新闻线...")
    news = fetch_market_news(f"{ticker} stock news")
    print(f"[新闻] 找到 {len(news)} 篇近期文章。")

    # 语义预览
    features = news_processor.process_batch(news)
    print(f"[语义层] 情绪: {features['sentiment_score']:.2f} | 置信度: {features['confidence']:.2f} | 主题: {features['topics']}")

    # 4. 初始化状态
    initial_state = {
        "ticker": ticker,
        "data": df,
        "news": news,
        "analysis": {},
        "signal": None,
        "risk_assessment": None,
        "execution_result": None,
        "critique": None
    }

    # 5. 启动智能体系统
    print("[系统] 正在唤醒智能体...")
    app = build_graph()
    final_state = app.invoke(initial_state)

    # 6. 报告
    print("\n========== 循环报告 ==========")
    signal = final_state.get("signal")
    risk = final_state.get("risk_assessment")
    exec_res = final_state.get("execution_result")
    critique = final_state.get("critique")

    if signal:
        print(f"策略研究员: {signal['action']} | {signal['reason']}")

    if risk:
        print(f"风控官    : {'批准' if risk['approved'] else '拒绝'} | {risk['reason']}")

    if exec_res:
        print(f"交易执行官: 已成交 {exec_res['action']} {exec_res['shares']} 股 @ ${exec_res['price']:.2f}")
    else:
        print(f"交易执行官: 无交易。")

    if critique:
        print(f"复盘分析师: {critique['feedback']}")

    print("==================================\n")

if __name__ == "__main__":
    # 在真实部署环境中，这里会循环运行：
    # while True:
    #   run_live_cycle("AAPL")
    #   time.sleep(3600)

    # 演示用，运行一次
    run_live_cycle("AAPL")
