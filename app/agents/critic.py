from __future__ import annotations

import logging

from app.core.config import load_settings
from app.core.state import AgentState, Critique, TraceEvent
from app.llm.gemini import generate_text
from app.utils.json_llm import parse_json_from_llm
from app.utils.llm_usage import append_usage
from app.utils.run_log import node_begin, node_end
from app.utils.time import timed

_LOG = logging.getLogger("capstone.agents")


async def critic_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        final_output_text = str(state.get("final_output") or "")
        structured = state.get("final_output_structured") or {}
        settings = load_settings()
        node_begin(
            "critic",
            state,
            detail=f"gemini={bool(settings.google_api_key and isinstance(structured, dict) and structured)}",
        )

        should_retry = False
        feedback = ""

        # Heuristic retry guard when Gemini is disabled/unavailable.
        if not final_output_text.strip():
            should_retry = True
            feedback = "Output is empty; retry recommended."

        if settings.google_api_key and isinstance(structured, dict) and structured:
            try:
                _LOG.info("critic: calling Gemini run_id=%s", state.get("run_id"))
                prompt = (
                    "Evaluate this output for completeness and usefulness.\n"
                    "Return JSON with keys: feedback (string), should_retry (bool).\n\n"
                    f"Output:\n{structured}"
                )
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system=(
                        "Return ONLY a single JSON object with keys: "
                        "feedback (string) and should_retry (boolean). "
                        "No markdown, no code fences, no other text."
                    ),
                    prompt=prompt,
                )
                parsed = parse_json_from_llm(resp.text)
                if isinstance(parsed, dict) and "should_retry" in parsed:
                    feedback = str(parsed.get("feedback") or "").strip()
                    should_retry = bool(parsed.get("should_retry"))
                    append_usage(state, resp.usage)
                    _LOG.info(
                        "critic: Gemini OK run_id=%s should_retry=%s",
                        state.get("run_id"),
                        should_retry,
                    )
            except (RuntimeError, ValueError, TypeError) as e:
                _LOG.warning("critic: Gemini failed, heuristic only run_id=%s err=%s", state.get("run_id"), e)

        critique: Critique = {
            "should_retry": should_retry,
            "feedback": feedback or ("Looks good." if not should_retry else "Needs improvement."),
        }

        rc = int(state.get("retry_count") or 0)
        max_r = int(state.get("max_retries") or 2)
        if critique["should_retry"] and rc >= max_r:
            critique = {
                "verdict": "needs_improvement",
                "reasons": list(critique["reasons"])
                + ["Max retries reached; returning best effort."],
                "should_retry": False,
            }
        elif critique["should_retry"]:
            state["retry_count"] = rc + 1

        trace_event: TraceEvent = {"node": "critic", "latency_ms": elapsed_ms()}
        state["critique"] = critique
        state.setdefault("trace", []).append(trace_event)
        node_end(
            "critic",
            state,
            trace_event["latency_ms"],
            detail=f"should_retry={critique['should_retry']}",
        )
        return state

