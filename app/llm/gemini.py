from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


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

    # The google-genai client is synchronous; run it directly for simplicity.
    client = genai.Client(api_key=api_key)

    contents = prompt if system is None else f"{system}\n\n{prompt}"
    resp = client.models.generate_content(model=model, contents=contents)

    text = getattr(resp, "text", None) or ""
    usage = {}
    # Best-effort usage extraction (varies by SDK version)
    for attr in ("usage_metadata", "usage", "metadata"):
        v = getattr(resp, attr, None)
        if v:
            try:
                usage = v if isinstance(v, dict) else v.model_dump()  # type: ignore[attr-defined]
            except (TypeError, AttributeError, ValueError):
                usage = {"raw": str(v)}
            break

    return GeminiResult(text=text, usage=usage)

