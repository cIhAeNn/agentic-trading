# System Task Setup & Scheduling Protocol: LangGraph Integration

## 1. Runtime Scope

### 1.1 Purpose

This protocol defines deterministic bootstrap checks, file dependencies, scheduling gates, and state-machine initialization rules for the `agentic-trading` workspace.

The runtime is bound to a Python LangGraph state machine. Claude Desktop Scheduled Tasks must initialize the workspace, verify MCP/tool connectivity, validate local files, and execute only through the approved graph pipeline.

### 1.2 Runtime Authority

| Domain             | Runtime Authority                     |
| ------------------ | ------------------------------------- |
| Graph execution    | `automation/pipeline.py`              |
| Graph topology     | `automation/graph_orchestrator.py`    |
| State schema       | `automation/models/state.py`          |
| Validation nodes   | `automation/nodes/validators.py`      |
| Edge routing       | `automation/routers/edge_routers.py`  |
| Discord runtime    | `automation/services/discord.py`      |
| Discord config     | `config/discord_config.yaml`          |
| Robinhood runtime  | `automation/services/robinhood.py`    |
| Logging protocol   | `instructions/logs_infrastructure.md` |
| Screening universe | `data/company_watchlist.md`           |
| Pattern library    | `data/trading_pattern_watchlist.md`   |

## 2. Project-Root File Map

### 2.1 Required Runtime Files

| Domain              | File Path                                 | Required State | Operational Role                                                                                                                      |
| ------------------- | ----------------------------------------- | -------------: | ------------------------------------------------------------------------------------------------------------------------------------- |
| MCP config          | `config/claude_desktop_config.json`       |          `R--` | Defines Claude Desktop MCP bindings and environment variables.                                                                        |
| MCP inventory       | `config/mcp_api_inventory.md`             |          `R--` | Documents available MCP tools, endpoint boundaries, quotas, and connector constraints.                                                |
| Discord config      | `config/discord_config.yaml`              |          `R--` | Runtime source of truth for Discord templates, approval regex, timeout, buttons/forms, fallback commands, and Discord log event keys. |
| Routing constraints | `context/routing_constraints.md`          |          `R--` | Primary instruction authority for identity, account routing constraints, and state transitions.                                       |
| Screening ops       | `context/screening_and_watchlist_ops.md`  |          `R--` | Defines screening universe handling, data-frame expectations, and watchlist rules.                                                    |
| Pattern library     | `data/trading_pattern_watchlist.md`       |          `R--` | Defines structural chart-pattern confirmation boundaries.                                                                             |
| Screening universe  | `data/company_watchlist.md`               |          `R--` | Canonical ticker universe for scanner ingestion.                                                                                      |
| Pipeline entry      | `automation/pipeline.py`                  |          `R--` | Scheduled task entry point and graph invocation layer.                                                                                |
| Graph orchestrator  | `automation/graph_orchestrator.py`        |          `R--` | Compiles LangGraph nodes, edges, checkpoints, and interrupts.                                                                         |
| State model         | `automation/models/state.py`              |          `R--` | Defines shared `AgentState` schema.                                                                                                   |
| Validators          | `automation/nodes/validators.py`          |          `R--` | Executes market-window, screening, pattern, risk, and revalidation gates.                                                             |
| Edge routers        | `automation/routers/edge_routers.py`      |          `R--` | Routes graph transitions across scan, stage, approve, execute, invalidate, and halt states.                                           |
| Discord service     | `automation/services/discord.py`          |          `R--` | Renders Discord messages, parses approval, handles timeout, sends `CRY` alerts, and logs Discord branches.                            |
| Robinhood service   | `automation/services/robinhood.py`        |          `R--` | Handles account telemetry, buying power, holdings, cost basis, and approved execution routing.                                        |
| Logging protocol    | `instructions/logs_infrastructure.md`     |          `R--` | Governs log schema, file routing, status flags, and diagnostic-card behavior.                                                         |
| Task setup          | `instructions/task_setup_instructions.md` |          `R--` | Defines bootstrap checks and scheduled task initialization gates.                                                                     |
| Activity ledger     | `logs/activity_ledger.json`               |          `RW-` | Stores successful runtime events.                                                                                                     |
| Error trace         | `logs/error_trace.json`                   |          `RW-` | Stores failed runtime events, exceptions, throttles, and diagnostic traces.                                                           |

### 2.2 Ignored Files

