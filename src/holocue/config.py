from __future__ import annotations
import json, os
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SceneSpec

SCENE_SETS = ("legacy", "reconstructed")


def root() -> Path:
    return Path(os.environ.get("HOLOCUE_ROOT", Path(__file__).resolve().parents[2])).resolve()


def scene_set(selected_set: str | None = None) -> str:
    value = os.environ.get("HOLOCUE_SCENE_SET", "reconstructed") if selected_set is None else selected_set
    if value not in SCENE_SETS:
        raise ValueError(f"Unknown scene set {value!r}; choose legacy or reconstructed")
    return value


def scene_dir(scene_id: str, selected_set: str | None = None) -> Path:
    if not scene_id.replace("_", "").isalnum():
        raise ValueError("Invalid scene ID")
    return root() / "scenes" / scene_set(selected_set) / scene_id


def runtime_dir() -> Path:
    value = Path(os.environ.get("RUN_DIR", root() / "runs/simulation" / scene_set()))
    path = (root() / value).resolve()
    if not path.is_relative_to(root()) or path == root():
        raise ValueError("RUN_DIR must be a directory inside the project")
    return path


def load_scene(scene_id: str, selected_set: str | None = None) -> SceneSpec:
    from .models import SceneSpec

    selected = scene_set(selected_set)
    p = scene_dir(scene_id, selected) / "scene.json"
    result = SceneSpec.model_validate(
        json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    )
    if result.scene_id != scene_id:
        raise ValueError("scene directory and scene_id differ")
    result.scene_set = selected
    return result


def list_scenes(selected_set: str | None = None) -> list[dict]:
    selected = scene_set(selected_set)
    return [
        {
            "scene_id": s.scene_id,
            "scene_set": selected,
            "title": s.title,
            "initial_instruction": s.initial_instruction,
        }
        for s in (
            load_scene(p.parent.name, selected)
            for p in sorted((root() / "scenes" / selected).glob("*/scene.json"))
            if not p.parent.name.startswith("_")
        )
    ]


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key}")
        result[key] = value
    return result


def load_policy() -> dict:
    return json.loads((root() / "configs/display_policy.json").read_text())


@lru_cache(maxsize=512)
def _asset_digest(path: str, mtime_ns: int, size: int) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene_fingerprint(scene: SceneSpec) -> str:
    assets = []
    for resource in [o.asset for o in scene.objects] + [p.asset for p in scene.environment]:
        path = (root() / resource).resolve()
        if not path.is_relative_to(root()):
            raise ValueError("scene asset is outside the project")
        stat = path.stat()
        assets.append((resource, _asset_digest(str(path), stat.st_mtime_ns, stat.st_size)))
    data = {"scene": scene.model_dump(mode="json"), "assets": assets}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
