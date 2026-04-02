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
        final_output = state.get("final_output") or {}
        settings = load_settings()
        node_begin("critic", state, detail=f"gemini={bool(settings.google_api_key and isinstance(final_output, dict))}")

        reasons = []
        should_retry = False

        # Heuristic retry guard when Gemini is disabled/unavailable:
        # only retry if we don't have the minimal structured output that the UI expects.
        if (
            not isinstance(final_output, dict)
            or not isinstance(final_output.get("insights"), list)
            or not isinstance(final_output.get("recommendations"), list)
            or not isinstance(final_output.get("summary"), str)
        ):
            reasons.append("Output missing key structured fields.")
            should_retry = True

        if settings.google_api_key and isinstance(final_output, dict):
            try:
                _LOG.info("critic: calling Gemini run_id=%s", state.get("run_id"))
                prompt = (
                    "Evaluate this output for completeness and usefulness.\n"
                    "Return JSON with keys: verdict (pass|needs_improvement), reasons (array), should_retry (bool).\n\n"
                    f"Output JSON:\n{final_output}"
                )
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system=(
                        "Return ONLY a single JSON object with keys: "
                        "verdict (string: pass or needs_improvement), reasons (array of strings), "
                        "should_retry (boolean). No markdown, no code fences, no other text."
                    ),
                    prompt=prompt,
                )
                parsed = parse_json_from_llm(resp.text)
                if isinstance(parsed, dict) and "should_retry" in parsed:
                    reasons = list(parsed.get("reasons") or [])
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
            "verdict": "needs_improvement" if should_retry else "pass",
            "reasons": reasons,
            "should_retry": should_retry,
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
            detail=f"verdict={critique['verdict']} should_retry={critique['should_retry']}",
        )
        return state

