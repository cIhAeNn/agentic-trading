from typing import Callable, Optional

import pandas as pd

from automation.domain.patterns.models import EngineConfig, PatternRule, PivotSet
from automation.domain.patterns.pivots import (
    last_pivots,
    max_high_between,
    min_low_between,
    recent_channel,
    similar,
)
from automation.domain.patterns.scoring import build_setup, volume_ok


Detector = Callable[[str, pd.DataFrame, PivotSet, PatternRule, EngineConfig], Optional[dict]]


def inverse_head_shoulders(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    lows = last_pivots(pivots.low_idx, pivots.low_values, 3)
    if len(lows) < 3:
        return None
    left, head, right = lows[-3], lows[-2], lows[-1]
    if not (head[1] < left[1] and head[1] < right[1] and similar(left[1], right[1], 0.07)):
        return None
    neckline = max_high_between(df, int(left[0]), int(right[0]))
    if neckline is None:
        return None
    price = float(df["close"].iloc[-1])
    if price > neckline and volume_ok(df, 2.0, config):
        depth = neckline - head[1]
        return build_setup(ticker, rule, price, price, head[1] * 0.99, price + depth, "Inverse H&S breakout above neckline.", {"neckline": neckline, "depth": depth}, df, config)
    return None


def head_shoulders(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 3)
    if len(highs) < 3:
        return None
    left, head, right = highs[-3], highs[-2], highs[-1]
    if not (head[1] > left[1] and head[1] > right[1] and similar(left[1], right[1], 0.07)):
        return None
    neckline = min_low_between(df, int(left[0]), int(right[0]))
    if neckline is None:
        return None
    price = float(df["close"].iloc[-1])
    if price < neckline and volume_ok(df, 2.0, config):
        depth = head[1] - neckline
        return build_setup(ticker, rule, price, price, head[1] * 1.01, price - depth, "Head & Shoulders breakdown below neckline.", {"neckline": neckline, "depth": depth}, df, config)
    return None


def double_bottom(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    lows = last_pivots(pivots.low_idx, pivots.low_values, 2)
    if len(lows) < 2:
        return None
    low1, low2 = lows[-2], lows[-1]
    if not similar(low1[1], low2[1], 0.035):
        return None
    peak = max_high_between(df, int(low1[0]), int(low2[0]))
    if peak is None:
        return None
    price = float(df["close"].iloc[-1])
    if price > peak and volume_ok(df, 1.5, config):
        depth = peak - min(low1[1], low2[1])
        return build_setup(ticker, rule, price, price, min(low1[1], low2[1]) * 0.99, price + depth, "Double bottom breakout above peak resistance.", {"peak": peak, "depth": depth}, df, config)
    return None


def triple_bottom(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    lows = last_pivots(pivots.low_idx, pivots.low_values, 3)
    if len(lows) < 3:
        return None
    values = [x[1] for x in lows[-3:]]
    if max(values) / min(values) - 1 > 0.045:
        return None
    resistance = max_high_between(df, int(lows[-3][0]), int(lows[-1][0]))
    if resistance is None:
        return None
    price = float(df["close"].iloc[-1])
    if price > resistance and volume_ok(df, 2.0, config):
        depth = resistance - min(values)
        return build_setup(ticker, rule, price, price, min(values) * 0.99, price + depth, "Triple bottom breakout above resistance.", {"resistance": resistance, "depth": depth}, df, config)
    return None


def double_top(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 2)
    if len(highs) < 2:
        return None
    high1, high2 = highs[-2], highs[-1]
    if not similar(high1[1], high2[1], 0.035):
        return None
    valley = min_low_between(df, int(high1[0]), int(high2[0]))
    if valley is None:
        return None
    price = float(df["close"].iloc[-1])
    if price < valley and volume_ok(df, 1.5, config):
        depth = max(high1[1], high2[1]) - valley
        return build_setup(ticker, rule, price, price, max(high1[1], high2[1]) * 1.01, price - depth, "Double top breakdown below valley support.", {"valley": valley, "depth": depth}, df, config)
    return None


def triple_top(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 3)
    if len(highs) < 3:
        return None
    values = [x[1] for x in highs[-3:]]
    if max(values) / min(values) - 1 > 0.045:
        return None
    support = min_low_between(df, int(highs[-3][0]), int(highs[-1][0]))
    if support is None:
        return None
    price = float(df["close"].iloc[-1])
    if price < support and volume_ok(df, 2.0, config):
        depth = max(values) - support
        return build_setup(ticker, rule, price, price, max(values) * 1.01, price - depth, "Triple top breakdown below support.", {"support": support, "depth": depth}, df, config)
    return None


def rectangle_bottom(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    channel = recent_channel(df, pivots)
    if not channel:
        return None
    floor, ceiling = channel
    price = float(df["close"].iloc[-1])
    height = ceiling - floor
    if price > ceiling and volume_ok(df, 2.0, config):
        return build_setup(ticker, rule, price, price, floor * 0.99, price + height, "Rectangle breakout above consolidation ceiling.", {"floor": floor, "ceiling": ceiling, "height": height}, df, config)
    return None


def rectangle_top(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    channel = recent_channel(df, pivots)
    if not channel:
        return None
    floor, ceiling = channel
    price = float(df["close"].iloc[-1])
    height = ceiling - floor
    if price < floor and volume_ok(df, 2.0, config):
        return build_setup(ticker, rule, price, price, ceiling * 1.01, price - height, "Rectangle breakdown below consolidation floor.", {"floor": floor, "ceiling": ceiling, "height": height}, df, config)
    return None


def ascending_triangle(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 3)
    lows = last_pivots(pivots.low_idx, pivots.low_values, 3)
    if len(highs) < 2 or len(lows) < 2:
        return None
    hv = [x[1] for x in highs[-3:]]
    lv = [x[1] for x in lows[-3:]]
    resistance = max(hv)
    price = float(df["close"].iloc[-1])
    if max(hv) / min(hv) - 1 <= 0.04 and lv[-1] > lv[0] and price > resistance and volume_ok(df, 2.0, config):
        height = resistance - min(lv)
        return build_setup(ticker, rule, price, price, lv[-1] * 0.99, price + height, "Ascending triangle breakout above flat resistance.", {"resistance": resistance, "height": height}, df, config)
    return None


def descending_triangle(ticker: str, df: pd.DataFrame, pivots: PivotSet, rule: PatternRule, config: EngineConfig) -> Optional[dict]:
    highs = last_pivots(pivots.high_idx, pivots.high_values, 3)
    lows = last_pivots(pivots.low_idx, pivots.low_values, 3)
    if len(highs) < 2 or len(lows) < 2:
        return None
    hv = [x[1] for x in highs[-3:]]
    lv = [x[1] for x in lows[-3:]]
    support = min(lv)
    price = float(df["close"].iloc[-1])
    if max(lv) / min(lv) - 1 <= 0.04 and hv[-1] < hv[0] and price < support and volume_ok(df, 2.0, config):
        height = max(hv) - support
        return build_setup(ticker, rule, price, price, hv[-1] * 1.01, price - height, "Descending triangle breakdown below flat support.", {"support": support, "height": height}, df, config)
    return None


DETECTORS = {
    "Pattern #1": inverse_head_shoulders,
    "Pattern #2": head_shoulders,
    "Pattern #3": double_bottom,
    "Pattern #4": triple_bottom,
    "Pattern #5": double_top,
    "Pattern #6": triple_top,
    "Pattern #7": rectangle_bottom,
    "Pattern #8": rectangle_top,
    "Pattern #9": ascending_triangle,
    "Pattern #10": descending_triangle,
}
