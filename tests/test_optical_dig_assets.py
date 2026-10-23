"""Exported optical/dig asset checks; no API, model or task execution.

Geometry tests evaluate the declared rigid transforms directly. Native Blender
and Viser images/controls are reviewed separately, not inferred from these tests.
"""

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from holocue.assets import load_asset
from holocue.camera import inspect_view
from holocue.config import load_scene, root
from holocue.models import DisplayCue, Pose, SceneSpec
from holocue.response import basis_from_normal, local_cue_pool, splat_arrays
from holocue.spatial import mating_goal, matrix, path_keyframes, rotate_about, trajectory, transform_points
from panel_optical_geometry import bottom_contacts, ray_hits
from test_asset_reconstruction import (
    BASELINE,
    PHYSICAL_FIELDS,
    assert_supported,
    environment_triangles,
    glb_json,
    intersecting_box_triangles,
    meshes,
    triangles,
    vertical_hits,
)


SCENES = ("optical_bench", "dig_site")


def combined(parts):
    return trimesh.util.concatenate(list(parts.values()))


def object_by_id(spec, identifier):
    return next(obj for obj in spec.objects if obj.object_id == identifier)


def assert_thin_card_support(source, support):
    """Resolve the small actual contact patch instead of striding past it."""
    low = source[:, :, 2].min()
    tolerance = 0.001
    source_low = source[:, :, :2].min(axis=(0, 1))
    source_high = source[:, :, :2].max(axis=(0, 1))
    candidate = support[
        (support[:, :, 2].min(axis=1) <= low + tolerance)
        & (support[:, :, 2].max(axis=1) >= low - tolerance)
        & (support[:, :, :2].min(axis=1) <= source_high).all(axis=1)
        & (support[:, :, :2].max(axis=1) >= source_low).all(axis=1)
    ]
    assert len(candidate)
    lower = np.maximum(source_low, candidate[:, :, :2].min(axis=(0, 1)))
    upper = np.minimum(source_high, candidate[:, :, :2].max(axis=(0, 1)))
    assert np.all(upper > lower)
    contacts = []
    for x in np.linspace(lower[0], upper[0], 17):
        for y in np.linspace(lower[1], upper[1], 9):
            a = vertical_hits(source, [x, y])
            b = vertical_hits(candidate, [x, y])
            if len(a) and len(b) and a.min() <= low + tolerance:
                if np.any(np.abs(b - a.min()) <= tolerance):
                    contacts.append([x, y, a.min()])
    assert len(contacts) >= 3, ("unsupported thin card", len(contacts))
    # The same 1 mm gap and >5 mm contact-span requirements remain in force.
    assert np.ptp(np.asarray(contacts)[:, :2], axis=0).max() > 0.005


def geometry_cue(obj, action, **kwargs):
    """Direct geometric inputs, with no planner/session/task-store lifecycle."""
    return DisplayCue(
        task_id="geometry-only",
        target_id=obj.object_id,
        task_role="current",
        cue_type="highlight" if action == "inspect_back" else "ghost_motion",
        action=action,
        instruction="Geometry regression",
        priority=1,
        depth_requirement="precise",
        n_gaussians=8192 if action == "inspect_back" else 0,
        sigma_value=1,
        sigma_units="relative",
        sigma_profile="geometry-only",
        pose=obj.pose,
        interaction=obj.interaction,
        **kwargs,
    )


@pytest.mark.parametrize("scene_id", SCENES)
def test_reconstruction_keeps_physical_identity_and_declared_actions(scene_id):
    spec = load_scene(scene_id)
    if scene_id == "optical_bench":
        old = BASELINE["scenes"][scene_id]
        original_objects = old["objects"]
        original_task = old["task_contract"]
    else:
        path = Path(__file__).parent / "fixtures/dig_site_before_reconstruction.json"
        old = SceneSpec.model_validate(json.loads(path.read_text()))
        original_objects = [obj.model_dump(mode="json") for obj in old.objects]
        original_task = old.task_contract.model_dump(mode="json")
    before = {obj["object_id"]: obj for obj in original_objects}
    assert {obj.object_id for obj in spec.objects} == set(before)
    for obj in spec.objects:
        current = obj.model_dump(mode="json")
        assert {key: current[key] for key in PHYSICAL_FIELDS} == {
            key: before[obj.object_id][key] for key in PHYSICAL_FIELDS
        }
    # Descriptions may be corrected to match the real scanned subject. They
    # must not force artificial grooves or other invented model features.
    task = spec.task_contract.model_dump(mode="json")
    for key in ("ordered_steps", "persistent_targets", "interrupt_target"):
        assert task[key] == original_task[key]
    assert spec.asset_axes == "gltf_y_up"


