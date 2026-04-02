from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

# Load .env before reading LOG_LEVEL / CORS / API keys (matches how you run from capstone/)
load_dotenv()

from app.api.routes import router as api_router

logger = logging.getLogger("capstone.api")

_CAPSTONE_LOGGERS = (
    "capstone",
    "capstone.api",
    "capstone.workflow",
    "capstone.agents",
    "capstone.llm",
)


def _configure_capstone_logging() -> None:
    """
    Uvicorn often leaves the root logger at WARNING. Our INFO lines would then
    never print (child loggers propagate, then root drops INFO). Attach one
    stderr StreamHandler on `capstone` and do not propagate to root.
    """
    lvl_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, lvl_name, logging.INFO)
    cap = logging.getLogger("capstone")
    cap.setLevel(level)
    for name in _CAPSTONE_LOGGERS:
        logging.getLogger(name).setLevel(level)
    if not cap.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(level)
        h.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        cap.addHandler(h)
    cap.propagate = False


_configure_capstone_logging()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logging.getLogger("capstone").info(
        "startup LOG_LEVEL=%s (capstone logs -> stderr)",
        os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    yield


app = FastAPI(
    title="Capstone Multi-Agent System",
    version="0.1.0",
    lifespan=_lifespan,
)

# CORS: browsers send OPTIONS preflight before POST /run. If Origin doesn't match
# allow_origins, or credentials + header wildcards trip the browser, the preflight
# can fall through and FastAPI returns 405 for OPTIONS.
#
# Default: any loopback origin on any port (Next on localhost:3000 + API on
# 127.0.0.1:8000 is still cross-origin; browsers need ACAO on OPTIONS *and* POST).
# Echoing Origin via regex is more reliable than "*" for some browsers (e.g. Edge)
# when Origin is http://localhost:3000 but the API is http://127.0.0.1:8000.
#
# Strict mode: CORS_ALLOW_ALL=0 and set CORS_ORIGINS to a comma-separated list.
_allow_all = os.getenv("CORS_ALLOW_ALL", "1").strip() not in ("0", "false", "no")
if _allow_all:
    _origins: list[str] = []
    _credentials = False
    _origin_regex = (
        r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"  # dev: any port on loopback
    )
else:
    _raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://[::1]:3000",
    )
    _origins = [o.strip() for o in _raw.split(",") if o.strip()]
    _credentials = True
    _origin_regex = ""

# How long (seconds) the browser may cache a successful OPTIONS preflight without
# re-requesting it. Default 600 (Starlette default). Set CORS_PREFLIGHT_MAX_AGE=0
# in .env when debugging CORS so you see OPTIONS in DevTools every time.
_preflight_max_age = int(os.getenv("CORS_PREFLIGHT_MAX_AGE", "600"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=_origin_regex or None,
    allow_credentials=_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
    max_age=_preflight_max_age,
)


@app.middleware("http")
async def log_long_requests(request: Request, call_next):
    """
    Uvicorn's default access log line is emitted when the response is done, so a
    slow POST /run (e.g. Gemini) looks like 'no POST log' while the client waits.
    This logs start + elapsed time so you can see the request immediately.
    """
    if request.method == "POST" and request.url.path.rstrip("/") == "/run":
        t0 = time.perf_counter()
        peer = request.client.host if request.client else "?"
        logger.info("POST /run START client=%s", peer)
        try:
            response = await call_next(request)
            logger.info(
                "POST /run DONE status=%s elapsed_s=%.2f",
                response.status_code,
                time.perf_counter() - t0,
            )
            return response
        except Exception:
            logger.exception(
                "POST /run ERROR elapsed_s=%.2f",
                time.perf_counter() - t0,
            )
            raise
    return await call_next(request)


app.include_router(api_router)

