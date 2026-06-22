from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional
from zoneinfo import ZoneInfo
class Side(str, Enum): BUY="BUY"; SELL="SELL"
class Action(str, Enum): APPROVE="APPROVE"; REJECT="REJECT"; REFRESH="REFRESH"; INVALID="INVALID"
class SizeType(str, Enum): SHARES="shares"; AMOUNT="amount"; NONE="none"
class OrderType(str, Enum): MARKET="market"; LIMIT="limit"
class TxStatus(str, Enum): SUCCESS="SUCCESS"; FAILED="FAILED"; BLOCKED="BLOCKED"; PENDING="PENDING"
def now_et() -> str: return datetime.now(ZoneInfo("America/New_York")).isoformat()
def f_money(v: Any) -> str:
    if v in (None,"","N/A"): return "N/A"
    try: return f"${float(v):,.2f}"
    except Exception: return str(v)
def f_num(v: Any) -> str:
    if v in (None,"","N/A"): return "N/A"
    try: return f"{float(v):,.4f}".rstrip("0").rstrip(".")
    except Exception: return str(v)
def f_pct(v: Any) -> str:
    if v in (None,"","N/A"): return "N/A"
    try:
        x=float(v); return f"{x*100 if abs(x)<=1 else x:.2f}%"
    except Exception: return str(v)
def val_float(v: Any) -> Optional[float]:
    if v in (None,"","N/A"): return None
    try: return float(str(v).replace("$","").replace(",","").replace("%",""))
    except Exception: return None
def val_int(v: Any) -> Optional[int]:
    x=val_float(v); return None if x is None else int(x)
def val_str(v: Any) -> Optional[str]: return None if v in (None,"") else str(v)
def side(v: Any) -> Side: return Side.SELL if str(v).strip().upper()=="SELL" else Side.BUY
def side_or_none(v: Any) -> Optional[Side]:
    raw=str(v or "").strip().upper(); return Side(raw) if raw in {"BUY","SELL"} else None
def size_type(v: Any) -> SizeType:
    raw=str(v or "").lower()
    if raw in {"amount","usd","$"}: return SizeType.AMOUNT
    if raw in {"shares","share","qty","quantity"}: return SizeType.SHARES
    return SizeType.NONE
def setup_from(state: Mapping[str, Any]) -> Dict[str, Any]:
    xs=state.get("matched_setups", []); return dict(xs[0]) if isinstance(xs,list) and xs and isinstance(xs[0],dict) else {}
def tx_status(v: Any) -> TxStatus:
    raw=str(v or "").upper()
    if raw in {"SUCCESS","SUCCEEDED","EXECUTED","EXECUTED_CONFIRMED","FILLED","ORDER_FILLED"}: return TxStatus.SUCCESS
    if raw in {"FAILED","FAIL","ERROR","REJECTED","CANCELLED"}: return TxStatus.FAILED
    if raw in {"BLOCKED","INVALIDATED_CANCELLED_CLEAN","REJECTED_MISSING_SIZE","REJECTED_INVALID_APPROVAL_FORMAT","REJECTED_BY_OPERATOR","TIMEOUT_EXPIRED","SKIP_INSUFFICIENT_FUNDS"}: return TxStatus.BLOCKED
    return TxStatus.PENDING
def enum_dict(obj: Any, enum_fields: tuple[str,...]) -> Dict[str, Any]:
    data=asdict(obj)
    for name in enum_fields:
        value=data.get(name)
        if isinstance(value, Enum): data[name]=value.value
    return data
TradeSide=Side; CardAction=Action; TransactionStatus=TxStatus
