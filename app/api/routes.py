from __future__ import annotations

from fastapi import APIRouter

from app.graph.workflow import run_workflow
from app.models.schemas import RunRequest, RunResponse

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/run", response_model=RunResponse)
async def run(req: RunRequest) -> RunResponse:
    result = await run_workflow(query=req.query, session_id=req.session_id, debug=req.debug)
    return RunResponse.model_validate(result)

