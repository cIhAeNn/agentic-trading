from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

import pandas as pd

from automation.domain.patterns.models import EngineConfig, PatternRule


def trend_ok(df: pd.DataFrame, direction: str) -> bool:
    """Precision filter: require price/trend alignment when moving averages exist."""
    price = float(df["close"].iloc[-1])
    sma20 = df["sma_20"].iloc[-1]
    sma50 = df["sma_50"].iloc[-1]

    if pd.isna(sma20) or pd.isna(sma50):
        return True

    if direction == "BUY":
        return price >= sma20 or sma20 >= sma50

    if direction == "SELL":
        return price <= sma20 or sma20 <= sma50

    return True


def volume_ok(df: pd.DataFrame, multiplier: float, config: EngineConfig) -> bool:
    current_volume = float(df["volume"].iloc[-1])
    avg20 = df["avg_20_day_volume"].iloc[-1]

    if pd.isna(avg20) or avg20 <= 0:
        return False

    required = max(multiplier, 2.0) if config.use_global_volume_override else multiplier
    return current_volume >= required * float(avg20)


def confidence_score(success_rate: float, risk_reward: float, trend_aligned: bool) -> float:
    score = success_rate

    if risk_reward >= 2.0:
        score += 3.0
    elif risk_reward >= 1.5:
        score += 1.0
    else:
        score -= 12.0

    if trend_aligned:
        score += 1.5
    else:
        score -= 4.0

    return round(max(0.0, min(score, 99.0)), 1)


def build_setup(
    ticker: str,
    rule: PatternRule,
    price: float,
    entry: float,
    stop: float,
    target: float,
    reason: str,
    structure: Dict[str, Any],
    df: pd.DataFrame,
    config: EngineConfig,
) -> dict:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else 0.0
    aligned = trend_ok(df, rule.direction)
    valid = risk_reward >= config.min_risk_reward and aligned

    setup = {
        "ticker": ticker,
        "asset_class": "equity",
        "direction": rule.direction,
        "pattern_id": rule.pattern_id,
        "pattern_name": rule.pattern_name,
        "is_valid": bool(valid),
        "confidence_pct": confidence_score(rule.success_rate, risk_reward, aligned),
        "confidence_method": "pattern_rate + risk_reward + trend_filter",
        "current_price": round(price, 4),
        "entry_price": round(entry, 4),
        "stop_loss": round(stop, 4),
        "price_target": round(target, 4),
        "risk_reward_ratio": risk_reward,
        "thesis": reason,
        "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
    }

    if config.debug:
        setup.update(
            {
                "success_rate_reference": rule.success_rate,
                "pattern_family": rule.family,
                "trigger": rule.trigger,
                "target_formula": rule.target_formula,
                "structure": structure,
                "trend_aligned": aligned,
            }
        )

    return setup


def invalid_eval(ticker: str, rule: PatternRule, reason: str) -> dict:
    return {
        "ticker": ticker,
        "pattern_id": rule.pattern_id,
        "pattern_name": rule.pattern_name,
        "direction": rule.direction,
        "is_valid": False,
        "reason": reason,
    }
