from typing import Any, Dict, Optional

import pandas as pd


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except Exception:
        return None


def normalize_ohlcv(snapshot: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Normalize common MCP historical candle payloads into OHLCV DataFrame."""
    candles = None

    for key in ("candles", "historicals", "ohlcv", "bars", "prices", "data"):
        value = snapshot.get(key)
        if isinstance(value, list) and value:
            candles = value
            break

    if candles is None:
        quote = snapshot.get("quote")
        if isinstance(quote, dict):
            return normalize_ohlcv(quote)
        return None

    rows = []
    for item in candles:
        if not isinstance(item, dict):
            continue

        row = {
            "timestamp": item.get("timestamp") or item.get("begins_at") or item.get("date") or item.get("time"),
            "open": as_float(item.get("open_price", item.get("open"))),
            "high": as_float(item.get("high_price", item.get("high"))),
            "low": as_float(item.get("low_price", item.get("low"))),
            "close": as_float(item.get("close_price", item.get("close", item.get("last_trade_price")))),
            "volume": as_float(item.get("volume")),
        }

        if all(row[k] is not None for k in ("open", "high", "low", "close", "volume")):
            rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame(rows)

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
    return df if not df.empty else None


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add vectorized indicators used by detectors."""
    df = df.copy()

    df["avg_20_day_volume"] = df["volume"].rolling(20, min_periods=10).mean()
    df["sma_20"] = df["close"].rolling(20, min_periods=10).mean()
    df["sma_50"] = df["close"].rolling(50, min_periods=20).mean()

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["atr_14"] = tr.rolling(14, min_periods=10).mean()
    return df
