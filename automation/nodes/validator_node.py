# automation/nodes/validator_node.py
from typing import Dict, Any
from automation.models.agent_state import AgentState
from tools.interface.pattern_tool_interface import IPatternEngineTool

def validator_node(state: AgentState, engine: IPatternEngineTool) -> Dict[str, Any]:
    """
    Validates setups found in state. 
    Returns partial updates for the 'approval' state.
    """
    market = state.get("market", {})
    setups = market.get("matched_setups", [])

    if not setups:
        return {"approval": {"revalidation_passed": False}}

    # Validation Logic
    ticker = setups[0]["ticker"]
    df = engine.normalize_ohlcv(market.get("market_data", {}).get(ticker))
    
    is_valid = False
    if df is not None:
        valid_setups, _ = engine.evaluate_ticker(ticker, df, {}, None)
        is_valid = len(valid_setups) > 0

    return {
        "approval": {
            "revalidation_passed": is_valid,
            "pattern_still_valid": is_valid
        }
    }