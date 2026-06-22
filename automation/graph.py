# automation/graph.py
from langgraph.graph import StateGraph, END
from automation.models.agent_state import AgentState
from automation.nodes.pattern_node import pattern_node
from automation.nodes.validator_node import validator_node

# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("research", lambda state: pattern_node(state, engine_tool))
workflow.add_node("validator", lambda state: validator_node(state, engine_tool))

# 3. Define Flow
workflow.set_entry_point("research")
workflow.add_edge("research", "validator")

# 4. Conditional Branching
def route_after_validation(state: AgentState) -> str:
    # Check the flag set by the validator_node
    if state.get("approval", {}).get("revalidation_passed"):
        return "executor"
    return "discord_notify"

workflow.add_conditional_edges("validator", route_after_validation)

# Compile
app = workflow.compile()