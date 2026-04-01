from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss  # type: ignore


@dataclass(frozen=True)
class Chunk:
    text: str
    metadata: Dict[str, Any]


def _iter_text_files(data_dir: Path) -> List[Path]:
    exts = {".txt", ".md"}
    files: List[Path] = []
    for p in data_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    return sorted(files)


def _chunk_text(text: str, chunk_size_chars: int = 2000, overlap_chars: int = 200) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    chunks: List[str] = []
    i = 0
    while i < len(t):
        end = min(len(t), i + chunk_size_chars)
        chunks.append(t[i:end])
        if end == len(t):
            break
        i = max(0, end - overlap_chars)
    return chunks


def _hash_embed_1536(text: str) -> List[float]:
    """
    Deterministic local embedding placeholder (1536 dims).
    This enables a fully runnable demo without network calls.

    Later: replace with real embeddings via OpenRouter/OpenAI-compatible endpoint.
    """
    import hashlib

    dim = 1536
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    base = list(digest)
    # Expand deterministically to dim floats in [0,1]
    out = []
    x = 0
    for i in range(dim):
        x = (x + base[i % len(base)] + i) % 256
        out.append(x / 255.0)
    return out


def build_chunks(data_dir: Path) -> List[Chunk]:
    chunks: List[Chunk] = []
    for fp in _iter_text_files(data_dir):
        raw = fp.read_text(encoding="utf-8", errors="ignore")
        for idx, c in enumerate(_chunk_text(raw)):
            chunks.append(
                Chunk(
                    text=c,
                    metadata={"source": fp.name, "path": str(fp), "chunk_id": idx},
                )
            )
    return chunks


def write_faiss_index(index_dir: Path, chunks: List[Chunk]) -> Tuple[Path, Path]:
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "rag.index"
    meta_path = index_dir / "rag.meta.jsonl"

    dim = 1536
    index = faiss.IndexFlatIP(dim)

    metas: List[Dict[str, Any]] = []
    vectors: List[List[float]] = []
    for c in chunks:
        vectors.append(_hash_embed_1536(c.text))
        metas.append({"text": c.text, "metadata": c.metadata})

    if vectors:
        import numpy as np

        x = np.asarray(vectors, dtype="float32")
        faiss.normalize_L2(x)
        index.add(x)

    faiss.write_index(index, str(index_path))

    with meta_path.open("w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    return index_path, meta_path


def main() -> None:
    capstone_root = Path(__file__).resolve().parents[2]
    data_dir = capstone_root / "data"
    index_dir = capstone_root / "index"

    chunks = build_chunks(data_dir)
    index_path, meta_path = write_faiss_index(index_dir, chunks)

    print(
        json.dumps(
            {
                "data_dir": str(data_dir),
                "chunks": len(chunks),
                "index_path": str(index_path),
                "meta_path": str(meta_path),
            }
        )
    )


if __name__ == "__main__":
    main()

