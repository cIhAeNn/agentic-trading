from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass(frozen=True)
class AccountInfo:
    account_number: str
    buying_power: float
    portfolio_cash: float
    portfolio_value: float
    is_day_trade_restricted: bool

@dataclass(frozen=True)
class HistoricalCandle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass(frozen=True)
class MarketSnapshot:
    ticker: str
    current_price: float
    candles: List[HistoricalCandle]

@dataclass(frozen=True)
class OrderResult:
    order_id: str
    ticker: str
    side: str
    state: str
    quantity: Optional[float]
    notional_usd: Optional[float]
    average_price: Optional[float]
    timestamp: datetime