from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class Critique(TypedDict):
    verdict: str  # "pass" | "needs_improvement"
    reasons: List[str]
    should_retry: bool


class Source(TypedDict, total=False):
    type: str  # "rag" | "tool"
    origin: str
    snippet: str
    metadata: Dict[str, Any]


class ToolCall(TypedDict):
    tool: str
    query: str


class TraceEvent(TypedDict, total=False):
    node: str
    latency_ms: int
    detail: Dict[str, Any]


class CostInfo(TypedDict, total=False):
    tokens: int
    estimated_usd: float


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: Optional[str]
    user_query: str

    plan: List[str]
    research_data: List[Dict[str, Any]]

    final_output: Dict[str, Any]
    critique: Critique

    sources: List[Source]
    tool_calls: List[ToolCall]
    trace: List[TraceEvent]

    cost: CostInfo
    latency_ms: int

    retry_count: int
    max_retries: int

    # Raw Gemini usage_metadata dicts; aggregated into cost before API response.
    llm_usage_events: List[Dict[str, Any]]

