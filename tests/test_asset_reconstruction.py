"""Physical and semantic checks of the two asset-led, actually exported scenes.

The former appearance fingerprints remain frozen for the unchanged scenes.
Here real support surfaces, cavity clearance, material payloads and sampled task
body sweeps replace equality to the intentionally superseded visual meshes.
"""

from functools import lru_cache
import json
from pathlib import Path
import struct

import numpy as np
import pytest

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.models import Pose
from holocue.spatial import matrix, path_keyframes, rotate_about, trajectory
from scripts.tests.audit_geometry import ordered_steps


SCENES = ("shelf_picking", "server_rack")
BASELINE = json.loads((Path(__file__).parent / "fixtures/floor_grounding_baseline.json").read_text())
PHYSICAL_FIELDS = ("object_id", "size_m", "pose", "capabilities", "anchors", "frames", "interaction")


def meshes(spec, entry, pose=None):
    asset = load_asset(str(root() / entry.asset), spec.asset_axes)
    transform = matrix(pose or entry.pose)
    if hasattr(entry, "scale_m"):
        transform = transform @ np.diag([*entry.scale_m, 1])
    result = {}
    for node in asset.graph.nodes_geometry:
        local, name = asset.graph[node]
        mesh = asset.geometry[name].copy()
        mesh.apply_transform(transform @ local)
        result[str(node)] = mesh
    return result


def triangles(parts):
    return np.concatenate([part.triangles for part in parts.values()])


@lru_cache(maxsize=2)
def environment_triangles(sid):
    spec = load_scene(sid)
    return np.concatenate([triangles(meshes(spec, entry)) for entry in spec.environment])


def vertical_hits(tris, xy):
    """All real triangle intersections along a vertical line, including open meshes."""
    candidate = tris[
        (tris[:, :, :2].min(axis=1) <= np.asarray(xy) + 1e-9).all(axis=1)
        & (tris[:, :, :2].max(axis=1) >= np.asarray(xy) - 1e-9).all(axis=1)
    ]
    if not len(candidate):
        return np.empty(0)
    a = candidate[:, 0, :2]
    u = candidate[:, 1, :2] - a
    v = candidate[:, 2, :2] - a
    w = np.asarray(xy) - a
    det = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    valid = np.abs(det) > 1e-14
    s = np.divide(w[:, 0] * v[:, 1] - w[:, 1] * v[:, 0], det, out=np.zeros_like(det), where=valid)
    t = np.divide(u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0], det, out=np.zeros_like(det), where=valid)
    hit = valid & (s >= -1e-8) & (t >= -1e-8) & (s + t <= 1 + 1e-8)
    z = candidate[:, 0, 2] + s * (candidate[:, 1, 2] - candidate[:, 0, 2])
    z += t * (candidate[:, 2, 2] - candidate[:, 0, 2])
    return z[hit]


def assert_supported(source, support, tolerance=0.001):
    """At least three separated low-surface witnesses touch real support triangles."""
    low = source[:, :, 2].min()
    # Include curved low vertices, edge points and triangle interiors. Testing
    # only planar triangles misses wheels; vertices alone miss a supported pad
    # whose corners slightly overhang its smaller support. Keep the 1 mm limit.
    weights = [[i / 4, j / 4, 1 - (i + j) / 4] for i in range(5) for j in range(5 - i)]
    weights.append([1 / 3, 1 / 3, 1 / 3])
    sampled = np.einsum("wj,tjk->twk", weights, source).reshape(-1, 3)
    points = sampled[sampled[:, 2] <= low + tolerance]
    assert len(points), "No actual low-surface contact candidates"
    points = np.unique(np.round(points, 7), axis=0)
    # Keep every selected surface witness. Crop the obstacle field instead of
    # striding past potentially narrow contact strips such as rack supports.
    region_low = points.min(axis=0) - [1e-8, 1e-8, tolerance]
    region_high = points.max(axis=0) + [1e-8, 1e-8, tolerance]
    support = support[
        (support.min(axis=1) <= region_high).all(axis=1) & (support.max(axis=1) >= region_low).all(axis=1)
    ]
    witnesses = []
    for point in points:
        hits = vertical_hits(support, point[:2])
        near = hits[np.abs(hits - point[2]) <= tolerance]
        if len(near):
            witnesses.append(point)
    assert len(witnesses) >= 3, ("unsupported asset", low, len(witnesses))
    assert np.ptp(np.asarray(witnesses)[:, :2], axis=0).max() > 0.005


