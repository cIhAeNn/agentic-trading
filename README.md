# Agentic Trading Pattern Scanner

A local Claude Desktop + Python workflow for scanning equities against rule-based technical chart patterns, generating Markdown/Discord reports, and optionally running a human-in-the-loop approval flow before any broker handoff.

> Current recommended mode: **pattern checking / scan-only first**.  
> Broker execution should remain disabled until data fetching, Discord approval, fresh revalidation, and confirmation logging are stable.

## What this project does

This project scans a fixed ticker universe from Markdown data files, fetches real OHLCV candles through an external market-data/MCP layer, evaluates the universe against 10 chart-pattern rules, and produces structured state for reporting or review.

The core safety principle is simple:

```text
No real OHLCV → no pattern result
No full-universe scan → no staging
No explicit human approval → no broker handoff
No fresh post-approval recheck → no broker handoff
No real broker confirmation → no execution confirmation
```

## Current architecture

```text
agentic-trading/
├── automation/
│   ├── cowork_scheduler.py
│   ├── graph_orchestrator.py
│   ├── pipeline.py
│   ├── models/
│   │   └── state.py
│   ├── nodes/
│   │   ├── pattern_engine.py
│   │   ├── position_sizing.py
│   │   ├── validators.py
│   │   └── patterns/
│   │       ├── detectors.py
│   │       ├── engine.py
│   │       ├── io.py
│   │       ├── logging_utils.py
│   │       ├── models.py
│   │       ├── normalizer.py
│   │       ├── pivots.py
│   │       ├── requests.py
│   │       └── scoring.py
│   ├── routers/
│   │   └── edge_routers.py
│   ├── runtime/
│   │   ├── discord_polling.py
│   │   ├── graph_runtime.py
│   │   ├── mcp_dispatcher.py
│   │   └── state_utils.py
│   └── services/
│       ├── discord.py
│       └── robinhood.py
├── config/
│   ├── claude_desktop_config.json
│   └── discord_config.yaml
├── data/
│   ├── 10_trading_patterns.md
│   └── agentic_screening.md
├── instructions/
│   └── logs_infrastructure.md
└── logs/
    ├── activity_ledger.json
    ├── error_trace.json
    ├── runtime.log
    └── runtime_error.log
```

## Graph flow

The canonical graph is `automation/graph_orchestrator.py`.

```text
pre_flight
→ ingest
→ request_market_data
→ telemetry_and_patterns
→ position_sizing
→ capital_gate
→ discord_submit
→ revalidate
→ broker_route OR cry_alert OR END
```

Expected pause points:

```text
AWAITING_LIVE_OHLCV
AWAITING_LIVE_MCP_BALANCES
STAGED_AWAITING_APPROVAL
POST_APPROVAL_PATTERN_RECHECK_REQUIRED
ORDER_READY_FOR_MCP_DISPATCH
```

These are intentional safe stops, not errors.

## Recommended development phases

### Phase 1 — scan-only pattern reports

Start here.

```text
load universe
→ fetch OHLCV
→ run PatternEngine
→ generate Markdown/Discord report
→ END
```

In this phase, do not use broker execution. The goal is to verify that pattern detection and reports are correct.

### Phase 2 — human approval workflow

Add Discord approval only after scan-only reports are stable.

Supported text commands:

```text
Approve shares 50
Approve amount 500
Reject
Refresh
```

After approval, the system still requires a fresh OHLCV recheck before broker handoff.

### Phase 3 — broker handoff

Only enable broker handoff after approval, sizing, fresh revalidation, logging, and Discord confirmation are stable.

The broker service should prepare an MCP request only. It must not fake fills or mark orders executed without a real broker confirmation.

## Pattern engine

The pattern engine is rule-based and uses real OHLCV candles.

Inputs:

```text
data/agentic_screening.md
data/10_trading_patterns.md
state["market_data"]
```

Important behaviors:

```text
Full universe OHLCV required by default
Cached Markdown parsing
ATR-adaptive pivot detection
Volume confirmation
Trend alignment filter
Risk/reward filter
Compact PROD output
Expanded DEBUG diagnostics
```

Runtime mode is read from environment/config:

```json
{
  "env": {
    "MODE": "PRODUCTION"
  }
}
```

Supported modes:

```text
PRODUCTION / PROD
DEBUG
```

## Cowork scheduler

`automation/cowork_scheduler.py` is the runtime supervisor around the graph.

