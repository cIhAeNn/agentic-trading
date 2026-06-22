from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from automation.models.discord_card_approval_pattern import ApprovalPatternCard
from automation.models.discord_card_buy_sell import BuySellAmountPriceCard
from automation.models.discord_card_general_status import GeneralStatusCard
from automation.models.transaction_result_card import TransactionResultCard


class IDiscordTool(ABC):
    """
    Interface contract for the Discord interaction layer.
    Allows for easy mocking/dependency injection in tests or agent execution.
    """

    @abstractmethod
    def fetch_recent_messages(self, limit: int = 50, channel_id: Optional[str] = None) -> List[Mapping[str, Any]]:
        """Retrieves recent messages from a target text channel."""
        pass

    @abstractmethod
    def send_text(self, content: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends a plain text message to the target channel."""
        pass

    @abstractmethod
    def send_approval_card(self, payload: Union[Mapping[str, Any], ApprovalPatternCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_transaction_card(self, payload: Union[Mapping[str, Any], TransactionResultCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_general_status_card(self, payload: Union[Mapping[str, Any], GeneralStatusCard], channel_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def send_buy_sell_card(self, payload: Union[str, BuySellAmountPriceCard], context: Optional[Mapping[str, Any]] = None, current_price: Optional[float] = None, channel_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def parse_messages(self, messages: Iterable[Mapping[str, Any]], context: Optional[Mapping[str, Any]] = None, current_price: Optional[float] = None) -> List[Any]:
        """Parses a batch of messages and returns a list of valid Card objects."""
        pass