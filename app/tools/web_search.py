from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Dict, List

import httpx

LOG = logging.getLogger("capstone.web_search")

_INT_RE = re.compile(r"-?\d+")


def _parse_env_int(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """
    Parse integers from env vars safely.
    Supports values like `3 (recommended)` by extracting the first integer token.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    m = _INT_RE.search(str(raw))
    if not m:
        return default
    val = int(m.group(0))
    if min_value is not None:
        val = max(min_value, val)
    if max_value is not None:
        val = min(max_value, val)
    return val


def _parse_env_float(
    name: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """
    Parse floats from env vars safely (also tolerates inline comments).
    Extracts the first float/int token.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    m = re.search(r"-?\d+(?:\.\d+)?", str(raw))
    if not m:
        return default
    val = float(m.group(0))
    if min_value is not None:
        val = max(min_value, val)
    if max_value is not None:
        val = min(max_value, val)
    return val


def _mock_search_result(query: str) -> Dict[str, object]:
    q = (query or "").strip()
    results: List[Dict[str, str]] = []
    if q:
        results = [
            {
                "title": "Mock result: AI trends overview",
                "url": "https://example.com/ai-trends",
                "snippet": f"Mock snippet for query: {q}",
            }
        ]
    return {"provider": "mock", "query": q, "results": results}


async def web_search(query: str) -> Dict[str, object]:
    """
    Web search tool for v1.

    - Default: deterministic mock so local demo never breaks.
    - Feature-flag: when `WEB_SEARCH_PROVIDER=tavily` and `TAVILY_API_KEY`
      are configured, use Tavily Search REST API.
    """
    q = (query or "").strip()
    provider = os.getenv("WEB_SEARCH_PROVIDER", "mock").strip().lower()

    if provider != "tavily":
        return _mock_search_result(q)

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        LOG.warning("Tavily provider selected but TAVILY_API_KEY is missing; using mock")
        return _mock_search_result(q)

    timeout_sec = _parse_env_float("WEB_SEARCH_TIMEOUT_SEC", 8.0, min_value=0.1, max_value=60.0)
    retries = _parse_env_int("WEB_SEARCH_RETRIES", 2, min_value=0, max_value=5)
    max_results = _parse_env_int("WEB_SEARCH_MAX_RESULTS", 3, min_value=0, max_value=20)

    url = "https://api.tavily.com/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "query": q,
        "max_results": max(0, min(max_results, 20)),
        "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        "include_answer": False,
        "include_raw_content": False,
    }

    async def _call_once() -> Dict[str, object]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            follow_redirects=True,
        ) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        items = []
        for item in (data.get("results") or [])[:max_results]:
            items.append(
                {
                    "title": str(item.get("title", ""))[:200],
                    "url": str(item.get("url", "")),
                    # Tavily uses `content` for the snippet in the response schema.
                    "snippet": str(item.get("content") or item.get("snippet") or item.get("raw_content") or "")[
                        :1000
                    ],
                }
            )
        return {"provider": "tavily", "query": q, "results": items}

    LOG.info(
        "web_search start provider=tavily q_len=%s max_results=%s timeout_s=%s retries=%s",
        len(q),
        max_results,
        timeout_sec,
        retries,
    )

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if not q:
                return {"provider": "tavily", "query": q, "results": []}
            return await _call_once()
        except (httpx.HTTPError, asyncio.TimeoutError, ValueError) as e:  # pragma: no cover
            last_err = e
            wait_s = min(2.0 ** attempt, 5.0)
            LOG.warning("web_search tavily failed attempt=%s err=%s; retrying in %.1fs", attempt, e, wait_s)
            await asyncio.sleep(wait_s)

    LOG.warning("web_search tavily giving up; using mock err=%s", last_err)
    return _mock_search_result(q)

