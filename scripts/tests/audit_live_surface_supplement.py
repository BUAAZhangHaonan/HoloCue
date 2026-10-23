"""Supplemental finite-pose surface checks of recorded real-model API workflows.

This reads completed live_twelve_scenes outputs; it never calls a model, HTTP,
Store or apply_decision, and never constructs a plan from expected answers.
The original closed-solid audit remains a separate, unchanged result.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import trimesh

from holocue.config import list_scenes, load_scene, root, scene_fingerprint, scene_set
from holocue.models import DisplayCue, Pose
from holocue.spatial import matrix, path_keyframes, trajectory

# Reuse the tested implementation, including its open-surface and containment
# regressions. Do not copy a second collision algorithm into this CLI.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))
from test_asset_reconstruction import meshes
from test_blocks_drone_assets import assert_actual_surface_clearance, closed_mesh_copy
from holocue.render_validation import polydata
from test_engine_cnc_assets import actual_world_parts


MOTION_ACTIONS = {"rotate", "insert", "assemble"}
TOLERANCE_M = 0.0001
MODEL = "Qwen/Qwen3.5-4B"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_record(path, receipts):
    data = path.read_bytes()
    receipts.append(
        {"path": str(path.resolve().relative_to(root())), "sha256": hashlib.sha256(data).hexdigest()}
    )
    return json.loads(data)


def same_pose(a, b):
    return np.allclose(matrix(Pose.model_validate(a)), matrix(Pose.model_validate(b)), atol=1e-7, rtol=0)


def require_poses(actual, expected, context):
    require(set(actual) == set(expected), f"{context}: object pose IDs differ")
    for identifier in expected:
        require(
            same_pose(actual[identifier], expected[identifier]), f"{context}: changed pose for {identifier}"
        )


def validate_sequence(spec, row, before, completed, fingerprint):
    """Reject mixed, stale or incomplete records before examining any geometry."""
    contract = spec.task_contract.ordered_steps
    require(len(before) == len(completed) == row["steps"] == len(contract), "recorded step count differs")
    previous_poses = {obj.object_id: obj.pose.model_dump(mode="json") for obj in spec.objects}
    previous_completed = None
    cues = []
    for index, (snapshot, confirmed, step) in enumerate(zip(before, completed, contract)):
        for item in (snapshot, confirmed):
            state, display = item["state"], item["display"]
            require(state["backend_mode"] == "live", "snapshot is not a live session")
            require(state["scene_fingerprint"] == fingerprint, "snapshot asset fingerprint is stale")
            for field in ("session_id", "scene_id", "scene_set", "revision", "epoch", "execution"):
                require(state[field] == display[field], f"non-atomic snapshot {field}")
            require(state["scene_set"] == spec.scene_set == "reconstructed", "wrong scene set")
            require(
                state["scene_id"] == spec.scene_id and state["session_id"] == row["session_id"],
                "mixed session",
            )
            require(
                display["axes"] == "right_handed_z_up" and display["units"] == "m",
                "unexpected geometry units",
            )
        state, display = snapshot["state"], snapshot["display"]
        require_poses(display["object_poses"], previous_poses, f"step {index} preceding state")
        if previous_completed is not None:
            require(state["completed"] == previous_completed, "preceding completion history differs")
        task = state["queue"][0]
        semantic = task["semantic"]
        expected = (step.target_id, step.action, step.reference_id, step.angle_deg)
        require(
            tuple(semantic.get(k) for k in ("target_id", "action", "reference_id", "angle_deg")) == expected,
            "recorded task differs from contract",
        )
        matches = [c for c in display["cues"] if c["task_id"] == task["task_id"]]
        require(len(matches) == 1, "current task does not have exactly one display cue")
        cue = DisplayCue.model_validate(matches[0])
        require(cue.task_role == "current", "recorded cue is not current")
        for key, value in semantic.items():
            require(getattr(cue, key) == value, f"display cue differs from committed semantic field {key}")
        obj = next(obj for obj in spec.objects if obj.object_id == cue.target_id)
        require(cue.interaction == obj.interaction, "display changed the source interaction")
        require(
            same_pose(cue.pose.model_dump(), display["object_poses"][cue.target_id]),
            "cue start differs from recorded pose",
        )
        after_poses = dict(display["object_poses"])
        after_poses[cue.target_id] = trajectory(cue, cue.interaction.duration_s).model_dump(mode="json")
        require_poses(confirmed["display"]["object_poses"], after_poses, f"step {index} explicit completion")
        after = confirmed["state"]
        require(after["revision"] > state["revision"], "completion did not advance revision")
        require(
            after["completed"] == [*state["completed"], task], "completion did not preserve task identity"
        )
        previous_poses, previous_completed = confirmed["display"]["object_poses"], after["completed"]
        cues.append(cue)
    require(
        not completed[-1]["state"]["queue"] and completed[-1]["state"]["execution"] == "idle",
        "workflow not complete",
    )
    return cues


def model_jobs(http_rows, session_id):
    jobs = {}
    for record in http_rows:
        if (
            record["method"] != "GET"
            or not record["path"].startswith("/api/v1/jobs/")
            or record["status"] != 200
        ):
            continue
        job = json.loads(record["response"])
        if job["status"] != "done":
            continue
        data = job["data"]
        require(job["session_id"] == session_id, "HTTP evidence contains a different session")
        require(data["backend_mode"] == "live" and data["model"] == MODEL, "wrong model evidence")
        require(data["http_status"] == 200, "model HTTP request did not succeed")
        choice = json.loads(data["raw_http_body"])["choices"][0]
        require(choice["finish_reason"] == "stop", "model response was truncated")
        require(choice["message"]["content"] == data["raw_response"], "raw model response differs")
        require(
            json.loads(data["raw_response"]) == data["decision"], "model decision differs from wire content"
        )
        jobs[job["id"]] = {
            "job_id": job["id"],
            "model": data["model"],
            "operation": data["decision"]["operation"],
            "revision": data["revision"],
        }
    require(len(jobs) >= 3, "initial/interruption/restoration model evidence is incomplete")
    return list(jobs.values())


def load_live(directory, receipts):
    selection = read_record(directory / "selection.json", receipts)
    rows = read_record(directory / "report.json", receipts)
    require(
        selection["scene_set"] == "reconstructed" and selection["complete"],
        "live selection is incomplete or wrong set",
    )
    selected = selection["selected_scene_ids"]
    require(len(selected) == len(set(selected)), "duplicate selected scenes")
    require([row["scene_id"] for row in rows] == selected, "live report does not match selection")
    result = []
    for row in rows:
        require(row["passed"] and row["backend_mode"] == "live", "live scene did not pass")
        spec = load_scene(row["scene_id"], "reconstructed")
        folder = directory / spec.scene_id
        before = read_record(folder / "snapshots.json", receipts)
        completed = read_record(folder / "completed_snapshots.json", receipts)
        final = read_record(folder / "final.json", receipts)
        jobs = model_jobs(read_record(folder / "http.json", receipts), row["session_id"])
        fingerprint = scene_fingerprint(spec)
        cues = validate_sequence(spec, row, before, completed, fingerprint)
        require(final == completed[-1]["state"], "final state differs from last completion snapshot")
        require(
            selection["expected_steps_by_scene"][spec.scene_id] == len(cues), "selection step count differs"
        )
        result.append((spec, row, before, cues, fingerprint, jobs))
    require(
        selection["expected_scene_count"] == selection["completed_scene_count"] == len(result),
        "selection scene count differs",
    )
    require(
        selection["expected_step_count"]
        == selection["completed_step_count"]
        == sum(len(item[3]) for item in result),
        "selection total step count differs",
    )
    return result


def closed_report_summary(data):
    rows = []
    for row in data["results"]:
        counts = Counter(part["status"] for part in row["obstacle_coverage"])
        faces = Counter()
        for part in row["obstacle_coverage"]:
            faces[part["status"]] += part["raw_faces"]
        rows.append(
            {
                "scene_id": row["scene_id"],
                "step_index": row["step_index"],
                "source_id": row["source_id"],
                "passed": row["passed"],
                "part_counts": dict(counts),
                "raw_triangle_counts": dict(faces),
                "detected_penetration_events": len(row["penetrations"]),
            }
        )
    return {
        "status": data["status"],
        "path_count": len(rows),
        "passed_path_count": sum(row["passed"] for row in rows),
        "detected_penetration_events": sum(row["detected_penetration_events"] for row in rows),
        "interpretation": "Zero reported events concerns covered closed-solid witnesses only. Invalid topology remains failed coverage, not a whole-scene clearance pass.",
        "results": rows,
    }


def explicit_textured_label(name, part):
    """Only a planar textured decal may be excluded; names alone are insufficient."""
    return (
        name.split("/")[-1].startswith("label_")
        and isinstance(part.visual, trimesh.visual.TextureVisuals)
        and getattr(part.visual.material, "baseColorTexture", None) is not None
        and np.linalg.matrix_rank(part.vertices - part.vertices.mean(axis=0), tol=1e-8) <= 2
    )


def surface_obstacles(parts):
    # Keep the shared actual-surface/containment algorithm. Apply the original
    # closed-audit decal rule before constructing its full-triangle inputs.
    return [
        (name, part, polydata(part), closed_mesh_copy(part))
        for name, part in parts.items()
        if not explicit_textured_label(name, part)
    ]


def coverage_report(parts, obstacles):
    included = {name: (data, solid) for name, _, data, solid in obstacles}
    expected = {name for name, part in parts.items() if not explicit_textured_label(name, part)}
    require(set(included) == expected, "a non-label obstacle was omitted")
    rows = []
    for name, part in parts.items():
        require(len(part.faces) > 0 and np.isfinite(part.vertices).all(), f"empty or invalid mesh {name}")
        if name in included:
            data, solid = included[name]
            require(data.GetNumberOfCells() == len(part.faces), f"triangle coverage changed for {name}")
            status = "surface_and_closed_containment" if solid is not None else "surface_only"
        else:
            material = getattr(part.visual, "material", None)
            require(
                getattr(material, "baseColorTexture", None) is not None,
                f"excluded label is not textured: {name}",
            )
            status = "excluded_explicit_textured_label"
        rows.append(
            {
                "part": name,
                "entry_id": name.split("/")[0],
                "triangles": len(part.faces),
                "vertices": len(part.vertices),
                "status": status,
            }
        )
    return rows


def sampled_poses(cue):
    count = 37 if cue.action == "rotate" else 61
    rows = [
        {"kind": "time_sample", "elapsed_s": float(t), "pose": trajectory(cue, float(t))}
        for t in np.linspace(0, cue.interaction.duration_s, count)
    ]
    if cue.action != "rotate":
        rows.extend(
            {"kind": "path_keyframe", "keyframe_index": index, "pose": pose}
            for index, pose in enumerate(path_keyframes(cue))
        )
    return rows


def check_motion(spec, snapshot, cue, step_index, closed_row):
    started = time.monotonic()
    source = next(obj for obj in spec.objects if obj.object_id == cue.target_id)
    local_parts = meshes(spec, source, Pose())
    local = trimesh.util.concatenate(list(local_parts.values()))
    overrides = {
        key: Pose.model_validate(value) for key, value in snapshot["display"]["object_poses"].items()
    }
    fixed = actual_world_parts(spec, exclude=cue.target_id, overrides=overrides)
    obstacles = surface_obstacles(fixed)
    coverage = coverage_report(fixed, obstacles)
    # An additional independent inventory comparison prevents a new loader
    # from accidentally dropping an environment prop or a large source asset.
    current_counts, closed_counts = Counter(), Counter()
    for part in coverage:
        current_counts[part["entry_id"]] += part["triangles"]
    for part in closed_row["obstacle_coverage"]:
        closed_counts[part["object_id"]] += part["raw_faces"]
    require(
        current_counts == closed_counts, "actual obstacle triangle inventory differs from the original audit"
    )
    setup_seconds = time.monotonic() - started
    samples, failures = sampled_poses(cue), []
    for index, sample in enumerate(samples):
        transform = matrix(sample["pose"])
        moved = local.copy().apply_transform(transform)
        moved_parts = [part.copy().apply_transform(transform) for part in local_parts.values()]
        try:
            assert_actual_surface_clearance(moved, obstacles, tolerance=TOLERANCE_M, moving_parts=moved_parts)
        except AssertionError as error:
            failures.append(
                {
                    "sample_index": index,
                    **{key: value for key, value in sample.items() if key != "pose"},
                    "pose": sample["pose"].model_dump(mode="json"),
                    "first_detected_witness": repr(error),
                }
            )
    return {
        "scene_id": spec.scene_id,
        "step_index": step_index,
        "task_id": cue.task_id,
        "source_id": cue.target_id,
        "action": cue.action,
        "receiver_id": cue.reference_id,
        "recorded_cue": cue.model_dump(mode="json"),
        "session_id": snapshot["state"]["session_id"],
        "revision": snapshot["state"]["revision"],
        "epoch": snapshot["state"]["epoch"],
        "prior_completed_task_ids": [task["task_id"] for task in snapshot["state"]["completed"]],
        "recorded_object_poses": snapshot["display"]["object_poses"],
        "moving_part_count": len(local_parts),
        "moving_triangle_count": len(local.faces),
        "moving_parts": [{"part": name, "triangles": len(part.faces)} for name, part in local_parts.items()],
        "fixed_coverage": coverage,
        "fixed_triangle_count": sum(len(part.faces) for part in fixed.values()),
        "included_fixed_triangle_count": sum(len(part.faces) for _, part, _, _ in obstacles),
        "inventory_matches_original_audit": True,
        "pose_count": len(samples),
        "setup_seconds": setup_seconds,
        "elapsed_seconds": time.monotonic() - started,
        "failures": failures,
        "passed": not failures,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        type=Path,
        nargs="+",
        required=True,
        help="Completed real live_twelve_scenes output directories",
    )
    parser.add_argument(
        "--closed-report",
        type=Path,
        required=True,
        help="Unmodified audit_geometry report, including any failures",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(scene_set() == "reconstructed", "supplement requires reconstructed scene configuration")
    require(not args.out.exists(), "output already exists; preserve the prior result")
    receipts = []
    sources = [item for directory in args.live for item in load_live(directory, receipts)]
    selected = [item[0].scene_id for item in sources]
    require(len(selected) == len(set(selected)), "live inputs contain duplicate scenes")
    closed = read_record(args.closed_report, receipts)
    closed_rows = {(row["scene_id"], row["step_index"]): row for row in closed["results"]}
    expected = sum(cue.action in MOTION_ACTIONS for _, _, _, cues, _, _ in sources for cue in cues)
    source_receipts = []
    for path in [
        Path(__file__),
        root() / "tests/test_blocks_drone_assets.py",
        root() / "tests/test_engine_cnc_assets.py",
        root() / "tests/test_asset_reconstruction.py",
        root() / "tests/panel_optical_geometry/__init__.py",
        root() / "src/holocue/spatial.py",
    ]:
        source_receipts.append(
            {
                "path": str(path.resolve().relative_to(root())),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    report = {
        "status": "running",
        "model_backend_exercised_by_this_check": False,
        "input_model": MODEL,
        "scene_set": "reconstructed",
        "selected_scene_ids": selected,
        "all_twelve_scenes_selected": set(selected)
        == {row["scene_id"] for row in list_scenes("reconstructed")},
        "expected_motion_paths": expected,
        "completed_motion_paths": 0,
        "method": "Shared VTK all-triangle contacts and local actual-surface witnesses, plus bidirectional containment of independently closed parts; no mesh filling or decimation.",
        "tolerance_m": TOLERANCE_M,
        "translation_time_samples": 61,
        "translation_keyframes": 6,
        "rotation_time_samples": 37,
        "limits": [
            "Finite poses and finite local/vertex/face-centre witnesses do not prove continuous or exhaustive collision freedom.",
            "At most the first detected witness per pose is reported, not every intersecting pair.",
            "Every non-label fixed triangle participates; only explicit planar textured label nodes are excluded, matching the original closed-audit decal rule. Moving geometry includes all source parts.",
            "These parameters differ from the original 41 x 1536 / 0.75 mm closed-solid audit and do not replace or relax its result.",
            "This is a read-only geometric supplement to real API records, not an additional LLM run or an independent UI/native acceptance.",
        ],
        "inputs": receipts,
        "implementation": source_receipts,
        "scenes": [
            {
                "scene_id": spec.scene_id,
                "session_id": row["session_id"],
                "scene_fingerprint": fingerprint,
                "real_model_jobs": jobs,
            }
            for spec, row, _, _, fingerprint, jobs in sources
        ],
        "original_closed_audit": closed_report_summary(closed),
        "results": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    for spec, _, before, cues, _, _ in sources:
        for index, (snapshot, cue) in enumerate(zip(before, cues)):
            if cue.action not in MOTION_ACTIONS:
                continue
            try:
                old = closed_rows[(spec.scene_id, index)]
                require(
                    old["source_id"] == cue.target_id and old["action"] == cue.action,
                    "original audit step does not match real record",
                )
                result = check_motion(spec, snapshot, cue, index, old)
            except Exception as error:
                result = {
                    "scene_id": spec.scene_id,
                    "step_index": index,
                    "source_id": cue.target_id,
                    "passed": False,
                    "error": repr(error),
                }
            report["results"].append(result)
            report["completed_motion_paths"] = len(report["results"])
            save()
            print(
                spec.scene_id,
                cue.target_id,
                "passed" if result["passed"] else "FAILED",
                f"{result.get('elapsed_seconds', 0):.2f}s",
                flush=True,
            )
    report["status"] = (
        "passed"
        if len(report["results"]) == expected and all(row["passed"] for row in report["results"])
        else "failed"
    )
    save()
    if report["status"] != "passed":
        raise SystemExit("Supplemental actual-surface checks failed; inspect the saved result")


if __name__ == "__main__":
    main()
