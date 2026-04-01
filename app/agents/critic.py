from __future__ import annotations

from app.core.config import load_settings
from app.core.state import AgentState, Critique, TraceEvent
from app.llm.gemini import generate_text
from app.utils.time import timed


async def critic_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        final_output = state.get("final_output") or {}

        reasons = []
        should_retry = False

        if not isinstance(final_output, dict) or not final_output.get("insights"):
            reasons.append("Output missing key structured fields.")
            should_retry = True

        settings = load_settings()
        if settings.google_api_key and isinstance(final_output, dict):
            try:
                prompt = (
                    "Evaluate this output for completeness and usefulness.\n"
                    "Return JSON with keys: verdict (pass|needs_improvement), reasons (array), should_retry (bool).\n\n"
                    f"Output JSON:\n{final_output}"
                )
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system="You are a strict reviewer. Return JSON only. No markdown.",
                    prompt=prompt,
                )
                import json

                parsed = json.loads(resp.text)
                if isinstance(parsed, dict) and "should_retry" in parsed:
                    reasons = list(parsed.get("reasons") or [])
                    should_retry = bool(parsed.get("should_retry"))
            except Exception:
                pass

        critique: Critique = {
            "verdict": "needs_improvement" if should_retry else "pass",
            "reasons": reasons,
            "should_retry": should_retry,
        }

        trace_event: TraceEvent = {"node": "critic", "latency_ms": elapsed_ms()}
        state["critique"] = critique
        state.setdefault("trace", []).append(trace_event)
        return state

