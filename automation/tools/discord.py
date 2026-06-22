from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from automation.models.approval_pattern_card import ApprovalPatternCard
from automation.models.buy_sell_amount_price_card import BuySellAmountPriceCard
from automation.models.general_status_card import GeneralStatusCard
from automation.models.transaction_result_card import TransactionResultCard


DISCORD_API = "https://discord.com/api/v10"


def runtime_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    path = Path("config/claude_desktop_config.json")
    if not path.exists():
        return default

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

    top_env = data.get("env")
    if isinstance(top_env, dict) and top_env.get(name) not in (None, ""):
        return str(top_env[name])

    servers = data.get("mcpServers")
    if isinstance(servers, dict):
        misplaced = servers.get("env")
        if isinstance(misplaced, dict) and misplaced.get(name) not in (None, ""):
            return str(misplaced[name])

        for server in servers.values():
            if isinstance(server, dict):
                env = server.get("env")
                if isinstance(env, dict) and env.get(name) not in (None, ""):
                    return str(env[name])

    return default


class DiscordTool:
    """
    Sends and parses Discord model cards.

    Cards:
    - ApprovalPatternCard
    - TransactionResultCard
    - BuySellAmountPriceCard
    - GeneralStatusCard

    This tool sends/parses messages only. It does not execute trades.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        channel_id: Optional[str] = None,
        authorized_user_id: Optional[str] = None,
        authorized_user_handle: Optional[str] = None,
    ):
        self.token = token or runtime_env("DISCORD_TOKEN")
        self.channel_id = channel_id or runtime_env("TARGET_CHANNEL_ID")
        self.authorized_user_id = authorized_user_id or runtime_env("AUTHORIZED_SNOWFLAKE_ID")
        self.authorized_user_handle = authorized_user_handle or runtime_env("AUTHORIZED_USER_HANDLE")
        self.poll_seconds = max(1, int(float(runtime_env("DISCORD_POLL_SECONDS", "5") or "5")))

    def ready(self) -> bool:
        return bool(self.token and self.channel_id)

    def send_approval_card(
        self,
        payload: Mapping[str, Any] | ApprovalPatternCard,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        card = payload if isinstance(payload, ApprovalPatternCard) else ApprovalPatternCard.parse(payload)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_transaction_card(
        self,
        payload: Mapping[str, Any] | TransactionResultCard,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        card = payload if isinstance(payload, TransactionResultCard) else TransactionResultCard.parse(payload)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_general_status_card(
        self,
        payload: Mapping[str, Any] | GeneralStatusCard,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        card = payload if isinstance(payload, GeneralStatusCard) else GeneralStatusCard.parse(payload)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_buy_sell_card(
        self,
        payload: str | BuySellAmountPriceCard,
        context: Optional[Mapping[str, Any]] = None,
        current_price: Optional[float] = None,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        card = payload if isinstance(payload, BuySellAmountPriceCard) else self.parse_buy_sell_text(payload, context, current_price)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def parse_buy_sell_text(
        self,
        text: str,
        context: Optional[Mapping[str, Any]] = None,
        current_price: Optional[float] = None,
    ) -> BuySellAmountPriceCard:
        return BuySellAmountPriceCard.parse(text, context=context, current_price=current_price)

    def parse_general_status(self, payload: Mapping[str, Any]) -> GeneralStatusCard:
        return GeneralStatusCard.parse(payload)

    def parse_channel_message(
        self,
        message: str | Mapping[str, Any],
        context: Optional[Mapping[str, Any]] = None,
        current_price: Optional[float] = None,
    ) -> BuySellAmountPriceCard:
        text = message.get("content", "") if isinstance(message, Mapping) else str(message)
        return self.parse_buy_sell_text(text, context=context, current_price=current_price)

    def send_text(self, content: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        target = channel_id or self.channel_id
        if not self.token:
            raise RuntimeError("DISCORD_TOKEN missing.")
        if not target:
            raise RuntimeError("TARGET_CHANNEL_ID missing.")

        return self._request("POST", f"/channels/{target}/messages", {"content": content})

    def fetch_messages_after(
        self,
        after_message_id: Optional[str] = None,
        limit: int = 20,
        channel_id: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        target = channel_id or self.channel_id
        if not target:
            raise RuntimeError("TARGET_CHANNEL_ID missing.")

        query = {"limit": str(limit)}
        if after_message_id:
            query["after"] = str(after_message_id)

        data = self._request("GET", f"/channels/{target}/messages?{urllib.parse.urlencode(query)}")
        return list(reversed(data)) if isinstance(data, list) else []

    def wait_for_parsed_command(
        self,
        after_message_id: str,
        context: Optional[Mapping[str, Any]] = None,
        current_price: Optional[float] = None,
        timeout_seconds: int = 300,
        channel_id: Optional[str] = None,
    ) -> BuySellAmountPriceCard:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            for msg in self.fetch_messages_after(after_message_id, channel_id=channel_id):
                if not self.is_authorized(msg):
                    continue

                card = self.parse_channel_message(msg, context=context, current_price=current_price)
                if card.is_valid:
                    return card

            time.sleep(self.poll_seconds)

        return BuySellAmountPriceCard.parse("")

    def is_authorized(self, message: Mapping[str, Any]) -> bool:
        author = message.get("author", {}) if isinstance(message, Mapping) else {}
        author_id = str(author.get("id", ""))

        if self.authorized_user_id and author_id == str(self.authorized_user_id):
            return True

        if self.authorized_user_handle:
            expected = self.authorized_user_handle.strip().lstrip("@").lower()
            names: Iterable[str] = (
                str(author.get("username", "")).lower(),
                str(author.get("global_name", "")).lower(),
                f'{author.get("username", "")}#{author.get("discriminator", "")}'.lower(),
            )
            return expected in [x.lstrip("@") for x in names if x]

        return False

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("DISCORD_TOKEN missing.")
        return {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "agentic-trading-discord-tool/1.1",
        }

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{DISCORD_API}{path}", data=body, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                text = response.read().decode("utf-8")
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Discord HTTP {exc.code}: {text}") from exc


DiscordCardTool = DiscordTool
