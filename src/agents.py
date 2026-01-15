from src.state import AgentState
from src.tools import calculate_technical_indicators
from src.database import TraderDB
from src.memory import VectorMemory
import pandas as pd
import random

def analyze_sentiment(news_list):
    """
    基于关键词的简单新闻情绪分析。
    返回 -1.0 (负面) 到 1.0 (正面) 的分数。
    """
    if not news_list:
        return 0.0

    score = 0
    total = 0

    # 模拟情绪字典
    positive_words = ["soar", "surge", "jump", "record", "growth", "buy", "outperform", "beat", "higher"]
    negative_words = ["plunge", "crash", "drop", "miss", "loss", "sell", "down", "lower", "lawsuit", "investigation"]

    for item in news_list:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        if not text.strip():
            continue

        total += 1
        found_pos = sum(1 for w in positive_words if w in text)
        found_neg = sum(1 for w in negative_words if w in text)

        if found_pos > found_neg:
            score += 1
        elif found_neg > found_pos:
            score -= 1

    if total == 0:
        return 0.0

    return score / total # 归一化到 -1 到 1

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

    # 2. 新闻情绪分析
    news_score = analyze_sentiment(state.get("news", []))
    print(f"--- [策略研究员] 技术面: RSI={rsi:.2f} | 消息面情绪: {news_score:.2f} ---")

    # 3. 混合决策逻辑
    signal = {"action": "HOLD", "confidence": 0.0, "reason": "中性市场"}

    # 条件: 买入 (BUY)
    # 技术面: RSI < 40 (超卖) 或 金叉 (通常由价格行为暗示，这里简化)
    # 基本面: 情绪 > -0.2 (不算太差)
    if rsi < 40 and news_score > -0.5:
        signal = {
            "action": "BUY",
            "confidence": 0.8,
            "reason": f"超卖 (RSI {rsi:.2f}) 且情绪尚可 ({news_score:.2f})"
        }
    # 条件: 卖出 (SELL)
    # 技术面: RSI > 70
    # 或 情绪非常糟糕 (< -0.5)
    elif rsi > 70:
        signal = {
            "action": "SELL",
            "confidence": 0.8,
            "reason": f"超买 (RSI {rsi:.2f})"
        }
    elif news_score < -0.5:
        signal = {
            "action": "SELL",
            "confidence": 0.9,
            "reason": f"负面新闻情绪 ({news_score:.2f})"
        }
    elif news_score > 0.5:
        signal = {
            "action": "BUY",
            "confidence": 0.6,
            "reason": f"正面新闻驱动 ({news_score:.2f})"
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

    # 重新计算新闻分数用于检索上下文
    news_score = analyze_sentiment(state.get("news", []))

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
    # 假设账户资金 $100,000
    account_equity = 100000.0
    risk_per_trade_pct = 0.01 # 单笔亏损不超过 1%
    risk_budget = account_equity * risk_per_trade_pct # $1000

    # 止损距离设为 2倍 ATR
    stop_loss_dist = 2 * atr

    # 凯利公式/波动率平价计算股数
    # Shares = Risk Budget / Risk Per Share
    if stop_loss_dist > 0:
        target_shares = int(risk_budget / stop_loss_dist)
    else:
        target_shares = 0

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

    # 记录交易到数据库
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
    print(f"--- [交易执行官] 交易已记录: {signal['action']} @ {price:.2f} ---")
    return state

def critic_node(state: AgentState) -> AgentState:
    print("--- [复盘分析师] 正在复盘 ---")

    exec_res = state.get("execution_result")
    risk = state.get("risk_assessment")

    db = TraderDB()
    memory = VectorMemory(db)

    news_score = analyze_sentiment(state.get("news", []))
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