| File Path                        | Rule                                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `logs/.__probe`                  | Ignore during normal runtime.                                                           |
| `logs/.__wtest_5.json`           | Ignore during normal runtime.                                                           |
| `logs/graph_topology.png`        | Optional visual reference only. Do not treat as runtime authority.                      |
| `data/history/2026/20260621.zip` | Historical archive. Do not load during live scheduled runs unless explicitly requested. |
| `__pycache__/`                   | Python cache. Ignore. Never treat as source code.                                       |

## 3. Bootstrap Gates

The `pre_flight_check` node must clear every gate before graph execution. Any failure freezes processing and writes a failed event to `logs/error_trace.json`.

### 3.1 Gate 1: Repository Path Validation

| Check                | Required Condition                                                            |
| -------------------- | ----------------------------------------------------------------------------- |
| Working directory    | Resolves to active `agentic-trading` repository root                          |
| Required directories | `automation/`, `config/`, `context/`, `data/`, `instructions/`, `logs/` exist |
| Python packages      | Required `__init__.py` files exist where needed                               |
| Cache folders        | `__pycache__/` ignored                                                        |

### 3.2 Gate 2: Runtime File Validation

Verify these files exist and are readable:

```text
config/claude_desktop_config.json
config/mcp_api_inventory.md
config/discord_config.yaml
context/routing_constraints.md
context/screening_and_watchlist_ops.md
data/trading_pattern_watchlist.md
data/company_watchlist.md
automation/pipeline.py
automation/graph_orchestrator.py
automation/models/state.py
automation/nodes/validators.py
automation/routers/edge_routers.py
automation/services/discord.py
automation/services/robinhood.py
instructions/logs_infrastructure.md
instructions/task_setup_instructions.md
```

Do not check for:

```text
instructions/discord_messaging_protocol.md
```

### 3.3 Gate 3: Discord Runtime Validation

| Check           | Required Condition                                           |
| --------------- | ------------------------------------------------------------ |
| Service file    | `automation/services/discord.py` exists and imports cleanly  |
| Config file     | `config/discord_config.yaml` exists and parses               |
| Channel env     | `TARGET_CHANNEL_ID` resolves from config or environment      |
| Approval parser | Accepts `Approve shares 1` and `Approve amount 1`            |
| Reject parser   | Accepts `Reject`                                             |
| Refresh parser  | Accepts `Refresh`                                            |
| Removed docs    | `instructions/discord_messaging_protocol.md` is not required |

### 3.4 Gate 4: MCP Tool Inventory Audit

Read `config/mcp_api_inventory.md` and verify MCP availability for the active graph.

| MCP           | Required Capability                                                           |
| ------------- | ----------------------------------------------------------------------------- |
| Robinhood     | Account telemetry, buying power, holdings, cost basis, approved order routing |
| Alpha Vantage | Market data ingestion within quota                                            |
| TipRanks      | Targeted high-conviction analyst telemetry after pattern validation           |
| Windsor.ai    | Cached structural data streams if configured                                  |
| Discord       | `discord_send` and `discord_read_messages`                                    |

### 3.5 Gate 5: Screening Universe Resolution

| Check           | Required Condition             |
| --------------- | ------------------------------ |
| Source file     | `data/company_watchlist.md`    |
| Role            | Canonical ticker universe      |
| Required output | Non-empty valid ticker list    |
| Failure action  | Log file fault and abort graph |

Do not query Robinhood watchlists for the scanner universe.

### 3.6 Gate 6: Pattern Library Resolution

| Check           | Required Condition                             |
| --------------- | ---------------------------------------------- |
| Source file     | `data/trading_pattern_watchlist.md`            |
| Role            | Canonical pattern validation library           |
| Required output | Readable pattern rules and buy/sell boundaries |
| Failure action  | Log file fault and abort graph                 |

### 3.7 Gate 7: Ledger Diagnostics

| File                        | Required Operation                             |
| --------------------------- | ---------------------------------------------- |
| `logs/activity_ledger.json` | Read final `3` entries and verify write access |
| `logs/error_trace.json`     | Read final `3` entries and verify write access |

Ignore:

```text
logs/.__probe
logs/.__wtest_5.json
logs/graph_topology.png
```

## 4. Scheduled Task Mode

### 4.1 Trigger Driver

Claude Desktop Scheduled Tasks trigger the graph at the configured cadence.

The scheduler may run outside market hours. Out-of-window runs must terminate cleanly without market-data polling.

