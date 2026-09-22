"""The collision audit must account for actual solid obstacles."""

import pytest
import trimesh
import numpy as np
from scipy.spatial.transform import Rotation

from holocue.config import load_scene
from scripts.tests.audit_geometry import ordered_steps, parts, transform


def test_blocks_support_surfaces_are_collision_obstacles():
    spec = load_scene("blocks")
    obstacles, coverage = parts(spec, spec.environment)
    included = {name for _, name, _, _ in obstacles}
    for suffix in ("_worktop", "_work_mat", "_left_parts_tray", "_right_parts_tray"):
        records = [row for row in coverage if row["part"].endswith(suffix)]
        assert len(records) == 1
        assert records[0]["status"] == "included_closed_solid"
        assert records[0]["part"] in included
    assert not any(row["status"] == "invalid_solid_topology" for row in coverage)
    assert any(row["status"] == "excluded_textured_label_surface" for row in coverage)


def test_optical_audit_keeps_completed_insertion_and_separate_mirror_steps():
    stages = list(ordered_steps(load_scene("optical_bench")))
    assert [(step.target_id, step.action) for _, step, _, _, _ in stages] == [
        ("L1", "insert"),
        ("M", "rotate"),
        ("M", "inspect_back"),
    ]
    insertion = stages[0][3]
    for _, _, display, _, completed in stages[1:]:
        assert np.allclose(transform(display.object_poses["L1"]), transform(insertion.goal_pose), atol=1e-8)
        assert completed[0]["task_id"] == insertion.task_id
    rotation = stages[1][3]
    inspection = stages[2][3]
    assert rotation.angle_deg == -15
    assert rotation.task_id != inspection.task_id
    assert stages[2][4][-1]["task_id"] == rotation.task_id
    # Independent local-axis rotation formula, including a possible pivot.
    pivot = np.asarray(rotation.interaction.pivot_local_m)
    local = np.eye(4)
    local[:3, :3] = Rotation.from_rotvec(
        np.asarray(rotation.interaction.rotation_axis_local) * np.deg2rad(-15)
    ).as_matrix()
    local[:3, 3] = pivot - local[:3, :3] @ pivot
    expected = transform(rotation.pose) @ local
    assert np.allclose(transform(inspection.pose), expected, atol=1e-8)


def test_geometry_audit_keeps_the_control_rotation_angle():
    stages = list(ordered_steps(load_scene("control_panel")))
    rotation = stages[0][3]
    assert (rotation.target_id, rotation.action, rotation.angle_deg) == ("B", "rotate", 30)
    assert stages[1][4][0]["task_id"] == rotation.task_id
    assert stages[1][4][0]["semantic"]["angle_deg"] == 30


@pytest.mark.parametrize("node_name", ["open_part", "label_untextured_open_part"])
def test_open_solid_is_reported_as_uncovered_not_silently_ignored(tmp_path, monkeypatch, node_name):
    spec = load_scene("blocks")
    mesh = trimesh.creation.box()
    mesh.update_faces(range(len(mesh.faces) - 1))
    path = tmp_path / "open-solid.glb"
    asset = trimesh.Scene()
    asset.add_geometry(mesh, node_name=node_name)
    asset.export(path)
    monkeypatch.setenv("HOLOCUE_ROOT", str(tmp_path))
    obj = spec.objects[0].model_copy(update={"asset": "open-solid.glb"})
    obstacles, coverage = parts(spec, [obj])
    assert not obstacles
    assert len(coverage) == 1
    assert coverage[0]["status"] == "invalid_solid_topology"
