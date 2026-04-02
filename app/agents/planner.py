from __future__ import annotations

import logging

from app.core.state import AgentState, TraceEvent
from app.core.config import load_settings
from app.llm.gemini import generate_text
from app.utils.run_log import node_begin, node_end
from app.utils.time import timed

_LOG = logging.getLogger("capstone.agents")


async def planner_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        query = (state.get("user_query") or "").strip()
        settings = load_settings()
        use_llm = bool(settings.google_api_key and query)
        node_begin("planner", state, detail=f"gemini={use_llm} model={settings.gemini_model!r}")

        plan = [
            "Clarify the objective and constraints",
            "Collect relevant evidence (RAG + tools)",
            "Synthesize insights and recommendations",
        ]

        # If Gemini is configured, ask it for a short step list.
        if settings.google_api_key and query:
            try:
                _LOG.info("planner: calling Gemini for plan run_id=%s", state.get("run_id"))
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system="You are a concise planning assistant. Return 3-5 bullet steps only.",
                    prompt=f"User query:\n{query}\n\nReturn steps as plain lines (no numbering).",
                )
                lines = [ln.strip("-• \t") for ln in resp.text.splitlines() if ln.strip()]
                plan = [ln for ln in lines if ln][:5] or plan
                _LOG.info("planner: Gemini OK plan_steps=%s run_id=%s", len(plan), state.get("run_id"))
            except Exception as e:
                _LOG.warning("planner: Gemini failed, using defaults run_id=%s err=%s", state.get("run_id"), e)

        trace_event: TraceEvent = {"node": "planner", "latency_ms": elapsed_ms()}
        state["plan"] = plan
        state.setdefault("trace", []).append(trace_event)
        node_end("planner", state, trace_event["latency_ms"], detail=f"plan_steps={len(plan)}")
        return state

