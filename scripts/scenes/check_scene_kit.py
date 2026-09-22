"""Validate executable scene assets and optionally require native Blender outputs."""

from __future__ import annotations

import argparse
import json

from holocue.config import root, list_scenes, load_scene, scene_fingerprint


def check(scene_id, require_blender=False):
    scene = load_scene(scene_id)
    objects = {obj.object_id: obj for obj in scene.objects}
    for item in scene.objects + scene.environment:
        path = (root() / item.asset).resolve()
        if not path.is_relative_to(root()) or not path.is_file():
            raise FileNotFoundError(path)
    for step in scene.task_contract.ordered_steps:
        if step.action not in objects[step.target_id].capabilities:
            raise ValueError("task action is absent from target capabilities")
        if step.reference_id is not None and step.reference_id not in objects:
            raise ValueError("task receiver is absent from scene")
    if require_blender and not (root() / "scenes" / scene_id / "scene.blend").is_file():
        raise FileNotFoundError(f"{scene_id}/scene.blend")
    return {
        "scene_id": scene_id,
        "fingerprint": scene_fingerprint(scene),
        "objects": len(scene.objects),
        "native_blender_required": require_blender,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenes", nargs="*")
    parser.add_argument("--require-blender", action="store_true")
    args = parser.parse_args()
    rows = [check(sid, args.require_blender) for sid in args.scenes or [x["scene_id"] for x in list_scenes()]]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
