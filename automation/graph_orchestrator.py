import json
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from automation.models.state import AgentState
from automation.nodes.patterns.models import runtime_env


class _JsonFormatter(logging.Formatter):
    """Minimal JSON-line formatter for runtime service logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message",
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in reserved:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _get_runtime_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    os.makedirs("logs", exist_ok=True)

    info_handler = RotatingFileHandler("logs/runtime.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(_JsonFormatter())

    error_handler = RotatingFileHandler("logs/runtime_error.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(_JsonFormatter())

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)
    return logger


LOGGER = _get_runtime_logger("agentic.graph")
ET = ZoneInfo("America/New_York")


def pre_flight_check(state: AgentState) -> Dict[str, Any]:
    """Validate runtime files and market window without sys.exit()."""
    try:
        os.makedirs("logs", exist_ok=True)

        now_est = datetime.now(ET)
        current_time_str = now_est.strftime("%H:%M")

        if runtime_env("MARKET_OVERRIDE", "FALSE") != "TRUE":
            if current_time_str < "09:30" or current_time_str > "17:30":
                LOGGER.info(
                    "Market window closed; graph hibernating.",
                    extra={"event": "LOW_POWER_HIBERNATE", "time_et": current_time_str},
                )
                return {"execution_status": "LOW_POWER_HIBERNATE", "market_open": False, "time_et": current_time_str}

        required_paths = [
            "data/agentic_screening.md",
            "data/10_trading_patterns.md",
            "automation/nodes/pattern_engine.py",
            "automation/nodes/patterns/engine.py",
            "automation/nodes/position_sizing.py",
            "automation/services/discord.py",
            "automation/services/robinhood.py",
            "config/discord_config.yaml",
            "logs/activity_ledger.json",
            "logs/error_trace.json",
        ]

        missing = [path for path in required_paths if not os.path.exists(path)]
        if missing:
            LOGGER.error("Pre-flight missing required paths.", extra={"event": "PRE_FLIGHT_MISSING_PATHS", "missing": missing})
            return {"execution_status": "PRE_FLIGHT_FAILED", "missing_paths": missing}

        LOGGER.info("Pre-flight passed.", extra={"event": "PRE_FLIGHT_PASSED", "time_et": current_time_str})
        return {"execution_status": "PRE_FLIGHT_PASSED", "market_open": True, "time_et": current_time_str}

    except Exception as exc:
        LOGGER.exception("Pre-flight failed.", extra={"event": "PRE_FLIGHT_EXCEPTION"})
        return {"execution_status": "PRE_FLIGHT_FAILED", "error": str(exc)}


def ingest_universe(state: AgentState) -> Dict[str, Any]:
    """Load every ticker from data/agentic_screening.md."""
    from automation.nodes.pattern_engine import PatternEngine

    tickers = PatternEngine.load_universe("data/agentic_screening.md")
    LOGGER.info("Ticker universe loaded.", extra={"event": "TICKER_UNIVERSE_LOADED", "ticker_count": len(tickers)})

    if not tickers:
        return {"ticker_universe": [], "execution_status": "SCREENING_EMPTY"}

    return {"ticker_universe": tickers, "execution_status": "SCREENING_LOADED"}


def request_live_market_data(state: AgentState) -> Dict[str, Any]:
    """Return batch MCP request when market_data is missing."""
    from automation.nodes.pattern_engine import PatternEngine

    tickers = state.get("ticker_universe", [])
    market_data = state.get("market_data", {})

    if market_data:
        return {"execution_status": "MARKET_DATA_PRESENT"}

    LOGGER.info("Live OHLCV required for universe.", extra={"event": "AWAITING_LIVE_OHLCV", "ticker_count": len(tickers)})
    return {"mcp_requests": PatternEngine.build_historical_requests(tickers), "execution_status": "AWAITING_LIVE_OHLCV"}


def process_telemetry_and_patterns(state: AgentState) -> Dict[str, Any]:
    """Run full-universe, real OHLCV pattern comparison."""
    from automation.nodes.pattern_engine import PatternEngine

    result = PatternEngine.evaluate_state(state)
    LOGGER.info(
        "Pattern engine result.",
        extra={
            "event": "PATTERN_ENGINE_RESULT",
            "execution_status": result.get("execution_status"),
            "matched_count": len(result.get("matched_setups", [])),
        },
    )
    return result


def calculate_position_size(state: AgentState) -> Dict[str, Any]:
    """Calculate suggested sizing before capital gate and Discord staging."""
    try:
        from automation.nodes.position_sizing import PositionSizer
        return PositionSizer.size_first_setup(state)
    except Exception as exc:
        LOGGER.exception("Position sizing failed.", extra={"event": "POSITION_SIZING_FAILED"})
        return {"execution_status": "POSITION_SIZING_FAILED", "position_sizing_status": "FAILED", "error": str(exc)}


def check_capital_gate(state: AgentState) -> Dict[str, Any]:
    """Use real account telemetry only. Never fabricate buying power or order cost."""
    setups = state.get("matched_setups", [])
    if not setups:
        return {"capital_available": False, "execution_status": "NO_SETUP_FOR_CAPITAL_GATE"}

    account = state.get("account_telemetry", {})
    if not isinstance(account, dict) or not account:
        LOGGER.info("Live account telemetry required before capital gate.", extra={"event": "AWAITING_LIVE_MCP_BALANCES"})
        return {
            "capital_available": False,
            "execution_status": "AWAITING_LIVE_MCP_BALANCES",
            "mcp_requests": [
                {
                    "tool_family": "robinhood_mcp",
                    "action": "fetch_account_balances",
                    "required_fields": ["buying_power", "cash_available", "net_liquidity", "positions"],
                }
            ],
        }

    buying_power_raw = account.get("buying_power", account.get("cash_available", state.get("buying_power")))
    try:
        buying_power = float(str(buying_power_raw).replace("$", "").replace(",", ""))
    except Exception:
        return {"capital_available": False, "execution_status": "INVALID_BUYING_POWER"}

    first_setup = setups[0]
    suggested_amount_raw = first_setup.get("suggested_amount") or state.get("suggested_amount") or state.get("order_notional") or 0

    try:
        suggested_amount = float(str(suggested_amount_raw).replace("$", "").replace(",", ""))
    except Exception:
        suggested_amount = 0.0

    if suggested_amount <= 0:
        return {"capital_available": False, "execution_status": "AWAITING_POSITION_SIZING"}

    has_funds = buying_power >= suggested_amount
    return {
        "capital_available": has_funds,
        "buying_power": buying_power,
        "execution_status": "CAPITAL_GATE_PASSED" if has_funds else "SKIP_INSUFFICIENT_FUNDS",
    }


def stage_and_submit_discord(state: AgentState) -> Dict[str, Any]:
    """Delegate Discord rendering, logging, and approval staging."""
    try:
        from automation.services.discord import DiscordMCPConnector
        return DiscordMCPConnector.submit_trade_blotter(state)
    except Exception as exc:
        LOGGER.exception("Discord staging failed.", extra={"event": "DISCORD_STAGE_FAILED"})
        return {"execution_status": "DISCORD_STAGE_FAILED", "error": str(exc)}


def post_approval_revalidate(state: AgentState) -> Dict[str, Any]:
    """Parse Discord approval and require a fresh post-approval pattern check."""
    try:
        from automation.services.discord import DiscordMCPConnector

        approval_result = DiscordMCPConnector.run_post_approval_revalidation(state)
        status = approval_result.get("execution_status")

        if status == "POST_APPROVAL_PATTERN_RECHECK_REQUIRED":
            ticker = state.get("ticker")
            if not ticker and state.get("matched_setups"):
                ticker = state["matched_setups"][0].get("ticker")

            return {
                **approval_result,
                "revalidation_passed": False,
                "mcp_requests": [
                    {
                        "tool_family": "market_data_mcp",
                        "action": "fetch_fresh_ohlcv_for_approved_ticker",
                        "ticker": ticker or "N/A",
                        "required_fields": ["open", "high", "low", "close", "volume", "timestamp"],
                    }
                ],
            }

        return approval_result

    except Exception as exc:
        LOGGER.exception("Post-approval revalidation failed.", extra={"event": "POST_APPROVAL_REVALIDATION_FAILED"})
        return {"revalidation_passed": False, "execution_status": "POST_APPROVAL_REVALIDATION_FAILED", "error": str(exc)}


def execute_brokerage_route(state: AgentState) -> Dict[str, Any]:
    """Delegate approved execution route to Robinhood service."""
    try:
        from automation.services.robinhood import RobinhoodMCPConnector
        return RobinhoodMCPConnector.execute_brokerage_order(state)
    except Exception as exc:
        LOGGER.exception("Brokerage route failed.", extra={"event": "BROKERAGE_ROUTE_FAILED"})
        return {"execution_status": "BROKERAGE_ROUTE_FAILED", "error": str(exc)}


def fire_cry_alert(state: AgentState) -> Dict[str, Any]:
    """Delegate CRY invalidation to Discord service."""
    try:
        from automation.services.discord import DiscordMCPConnector
        return DiscordMCPConnector.emit_cry_alert(state)
    except Exception as exc:
        LOGGER.exception("CRY alert failed.", extra={"event": "CRY_ALERT_FAILED"})
        return {"execution_status": "CRY_ALERT_FAILED", "error": str(exc)}


def preflight_router(state: AgentState) -> Literal["continue", "end"]:
    return "continue" if state.get("execution_status") == "PRE_FLIGHT_PASSED" else "end"


def market_data_router(state: AgentState) -> Literal["has_data", "awaiting"]:
    return "has_data" if state.get("execution_status") == "MARKET_DATA_PRESENT" else "awaiting"


def pattern_router(state: AgentState) -> Literal["has_patterns", "awaiting", "no_patterns"]:
    status = state.get("execution_status", "")
    if state.get("matched_setups"):
        return "has_patterns"
    if status in {"AWAITING_LIVE_OHLCV", "PATTERN_RULES_MISSING"}:
        return "awaiting"
    return "no_patterns"


def sizing_router(state: AgentState) -> Literal["sized", "awaiting", "blocked"]:
    status = state.get("execution_status", "")
    if status == "POSITION_SIZED":
        return "sized"
    if status in {"AWAITING_LIVE_MCP_BALANCES"}:
        return "awaiting"
    return "blocked"


def capital_router(state: AgentState) -> Literal["funded", "awaiting", "nsf"]:
    status = state.get("execution_status", "")
    if state.get("capital_available"):
        return "funded"
    if status in {"AWAITING_LIVE_MCP_BALANCES", "AWAITING_POSITION_SIZING"}:
        return "awaiting"
    return "nsf"


def revalidation_router(state: AgentState) -> Literal["execute", "awaiting", "cry", "end"]:
    status = state.get("execution_status", "")
    if state.get("revalidation_passed"):
        return "execute"
    if status in {"POST_APPROVAL_PATTERN_RECHECK_REQUIRED", "REFRESH_REQUESTED"}:
        return "awaiting"
    if status in {"POST_APPROVAL_PATTERN_FAILED", "PATTERN_INVALID_AFTER_APPROVAL"}:
        return "cry"
    return "end"


workflow = StateGraph(AgentState)

workflow.add_node("pre_flight", pre_flight_check)
workflow.add_node("ingest", ingest_universe)
workflow.add_node("request_market_data", request_live_market_data)
workflow.add_node("telemetry_and_patterns", process_telemetry_and_patterns)
workflow.add_node("position_sizing", calculate_position_size)
workflow.add_node("capital_gate", check_capital_gate)
workflow.add_node("discord_submit", stage_and_submit_discord)
workflow.add_node("revalidate", post_approval_revalidate)
workflow.add_node("broker_route", execute_brokerage_route)
workflow.add_node("cry_alert", fire_cry_alert)

workflow.set_entry_point("pre_flight")

workflow.add_conditional_edges("pre_flight", preflight_router, {"continue": "ingest", "end": END})
workflow.add_edge("ingest", "request_market_data")
workflow.add_conditional_edges("request_market_data", market_data_router, {"has_data": "telemetry_and_patterns", "awaiting": END})
workflow.add_conditional_edges("telemetry_and_patterns", pattern_router, {"has_patterns": "position_sizing", "awaiting": END, "no_patterns": END})
workflow.add_conditional_edges("position_sizing", sizing_router, {"sized": "capital_gate", "awaiting": END, "blocked": END})
workflow.add_conditional_edges("capital_gate", capital_router, {"funded": "discord_submit", "awaiting": END, "nsf": END})
workflow.add_edge("discord_submit", "revalidate")
workflow.add_conditional_edges("revalidate", revalidation_router, {"execute": "broker_route", "cry": "cry_alert", "awaiting": END, "end": END})
workflow.add_edge("broker_route", END)
workflow.add_edge("cry_alert", END)

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer, interrupt_after=["discord_submit"])
