from __future__ import annotations

from app.core.state import AgentState, TraceEvent
from app.core.config import load_settings
from app.llm.gemini import generate_text
from app.utils.time import timed


async def planner_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        query = (state.get("user_query") or "").strip()
        settings = load_settings()

        plan = [
            "Clarify the objective and constraints",
            "Collect relevant evidence (RAG + tools)",
            "Synthesize insights and recommendations",
        ]

        # If Gemini is configured, ask it for a short step list.
        if settings.google_api_key and query:
            try:
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system="You are a concise planning assistant. Return 3-5 bullet steps only.",
                    prompt=f"User query:\n{query}\n\nReturn steps as plain lines (no numbering).",
                )
                lines = [ln.strip("-• \t") for ln in resp.text.splitlines() if ln.strip()]
                plan = [ln for ln in lines if ln][:5] or plan
            except Exception:
                pass

        trace_event: TraceEvent = {"node": "planner", "latency_ms": elapsed_ms()}
        state["plan"] = plan
        state.setdefault("trace", []).append(trace_event)
        return state

