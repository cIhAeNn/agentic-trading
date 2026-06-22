# Logging, Telemetry, and Exception Isolation Specification

## 1. Purpose

This document defines production logging, audit ledgers, exception isolation, and diagnostic routing for the `agentic-trading` LangGraph runtime.

The system uses two logging layers:

| Layer | Files | Purpose |
|---|---|---|
| Audit ledger layer | `logs/activity_ledger.json`, `logs/error_trace.json` | Structured state-machine event history |
| Runtime service layer | `logs/runtime.log`, `logs/runtime_error.log` | Rotating JSON-line Python service logs |

## 2. Required Log Directory

| Directory | Required State | Access |
|---|---|---|
| `logs/` | Exists before graph execution | Read / Write |

Ignore during normal runtime:

```text
logs/.__probe
logs/.__wtest_5.json
logs/graph_topology.png
```

## 3. Audit Ledger Files

| File | Format | Status Type | Purpose |
|---|---|---|---|
| `logs/activity_ledger.json` | JSON array | `SUCCESS` | Successful graph events |
| `logs/error_trace.json` | JSON array | `FAILED` | Failed graph events, invalidations, throttles, exceptions |

## 4. Runtime Service Log Files

| File | Format | Rotation | Purpose |
|---|---|---|---|
| `logs/runtime.log` | JSON Lines | `1 MB x 5 backups` | INFO+ service telemetry |
| `logs/runtime_error.log` | JSON Lines | `1 MB x 5 backups` | WARNING+ service faults |

Runtime modules must use Python `logging`.

Do not use `print()` in production modules.

## 5. Production Logger Requirements

### 5.1 Logger Format

Each runtime log row must be a single JSON object.

```json
{
  "timestamp": "ISO 8601 America/New_York timestamp",
  "level": "INFO | WARNING | ERROR | CRITICAL",
  "logger": "agentic.discord | agentic.robinhood | agentic.validators",
  "message": "Short event message",
  "module": "Python module name",
  "function": "Function name",
  "event": "MACHINE_READABLE_EVENT_KEY"
}
```

### 5.2 Required Logger Names

| Module | Logger Name |
|---|---|
| `automation/services/discord.py` | `agentic.discord` |
| `automation/services/robinhood.py` | `agentic.robinhood` |
| `automation/nodes/validators.py` | `agentic.validators` |

### 5.3 Runtime Log Handler

Runtime logs must use `RotatingFileHandler`.

| Parameter | Value |
|---|---|
| `maxBytes` | `1_000_000` |
| `backupCount` | `5` |
| Encoding | `utf-8` |

## 6. Authorized Audit Event Types

### 6.1 Successful Events

Write successful events to `logs/activity_ledger.json`.

| Event Type | Trigger |
|---|---|
| `SCREEN_RUN` | Scanner completes without trade staging |
| `PATTERN_MATCH` | Pattern validation succeeds |
| `ORDER_STAGED` | Discord trade approval message is prepared |
| `ORDER_APPROVED` | Operator approval parses and post-approval revalidation passes |
| `ORDER_EXECUTED` | Brokerage confirms execution |

### 6.2 Failed Events

Write failed events to `logs/error_trace.json`.

| Event Type | Trigger |
|---|---|
| `ORDER_INVALIDATED` | Approved setup fails post-approval revalidation |
| `API_ERROR` | Tool fault, parser failure, timeout, missing channel, file fault, or runtime exception |
| `RATE_LIMIT_THROTTLE` | API quota or HTTP `429` throttle |
| `PARITY_ERROR` | Pre-flight log/file/state parity failure |

## 7. Audit JSON Schema

### 7.1 Activity Ledger Schema

```json
{
  "timestamp": "ISO 8601 America/New_York timestamp",
  "event_type": "SCREEN_RUN | PATTERN_MATCH | ORDER_STAGED | ORDER_APPROVED | ORDER_EXECUTED",
  "status": "SUCCESS",
  "payload": {}
}
```

### 7.2 Error Trace Schema

```json
{
  "timestamp": "ISO 8601 America/New_York timestamp",
  "event_type": "ORDER_INVALIDATED | API_ERROR | RATE_LIMIT_THROTTLE | PARITY_ERROR",
  "status": "FAILED",
  "payload": {}
}
```

## 8. Compact Audit Payloads

Do not write full Discord message bodies to audit files unless debugging is explicitly enabled.

| Event | Required Payload |
|---|---|
| `ORDER_STAGED` | `ticker`, `direction`, `pattern_id`, `pattern_name`, `target_channel_id_present`, `execution_status` |
| `ORDER_APPROVED` | `size_mode`, `size_value`, `execution_status` |
| `ORDER_EXECUTED` | `ticker`, `direction`, `quantity`, `notional`, `transaction_id` |
| `ORDER_INVALIDATED` | `ticker`, `direction`, `reason`, `execution_status` |
| `API_ERROR` | `reason`, `execution_status`, `ticker`, `direction` |
| `RATE_LIMIT_THROTTLE` | `trigger_source`, `http_status_code`, `quota_state`, `execution_status` |
| `PARITY_ERROR` | `source_file`, `reason`, `execution_status` |

