from abc import ABC, abstractmethod
from typing import Any, Optional


class ILoggerTool(ABC):
    """
    Interface contract for generalized application logging.
    Allows for easy swapping of logging implementations (e.g., File, Console, Cloud).
    """

    @abstractmethod
    def debug(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def info(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def warning(self, message: str, context: Optional[str] = None, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def error(self, message: str, context: Optional[str] = None, exc_info: bool = False, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def critical(self, message: str, context: Optional[str] = None, exc_info: bool = False, **kwargs: Any) -> None:
        pass