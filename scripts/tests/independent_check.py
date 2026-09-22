"""Independent-process validation of saved meshes, image evidence and source constraints."""

from __future__ import annotations

import ast
import argparse
import hashlib
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import trimesh

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rendered", type=Path, default=ROOT / "runs/simulation/rendered")
    parser.add_argument(
        "--flat-rendered",
        action="store_true",
        help="Read validate_renderings.py output directly, without scene subdirectories",
    )
    parser.add_argument("--geometry", type=Path, default=ROOT / "runs/simulation/geometry_audit.json")
    parser.add_argument("--junit", type=Path, default=ROOT / "runs/simulation/domain_tests.xml")
    parser.add_argument("--out", type=Path, default=ROOT / "runs/simulation/independent_check.json")
    args = parser.parse_args()
    manifests = [
        p for p in sorted((ROOT / "scenes").glob("*/scene.json")) if not p.parent.name.startswith("_")
    ]
    if len(manifests) != 12:
        raise AssertionError("expected twelve scene manifests")
    files = []
    totals = {"scenes": 12, "objects": 0, "meshes": 0, "triangles": 0}
    for path in manifests:
        scene = json.loads(path.read_text())
        if scene["scene_id"] != path.parent.name:
            raise AssertionError("scene identifier mismatch")
        totals["objects"] += len(scene["objects"])
        for item in scene["objects"] + scene["environment"]:
            asset = (ROOT / item["asset"]).resolve()
            if not asset.is_relative_to(ROOT):
                raise AssertionError("asset path leaves project")
            mesh = trimesh.load_scene(asset)
            if not mesh.geometry:
                raise AssertionError("asset has no geometry")
            count = 0
            for geometry in mesh.geometry.values():
                if not np.isfinite(geometry.vertices).all() or len(geometry.faces) == 0:
                    raise AssertionError("invalid mesh vertices or faces")
                count += len(geometry.faces)
            files.append(
                {
                    "path": item["asset"],
                    "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    "triangles": count,
                }
            )
            totals["triangles"] += count
            totals["meshes"] += 1
        for view in ("overview", "front", "detail", "inspection"):
            image_directory = args.rendered if args.flat_rendered else args.rendered / scene["scene_id"]
            image = image_directory / f"{scene['scene_id']}_{view}.png"
            with Image.open(image) as frame:
                frame.load()
                if frame.width != 1280 or np.asarray(frame).std() < 5:
                    raise AssertionError("render evidence lacks valid image content")
    audit = json.loads(args.geometry.read_text())
    if (
        audit.get("status") != "passed"
        or len(audit["results"]) != 11
        or any(
            not row.get("passed")
            or row["penetrations"]
            or any(part["status"] == "invalid_solid_topology" for part in row["obstacle_coverage"])
            for row in audit["results"]
        )
    ):
        raise AssertionError("trajectory geometry audit failed")
    source_files = list((ROOT / "src/holocue").glob("*.py")) + list((ROOT / "scripts/scenes").glob("*.py"))
    source_files += list((ROOT / "scripts/tests").glob("*.py")) + list(
        (ROOT / "scripts/capture").glob("*.py")
    )
    source_hashes = []
    for path in sorted(source_files):
        tree = ast.parse(path.read_text(), filename=str(path))
        source_hashes.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for statement in node.body:
                    if any(isinstance(part, (ast.Import, ast.ImportFrom)) for part in ast.walk(statement)):
                        raise AssertionError(f"import inside try block: {path}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if Path(node.value).parts[:2] == ("/", "tmp"):
                    raise AssertionError(f"prohibited temporary path in {path}")
    suites = ET.parse(args.junit).getroot()
    tests = sum(int(suite.attrib["tests"]) for suite in suites.iter("testsuite"))
    failures = sum(
        int(suite.attrib["failures"]) + int(suite.attrib["errors"]) for suite in suites.iter("testsuite")
    )
    if failures:
        raise AssertionError("unit test evidence contains failures")
    report = {
        "status": "passed",
        "review_type": "independent_process",
        "python": sys.version,
        "subagent_used": False,
        "native_blender_exercised": False,
        "native_viser_exercised": False,
        "model_generation_exercised": False,
        "tests": tests,
        "asset_totals": totals,
        "assets": files,
        "checked_source_files": source_hashes,
        "source_digest": hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(),
    }
    report["evidence_inputs"] = {
        key: str(getattr(args, key).resolve()) for key in ("rendered", "geometry", "junit")
    }
    report["rendered_layout"] = "flat" if args.flat_rendered else "scene_subdirectories"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in ("assets", "checked_source_files")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
