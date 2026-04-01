from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_run_snapshot_file(*, capstone_root: Path, run_id: str, snapshot: Dict[str, Any]) -> Path:
    index_dir = capstone_root / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    path = index_dir / f"run.{run_id}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

