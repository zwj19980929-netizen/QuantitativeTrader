from src.state import AgentState
from src.tools import calculate_technical_indicators
from src.database import TraderDB
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

    # 检查长期记忆中的过往教训
    # (在真实系统中，我们会嵌入当前状态并查询向量数据库。
    # 这里我们只检查最近反思中的关键词)

    db = TraderDB() # 连接数据库
    recent_reflections = db.get_latest_reflections(limit=3)

    caution_flag = False
    for ref in recent_reflections:
        if "risk" in ref["content"].lower() and ref["rating"] < 3:
            print(f"--- [风控官] 回忆起: {ref['content']} ---")
            caution_flag = True

    analysis = state["analysis"]
    rsi = analysis.get("rsi_14", 50)

    assessment = {"approved": True, "reason": "风控通过"}

    if signal["action"] == "BUY":
        if rsi > 75:
             assessment = {"approved": False, "reason": "RSI 过高，禁止追高"}
        elif caution_flag and random.random() < 0.5:
             assessment = {"approved": False, "reason": "由于过往表现不佳，谨慎行事，拒绝交易。"}

    state["risk_assessment"] = assessment
    print(f"--- [风控官] 决策: {'批准' if assessment['approved'] else '拒绝'} ({assessment['reason']}) ---")
    return state

def executor_node(state: AgentState) -> AgentState:
    print("--- [交易执行官] 正在执行 ---")
    risk = state.get("risk_assessment")
    if not risk or not risk["approved"]:
        return state

    signal = state["signal"]
    price = state["analysis"]["current_price"]

    # 记录交易到数据库
    db = TraderDB()
    db.log_trade(
        ticker=state["ticker"],
        action=signal["action"],
        price=price,
        shares=10, # 暂时固定手数
        reason=signal["reason"]
    )

    result = {
        "status": "FILLED",
        "ticker": state["ticker"],
        "action": signal["action"],
        "price": price,
        "shares": 10
    }
    state["execution_result"] = result
    print(f"--- [交易执行官] 交易已记录: {signal['action']} @ {price:.2f} ---")
    return state

def critic_node(state: AgentState) -> AgentState:
    print("--- [复盘分析师] 正在复盘 ---")

    exec_res = state.get("execution_result")
    risk = state.get("risk_assessment")

    db = TraderDB()

    if exec_res:
        reflection = f"在 {state['ticker']} 执行了 {exec_res['action']}。当时的市场情绪分数为 {analyze_sentiment(state.get('news')):.2f}。"
        rating = 4
    elif risk and not risk["approved"]:
        reflection = f"风控拦截了 {state['ticker']} 的交易: {risk['reason']}。纪律性很好。"
        rating = 5
    else:
        reflection = f"{state['ticker']} 无操作。"
        rating = 3

    # 保存到记忆
    db.add_reflection(reflection, rating)
    state["critique"] = {"feedback": reflection, "rating": rating}
    print(f"--- [复盘分析师] 记忆已保存: {reflection} ---")
    return state
