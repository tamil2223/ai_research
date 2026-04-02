from __future__ import annotations

import os
from typing import Any, Dict, List, MutableMapping, Optional, Tuple

def append_usage(state: MutableMapping[str, Any], usage: Optional[Dict[str, Any]]) -> None:
    """Accumulate Gemini usage dicts on state for end-of-run cost aggregation."""
    if not usage:
        return
    clean = _flatten_usage(usage)
    if clean:
        state.setdefault("llm_usage_events", []).append(clean)


def _flatten_usage(u: Any) -> Dict[str, Any]:
    if u is None:
        return {}
    if hasattr(u, "model_dump"):
        try:
            u = u.model_dump()
        except (TypeError, AttributeError, ValueError):
            return {}
    if not isinstance(u, dict):
        return {}
    return dict(u)


def counts_from_usage(u: Dict[str, Any]) -> Tuple[int, int, int]:
    """
    Return (prompt_tokens, completion_tokens, total_tokens).
    Handles google-genai usage_metadata shape and a few aliases.
    """
    u = _flatten_usage(u)
    prompt = int(
        u.get("prompt_token_count")
        or u.get("prompt_tokens")
        or u.get("input_tokens")
        or 0
    )
    completion = int(
        u.get("candidates_token_count")
        or u.get("candidates_tokens")
        or u.get("completion_tokens")
        or u.get("output_tokens")
        or 0
    )
    total = int(u.get("total_token_count") or u.get("total_tokens") or 0)
    if total <= 0 and (prompt or completion):
        total = prompt + completion
    if prompt == 0 and completion == 0 and total > 0:
        # No breakdown: treat as total only
        return 0, 0, total
    return prompt, completion, total


def aggregate_cost(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build cost dict for API response from accumulated usage events."""
    pt = ct = tt = 0
    for e in events:
        p, c, t = counts_from_usage(e)
        pt += p
        ct += c
        if t > 0:
            tt += t
        else:
            tt += p + c
    if tt == 0:
        tt = pt + ct
    usd = _estimate_usd(pt, ct, tt)
    return {
        "tokens": tt,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "estimated_usd": round(usd, 6),
    }


def _estimate_usd(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> float:
    pin = float(os.getenv("GEMINI_PRICE_INPUT_PER_1M_USD", "0.10"))
    pout = float(os.getenv("GEMINI_PRICE_OUTPUT_PER_1M_USD", "0.40"))
    blended = float(os.getenv("GEMINI_PRICE_PER_1M_USD", "0.0"))
    if prompt_tokens or completion_tokens:
        return (prompt_tokens / 1_000_000.0) * pin + (completion_tokens / 1_000_000.0) * pout
    if blended > 0 and total_tokens > 0:
        return (total_tokens / 1_000_000.0) * blended
    # Default Flash-ish blend if only total known
    if total_tokens > 0:
        return (total_tokens / 1_000_000.0) * 0.25
    return 0.0
