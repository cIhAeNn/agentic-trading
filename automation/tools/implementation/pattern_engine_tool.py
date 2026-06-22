from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from automation.models.pattern_models import EngineConfig, PatternRule
from automation.domain.patterns.normalizer import add_indicators, normalize_ohlcv
from automation.domain.patterns.pivots import find_pivots
from automation.domain.patterns.detectors import DETECTORS
from automation.domain.patterns.scoring import invalid_eval
from automation.tools.implementation.logger_tool import LoggerTool
from automation.tools.interface.logger_tool_interface import ILoggerTool
from automation.tools.interface.pattern_tool_interface import IPatternEngineTool


class PatternEngineTool(IPatternEngineTool):
    """
    Concrete implementation of IPatternEngineTool.
    Consolidates Engine execution, IO rules loading, and Request generation.
    """

    def __init__(
        self,
        logger: Optional[ILoggerTool] = None,
        pattern_path: str = "data/trading_pattern_watchlist.md",
        screening_path: str = "data/company_watchlist.md",
    ):
        self.logger = logger or LoggerTool()
        self.log_context = "PatternEngineTool"
        self.pattern_path = pattern_path
        self.screening_path = screening_path
        
        # Internal caching to prevent excessive disk reads during the same lifecycle
        self._universe_cache: List[str] = []
        self._rules_cache: Dict[str, PatternRule] = {}

    # --- IO FOLDED METHODS (Previously in io.py) ---

    def _load_universe(self) -> List[str]:
        """Load tickers from Markdown table or ticker list."""
        if self._universe_cache:
            return self._universe_cache

        if not os.path.exists(self.screening_path):
            self.logger.error(f"Screening universe file missing at {self.screening_path}", context=self.log_context)
            return []

        text = Path(self.screening_path).read_text(encoding="utf-8")
        tickers: List[str] = []

        # Preferred format: markdown table row: | 1 | NVDA | ...
        tickers.extend(re.findall(r"\|\s*\d+\s*\|\s*([A-Z][A-Z0-9.\-]{0,6})\s*\|", text))

        if not tickers:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("|"):
                    continue
                line = line.lstrip("-*•").strip()
                for token in re.split(r"[\s,]+", line):
                    token = token.strip().upper()
                    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,6}", token):
                        tickers.append(token)

        self._universe_cache = list(dict.fromkeys(tickers))  # deduplicate
        self.logger.info(f"Loaded {len(self._universe_cache)} tickers from universe.", context=self.log_context)
        return self._universe_cache

    def _load_pattern_rules(self) -> Dict[str, PatternRule]:
        """Parse pattern rules from markdown matrix."""
        if self._rules_cache:
            return self._rules_cache

        if not os.path.exists(self.pattern_path):
            self.logger.error(f"Pattern matrix missing at {self.pattern_path}", context=self.log_context)
            return {}

        text = Path(self.pattern_path).read_text(encoding="utf-8")
        blocks = re.split(r"(?=^##\s+\d+\.)", text, flags=re.MULTILINE)
        rules: Dict[str, PatternRule] = {}

        for block in blocks:
            header = re.search(r"^##\s+(\d+)\.\s+(.+?)\s+\((.+?)\)", block, flags=re.MULTILINE)
            if not header:
                continue

            num = header.group(1).strip()
            name = header.group(2).strip()
            family = header.group(3).strip()

            success = re.search(r"Success_Rate:\s*([0-9.]+)", block)
            trigger = re.search(r"Trigger:\s*(.+)", block)
            target = re.search(r"Target:\s*(.+)", block)
            direction = re.search(r"Direction:\s*(BUY|SELL|LONG|SHORT)", block, re.IGNORECASE)

            pattern_id = f"Pattern #{num}"
            rules[pattern_id] = PatternRule(
                pattern_id=pattern_id,
                pattern_name=name,
                family=family,
                success_rate=float(success.group(1)) if success else 0.0,
                trigger=trigger.group(1).strip() if trigger else "",
                target_formula=target.group(1).strip() if target else "",
                direction=direction.group(1).upper() if direction else "BUY",
            )

        self._rules_cache = rules
        self.logger.info(f"Loaded {len(rules)} pattern rules.", context=self.log_context)
        return rules

    # --- REQUEST FOLDED METHODS (Previously in requests.py) ---

    def build_historical_requests(self, tickers: List[str]) -> List[dict]:
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

    # --- UTILITY EXPOSURE ---

    def normalize_ohlcv(self, snapshot: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Exposes the pure normalizing function through the interface."""
        return normalize_ohlcv(snapshot)

    # --- CORE ENGINE METHODS (Previously in engine.py) ---

    def evaluate_ticker(
        self,
        ticker: str,
        df: pd.DataFrame,
        rules: Dict[str, Any],
        config: EngineConfig,
    ) -> Tuple[List[dict], List[dict]]:
        """Run all detectors for one ticker; return valid setups and optional diagnostics."""
        df = add_indicators(df)
        df_recent = df.tail(config.structure_lookback).reset_index(drop=True)
        pivots = find_pivots(df_recent)

        valid: List[dict] = []
        diagnostics: List[dict] = []

        for pattern_id, detector in DETECTORS.items():
            rule = rules.get(pattern_id)
            if not rule:
                continue

            try:
                result = detector(ticker, df_recent, pivots, rule, config)
                if result and result.get("is_valid"):
                    valid.append(result)
                elif config.debug:
                    diagnostics.append(result if result else invalid_eval(ticker, rule, "Trigger not satisfied."))
            except Exception as exc:
                self.logger.error(
                    f"Pattern detector failed for {ticker} on {pattern_id}", 
                    context=self.log_context, 
                    exc_info=True
                )
                if config.debug:
                    diagnostics.append(invalid_eval(ticker, rule, f"Detector error: {exc}"))

        return valid, diagnostics

    def evaluate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all tickers in state against real OHLCV data."""
        self.logger.info("Starting evaluation of Agent State.", context=self.log_context)
        
        config = EngineConfig.from_env()
        tickers = state.get("ticker_universe") or self._load_universe()
        market_data = state.get("market_data", {})

        if not tickers:
            self.logger.warning("No tickers found to evaluate.", context=self.log_context)
            return {"setups": [], "diagnostics": [], "missing_ohlcv": []}

        rules = self._load_pattern_rules()
        if not rules:
            self.logger.warning("No pattern rules loaded. Aborting evaluation.", context=self.log_context)
            return {"setups": [], "diagnostics": [], "missing_ohlcv": tickers}

        all_setups = []
        all_diagnostics = []
        missing = []

        for ticker in tickers:
            snapshot = market_data.get(ticker)
            df = self.normalize_ohlcv(snapshot) if snapshot else None

            if df is None or len(df) < config.min_candles:
                missing.append(ticker)
                continue

            valid, diag = self.evaluate_ticker(ticker, df, rules, config)
            all_setups.extend(valid)
            all_diagnostics.extend(diag)

        # Sort setups by confidence
        all_setups.sort(key=lambda x: x.get("confidence_pct", 0.0), reverse=True)

        self.logger.info(
            f"Evaluation complete. Found {len(all_setups)} valid setups across {len(tickers)} tickers. {len(missing)} missing data.",
            context=self.log_context
        )

        return {
            "setups": all_setups[: config.max_setups],
            "diagnostics": all_diagnostics,
            "missing_ohlcv": missing,
        }