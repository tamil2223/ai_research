from __future__ import annotations

import json
import re
from typing import Any


def parse_json_from_llm(raw: str) -> Any:
    """
    Parse JSON from model output that may be wrapped in markdown fences or prose.
    Raises json.JSONDecodeError or ValueError if nothing usable is found.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty model response")

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
    if fence:
        inner = fence.group(1).strip()
        if inner:
            return json.loads(inner)

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(s[start : end + 1])

    raise json.JSONDecodeError("no JSON object found in model output", s, 0)
