from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    # Universe / market data
    ticker_universe: List[str]
    market_data: Dict[str, dict]
    pattern_evaluations: Dict[str, Any]
    pattern_summary: Dict[str, Any]
    post_approval_recheck: Dict[str, Any]
    matched_setups: List[dict]
    mcp_requests: List[dict]
    mcp_dispatches: List[dict]

    # Account / sizing
    account_telemetry: Dict[str, Any]
    capital_available: bool
    buying_power: Any
    cash_available: Any
    net_liquidity: Any
    order_quantity: int
    order_notional: float
    suggested_amount: Any
    suggested_qty: Any
    suggested_pct: Any
    max_pct: Any
    max_qty_by_risk: Any
    position_sizing_status: str
    sizing_reason: str
    risk_budget: Any
    per_share_risk: Any

    # Staging / approval
    staged_orders: List[dict]
    order_staged_at: str
    operator_msg_payload: str
    discord_operator_message: str
    approval_message: str
    discord_approval_message_id: str
    discord_approval_author_id: str
    approval_size_mode: str
    approval_size_value: Any
    revalidation_passed: bool
    pattern_still_valid: bool

    # Execution / broker result
    fill_status: str
    transaction_id: str
    executed_at: str
    broker_request: Dict[str, Any]
    broker_confirmation: Dict[str, Any]

    # Runtime routing / diagnostics
    execution_status: str
    market_open: bool
    market_override: bool
    time_et: str
    missing_paths: List[str]
    error: str
    rejection_reason: str
    invalidation_reason: str
    scheduler_status: str
    cowork_step: int
    scheduler_thread_id: str

    # Optional message/template fields used by Discord cards
    discord_message: str
    ticker: str
    direction: str
    pattern_id: str
    pattern_name: str
    asset_class: str
    current_price: Any
    entry_price: Any
    stop_loss: Any
    price_target: Any
    risk_reward_ratio: Any
    confidence_pct: Any
    confidence_method: str
    thesis: str
    conviction_thesis: str

    # Account display fields used by Discord templates
    current_position_qty: Any
    current_position_market_value: Any
    current_position_pct: Any
    position_qty: Any
    position_value: Any
    position_pct: Any
    alpha_vantage_quota: Any
    tipranks_quota: Any
    av_quota: Any
    tr_quota: Any

    # Readiness / critical error cards
    mode: str
    market_state: str
    scheduler_state: str
    file_parity: str
    log_access: str
    robinhood_status: str
    alpha_vantage_status: str
    tipranks_status: str
    windsor_status: str
    discord_status: str
    system_state: str
    endpoint: str
    failure_type: str
    tier_limit: str
    diagnostic_payload: Dict[str, Any]
    processing_state: str