## 9. Pre-Flight Log Parity Check

Before entering an active market loop:

| Step | Required Action |
|---:|---|
| 1 | Open `logs/activity_ledger.json`. |
| 2 | Open `logs/error_trace.json`. |
| 3 | Read final `3` entries from each file. |
| 4 | Validate both files are JSON arrays. |
| 5 | Validate each entry contains `timestamp`, `event_type`, `status`, and `payload`. |
| 6 | If validation fails, write `PARITY_ERROR` to `logs/error_trace.json` and halt graph execution. |

## 10. Exception Isolation Protocol

If any module detects an exception, timeout, bad credential, malformed response, rate-limit throttle, or missing runtime dependency:

| Step | Action |
|---:|---|
| 1 | Stop the active graph branch. |
| 2 | Clear staged order state. |
| 3 | Write failed audit event to `logs/error_trace.json`. |
| 4 | Write runtime stack trace to `logs/runtime_error.log`. |
| 5 | Send critical Discord message if Discord remains available. |
| 6 | Return terminal fault state. |

## 11. Queue Evacuation Rule

When any event writes to `logs/error_trace.json`:

| Variable Class | Action |
|---|---|
| Staged order payload | Clear |
| Pending approval token | Clear |
| Cached broker order | Clear |
| Unexecuted order quantity | Clear unless retained only for diagnostic payload |

## 12. Discord Logging Rules

| Branch | Audit Event | Runtime Log |
|---|---|---|
| Trade message prepared | `ORDER_STAGED` | `agentic.discord` INFO |
| Approval parsed | `ORDER_APPROVED` | `agentic.discord` INFO |
| Missing size | `API_ERROR` | `agentic.discord` WARNING |
| Timeout | `API_ERROR` | `agentic.discord` WARNING |
| CRY invalidation | `ORDER_INVALIDATED` | `agentic.discord` WARNING |
| Missing channel | `API_ERROR` | `agentic.discord` ERROR |
| Critical fault | `API_ERROR` | `agentic.discord` ERROR |

## 13. Robinhood Logging Rules

| Branch | Runtime Log |
|---|---|
| Awaiting live quote tool | `agentic.robinhood` INFO |
| Awaiting balance tool | `agentic.robinhood` INFO |
| Order ready for MCP dispatch | `agentic.robinhood` INFO |
| Invalid order size | `agentic.robinhood` ERROR |
| Empty ticker universe | `agentic.robinhood` WARNING |

## 14. Validator Logging Rules

| Branch | Runtime Log |
|---|---|
| Pre-flight passed | `agentic.validators` INFO |
| Market closed / off-hours | `agentic.validators` INFO |
| Market override active | `agentic.validators` WARNING |
| Screening universe loaded | `agentic.validators` INFO |
| Screening file missing | `agentic.validators` ERROR |
| Validator crash | `agentic.validators` ERROR with exception |

## 15. Hard Prohibitions

| Prohibited Action | Reason |
|---|---|
| `print()` in production modules | Not structured, not persisted, not queryable |
| Full Discord message in audit payload by default | Token waste |
| Successful events in `error_trace.json` | Trace contamination |
| Failed events in `activity_ledger.json` | Trace contamination |
| Silent exception swallowing | Breaks auditability |
| Direct `sys.exit()` inside graph nodes | Bypasses state-machine routing |

## 16. Critical Error Diagnostic Card

If a critical fault occurs and Discord remains available, emit:

```text
🚨 CRITICAL ERROR
endpoint `{endpoint}` | type `{failure_type}` | limit `{tier_limit}` | state `FROZEN`
log `logs/error_trace.json`
```

## 17. Operational Result Codes

| Code | Meaning |
|---|---|
| `PRE_FLIGHT_PASSED` | Startup checks passed |
| `LOW_POWER_HIBERNATE` | Market window closed; clean termination |
| `SCREENING_LOADED` | Screening universe loaded |
| `SCREENING_EMPTY` | Screening file exists but no tickers parsed |
| `SCREENING_FILE_MISSING` | Screening universe file missing |
| `AWAITING_LIVE_MCP_TELEMETRY` | Orchestrator must call market data MCP |
| `AWAITING_LIVE_MCP_BALANCES` | Orchestrator must call balance MCP |
| `ORDER_READY_FOR_MCP_DISPATCH` | Approved order ready for live MCP route |
| `STAGED_AWAITING_APPROVAL` | Discord approval pending |
| `APPROVED_REVALIDATION_PASSED` | Approval parsed and revalidation passed |
| `INVALIDATED_CANCELLED_CLEAN` | Post-approval revalidation failed; no trade executed |
| `CRITICAL_ERROR_REPORTED` | Critical fault surfaced and logged |
