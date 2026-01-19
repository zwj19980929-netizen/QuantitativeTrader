from src.state import AgentState
from src.tools import calculate_technical_indicators
from src.database import TraderDB
from src.memory import VectorMemory
from src.semantic import NewsProcessor
import pandas as pd
import random

# 初始化语义处理器 (含缓存)
news_processor = NewsProcessor()

def strategist_node(state: AgentState) -> AgentState:
    print(f"--- [策略研究员] 正在分析 {state['ticker']} ---")

    # 1. 技术分析
    analysis = calculate_technical_indicators(state["data"])
    state["analysis"] = analysis

    if not analysis:
        print("--- [策略研究员] 数据不足。 ---")
        return state

    rsi = analysis["rsi_14"]
    price = analysis["current_price"]

    # 2. 语义分析 (从“漏斗”中提取特征)
    news_list = state.get("news", [])
    semantic_features = news_processor.process_batch(news_list)

    news_score = semantic_features["sentiment_score"]
    confidence = semantic_features["confidence"]
    topics = semantic_features["topics"]

    print(f"--- [策略研究员] 技术面: RSI={rsi:.2f} | 语义特征: 情绪={news_score:.2f}, 置信度={confidence:.2f}, 主题={topics} ---")

    # 3. 混合决策逻辑 (逻辑驱动)
    signal = {"action": "HOLD", "confidence": 0.0, "reason": "中性市场"}

    # --- 基础评分系统 ---
    base_confidence = 0.5

    # 规则 1: 财报季动量 (Earnings Momentum)
    if "Earnings" in topics:
        if news_score > 0.3:
            signal = {
                "action": "BUY",
                "confidence": 0.8 * confidence, # 根据 LLM 置信度加权
                "reason": f"财报超预期驱动 (情绪 {news_score:.2f})"
            }
        elif news_score < -0.3:
            signal = {
                "action": "SELL",
                "confidence": 0.9 * confidence,
                "reason": f"财报不及预期 (情绪 {news_score:.2f})"
            }

    # 规则 2: 超卖/超买回归 (Mean Reversion)
    elif rsi < 30: # 深度超卖
        # 只要新闻不是极度负面，就尝试抄底
        if news_score > -0.6:
            signal = {
                "action": "BUY",
                "confidence": 0.7,
                "reason": f"深度超卖 (RSI {rsi:.2f}) 且基本面未恶化"
            }
    elif rsi > 70: # 超买
         signal = {
            "action": "SELL",
            "confidence": 0.7,
            "reason": f"技术面超买 (RSI {rsi:.2f})"
        }

    # 规则 3: 宏观恐慌 (Macro Panic)
    if "Macro" in topics and news_score < -0.5:
        # 即使 RSI 低，如果宏观环境极差，也要卖出或观望
        if signal["action"] == "BUY":
            signal = {"action": "HOLD", "confidence": 0.0, "reason": "宏观环境恶劣，取消抄底"}
        else:
            signal = {
                "action": "SELL",
                "confidence": 0.8,
                "reason": "宏观恐慌情绪抛售"
            }

    state["signal"] = signal
    print(f"--- [策略研究员] 生成信号: {signal['action']} ({signal['reason']}) ---")
    return state

