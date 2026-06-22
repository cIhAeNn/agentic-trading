import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from automation.nodes.patterns.models import normalize_mode


_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message",
}


class JsonFormatter(logging.Formatter):
    """Small JSON-line formatter for runtime logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def get_runtime_logger(name: str) -> logging.Logger:
    """Create one production logger with rotating JSON-line file handlers."""
    mode = normalize_mode()
    level = logging.DEBUG if mode == "DEBUG" else logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    os.makedirs("logs", exist_ok=True)

    runtime = RotatingFileHandler("logs/runtime.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    runtime.setLevel(level)
    runtime.setFormatter(JsonFormatter())

    errors = RotatingFileHandler("logs/runtime_error.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    errors.setLevel(logging.WARNING)
    errors.setFormatter(JsonFormatter())

    logger.addHandler(runtime)
    logger.addHandler(errors)
    return logger
