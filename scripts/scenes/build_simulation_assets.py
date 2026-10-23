"""Build the authored scene contracts into standard, self-contained glTF assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from holocue.config import list_scenes, load_scene, root, scene_set, runtime_dir, SCENE_SETS
from holocue.modeling import make_environment, make_object
from holocue.assets import load_asset
from scripts.scenes.build_provenance import inputs, write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", nargs="*")
    parser.add_argument("--report")
    parser.add_argument("--scene-set", choices=SCENE_SETS, default=scene_set())
    args = parser.parse_args()
    os.environ["HOLOCUE_SCENE_SET"] = args.scene_set
    selected = args.scenes or [x["scene_id"] for x in list_scenes()]
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate selected scenes")
    output = root() / args.report if args.report else runtime_dir() / "assets.json"
    provenance_path = output.with_suffix(".provenance.json")
    provenance = {
        "scene_set": scene_set(),
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
        authored = None
        if scene_set() == "legacy":
            pass  # Original make_object/make_environment recipes; never the reconstruction builders.
        elif sid == "shelf_picking":
            from scripts.scenes.rebuild_shelf_assets import build

            authored = build(spec)
        elif sid == "server_rack":
            from scripts.scenes.rebuild_server_assets import build

            authored = build(spec)
        elif sid == "optical_bench":
            from scripts.scenes.rebuild_optical_assets import build

            authored = build(spec)
        elif sid == "dig_site":
            from scripts.scenes.rebuild_dig_assets import build

            authored = build(spec)
        elif sid == "control_panel":
            from scripts.scenes.rebuild_control_panel_assets import build

            authored = build(spec)
        elif sid == "connector":
            from scripts.scenes.rebuild_connector_assets import build

            authored = build(spec)
        elif sid == "blocks":
            from scripts.scenes.rebuild_blocks_assets import build

            authored = build(spec)
        elif sid == "drone_bench":
            from scripts.scenes.rebuild_drone_assets import build

            authored = build(spec)
        elif sid == "engine_bay":
            from scripts.scenes.rebuild_engine_assets import build

            authored = build(spec)
        elif sid == "cnc_toolchange":
            from scripts.scenes.rebuild_cnc_assets import build

            authored = build(spec)
        elif sid == "dive_fillstation":
            from scripts.scenes.rebuild_dive_assets import build

            authored = build(spec)
        elif sid == "infusion_ward":
            from scripts.scenes.rebuild_infusion_assets import build

            authored = build(spec)
        for obj in spec.objects:
            assembly = authored[obj.object_id] if authored is not None else make_object(obj)
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
        env = authored["environment"] if authored is not None else make_environment(spec)
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
