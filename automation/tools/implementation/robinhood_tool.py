from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

# Domain Models
from automation.models.robinhood_models import (
    AccountInfo, MarketSnapshot, OrderResult, PositionInfo, LiveQuote
)

# Interface
from automation.tools.implementation.logger_tool import LoggerTool
from automation.tools.interface.logger_tool_interface import ILoggerTool
from automation.tools.interface.robinhood_tool_interface import IRobinhoodTool


class RobinhoodTool(IRobinhoodTool):
    """
    Concrete implementation of IRobinhoodTool.
    This implementation bridges the Interface to your Robinhood MCP server.
    """

    def __init__(self, logger: Optional[ILoggerTool] = None, mcp_client: Any = None):
        self.logger = logger or LoggerTool()
        self.mcp = mcp_client  # The client connected to your Robinhood MCP server
        self.ctx = "RobinhoodTool"

    def _call_mcp(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Helper to invoke MCP tools safely."""
        try:
            return self.mcp.call_tool(tool_name, args)
        except Exception as e:
            self.logger.error(f"MCP Call Failed: {tool_name} | Error: {e}", context=self.ctx)
            raise RuntimeError(f"Robinhood MCP Error: {e}")

    # --- ACCOUNT & PORTFOLIO ---
    def get_account_information(self) -> AccountInfo:
        data = self._call_mcp("get_account_info", {})
        self.logger.info("Retrieved account information.", context=self.ctx)
        return AccountInfo(**data)

    def get_open_positions(self) -> List[PositionInfo]:
        data = self._call_mcp("get_positions", {})
        return [PositionInfo(**p) for p in data]

    def get_open_orders(self) -> List[OrderResult]:
        data = self._call_mcp("get_orders", {"status": "queued"})
        return [OrderResult(**o) for o in data]

    # --- MARKET DATA ---
    def get_batch_market_snapshots(
        self, tickers: List[str], interval: str = "day", span: str = "3month"
    ) -> Dict[str, MarketSnapshot]:
        self.logger.info(f"Fetching {len(tickers)} snapshots.", context=self.ctx)
        data = self._call_mcp("get_market_data", {
            "tickers": tickers, "interval": interval, "span": span
        })
        return {t: MarketSnapshot(**s) for t, s in data.items()}

    def get_realtime_quote(self, ticker: str) -> LiveQuote:
        data = self._call_mcp("get_quote", {"ticker": ticker})
        return LiveQuote(**data)

    # --- EXECUTION ---
    def execute_buy(self, ticker: str, amount_usd: Optional[float] = None, quantity: Optional[float] = None) -> OrderResult:
        self.logger.info(f"Executing BUY: {ticker}", context=self.ctx)
        resp = self._call_mcp("place_order", {
            "ticker": ticker, "side": "buy", "amount_usd": amount_usd, "quantity": quantity
        })
        return OrderResult(**resp)

    def execute_limit_buy(self, ticker: str, limit_price: float, quantity: float) -> OrderResult:
        self.logger.info(f"Executing LIMIT BUY: {ticker} @ {limit_price}", context=self.ctx)
        resp = self._call_mcp("place_order", {
            "ticker": ticker, "side": "buy", "limit_price": limit_price, "quantity": quantity, "type": "limit"
        })
        return OrderResult(**resp)

    def execute_stop_loss(self, ticker: str, stop_price: float, quantity: float) -> OrderResult:
        self.logger.info(f"Executing STOP LOSS: {ticker} @ {stop_price}", context=self.ctx)
        resp = self._call_mcp("place_order", {
            "ticker": ticker, "side": "sell", "stop_price": stop_price, "quantity": quantity, "type": "stop"
        })
        return OrderResult(**resp)

    def execute_sell(self, ticker: str, amount_usd: Optional[float] = None, quantity: Optional[float] = None) -> OrderResult:
        self.logger.info(f"Executing SELL: {ticker}", context=self.ctx)
        resp = self._call_mcp("place_order", {
            "ticker": ticker, "side": "sell", "amount_usd": amount_usd, "quantity": quantity
        })
        return OrderResult(**resp)

    def cancel_order(self, order_id: str) -> bool:
        self.logger.info(f"Cancelling order: {order_id}", context=self.ctx)
        return self._call_mcp("cancel_order", {"order_id": order_id})