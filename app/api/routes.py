from __future__ import annotations

import logging

from fastapi import APIRouter

from app.graph.workflow import run_workflow
from app.models.schemas import RunRequest, RunResponse

router = APIRouter()
LOG = logging.getLogger("capstone.api")


def _preview(text: str, max_len: int = 120) -> str:
    t = text.replace("\n", " ").strip()
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/run", response_model=RunResponse)
async def run(req: RunRequest) -> RunResponse:
    LOG.info(
        "/run request query_len=%s session_id=%s debug=%s query_preview=%r",
        len(req.query),
        req.session_id or "-",
        req.debug,
        _preview(req.query),
    )
    result = await run_workflow(query=req.query, session_id=req.session_id, debug=req.debug)
    rid = result.get("run_id", "?")
    LOG.info(
        "/run response run_id=%s latency_ms=%s plan_steps=%s sources=%s critique=%s",
        rid,
        result.get("latency_ms"),
        len(result.get("plan") or []),
        len(result.get("sources") or []),
        (result.get("critique") or {}).get("verdict"),
    )
    return RunResponse.model_validate(result)

