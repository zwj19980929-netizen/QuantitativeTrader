from src.state import AgentState
from src.tools import calculate_technical_indicators
from src.database import TraderDB
import random

def analyze_sentiment(news_list):
    """
    Simple keyword-based sentiment analysis on news headlines.
    Returns a score from -1.0 (Negative) to 1.0 (Positive).
    """
    if not news_list:
        return 0.0

    score = 0
    total = 0

    # Mock sentiment dictionary
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

    return score / total # Normalize to -1 to 1

def strategist_node(state: AgentState) -> AgentState:
    print(f"--- [Strategist] Analyzing {state['ticker']} ---")

    # 1. Technical Analysis
    analysis = calculate_technical_indicators(state["data"])
    state["analysis"] = analysis

    if not analysis:
        print("--- [Strategist] Not enough data. ---")
        return state

    rsi = analysis["rsi_14"]
    price = analysis["current_price"]

    # 2. News Sentiment Analysis
    news_score = analyze_sentiment(state.get("news", []))
    print(f"--- [Strategist] Tech: RSI={rsi:.2f} | News Sentiment: {news_score:.2f} ---")

    # 3. Hybrid Decision Logic
    signal = {"action": "HOLD", "confidence": 0.0, "reason": "Neutral"}

    # Condition: BUY
    # Technical: RSI < 40 (Oversold) OR Golden Cross (implied by price action usually, simplified here)
    # Fundamental: Sentiment > -0.2 (Not terrible)
    if rsi < 40 and news_score > -0.5:
        signal = {
            "action": "BUY",
            "confidence": 0.8,
            "reason": f"Oversold (RSI {rsi:.2f}) & Sentiment OK ({news_score:.2f})"
        }
    # Condition: SELL
    # Technical: RSI > 70
    # OR Sentiment is very bad (< -0.5)
    elif rsi > 70:
        signal = {
            "action": "SELL",
            "confidence": 0.8,
            "reason": f"Overbought (RSI {rsi:.2f})"
        }
    elif news_score < -0.5:
        signal = {
            "action": "SELL",
            "confidence": 0.9,
            "reason": f"Negative News Sentiment ({news_score:.2f})"
        }
    elif news_score > 0.5:
        signal = {
            "action": "BUY",
            "confidence": 0.6,
            "reason": f"Positive News Momentum ({news_score:.2f})"
        }

    state["signal"] = signal
    print(f"--- [Strategist] Signal: {signal['action']} ({signal['reason']}) ---")
    return state

def risk_manager_node(state: AgentState) -> AgentState:
    print("--- [Risk Manager] Reviewing Signal ---")
    signal = state.get("signal")

    if not signal or signal["action"] == "HOLD":
        state["risk_assessment"] = {"approved": False, "reason": "No signal"}
        return state

    # Check Long-term Memory for past lessons
    # (In a real system, we'd embed the current state and query vector DB.
    # Here we just check latest reflections for keywords)

    db = TraderDB() # Connect to DB
    recent_reflections = db.get_latest_reflections(limit=3)

    caution_flag = False
    for ref in recent_reflections:
        if "risk" in ref["content"].lower() and ref["rating"] < 3:
            print(f"--- [Risk Manager] Recall: {ref['content']} ---")
            caution_flag = True

    analysis = state["analysis"]
    rsi = analysis.get("rsi_14", 50)

    assessment = {"approved": True, "reason": "Checks passed"}

    if signal["action"] == "BUY":
        if rsi > 75:
             assessment = {"approved": False, "reason": "RSI too high for BUY"}
        elif caution_flag and random.random() < 0.5:
             assessment = {"approved": False, "reason": "Cautious due to past poor performance."}

    state["risk_assessment"] = assessment
    print(f"--- [Risk Manager] {assessment['approved']} ({assessment['reason']}) ---")
    return state

def executor_node(state: AgentState) -> AgentState:
    print("--- [Executor] Executing ---")
    risk = state.get("risk_assessment")
    if not risk or not risk["approved"]:
        return state

    signal = state["signal"]
    price = state["analysis"]["current_price"]

    # Log trade to DB
    db = TraderDB()
    db.log_trade(
        ticker=state["ticker"],
        action=signal["action"],
        price=price,
        shares=10, # Fixed size for now
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
    print(f"--- [Executor] Trade Logged: {signal['action']} @ {price:.2f} ---")
    return state

def critic_node(state: AgentState) -> AgentState:
    print("--- [Critic] Reflecting ---")

    exec_res = state.get("execution_result")
    risk = state.get("risk_assessment")

    db = TraderDB()

    if exec_res:
        reflection = f"Executed {exec_res['action']} on {state['ticker']}. Market Sentiment was {analyze_sentiment(state.get('news')):.2f}."
        rating = 4
    elif risk and not risk["approved"]:
        reflection = f"Risk blocked trade on {state['ticker']}: {risk['reason']}. Good discipline."
        rating = 5
    else:
        reflection = f"No action on {state['ticker']}."
        rating = 3

    # Save to Memory
    db.add_reflection(reflection, rating)
    state["critique"] = {"feedback": reflection, "rating": rating}
    print(f"--- [Critic] Memory Saved: {reflection} ---")
    return state
