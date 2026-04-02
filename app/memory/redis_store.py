from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


def _redis_client(redis_url: str) -> redis.Redis:
    if redis is None:
        raise RuntimeError("redis package is not installed")
    # Avoid hanging the ASGI event loop when Redis is down or misaddressed.
    return redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )


def write_run_snapshot(
    *,
    redis_url: str,
    run_id: str,
    snapshot: Dict[str, Any],
    ttl_seconds: int = 3600,
    session_id: Optional[str] = None,
) -> None:
    r = _redis_client(redis_url)
    key = f"run:{run_id}"
    r.set(key, json.dumps(snapshot, ensure_ascii=False, default=str), ex=ttl_seconds)

    if session_id:
        r.set(f"session:{session_id}:latest", key, ex=ttl_seconds)

