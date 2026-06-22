from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from automation.models.pattern_models import EngineConfig

class IPatternEngineTool(ABC):
    """
    Interface contract for the Pattern Recognition Engine.
    Handles data normalization, I/O for rules/tickers, and pattern detection execution.
    """

    @abstractmethod
    def evaluate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates all tickers in the given agent state against OHLCV data."""
        pass

    @abstractmethod
    def evaluate_ticker(
        self, ticker: str, df: pd.DataFrame, rules: Dict[str, Any], config: EngineConfig
    ) -> Tuple[List[dict], List[dict]]:
        """Runs all detectors for one specific ticker."""
        pass

    @abstractmethod
    def build_historical_requests(self, tickers: List[str]) -> List[dict]:
        """Builds a batch handoff payload to fetch real OHLCV candles."""
        pass

    @abstractmethod
    def normalize_ohlcv(self, snapshot: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Normalizes common historical candle payloads into an OHLCV DataFrame."""
        pass