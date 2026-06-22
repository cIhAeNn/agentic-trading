from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from automation.models.robinhood_models import (
    AccountInfo,
    LiveQuote,
    MarketSnapshot,
    OrderResult,
    PositionInfo,
)


class IRobinhoodTool(ABC):
    """
    Interface contract for Robinhood trading and market data operations.
    """

    @abstractmethod
    def get_account_information(self) -> AccountInfo:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[PositionInfo]:
        pass

    @abstractmethod
    def get_open_orders(self) -> List[OrderResult]:
        pass

    @abstractmethod
    def get_batch_market_snapshots(
        self, tickers: List[str], interval: str = "day", span: str = "3month"
    ) -> Dict[str, MarketSnapshot]:
        pass

    @abstractmethod
    def get_realtime_quote(self, ticker: str) -> LiveQuote:
        pass

    @abstractmethod
    def execute_buy(
        self, ticker: str, amount_usd: Optional[float] = None, quantity: Optional[float] = None
    ) -> OrderResult:
        pass

    @abstractmethod
    def execute_limit_buy(self, ticker: str, limit_price: float, quantity: float) -> OrderResult:
        pass

    @abstractmethod
    def execute_sell(
        self, ticker: str, amount_usd: Optional[float] = None, quantity: Optional[float] = None
    ) -> OrderResult:
        pass

    @abstractmethod
    def execute_stop_loss(self, ticker: str, stop_price: float, quantity: float) -> OrderResult:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
