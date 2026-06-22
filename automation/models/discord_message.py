from __future__ import annotations

from typing import Any, Mapping, Optional

from automation.models.approval_pattern_card import ApprovalPatternCard
from automation.models.buy_sell_amount_price_card import BuySellAmountPriceCard
from automation.models.discord_common import (
    Action,
    CardAction,
    OrderType,
    Side,
    SizeType,
    TradeSide,
    TransactionStatus,
    TxStatus,
)
from automation.models.general_status_card import GeneralStatusCard, IssueSeverity, IssueType
from automation.models.transaction_result_card import TransactionResultCard


def parse_discord_channel_text(
    text: str,
    context: Optional[Mapping[str, Any]] = None,
    current_price: Optional[float] = None,
) -> BuySellAmountPriceCard:
    return BuySellAmountPriceCard.parse(text, context=context, current_price=current_price)


__all__ = [
    "ApprovalPatternCard",
    "BuySellAmountPriceCard",
    "TransactionResultCard",
    "GeneralStatusCard",
    "parse_discord_channel_text",
    "Action",
    "CardAction",
    "Side",
    "TradeSide",
    "SizeType",
    "OrderType",
    "TxStatus",
    "TransactionStatus",
    "IssueSeverity",
    "IssueType",
]
