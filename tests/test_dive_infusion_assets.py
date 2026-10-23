"""Actual dive/infusion exports without task, API or model execution.

Rigid paths use finite poses and finite actual-surface witnesses at the shared
0.1 mm collision tolerance. They do not prove continuous collision freedom or
dynamic stability. Native Blender and Viser appearance and the literal training-
label text are reviewed directly.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
import vtk

from holocue.camera import inspect_view, project
from holocue.config import load_scene, root, scene_dir, scene_set
from holocue.models import Pose
from holocue.render_validation import polydata
from holocue.spatial import mating_goal, matrix, path_keyframes, rotate_about, trajectory, transform_points
from panel_optical_geometry import ray_hits
from test_asset_reconstruction import glb_json, meshes
from test_blocks_drone_assets import assert_actual_surface_clearance, surface_obstacles
from test_engine_cnc_assets import (
    actual_contact_witnesses,
    actual_world_parts,
    combined,
    test_every_nonlabel_environment_triangle_is_a_collision_obstacle as check_surface_coverage,
    visible_surface_points,
)
from test_optical_dig_assets import (
    geometry_cue,
    object_by_id,
    test_reconstructed_glbs_embed_usable_materials_and_uvs as check_materials,
    test_static_inspection_ring_clears_actual_mesh_without_a_task_session as check_inspection,
)


BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/dive_infusion_before_reconstruction.json").read_text()
)["scenes"]
SCENES = ("dive_fillstation", "infusion_ward")
INSERTIONS = [
    ("dive_fillstation", "QRC", "VALVE", [0.35, -0.009, 1.00]),
    ("infusion_ward", "PUMPCASSETTE", "SLOT2", [0.05, 0.198, 1.30]),
]
ROTATIONS = [("dive_fillstation", "STEM", 90), ("infusion_ward", "STOPCOCK", -90)]
LABELS = [("dive_fillstation", name) for name in ("BOTTLE1", "BOTTLE2", "BOTTLE3")] + [
    ("infusion_ward", name) for name in ("BAG1", "BAG2")
]


# These RGB pixels were extracted from the formal GLBs and directly viewed:
# TRAINING BOTTLE1/2/3 and TRAINING A / ID BAG1, TRAINING B / ID BAG2.
# Bind the reviewed exported text, rather than redrawing the font to derive
# an expectation from the builder under test.
VERIFIED_LABEL_RGB = {
    "BOTTLE1": ((512, 292), "64006c71a77f0ae5052c16261171f7d5d85fddb38c70a3b4c5536cb3a9e8f772"),
    "BOTTLE2": ((512, 292), "9712f7e413bb10ab6cb374d7afb543019021247ab061088723a704d512a0e06e"),
    "BOTTLE3": ((512, 292), "ddbc141cf2bbfe37ba48aa34082b0801c4ec389437c073bd3f5b0c4290097af7"),
    "BAG1": ((512, 462), "93af1bc8c8add7f24036690c64dd0768872d84a147275da0d974164416b30d51"),
    "BAG2": ((512, 462), "9b262a11f2a99da92603f424d69c22de523f8641437db9ce9880640830fb5550"),
}


def insertion_override(spec):
    _, source, target, _ = next(row for row in INSERTIONS if row[0] == spec.scene_id)
    moving, receiver = (object_by_id(spec, name) for name in (source, target))
    return {source: mating_goal(moving, receiver, receiver.pose, "insert")}


@pytest.mark.parametrize("sid", SCENES)
def test_complete_original_scene_contract_is_unchanged(sid):
    current = json.loads((scene_dir(sid) / "scene.json").read_text())
    for entry in current["objects"] + current["environment"]:
        prefix = f"scenes/{scene_set()}/{sid}/"
        assert entry["asset"].startswith(prefix)
        entry["asset"] = entry["asset"].replace(prefix, f"scenes/{sid}/", 1)
    assert current == BASELINE[sid]["scene_json"]


@pytest.mark.parametrize("sid", SCENES)
def test_embedded_materials_uvs_and_normals(sid):
    check_materials(sid)
    if sid == "infusion_ward":
        spec = load_scene(sid)
        for identifier in ("BAG1", "BAG2"):
            obj = object_by_id(spec, identifier)
            bodies = [
                part for name, part in meshes(spec, obj, Pose()).items() if "ethan_cragun_water_bag" in name
            ]
            assert bodies
            materials = glb_json(root() / obj.asset)["materials"]
            for body in bodies:
                material = body.visual.material
                record = next(item for item in materials if item.get("name") == material.name)
                transmission = (
                    record.get("extensions", {})
                    .get("KHR_materials_transmission", {})
                    .get("transmissionFactor", 0)
                )
                assert material.metallicFactor == 0
                if transmission > 0:
                    assert transmission <= 1
                else:
                    # Check actual body UVs, not unrelated transparent atlas
                    # pixels or the alphaMode string alone. The opaque printed
                    # training label is a separate surface.
                    assert material.alphaMode == "BLEND"
                    rgba = trimesh.visual.color.uv_to_color(
                        body.visual.uv[body.faces].mean(axis=1), material.baseColorTexture
                    )
                    factor = 1 if material.baseColorFactor is None else material.baseColorFactor[3] / 255
                    alpha = rgba[:, 3] / 255 * factor
                    assert np.mean((alpha > 0.02) & (alpha < 0.98)) > 0.5


@pytest.mark.parametrize("sid", SCENES)
def test_actual_bodies_fit_original_body_and_interface_envelopes(sid):
    spec = load_scene(sid)
    for obj in spec.objects:
        low, high = np.asarray(BASELINE[sid]["exported_object_bounds"][obj.object_id])
        # Saved exports include original lever, suspension-eye and guide-pin
        # allowances. Mature sources can be smaller and need not fill size_m.
        low = np.minimum(low, -np.asarray(obj.size_m) / 2)
        high = np.maximum(high, np.asarray(obj.size_m) / 2)
        for name, part in meshes(spec, obj, Pose()).items():
            if name.split("/")[-1].startswith("label_"):
                continue
            assert np.all(part.bounds[0] >= low - 1e-6), (sid, obj.object_id, name, part.bounds, low)
            assert np.all(part.bounds[1] <= high + 1e-6), (sid, obj.object_id, name, part.bounds, high)


@pytest.mark.parametrize(
    "sid,identifier,direction",
    [("dive_fillstation", name, [0, 0, 1]) for name in ("QRC", "VALVE", "BOTTLE1", "BOTTLE2", "BOTTLE3")]
    + [("dive_fillstation", name, [0, -1, 0]) for name in ("STEM", "GAUGES")]
    + [("infusion_ward", name, [0, 0, 1]) for name in ("PUMPCASSETTE", "BAG1", "BAG2")]
    + [("infusion_ward", name, [0, -1, 0]) for name in ("SLOT2", "STOPCOCK", "MONITOR")],
)
def test_initial_objects_have_actual_support_or_mount_contact(sid, identifier, direction):
    spec = load_scene(sid)
    source = combined(meshes(spec, object_by_id(spec, identifier)))
    # A valve may be carried by its bottle, and a bag by the upper inside of
    # its suspension eye. The actual opposing faces decide contact, not AABBs
    # or a requirement that every object sit on an environment floor plane.
    support = combined(actual_world_parts(spec, exclude=identifier))
    actual_contact_witnesses(source, support, direction)


@pytest.mark.parametrize("sid,source,target,position", INSERTIONS)
def test_original_inserted_endpoint_has_actual_vertical_support(sid, source, target, position):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in (source, target))
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    np.testing.assert_allclose(goal.position_m, position, atol=1e-8)
    # Axial coincidence alone is not support. Both installed objects require
    # actual lower faces opposing a real cradle or rail in the complete scene.
    actual_contact_witnesses(
        combined(meshes(spec, moving, goal)),
        combined(actual_world_parts(spec, exclude=source)),
        [0, 0, 1],
        tolerance=0.0001,
    )


@pytest.mark.parametrize("sid", SCENES)
def test_every_nonlabel_environment_triangle_is_a_collision_obstacle(sid):
    check_surface_coverage(sid)


@pytest.mark.parametrize("sid,source,target,position", INSERTIONS)
def test_entire_inserted_asset_clears_original_keyframes_and_61_poses(sid, source, target, position):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in (source, target))
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    np.testing.assert_allclose(goal.position_m, position, atol=1e-8)
    cue = geometry_cue(moving, "insert", goal_pose=goal, reference_id=target)
    # In both original contracts insertion precedes rotation. Retain the
    # original starting poses for every other object while checking this path.
    obstacles = surface_obstacles(actual_world_parts(spec, exclude=source))
    local_parts = list(meshes(spec, moving, Pose()).values())
    poses = path_keyframes(cue) + [
        trajectory(cue, float(t)) for t in np.linspace(0, cue.interaction.duration_s, 61)
    ]
    for index, pose in enumerate(poses):
        transformed = [part.copy().apply_transform(matrix(pose)) for part in local_parts]
        try:
            assert_actual_surface_clearance(
                trimesh.util.concatenate(transformed), obstacles, moving_parts=transformed
            )
        except AssertionError as error:
            raise AssertionError(
                (sid, source, "insertion pose", index, pose.position_m, str(error))
            ) from error


@pytest.mark.parametrize("sid,identifier,angle", ROTATIONS)
def test_entire_rotating_asset_clears_37_poses_with_installed_source(sid, identifier, angle):
    spec = load_scene(sid)
    obj = object_by_id(spec, identifier)
    local_parts = list(meshes(spec, obj, Pose()).values())
    obstacles = surface_obstacles(
        actual_world_parts(spec, exclude=identifier, overrides=insertion_override(spec))
    )
    axis, pivot = obj.interaction.rotation_axis_local, obj.interaction.pivot_local_m
    np.testing.assert_allclose(matrix(obj.pose)[:3, :3] @ axis, [0, -1, 0], atol=1e-8)
    for index, value in enumerate(np.linspace(0, angle, 37)):
        pose = rotate_about(obj.pose, axis, pivot, float(value))
        np.testing.assert_allclose(
            transform_points(pose, [pivot]), transform_points(obj.pose, [pivot]), atol=1e-8
        )
        transformed = [part.copy().apply_transform(matrix(pose)) for part in local_parts]
        try:
            assert_actual_surface_clearance(
                trimesh.util.concatenate(transformed), obstacles, moving_parts=transformed
            )
        except AssertionError as error:
            raise AssertionError(
                (sid, identifier, "rotation pose", index, float(value), str(error))
            ) from error


@pytest.mark.parametrize("sid,identifier", LABELS)
def test_original_inspection_prompt_clears_actual_exported_mesh(sid, identifier):
    check_inspection(sid, identifier)


@pytest.mark.parametrize("sid,identifier", LABELS)
def test_actual_training_label_texture_and_surface_are_visible(sid, identifier):
    spec = load_scene(sid)
    obj = object_by_id(spec, identifier)
    parts = meshes(spec, obj, Pose())
    labels = {name: part for name, part in parts.items() if "training_serial_label" in name}
    assert labels, (identifier, "missing actual training-label surface")
    for name, part in labels.items():
        texture = getattr(part.visual.material, "baseColorTexture", None)
        assert texture is not None, (name, "label text must exist in the exported texture")
        material = part.visual.material
        assert material.alphaMode in (None, "OPAQUE")
        assert material.baseColorFactor is None or material.baseColorFactor[3] == 255
        assert np.asarray(texture.convert("RGBA"))[:, :, 3].min() == 255
        pixels = np.asarray(texture.convert("RGB"))
        expected_size, expected_pixels = VERIFIED_LABEL_RGB[identifier]
        assert texture.size == expected_size
        assert hashlib.sha256(pixels.tobytes()).hexdigest() == expected_pixels, (
            identifier,
            "training text differs from the directly reviewed export",
        )
        assert min(pixels.shape[:2]) >= 64
        assert np.ptp(pixels.astype(float).mean(axis=2)) > 80, (name, "unreadable flat or low-contrast label")
        assert len(np.unique(pixels.reshape(-1, 3), axis=0)) > 16
        assert part.visual.uv is not None and np.isfinite(part.visual.uv).all()
    label = combined(labels)
    normal = np.asarray(obj.interaction.inspect_normal_local, dtype=float)
    point = np.asarray(obj.interaction.inspect_point_local_m, dtype=float)
    hits = ray_hits(label, point + 0.10 * normal, -normal)
    assert hits and np.linalg.norm(np.asarray(hits[0]["point"]) - point) < 0.005
    assert label.face_normals[hits[0]["triangle_index"]] @ normal > 0.9
    # Interior barycentric witnesses come from the exported label triangles.
    # Their first scene hits must be the label, including after the preceding
    # insertion. Exact text is checked on extracted images, not inferred from
    # semantic node names or by redrawing the implementation's font.
    weights = np.asarray([[i / 5, j / 5, 1 - (i + j) / 5] for i in range(1, 5) for j in range(1, 5 - i)])
    local = np.unique(np.round(np.einsum("wj,tjk->twk", weights, label.triangles).reshape(-1, 3), 9), axis=0)
    world = transform_points(obj.pose, local)
    position, look, up = inspect_view(obj, obj.pose)
    projected, _ = project(world, position, look, aspect=1.6, up=up)
    assert np.abs(projected).max() <= 0.860001
    for overrides in ({}, insertion_override(spec)):
        locator = vtk.vtkStaticCellLocator()
        locator.SetDataSet(polydata(combined(actual_world_parts(spec, overrides=overrides))))
        locator.BuildLocator()
        visible = visible_surface_points(world, position, locator)
        assert len(visible) >= max(9, int(np.ceil(0.9 * len(world)))), (
            identifier,
            "visible label witnesses",
            len(visible),
            len(world),
        )


def test_qrc_open_channel_and_receiver_have_actual_radial_clearance():
    spec = load_scene("dive_fillstation")
    moving, receiver = (object_by_id(spec, name) for name in ("QRC", "VALVE"))
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    moving_parts = meshes(spec, moving, goal)
    nose_parts = {name: part for name, part in moving_parts.items() if "teaching_open_mating_spigot" in name}
    assert len(nose_parts) == 1
    nose = combined(nose_parts)
    source_body = combined(
        {name: part for name, part in moving_parts.items() if not name.split("/")[-1].startswith("label_")}
    )
    receiving = combined(meshes(spec, receiver))
    axis = np.asarray(goal.position_m, dtype=float)
    tip_y = transform_points(goal, [moving.interaction.mating_pose.position_m])[0, 1]
    assert nose.bounds[1, 1] == pytest.approx(tip_y, abs=1e-6)
    mouth_y = receiving.bounds[0, 1]
    assert tip_y - mouth_y > 0.005, "The nose must enter a real receiver, not end in empty space"
    # Finite rays at three actual overlap depths inspect both sides of the
    # hollow spigot wall and the mature threaded receiver. An omitted inner
    # wall cannot pass simply because the outside shell looks tubular.
    for y in np.linspace(mouth_y + 0.0005, tip_y - 0.0005, 3):
        center = axis.copy()
        center[1] = y
        for angle in np.linspace(0.075, 2 * np.pi + 0.075, 24, endpoint=False):
            radial = np.array([np.cos(angle), 0.0, np.sin(angle)])
            male = ray_hits(nose, center, radial)
            female = ray_hits(receiving, center, radial)
            assert len(male) >= 2 and female, (y, angle, "missing inner/outer/bore surface")
            assert 0.0035 < male[0]["distance_m"] < 0.0045
            assert male[-1]["distance_m"] - male[0]["distance_m"] > 0.001
            assert female[0]["distance_m"] - male[-1]["distance_m"] > 0.0001, (y, angle, male, female[:1])
    # The real complete coupling retains an axial channel. Pure printed
    # decals do not substitute for, or close, a physical pressure-free bore.
    offsets = [(0.0, 0.0)] + [
        (0.003 * np.cos(a), 0.003 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)
    ]
    for x, z in offsets:
        origin = axis + [x, 0, z]
        origin[1] = source_body.bounds[0, 1] - 0.001
        hits = ray_hits(source_body, origin, np.array([0.0, 1.0, 0.0]))
        assert not hits or hits[0]["point"][1] > tip_y + 0.0001, ("capped coupling channel", origin, hits[:1])
        origin[1] = mouth_y - 0.001
        hits = ray_hits(receiving, origin, np.array([0.0, 1.0, 0.0]))
        assert not hits or hits[0]["point"][1] > tip_y + 0.0001, (
            "receiver cap before the original tip",
            origin,
            hits[:1],
        )


def test_cassette_four_real_guide_pins_enter_open_receiver_bores():
    spec = load_scene("infusion_ward")
    moving, receiver = (object_by_id(spec, name) for name in ("PUMPCASSETTE", "SLOT2"))
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    moving_parts, receiving_parts = meshes(spec, moving, goal), meshes(spec, receiver)
    pins = {name: part for name, part in moving_parts.items() if "rear_guiding_pin" in name}
    plates = {name: part for name, part in receiving_parts.items() if "receiver_bored_guide_plate" in name}
    assert len(pins) == 4 and len(plates) == 1
    plate, receiving = combined(plates), combined(receiving_parts)
    for name, pin in pins.items():
        center = pin.bounds.mean(axis=0)
        begin = max(pin.bounds[0, 1], plate.bounds[0, 1])
        end = min(pin.bounds[1, 1], plate.bounds[1, 1])
        assert end - begin > 0.002, (name, "no meaningful guide engagement")
        for y in np.linspace(begin + 0.0002, end - 0.0002, 3):
            center[1] = y
            for angle in np.linspace(0.075, 2 * np.pi + 0.075, 24, endpoint=False):
                radial = np.array([np.cos(angle), 0.0, np.sin(angle)])
                male, female = ray_hits(pin, center, radial), ray_hits(receiving, center, radial)
                assert male and female, (name, y, angle, "missing actual guide wall")
                assert male[0]["distance_m"] > 0.001
                assert female[0]["distance_m"] - male[0]["distance_m"] > 0.0001, (
                    name,
                    y,
                    angle,
                    male[:1],
                    female[:1],
                )
        center[1] = receiving.bounds[0, 1] - 0.001
        hits = ray_hits(receiving, center, np.array([0.0, 1.0, 0.0]))
        assert not hits or hits[0]["point"][1] > pin.bounds[1, 1] + 0.0001, (
            name,
            "blocked guide approach",
            hits[:1],
        )
        center[1] = plate.bounds[0, 1] - 0.001
        hits = ray_hits(plate, center, np.array([0.0, 1.0, 0.0]))
        assert not hits or hits[0]["point"][1] > plate.bounds[1, 1] + 0.0001, (
            name,
            "guide hole is capped",
            hits[:1],
        )
