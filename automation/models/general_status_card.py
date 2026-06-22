from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from automation.models.discord_common import enum_dict, f_num, now_et, val_float, val_str


class IssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IssueType(str, Enum):
    APP_ISSUE = "APP_ISSUE"
    LIMIT_HIT = "LIMIT_HIT"
    APPROVAL_TIMEOUT = "APPROVAL_TIMEOUT"
    MARKET_CLOSED = "MARKET_CLOSED"
    MCP_DISPATCH_REQUIRED = "MCP_DISPATCH_REQUIRED"
    DATA_MISSING = "DATA_MISSING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GeneralStatusCard:
    issue_type: IssueType
    severity: IssueSeverity
    title: str
    message: str
    status: str = "N/A"
    action_required: str = "Review logs and resume only when fixed."
    source: str = "agentic-trading"
    retry_after_seconds: Optional[float] = None
    limit_name: Optional[str] = None
    endpoint: Optional[str] = None
    thread_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=now_et)

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> "GeneralStatusCard":
        data = dict(payload or {})
        raw_status = str(data.get("execution_status", data.get("status", ""))).upper()
        issue_type = cls._issue_type(data, raw_status)
        severity = cls._severity(data, issue_type)

        title = val_str(data.get("title")) or cls._default_title(issue_type)
        message = (
            val_str(data.get("message"))
            or val_str(data.get("error"))
            or val_str(data.get("reason"))
            or val_str(data.get("rejection_reason"))
            or val_str(data.get("invalidation_reason"))
            or cls._default_message(issue_type)
        )

        return cls(
            issue_type=issue_type,
            severity=severity,
            title=title,
            message=message,
            status=raw_status or "N/A",
            action_required=val_str(data.get("action_required")) or cls._default_action(issue_type),
            source=val_str(data.get("source")) or "agentic-trading",
            retry_after_seconds=val_float(data.get("retry_after_seconds", data.get("retry_after"))),
            limit_name=val_str(data.get("limit_name", data.get("tier_limit"))),
            endpoint=val_str(data.get("endpoint")),
            thread_id=val_str(data.get("thread_id", data.get("scheduler_thread_id"))),
            details=cls._details(data),
        )

    @staticmethod
    def _issue_type(data: Mapping[str, Any], status: str) -> IssueType:
        explicit = str(data.get("issue_type", "")).upper()
        if explicit in IssueType.__members__:
            return IssueType[explicit]

        if "TIMEOUT" in status or status in {"DISCORD_APPROVAL_POLL_TIMEOUT", "TIMEOUT_EXPIRED"}:
            return IssueType.APPROVAL_TIMEOUT

        if "LIMIT" in status or "QUOTA" in status or data.get("limit_name") or data.get("tier_limit"):
            return IssueType.LIMIT_HIT

        if status in {"LOW_POWER_HIBERNATE", "MARKET_CLOSED"}:
            return IssueType.MARKET_CLOSED

        if status == "MCP_DISPATCH_REQUIRED" or data.get("queued") is True:
            return IssueType.MCP_DISPATCH_REQUIRED

        if "MISSING" in status or status in {"AWAITING_LIVE_OHLCV", "AWAITING_LIVE_MCP_BALANCES"}:
            return IssueType.DATA_MISSING

        if "FAILED" in status or "INVALID" in status or "REJECTED" in status:
            return IssueType.VALIDATION_FAILED

        if data.get("error"):
            return IssueType.APP_ISSUE

        return IssueType.UNKNOWN

    @staticmethod
    def _severity(data: Mapping[str, Any], issue_type: IssueType) -> IssueSeverity:
        explicit = str(data.get("severity", "")).upper()
        if explicit in IssueSeverity.__members__:
            return IssueSeverity[explicit]

        if issue_type in {IssueType.APPROVAL_TIMEOUT, IssueType.MARKET_CLOSED, IssueType.MCP_DISPATCH_REQUIRED, IssueType.DATA_MISSING}:
            return IssueSeverity.WARNING

        if issue_type in {IssueType.LIMIT_HIT, IssueType.VALIDATION_FAILED, IssueType.APP_ISSUE}:
            return IssueSeverity.ERROR

        return IssueSeverity.INFO

    @staticmethod
    def _details(data: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        keys = (
            "ticker",
            "direction",
            "pattern_id",
            "queue_path",
            "missing_paths",
            "mcp_requests",
            "diagnostic_payload",
            "scheduler_status",
        )
        out = {k: data[k] for k in keys if k in data and data[k] not in (None, "", [], {})}
        return out or None

    @staticmethod
    def _default_title(issue_type: IssueType) -> str:
        return {
            IssueType.APP_ISSUE: "App issue",
            IssueType.LIMIT_HIT: "API or tier limit hit",
            IssueType.APPROVAL_TIMEOUT: "Approval window expired",
            IssueType.MARKET_CLOSED: "Market window closed",
            IssueType.MCP_DISPATCH_REQUIRED: "MCP dispatch required",
            IssueType.DATA_MISSING: "Required data missing",
            IssueType.VALIDATION_FAILED: "Validation failed",
            IssueType.UNKNOWN: "Status update",
        }[issue_type]

    @staticmethod
    def _default_message(issue_type: IssueType) -> str:
        return {
            IssueType.APP_ISSUE: "The app hit an issue and stopped safely.",
            IssueType.LIMIT_HIT: "A provider or API limit was reached.",
            IssueType.APPROVAL_TIMEOUT: "Approval arrived too late or was not received in time.",
            IssueType.MARKET_CLOSED: "The graph hibernated because the market window is closed.",
            IssueType.MCP_DISPATCH_REQUIRED: "A request was queued because no dispatcher handled it.",
            IssueType.DATA_MISSING: "The graph is waiting for required live data.",
            IssueType.VALIDATION_FAILED: "The request failed validation and was blocked.",
            IssueType.UNKNOWN: "The app reported a non-terminal status.",
        }[issue_type]

    @staticmethod
    def _default_action(issue_type: IssueType) -> str:
        return {
            IssueType.APP_ISSUE: "Check runtime_error.log, fix the issue, then rerun.",
            IssueType.LIMIT_HIT: "Wait for quota reset or switch provider before resuming.",
            IssueType.APPROVAL_TIMEOUT: "Restage the signal if still valid. Do not execute the stale approval.",
            IssueType.MARKET_CLOSED: "No action needed. Scheduler can run during the next market window.",
            IssueType.MCP_DISPATCH_REQUIRED: "Process logs/mcp_request_queue.jsonl or configure MCP_DISPATCH_COMMAND.",
            IssueType.DATA_MISSING: "Fetch the required live data and resume the same thread.",
            IssueType.VALIDATION_FAILED: "Review the rejection reason. Do not force execution.",
            IssueType.UNKNOWN: "Review state and logs before resuming.",
        }[issue_type]

    def to_dict(self) -> Dict[str, Any]:
        return enum_dict(self, ("issue_type", "severity"))

    def render_markdown(self) -> str:
        icon = {
            IssueSeverity.INFO: "ℹ️",
            IssueSeverity.WARNING: "⚠️",
            IssueSeverity.ERROR: "🚨",
            IssueSeverity.CRITICAL: "🧯",
        }[self.severity]

        lines = [
            f"{icon} **{self.title.upper()}**",
            f"Type: `{self.issue_type.value}` | Severity: `{self.severity.value}` | Status: `{self.status}`",
            f"Message: {self.message}",
            f"Action: {self.action_required}",
        ]

        if self.retry_after_seconds is not None:
            lines.append(f"Retry after: `{f_num(self.retry_after_seconds)}` sec")
        if self.limit_name:
            lines.append(f"Limit: `{self.limit_name}`")
        if self.endpoint:
            lines.append(f"Endpoint: `{self.endpoint}`")
        if self.thread_id:
            lines.append(f"Thread: `{self.thread_id}`")
        if self.details:
            lines.append(f"Details: `{self.details}`")

        lines.append(f"Time: `{self.timestamp}`")
        return "\n".join(lines)
