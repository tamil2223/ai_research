from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from app.llm.gemini import generate_text

_LOG = logging.getLogger("capstone.topic_diagram")


def _strip_mermaid_fences(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"```(?:mermaid)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return raw


def _normalize_mermaid(text: str) -> str:
    text = _strip_mermaid_fences(text)
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    first = lines[0].lower()
    if not (first.startswith("flowchart") or first.startswith("graph ")):
        lines.insert(0, "flowchart TD")
    return "\n".join(lines)


def fallback_mermaid(query: str, plan: List[str]) -> str:
    """Topic-shaped steps from the plan when Gemini is unavailable or fails."""
    q = query.replace('"', "'").strip()[:72] or "Your goal"
    lines: List[str] = ["flowchart TD", f'    goal["{_esc_mermaid_label(q)}"]']
    prev = "goal"
    steps = [str(s).strip() for s in (plan or []) if str(s).strip()][:10]
    if not steps:
        lines.append('    done["Take concrete next steps toward your goal"]')
        lines.append("    goal --> done")
        return "\n".join(lines)
    for i, step in enumerate(steps):
        nid = f"s{i}"
        label = _esc_mermaid_label(str(step)[:100])
        lines.append(f'    {nid}["{label}"]')
        lines.append(f"    {prev} --> {nid}")
        prev = nid
    return "\n".join(lines)


def _esc_mermaid_label(s: str) -> str:
    return s.replace('"', "'").replace("\n", " ")


async def generate_topic_diagram_mermaid(
    *,
    api_key: str,
    model: str,
    query: str,
    plan: List[str],
    final_output: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Mermaid flowchart about the *user's question* (how to plan, research, act),
    not about LangGraph agents. Returns (mermaid_source, gemini_usage_dict).
    """
    plan_text = "\n".join(f"- {p}" for p in plan[:12]) if plan else "(no plan list)"
    summary = ""
    if isinstance(final_output, dict):
        summary = str(final_output.get("summary", ""))[:600]
    insights = final_output.get("insights") if isinstance(final_output, dict) else None
    if isinstance(insights, list) and insights:
        summary += "\nInsights:\n" + "\n".join(f"- {str(x)[:200]}" for x in insights[:4])

    if not api_key.strip():
        _LOG.info("topic_diagram: no API key, using plan fallback")
        return fallback_mermaid(query, plan), {}

    prompt = (
        f"User question:\n{query}\n\n"
        f"Plan steps (from an assistant):\n{plan_text}\n\n"
        f"Context from synthesized answer:\n{summary[:1200]}\n\n"
        "Create ONE Mermaid diagram: a flowchart TD that visualizes a practical path for the USER's goal "
        "(e.g. how to plan, what to research, skills to build, milestones, how to execute). "
        "The diagram must be about the *topic of the question*, not about software systems, agents, or APIs.\n"
        "Rules:\n"
        "- Output ONLY Mermaid source. No markdown fences, no prose before or after.\n"
        "- First line must be `flowchart TD` or `flowchart LR`.\n"
        "- Use quoted labels for nodes with spaces: A[\"Short label\"].\n"
        "- At most 16 nodes, keep labels under 8 words when possible.\n"
        "- Show a sensible flow: e.g. clarify goal → learn/research → practice → milestones → next steps.\n"
    )

    try:
        res = await generate_text(
            api_key=api_key,
            model=model,
            system=(
                "You output only valid Mermaid diagram syntax. "
                "Never mention planner, researcher, executor, critic, LangGraph, or API."
            ),
            prompt=prompt,
        )
        normalized = _normalize_mermaid(res.text)
        if not normalized or len(normalized) < 15:
            _LOG.warning("topic_diagram: Gemini returned empty/short, using fallback")
            return fallback_mermaid(query, plan), dict(res.usage or {})
        return normalized, dict(res.usage or {})
    except Exception as e:
        _LOG.warning("topic_diagram: Gemini failed, using fallback err=%s", e)
        return fallback_mermaid(query, plan), {}
