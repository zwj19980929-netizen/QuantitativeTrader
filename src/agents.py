from src.state import AgentState
from src.tools import calculate_technical_indicators
import random

def strategist_node(state: AgentState) -> AgentState:
    """
    Strategist Agent: Analyzes market data and generates trading signals.
    """
    print(f"--- [Strategist] Analyzing {state['ticker']} ---")

    # 1. Use Tool: Calculate Indicators
    analysis = calculate_technical_indicators(state["data"])
    state["analysis"] = analysis

    if not analysis:
        print("--- [Strategist] Not enough data to analyze. ---")
        return state

    # 2. Logic (Mocking LLM Reasoning)
    rsi = analysis["rsi_14"]
    sma20 = analysis["sma_20"]
    sma50 = analysis["sma_50"]
    price = analysis["current_price"]

    print(f"--- [Strategist] Indicators: RSI={rsi:.2f}, SMA20={sma20:.2f}, Price={price:.2f} ---")

    signal = {"action": "HOLD", "confidence": 0.0, "reason": "Market is neutral"}

    # Simple Mean Reversion / Trend Following Logic
    if rsi < 40: # Low threshold for demo
        signal = {
            "action": "BUY",
            "confidence": 0.8,
            "reason": f"Oversold (RSI {rsi:.2f} < 40)"
        }
    elif rsi > 70:
        signal = {
            "action": "SELL",
            "confidence": 0.8,
            "reason": f"Overbought (RSI {rsi:.2f} > 70)"
        }
    elif sma20 > sma50 and price > sma20:
        # Golden Cross-ish
        signal = {
            "action": "BUY",
            "confidence": 0.6,
            "reason": "Uptrend (Price > SMA20 > SMA50)"
        }

    state["signal"] = signal
    print(f"--- [Strategist] Signal Generated: {signal['action']} ({signal['reason']}) ---")
    return state


def risk_manager_node(state: AgentState) -> AgentState:
    """
    Risk Manager Agent: Validates signals against risk constraints.
    """
    print("--- [Risk Manager] Reviewing Signal ---")
    signal = state.get("signal")

    if not signal or signal["action"] == "HOLD":
        state["risk_assessment"] = {"approved": False, "reason": "No actionable signal"}
        return state

    # Logic (Mocking Risk Model)
    # Rule 1: Don't buy if RSI is extremely high (even if Strategist says Buy for some reason - simplified conflict)
    # Rule 2: Random "Macro Event" simulated veto

    analysis = state["analysis"]
    rsi = analysis.get("rsi_14", 50)

    # Hard Rule: Veto BUY if RSI > 80 (Extreme risk)
    if signal["action"] == "BUY" and rsi > 80:
        assessment = {
            "approved": False,
            "reason": f"REJECTED: RSI {rsi:.2f} is dangerously high."
        }
    else:
        # Simulate a 10% chance of Risk Rejection due to "Portfolio Exposure" or "Macro News"
        if random.random() < 0.1:
            assessment = {
                "approved": False,
                "reason": "REJECTED: Portfolio exposure limit reached."
            }
        else:
            assessment = {
                "approved": True,
                "reason": "Risk checks passed."
            }

    state["risk_assessment"] = assessment
    print(f"--- [Risk Manager] Decision: {'APPROVED' if assessment['approved'] else 'REJECTED'} ({assessment['reason']}) ---")
    return state


def executor_node(state: AgentState) -> AgentState:
    """
    Executor Agent: Executes the trade if approved.
    """
    print("--- [Executor] Processing Trade ---")

    risk = state.get("risk_assessment")
    if not risk or not risk["approved"]:
        print("--- [Executor] No approved trade to execute. ---")
        return state

    signal = state["signal"]
    price = state["analysis"]["current_price"]

    # Simulate Execution (Slippage)
    slippage = price * 0.001 # 0.1% slippage
    exec_price = price + slippage if signal["action"] == "BUY" else price - slippage

    result = {
        "status": "FILLED",
        "ticker": state["ticker"],
        "action": signal["action"],
        "price": exec_price,
        "shares": 100, # Mock quantity
        "commission": 1.0
    }

    state["execution_result"] = result
    print(f"--- [Executor] Trade Executed: {signal['action']} @ {exec_price:.2f} ---")
    return state

def critic_node(state: AgentState) -> AgentState:
    """
    Critic Agent: Reviews the cycle and stores learnings (mocked).
    """
    print("--- [Critic] Analyzing Outcome ---")

    exec_res = state.get("execution_result")

    critique = {}
    if exec_res:
         critique = {
             "feedback": f"Trade executed at {exec_res['price']:.2f}. Monitoring for profit.",
             "rating": 5
         }
    else:
        risk = state.get("risk_assessment")
        if risk and not risk["approved"]:
            critique = {
                "feedback": f"Good risk control: {risk['reason']}",
                "rating": 4
            }
        else:
            critique = {
                "feedback": "No trade generated, standard monitoring.",
                "rating": 3
            }

    state["critique"] = critique
    print(f"--- [Critic] Feedback: {critique['feedback']} ---")
    return state
