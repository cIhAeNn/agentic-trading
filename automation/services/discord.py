import json
import os
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, Tuple

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
            try:
                json.dumps(value, default=str)
                payload[key] = value
            except Exception:
                payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _get_runtime_logger(name: str) -> logging.Logger:
    """Create one production logger per service with rotating JSON-line file handlers."""
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


LOGGER = _get_runtime_logger("agentic.discord")


class DiscordMCPConnector:
    """Discord routing service for staged trade approval, approval parsing, and invalidation alerts."""

    CONFIG_PATH = "config/discord_config.yaml"
    DEFAULT_TZ = "America/New_York"

    DEFAULT_CONFIG: Dict[str, Any] = {
        "v": 3,
        "tz": "America/New_York",
        "channel": {"env": "TARGET_CHANNEL_ID", "required": True},
        "approval": {
            "tokens": ["Approve", "Go", "Yes"],
            "case_sensitive": False,
            "timeout_min": 5,
            "size_required": True,
            "size_modes": ["shares", "amount"],
            "text": {
                "shares": r"^(approve|go|yes)\s+shares\s+(\d+)$",
                "amount": r"^(approve|go|yes)\s+amount\s+(\d+(?:\.\d{1,2})?)$",
                "reject": r"^(reject|no|cancel)$",
                "refresh": r"^(refresh|recheck|revalidate)$",
            },
        },
        "safety": {
            "human_approval": True,
            "revalidate_after_approval": True,
            "execute_only_if_valid": True,
            "cry_if_invalid": True,
            "block_if_no_size": True,
            "block_if_timeout": True,
            "block_if_no_buying_power": True,
            "block_if_allocation_exceeded": True,
        },
        "logs": {
            "ok": "logs/activity_ledger.json",
            "err": "logs/error_trace.json",
            "max_rows": 25,
            "events": {
                "staged": "ORDER_STAGED",
                "approved": "ORDER_APPROVED",
                "executed": "ORDER_EXECUTED",
                "invalidated": "ORDER_INVALIDATED",
                "error": "API_ERROR",
            },
        },
        "templates": {
            "trade": (
                "📈 **TRADE?** `{ticker}` `{asset_class}` **{direction}**\n"
                "Pattern: **{pattern_id}: {pattern_name}** | Conf: **{confidence_pct}%** ({confidence_method})\n"
                "Price: now `{current_price}` | entry `{entry_price}` | stop `{stop_loss}` | target `{price_target}` | R/R `{risk_reward_ratio}`\n"
                "Why: {thesis}\n"
                "Account: net `{net_liquidity}` | buying `{buying_power}` | cash `{cash_available}` | pos `{position_qty}` sh / `{position_value}` / `{position_pct}`\n"
                "Size: suggest `{suggested_qty}` sh / `{suggested_amount}` / `{suggested_pct}` | max `{max_pct}` | max-risk `{max_qty_by_risk}` sh\n"
                "Quota: AV `{av_quota}` | TR `{tr_quota}`\n"
                "Reply: `Approve shares 50`, `Approve amount 500`, `Reject`, or `Refresh`.\n"
                "State: `HALTED_AWAITING_APPROVAL`"
            ),
            "approved": (
                "✅ **APPROVED — REVALIDATED**\n"
                "`{ticker}` {direction} | size `{size_mode}` `{size_value}` | staged `{staged_at}`"
            ),
            "executed": (
                "✅ **EXECUTED**\n"
                "`{ticker}` {direction} | qty `{qty}` | notional `{notional}` | fill `{fill_status}` | tx `{tx_id}` | at `{executed_at}`\n"
                "Log: `logs/activity_ledger.json`"
            ),
            "cry": (
                "😭 **CRY — EXECUTION BLOCKED**\n"
                "`{ticker}` {direction}\n"
                "Pattern broke: **{pattern_id}: {pattern_name}**\n"
                "Entry `{entry_price}` | now `{current_price}`\n"
                "Reason: {reason}\n"
                "No trade executed.\n"
                "Log: `logs/error_trace.json`"
            ),
            "timeout": (
                "⏱️ **TIMEOUT**\n"
                "`{ticker}` staged `{staged_at}` exceeded `{timeout_min}` min. No trade executed."
            ),
            "missing_size": (
                "⚠️ **SIZE REQUIRED**\n"
                "Use `Approve shares 50` or `Approve amount 500`. No trade executed."
            ),
            "readiness": (
                "**SYSTEM READINESS**\n"
                "mode `{mode}` | market `{market}` | scheduler `{scheduler}`\n"
                "files `{files}` | logs `{log_access}` | channel `{channel}`\n"
                "MCP: RH `{rh}` | AV `{av}` | TR `{tr}` | WA `{wa}` | DC `{dc}`\n"
                "state `{state}`"
            ),
            "critical": (
                "🚨 **CRITICAL ERROR**\n"
                "endpoint `{endpoint}` | type `{failure_type}` | limit `{tier_limit}` | state `FROZEN`\n"
                "log `logs/error_trace.json`\n"
                "```json\n{payload}\n```"
            ),
        },
    }

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """Load compact Discord YAML config. Fallback to embedded defaults if missing or unreadable."""
        config = json.loads(json.dumps(cls.DEFAULT_CONFIG))

        if not os.path.exists(cls.CONFIG_PATH):
            LOGGER.warning("Discord config missing; embedded defaults active.", extra={"config_path": cls.CONFIG_PATH})
            return config

        try:
            import yaml  # type: ignore
        except Exception:
            LOGGER.warning("PyYAML unavailable; embedded Discord defaults active.", extra={"config_path": cls.CONFIG_PATH})
            return config

        try:
            with open(cls.CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                LOGGER.warning("Discord config parsed as non-dict; embedded defaults active.", extra={"config_path": cls.CONFIG_PATH})
                return config
            return cls._deep_merge(config, loaded)
        except Exception:
            LOGGER.exception("Discord config load failed; embedded defaults active.", extra={"config_path": cls.CONFIG_PATH})
            return config

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge override into base without dropping default keys."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = DiscordMCPConnector._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    @classmethod
    def _now_iso(cls, config: Optional[Dict[str, Any]] = None) -> str:
        config = config or cls._load_config()
        return datetime.now(ZoneInfo(config.get("tz", cls.DEFAULT_TZ))).isoformat()

    @classmethod
    def _target_channel_id(cls) -> Optional[str]:
        config = cls._load_config()
        env_name = config.get("channel", {}).get("env", "TARGET_CHANNEL_ID")
        return runtime_env(env_name)

    @staticmethod
    def _safe_get(state: AgentState, key: str, default: Any = "N/A") -> Any:
        try:
            value = state.get(key, default)
        except Exception:
            value = default
        return default if value is None else value

    @classmethod
    def _primary_setup(cls, state: AgentState) -> Dict[str, Any]:
        """Return first matched setup if available; otherwise use state-level fields."""
        matched = cls._safe_get(state, "matched_setups", [])
        if isinstance(matched, list) and matched:
            first = matched[0]
            if isinstance(first, dict):
                return first
        return {}

    @classmethod
    def _setup_or_state(cls, state: AgentState, setup: Dict[str, Any], key: str, default: Any = "N/A") -> Any:
        return setup.get(key, cls._safe_get(state, key, default))

    @classmethod
    def _basic_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        setup = cls._primary_setup(state)
        return {
            "ticker": cls._setup_or_state(state, setup, "ticker"),
            "direction": cls._setup_or_state(state, setup, "direction"),
            "staged_at": cls._safe_get(state, "order_staged_at"),
        }

    @classmethod
    def _trade_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        setup = cls._primary_setup(state)
        return {
            "ticker": cls._setup_or_state(state, setup, "ticker"),
            "asset_class": cls._setup_or_state(state, setup, "asset_class", "equity"),
            "direction": cls._setup_or_state(state, setup, "direction"),
            "pattern_id": cls._setup_or_state(state, setup, "pattern_id"),
            "pattern_name": cls._setup_or_state(state, setup, "pattern_name"),
            "confidence_pct": cls._setup_or_state(state, setup, "confidence_pct"),
            "confidence_method": cls._setup_or_state(state, setup, "confidence_method", "pattern_score"),
            "current_price": cls._setup_or_state(state, setup, "current_price"),
            "entry_price": cls._setup_or_state(state, setup, "entry_price"),
            "stop_loss": cls._setup_or_state(state, setup, "stop_loss"),
            "price_target": cls._setup_or_state(state, setup, "price_target"),
            "risk_reward_ratio": cls._setup_or_state(state, setup, "risk_reward_ratio"),
            "thesis": setup.get("thesis", cls._safe_get(state, "conviction_thesis", cls._safe_get(state, "thesis"))),
            "net_liquidity": cls._safe_get(state, "net_liquidity"),
            "buying_power": cls._safe_get(state, "buying_power"),
            "cash_available": cls._safe_get(state, "cash_available"),
            "position_qty": cls._safe_get(state, "current_position_qty", cls._safe_get(state, "position_qty")),
            "position_value": cls._safe_get(state, "current_position_market_value", cls._safe_get(state, "position_value")),
            "position_pct": cls._safe_get(state, "current_position_pct", cls._safe_get(state, "position_pct")),
            "suggested_amount": cls._setup_or_state(state, setup, "suggested_amount"),
            "suggested_qty": cls._setup_or_state(state, setup, "suggested_qty"),
            "suggested_pct": cls._setup_or_state(state, setup, "suggested_pct"),
            "max_pct": cls._setup_or_state(state, setup, "max_pct"),
            "max_qty_by_risk": cls._setup_or_state(state, setup, "max_qty_by_risk"),
            "av_quota": cls._safe_get(state, "alpha_vantage_quota", cls._safe_get(state, "av_quota")),
            "tr_quota": cls._safe_get(state, "tipranks_quota", cls._safe_get(state, "tr_quota")),
        }

    @classmethod
    def _approval_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        base = cls._basic_values(state, config)
        base.update({
            "size_mode": cls._safe_get(state, "approval_size_mode"),
            "size_value": cls._safe_get(state, "approval_size_value"),
        })
        return base

    @classmethod
    def _execution_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        setup = cls._primary_setup(state)
        return {
            "ticker": cls._setup_or_state(state, setup, "ticker"),
            "direction": cls._setup_or_state(state, setup, "direction"),
            "qty": cls._safe_get(state, "order_quantity"),
            "notional": cls._safe_get(state, "order_notional"),
            "fill_status": cls._safe_get(state, "fill_status"),
            "tx_id": cls._safe_get(state, "transaction_id"),
            "executed_at": cls._safe_get(state, "executed_at"),
        }

    @classmethod
    def _cry_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        setup = cls._primary_setup(state)
        return {
            "ticker": cls._setup_or_state(state, setup, "ticker"),
            "direction": cls._setup_or_state(state, setup, "direction"),
            "pattern_id": cls._setup_or_state(state, setup, "pattern_id"),
            "pattern_name": cls._setup_or_state(state, setup, "pattern_name"),
            "entry_price": cls._setup_or_state(state, setup, "entry_price"),
            "current_price": cls._setup_or_state(state, setup, "current_price"),
            "reason": cls._safe_get(state, "invalidation_reason", "post-approval pattern revalidation failed"),
        }

    @classmethod
    def _timeout_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        base = cls._basic_values(state, config)
        base["timeout_min"] = config.get("approval", {}).get("timeout_min", 5)
        return base

    @classmethod
    def _readiness_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "mode": cls._safe_get(state, "mode"),
            "market": cls._safe_get(state, "market_state"),
            "scheduler": cls._safe_get(state, "scheduler_state"),
            "files": cls._safe_get(state, "file_parity"),
            "log_access": cls._safe_get(state, "log_access"),
            "channel": "PRESENT" if cls._target_channel_id() else "MISSING",
            "rh": cls._safe_get(state, "robinhood_status"),
            "av": cls._safe_get(state, "alpha_vantage_status"),
            "tr": cls._safe_get(state, "tipranks_status"),
            "wa": cls._safe_get(state, "windsor_status"),
            "dc": cls._safe_get(state, "discord_status"),
            "state": cls._safe_get(state, "system_state"),
        }

    @classmethod
    def _critical_values(cls, state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "endpoint": cls._safe_get(state, "endpoint"),
            "failure_type": cls._safe_get(state, "failure_type"),
            "tier_limit": cls._safe_get(state, "tier_limit"),
            "payload": json.dumps(cls._safe_get(state, "diagnostic_payload", {}), ensure_ascii=False, default=str),
        }

    @classmethod
    def _render(cls, template_key: str, state: AgentState, extra: Optional[Dict[str, Any]] = None) -> str:
        """Render only the value fields required by the selected template."""
        config = cls._load_config()
        extra = extra or {}

        builders = {
            "trade": cls._trade_values,
            "approved": cls._approval_values,
            "executed": cls._execution_values,
            "cry": cls._cry_values,
            "timeout": cls._timeout_values,
            "missing_size": cls._basic_values,
            "readiness": cls._readiness_values,
            "critical": cls._critical_values,
        }

        builder = builders.get(template_key, cls._basic_values)
        values = builder(state, config)
        values.update(extra)

        template = config.get("templates", {}).get(template_key, cls.DEFAULT_CONFIG["templates"].get(template_key, ""))
        return template.format_map(_SafeFormat(values))

    @classmethod
    def _dispatch(cls, message: str) -> None:
        """
        Production dispatch hook.

        In Claude Desktop, the orchestrator must bind this event to the real MCP call:
        discord_send(channel_id=TARGET_CHANNEL_ID, content=message)
        """
        channel_id = cls._target_channel_id()
        if not channel_id:
            LOGGER.error("Discord target channel missing; dispatch blocked.", extra={"event": "DISCORD_CHANNEL_MISSING"})
            raise RuntimeError("TARGET_CHANNEL_ID is missing; Discord dispatch blocked.")

        LOGGER.info(
            "Discord message prepared for MCP dispatch.",
            extra={"event": "DISCORD_MESSAGE_PREPARED", "target_channel_id_present": True, "message_chars": len(message)},
        )

    @classmethod
    def _write_log(cls, event_type: str, status: str, payload: Dict[str, Any]) -> None:
        """Write schema-compliant rolling JSON logs with compact payloads."""
        config = cls._load_config()
        log_key = "ok" if status == "SUCCESS" else "err"
        fallback = "logs/activity_ledger.json" if status == "SUCCESS" else "logs/error_trace.json"
        log_path = config.get("logs", {}).get(log_key, fallback)
        max_rows = int(config.get("logs", {}).get("max_rows", 25))

        entry = {"timestamp": cls._now_iso(config), "event_type": event_type, "status": status, "payload": payload}

        rows = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                if not isinstance(rows, list):
                    rows = []
            except Exception:
                LOGGER.exception("Audit log read failed; resetting in memory.", extra={"log_path": log_path})
                rows = []

        rows.append(entry)
        rows = rows[-max_rows:]

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False, default=str)

        LOGGER.info("Audit event written.", extra={"event": event_type, "status": status, "log_path": log_path})

    @classmethod
    def _log_event_name(cls, event_key: str, default: str) -> str:
        config = cls._load_config()
        return config.get("logs", {}).get("events", {}).get(event_key, default)

    @classmethod
    def submit_trade_blotter(cls, state: AgentState) -> Dict[str, Any]:
        """Stage a trade candidate, prepare approval request, and log ORDER_STAGED."""
        config = cls._load_config()
        timestamp_str = cls._now_iso(config)

        message = cls._render("trade", state)
        cls._dispatch(message)

        event_type = cls._log_event_name("staged", "ORDER_STAGED")
        setup = cls._primary_setup(state)

        cls._write_log(
            event_type,
            "SUCCESS",
            {
                "ticker": setup.get("ticker", cls._safe_get(state, "ticker")),
                "direction": setup.get("direction", cls._safe_get(state, "direction")),
                "pattern_id": setup.get("pattern_id", cls._safe_get(state, "pattern_id")),
                "pattern_name": setup.get("pattern_name", cls._safe_get(state, "pattern_name")),
                "target_channel_id_present": bool(cls._target_channel_id()),
                "execution_status": "STAGED_AWAITING_APPROVAL",
            },
        )

        LOGGER.info(
            "Trade blotter staged.",
            extra={"event": event_type, "ticker": setup.get("ticker", cls._safe_get(state, "ticker"))},
        )

        return {"execution_status": "STAGED_AWAITING_APPROVAL", "order_staged_at": timestamp_str, "discord_message": message}

    @classmethod
    def run_post_approval_revalidation(cls, state: AgentState) -> Dict[str, Any]:
        """
        Parse operator approval, enforce timeout/size, and require explicit fresh pattern validity.

        Missing pattern_still_valid never defaults to true.
        """
        config = cls._load_config()
        now = datetime.now(ZoneInfo(config.get("tz", cls.DEFAULT_TZ)))

        staged_raw = cls._safe_get(state, "order_staged_at", None)
        if not staged_raw:
            return cls._reject(state, "REJECTED_MISSING_STAGED_TIME", "Missing staged order timestamp.")

        try:
            staged_time = datetime.fromisoformat(staged_raw)
            if staged_time.tzinfo is None:
                staged_time = staged_time.replace(tzinfo=ZoneInfo(config.get("tz", cls.DEFAULT_TZ)))
        except Exception:
            return cls._reject(state, "REJECTED_INVALID_STAGED_TIME", "Invalid staged order timestamp.")

        timeout_min = int(config.get("approval", {}).get("timeout_min", 5))
        if now - staged_time > timedelta(minutes=timeout_min):
            message = cls._render("timeout", state, {"timeout_min": timeout_min, "staged_at": staged_raw})
            cls._dispatch(message)
            return cls._reject(state, "TIMEOUT_EXPIRED", "Operator response exceeded timeout window.", {"template": "timeout"})

        operator_msg = str(
            cls._safe_get(
                state,
                "operator_msg_payload",
                cls._safe_get(state, "discord_operator_message", cls._safe_get(state, "approval_message", "")),
            )
        ).strip()

        action = cls._parse_operator_message(operator_msg, config)

        if action[0] == "reject":
            return cls._reject(state, "REJECTED_BY_OPERATOR", "Operator rejected staged order.")

        if action[0] == "refresh":
            LOGGER.info("Operator requested signal refresh.", extra={"event": "REFRESH_REQUESTED"})
            return {"revalidation_passed": False, "execution_status": "REFRESH_REQUESTED", "operator_action": "refresh"}

        if action[0] == "missing_size":
            message = cls._render("missing_size", state)
            cls._dispatch(message)
            return cls._reject(state, "REJECTED_MISSING_SIZE", "Missing explicit shares or dollar amount.", {"template": "missing_size"})

        if action[0] != "approved":
            message = cls._render("missing_size", state)
            cls._dispatch(message)
            return cls._reject(state, "REJECTED_INVALID_APPROVAL_FORMAT", "Approval format not recognized.", {"template": "missing_size"})

        _, size_mode, size_value = action

        pattern_valid = cls._safe_get(state, "pattern_still_valid", None)
        if pattern_valid is not True:
            if pattern_valid is False:
                return cls.emit_cry_alert(
                    {
                        **state,
                        "invalidation_reason": cls._safe_get(
                            state,
                            "invalidation_reason",
                            "post-approval pattern revalidation failed",
                        ),
                    }
                )

            LOGGER.info(
                "Approval parsed; fresh pattern recheck required before execution.",
                extra={"event": "POST_APPROVAL_PATTERN_RECHECK_REQUIRED", "size_mode": size_mode, "size_value": size_value},
            )
            result = {
                "revalidation_passed": False,
                "execution_status": "POST_APPROVAL_PATTERN_RECHECK_REQUIRED",
                "approval_size_mode": size_mode,
                "approval_size_value": size_value,
                "operator_action": "approved_pending_revalidation",
            }
            if size_mode == "shares":
                result["order_quantity"] = int(size_value)
            elif size_mode == "amount":
                result["order_notional"] = float(size_value)
            return result

        extra = {"size_mode": size_mode, "size_value": size_value, "staged_at": staged_raw}
        message = cls._render("approved", state, extra)
        cls._dispatch(message)

        event_type = cls._log_event_name("approved", "ORDER_APPROVED")
        cls._write_log(event_type, "SUCCESS", {"size_mode": size_mode, "size_value": size_value, "execution_status": "APPROVED_REVALIDATION_PASSED"})

        result = {
            "revalidation_passed": True,
            "execution_status": "APPROVED_REVALIDATION_PASSED",
            "approval_size_mode": size_mode,
            "approval_size_value": size_value,
            "discord_message": message,
        }

        if size_mode == "shares":
            result["order_quantity"] = int(size_value)
        elif size_mode == "amount":
            result["order_notional"] = float(size_value)

        return result

    @classmethod
    def emit_execution_confirmation(cls, state: AgentState) -> Dict[str, Any]:
        """Prepare execution confirmation and log ORDER_EXECUTED."""
        executed_at = cls._now_iso()
        message = cls._render("executed", state, {"executed_at": executed_at})
        cls._dispatch(message)

        event_type = cls._log_event_name("executed", "ORDER_EXECUTED")
        cls._write_log(
            event_type,
            "SUCCESS",
            {
                "ticker": cls._safe_get(state, "ticker"),
                "direction": cls._safe_get(state, "direction"),
                "quantity": cls._safe_get(state, "order_quantity"),
                "notional": cls._safe_get(state, "order_notional"),
                "transaction_id": cls._safe_get(state, "transaction_id"),
            },
        )

        return {"execution_status": "EXECUTED_CONFIRMED", "executed_at": executed_at, "discord_message": message}

    @classmethod
    def emit_cry_alert(cls, state: AgentState) -> Dict[str, Any]:
        """Prepare CRY invalidation alert, block execution, and log ORDER_INVALIDATED."""
        message = cls._render("cry", state)
        cls._dispatch(message)

        event_type = cls._log_event_name("invalidated", "ORDER_INVALIDATED")
        reason = cls._safe_get(state, "invalidation_reason", "post-approval pattern revalidation failed")
        cls._write_log(
            event_type,
            "FAILED",
            {
                "ticker": cls._safe_get(state, "ticker"),
                "direction": cls._safe_get(state, "direction"),
                "reason": reason,
                "execution_status": "INVALIDATED_CANCELLED_CLEAN",
            },
        )

        LOGGER.warning("Order invalidated after approval.", extra={"event": event_type, "ticker": cls._safe_get(state, "ticker"), "reason": reason})
        return {"revalidation_passed": False, "execution_status": "INVALIDATED_CANCELLED_CLEAN", "discord_message": message}

    @classmethod
    def emit_readiness_blotter(cls, state: AgentState) -> Dict[str, Any]:
        """Prepare compact system readiness blotter."""
        message = cls._render("readiness", state)
        cls._dispatch(message)
        return {"execution_status": "READINESS_REPORTED", "discord_message": message}

    @classmethod
    def emit_critical_error(cls, state: AgentState) -> Dict[str, Any]:
        """Prepare critical fault card and log API_ERROR."""
        message = cls._render("critical", state)
        try:
            cls._dispatch(message)
        except Exception:
            LOGGER.exception("Critical Discord dispatch failed.", extra={"event": "CRITICAL_DISPATCH_FAILED"})

        event_type = cls._log_event_name("error", "API_ERROR")
        cls._write_log(
            event_type,
            "FAILED",
            {
                "endpoint": cls._safe_get(state, "endpoint"),
                "failure_type": cls._safe_get(state, "failure_type"),
                "tier_limit": cls._safe_get(state, "tier_limit"),
                "diagnostic_payload": cls._safe_get(state, "diagnostic_payload", {}),
            },
        )

        return {"execution_status": "CRITICAL_ERROR_REPORTED", "processing_state": "FROZEN"}

    @classmethod
    def _parse_operator_message(cls, message: str, config: Dict[str, Any]) -> Tuple[Any, ...]:
        """Parse text fallback approvals: Approve shares 50, Approve amount 500, Reject, Refresh."""
        approval_cfg = config.get("approval", {})
        patterns = approval_cfg.get("text", {})
        flags = 0 if approval_cfg.get("case_sensitive", False) else re.IGNORECASE

        if re.match(patterns.get("reject", r"^(reject|no|cancel)$"), message, flags):
            return ("reject",)

        if re.match(patterns.get("refresh", r"^(refresh|recheck|revalidate)$"), message, flags):
            return ("refresh",)

        shares_match = re.match(patterns.get("shares", r"^(approve|go|yes)\s+shares\s+(\d+)$"), message, flags)
        if shares_match:
            return ("approved", "shares", int(shares_match.group(2)))

        amount_match = re.match(patterns.get("amount", r"^(approve|go|yes)\s+amount\s+(\d+(?:\.\d{1,2})?)$"), message, flags)
        if amount_match:
            return ("approved", "amount", float(amount_match.group(2)))

        legacy = re.match(r"^(approve|go|yes)\s+(\d+)$", message, flags)
        if legacy:
            return ("approved", "shares", int(legacy.group(2)))

        return ("missing_size",)

    @classmethod
    def _reject(
        cls,
        state: AgentState,
        status: str,
        reason: str,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write failed approval-state branch to error log."""
        event_type = cls._log_event_name("error", "API_ERROR")
        payload = {
            "reason": reason,
            "execution_status": status,
            "ticker": cls._safe_get(state, "ticker"),
            "direction": cls._safe_get(state, "direction"),
        }
        if extra_payload:
            payload.update(extra_payload)

        cls._write_log(event_type, "FAILED", payload)
        LOGGER.warning("Approval branch rejected.", extra={"event": event_type, "status": status, "reason": reason})
        return {"revalidation_passed": False, "execution_status": status, "rejection_reason": reason}


class _SafeFormat(dict):
    """Prevent KeyError during template rendering by displaying missing fields as N/A."""

    def __missing__(self, key: str) -> str:
        return "N/A"
