from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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


async def rag_retrieve(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
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
    scores, ids = index.search(q, min(top_k, len(metas)))

    out: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
        if idx < 0 or idx >= len(metas):
            continue
        m = metas[idx]
        md = dict(m.get("metadata", {}) or {})
        out.append(
            {
                "origin": md.get("source") or md.get("path") or "data",
                "snippet": str(m.get("text", ""))[:1000],
                "metadata": {**md, "score": float(score)},
            }
        )
    return out

