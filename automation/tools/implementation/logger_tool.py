import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from automation.tools.interface.logger_tool_interface import ILoggerTool


class LoggerTool(ILoggerTool):
    """
    Concrete implementation of ILoggerTool using RotatingFileHandler.
    Centralizes log formatting and file rotation for the entire application.
    """

    def __init__(
        self,
        log_dir: str = "logs",
        log_file: str = "agentic_trading.log",
        max_bytes: int = 5 * 1024 * 1024,  # 5 MB
        backup_count: int = 3,
        level: int = logging.INFO
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_path = self.log_dir / log_file
        
        # We use a base logger for the tool, but dynamic contexts will wrap this
        self._base_logger = logging.getLogger("AppLogger")
        self._base_logger.setLevel(level)

        # Prevent adding multiple handlers if instantiated multiple times
        if not self._base_logger.handlers:
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            # Rotating file handler
            file_handler = RotatingFileHandler(
                filename=self.log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            self._base_logger.addHandler(file_handler)

            # Optional: Console handler for development
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._base_logger.addHandler(console_handler)

    def _get_logger_for_context(self, context: Optional[str]) -> logging.Logger:
        """Returns a child logger specific to the requested context."""
        if context:
            return self._base_logger.getChild(context)
        return self._base_logger

    def debug(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        self._get_logger_for_context(context).debug(message, extra=kwargs)

    def info(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        self._get_logger_for_context(context).info(message, extra=kwargs)

    def warning(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        self._get_logger_for_context(context).warning(message, extra=kwargs)

    def error(self, message: str, context: Optional[str] = None, exc_info: bool = False, **kwargs: Any) -> None:
        self._get_logger_for_context(context).error(message, exc_info=exc_info, extra=kwargs)

    def critical(self, message: str, context: Optional[str] = None, exc_info: bool = False, **kwargs: Any) -> None:
        self._get_logger_for_context(context).critical(message, exc_info=exc_info, extra=kwargs)