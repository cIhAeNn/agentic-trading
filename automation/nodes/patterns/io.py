import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from automation.nodes.patterns.logging_utils import get_runtime_logger
from automation.nodes.patterns.models import PatternRule

LOGGER = get_runtime_logger("agentic.pattern_engine.io")


@lru_cache(maxsize=8)
def load_universe(path: str = "data/agentic_screening.md") -> List[str]:
    """Load tickers from Markdown table or ticker list. Cached per process."""
    if not os.path.exists(path):
        LOGGER.error("Screening universe file missing.", extra={"event": "SCREENING_FILE_MISSING", "path": path})
        return []

    text = Path(path).read_text(encoding="utf-8")
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

    unique = list(dict.fromkeys(tickers))
    LOGGER.info("Universe loaded.", extra={"event": "UNIVERSE_LOADED", "ticker_count": len(unique)})
    return unique


@lru_cache(maxsize=8)
def load_pattern_rules(path: str = "data/10_trading_patterns.md") -> Dict[str, PatternRule]:
    """Parse pattern rules once per process."""
    if not os.path.exists(path):
        LOGGER.error("Pattern matrix missing.", extra={"event": "PATTERN_MATRIX_MISSING", "path": path})
        return {}

    text = Path(path).read_text(encoding="utf-8")
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

        pattern_id = f"Pattern #{num}"
        rules[pattern_id] = PatternRule(
            pattern_id=pattern_id,
            pattern_name=name,
            success_rate=float(success.group(1)) if success else 0.0,
            trigger=trigger.group(1).strip() if trigger else "",
            target_formula=target.group(1).strip() if target else "",
            direction="BUY" if "Bullish" in family else "SELL",
            family=family,
        )

    LOGGER.info("Pattern rules loaded.", extra={"event": "PATTERN_RULES_LOADED", "rule_count": len(rules)})
    return rules
