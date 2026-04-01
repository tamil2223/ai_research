from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import load_settings
from app.core.state import AgentState, TraceEvent
from app.llm.gemini import generate_text
from app.utils.time import timed


def _extract_snippets(research_data: List[Dict[str, Any]]) -> List[str]:
    snippets: List[str] = []
    for item in research_data:
        if item.get("type") == "rag":
            for doc in item.get("docs", []) or []:
                s = str(doc.get("snippet", "")).strip()
                if s:
                    snippets.append(s)
        if item.get("type") == "tool":
            result = item.get("result", {})
            if isinstance(result, dict):
                for r in result.get("results", []) or []:
                    s = str(r.get("snippet", "")).strip()
                    if s:
                        snippets.append(s)
    return snippets[:5]


async def executor_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        query = state.get("user_query", "")
        snippets = _extract_snippets(state.get("research_data", []) or [])

        settings = load_settings()

        final_output: Dict[str, Any] = {
            "summary": f"Analysis for: {query}",
            "insights": [
                "This is a v1 runnable demo. Insights will improve as real retrieval and models are wired in."
            ],
            "recommendations": ["Add more data into /data and run ingestion; swap mock tool for real web search."],
            "evidence_snippets": snippets,
        }

        if settings.google_api_key and query:
            try:
                prompt = (
                    "Using the evidence snippets below, produce a JSON object with keys:\n"
                    "- summary: string\n"
                    "- insights: array of strings\n"
                    "- recommendations: array of strings\n\n"
                    "Evidence snippets:\n"
                    + "\n".join(f"- {s}" for s in snippets)
                )
                resp = await generate_text(
                    api_key=settings.google_api_key,
                    model=settings.gemini_model,
                    system="You generate structured JSON only. No markdown.",
                    prompt=prompt,
                )
                import json

                parsed = json.loads(resp.text)
                if isinstance(parsed, dict) and "insights" in parsed:
                    parsed["evidence_snippets"] = snippets
                    final_output = parsed
            except Exception:
                pass

        trace_event: TraceEvent = {"node": "executor", "latency_ms": elapsed_ms()}
        state["final_output"] = final_output
        state.setdefault("trace", []).append(trace_event)
        return state

