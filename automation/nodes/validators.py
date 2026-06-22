import json
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict

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


LOGGER = _get_runtime_logger("agentic.validators")


class SystemValidators:
    """Pre-flight and file-ingestion validators for scheduled LangGraph runs."""

    REQUIRED_PATHS = [
        "data/agentic_screening.md",
        "data/10_trading_patterns.md",
        "automation/nodes/pattern_engine.py",
        "automation/nodes/patterns/engine.py",
        "automation/services/discord.py",
        "automation/services/robinhood.py",
        "config/discord_config.yaml",
        "logs/activity_ledger.json",
        "logs/error_trace.json",
    ]

    @staticmethod
    def run_pre_flight(state: AgentState) -> Dict:
        """Validate market-window access and required runtime files."""
        try:
            os.makedirs("logs", exist_ok=True)

            missing = [path for path in SystemValidators.REQUIRED_PATHS if not os.path.exists(path)]
            if missing:
                LOGGER.error(
                    "Pre-flight missing required paths.",
                    extra={"event": "PRE_FLIGHT_MISSING_PATHS", "missing": missing},
                )
                return {"execution_status": "PRE_FLIGHT_FAILED", "missing_paths": missing}

            if runtime_env("MARKET_OVERRIDE", "FALSE") == "TRUE":
                LOGGER.warning(
                    "Market clock override active via config/env.",
                    extra={"event": "MARKET_OVERRIDE_ACTIVE"},
                )
                return {"execution_status": "PRE_FLIGHT_PASSED", "market_override": True}

            now_est = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
            if now_est < "09:30" or now_est > "17:30":
                LOGGER.info(
                    "Market time out of bounds; clean hibernate.",
                    extra={"event": "LOW_POWER_HIBERNATE", "time_et": now_est},
                )
                return {
                    "execution_status": "LOW_POWER_HIBERNATE",
                    "market_open": False,
                    "time_et": now_est,
                }

            LOGGER.info("Pre-flight passed.", extra={"event": "PRE_FLIGHT_PASSED", "time_et": now_est})
            return {"execution_status": "PRE_FLIGHT_PASSED", "market_open": True, "time_et": now_est}

        except Exception as exc:
            LOGGER.exception("Pre-flight validator crashed.", extra={"event": "PRE_FLIGHT_FAILED"})
            return {"execution_status": "PRE_FLIGHT_FAILED", "error": str(exc)}

    @staticmethod
    def run_universe_ingestion(state: AgentState) -> Dict:
        """Load tickers using the same parser as the pattern engine."""
        try:
            from automation.nodes.pattern_engine import PatternEngine

            tickers = PatternEngine.load_universe("data/agentic_screening.md")
            LOGGER.info(
                "Screening universe ingested.",
                extra={
                    "event": "SCREENING_UNIVERSE_INGESTED",
                    "path": "data/agentic_screening.md",
                    "ticker_count": len(tickers),
                },
            )

            if not tickers:
                return {"ticker_universe": [], "execution_status": "SCREENING_EMPTY"}

            return {"ticker_universe": tickers, "execution_status": "SCREENING_LOADED"}

        except Exception as exc:
            LOGGER.exception(
                "Screening universe ingestion failed.",
                extra={"event": "SCREENING_INGESTION_FAILED", "path": "data/agentic_screening.md"},
            )
            return {
                "ticker_universe": [],
                "execution_status": "SCREENING_INGESTION_FAILED",
                "error": str(exc),
            }