@pytest.mark.parametrize("scene_id", SCENES)
def test_reconstructed_glbs_embed_usable_materials_and_uvs(scene_id):
    spec = load_scene(scene_id)
    full_pbr = 0
    for entry in [*spec.objects, *spec.environment]:
        doc = glb_json(root() / entry.asset)
        assert all("uri" not in item for item in doc.get("buffers", []))
        assert all("bufferView" in item and "uri" not in item for item in doc.get("images", []))
        if scene_id == "optical_bench" and getattr(entry, "object_id", None) in {"L1", "L2"}:
            glass = [item for item in doc["materials"] if item.get("name") == "BK7_biconvex_optical_glass"]
            assert glass, "The real optical aperture must retain its lens material"
            for material in glass:
                pbr = material["pbrMetallicRoughness"]
                # Physical transmission already conveys transparency. Low
                # BLEND alpha attenuated the glass again in the real viewer.
                assert material.get("alphaMode", "OPAQUE") == "OPAQUE"
                assert pbr.get("baseColorFactor", [1, 1, 1, 1])[3] == 1
                assert pbr["metallicFactor"] == 0
                extensions = material["extensions"]
                assert 0 < extensions["KHR_materials_transmission"]["transmissionFactor"] <= 1
                assert extensions["KHR_materials_ior"]["ior"] > 1
        for mesh in doc["meshes"]:
            for primitive in mesh["primitives"]:
                material = doc["materials"][primitive["material"]]
                pbr = material.get("pbrMetallicRoughness", {})
                assert "NORMAL" in primitive["attributes"]
                if "baseColorTexture" in pbr or "normalTexture" in material:
                    assert "TEXCOORD_0" in primitive["attributes"]
                full_pbr += int("normalTexture" in material and "metallicRoughnessTexture" in pbr)
        asset = load_asset(str(root() / entry.asset), spec.asset_axes)
        for mesh in asset.geometry.values():
            assert len(mesh.faces) and np.isfinite(mesh.vertices).all()
            assert np.isfinite(mesh.vertex_normals).all()
            uv = getattr(mesh.visual, "uv", None)
            if uv is not None:
                assert len(uv) == len(mesh.vertices) and np.isfinite(uv).all()
    assert full_pbr > 0, "The reconstructed scene has lost its embedded PBR surface maps"


@pytest.mark.parametrize("scene_id", SCENES)
def test_rebuilt_bodies_fit_the_declared_training_envelopes(scene_id):
    spec = load_scene(scene_id)
    unchanged_dig_objects = {"FLAG", "STAY"}
    for obj in spec.objects:
        if scene_id == "dig_site" and obj.object_id in unchanged_dig_objects:
            continue
        half = np.asarray(obj.size_m) / 2
        low, high = -half, half.copy()
        if scene_id == "optical_bench" and obj.object_id == "M":
            # The original rear tag plane is y=.034, outside the .0325 half
            # thickness. Preserve that explicit contract, not a resized tag.
            high[1] = obj.interaction.inspect_point_local_m[1]
        for name, part in meshes(spec, obj, Pose()).items():
            assert np.all(part.bounds[0] >= low - 1e-6), (obj.object_id, name, part.bounds, low, high)
            assert np.all(part.bounds[1] <= high + 1e-6), (obj.object_id, name, part.bounds, low, high)


