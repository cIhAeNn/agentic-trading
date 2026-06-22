import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


CLAUDE_CONFIG_PATH = "config/claude_desktop_config.json"


@lru_cache(maxsize=1)
def _load_claude_config() -> Dict[str, Any]:
    """Read Claude Desktop config so local project Python can use project env values."""
    path = Path(CLAUDE_CONFIG_PATH)

    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def runtime_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Runtime env lookup order:
    1. Real OS environment.
    2. Top-level `env` in config/claude_desktop_config.json.
    3. Backward-compatible `mcpServers.env`.
    4. Per-server `mcpServers.<server>.env`.
    5. Default.
    """
    os_value = os.getenv(name)
    if os_value not in (None, ""):
        return os_value

    cfg = _load_claude_config()

    top_env = cfg.get("env")
    if isinstance(top_env, dict):
        value = top_env.get(name)
        if value not in (None, ""):
            return str(value)

    servers = cfg.get("mcpServers")
    if isinstance(servers, dict):
        misplaced_env = servers.get("env")
        if isinstance(misplaced_env, dict):
            value = misplaced_env.get(name)
            if value not in (None, ""):
                return str(value)

        for server_config in servers.values():
            if not isinstance(server_config, dict):
                continue

            server_env = server_config.get("env")
            if isinstance(server_env, dict):
                value = server_env.get(name)
                if value not in (None, ""):
                    return str(value)

    return default


def normalize_mode(value: Optional[str] = None) -> str:
    """Normalize runtime mode from env/config."""
    raw = (value or runtime_env("MODE", "PROD") or "PROD").strip().upper()

    if raw in {"PROD", "PRODUCTION"}:
        return "PROD"

    if raw == "DEBUG":
        return "DEBUG"

    return "PROD"


def runtime_bool(name: str, default: bool) -> bool:
    value = runtime_env(name)

    if value is None:
        return default

    return str(value).strip().upper() not in {"0", "FALSE", "NO", "OFF"}


@dataclass(frozen=True)
class EngineConfig:
    """Runtime knobs for precision, efficiency, and token/state-size control."""
    mode: str = "PROD"
    min_candles: int = 60
    structure_lookback: int = 90
    min_risk_reward: float = 1.50
    max_setups: int = 3
    use_global_volume_override: bool = True
    require_full_universe_ohlcv: bool = True

    @property
    def debug(self) -> bool:
        return self.mode == "DEBUG"

    @classmethod
    def from_env(cls) -> "EngineConfig":
        mode = normalize_mode()

        if mode == "DEBUG":
            return cls(
                mode="DEBUG",
                min_candles=int(runtime_env("PATTERN_MIN_CANDLES", "50") or "50"),
                structure_lookback=int(runtime_env("PATTERN_LOOKBACK", "120") or "120"),
                min_risk_reward=float(runtime_env("PATTERN_MIN_RR", "1.35") or "1.35"),
                max_setups=int(runtime_env("PATTERN_MAX_SETUPS", "5") or "5"),
                use_global_volume_override=runtime_bool("PATTERN_GLOBAL_VOLUME_OVERRIDE", True),
                require_full_universe_ohlcv=runtime_bool("PATTERN_REQUIRE_FULL_UNIVERSE_OHLCV", True),
            )

        return cls(
            mode="PROD",
            min_candles=int(runtime_env("PATTERN_MIN_CANDLES", "60") or "60"),
            structure_lookback=int(runtime_env("PATTERN_LOOKBACK", "90") or "90"),
            min_risk_reward=float(runtime_env("PATTERN_MIN_RR", "1.50") or "1.50"),
            max_setups=int(runtime_env("PATTERN_MAX_SETUPS", "3") or "3"),
            use_global_volume_override=runtime_bool("PATTERN_GLOBAL_VOLUME_OVERRIDE", True),
            require_full_universe_ohlcv=runtime_bool("PATTERN_REQUIRE_FULL_UNIVERSE_OHLCV", True),
        )


@dataclass(frozen=True)
class PatternRule:
    pattern_id: str
    pattern_name: str
    success_rate: float
    trigger: str
    target_formula: str
    direction: str
    family: str


@dataclass
class PivotSet:
    high_idx: np.ndarray
    low_idx: np.ndarray
    high_values: np.ndarray
    low_values: np.ndarray


PatternEval = Dict[str, Any]
PatternEvalList = List[PatternEval]