### 4.2 Market Window

| Variable             | Value                                             |
| -------------------- | ------------------------------------------------- |
| Time zone            | `America/New_York`                                |
| Start                | `09:30:00 ET`                                     |
| End                  | `17:30:00 ET`                                     |
| Valid days           | Exchange-open business days                       |
| Out-of-window action | Exit cleanly without external market-data polling |

### 4.3 Time Gate Formula

```text
Current ET time ∈ [09:30:00, 17:30:00]
```

If false:

| Action                 | Required                                 |
| ---------------------- | ---------------------------------------- |
| Market-data API calls  | No                                       |
| Discord trade messages | No                                       |
| Order staging          | No                                       |
| Brokerage routing      | No                                       |
| Log write              | No, unless an actual fault occurs        |
| State                  | `LOW_POWER_HIBERNATE` or clean `__end__` |

## 5. LangGraph Vertex Inventory

| Vertex                       | Domain                    | Objective                                                                                                |
| ---------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `pre_flight_check`           | Bootstrap / Observability | Validate files, logs, MCP inventory, Discord config, and environment state.                              |
| `load_screening_universe`    | Ingestion                 | Read tickers from `data/company_watchlist.md`.                                                           |
| `market_window_gate`         | Scheduling                | Validate current ET time and exchange-open state.                                                        |
| `extract_telemetry`          | Market Data               | Retrieve current price and account telemetry through MCP services.                                       |
| `pattern_validation`         | Strategy                  | Match telemetry against `data/trading_pattern_watchlist.md`.                                             |
| `risk_validation`            | Risk                      | Check cash, buying power, exposure, position size, and account constraints.                              |
| `discord_submit`             | HITL Gate                 | Render Discord trade proposal through `automation/services/discord.py` and `config/discord_config.yaml`. |
| `approval_poll`              | HITL Gate                 | Read Discord replies and parse operator action.                                                          |
| `post_approval_revalidation` | Execution Guard           | Recheck price, pattern, risk, and timeout after approval.                                                |
| `execute_order`              | Brokerage                 | Route approved and revalidated order through Robinhood service.                                          |
| `invalidate_order`           | Safety                    | Send `CRY`, cancel staged order, and block execution.                                                    |
| `global_exception_handler`   | Safety                    | Log faults, freeze processing, and clear staged order state.                                             |

## 6. End-to-End Lifecycle

The graph must execute the lifecycle in order.

| Step | Operation                  | Required Behavior                                                                           |
| ---: | -------------------------- | ------------------------------------------------------------------------------------------- |
|    1 | Observability audit        | Read final `3` entries from both runtime logs.                                              |
|    2 | Runtime file validation    | Verify required project files. Do not require `instructions/discord_messaging_protocol.md`. |
|    3 | Discord config validation  | Load `automation/services/discord.py` and `config/discord_config.yaml`.                     |
|    4 | Temporal gate              | Validate current ET time against scheduled market window.                                   |
|    5 | Screening load             | Read tickers from `data/company_watchlist.md`.                                              |
|    6 | Telemetry extraction       | Call approved MCP tools for market/account telemetry.                                       |
|    7 | Pattern validation         | Match against `data/trading_pattern_watchlist.md`.                                          |
|    8 | Risk validation            | Check cash, buying power, exposure, and account constraints.                                |
|    9 | Discord dispatch           | Render trade message using `config/discord_config.yaml`.                                    |
|   10 | Ledger stage               | Write `ORDER_STAGED` to `logs/activity_ledger.json`.                                        |
|   11 | Graph breakpoint           | Freeze at Discord approval boundary.                                                        |
|   12 | Approval polling           | Poll Discord and parse text commands.                                                       |
|   13 | Post-approval revalidation | Recheck pattern, price, risk, and timeout.                                                  |
|   14 | Execution or invalidation  | Execute only if valid; otherwise send `CRY` and block.                                      |
|   15 | Terminal logging           | Write `ORDER_EXECUTED`, `ORDER_INVALIDATED`, or `API_ERROR`.                                |

## 7. Discord Approval Runtime

### 7.1 Runtime Source

Discord behavior is governed only by:

```text
automation/services/discord.py
config/discord_config.yaml
```

### 7.2 Valid Approval Commands

```text
Approve shares 50
Approve amount 500
Go shares 25
Yes amount 1000
Reject
Refresh
```

Legacy support is allowed:

