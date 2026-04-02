from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    session_id: Optional[str] = None
    debug: bool = False


class SourceModel(BaseModel):
    type: Literal["rag", "tool"]
    origin: str
    snippet: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TraceEventModel(BaseModel):
    node: str
    latency_ms: int
    detail: Dict[str, Any] = Field(default_factory=dict)


class ToolCallModel(BaseModel):
    tool: str
    query: str


class CostModel(BaseModel):
    """Aggregated Gemini usage for the run (all agents + topic diagram)."""

    tokens: int = 0
    estimated_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class CritiqueModel(BaseModel):
    should_retry: bool = False
    feedback: str = ""


class RunResponse(BaseModel):
    run_id: str
    plan: List[str]
    final_output: str
    critique: CritiqueModel
    sources: List[SourceModel] = Field(default_factory=list)
    trace: List[TraceEventModel] = Field(default_factory=list)
    tool_calls: List[ToolCallModel] = Field(default_factory=list)
    cost: CostModel = Field(default_factory=CostModel)
    latency_ms: int
    # Mermaid source: diagram about the *user's topic* (plan, research, execution path), not the agent stack
    topic_diagram_mermaid: str = ""

