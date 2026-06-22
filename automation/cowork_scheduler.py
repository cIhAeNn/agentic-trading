import argparse
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from automation.graph_orchestrator import app
from automation.models.state import AgentState
from automation.nodes.pattern_engine import PatternEngine
from automation.nodes.patterns.models import EngineConfig, runtime_env
from automation.runtime.discord_polling import DiscordPollingClient, DiscordPollingError
from automation.runtime.graph_runtime import GraphRuntime
from automation.runtime.mcp_dispatcher import MCPDispatcher
from automation.runtime.state_utils import approved_pattern_id, approved_ticker, merge_state, primary_setup


TERMINAL_STATUSES = {
    "NO_TICKERS",
    "SCREENING_EMPTY",
    "NO_PATTERN_MATCH",
    "PRE_FLIGHT_FAILED",
    "LOW_POWER_HIBERNATE",
    "SKIP_INSUFFICIENT_FUNDS",
    "POSITION_SIZE_TOO_SMALL",
    "REJECTED_MISSING_SIZE",
    "REJECTED_INVALID_APPROVAL_FORMAT",
    "REJECTED_BY_OPERATOR",
    "TIMEOUT_EXPIRED",
    "INVALIDATED_CANCELLED_CLEAN",
    "ORDER_READY_FOR_MCP_DISPATCH",
    "MCP_DISPATCH_REQUIRED",
    "DISCORD_APPROVAL_POLL_TIMEOUT",
}


