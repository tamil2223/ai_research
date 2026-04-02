from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from app.agents.critic import critic_node
from app.agents.executor import executor_node
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.core.config import load_settings
from app.core.state import AgentState
from pathlib import Path

from app.memory.file_store import write_run_snapshot_file
from app.memory.redis_store import write_run_snapshot
from app.utils.ids import new_run_id
from app.utils.run_log import graph_decision
from app.utils.time import timed

_LOG = logging.getLogger("capstone.workflow")


def _should_retry(state: AgentState) -> str:
    # LangGraph does not merge state mutations from conditional edge callbacks—only
    # node return values update state. Retry accounting is done in critic_node.
    critique = state.get("critique") or {}
    should_retry = bool(critique.get("should_retry"))
    max_retries = int(state.get("max_retries") or 2)

    if should_retry:
        graph_decision(
            f"critic -> RETRY researcher (retry_count={state.get('retry_count', 0)}/{max_retries})",
            state,
        )
        return "retry"
    graph_decision(
        f"critic -> END (verdict={critique.get('verdict')!r} should_retry={should_retry})",
        state,
    )
    return "done"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "executor")
    graph.add_edge("executor", "critic")

    graph.add_conditional_edges(
        "critic",
        _should_retry,
        {"retry": "researcher", "done": END},
    )
    return graph.compile()


_APP = build_graph()


async def run_workflow(query: str, session_id: Optional[str], debug: bool) -> Dict[str, Any]:
    with timed() as elapsed_ms:
        settings = load_settings()
        capstone_root = Path(__file__).resolve().parents[2]
        state: AgentState = {
            "run_id": new_run_id(),
            "session_id": session_id,
            "user_query": query,
            "max_retries": 2,
            "retry_count": 0,
            "trace": [],
            "tool_calls": [],
            "sources": [],
        }

        _LOG.info(
            "LangGraph.ainvoke START run_id=%s query_len=%s session_id=%s debug=%s",
            state["run_id"],
            len(query),
            session_id or "-",
            debug,
        )
        final_state = await _APP.ainvoke(state)  # type: ignore[attr-defined]
        final_state["latency_ms"] = elapsed_ms()
        _LOG.info(
            "LangGraph.ainvoke END run_id=%s workflow_elapsed_ms=%s trace_nodes=%s",
            final_state.get("run_id"),
            final_state["latency_ms"],
            [t.get("node") for t in (final_state.get("trace") or [])],
        )

        # v1: placeholders; will be computed from provider later
        final_state.setdefault("cost", {"tokens": 0, "estimated_usd": 0.0})

        # In debug=false, we still return trace by spec; only detail fields should be suppressed by nodes.
        _ = debug

        snapshot = dict(final_state)
        rid = str(final_state.get("run_id"))

        # Local file first so a slow/broken Redis never blocks returning /run to the client.
        snap_path = write_run_snapshot_file(
            capstone_root=capstone_root,
            run_id=rid,
            snapshot=snapshot,
        )
        _LOG.info("File snapshot %s", snap_path)

        async def _redis_best_effort() -> None:
            def _write() -> None:
                write_run_snapshot(
                    redis_url=settings.redis_url,
                    run_id=rid,
                    snapshot=snapshot,
                    ttl_seconds=3600,
                    session_id=session_id,
                )

            await asyncio.wait_for(asyncio.to_thread(_write), timeout=5.0)

        try:
            await _redis_best_effort()
            _LOG.info("Redis snapshot written run_id=%s", rid)
        except asyncio.TimeoutError:
            _LOG.warning("Redis snapshot timed out (5s) run_id=%s — response still returned", rid)
        except Exception as e:
            _LOG.warning("Redis snapshot skipped run_id=%s err=%s", rid, e)

        return snapshot