@pytest.mark.parametrize("scene_id,identifier", [("optical_bench", "M"), ("dig_site", "POT3")])
def test_static_inspection_ring_clears_actual_mesh_without_a_task_session(scene_id, identifier):
    spec = load_scene(scene_id)
    obj = object_by_id(spec, identifier)
    cue = geometry_cue(obj, "inspect_back")
    position, look, _ = inspect_view(obj, obj.pose)
    original = local_cue_pool(scene_id, identifier, "highlight").copy()
    centers, cov, _, alpha = splat_arrays(spec, cue, cue.pose, position, look, 0.2)
    assert np.isfinite(cov).all() and np.isfinite(alpha).all()
    np.testing.assert_array_equal(local_cue_pool(scene_id, identifier, "highlight"), original)
    point = cue.model_copy(update={"action": "point"})
    point_centers, *_ = splat_arrays(spec, point, point.pose, position, look, 0.2)
    np.testing.assert_array_equal(point_centers, original)
    basis = basis_from_normal(obj.interaction.inspect_normal_local)
    projected = triangles(meshes(spec, obj, Pose())) @ basis
    # Match the existing inspection regression's 64 spaced surface witnesses,
    # but construct geometric inputs directly instead of executing a plan.
    for center in (centers @ basis)[::128]:
        depths = vertical_hits(projected, center[:2])
        assert not len(depths) or center[2] > depths.max(), (scene_id, identifier, center, depths)


@pytest.mark.parametrize(
    "scene_id,identifier",
    [("optical_bench", name) for name in ("L1", "POST2", "L2", "M", "TARGET")]
    + [("dig_site", name) for name in ("POT3", "TROWEL")],
)
def test_exported_objects_have_real_support_contacts(scene_id, identifier):
    spec = load_scene(scene_id)
    obj = object_by_id(spec, identifier)
    source = triangles(meshes(spec, obj))
    support = environment_triangles(scene_id)
    if scene_id == "optical_bench" and identifier == "TARGET":
        assert_thin_card_support(source, support)
    else:
        assert_supported(source, support)


def test_exported_l1_seats_in_open_post2_with_radial_clearance():
    spec = load_scene("optical_bench")
    lens = object_by_id(spec, "L1")
    receiver = object_by_id(spec, "POST2")
    goal = mating_goal(lens, receiver, receiver.pose, "insert")
    np.testing.assert_allclose(goal.position_m, [0, 0.1, 0.168], atol=1e-8)
    source = meshes(spec, lens, goal)
    shaft_parts = {name: mesh for name, mesh in source.items() if "mounting_post" in name}
    assert shaft_parts, "The actual insertion shaft must remain independently inspectable"
    shaft = combined(shaft_parts)
    sleeve = combined(meshes(spec, receiver))
    centre = transform_points(goal, np.asarray([lens.interaction.mating_pose.position_m]))[0]
    np.testing.assert_allclose(centre, [0, 0.1, 0.103], atol=1e-8)
    top = sleeve.bounds[1, 2]
    assert top > centre[2] + 0.005
    axial = ray_hits(sleeve, [*centre[:2], top + 0.01], np.array([0.0, 0.0, -1.0]))
    assert axial and axial[0]["point"][2] == pytest.approx(centre[2], abs=1e-6)
    # Real cap triangles must bear on the blind seat, not merely share AABBs.
    bottom_contacts(shaft, sleeve)
    # Preserve the existing optical joint's 0.1 mm minimum radial clearance.
    for z in np.linspace(centre[2] + 0.00025, min(top, shaft.bounds[1, 2]) - 0.00025, 3):
        for angle in np.linspace(0, 2 * np.pi, 32, endpoint=False):
            direction = np.array([np.cos(angle), np.sin(angle), 0.0])
            origin = np.array([*centre[:2], z])
            moving = ray_hits(shaft, origin, direction)
            fixed = ray_hits(sleeve, origin, direction)
            assert moving and fixed
            assert fixed[0]["distance_m"] - moving[0]["distance_m"] > 0.0001


