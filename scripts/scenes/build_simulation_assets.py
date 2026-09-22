"""Build the authored scene contracts into standard, self-contained glTF assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from holocue.config import list_scenes, load_scene, root
from holocue.modeling import make_environment, make_object
from holocue.assets import load_asset
from scripts.scenes.build_provenance import inputs, write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", nargs="*")
    parser.add_argument("--report", default="runs/simulation/assets.json")
    args = parser.parse_args()
    selected = args.scenes or [x["scene_id"] for x in list_scenes()]
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate selected scenes")
    output = root() / args.report
    provenance_path = output.with_suffix(".provenance.json")
    provenance = {
        "requested_scene_ids": selected,
        "built_scene_ids": [],
        "built_assets": [],
        "scene_inputs": {},
        "disk_inventory": [],
        "complete": False,
    }
    write_report(provenance_path, provenance)
    records = []
    for sid in selected:
        spec = load_scene(sid)
        if spec.asset_axes != "gltf_y_up":
            raise ValueError("asset builds require standard glTF coordinates")
        for obj in spec.objects:
            assembly = make_object(obj)
            path = root() / obj.asset
            assembly.save(path)
            records.append(
                {
                    "scene_id": sid,
                    "object_id": obj.object_id,
                    "path": obj.asset,
                    "parts": len(assembly.scene.geometry),
                    "triangles": sum(len(m.faces) for m in assembly.scene.geometry.values()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            provenance["built_assets"] = records
            write_report(provenance_path, provenance)
        env = make_environment(spec)
        path = root() / spec.environment[0].asset
        env.save(path)
        records.append(
            {
                "scene_id": sid,
                "object_id": "environment",
                "path": spec.environment[0].asset,
                "parts": len(env.scene.geometry),
                "triangles": sum(len(m.faces) for m in env.scene.geometry.values()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        provenance["built_assets"] = records
        provenance["built_scene_ids"].append(sid)
        provenance["scene_inputs"][sid] = inputs(spec)
        write_report(provenance_path, provenance)
        print(sid, "built", len(spec.objects), "objects", flush=True)
    records = []
    for entry in list_scenes():
        spec = load_scene(entry["scene_id"])
        for obj in [*spec.objects, *spec.environment]:
            path = root() / obj.asset
            scene = load_asset(str(path), spec.asset_axes)
            identifier = obj.object_id if hasattr(obj, "object_id") else obj.prop_id
            records.append(
                {
                    "scene_id": spec.scene_id,
                    "object_id": identifier,
                    "path": obj.asset,
                    "parts": len(scene.geometry),
                    "triangles": sum(len(m.faces) for m in scene.geometry.values()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance["disk_inventory"] = records
    provenance["complete"] = True
    write_report(provenance_path, provenance)


if __name__ == "__main__":
    main()
