from __future__ import annotations

from typing import Any, Dict, List

from app.core.state import AgentState, Source, ToolCall, TraceEvent
from app.rag.retrieve import rag_retrieve
from app.tools.web_search import web_search
from app.utils.time import timed


async def researcher_node(state: AgentState) -> AgentState:
    with timed() as elapsed_ms:
        query = state.get("user_query", "")

        sources: List[Source] = []
        tool_calls: List[ToolCall] = []
        research_data: List[Dict[str, Any]] = []

        # RAG retrieval (v1 will be backed by FAISS later)
        rag_docs = await rag_retrieve(query=query, top_k=3)
        for doc in rag_docs:
            sources.append(
                {
                    "type": "rag",
                    "origin": str(doc.get("origin", "data")),
                    "snippet": str(doc.get("snippet", ""))[:1000],
                    "metadata": dict(doc.get("metadata", {}) or {}),
                }
            )
        if rag_docs:
            research_data.append({"type": "rag", "docs": rag_docs})

        # Tool call: web_search (mock)
        tool_calls.append({"tool": "web_search", "query": query})
        tool_result = await web_search(query=query)
        results = tool_result.get("results", []) if isinstance(tool_result, dict) else []
        if results:
            first = results[0]
            sources.append(
                {
                    "type": "tool",
                    "origin": "web_search",
                    "snippet": str(first.get("snippet", ""))[:1000],
                    "metadata": {"url": first.get("url"), "title": first.get("title")},
                }
            )
        research_data.append({"type": "tool", "name": "web_search", "result": tool_result})

        trace_event: TraceEvent = {"node": "researcher", "latency_ms": elapsed_ms()}

        state.setdefault("sources", []).extend(sources)
        state.setdefault("tool_calls", []).extend(tool_calls)
        state["research_data"] = research_data
        state.setdefault("trace", []).append(trace_event)
        return state

