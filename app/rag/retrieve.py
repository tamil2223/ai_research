from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import faiss  # type: ignore


def _hash_embed_1536(text: str) -> List[float]:
    # Keep in sync with ingest.py (deterministic local embedding placeholder)
    import hashlib

    dim = 1536
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    base = list(digest)
    out = []
    x = 0
    for i in range(dim):
        x = (x + base[i % len(base)] + i) % 256
        out.append(x / 255.0)
    return out


def _load_meta(meta_path: Path) -> List[Dict[str, Any]]:
    if not meta_path.exists():
        return []
    metas: List[Dict[str, Any]] = []
    for line in meta_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        metas.append(json.loads(line))
    return metas


def _tokens(s: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _lexical_score(query: str, text: str) -> float:
    """Overlap of query word types with chunk (0..1). Strong signal for hash-based 'embeddings'."""
    q = _tokens(query)
    t = _tokens(text)
    if not q:
        return 0.0
    inter = len(q & t)
    return inter / max(len(q), 1)


def _faiss_norm(score: float) -> float:
    """Map inner-product score of L2-normalized vectors to [0, 1]."""
    return max(0.0, min(1.0, (float(score) + 1.0) / 2.0))


async def rag_retrieve(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: hash embeddings are not semantic; we re-rank FAISS candidates
    with lexical overlap so queries like 'software engineer' match relevant chunks.
    """
    capstone_root = Path(__file__).resolve().parents[2]
    index_dir = capstone_root / "index"
    index_path = index_dir / "rag.index"
    meta_path = index_dir / "rag.meta.jsonl"

    if not index_path.exists() or not meta_path.exists():
        return []

    index = faiss.read_index(str(index_path))
    metas = _load_meta(meta_path)
    if not metas:
        return []

    import numpy as np

    q = np.asarray([_hash_embed_1536(query)], dtype="float32")
    faiss.normalize_L2(q)

    n_meta = len(metas)
    # Pull a wider candidate pool, then re-rank with lexical + vector similarity.
    k_cand = min(max(top_k * 10, 24), n_meta)
    scores, ids = index.search(q, k_cand)

    ranked: List[Tuple[float, int]] = []
    seen: set[int] = set()
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0 or idx >= n_meta or idx in seen:
            continue
        seen.add(idx)
        text = str(metas[idx].get("text", ""))
        lex = _lexical_score(query, text)
        fn = _faiss_norm(float(score))
        # Lexical dominates so user wording matches corpus; FAISS breaks ties.
        combined = 0.62 * lex + 0.38 * fn
        ranked.append((combined, idx))

    ranked.sort(key=lambda x: -x[0])

    # If corpus is small, allow pure lexical top-ups when overlap exists.
    if n_meta <= 400 and top_k > 0:
        lex_only: List[Tuple[float, int]] = []
        for i, m in enumerate(metas):
            text = str(m.get("text", ""))
            ls = _lexical_score(query, text)
            if ls > 0:
                lex_only.append((ls, i))
        lex_only.sort(key=lambda x: -x[0])
        best_combined = ranked[0][0] if ranked else 0.0
        if best_combined < 0.08 and lex_only:
            for ls, idx in lex_only[: top_k * 2]:
                if idx not in seen:
                    ranked.append((0.15 + 0.85 * ls, idx))
                    seen.add(idx)
            ranked.sort(key=lambda x: -x[0])

    out: List[Dict[str, Any]] = []
    for combined, idx in ranked[:top_k]:
        m = metas[idx]
        md = dict(m.get("metadata", {}) or {})
        out.append(
            {
                "origin": md.get("source") or md.get("path") or "data",
                "snippet": str(m.get("text", ""))[:1000],
                "metadata": {
                    **md,
                    "hybrid_score": round(float(combined), 4),
                },
            }
        )
    return out