```text
Approve 50
```

Interpret as:

```text
Approve shares 50
```

### 7.3 Hard Rules

| Rule                   | Requirement                                                                |
| ---------------------- | -------------------------------------------------------------------------- |
| Approval required      | Do not execute without Discord approval.                                   |
| Explicit size required | Reject approval without shares or dollar amount.                           |
| Revalidation required  | Do not execute immediately after approval.                                 |
| CRY required           | If post-approval pattern breaks, send `CRY` and block execution.           |
| Config authority       | Message templates and parser rules come from `config/discord_config.yaml`. |
| Service authority      | Runtime send/parse/log methods come from `automation/services/discord.py`. |

## 8. Logging Requirements

### 8.1 Log Authority

All log behavior must follow:

```text
instructions/logs_infrastructure.md
```

### 8.2 Required Logs

| File                        | Purpose                                                      |
| --------------------------- | ------------------------------------------------------------ |
| `logs/activity_ledger.json` | Successful operational events                                |
| `logs/error_trace.json`     | Failures, invalidations, timeouts, throttles, and exceptions |

### 8.3 Event Routing

| Event               | Destination                 |
| ------------------- | --------------------------- |
| `SCREEN_RUN`        | `logs/activity_ledger.json` |
| `PATTERN_MATCH`     | `logs/activity_ledger.json` |
| `ORDER_STAGED`      | `logs/activity_ledger.json` |
| `ORDER_APPROVED`    | `logs/activity_ledger.json` |
| `ORDER_EXECUTED`    | `logs/activity_ledger.json` |
| `ORDER_INVALIDATED` | `logs/error_trace.json`     |
| `API_ERROR`         | `logs/error_trace.json`     |

## 9. Global Exception Handling

### 9.1 Fault Triggers

| Fault                                | Required Action                                       |
| ------------------------------------ | ----------------------------------------------------- |
| Missing required file                | Freeze processing and log `API_ERROR`.                |
| Missing `config/discord_config.yaml` | Freeze processing and log `API_ERROR`.                |
| Missing `TARGET_CHANNEL_ID`          | Freeze processing and log `API_ERROR`.                |
| MCP timeout                          | Freeze processing and log `API_ERROR`.                |
| Rate-limit throttle                  | Freeze processing and log `API_ERROR`.                |
| Credential failure                   | Freeze processing and log `API_ERROR`.                |
| Log write failure                    | Freeze processing and surface diagnostic state.       |
| Pattern invalidation after approval  | Send `CRY`, block execution, log `ORDER_INVALIDATED`. |

### 9.2 Fault Sequence

| Step | Action                                                      |
| ---: | ----------------------------------------------------------- |
|    1 | Stop active graph branch.                                   |
|    2 | Clear staged order state.                                   |
|    3 | Write diagnostic payload to `logs/error_trace.json`.        |
|    4 | Send critical Discord message if Discord remains available. |
|    5 | Return terminal fault state.                                |

## 10. Scheduler-Safe Startup Prompt

Use this prompt when Claude Desktop starts or the scheduler initializes outside market hours.

```text
Initialize `agentic-trading`.

Load required runtime files.
Use Discord runtime from `automation/services/discord.py` and `config/discord_config.yaml`.
Do not load or require `instructions/discord_messaging_protocol.md`.

Check logs.
Find `TARGET_CHANNEL_ID`.
Test MCP connections.
Confirm protocol parity.

Scheduler is configured.
Do not start the market loop manually.

If current time is outside `09:30:00 ET – 17:30:00 ET`, set state to:

LOW_POWER_HIBERNATE: Scheduler Armed

Do not scan tickers.
Do not call market-data APIs.
Do not stage orders.
Do not send Discord trade messages.
Do not poll Discord.
Do not route trades.

Return only SYSTEM READINESS BLOTTER.
```

## 11. Market Loop Start Prompt

Use this only when the scheduler triggers inside the valid market window.

```text
start market loop
```

Required behavior:

| Rule             | Requirement                                                       |
| ---------------- | ----------------------------------------------------------------- |
| Screening source | `data/company_watchlist.md`                                       |
| Pattern source   | `data/trading_pattern_watchlist.md`                               |
| Discord source   | `automation/services/discord.py` and `config/discord_config.yaml` |
| Logging source   | `instructions/logs_infrastructure.md`                             |
| Removed file     | Do not use `instructions/discord_messaging_protocol.md`           |
