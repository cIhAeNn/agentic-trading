import json
import math
import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

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


LOGGER = _get_runtime_logger("agentic.position_sizing")


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").replace("%", ""))
    except Exception:
        return default


def _primary_setup(state: AgentState) -> Dict[str, Any]:
    setups = state.get("matched_setups", [])
    if isinstance(setups, list) and setups and isinstance(setups[0], dict):
        return dict(setups[0])
    return {}


class PositionSizer:
    """
    Converts a validated pattern setup into explicit suggested sizing fields.

    It does not execute anything. It only prepares sizing fields for human review:
    - suggested_qty
    - suggested_amount
    - suggested_pct
    - max_qty_by_risk
    - max_pct
    """

    @staticmethod
    def size_first_setup(state: AgentState) -> Dict[str, Any]:
        setup = _primary_setup(state)
        if not setup:
            return {
                "execution_status": "NO_SETUP_FOR_POSITION_SIZING",
                "position_sizing_status": "SKIPPED",
            }

        account = state.get("account_telemetry", {})
        if not isinstance(account, dict) or not account:
            LOGGER.info(
                "Account telemetry required before position sizing.",
                extra={"event": "AWAITING_LIVE_MCP_BALANCES"},
            )
            return {
                "execution_status": "AWAITING_LIVE_MCP_BALANCES",
                "position_sizing_status": "AWAITING_ACCOUNT_TELEMETRY",
                "mcp_requests": [
                    {
                        "tool_family": "robinhood_mcp",
                        "action": "fetch_account_balances",
                        "required_fields": [
                            "buying_power",
                            "cash_available",
                            "net_liquidity",
                            "positions",
                        ],
                    }
                ],
            }

        buying_power = _as_float(account.get("buying_power", account.get("cash_available")))
        cash_available = _as_float(account.get("cash_available", buying_power))
        net_liquidity = _as_float(account.get("net_liquidity", account.get("portfolio_value", buying_power)))

        entry = _as_float(setup.get("entry_price", setup.get("current_price")))
        stop = _as_float(setup.get("stop_loss"))
        direction = str(setup.get("direction", "BUY")).upper()

        if buying_power is None or buying_power <= 0:
            return {
                "execution_status": "INVALID_BUYING_POWER",
                "position_sizing_status": "BLOCKED",
                "sizing_reason": "Buying power missing or non-positive.",
            }

        if net_liquidity is None or net_liquidity <= 0:
            net_liquidity = buying_power

        if entry is None or entry <= 0:
            return {
                "execution_status": "INVALID_ENTRY_PRICE",
                "position_sizing_status": "BLOCKED",
                "sizing_reason": "Entry price missing or non-positive.",
            }

        if stop is None or stop <= 0:
            return {
                "execution_status": "INVALID_STOP_LOSS",
                "position_sizing_status": "BLOCKED",
                "sizing_reason": "Stop loss missing or non-positive.",
            }

        max_position_pct = _as_float(runtime_env("MAX_POSITION_PCT", "0.05"), 0.05) or 0.05
        max_trade_risk_pct = _as_float(runtime_env("MAX_TRADE_RISK_PCT", "0.005"), 0.005) or 0.005
        min_notional = _as_float(runtime_env("MIN_TRADE_NOTIONAL", "25"), 25.0) or 25.0
        cash_buffer_pct = _as_float(runtime_env("CASH_BUFFER_PCT", "0.02"), 0.02) or 0.02

        max_notional_by_allocation = max(0.0, net_liquidity * max_position_pct)
        max_notional_by_cash = max(0.0, buying_power * (1 - cash_buffer_pct))

        per_share_risk = abs(entry - stop)
        if per_share_risk <= 0:
            return {
                "execution_status": "INVALID_RISK_DISTANCE",
                "position_sizing_status": "BLOCKED",
                "sizing_reason": "Entry and stop produce zero risk distance.",
            }

        risk_budget = max(0.0, net_liquidity * max_trade_risk_pct)
        max_qty_by_risk = math.floor(risk_budget / per_share_risk)

        # This engine currently stages long/short signals for human review.
        # Order sizing remains positive; broker service handles side/direction.
        max_qty_by_allocation = math.floor(max_notional_by_allocation / entry)
        max_qty_by_cash = math.floor(max_notional_by_cash / entry)

        suggested_qty = max(0, min(max_qty_by_risk, max_qty_by_allocation, max_qty_by_cash))
        suggested_amount = round(suggested_qty * entry, 2)
        suggested_pct = round(suggested_amount / net_liquidity, 4) if net_liquidity > 0 else 0.0

        if suggested_qty <= 0 or suggested_amount < min_notional:
            LOGGER.warning(
                "Position sizing blocked by risk/allocation/min-notional constraints.",
                extra={
                    "event": "POSITION_SIZING_BLOCKED",
                    "ticker": setup.get("ticker"),
                    "suggested_qty": suggested_qty,
                    "suggested_amount": suggested_amount,
                    "min_notional": min_notional,
                },
            )
            return {
                "execution_status": "POSITION_SIZE_TOO_SMALL",
                "position_sizing_status": "BLOCKED",
                "sizing_reason": "Risk/allocation constraints produced no actionable minimum size.",
                "risk_budget": round(risk_budget, 2),
                "per_share_risk": round(per_share_risk, 4),
                "max_qty_by_risk": max_qty_by_risk,
                "max_pct": max_position_pct,
            }

        enriched_setup = {
            **setup,
            "suggested_qty": suggested_qty,
            "suggested_amount": suggested_amount,
            "suggested_pct": suggested_pct,
            "max_pct": max_position_pct,
            "max_qty_by_risk": max_qty_by_risk,
            "risk_budget": round(risk_budget, 2),
            "per_share_risk": round(per_share_risk, 4),
        }

        matched_setups = list(state.get("matched_setups", []))
        matched_setups[0] = enriched_setup

        result = {
            "matched_setups": matched_setups,
            "execution_status": "POSITION_SIZED",
            "position_sizing_status": "SIZED",
            "suggested_qty": suggested_qty,
            "suggested_amount": suggested_amount,
            "suggested_pct": suggested_pct,
            "max_pct": max_position_pct,
            "max_qty_by_risk": max_qty_by_risk,
            "risk_budget": round(risk_budget, 2),
            "per_share_risk": round(per_share_risk, 4),
            "order_notional": suggested_amount,
            "buying_power": buying_power,
            "cash_available": cash_available,
            "net_liquidity": net_liquidity,
        }

        LOGGER.info(
            "Position sizing complete.",
            extra={
                "event": "POSITION_SIZED",
                "ticker": enriched_setup.get("ticker"),
                "direction": direction,
                "suggested_qty": suggested_qty,
                "suggested_amount": suggested_amount,
                "suggested_pct": suggested_pct,
            },
        )
        return result
