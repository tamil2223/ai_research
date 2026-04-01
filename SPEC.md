# 🧪 Implementation Spec (v1)

This document turns the architecture in `readme.md` into a **buildable, testable spec**.

## 🎯 MVP Scope (v1)

The system must:

1. Accept a natural language query
2. Execute the full multi-agent pipeline:
   - Planner → Researcher (RAG + tools) → Executor → Critic
3. Return structured output with:
   - Plan
   - Final output (structured)
   - Critique (structured)
   - Sources
4. Persist memory:
   - **Short-term**: Redis (run snapshot / trace)
   - **Long-term**: Vector DB (FAISS local)
5. Log execution trace with a `run_id`

### Single-turn clarity

- v1 is **single-turn**: one request in → one response out.
- `session_id` is **optional** in v1. If provided, it is only used for keying Redis state; **multi-turn conversation behavior is not required** for v1.

---

## ✅ Acceptance Criteria (Definition of Done)

- [ ] `POST /run` returns a valid structured response (see schema below)
- [ ] Planner generates ≥2 meaningful steps
- [ ] Researcher retrieves:
  - [ ] ≥1 RAG document (from `/data` ingestion)
  - [ ] ≥1 tool response (can be a deterministic mock in v1)
- [ ] Executor produces structured output (not a raw text blob)
- [ ] Critic returns a structured evaluation and a retry decision
- [ ] Baseline completes in **<10 seconds** (local small corpus + mock tools)
- [ ] All steps logged with `run_id`
- [ ] Memory written:
  - [ ] Redis snapshot/trace written
  - [ ] Long-term memory written to FAISS
- [ ] Sources included in response

---

## ⚙️ Pinned Defaults (Opinionated Setup)

To avoid ambiguity, v1 uses:

| Component | Default Choice |
| --- | --- |
| LLM | OpenAI (`gpt-4o-mini`) |
| Embeddings | OpenAI embeddings (configurable) |
| Vector DB | FAISS (local) |
| Memory (short) | Redis (local via Docker) |
| Framework | LangGraph |
| Backend | FastAPI |
| Tools | Mock web search (upgrade later to real provider) |

> Everything should be configurable, but defaults should enable **zero-friction local setup**.

---

## 🌐 API Contract (v1)

### POST `/run`

#### Request

```json
{
  "query": "Analyze AI startup trends and suggest opportunities",
  "session_id": "optional-session-id",
  "debug": true
}
```

#### Response

```json
{
  "run_id": "uuid",
  "plan": ["step1", "step2"],
  "final_output": {
    "summary": "string",
    "insights": ["string"],
    "recommendations": ["string"]
  },
  "critique": {
    "verdict": "pass|needs_improvement",
    "reasons": ["string"],
    "should_retry": false
  },
  "sources": [
    {
      "type": "rag",
      "origin": "filename.pdf",
      "snippet": "...",
      "metadata": {}
    },
    {
      "type": "tool",
      "origin": "web_search",
      "snippet": "..."
    }
  ],
  "trace": [
    {
      "node": "planner",
      "latency_ms": 1200
    }
  ],
  "tool_calls": [
    {
      "tool": "web_search",
      "query": "AI trends 2026"
    }
  ],
  "cost": {
    "tokens": 1200,
    "estimated_usd": 0.01
  },
  "latency_ms": 5200
}
```

### GET `/health`

- Returns service health (and optionally dependencies in debug mode).

---

## 🔄 LangGraph State & Transitions

### State schema (v1)

```python
from typing import TypedDict, List, Dict, Any, Optional

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

    retry_count: int
    max_retries: int
```

### Node responsibilities

| Node | Reads | Writes |
| --- | --- | --- |
| Planner | `user_query` | `plan` |
| Researcher | `plan` (+ optional memory retrieval) | `research_data`, `sources`, `tool_calls` |
| Executor | `research_data` | `final_output` |
| Critic | `final_output` | `critique` |
| Memory | `user_query`, `final_output`, `sources`, `trace` | persistence side-effects |

### Retry logic

- Critic can trigger a retry when `critique.should_retry == true` **and** `retry_count < max_retries`.
- Default: `max_retries = 2`
- Retry target (v1): go back to **Researcher** (refresh context) then re-run Executor + Critic.

---

## 🧠 Memory Semantics

### Short-term memory (Redis)

- **Key**: `run:{run_id}` (and optionally `session:{session_id}:latest`)
- **Value**: latest state snapshot + trace metadata
- **TTL**: 1 hour (v1)
- **Used for**:
  - Debugging / trace inspection
  - Optional session grouping (non-required in v1)

### Long-term memory (FAISS / vector DB)

Stored entries (embedded) should include:

- `query`
- `final_output` (serialized)
- `metadata` (timestamp, tags, run_id)

Retrieval:

- Triggered in Researcher
- `top_k = 3`
- Optional similarity threshold

---

## 🔍 RAG Ingestion (v1 Scope)

### Initial data source

- `/data` folder (local documents)

### Chunking strategy

- Chunk size: 500 tokens
- Overlap: 50 tokens

### Metadata (minimum)

```json
{
  "source": "filename.pdf",
  "chunk_id": 1
}
```

### Retrieval behavior

- `top_k = 3`
- Merge RAG + tool results into a single research context for Executor

### Source attribution

Each response must include, per source:

- Source type (`rag` / `tool`)
- Origin (file name / tool name)
- Snippet (short quote or extracted text)

---

## 🐳 Local Setup (Complete)

### Requirements

- Python 3.10+
- Docker (for Redis)

### Run Redis (quick)

```bash
docker run -d -p 6379:6379 redis
```

### `.env.example`

```env
OPENAI_API_KEY=
REDIS_URL=redis://localhost:6379
```

---

## 📊 Observability (v1)

Minimum logging:

- `run_id` per request
- Per node:
  - latency
  - inputs/outputs (debug mode only)

Example log shape:

```json
{
  "run_id": "123",
  "node": "researcher",
  "latency_ms": 1800
}
```

---

## 🔐 Security & Guardrails (v1)

### Input validation

- Max query length
- Reject empty inputs

### Tool safety

- Tool allowlist (v1):
  - `web_search`
  - `rag_retrieval`

### Output guardrails

- Enforce structured response schema
- Prevent hallucinated tool names (must match allowlist)

---

## ❗ Error model (v1)

Define a consistent error response for failures (e.g., tool error, ingestion missing, Redis down). Minimum:

- HTTP status code
- `run_id` (if available)
- `error.code` and `error.message`

---

## 🧪 Minimal test plan (v1)

- **Health**: `GET /health` returns 200
- **Schema smoke**: `POST /run` returns JSON matching required fields (`run_id`, `plan`, `final_output`, `critique`, `sources`)
- **Persistence smoke**: after `/run`, Redis contains `run:{run_id}` and long-term memory store was written

