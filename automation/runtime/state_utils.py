from typing import Any, Dict


def merge_state(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow state merge helper for scheduler-side state snapshots."""
    merged = dict(base or {})
    merged.update(update or {})
    return merged


def primary_setup(state: Dict[str, Any]) -> Dict[str, Any]:
    setups = state.get("matched_setups", [])
    if isinstance(setups, list) and setups and isinstance(setups[0], dict):
        return dict(setups[0])
    return {}


def approved_ticker(state: Dict[str, Any]) -> str | None:
    if state.get("ticker"):
        return str(state["ticker"])

    setup = primary_setup(state)
    ticker = setup.get("ticker")
    return str(ticker) if ticker else None


def approved_pattern_id(state: Dict[str, Any]) -> str | None:
    setup = primary_setup(state)
    pattern_id = setup.get("pattern_id") or state.get("pattern_id")
    return str(pattern_id) if pattern_id else None
