"""Input/coverage regressions only; synthetic records are never E2E evidence."""

from copy import deepcopy

import numpy as np
import pytest
import trimesh

from holocue.config import load_scene
from holocue.models import DisplayCue
from holocue.spatial import trajectory
from scripts.tests import audit_live_surface_supplement as audit


def unit_sequence():
    """Small consistency fixture, without a planner, Store or HTTP request."""
    spec = load_scene("control_panel", "reconstructed")
    poses = {obj.object_id: obj.pose.model_dump(mode="json") for obj in spec.objects}
    before, completed, history = [], [], []
    for index, step in enumerate(spec.task_contract.ordered_steps):
        obj = next(obj for obj in spec.objects if obj.object_id == step.target_id)
        semantic = dict(
            target_id=step.target_id,
            action=step.action,
            reference_id=step.reference_id,
            angle_deg=step.angle_deg,
            task_role="current",
            cue_type="highlight",
            instruction="Unit consistency fixture",
            priority=1,
            depth_requirement="precise",
        )
        task = {"task_id": f"unit-{index}", "semantic": semantic}
        cue = DisplayCue(
            **semantic,
            task_id=task["task_id"],
            n_gaussians=1,
            sigma_value=1,
            sigma_units="relative",
            sigma_profile="unit",
            pose=poses[obj.object_id],
            interaction=obj.interaction,
        )
        shared = dict(
            scene_set="reconstructed",
            scene_id=spec.scene_id,
            session_id="unit-session",
            revision=index * 2 + 1,
            epoch=1,
            execution="running",
        )
        state = dict(
            **shared,
            backend_mode="live",
            scene_fingerprint="unit-fingerprint",
            queue=[task],
            completed=deepcopy(history),
        )
        display = dict(
            **shared,
            axes="right_handed_z_up",
            units="m",
            object_poses=deepcopy(poses),
            cues=[cue.model_dump(mode="json")],
        )
        before.append({"state": state, "display": display})
        poses[obj.object_id] = trajectory(cue, cue.interaction.duration_s).model_dump(mode="json")
        history.append(task)
        after = deepcopy(before[-1])
        for payload in after.values():
            payload.update(revision=shared["revision"] + 1, execution="idle")
        after["state"].update(queue=[], completed=deepcopy(history))
        after["display"].update(object_poses=deepcopy(poses), cues=[])
        completed.append(after)
    return spec, {"steps": len(before), "session_id": "unit-session"}, before, completed


@pytest.mark.parametrize(
    "corruption",
    [
        None,
        "fingerprint",
        "set",
        "atomic",
        "missing_step",
        "cue_start",
        "prior_pose",
        "completion_pose",
        "task_identity",
    ],
)
def test_snapshot_validation_rejects_corruption_without_executing_tasks(corruption):
    spec, row, before, completed = unit_sequence()
    if corruption == "fingerprint":
        before[0]["state"]["scene_fingerprint"] = "old-assets"
    elif corruption == "set":
        before[0]["state"]["scene_set"] = before[0]["display"]["scene_set"] = "legacy"
    elif corruption == "atomic":
        before[0]["display"]["revision"] += 1
    elif corruption == "missing_step":
        before.pop()
    elif corruption == "cue_start":
        before[0]["display"]["cues"][0]["pose"]["position_m"][0] += 0.01
    elif corruption == "prior_pose":
        # A physically unchanged second task must still include the first
        # task's completed rotation when building its fixed obstacles.
        before[1]["display"]["object_poses"]["B"] = before[0]["display"]["object_poses"]["B"]
    elif corruption == "completion_pose":
        completed[0]["display"]["object_poses"]["B"]["position_m"][0] += 0.01
    elif corruption == "task_identity":
        completed[0]["state"]["completed"][-1]["task_id"] = "replacement-task"
    if corruption is None:
        assert len(audit.validate_sequence(spec, row, before, completed, "unit-fingerprint")) == 2
    else:
        with pytest.raises(ValueError):
            audit.validate_sequence(spec, row, before, completed, "unit-fingerprint")


def test_actual_inventory_keeps_open_environment_and_decorative_triangles():
    wall = trimesh.Trimesh(vertices=[[0, 0, 0], [0, 1, 0], [0, 0, 1]], faces=[[0, 1, 2]], process=False)
    parts = {"environment/large_open_wall": wall, "environment/decorative_stand": trimesh.creation.box()}
    obstacles = audit.surface_obstacles(parts)
    rows = audit.coverage_report(parts, obstacles)
    assert {row["part"] for row in rows} == set(parts)
    assert sum(row["triangles"] for row in rows) == 13
    assert rows[0]["status"] == "surface_only"
    assert rows[1]["status"] == "surface_and_closed_containment"
    with pytest.raises(ValueError, match="non-label obstacle was omitted"):
        audit.coverage_report(parts, obstacles[:1])


def test_label_name_cannot_hide_untextured_solid_geometry():
    parts = {"environment/label_misnamed_solid": trimesh.creation.box()}
    obstacles = audit.surface_obstacles(parts)
    rows = audit.coverage_report(parts, obstacles)
    assert len(obstacles) == 1
    assert rows[0]["triangles"] == 12
    assert rows[0]["status"] == "surface_and_closed_containment"
    with pytest.raises(ValueError, match="non-label obstacle was omitted"):
        audit.coverage_report(parts, [])


@pytest.mark.parametrize(
    "textured,solid,excluded", [(True, False, True), (False, False, False), (True, True, False)]
)
def test_only_planar_textured_decals_are_excluded(textured, solid, excluded):
    from PIL import Image

    part = (
        trimesh.creation.box()
        if solid
        else trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]], process=False)
    )
    if textured:
        part.visual = trimesh.visual.TextureVisuals(
            uv=np.zeros((len(part.vertices), 2)),
            material=trimesh.visual.material.PBRMaterial(baseColorTexture=Image.new("RGB", (2, 2))),
        )
    parts = {"object/label_arrow": part}
    obstacles = audit.surface_obstacles(parts)
    rows = audit.coverage_report(parts, obstacles)
    assert bool(obstacles) is not excluded
    assert (rows[0]["status"] == "excluded_explicit_textured_label") is excluded


def test_translations_preserve_every_original_keyframe_and_endpoint():
    cue = DisplayCue(
        task_id="unit",
        target_id="unit",
        task_role="current",
        cue_type="ghost_motion",
        action="insert",
        instruction="Unit only",
        priority=1,
        depth_requirement="precise",
        n_gaussians=1,
        sigma_value=1,
        sigma_units="relative",
        sigma_profile="unit",
        pose={"position_m": [0, 0, 0]},
        goal_pose={"position_m": [1, 1, 1]},
    )
    samples = audit.sampled_poses(cue)
    assert len(samples) == 67
    assert [row["keyframe_index"] for row in samples if row["kind"] == "path_keyframe"] == list(range(6))
    np.testing.assert_allclose(samples[60]["pose"].position_m, [1, 1, 1])


def test_old_topology_failure_is_not_relabelled_as_clearance():
    result = audit.closed_report_summary(
        {
            "status": "failed",
            "results": [
                {
                    "scene_id": "unit",
                    "step_index": 0,
                    "source_id": "unit",
                    "passed": False,
                    "penetrations": [],
                    "obstacle_coverage": [{"status": "invalid_solid_topology", "raw_faces": 100}],
                }
            ],
        }
    )
    assert result["status"] == "failed"
    assert result["detected_penetration_events"] == 0
    assert result["passed_path_count"] == 0
    assert result["results"][0]["raw_triangle_counts"]["invalid_solid_topology"] == 100
