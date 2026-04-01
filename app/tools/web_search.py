from __future__ import annotations

from typing import Dict, List


async def web_search(query: str) -> Dict[str, object]:
    """
    Deterministic mock web search for v1.
    Replace with a real provider later (SerpAPI, Tavily, etc.).
    """
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

