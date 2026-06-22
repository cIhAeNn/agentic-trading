Here is the completely updated and structurally optimized **`context/routing_constraints.md`** file.

This update removes the old markdown workflow reference, permanently registers your Python **LangGraph State Machine (`automation/graph_orchestrator.py`)**, and preserves your strict account selection rules (ensuring approved orders only hit the Agentic cash account `••••6614` and bypass the default/retirement accounts entirely).

---

```markdown
# Brokerage Routing Constraints & Graph State Machine

> Operator-confirmed parity note. Read before any Robinhood order routing (End-to-End State Machine / `execute_brokerage_route` node).

## 1. Project-Root File Map (Claude Desktop Scheduled Task Native)

The runtime environment and state transitions are programmatically bound to a Python LangGraph State Machine. The workspace artifact layout is structured as follows:

| Domain                   | File Path                                 | Operational Role                                                                                                                                   |
| :----------------------- | :---------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP Configuration**    | `config/claude_desktop_config.json`       | Defines Robinhood, Alpha Vantage, TipRanks, Windsor.ai, and Discord MCP bindings.                                                                  |
| **MCP Inventory**        | `config/mcp_api_inventory.md`             | Reference inventory for available MCP tools, endpoint boundaries, quotas, and connector constraints.                                               |
| **Graph State Machine**  | `automation/graph_orchestrator.py`        | Compiles Python LangGraph state paths, checkpoints, conditional routers, and breakpoint interrupts.                                                |
| **Pipeline Entry Point** | `automation/pipeline.py`                  | Runtime entry point for scheduled task execution and graph invocation.                                                                             |
| **State Schema**         | `automation/models/state.py`              | Defines the shared agent state object used across graph nodes, routers, and services.                                                              |
| **Validation Nodes**     | `automation/nodes/validators.py`          | Executes validation gates for market window, screening state, pattern eligibility, and post-approval revalidation.                                 |
| **Edge Routers**         | `automation/routers/edge_routers.py`      | Defines conditional graph transitions between scan, validate, approve, execute, invalidate, and halt states.                                       |
| **Discord Service**      | `automation/services/discord.py`          | Runtime Discord controller for message rendering, approval parsing, timeout handling, CRY alerts, and Discord-side execution gates.                |
| **Discord Config**       | `config/discord_config.yaml`              | Runtime source of truth for Discord templates, approval regex, timeout values, button/modal schema, fallback commands, and Discord log event keys. |
| **Robinhood Service**    | `automation/services/robinhood.py`        | Runtime brokerage service for account telemetry, holdings, buying power, cost basis, and approved execution routing.                               |
| **Routing Protocol**     | `context/routing_constraints.md`          | Primary instruction authority for identity, account routing constraints, and state transitions.                                                    |
| **Screening Ops**        | `context/screening_and_watchlist_ops.md`  | Rules for handling the screening universe and market data frames.                                                                                  |
| **Pattern Library**      | `data/10_trading_patterns.md`             | Structural geometric technical chart confirmation boundaries.                                                                                      |
| **Screening Universe**   | `data/agentic_screening.md`               | Canonical target ticker universe list to parse.                                                                                                    |
| **System Logging**       | `instructions/logs_infrastructure.md`     | Governing authority for log schemas, JSON formats, event routing, and log paths.                                                                   |
| **Task Setup**           | `instructions/task_setup_instructions.md` | Local workspace bootstrap gates and validation checkpoints.                                                                                        |

---

## 2. State Machine Architectural Invariants

The execution loop is governed exclusively by the compiled graph in `automation/graph_orchestrator.py`. To prevent unmapped race conditions and infinite loops, the agent must enforce these constraints:

1. **In-Memory Time Isolation:** Time calculations are zone-independent and forced to Eastern Time (09:30–17:30). Out-of-hours triggers terminate the session at the `pre_flight` node.
2. **Capital Preservation Gate:** The `check_capital_gate` node evaluates buying power via Robinhood MCP before staging. If funds are insufficient, the conditional router shifts directly to `__end__`—**if no money, it will not send for a buy request**.
3. **5-Minute Operator Deadline:** The `post_approval_revalidate` node evaluates the time delta from the `order_staged_at` timestamp. If user confirmation takes longer than 5 minutes, it flags a timeout, triggers `cry_alert`, and exits.
4. **Deterministic Failure Branch:** If the chart pattern breaks or times out during the human wait window, the agent executes the `cry_alert` sequence and drops the cache. The session terminates immediately at `__end__` with **no loop resets**.

---

## 3. Agentic-Routable Account Selection

All approved brokerage routing operations must isolate capital allocation entirely within the designated agentic sub-account.

| Parameter               | Execution Mapping Target Value         |
| :---------------------- | :------------------------------------- |
| **Account Nickname**    | `Agentic`                              |
| **Target Account Mask** | `••••6614`                             |
| **Account Type**        | Cash Account                           |
| **Asset Restrictions**  | Equities Only (Single-name equities)   |
| **Options**             | None (no option level — equities only) |

All approved orders MUST be routed to the **Agentic ••••6614** cash account. Resolve the full `account_number` at routing time via Robinhood `get_accounts` (do not hardcode).

---

## 4. Blocked Routing Targets

The following accounts exist within the environment profile but are explicitly **blocked** from agentic order entry. Routing any automated order execution to these targets represents an immediate risk failure.

| Account                           | Mask       | Reason                                                                                               |
| :-------------------------------- | :--------- | :--------------------------------------------------------------------------------------------------- |
| **Margin / Individual (Default)** | `••••3473` | `agentic_allowed=false` — NOT agentic-routable despite being the default and holding option level 3. |
| **Roth IRA / Cash**               | `••••0530` | `agentic_allowed=false` — Retirement account, completely restricted from automated routing.          |

### Operational Implications

- The default account (`••••3473`) is the margin/options account but is **blocked** for agentic routing. Never route approved orders there.
- The Agentic account (`••••6614`) is **cash and equities-only**. Derivatives/option orders cannot be routed agentically under current account permissions, even if historical strategy blueprints define a derivatives exposure cap. Treat option setups as non-routable until an agentic-allowed options account exists.
- The single-name equity single-exposure cap (5% of net liquidity) must be computed strictly against the Agentic `••••6614` account's net liquidity, not the aggregate household balance.
```
