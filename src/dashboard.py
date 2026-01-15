import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.graph import build_graph
from src.database import MarketDB, TraderDB
from src.market_data import MarketDataLoader
from src.news import fetch_market_news
from src.agents import analyze_sentiment
import time

# 设置页面配置
st.set_page_config(page_title="量化智能体驾驶舱", layout="wide")

st.title("🤖 资管级量化智能体驾驶舱")

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("控制面板")
    ticker = st.text_input("股票代码 (Ticker)", value="NVDA")
    run_btn = st.button("运行决策循环 (Run Cycle)", type="primary")

    st.divider()
    st.header("记忆库概览")
    db = TraderDB()
    reflections = db.get_latest_reflections(10)
    for ref in reflections:
        st.caption(f"{ref['rating']}⭐ {ref['content']}")

# --- 主逻辑 ---
if run_btn:
    with st.status("正在执行多智能体协作...", expanded=True) as status:

        # 1. 获取数据
        st.write("📡 连接数据金库 (The Vault)...")
        market_db = MarketDB()
        data_loader = MarketDataLoader(market_db)

        st.write(f"📥 获取 {ticker} 市场数据...")
        data_loader.fetch_and_store(ticker, period="6mo")
        df = market_db.load_data(ticker)

        if df.empty:
            st.error("无法获取数据！")
            status.update(label="执行失败", state="error")
            st.stop()

        latest_price = df.iloc[-1]['Close']
        st.write(f"💰 当前价格: ${latest_price:.2f}")

        # 2. 获取新闻
        st.write(f"📰 扫描 {ticker} 全球新闻...")
        news = fetch_market_news(f"{ticker} stock news")
        sentiment_score = analyze_sentiment(news)
        st.write(f"📊 新闻情绪分: {sentiment_score:.2f}")

        # 3. 运行智能体
        st.write("🧠 唤醒智能体集群...")
        app = build_graph()

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

        final_state = app.invoke(initial_state)
        status.update(label="决策循环完成", state="complete")

    # --- 结果展示面板 ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📈 市场走势与信号")

        # 绘制 K 线图
        fig = go.Figure(data=[go.Candlestick(x=df.index,
                        open=df['Open'],
                        high=df['High'],
                        low=df['Low'],
                        close=df['Close'])])

        fig.update_layout(height=500, title=f"{ticker} Price Action")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🧠 智能体对话")

        signal = final_state.get("signal")
        risk = final_state.get("risk_assessment")
        exec_res = final_state.get("execution_result")
        critique = final_state.get("critique")

        # 策略师卡片
        with st.chat_message("user", avatar="🧠"):
            st.write("**策略研究员 (Strategist)**")
            if signal:
                st.info(f"动作: {signal['action']}\n\n理由: {signal['reason']}")
            else:
                st.write("正在思考...")

        # 风控官卡片
        with st.chat_message("assistant", avatar="🛡️"):
            st.write("**风控官 (Risk Manager)**")
            if risk:
                status_color = "green" if risk['approved'] else "red"
                st.markdown(f":{status_color}[{'批准' if risk['approved'] else '拒绝'}]")
                st.write(f"理由: {risk['reason']}")
                if 'target_shares' in risk:
                    st.write(f"🎯 目标仓位: {risk['target_shares']} 股")
            else:
                st.write("待命中...")

        # 执行官卡片
        with st.chat_message("assistant", avatar="⚡"):
            st.write("**交易执行官 (Executor)**")
            if exec_res:
                st.success(f"已执行: {exec_res['action']} {exec_res['shares']} 股 @ ${exec_res['price']:.2f}")
            else:
                st.write("无操作。")

        # 复盘卡片
        with st.chat_message("user", avatar="📝"):
            st.write("**复盘分析师 (Critic)**")
            if critique:
                st.write(f"💭 \"{critique['feedback']}\"")
                st.caption(f"记忆评分: {critique['rating']}/5")