It handles:

```text
Discord send + polling
MCP request dispatch loop
same-thread LangGraph resume
fresh OHLCV recheck after approval
broker execution request dispatch
execution confirmation after broker confirmation
```

Run:

```bash
python -m automation.cowork_scheduler --thread-id agentic-trading-20260622
```

## Discord

The current implementation supports REST send + polling through a Discord bot token.

Required config/env:

```json
{
  "env": {
    "DISCORD_TOKEN": "YOUR_BOT_TOKEN",
    "TARGET_CHANNEL_ID": "YOUR_CHANNEL_ID",
    "AUTHORIZED_SNOWFLAKE_ID": "YOUR_DISCORD_USER_ID"
  }
}
```

Recommended future improvement:

```text
Replace REST polling with Discord Gateway listener.
Replace free-text approval with slash commands/buttons.
```

For now, REST polling is acceptable for a low-frequency local prototype.

## MCP dispatch

`automation/runtime/mcp_dispatcher.py` dispatches graph MCP requests.

Dispatch order:

```text
1. Direct Alpha Vantage OHLCV adapter if ALPHA_VANTAGE_API_KEY exists
2. Subprocess bridge if MCP_DISPATCH_COMMAND exists
3. Queue request to logs/mcp_request_queue.jsonl
```

Example bridge config:

```json
{
  "env": {
    "MCP_DISPATCH_COMMAND": "python automation/runtime/your_mcp_bridge.py"
  }
}
```

The bridge receives JSON on stdin:

```json
{
  "request": {},
  "state": {}
}
```

It must return JSON on stdout.

OHLCV response shape:

```json
{
  "market_data": {
    "AMD": {
      "candles": []
    }
  }
}
```

Account response shape:

```json
{
  "account_telemetry": {
    "buying_power": 5000,
    "cash_available": 5000,
    "net_liquidity": 25000,
    "positions": []
  }
}
```

Broker confirmation shape:

```json
{
  "broker_confirmation": {
    "status": "filled",
    "transaction_id": "abc123",
    "executed_at": "2026-06-22T10:00:00-04:00"
  }
}
```

If no adapter or bridge is configured, the scheduler queues requests and returns:

```text
MCP_DISPATCH_REQUIRED
```

It does not fabricate missing data.

## Safety rules

This project is designed to avoid accidental autonomous execution.

Required before broker handoff:

```text
real OHLCV
full-universe pattern scan
real account telemetry
position sizing
Discord approval
explicit size
fresh post-approval revalidation
revalidation_passed=True
broker request dispatch
real broker confirmation
```

Blocked cases:

```text
missing OHLCV
partial universe data
missing account telemetry
missing size
approval timeout
operator reject
pattern invalid after approval
missing broker confirmation
```

## Logs

Runtime logs:

```text
logs/runtime.log
logs/runtime_error.log
```

Audit logs:

```text
logs/activity_ledger.json
logs/error_trace.json
```

Queued MCP requests:

```text
logs/mcp_request_queue.jsonl
```

Do not commit logs with private runtime data.

## Environment/config

Use top-level `env` in `config/claude_desktop_config.json` for local Python runtime settings:

```json
{
  "env": {
    "MODE": "PRODUCTION",
    "MARKET_OVERRIDE": "FALSE",
    "DISCORD_TOKEN": "YOUR_BOT_TOKEN",
    "TARGET_CHANNEL_ID": "YOUR_CHANNEL_ID",
    "AUTHORIZED_SNOWFLAKE_ID": "YOUR_USER_ID",
    "ALPHA_VANTAGE_API_KEY": "YOUR_KEY",
    "MAX_POSITION_PCT": "0.05",
    "MAX_TRADE_RISK_PCT": "0.005",
    "MIN_TRADE_NOTIONAL": "25",
    "CASH_BUFFER_PCT": "0.02"
  }
}
```

Do not commit real tokens, account identifiers, or local Claude Desktop config.

## Install

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install requirements:

```bash
pip install -r requirements.txt
```

## Validate

Compile-check Python files:

```bash
python -m compileall automation
```

Run the cowork scheduler:

```bash
python -m automation.cowork_scheduler --thread-id agentic-trading-test
```

## Important disclaimer

This project is for local automation, research, and pattern-screening workflow development. It is not financial advice. Do not enable broker execution until you have independently verified data quality, broker routing, risk controls, logging, and human approval behavior.
