from typing import List


def build_historical_requests(tickers: List[str]) -> List[dict]:
    """Compact batch handoff payload for Claude/MCP to fetch real OHLCV candles."""
    if not tickers:
        return []

    return [
        {
            "tool_family": "Robinhood MCP or market-data MCP",
            "action": "fetch_historical_ohlcv_batch",
            "tickers": tickers,
            "interval": "day",
            "span": "3month",
            "required_fields": ["open", "high", "low", "close", "volume", "timestamp"],
        }
    ]