def test_m_rotation_keeps_its_vertical_axis_and_rear_inspection_target():
    spec = load_scene("optical_bench")
    mirror = object_by_id(spec, "M")
    axis = np.asarray(mirror.interaction.rotation_axis_local)
    pivot = np.asarray([mirror.interaction.pivot_local_m])
    before = transform_points(mirror.pose, pivot)
    for angle in (0, -7.5, -15):
        pose = rotate_about(mirror.pose, axis, pivot[0], angle)
        np.testing.assert_allclose(matrix(pose)[:3, :3] @ axis, [0, 0, 1], atol=1e-8)
        np.testing.assert_allclose(transform_points(pose, pivot), before, atol=1e-8)
    parts = meshes(spec, mirror, Pose())
    label = [mesh for name, mesh in parts.items() if "rear_serial_label" in name]
    assert len(label) == 1, "Inspection must address the visible real rear identifier"
    label = label[0]
    point = np.asarray(mirror.interaction.inspect_point_local_m)
    assert label.bounds[0, 0] <= point[0] <= label.bounds[1, 0]
    assert label.bounds[0, 2] <= point[2] <= label.bounds[1, 2]
    np.testing.assert_allclose(label.vertices[:, 1], point[1], atol=1e-6)
    assert label.face_normals[:, 1].min() > 0.99
    assert label.visual.material.baseColorTexture is not None


def test_pot3_inspection_hits_a_textured_finite_scanned_wall():
    spec = load_scene("dig_site")
    pot = object_by_id(spec, "POT3")
    parts = meshes(spec, pot, Pose())
    # The scan is split across UV/vertex primitives. Both physical wall faces
    # belong to the complete fragment, not necessarily its largest primitive.
    scan = {name: mesh for name, mesh in parts.items() if "fpan_photogrammetry_sherd" in name}
    assert scan, "The inspection wall must be the scanned fragment, not a label"
    for part in scan.values():
        material = part.visual.material
        assert material.baseColorTexture is not None
        assert material.metallicFactor == 0
        pixels = np.asarray(material.baseColorTexture.convert("RGB"))
        assert np.ptp(pixels.astype(float), axis=(0, 1)).max() > 1
    wall = combined(scan)
    point = np.asarray(pot.interaction.inspect_point_local_m)
    normal = np.asarray(pot.interaction.inspect_normal_local)
    rays = ray_hits(wall, point + normal * 0.10, -normal)
    assert len(rays) >= 2, "The inspection point must face a finite wall, not a flat decal or empty space"
    assert rays[0]["distance_m"] >= 0.10 - 1e-6
    assert rays[1]["distance_m"] - rays[0]["distance_m"] > 0.0001
    assert wall.face_normals[rays[0]["triangle_index"]] @ normal > 0


def test_flag_path_keeps_clear_of_exported_remains_and_terrain():
    spec = load_scene("dig_site")
    flag, bone = (object_by_id(spec, name) for name in ("FLAG", "BONE"))
    goal = mating_goal(flag, bone, bone.pose, "assemble")
    # A geometry-only DisplayCue supplies trajectory inputs; no session, API,
    # store, planner or task completion is created by this test.
    cue = geometry_cue(flag, "assemble", goal_pose=goal, reference_id="BONE")
    obstacles = [environment_triangles("dig_site")]
    obstacles.extend(triangles(meshes(spec, obj)) for obj in spec.objects if obj.object_id != "FLAG")
    obstacle = np.concatenate(obstacles)
    parts = meshes(spec, flag, Pose())
    contact_z = min(part.bounds[0, 2] for part in parts.values())
    poses = path_keyframes(cue) + [
        trajectory(cue, float(t)) for t in np.linspace(0, cue.interaction.duration_s, 81)
    ]
    for index, pose in enumerate(poses):
        inverse = np.linalg.inv(matrix(pose))
        local_obstacle = obstacle @ inverse[:3, :3].T + inverse[:3, 3]
        for name, part in parts.items():
            low, high = part.bounds.copy()
            # Keep the existing 0.75 mm vertical contact tolerance at the base.
            # Per-part boxes conservatively bound the narrow pole and cloth;
            # empty space between them is not treated as moving solid material.
            if low[2] <= contact_z + 1e-9:
                low[2] += min(0.00075, (high[2] - low[2]) / 2)
            hits = intersecting_box_triangles(local_obstacle, low, high)
            assert not len(hits), (index, name, pose.position_m, len(hits), hits[:2].tolist())