def intersecting_box_triangles(tris, low, high):
    """Triangle/box separating-axis test; does not discard non-watertight assets."""
    select = (tris.min(axis=1) < high).all(axis=1) & (tris.max(axis=1) > low).all(axis=1)
    candidates = tris[select]
    if not len(candidates):
        return candidates
    v = candidates - (low + high) / 2
    half = (high - low) / 2
    edges = np.roll(v, -1, axis=1) - v
    keep = np.ones(len(v), dtype=bool)
    axes = [np.cross(edges[:, 0], edges[:, 1])]
    axes.extend(np.cross(edges[:, edge], unit) for edge in range(3) for unit in np.eye(3))
    for axis in axes:
        projected = np.einsum("nij,nj->ni", v, axis)
        radius = np.abs(axis) @ half
        separated = (projected.min(axis=1) > radius + 1e-12) | (projected.max(axis=1) < -radius - 1e-12)
        keep &= ~separated
    return candidates[keep]


def glb_json(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and length == len(data)
    length, kind = struct.unpack_from("<II", data, 12)
    assert kind == 0x4E4F534A
    return json.loads(data[20 : 20 + length])


@pytest.mark.parametrize("sid", SCENES)
def test_reconstruction_preserves_task_geometry_and_identity(sid):
    spec = load_scene(sid)
    old = BASELINE["scenes"][sid]
    old_objects = {obj["object_id"]: obj for obj in old["objects"]}
    assert {obj.object_id for obj in spec.objects} == set(old_objects)
    for obj in spec.objects:
        current = obj.model_dump(mode="json")
        assert {key: current[key] for key in PHYSICAL_FIELDS} == {
            key: old_objects[obj.object_id][key] for key in PHYSICAL_FIELDS
        }
    assert spec.task_contract.model_dump(mode="json") == old["task_contract"]
    poses = json.loads(
        json.dumps(
            [
                {"pose": entry.pose.model_dump(mode="json"), "scale_m": entry.scale_m}
                for entry in spec.environment
            ]
        )
    )
    assert poses == old["environment_poses"]
    assert spec.asset_axes == "gltf_y_up"


@pytest.mark.parametrize("sid", SCENES)
def test_exported_assets_have_embedded_pbr_and_valid_uvs(sid):
    spec = load_scene(sid)
    pbr_materials = 0
    crate_entries = set()
    for entry in [*spec.objects, *spec.environment]:
        document = glb_json(root() / entry.asset)
        assert all("uri" not in buffer for buffer in document.get("buffers", []))
        assert all("bufferView" in image and "uri" not in image for image in document.get("images", []))
        materials = document.get("materials", [])
        for mesh in document["meshes"]:
            for primitive in mesh["primitives"]:
                attributes = primitive["attributes"]
                assert "NORMAL" in attributes
                material = materials[primitive["material"]]
                pbr = material.get("pbrMetallicRoughness", {})
                if (
                    any(key in pbr for key in ("baseColorTexture", "metallicRoughnessTexture"))
                    or "normalTexture" in material
                ):
                    assert "TEXCOORD_0" in attributes
                if "normalTexture" in material and "metallicRoughnessTexture" in pbr:
                    pbr_materials += 1
        asset = load_asset(str(root() / entry.asset), spec.asset_axes)
        for mesh in asset.geometry.values():
            assert np.isfinite(mesh.vertices).all()
            assert np.isfinite(mesh.vertex_normals).all()
            uv = getattr(mesh.visual, "uv", None)
            if uv is not None:
                assert np.isfinite(uv).all()
        if sid == "shelf_picking":
            # The two task crates and yellow shelf-stock crate share an RGB
            # source with modelled vents. BLEND/one-sided rendering made entire
            # walls disappear in the real Viser scene despite opaque pixels.
            for node in asset.graph.nodes_geometry:
                if "plastic_crate_02" not in str(node) and "shelf_stock_5" not in str(node):
                    continue
                _, geometry = asset.graph[node]
                material = asset.geometry[geometry].visual.material
                assert (material.alphaMode or "OPAQUE") == "OPAQUE", node
                assert material.doubleSided is True, node
                assert material.baseColorFactor[3] == 255, node
                assert material.baseColorTexture is not None, node
                assert material.normalTexture is not None, node
                assert material.metallicRoughnessTexture is not None, node
                albedo = material.baseColorTexture
                assert albedo.mode == "RGB" or (
                    "A" in albedo.getbands() and albedo.getchannel("A").getextrema() == (255, 255)
                ), node
                crate_entries.add(entry.asset)
    assert pbr_materials > 0, "The rebuilt scene must actually reference textured mature assets"
    if sid == "shelf_picking":
        expected = {obj.asset for obj in spec.objects if obj.object_id in {"BLUE", "BASKET"}}
        expected.add(spec.environment[0].asset)
        assert crate_entries == expected, "All three reconstructed crate instances must be checked"


@pytest.mark.parametrize(
    "sid,identifier",
    [("shelf_picking", name) for name in ("RED", "BLUE", "BASKET", "GREEN", "CONV")]
    + [("server_rack", name) for name in ("SPARE", "NODE3")],
)
def test_actual_task_objects_rest_on_real_support_surfaces(sid, identifier):
    spec = load_scene(sid)
    obj = next(obj for obj in spec.objects if obj.object_id == identifier)
    assert_supported(triangles(meshes(spec, obj)), environment_triangles(sid))


def test_shelf_workstations_and_service_mats_have_real_floor_connections():
    spec = load_scene("shelf_picking")
    parts = meshes(spec, spec.environment[0])
    floor = {name: mesh for name, mesh in parts.items() if "warehouse_floor" in name}
    assert floor
    for prefix in ("picking_rack", "basket_cart", "inspection_cart", "conveyor_foot"):
        structure = {
            name: mesh
            for name, mesh in parts.items()
            if prefix in name and "service_mat" not in name and "toolbox" not in name
        }
        assert structure, prefix
        assert_supported(triangles(structure), triangles(floor))
    for prefix in ("basket_cart", "inspection_cart"):
        mat = {name: mesh for name, mesh in parts.items() if prefix + "_service_mat" in name}
        cart = {
            name: mesh
            for name, mesh in parts.items()
            if prefix in name and "service_mat" not in name and "toolbox" not in name
        }
        assert mat and cart
        assert_supported(triangles(mat), triangles(cart))


@pytest.mark.parametrize("sid", SCENES)
def test_task_body_sweep_clears_actual_obstacle_triangles(sid):
    spec = load_scene(sid)
    _, step, display, cue, _ = next(ordered_steps(spec))
    source = next(obj for obj in spec.objects if obj.object_id == step.target_id)
    obstacles = [environment_triangles(sid)]
    for obj in spec.objects:
        if obj.object_id != source.object_id:
            obstacles.append(triangles(meshes(spec, obj, display.object_poses[obj.object_id])))
    obstacle = np.concatenate(obstacles)
    keys = path_keyframes(cue)
    poses = keys + [trajectory(cue, float(time)) for time in np.linspace(0, cue.interaction.duration_s, 81)]
    # The moving parcel/chassis body is a rectangular envelope; retain a 0.75 mm
    # contact tolerance. This is a sampled body-clearance check, not a claim of
    # continuous collision freedom for every decorative or articulated part.
    half = np.asarray(source.size_m) / 2 - 0.00075
    for index, pose in enumerate(poses):
        np.testing.assert_allclose(pose.wxyz, [1, 0, 0, 0], atol=1e-8)
        center = np.asarray(pose.position_m)
        hits = intersecting_box_triangles(obstacle, center - half, center + half)
        assert len(hits) == 0, (sid, index, pose.position_m, len(hits), hits[:2].tolist())
    if sid == "server_rack":
        # The final insertion is an axis-aligned translation, so this one box
        # is the exact swept rectangular body for the entire segment.
        start, end = np.asarray(keys[-2].position_m), np.asarray(keys[-1].position_m)
        np.testing.assert_allclose(start[[0, 2]], end[[0, 2]], atol=1e-8)
        hits = intersecting_box_triangles(
            obstacle, np.minimum(start, end) - half, np.maximum(start, end) + half
        )
        assert len(hits) == 0, ("continuous insertion corridor", len(hits), hits[:2].tolist())
    expected_goal = [-0.25, -0.62, 0.905] if sid == "shelf_picking" else [0, 0.26, 1.13]
    np.testing.assert_allclose(cue.goal_pose.position_m, expected_goal, atol=1e-8)
    if sid == "shelf_picking":
        receiver = next(obj for obj in spec.objects if obj.object_id == "BASKET")
        support = triangles(meshes(spec, receiver))
    else:
        receiver = next(obj for obj in spec.objects if obj.object_id == "SLOT4")
        support = np.concatenate([triangles(meshes(spec, receiver)), environment_triangles(sid)])
    assert_supported(triangles(meshes(spec, source, cue.goal_pose)), support)


def test_basket_cavity_and_blue_back_label_are_real_exported_surfaces():
    spec = load_scene("shelf_picking")
    objects = {obj.object_id: obj for obj in spec.objects}
    basket = meshes(spec, objects["BASKET"], Pose())
    liner = [mesh for name, mesh in basket.items() if "basket_inner_liner" in name]
    assert liner
    liner_triangles = np.concatenate([mesh.triangles for mesh in liner])
    for x in (-0.12, 0, 0.12):
        for y in (-0.095, 0, 0.095):
            hit = vertical_hits(liner_triangles, [x, y])
            assert len(hit)
            assert max(hit) == pytest.approx(-0.085, abs=1e-6)
    blue = meshes(spec, objects["BLUE"], Pose())
    labels = [mesh for name, mesh in blue.items() if "back_shipping_label" in name]
    assert len(labels) == 1
    label = labels[0]
    np.testing.assert_allclose(
        label.vertices[:, 1], objects["BLUE"].interaction.inspect_point_local_m[1], atol=1e-7
    )
    assert np.all(label.face_normals[:, 1] > 0.999)
    material = label.visual.material
    assert material.baseColorTexture is not None and material.metallicFactor == 0
    pixels = np.asarray(material.baseColorTexture.convert("RGB")).reshape(-1, 3)
    assert np.unique(pixels, axis=0).shape[0] > 16


def test_blue_rotation_keeps_the_rebuilt_crate_clear_of_the_workstation():
    spec = load_scene("shelf_picking")
    obj = next(obj for obj in spec.objects if obj.object_id == "BLUE")
    parts = meshes(spec, obj, Pose())
    bounds = np.asarray([mesh.bounds for mesh in parts.values()])
    low, high = bounds[:, 0].min(axis=0) + 0.00075, bounds[:, 1].max(axis=0) - 0.00075
    center = np.asarray(obj.pose.position_m)
    radius = max(np.linalg.norm(low), np.linalg.norm(high))
    obstacle = environment_triangles("shelf_picking")
    nearby = obstacle[
        (obstacle.min(axis=1) < center + radius).all(axis=1)
        & (obstacle.max(axis=1) > center - radius).all(axis=1)
    ]
    # Test the supported rotation capability against the real cart, including
    # its handles, at 15 degree intervals without changing the frozen pivot.
    for angle in np.linspace(-180, 180, 25):
        pose = rotate_about(
            obj.pose, obj.interaction.rotation_axis_local, obj.interaction.pivot_local_m, angle
        )
        transform = np.linalg.inv(matrix(pose))
        local = nearby @ transform[:3, :3].T + transform[:3, 3]
        hits = intersecting_box_triangles(local, low, high)
        assert len(hits) == 0, (angle, len(hits), hits[:2].tolist())


def test_server_service_carts_and_cabinet_have_real_floor_connections():
    spec = load_scene("server_rack")
    parts = meshes(spec, spec.environment[0])
    floor = {name: mesh for name, mesh in parts.items() if "raised_floor" in name}
    assert floor
    rack = {name: mesh for name, mesh in parts.items() if "rack_frame" in name}
    assert rack
    assert_supported(triangles(rack), triangles(floor))
    for sign in (-1, 1):
        structure = {
            name: mesh
            for name, mesh in parts.items()
            if "service_cart" in name and np.sign(mesh.bounds.mean(axis=0)[0]) == sign
        }
        assert structure, sign
        assert_supported(triangles(structure), triangles(floor))
    for prefix, support_prefix in (("service_riser", "service_cart"), ("service_pad", "service_riser")):
        pieces = {name: mesh for name, mesh in parts.items() if prefix in name}
        support = {name: mesh for name, mesh in parts.items() if support_prefix in name}
        assert len(pieces) == 2 and support
        for piece in pieces.values():
            assert_supported(piece.triangles, triangles(support))
