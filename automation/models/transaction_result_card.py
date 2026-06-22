from dataclasses import dataclass
from typing import Any, Mapping, Dict
from automation.models.discord_common import Side, TxStatus, side, tx_status, enum_dict
@dataclass(frozen=True)
class TransactionResultCard:
    status: TxStatus; ticker: str; side: Side
    @classmethod
    def parse(cls, payload: Mapping[str, Any]): return cls(tx_status(payload.get("execution_status")), str(payload.get("ticker","N/A")).upper(), side(payload.get("direction","BUY")))
    def to_dict(self) -> Dict[str, Any]: return enum_dict(self, ("status","side"))
    def render_markdown(self) -> str: return f"**TRANSACTION {self.status.value}** `{self.ticker}` {self.side.value}"
