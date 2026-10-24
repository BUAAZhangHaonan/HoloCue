"""The collision audit must account for actual solid obstacles."""

import pytest
import trimesh
import numpy as np
from scipy.spatial.transform import Rotation

from holocue.config import load_scene
from scripts.tests.audit_geometry import geometry_copy, ordered_steps, parts, transform


def test_generic_blocks_support_surfaces_are_collision_obstacles(tmp_path, monkeypatch):
    from holocue.modeling import make_environment

    spec = load_scene("blocks")
    # Retain the closed-solid audit contract for the generic CAD environment.
    # Production blocks uses mature surface meshes; its complete triangle
    # coverage and real support contacts are checked in test_blocks_drone_assets.
    path = tmp_path / "generic-blocks-environment.glb"
    make_environment(spec).save(path)
    monkeypatch.setenv("HOLOCUE_ROOT", str(tmp_path))
    environment = spec.environment[0].model_copy(update={"asset": str(path)})
    obstacles, coverage = parts(spec, [environment])
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


def test_geometry_copy_joins_attribute_seams_without_changing_render_asset():
    box = trimesh.creation.box([0.02, 0.02, 0.02])
    vertices = box.triangles.reshape(-1, 3)
    faces = np.arange(len(vertices)).reshape(-1, 3)
    uv = np.arange(len(vertices) * 2).reshape(-1, 2) / 100
    mesh = trimesh.Trimesh(
        vertices,
        faces,
        process=False,
        vertex_normals=np.repeat(box.face_normals, 3, axis=0),
        visual=trimesh.visual.TextureVisuals(uv=uv),
    )
    solid = geometry_copy(mesh)
    assert solid.is_watertight and solid.is_winding_consistent
    np.testing.assert_array_equal(solid.triangles, mesh.triangles)
    np.testing.assert_array_equal(mesh.visual.uv, uv)
    np.testing.assert_array_equal(mesh.vertices, vertices)
    assert not mesh.is_watertight


def test_geometry_copy_preserves_thin_topologically_required_faces():
    box = trimesh.creation.box([0.02, 0.02, 0.02])
    a, b, c = box.faces[0]
    midpoint = (box.vertices[a] + box.vertices[b]) / 2
    point = midpoint + 1e-7 * (box.vertices[c] - midpoint)
    vertices = np.vstack([box.vertices, point])
    p = len(vertices) - 1
    faces = np.vstack([box.faces[1:], [a, b, p], [b, c, p], [c, a, p]])
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    assert mesh.is_watertight and mesh.is_winding_consistent
    solid = geometry_copy(mesh)
    assert solid.is_watertight and solid.is_winding_consistent
    np.testing.assert_array_equal(solid.triangles, mesh.triangles)


def test_geometry_copy_does_not_close_a_real_subnanometre_gap():
    box = trimesh.creation.box([0.02, 0.02, 0.02])
    vertices = box.triangles.reshape(-1, 3).copy()
    vertices[0] += [1e-10, 0, 0]
    mesh = trimesh.Trimesh(vertices, np.arange(len(vertices)).reshape(-1, 3), process=False)
    solid = geometry_copy(mesh)
    assert not solid.is_watertight
    np.testing.assert_array_equal(solid.triangles, mesh.triangles)


def test_closed_components_each_have_outward_signed_distance(monkeypatch):
    spec = load_scene("blocks")
    obj = spec.objects[0]
    first = trimesh.creation.box([0.02, 0.02, 0.02])
    first.invert()
    second = trimesh.creation.box([0.03, 0.03, 0.03])
    second.apply_translation([0.06, 0, 0])
    mesh = trimesh.util.concatenate([first, second])
    source_faces = mesh.faces.copy()
    monkeypatch.setattr("scripts.tests.audit_geometry.load_asset", lambda *args: trimesh.Scene(mesh))
    obstacles, coverage = parts(spec, [obj])
    assert coverage[0]["status"] == "included_closed_solid"
    field = obstacles[0][3]
    for local in ([0, 0, 0], [0.06, 0, 0]):
        point = trimesh.transform_points([local], transform(obj.pose))[0]
        assert field.EvaluateFunction(point) < -0.009
    np.testing.assert_array_equal(mesh.faces, source_faces)
