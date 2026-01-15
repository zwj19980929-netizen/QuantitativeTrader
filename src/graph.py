from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents import strategist_node, risk_manager_node, executor_node, critic_node

def should_execute(state: AgentState) -> str:
    """
    条件边: 检查风控官是否批准了交易。
    """
    risk = state.get("risk_assessment")
    if risk and risk["approved"]:
        return "executor"
    return "critic"

def build_graph():
    # 1. 初始化图
    workflow = StateGraph(AgentState)

    # 2. 添加节点
    workflow.add_node("strategist", strategist_node)
    workflow.add_node("risk_manager", risk_manager_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)

    # 3. 定义边
    workflow.set_entry_point("strategist")
    workflow.add_edge("strategist", "risk_manager")

    # 来自风控官的条件边
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

    # 4. 编译
    return workflow.compile()
