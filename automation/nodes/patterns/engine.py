from typing import Any, Dict, List

from automation.models.state import AgentState
from automation.nodes.patterns.detectors import DETECTORS
from automation.nodes.patterns.io import load_pattern_rules, load_universe
from automation.nodes.patterns.logging_utils import get_runtime_logger
from automation.nodes.patterns.models import EngineConfig
from automation.nodes.patterns.normalizer import add_indicators, normalize_ohlcv
from automation.nodes.patterns.pivots import find_pivots
from automation.nodes.patterns.requests import build_historical_requests
from automation.nodes.patterns.scoring import invalid_eval

LOGGER = get_runtime_logger("agentic.pattern_engine")


class PatternEngine:
    """Efficient rule-based OHLCV pattern engine using scipy.signal.find_peaks."""

    PATTERN_PATH = "data/10_trading_patterns.md"
    SCREENING_PATH = "data/agentic_screening.md"

    load_universe = staticmethod(load_universe)
    load_pattern_rules = staticmethod(load_pattern_rules)
    build_historical_requests = staticmethod(build_historical_requests)
    normalize_ohlcv = staticmethod(normalize_ohlcv)

    @classmethod
    def evaluate_state(cls, state: AgentState) -> Dict[str, Any]:
        """Evaluate all tickers in state against real OHLCV data."""
        config = EngineConfig.from_env()
        tickers = state.get("ticker_universe") or cls.load_universe(cls.SCREENING_PATH)
        market_data = state.get("market_data", {})

        if not tickers:
            return {
                "matched_setups": [],
                "pattern_summary": {"tickers": 0, "matches": 0, "mode": config.mode},
                "execution_status": "NO_TICKERS",
            }

        if not isinstance(market_data, dict) or not market_data:
            return {
                "matched_setups": [],
                "pattern_summary": {"tickers": len(tickers), "matches": 0, "mode": config.mode},
                "mcp_requests": cls.build_historical_requests(tickers),
                "execution_status": "AWAITING_LIVE_OHLCV",
            }

        return cls.evaluate_universe(tickers=tickers, market_data=market_data, config=config)

    @classmethod
    def evaluate_universe(
        cls,
        tickers: List[str],
        market_data: Dict[str, Any],
        config: EngineConfig | None = None,
    ) -> Dict[str, Any]:
        """
        Evaluate every ticker.

        Safety rule:
        - In default production mode, a partial universe is not allowed to produce
          matched_setups. If any ticker is missing valid OHLCV, return
          AWAITING_LIVE_OHLCV and request the missing batch.
        """
        config = config or EngineConfig.from_env()
        rules = cls.load_pattern_rules(cls.PATTERN_PATH)

        if not rules:
            return {
                "matched_setups": [],
                "pattern_summary": {"tickers": len(tickers), "matches": 0, "mode": config.mode},
                "execution_status": "PATTERN_RULES_MISSING",
            }

        normalized: Dict[str, Any] = {}
        missing: List[str] = []

        for ticker in tickers:
            snapshot = market_data.get(ticker) or market_data.get(ticker.upper())
            if not isinstance(snapshot, dict):
                missing.append(ticker)
                continue

            df = cls.normalize_ohlcv(snapshot)
            if df is None or len(df) < config.min_candles:
                missing.append(ticker)
                continue

            normalized[ticker] = df

        if missing and config.require_full_universe_ohlcv:
            result: Dict[str, Any] = {
                "matched_setups": [],
                "pattern_summary": {
                    "mode": config.mode,
                    "tickers": len(tickers),
                    "scanned": len(normalized),
                    "matches": 0,
                    "missing_ohlcv": len(missing),
                    "full_universe_required": True,
                },
                "mcp_requests": cls.build_historical_requests(missing),
                "execution_status": "AWAITING_LIVE_OHLCV",
            }

            if config.debug:
                result["missing_ohlcv_tickers"] = missing

            LOGGER.info(
                "Pattern evaluation blocked until full universe OHLCV is available.",
                extra={
                    "event": "FULL_UNIVERSE_OHLCV_REQUIRED",
                    "mode": config.mode,
                    "ticker_count": len(tickers),
                    "ready_count": len(normalized),
                    "missing_ohlcv_count": len(missing),
                },
            )
            return result

        matched: List[dict] = []
        debug_evals: Dict[str, Any] = {}

        for ticker, df in normalized.items():
            valid, evaluations = cls.evaluate_ticker(ticker=ticker, df=df, rules=rules, config=config)

            if valid:
                matched.extend(valid)

            if config.debug:
                debug_evals[ticker] = evaluations

        matched = sorted(matched, key=lambda x: x.get("confidence_pct", 0), reverse=True)[: config.max_setups]

        result = {
            "matched_setups": matched,
            "pattern_summary": {
                "mode": config.mode,
                "tickers": len(tickers),
                "scanned": len(normalized),
                "matches": len(matched),
                "missing_ohlcv": len(missing),
                "full_universe_required": config.require_full_universe_ohlcv,
            },
            "execution_status": "PATTERN_MATCH" if matched else "NO_PATTERN_MATCH",
        }

        if missing:
            result["mcp_requests"] = cls.build_historical_requests(missing)

        if config.debug:
            result["pattern_evaluations"] = debug_evals
            result["missing_ohlcv_tickers"] = missing

        LOGGER.info(
            "Universe pattern evaluation complete.",
            extra={
                "event": "UNIVERSE_PATTERN_EVALUATED",
                "mode": config.mode,
                "ticker_count": len(tickers),
                "scanned_count": len(normalized),
                "matched_count": len(matched),
                "missing_ohlcv_count": len(missing),
            },
        )
        return result

    @classmethod
    def evaluate_ticker(
        cls,
        ticker: str,
        df,
        rules: Dict[str, Any],
        config: EngineConfig,
    ) -> tuple[List[dict], List[dict]]:
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
                LOGGER.exception(
                    "Pattern detector failed.",
                    extra={"event": "PATTERN_DETECTOR_FAILED", "ticker": ticker, "pattern_id": pattern_id},
                )
                if config.debug:
                    diagnostics.append(invalid_eval(ticker, rule, f"Detector error: {exc}"))

        return valid, diagnostics
