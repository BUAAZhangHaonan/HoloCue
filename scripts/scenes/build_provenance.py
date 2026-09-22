"""Streaming file identities shared by application and Blender builders."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def file_record(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Build input outside project: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def inputs(spec):
    names = [ROOT / "src/holocue/modeling.py", ROOT / "scenes" / spec.scene_id / "scene.json"]
    names.extend(sorted((ROOT / "scripts/scenes").glob("*.py")))
    return {
        "source": [file_record(p) for p in names],
        "assets": [file_record(ROOT / obj.asset) for obj in [*spec.objects, *spec.environment]],
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("trimesh", "numpy", "cadquery", "pillow", "pygltflib")
        },
    }


def output_root():
    path = Path(os.environ.get("RUN_DIR", ROOT / "runs/simulation")).resolve()
    if not path.is_relative_to(ROOT / "runs") and not path.is_relative_to(ROOT / ".work"):
        raise ValueError("Build reports must stay inside project runs or .work")
    return path


def write_report(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
