import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from automation.nodes.patterns.models import runtime_env


class MCPDispatchError(RuntimeError):
    pass


class MCPDispatcher:
    """
    MCP request dispatcher used by cowork_scheduler.

    Dispatch order:
    1. Built-in Alpha Vantage REST adapter for OHLCV if ALPHA_VANTAGE_API_KEY is available.
    2. Subprocess bridge via MCP_DISPATCH_COMMAND.
    3. Queue request to logs/mcp_request_queue.jsonl and return MCP_DISPATCH_REQUIRED.

    This class never fabricates account, market, or broker responses.
    """

    def __init__(self):
        self.dispatch_command = runtime_env("MCP_DISPATCH_COMMAND")
        self.alpha_vantage_key = (
            runtime_env("ALPHA_VANTAGE_API_KEY")
            or runtime_env("ALPHAVANTAGE_API_KEY")
            or runtime_env("AV_API_KEY")
        )
        self.queue_path = Path(runtime_env("MCP_REQUEST_QUEUE_PATH", "logs/mcp_request_queue.jsonl") or "logs/mcp_request_queue.jsonl")
        self.alpha_sleep_seconds = float(runtime_env("ALPHA_VANTAGE_SLEEP_SECONDS", "12") or "12")

    def dispatch_many(self, requests: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not requests:
            return {}

        combined: Dict[str, Any] = {
            "mcp_dispatches": [],
        }

        for request in requests:
            result = self.dispatch_one(request, state=state or {})
            combined["mcp_dispatches"].append({"request": request, "result": result})

            for key in ("market_data", "account_telemetry", "broker_confirmation"):
                if key in result:
                    if key == "market_data":
                        combined.setdefault("market_data", {}).update(result["market_data"])
                    else:
                        combined[key] = result[key]

            if "execution_status" in result and key not in combined:
                combined["execution_status"] = result["execution_status"]

        if "market_data" in combined:
            combined["execution_status"] = "MARKET_DATA_PRESENT"

        if "account_telemetry" in combined:
            # Position sizing/capital gate will consume this and continue.
            combined["execution_status"] = "ACCOUNT_TELEMETRY_PRESENT"

        if "broker_confirmation" in combined:
            combined["execution_status"] = "BROKER_CONFIRMATION_RECEIVED"

        return combined

    def dispatch_one(self, request: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        action = request.get("action")

        if action in {"fetch_historical_ohlcv_batch", "fetch_fresh_ohlcv_for_approved_ticker"}:
            if self.alpha_vantage_key:
                return self._dispatch_alpha_vantage_ohlcv(request)

        if self.dispatch_command:
            return self._dispatch_subprocess(request, state)

        self._queue_request(request, state)
        return {
            "execution_status": "MCP_DISPATCH_REQUIRED",
            "queued": True,
            "queue_path": str(self.queue_path),
        }

    def _dispatch_subprocess(self, request: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"request": request, "state": state}
        cmd = shlex.split(self.dispatch_command or "")

        if not cmd:
            raise MCPDispatchError("MCP_DISPATCH_COMMAND is empty.")

        completed = subprocess.run(
            cmd,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=int(runtime_env("MCP_DISPATCH_TIMEOUT_SECONDS", "120") or "120"),
            check=False,
        )

        if completed.returncode != 0:
            raise MCPDispatchError(
                f"MCP dispatch command failed with code {completed.returncode}: {completed.stderr}"
            )

        stdout = completed.stdout.strip()
        if not stdout:
            return {"execution_status": "MCP_DISPATCH_EMPTY_RESPONSE"}

        try:
            result = json.loads(stdout)
        except Exception as exc:
            raise MCPDispatchError(f"MCP dispatch command returned non-JSON: {stdout[:500]}") from exc

        if not isinstance(result, dict):
            raise MCPDispatchError("MCP dispatch command must return a JSON object.")

        return result

    def _queue_request(self, request: Dict[str, Any], state: Dict[str, Any]) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "request": request,
            "state_keys": sorted(list(state.keys())),
        }
        with self.queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def _dispatch_alpha_vantage_ohlcv(self, request: Dict[str, Any]) -> Dict[str, Any]:
        tickers = request.get("tickers")
        if not tickers and request.get("ticker"):
            tickers = [request["ticker"]]

        if not isinstance(tickers, list) or not tickers:
            return {"market_data": {}, "execution_status": "NO_TICKERS"}

        market_data: Dict[str, Any] = {}

        for idx, ticker in enumerate(tickers):
            candles = self._fetch_alpha_vantage_daily(str(ticker))
            market_data[str(ticker).upper()] = {"candles": candles}

            # Alpha Vantage free tiers are rate limited; sleep between batch calls unless disabled.
            if idx < len(tickers) - 1 and self.alpha_sleep_seconds > 0:
                time.sleep(self.alpha_sleep_seconds)

        return {
            "market_data": market_data,
            "execution_status": "MARKET_DATA_PRESENT",
        }

    def _fetch_alpha_vantage_daily(self, ticker: str) -> List[Dict[str, Any]]:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": self.alpha_vantage_key,
        }
        url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode(params)

        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MCPDispatchError(f"Alpha Vantage HTTP {exc.code}: {body}") from exc

        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise MCPDispatchError(f"Alpha Vantage response missing daily series for {ticker}: {payload}")

        candles: List[Dict[str, Any]] = []
        for date_str, row in sorted(series.items()):
            candles.append(
                {
                    "timestamp": date_str,
                    "open": row.get("1. open"),
                    "high": row.get("2. high"),
                    "low": row.get("3. low"),
                    "close": row.get("4. close"),
                    "volume": row.get("5. volume"),
                }
            )

        return candles
