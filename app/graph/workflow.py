from __future__ import annotations

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
from app.utils.time import timed


def _should_retry(state: AgentState) -> str:
    critique = state.get("critique") or {}
    retry_count = int(state.get("retry_count") or 0)
    max_retries = int(state.get("max_retries") or 2)
    should_retry = bool(critique.get("should_retry"))

    if should_retry and retry_count < max_retries:
        state["retry_count"] = retry_count + 1
        return "retry"
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

        final_state = await _APP.ainvoke(state)  # type: ignore[attr-defined]
        final_state["latency_ms"] = elapsed_ms()

        # v1: placeholders; will be computed from provider later
        final_state.setdefault("cost", {"tokens": 0, "estimated_usd": 0.0})

        # In debug=false, we still return trace by spec; only detail fields should be suppressed by nodes.
        _ = debug

        # Persist short-term snapshot to Redis (best-effort)
        try:
            write_run_snapshot(
                redis_url=settings.redis_url,
                run_id=str(final_state.get("run_id")),
                snapshot=dict(final_state),
                ttl_seconds=3600,
                session_id=session_id,
            )
        except Exception:
            # v1: don't fail request due to Redis issues
            pass

        # Always persist a local snapshot file for the demo
        write_run_snapshot_file(
            capstone_root=capstone_root,
            run_id=str(final_state.get("run_id")),
            snapshot=dict(final_state),
        )

        return dict(final_state)

