"""Thin runtime entrypoint.

The canonical graph topology lives in automation.graph_orchestrator.
This file intentionally does not define a second LangGraph topology.
"""

from automation.graph import app

__all__ = ["app"]


def run(initial_state: dict | None = None, config: dict | None = None):
    """Run the compiled graph with an optional initial state."""
    initial_state = initial_state or {}
    return app.invoke(initial_state, config=config)


if __name__ == "__main__":
    result = run({})
    print(result)
