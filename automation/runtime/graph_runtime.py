from typing import Any, Dict, Optional


class GraphRuntime:
    """Small LangGraph resume helper that keeps one checkpoint thread_id."""

    def __init__(self, app: Any, thread_id: str):
        self.app = app
        self.thread_id = thread_id
        self.config = {"configurable": {"thread_id": thread_id}}
        self.last_state: Dict[str, Any] = {}

    def invoke(self, update: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        update = update or {}
        result = self.app.invoke(update, config=self.config)
        if isinstance(result, dict):
            self.last_state = result
            return result

        values = self.get_state()
        self.last_state = values
        return values

    def resume(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resume from the existing checkpoint.

        Uses update_state when available, then invokes with empty input.
        Falls back to invoking the merged update directly.
        """
        if hasattr(self.app, "update_state"):
            self.app.update_state(self.config, update)
            try:
                result = self.app.invoke(None, config=self.config)
            except Exception:
                result = self.app.invoke({}, config=self.config)

            if isinstance(result, dict):
                self.last_state = result
                return result

            values = self.get_state()
            self.last_state = values
            return values

        merged = dict(self.last_state)
        merged.update(update)
        return self.invoke(merged)

    def get_state(self) -> Dict[str, Any]:
        if not hasattr(self.app, "get_state"):
            return dict(self.last_state)

        snapshot = self.app.get_state(self.config)
        values = getattr(snapshot, "values", None)

        if isinstance(values, dict):
            return values

        if isinstance(snapshot, dict):
            return snapshot

        return dict(self.last_state)