class CoworkScheduler:
    """
    Runtime supervisor around the LangGraph app.

    Responsibilities:
    - Dispatch MCP requests.
    - Send Discord trade cards.
    - Poll Discord for authorized approval/reject/refresh replies.
    - Resume the same LangGraph thread_id.
    - Run fresh OHLCV recheck after approval.
    - Dispatch broker request after revalidation passes.
    """

    def __init__(self, thread_id: Optional[str] = None):
        self.thread_id = thread_id or self._default_thread_id()
        self.graph = GraphRuntime(app, thread_id=self.thread_id)
        self.discord = DiscordPollingClient()
        self.dispatcher = MCPDispatcher()
        self.state: Dict[str, Any] = {}
        self.sent_discord_message_id: Optional[str] = None

    @staticmethod
    def _default_thread_id() -> str:
        today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
        return f"agentic-trading-{today}"

    def run(self, initial_state: Optional[AgentState] = None, max_steps: Optional[int] = None) -> Dict[str, Any]:
        max_steps = max_steps or int(runtime_env("COWORK_MAX_STEPS", "20") or "20")
        self.state = self.graph.invoke(dict(initial_state or {}))

        for step in range(max_steps):
            self.state["cowork_step"] = step
            status = str(self.state.get("execution_status", ""))

            if status in {"AWAITING_LIVE_OHLCV", "AWAITING_LIVE_MCP_TELEMETRY"}:
                self._dispatch_mcp_and_resume()
                continue

            if status in {"AWAITING_LIVE_MCP_BALANCES", "ACCOUNT_TELEMETRY_REQUIRED"}:
                self._dispatch_mcp_and_resume()
                continue

            if status == "STAGED_AWAITING_APPROVAL":
                self._send_discord_and_wait()
                continue

            if status == "POST_APPROVAL_PATTERN_RECHECK_REQUIRED":
                self._fresh_recheck_and_resume()
                continue

            if status == "ORDER_READY_FOR_MCP_DISPATCH":
                self._dispatch_broker_and_confirm()
                return self.state

            if status in TERMINAL_STATUSES:
                return self.state

            # Some LangGraph interrupt states may not expose execution_status as expected;
            # if a Discord message is present, treat it as staged.
            if self.state.get("discord_message") and not self.state.get("operator_msg_payload"):
                self._send_discord_and_wait()
                continue

            # Unknown stable state: return for manual inspection rather than loop forever.
            self.state["scheduler_status"] = "STOPPED_UNKNOWN_STATUS"
            return self.state

        self.state["scheduler_status"] = "MAX_STEPS_EXCEEDED"
        return self.state

    def _dispatch_mcp_and_resume(self) -> None:
        requests = self.state.get("mcp_requests", [])
        if not isinstance(requests, list) or not requests:
            self.state["scheduler_status"] = "NO_MCP_REQUESTS_TO_DISPATCH"
            return

        result = self.dispatcher.dispatch_many(requests, state=self.state)

        if result.get("execution_status") == "MCP_DISPATCH_REQUIRED":
            self.state = merge_state(self.state, result)
            return

        update: Dict[str, Any] = {}

        if "market_data" in result:
            existing = dict(self.state.get("market_data", {}))
            existing.update(result["market_data"])
            update["market_data"] = existing

        if "account_telemetry" in result:
            update["account_telemetry"] = result["account_telemetry"]

        update["mcp_requests"] = []
        self.state = self.graph.resume(update)

    def _send_discord_and_wait(self) -> None:
        message = self.state.get("discord_message")
        if not message:
            self.state["scheduler_status"] = "NO_DISCORD_MESSAGE_TO_SEND"
            return

        if not self.discord.ready():
            self.state["scheduler_status"] = "DISCORD_CLIENT_NOT_READY"
            return

        if not self.sent_discord_message_id:
            sent = self.discord.send_message(str(message))
            self.sent_discord_message_id = str(sent.get("id"))
            if not self.sent_discord_message_id:
                self.state["scheduler_status"] = "DISCORD_SEND_NO_MESSAGE_ID"
                return

        timeout_min = int(runtime_env("APPROVAL_TIMEOUT_MIN", "5") or "5")
        approval = self.discord.wait_for_approval(
            after_message_id=self.sent_discord_message_id,
            timeout_seconds=timeout_min * 60,
        )

        if not approval.get("operator_msg_payload"):
            self.state = merge_state(self.state, approval)
            return

        self.state = self.graph.resume(
            {
                "operator_msg_payload": approval["operator_msg_payload"],
                "discord_approval_message_id": approval.get("discord_approval_message_id"),
                "discord_approval_author_id": approval.get("discord_approval_author_id"),
            }
        )

    def _fresh_recheck_and_resume(self) -> None:
        ticker = approved_ticker(self.state)
        if not ticker:
            self.state = self.graph.resume(
                {
                    "pattern_still_valid": False,
                    "invalidation_reason": "No approved ticker found for post-approval recheck.",
                }
            )
            return

        requests = self.state.get("mcp_requests", [])
        if not isinstance(requests, list) or not requests:
            requests = [
                {
                    "tool_family": "market_data_mcp",
                    "action": "fetch_fresh_ohlcv_for_approved_ticker",
                    "ticker": ticker,
                    "required_fields": ["open", "high", "low", "close", "volume", "timestamp"],
                }
            ]

        result = self.dispatcher.dispatch_many(requests, state=self.state)
        if "market_data" not in result:
            self.state = merge_state(self.state, result)
            return

        fresh_market_data = result["market_data"]
        ticker_data = fresh_market_data.get(ticker) or fresh_market_data.get(ticker.upper())

        if not ticker_data:
            self.state = self.graph.resume(
                {
                    "pattern_still_valid": False,
                    "invalidation_reason": "Fresh OHLCV was not returned for approved ticker.",
                }
            )
            return

        pattern_id = approved_pattern_id(self.state)
        config = EngineConfig.from_env()
        recheck = PatternEngine.evaluate_universe([ticker], {ticker: ticker_data}, config=config)

        matches = recheck.get("matched_setups", [])
        still_valid = False

        if isinstance(matches, list):
            for match in matches:
                if not isinstance(match, dict):
                    continue
                if pattern_id and match.get("pattern_id") != pattern_id:
                    continue
                still_valid = bool(match.get("is_valid", True))
                break

        existing_market_data = dict(self.state.get("market_data", {}))
        existing_market_data.update({ticker: ticker_data})

        update = {
            "market_data": existing_market_data,
            "pattern_still_valid": still_valid,
            "post_approval_recheck": recheck.get("pattern_summary", {}),
            "mcp_requests": [],
        }

        if not still_valid:
            update["invalidation_reason"] = "Pattern no longer matched after fresh OHLCV recheck."

        self.state = self.graph.resume(update)

    def _dispatch_broker_and_confirm(self) -> None:
        requests = self.state.get("mcp_requests", [])
        if not isinstance(requests, list) or not requests:
            self.state["scheduler_status"] = "NO_BROKER_REQUEST_TO_DISPATCH"
            return

        result = self.dispatcher.dispatch_many(requests, state=self.state)

        if result.get("execution_status") == "MCP_DISPATCH_REQUIRED":
            self.state = merge_state(self.state, result)
            return

        self.state = merge_state(self.state, result)

        confirmation = result.get("broker_confirmation", {})
        if not isinstance(confirmation, dict):
            confirmation = {}

        execution_state = merge_state(
            self.state,
            {
                "fill_status": confirmation.get("fill_status", confirmation.get("status", "CONFIRMED")),
                "transaction_id": confirmation.get("transaction_id", confirmation.get("tx_id", "N/A")),
                "executed_at": confirmation.get("executed_at", datetime.now(ZoneInfo("America/New_York")).isoformat()),
            },
        )

        # Prepare execution confirmation card.
        try:
            from automation.services.discord import DiscordMCPConnector

            confirm = DiscordMCPConnector.emit_execution_confirmation(execution_state)
            self.state = merge_state(execution_state, confirm)

            if self.discord.ready() and confirm.get("discord_message"):
                self.discord.send_message(str(confirm["discord_message"]))

        except DiscordPollingError:
            raise
        except Exception as exc:
            self.state = merge_state(
                execution_state,
                {
                    "execution_status": "BROKER_CONFIRMATION_RECEIVED_DISCORD_CONFIRM_FAILED",
                    "error": str(exc),
                },
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic trading cowork scheduler.")
    parser.add_argument("--thread-id", default=None)
    parser.add_argument("--initial-state-json", default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()

    initial_state: Dict[str, Any] = {}
    if args.initial_state_json:
        initial_state = json.loads(args.initial_state_json)

    scheduler = CoworkScheduler(thread_id=args.thread_id)
    result = scheduler.run(initial_state=initial_state, max_steps=args.max_steps)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
