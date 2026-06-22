from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from automation.domain.patterns.models import PivotSet


def find_pivots(df: pd.DataFrame) -> PivotSet:
    """Find swing highs/lows with ATR-adaptive prominence."""
    highs = df["high"].astype(float).to_numpy()
    lows = df["low"].astype(float).to_numpy()

    price = float(df["close"].iloc[-1])
    atr_series = df["atr_14"].dropna() if "atr_14" in df else pd.Series(dtype=float)
    atr = float(atr_series.tail(10).mean()) if not atr_series.empty else price * 0.01

    prominence = max(atr * 0.55, price * 0.005)
    high_idx, _ = find_peaks(highs, distance=3, prominence=prominence)
    low_idx, _ = find_peaks(-lows, distance=3, prominence=prominence)

    if len(high_idx) < 3:
        high_idx, _ = find_peaks(highs, distance=3, prominence=max(prominence * 0.45, price * 0.0025))
    if len(low_idx) < 3:
        low_idx, _ = find_peaks(-lows, distance=3, prominence=max(prominence * 0.45, price * 0.0025))

    return PivotSet(
        high_idx=high_idx,
        low_idx=low_idx,
        high_values=highs[high_idx] if len(high_idx) else np.array([]),
        low_values=lows[low_idx] if len(low_idx) else np.array([]),
    )


def last_pivots(indices: np.ndarray, values: np.ndarray, n: int) -> List[Tuple[int, float]]:
    return list(zip(indices.tolist(), values.tolist()))[-n:]


def similar(a: float, b: float, tolerance: float) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / ((a + b) / 2) <= tolerance


def max_high_between(df: pd.DataFrame, start: int, end: int) -> Optional[float]:
    if end <= start + 1:
        return None
    return float(df["high"].iloc[start + 1:end].max())


def min_low_between(df: pd.DataFrame, start: int, end: int) -> Optional[float]:
    if end <= start + 1:
        return None
    return float(df["low"].iloc[start + 1:end].min())


def recent_channel(df: pd.DataFrame, pivots: PivotSet) -> Optional[Tuple[float, float]]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 4)
    lows = last_pivots(pivots.low_idx, pivots.low_values, 4)

    if len(highs) < 2 or len(lows) < 2:
        return None

    high_values = [x[1] for x in highs]
    low_values = [x[1] for x in lows]

    if max(high_values) / min(high_values) - 1 > 0.05:
        return None
    if max(low_values) / min(low_values) - 1 > 0.05:
        return None

    floor = float(np.mean(low_values))
    ceiling = float(np.mean(high_values))

    if ceiling <= floor or (ceiling - floor) / floor > 0.25:
        return None

    return floor, ceiling
