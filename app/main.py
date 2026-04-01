from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="Capstone Multi-Agent System", version="0.1.0")
app.include_router(api_router)

