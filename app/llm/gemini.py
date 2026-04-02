from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("capstone.llm")


def _extract_response_text(resp: Any) -> str:
    """Gemini SDK sometimes leaves `.text` empty; fall back to candidates/parts."""
    t = getattr(resp, "text", None)
    if t is not None and str(t).strip():
        return str(t)
    chunks: list[str] = []
    for c in getattr(resp, "candidates", None) or []:
        content = getattr(c, "content", None)
        if content is None:
            continue
        for p in getattr(content, "parts", None) or []:
            pt = getattr(p, "text", None)
            if pt:
                chunks.append(str(pt))
    return "".join(chunks)


@dataclass(frozen=True)
class GeminiResult:
    text: str
    usage: Dict[str, Any]


def _try_import_google_genai():
    try:
        from google import genai  # type: ignore

        return genai
    except ImportError:
        return None


async def generate_text(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
) -> GeminiResult:
    """
    Minimal Gemini text generation wrapper.

    Uses the `google-genai` SDK when available. If the SDK isn't installed,
    raises a RuntimeError so callers can fall back gracefully.
    """
    genai = _try_import_google_genai()
    if genai is None:
        raise RuntimeError("google-genai SDK not installed (pip install google-genai)")

    # SDK calls are synchronous and block the thread. Run in a worker thread so the
    # asyncio event loop stays responsive (logs, health checks, concurrent requests).
    def _call() -> GeminiResult:
        client = genai.Client(api_key=api_key)
        contents = prompt if system is None else f"{system}\n\n{prompt}"
        resp = client.models.generate_content(model=model, contents=contents)
        text = _extract_response_text(resp)
        if not text.strip():
            fb = getattr(resp, "prompt_feedback", None)
            logger.warning(
                "Gemini returned empty text model=%r prompt_feedback=%s candidates=%s",
                model,
                fb,
                len(getattr(resp, "candidates", None) or []),
            )
        usage: Dict[str, Any] = {}
        for attr in ("usage_metadata", "usage", "metadata"):
            v = getattr(resp, attr, None)
            if v:
                try:
                    usage = v if isinstance(v, dict) else v.model_dump()  # type: ignore[attr-defined]
                except (TypeError, AttributeError, ValueError):
                    usage = {"raw": str(v)}
                break
        return GeminiResult(text=text, usage=usage)

    timeout_sec = float(os.getenv("GEMINI_REQUEST_TIMEOUT_SEC", "120"))
    logger.info("Gemini generate_content start model=%r timeout_s=%s", model, timeout_sec)
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout_sec)
        logger.info("Gemini generate_content done model=%r text_len=%s", model, len(result.text))
        return result
    except TimeoutError as e:
        logger.error("Gemini generate_content exceeded %.1fs (model=%s)", timeout_sec, model)
        raise RuntimeError(
            f"Gemini request timed out after {timeout_sec:.0f}s; check API key, network, or GEMINI_REQUEST_TIMEOUT_SEC"
        ) from e