def risk_manager_node(state: AgentState) -> AgentState:
    print("--- [风控官] 正在审核信号 ---")
    signal = state.get("signal")

    if not signal or signal["action"] == "HOLD":
        state["risk_assessment"] = {"approved": False, "reason": "无操作信号"}
        return state

    # 获取市场数据
    analysis = state["analysis"]
    price = analysis.get("current_price", 100.0)
    atr = analysis.get("atr_14", price * 0.02) # 默认 2% 波动率如果 ATR 缺失
    if pd.isna(atr): atr = price * 0.02

    # --- 1. 记忆检索 (Memory Recall) ---
    # 使用 VectorMemory 进行情境感知检索
    db = TraderDB()
    memory = VectorMemory(db)

    # 获取语义特征
    news_list = state.get("news", [])
    semantic_features = news_processor.process_batch(news_list)
    news_score = semantic_features["sentiment_score"]

    relevant_memories = memory.retrieve_relevant_memories(analysis, news_score)

    caution_flag = False
    for mem in relevant_memories:
        print(f"--- [风控官] 联想到相似历史 (Sim={mem['similarity']:.2f}): {mem['content']} ---")
        if mem["rating"] < 3:
            caution_flag = True

    # --- 2. 核心风控规则 ---
    rsi = analysis.get("rsi_14", 50)
    approved = True
    reason = "风控通过"

    if signal["action"] == "BUY":
        if rsi > 75:
             approved = False
             reason = "RSI 过高 (>75)，禁止追高"
        elif caution_flag:
             # 如果有历史教训，我们要么拒绝，要么减半仓位。这里为了演示选择收紧。
             reason += " (基于历史教训，仓位减半)"

    # --- 3. 动态仓位管理 (Volatility Sizing) ---
    # 从 Broker 获取真实账户净值
    account_equity = 100000.0 # Default fallback
    broker = state.get("broker")
    if broker:
        # Equity = Total Cash (Balance) + Market Value of Positions
        # But broker.get_total_value() calculates total equity
        # Ideally we use get_total_value but need to handle pricing context
        # For simplicity, assuming Broker is up to date or we use Balance
        # User said: "Current cash ... total equity"
        try:
            # Pass current price context for backtest accuracy
            price_map = {state["ticker"]: price}
            account_equity = broker.get_total_value(current_prices=price_map)
        except:
            acct = broker.get_account_state()
            if acct: account_equity = float(acct["total_cash"])

    risk_per_trade_pct = 0.01 # 单笔亏损不超过 1%
    risk_budget = account_equity * risk_per_trade_pct # $1000

    # 止损距离设为 2倍 ATR
    stop_loss_dist = 2 * atr

    # 凯利公式/波动率平价计算股数
    # Shares = Risk Budget / Risk Per Share
    target_shares = 0
    if stop_loss_dist > 0:
        target_shares = int(risk_budget / stop_loss_dist)

    # 限制单票最大持仓 (例如 20%)
    # If Broker available, check existing
    if broker and approved and signal["action"] == "BUY":
        current_pos_val = 0
        positions = broker.get_positions()
        for p in positions:
            if p["ticker"] == state["ticker"]:
                current_pos_val = float(p["quantity"]) * price
                break

        # Max pos value = 20% equity
        max_pos_val = account_equity * 0.2
        avail_space_val = max_pos_val - current_pos_val
        if avail_space_val <= 0:
            approved = False
            reason = "超过单票持仓上限 (20%)"
            target_shares = 0
        else:
            # Cap target shares to available space
            max_shares = int(avail_space_val / price)
            target_shares = min(target_shares, max_shares)

    # 如果有历史教训，仓位减半
    if caution_flag:
        target_shares = int(target_shares * 0.5)

    if not approved:
        target_shares = 0

    assessment = {
        "approved": approved,
        "target_shares": target_shares,
        "reason": f"{reason} | ATR={atr:.2f}, 目标仓位={target_shares}股"
    }

    state["risk_assessment"] = assessment
    print(f"--- [风控官] 决策: {'批准' if approved else '拒绝'} ({assessment['reason']}) ---")
    return state

def executor_node(state: AgentState) -> AgentState:
    print("--- [交易执行官] 正在执行 ---")
    risk = state.get("risk_assessment")
    if not risk or not risk["approved"]:
        return state

    signal = state["signal"]
    price = state["analysis"]["current_price"]
    shares = risk.get("target_shares", 0)
    broker = state.get("broker")

    if broker:
        # 使用 Broker 执行
        if signal["action"] == "BUY":
            broker.submit_order(state["ticker"], "BUY", shares, price=price)
        elif signal["action"] == "SELL":
            # 卖出逻辑：卖出多少？Risk Manager 应该决定卖出数量
            # 目前 Risk Manager 只计算 Target Shares (Buying)
            # 如果是 SELL，通常全卖或卖一半。
            # 为了简单，如果是 SELL 信号，我们卖出所有可用持仓
            positions = broker.get_positions()
            for p in positions:
                if p["ticker"] == state["ticker"]:
                    qty = float(p["available_quantity"])
                    if qty > 0:
                        broker.submit_order(state["ticker"], "SELL", qty, price=price)
                        shares = qty # Update shares for logging

    else:
        # Fallback to DB logging only (Legacy)
        db = TraderDB()
        db.log_trade(
            ticker=state["ticker"],
            action=signal["action"],
            price=price,
            shares=shares,
            reason=signal["reason"]
        )

    result = {
        "status": "FILLED",
        "ticker": state["ticker"],
        "action": signal["action"],
        "price": price,
        "shares": shares
    }
    state["execution_result"] = result
    print(f"--- [交易执行官] 交易已记录: {signal['action']} {shares} @ {price:.2f} ---")
    return state

def critic_node(state: AgentState) -> AgentState:
    print("--- [复盘分析师] 正在复盘 ---")

    exec_res = state.get("execution_result")
    risk = state.get("risk_assessment")

    db = TraderDB()
    memory = VectorMemory(db)

    # 获取语义特征
    news_list = state.get("news", [])
    semantic_features = news_processor.process_batch(news_list)
    news_score = semantic_features["sentiment_score"]
    analysis = state.get("analysis", {})

    if exec_res:
        reflection = f"在 {state['ticker']} 执行了 {exec_res['action']}。当时的市场情绪分数为 {news_score:.2f}。"
        rating = 4
    elif risk and not risk["approved"]:
        reflection = f"风控拦截了 {state['ticker']} 的交易: {risk['reason']}。纪律性很好。"
        rating = 5
    else:
        reflection = f"{state['ticker']} 无操作。"
        rating = 3

    # 保存到向量记忆库
    memory.add_memory(reflection, rating, analysis, news_score)

    state["critique"] = {"feedback": reflection, "rating": rating}
    print(f"--- [复盘分析师] 记忆已保存: {reflection} ---")
    return state
