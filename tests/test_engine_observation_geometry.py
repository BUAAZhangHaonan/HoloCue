"""Regressions for the detached terminal and the occluded installed port view."""

import numpy as np
import pytest
import trimesh
from pydantic import ValidationError

from holocue import camera
from holocue.assets import load_asset, world_scene
from holocue.config import load_scene, root
from holocue.modeling import make_object
from holocue.models import Interaction, Pose
from holocue.spatial import mating_goal, rotation, transform_points


@pytest.mark.parametrize("roundtrip", [False, True])
def test_terminal_contacts_ceramic_without_changing_tip_or_outer_envelope(tmp_path, roundtrip):
    spec = load_scene("engine_bay")
    plug = next(o for o in spec.objects if o.object_id == "PLUG")
    assembly = make_object(plug)
    scene = assembly.scene
    if roundtrip:
        path = tmp_path / "plug.glb"
        assembly.save(path)
        scene = load_asset(str(path), spec.asset_axes)
    parts = {}
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        parts[str(node).split("_", 1)[1]] = mesh
    terminal, ceramic = parts["terminal"], parts["ceramic"]
    assert terminal.bounds[0, 2] == pytest.approx(ceramic.bounds[1, 2], abs=1e-8)
    assert terminal.bounds[1, 2] == pytest.approx(0.0468, abs=1e-8)
    np.testing.assert_allclose(terminal.bounds[:, :2], [[-0.002, -0.002], [0.002, 0.002]], atol=1e-8)
    np.testing.assert_allclose(scene.bounds[:, 2], [-0.0423, 0.0468], atol=1e-8)
    for mesh in (terminal, ceramic):
        welded = mesh.copy()
        welded.merge_vertices(merge_norm=True, merge_tex=True)
        assert welded.is_watertight and welded.is_winding_consistent
        assert welded.volume > 0


def first_hit_distance(triangles, origin, direction):
    """Direct segment/triangle intersections; no ray-index package is required."""
    edge1 = triangles[:, 1] - triangles[:, 0]
    edge2 = triangles[:, 2] - triangles[:, 0]
    cross = np.cross(direction, edge2)
    determinant = np.einsum("ij,ij->i", edge1, cross)
    nonparallel = np.abs(determinant) > 1e-12
    inverse = np.divide(1.0, determinant, out=np.zeros_like(determinant), where=nonparallel)
    delta = origin - triangles[:, 0]
    u = np.einsum("ij,ij->i", delta, cross) * inverse
    q = np.cross(delta, edge1)
    v = (q @ direction) * inverse
    distance = np.einsum("ij,ij->i", edge2, q) * inverse
    hits = nonparallel & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (distance > 0)
    return float(distance[hits].min()) if hits.any() else float("inf")


def actual_annular_rim_points(mesh):
    """Sixteen inner-lip witnesses from actual upward annular triangles.

    Do not reuse the old hand-authored radius/height or infer a rim from an AABB.
    Candidate points are required to lie on the exported triangles. The highest
    complete annular plane supplies the lip, rather than a single convenient
    visible triangle or a lower internal seat.
    """
    triangles = mesh.triangles
    horizontal = (mesh.face_normals[:, 2] > 0.99) & (np.ptp(triangles[:, :, 2], axis=1) < 1e-7)
    heights = np.unique(np.round(triangles[horizontal, :, 2].mean(axis=1), 7))[::-1]
    angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    down = np.array([0.0, 0.0, -1.0])
    for height in heights:
        planar = triangles[horizontal & (np.abs(triangles[:, :, 2].mean(axis=1) - height) < 1e-7)]
        # A solid cap is not an annular opening.
        if np.isfinite(first_hit_distance(planar, np.array([0.0, 0.0, height + 0.001]), down)):
            continue
        starts = planar[:, :, :2].reshape(-1, 2)
        edges = (np.roll(planar[:, :, :2], -1, axis=1) - planar[:, :, :2]).reshape(-1, 2)
        points = []
        for angle in angles:
            before = len(points)
            direction = np.array([np.cos(angle), np.sin(angle)])
            determinant = edges[:, 0] * direction[1] - edges[:, 1] * direction[0]
            valid = np.abs(determinant) > 1e-12
            t = np.divide(
                -starts[:, 0] * direction[1] + starts[:, 1] * direction[0],
                determinant,
                out=np.zeros_like(determinant),
                where=valid,
            )
            radial = np.divide(
                -starts[:, 0] * edges[:, 1] + starts[:, 1] * edges[:, 0],
                determinant,
                out=np.zeros_like(determinant),
                where=valid,
            )
            cuts = np.unique(np.round(radial[valid & (t >= -1e-7) & (t <= 1 + 1e-7) & (radial > 0)], 8))
            for inner, outer in zip(cuts[:-1], cuts[1:]):
                if inner <= 0.002 or outer - inner <= 1e-7:
                    continue
                radius = inner + min(0.0005, (outer - inner) / 2)
                point = np.array([*(radius * direction), height])
                hit = first_hit_distance(planar, point + [0, 0, 0.001], down)
                if abs(hit - 0.001) < 1e-7:
                    points.append(point)
                    break
            if len(points) == before:
                break
        if len(points) == 16:
            return np.asarray(points)
    raise AssertionError("No complete actual annular opening with sixteen lip witnesses")


@pytest.mark.parametrize("aspect", [0.72, 0.97, 1.276, 16 / 9])
def test_installed_port_inner_rim_is_in_frame_and_not_hidden_by_real_environment(aspect):
    spec = load_scene("engine_bay")
    plug = next(o for o in spec.objects if o.object_id == "PLUG")
    port = next(o for o in spec.objects if o.object_id == "PLUGPORT")
    local = load_asset(str(root() / port.asset), spec.asset_axes)
    position, look, up = camera.detail_view(
        port,
        port.pose,
        local.bounds,
        np.asarray(spec.camera_position_m) - spec.camera_look_at_m,
        aspect=aspect,
    )
    points = transform_points(port.pose, camera.corners(local.bounds))
    projected, _ = camera.project(points, position, look, aspect=aspect, up=up)
    assert np.abs(projected).max() <= 0.860001
    # Test the real opening around all sixteen azimuths, including the installed
    # plug. A rebuilt shoulder/receiver need not retain the old procedural rim.
    rim = transform_points(port.pose, actual_annular_rim_points(local.to_geometry()))
    installed = mating_goal(plug, port, port.pose, "insert")
    world = world_scene(root(), spec, {"PLUG": installed}).to_geometry()
    for point in rim:
        delta = point - position
        length = np.linalg.norm(delta)
        distance = first_hit_distance(world.triangles, np.asarray(position), delta / length)
        assert distance >= length - 1e-6, "A scene surface hides the port inner rim"


def test_explicit_detail_axis_follows_object_pose_and_rejects_invalid_axes():
    spec = load_scene("engine_bay")
    port = next(o for o in spec.objects if o.object_id == "PLUGPORT")
    local = load_asset(str(root() / port.asset), spec.asset_axes)
    pose = Pose(position_m=(0.2, 0.3, 0.4), wxyz=(2**-0.5, 0.0, 2**-0.5, 0.0))
    position, look, _ = camera.detail_view(port, pose, local.bounds, (1.0, -1.0, 1.0))
    direction = np.asarray(position) - look
    np.testing.assert_allclose(
        direction / np.linalg.norm(direction), rotation(pose).apply([0, 0, 1]), atol=1e-8
    )
    with pytest.raises(ValidationError):
        Interaction(detail_direction_local=(0.0, 0.0, 0.0))
