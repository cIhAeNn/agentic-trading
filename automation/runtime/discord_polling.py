import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from automation.nodes.patterns.models import runtime_env


DISCORD_API = "https://discord.com/api/v10"


class DiscordPollingError(RuntimeError):
    pass


class DiscordPollingClient:
    """
    Minimal Discord REST polling client.

    This uses a bot token and polls channel messages after the trade-card message id.
    It does not use a user token.
    """

    def __init__(self):
        self.token = runtime_env("DISCORD_TOKEN")
        self.channel_id = runtime_env("TARGET_CHANNEL_ID")
        self.authorized_snowflake_id = runtime_env("AUTHORIZED_SNOWFLAKE_ID")
        self.authorized_user_handle = runtime_env("AUTHORIZED_USER_HANDLE")

        poll_seconds_raw = runtime_env("DISCORD_POLL_SECONDS", "5") or "5"
        self.poll_seconds = max(1, int(float(poll_seconds_raw)))

    def ready(self) -> bool:
        return bool(self.token and self.channel_id)

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise DiscordPollingError("DISCORD_TOKEN is missing.")
        return {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "agentic-trading-cowork-scheduler/1.0",
        }

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        url = f"{DISCORD_API}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise DiscordPollingError(f"Discord HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise DiscordPollingError(f"Discord request failed: {exc}") from exc

    def send_message(self, content: str) -> Dict[str, Any]:
        if not self.channel_id:
            raise DiscordPollingError("TARGET_CHANNEL_ID is missing.")
        return self._request("POST", f"/channels/{self.channel_id}/messages", {"content": content})

    def fetch_messages_after(self, after_message_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.channel_id:
            raise DiscordPollingError("TARGET_CHANNEL_ID is missing.")

        query = {"limit": str(limit)}
        if after_message_id:
            query["after"] = str(after_message_id)

        path = f"/channels/{self.channel_id}/messages?{urllib.parse.urlencode(query)}"
        messages = self._request("GET", path)
        if not isinstance(messages, list):
            return []

        # Discord returns newest first; process oldest first.
        return list(reversed(messages))

    def is_authorized(self, message: Dict[str, Any]) -> bool:
        author = message.get("author", {})
        author_id = str(author.get("id", ""))

        if self.authorized_snowflake_id and author_id == str(self.authorized_snowflake_id):
            return True

        if self.authorized_user_handle:
            expected = self.authorized_user_handle.strip().lstrip("@").lower()
            candidates = [
                str(author.get("username", "")).lower(),
                str(author.get("global_name", "")).lower(),
                f'{author.get("username", "")}#{author.get("discriminator", "")}'.lower(),
            ]
            return expected in [c.lstrip("@") for c in candidates if c]

        # If neither allow-list is set, block by default.
        return False

    def wait_for_approval(self, after_message_id: str, timeout_seconds: int) -> Dict[str, Any]:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            messages = self.fetch_messages_after(after_message_id=after_message_id)

            for message in messages:
                content = str(message.get("content", "")).strip()
                if not content:
                    continue

                if not self.is_authorized(message):
                    continue

                lowered = content.lower()
                if (
                    lowered.startswith("approve")
                    or lowered.startswith("go")
                    or lowered.startswith("yes")
                    or lowered in {"reject", "no", "cancel", "refresh", "recheck", "revalidate"}
                ):
                    return {
                        "operator_msg_payload": content,
                        "discord_approval_message_id": message.get("id"),
                        "discord_approval_author_id": message.get("author", {}).get("id"),
                    }

            time.sleep(self.poll_seconds)

        return {
            "operator_msg_payload": "",
            "execution_status": "DISCORD_APPROVAL_POLL_TIMEOUT",
        }
