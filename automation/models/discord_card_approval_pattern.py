from dataclasses import dataclass
from typing import Any, Mapping, Dict
from automation.models.discord_common import Side, side, enum_dict
@dataclass(frozen=True)
class ApprovalPatternCard:
    ticker: str; side: Side; pattern_id: str="N/A"; pattern_name: str="N/A"
    @classmethod
    def parse(cls, payload: Mapping[str, Any]): return cls(str(payload.get("ticker","N/A")).upper(), side(payload.get("direction","BUY")))
    def to_dict(self) -> Dict[str, Any]: return enum_dict(self, ("side",))
    def render_markdown(self) -> str: return f"**APPROVAL** `{self.ticker}` {self.side.value}"
