from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents import strategist_node, risk_manager_node, executor_node, critic_node

def should_execute(state: AgentState) -> str:
    """
    Conditional edge: Checks if risk manager approved the trade.
    """
    risk = state.get("risk_assessment")
    if risk and risk["approved"]:
        return "executor"
    return "critic"

def build_graph():
    # 1. Initialize Graph
    workflow = StateGraph(AgentState)

    # 2. Add Nodes
    workflow.add_node("strategist", strategist_node)
    workflow.add_node("risk_manager", risk_manager_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)

    # 3. Define Edges
    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "risk_manager")

    # Conditional Edge from Risk Manager
    workflow.add_conditional_edges(
        "risk_manager",
        should_execute,
        {
            "executor": "executor",
            "critic": "critic"
        }
    )

    workflow.add_edge("executor", "critic")
    workflow.add_edge("critic", END)

    # 4. Compile
    return workflow.compile()
