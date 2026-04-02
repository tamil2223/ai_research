from __future__ import annotations

import logging
from typing import Optional

from app.core.state import AgentState

LOG = logging.getLogger("capstone.workflow")


def run_id(state: AgentState) -> str:
    return str(state.get("run_id", "?"))


def node_begin(node: str, state: AgentState, *, detail: Optional[str] = None) -> None:
    parts = [
        f"node={node}",
        f"run_id={run_id(state)}",
        f"retry={state.get('retry_count', 0)}",
    ]
    if detail:
        parts.append(detail)
    LOG.info("BEGIN %s", " ".join(parts))


def node_end(node: str, state: AgentState, elapsed_ms: int, *, detail: Optional[str] = None) -> None:
    parts = [
        f"node={node}",
        f"run_id={run_id(state)}",
        f"elapsed_ms={elapsed_ms}",
    ]
    if detail:
        parts.append(detail)
    LOG.info("END %s", " ".join(parts))


def graph_decision(detail: str, state: AgentState) -> None:
    LOG.info("GRAPH run_id=%s %s", run_id(state), detail)
