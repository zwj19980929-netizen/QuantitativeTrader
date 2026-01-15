from src.data_loader import generate_mock_data
from src.graph import build_graph
import pandas as pd

def main():
    ticker = "MOCK_AAPL"
    print(f"=== Starting Quantitative Agent Simulation for {ticker} ===")

    # 1. Load Data
    print("... Generating mock market data ...")
    df = generate_mock_data(ticker)
    print(f"Data loaded: {len(df)} rows.")

    # 2. Build Graph
    app = build_graph()

    # 3. Initial State
    initial_state = {
        "ticker": ticker,
        "data": df,
        "analysis": {},
        "signal": None,
        "risk_assessment": None,
        "execution_result": None
    }

    # 4. Run Simulation
    print("\n>>> Running Agents Workflow >>>\n")
    final_state = app.invoke(initial_state)

    print("\n<<< Simulation Complete <<<\n")

    # 5. Report
    print("=== Final Report ===")
    signal = final_state.get("signal")
    risk = final_state.get("risk_assessment")
    exec_res = final_state.get("execution_result")

    if signal:
        print(f"Strategist Signal: {signal['action']} | Reason: {signal['reason']}")

    if risk:
        print(f"Risk Assessment: {'APPROVED' if risk['approved'] else 'REJECTED'} | Reason: {risk['reason']}")

    if exec_res:
        print(f"Execution: {exec_res['status']} {exec_res['action']} {exec_res['shares']} shares @ ${exec_res['price']:.2f}")
    else:
        print("Execution: No trade executed.")

if __name__ == "__main__":
    main()
