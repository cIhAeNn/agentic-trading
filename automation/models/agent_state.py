from typing import TypedDict, List, Dict, Any

# 1. Market & Pattern Context (Used by Research Agent)
class MarketState(TypedDict, total=False):
    ticker_universe: List[str]
    market_data: Dict[str, dict]
    pattern_evaluations: Dict[str, Any]
    matched_setups: List[dict]

# 2. Risk & Sizing (Used by Execution Agent)
class SizingState(TypedDict, total=False):
    buying_power: float
    order_quantity: int
    order_notional: float
    risk_budget: float
    position_sizing_status: str

# 3. Approval Context (Used by Discord/Compliance Agent)
class ApprovalState(TypedDict, total=False):
    staged_orders: List[dict]
    discord_approval_message_id: str
    revalidation_passed: bool
    pattern_still_valid: bool

# 4. Master State (The Orchestrator)
class AgentState(TypedDict, total=False):
    market: MarketState
    sizing: SizingState
    approval: ApprovalState
    execution: Dict[str, Any]
    diagnostics: Dict[str, Any]