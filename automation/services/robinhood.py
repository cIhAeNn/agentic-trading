import json
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict

from automation.models.state import AgentState


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


LOGGER = _get_runtime_logger("agentic.robinhood")


def _primary_setup(state: AgentState) -> Dict[str, Any]:
    setups = state.get("matched_setups", [])
    if isinstance(setups, list) and setups and isinstance(setups[0], dict):
        return setups[0]
    return {}


class RobinhoodMCPConnector:
    """Robinhood MCP routing hooks. These methods return MCP-required states; no emulation."""

    @staticmethod
    def fetch_market_telemetry(state: AgentState) -> Dict[str, Any]:
        """Signal the orchestrator to invoke live MCP telemetry tools."""
        ticker_universe = state.get("ticker_universe", [])
        if not ticker_universe:
            LOGGER.warning("Telemetry skipped: empty ticker universe.", extra={"event": "EMPTY_TICKER_UNIVERSE"})
            return {"matched_setups": [], "market_data": {}, "execution_status": "NO_TICKERS"}

        LOGGER.info(
            "Live MCP market telemetry required.",
            extra={
                "event": "AWAITING_LIVE_MCP_TELEMETRY",
                "ticker_count": len(ticker_universe),
                "required_tools": ["fetch_historical_ohlcv_batch"],
            },
        )

        return {
            "execution_status": "AWAITING_LIVE_MCP_TELEMETRY",
            "mcp_requests": [
                {
                    "tool_family": "Robinhood MCP or market-data MCP",
                    "action": "fetch_historical_ohlcv_batch",
                    "tickers": ticker_universe,
                    "interval": "day",
                    "span": "3month",
                    "required_fields": ["open", "high", "low", "close", "volume", "timestamp"],
                }
            ],
        }

    @staticmethod
    def evaluate_capital_gate(state: AgentState) -> Dict[str, Any]:
        """Signal the orchestrator to invoke live MCP account-balance tools."""
        LOGGER.info(
            "Live MCP balance check required.",
            extra={"event": "AWAITING_LIVE_MCP_BALANCES", "required_tools": ["get_account_balances", "get_buying_power"]},
        )
        return {
            "execution_status": "AWAITING_LIVE_MCP_BALANCES",
            "mcp_requests": [
                {
                    "tool_family": "robinhood_mcp",
                    "action": "fetch_account_balances",
                    "required_fields": ["buying_power", "cash_available", "net_liquidity", "positions"],
                }
            ],
        }

    @staticmethod
    def execute_brokerage_order(state: AgentState) -> Dict[str, Any]:
        """
        Prepare the live Robinhood MCP execution request.

        This method does not fake execution. It returns a structured mcp_requests
        payload that the outer Claude/MCP runtime must dispatch to the live broker.
        """
        setup = _primary_setup(state)

        ticker = state.get("ticker") or setup.get("ticker")
        direction = (state.get("direction") or setup.get("direction") or "BUY").upper()
        target_qty = state.get("order_quantity", 0) or 0
        target_notional = state.get("order_notional", 0) or 0

        try:
            target_qty = int(target_qty)
        except Exception:
            target_qty = 0

        try:
            target_notional = float(str(target_notional).replace("$", "").replace(",", ""))
        except Exception:
            target_notional = 0.0

        if not ticker:
            LOGGER.error("Broker route rejected: missing ticker.", extra={"event": "REJECTED_MISSING_TICKER"})
            return {"execution_status": "REJECTED_MISSING_TICKER"}

        if target_qty <= 0 and target_notional <= 0:
            LOGGER.error(
                "Broker route rejected: missing valid quantity or notional.",
                extra={"event": "REJECTED_INVALID_ORDER_SIZE", "order_quantity": target_qty, "order_notional": target_notional},
            )
            return {"execution_status": "REJECTED_INVALID_ORDER_SIZE"}

        if state.get("revalidation_passed") is not True:
            LOGGER.error("Broker route rejected: revalidation not passed.", extra={"event": "REJECTED_REVALIDATION_NOT_PASSED"})
            return {"execution_status": "REJECTED_REVALIDATION_NOT_PASSED"}

        side = "buy" if direction == "BUY" else "sell"

        order_payload = {
            "tool_family": "robinhood_mcp",
            "action": "execute_trade",
            "ticker": ticker,
            "side": side,
            "order_type": "market",
            "time_in_force": "gfd",
            "requires_broker_confirmation": True,
        }

        if target_qty > 0:
            order_payload["quantity"] = target_qty
        else:
            order_payload["notional"] = round(target_notional, 2)

        LOGGER.info(
            "Live brokerage MCP execution request prepared.",
            extra={
                "event": "ORDER_READY_FOR_MCP_DISPATCH",
                "ticker": ticker,
                "direction": direction,
                "order_quantity": target_qty,
                "order_notional": target_notional,
                "required_tool": "execute_trade",
            },
        )

        return {
            "execution_status": "ORDER_READY_FOR_MCP_DISPATCH",
            "broker_request": order_payload,
            "mcp_requests": [order_payload],
        }
