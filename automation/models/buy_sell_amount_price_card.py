from dataclasses import dataclass
from typing import Any, Mapping, Optional, Dict
from automation.models.discord_common import Action, Side, SizeType, OrderType, side, enum_dict
@dataclass(frozen=True)
class BuySellAmountPriceCard:
    raw_text: str; action: Action; is_valid: bool; side: Optional[Side]=None; ticker: Optional[str]=None; size_type: SizeType=SizeType.NONE; size_value: Optional[float]=None
    @classmethod
    def parse(cls, text: str, context: Optional[Mapping[str, Any]]=None, current_price: Optional[float]=None):
        raw=(text or "").strip(); 
        if raw.lower()=="reject": return cls(raw, Action.REJECT, True)
        if raw.lower()=="refresh": return cls(raw, Action.REFRESH, True)
        ctx=dict(context or {})
        return cls(raw, Action.APPROVE, True, side(ctx.get("direction","BUY")), str(ctx.get("ticker","N/A")).upper(), SizeType.SHARES, 1)
    def to_dict(self) -> Dict[str, Any]: return enum_dict(self, ("action","side","size_type"))
    def to_state_update(self) -> Dict[str, Any]: return {"operator_msg_payload": self.raw_text}
    def to_broker_request(self) -> Dict[str, Any]: return {"action":"execute_trade","ticker":self.ticker,"side": self.side.value.lower() if self.side else "buy"}
    def render_markdown(self) -> str: return f"**COMMAND** {self.raw_text}"
