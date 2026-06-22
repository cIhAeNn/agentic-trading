from typing import Literal

from automation.models.agent_state import AgentState


class GraphRouters:
    """Conditional routing helpers for graph topologies that import shared routers."""

    @staticmethod
    def route_preflight(state: AgentState) -> Literal["continue", "end"]:
        return "continue" if state.get("execution_status") == "PRE_FLIGHT_PASSED" else "end"

    @staticmethod
    def route_market_data(state: AgentState) -> Literal["has_data", "awaiting"]:
        return "has_data" if state.get("execution_status") == "MARKET_DATA_PRESENT" else "awaiting"

    @staticmethod
    def route_patterns(state: AgentState) -> Literal["has_patterns", "awaiting", "no_patterns"]:
        status = state.get("execution_status", "")

        if state.get("matched_setups"):
            return "has_patterns"

        if status in {"AWAITING_LIVE_OHLCV", "AWAITING_LIVE_MCP_TELEMETRY", "AWAITING_PATTERN_EVALUATION", "PATTERN_RULES_MISSING"}:
            return "awaiting"

        return "no_patterns"

    @staticmethod
    def route_sizing(state: AgentState) -> Literal["sized", "awaiting", "blocked"]:
        status = state.get("execution_status", "")

        if status == "POSITION_SIZED":
            return "sized"

        if status in {"AWAITING_LIVE_MCP_BALANCES"}:
            return "awaiting"

        return "blocked"

    @staticmethod
    def route_capital(state: AgentState) -> Literal["funded", "awaiting", "nsf"]:
        status = state.get("execution_status", "")

        if state.get("capital_available"):
            return "funded"

        if status in {"AWAITING_LIVE_MCP_BALANCES", "AWAITING_POSITION_SIZING"}:
            return "awaiting"

        return "nsf"

    @staticmethod
    def route_revalidation(state: AgentState) -> Literal["execute", "awaiting", "cry", "end"]:
        status = state.get("execution_status", "")

        if state.get("revalidation_passed"):
            return "execute"

        if status in {"POST_APPROVAL_PATTERN_RECHECK_REQUIRED", "REFRESH_REQUESTED"}:
            return "awaiting"

        if status in {"POST_APPROVAL_PATTERN_FAILED", "PATTERN_INVALID_AFTER_APPROVAL"}:
            return "cry"

        return "end"
