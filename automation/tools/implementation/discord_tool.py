from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from automation.models.discord_card_approval_pattern import ApprovalPatternCard
from automation.models.discord_card_buy_sell import BuySellAmountPriceCard
from automation.models.discord_card_general_status import GeneralStatusCard
from automation.models.transaction_result_card import TransactionResultCard

from automation.tools.interface.discord_tool_interface import IDiscordTool
from automation.tools.interface.logger_tool_interface import ILoggerTool
from automation.tools.implementation.logger_tool import LoggerTool


DISCORD_API = "https://discord.com/api/v10"


def runtime_env(name: str, default: Optional[str] = None) -> Optional[str]:
    # ... [Same environment resolution logic as before] ...
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


class DiscordTool(IDiscordTool):
    """
    Concrete implementation of IDiscordTool.
    Includes injected dependency for centralized application logging.
    """

    def __init__(
        self,
        logger: Optional[ILoggerTool] = None,
        token: Optional[str] = None,
        channel_id: Optional[str] = None,
        authorized_user_id: Optional[str] = None,
        authorized_user_handle: Optional[str] = None,
    ):
        self.logger = logger or LoggerTool()
        self.log_context = "DiscordTool"
        
        self.token = token or runtime_env("DISCORD_TOKEN")
        self.channel_id = channel_id or runtime_env("TARGET_CHANNEL_ID")
        self.authorized_user_id = authorized_user_id or runtime_env("AUTHORIZED_SNOWFLAKE_ID")
        self.authorized_user_handle = authorized_user_handle or runtime_env("AUTHORIZED_USER_HANDLE")

        if not self.ready():
            self.logger.warning("DiscordTool initialized without full credentials.", context=self.log_context)
        else:
            self.logger.info("DiscordTool initialized successfully.", context=self.log_context)

    def ready(self) -> bool:
        return bool(self.token and self.channel_id)

    def validate_configuration(self, target_channel: Optional[str] = None) -> str:
        if not self.token:
            self.logger.error("DISCORD_TOKEN missing during validation.", context=self.log_context)
            raise RuntimeError("DISCORD_TOKEN missing. Configuration invalid.")
        
        active_channel = target_channel or self.channel_id
        if not active_channel:
            self.logger.error("TARGET_CHANNEL_ID missing during validation.", context=self.log_context)
            raise RuntimeError("TARGET_CHANNEL_ID missing. Configuration invalid.")
            
        return active_channel

    def _is_authorized(self, message: Mapping[str, Any]) -> bool:
        match message:
            case {"author": {"id": author_id}} if self.authorized_user_id and str(author_id) == str(self.authorized_user_id):
                return True
                
            case {"author": author_dict} if self.authorized_user_handle:
                expected = self.authorized_user_handle.strip().lstrip("@").lower()
                names: Iterable[str] = (
                    str(author_dict.get("username", "")).lower(),
                    str(author_dict.get("global_name", "")).lower(),
                    f'{author_dict.get("username", "")}#{author_dict.get("discriminator", "")}'.lower(),
                )
                return expected in [x.lstrip("@") for x in names if x]
                
            case _:
                return False

    # --- FETCH METHODS ---

    def fetch_recent_messages(self, limit: int = 50, channel_id: Optional[str] = None) -> List[Mapping[str, Any]]:
        target = self.validate_configuration(channel_id)
        safe_limit = max(1, min(limit, 100))
        
        self.logger.debug(f"Fetching up to {safe_limit} recent messages from channel {target}.", context=self.log_context)
        endpoint = f"/channels/{target}/messages?limit={safe_limit}"
        response = self._request("GET", endpoint)
        
        return response if isinstance(response, list) else []

    # --- SEND METHODS ---

    def send_text(self, content: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        target = self.validate_configuration(channel_id)
        self.logger.debug(f"Sending text message to channel {target}.", context=self.log_context)
        return self._request("POST", f"/channels/{target}/messages", {"content": content})

    def send_approval_card(self, payload: Union[Mapping[str, Any], ApprovalPatternCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        card = payload if isinstance(payload, ApprovalPatternCard) else ApprovalPatternCard.parse(payload)
        self.logger.info("Sending ApprovalPatternCard to Discord.", context=self.log_context)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_transaction_card(self, payload: Union[Mapping[str, Any], TransactionResultCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        card = payload if isinstance(payload, TransactionResultCard) else TransactionResultCard.parse(payload)
        self.logger.info("Sending TransactionResultCard to Discord.", context=self.log_context)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_general_status_card(self, payload: Union[Mapping[str, Any], GeneralStatusCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        card = payload if isinstance(payload, GeneralStatusCard) else GeneralStatusCard.parse(payload)
        self.logger.info("Sending GeneralStatusCard to Discord.", context=self.log_context)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    def send_buy_sell_card(self, payload: Union[str, BuySellAmountPriceCard], context: Optional[Mapping[str, Any]] = None, current_price: Optional[float] = None, channel_id: Optional[str] = None) -> Dict[str, Any]:
        card = payload if isinstance(payload, BuySellAmountPriceCard) else BuySellAmountPriceCard.parse(payload, context=context, current_price=current_price)
        self.logger.info("Sending BuySellAmountPriceCard to Discord.", context=self.log_context)
        return self.send_text(card.render_markdown(), channel_id=channel_id)

    # --- PARSE METHODS ---

    def _extract_text(self, message: Union[str, Mapping[str, Any]]) -> str:
        match message:
            case {"content": str(content)}:
                return content
            case str(content):
                return content
            case _:
                return ""

    def parse_messages(self, messages: Iterable[Mapping[str, Any]], context: Optional[Mapping[str, Any]] = None, current_price: Optional[float] = None) -> List[Any]:
        self.validate_configuration()
        valid_cards: List[Any] = []

        self.logger.debug("Parsing message batch for valid trading cards.", context=self.log_context)

        for msg in messages:
            if not self._is_authorized(msg):
                continue

            content = self._extract_text(msg)
            if not content.strip():
                continue

            buy_sell = BuySellAmountPriceCard.parse(content, context=context, current_price=current_price)
            approval = ApprovalPatternCard.parse(content)
            transaction = TransactionResultCard.parse(content)
            status = GeneralStatusCard.parse(content)

            match (buy_sell, approval, transaction, status):
                case (BuySellAmountPriceCard(is_valid=True) as valid_card, _, _, _):
                    self.logger.debug("Successfully parsed a BuySellAmountPriceCard.", context=self.log_context)
                    valid_cards.append(valid_card)
                case (_, ApprovalPatternCard(is_valid=True) as valid_card, _, _):
                    self.logger.debug("Successfully parsed an ApprovalPatternCard.", context=self.log_context)
                    valid_cards.append(valid_card)
                case (_, _, TransactionResultCard(is_valid=True) as valid_card, _):
                    self.logger.debug("Successfully parsed a TransactionResultCard.", context=self.log_context)
                    valid_cards.append(valid_card)
                case (_, _, _, GeneralStatusCard(is_valid=True) as valid_card):
                    self.logger.debug("Successfully parsed a GeneralStatusCard.", context=self.log_context)
                    valid_cards.append(valid_card)
                case _:
                    pass 

        return valid_cards

    # --- HTTP UTILS ---

    def _headers(self) -> Dict[str, str]:
        self.validate_configuration()
        return {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "agentic-trading-discord-tool/2.0",
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
            self.logger.error(f"Discord HTTP {exc.code} Error during {method} {path}: {text}", context=self.log_context, exc_info=True)
            raise RuntimeError(f"Discord HTTP {exc.code}: {text}") from exc


DiscordCardTool = DiscordTool