"""Actual engine/CNC exports, evaluated without a task, API or model run.

Rigid paths are checked at finite poses, with finite local surface witnesses and
the shared 0.1 mm collision tolerance. This is not continuous collision proof.
Native Blender and Viser appearance are reviewed separately.
"""

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
import vtk

from holocue.config import load_scene, root, scene_dir, scene_set
from holocue.camera import inspect_view, project
from holocue.models import Pose
from holocue.render_validation import polydata
from holocue.spatial import mating_goal, matrix, path_keyframes, rotate_about, trajectory, transform_points
from panel_optical_geometry import ray_hits
from test_asset_reconstruction import meshes
from test_blocks_drone_assets import assert_actual_surface_clearance, surface_obstacles
from test_optical_dig_assets import (
    geometry_cue,
    object_by_id,
    test_reconstructed_glbs_embed_usable_materials_and_uvs as check_materials,
    test_static_inspection_ring_clears_actual_mesh_without_a_task_session as check_inspection,
)


BASELINE = json.loads((Path(__file__).parent / "fixtures/engine_cnc_before_reconstruction.json").read_text())[
    "scenes"
]
SCENES = ("engine_bay", "cnc_toolchange")
INSERTIONS = [
    ("engine_bay", "PLUG", "PLUGPORT", [0.16, 0.26, 1.076]),
    ("cnc_toolchange", "T09", "POCKET9", [0.20, 0.25, 1.255]),
]
ROTATIONS = [("engine_bay", "CLAMP", 90), ("cnc_toolchange", "MODESWITCH", -90)]


def combined(parts):
    return trimesh.util.concatenate(list(parts.values()))


def actual_world_parts(spec, exclude=None, overrides=None, environment_only=False):
    """Keep entry identities even if two imported source files reuse node names."""
    result = {}
    entries = list(spec.environment) + ([] if environment_only else list(spec.objects))
    for entry in entries:
        identifier = getattr(entry, "object_id", None) or entry.prop_id
        if identifier == exclude:
            continue
        for name, part in meshes(spec, entry, (overrides or {}).get(identifier)).items():
            key = f"{identifier}/{name}"
            assert key not in result
            result[key] = part
    return result


def actual_contact_witnesses(source, support, direction, tolerance=0.001):
    """Find opposing actual faces, including a shoulder above a free lower tip.

    Sample both sides: a smaller support patch can fall between every fixed
    barycentric sample on a large source triangle, and vice versa. Every
    witness remains a pair of actual opposing faces within the same tolerance;
    bounds only reject distant candidates. This proves sampled contact, not
    mass balance, friction, load capacity or dynamic stability.
    """
    direction = np.asarray(direction, dtype=float)
    direction /= np.linalg.norm(direction)
    weights = np.asarray([[i / 4, j / 4, 1 - (i + j) / 4] for i in range(5) for j in range(5 - i)])
    witnesses = []
    seen_witnesses = set()
    for reverse in (False, True):
        sampler, target = (support, source) if reverse else (source, support)
        sign = 1 if reverse else -1
        indices = np.flatnonzero(sampler.face_normals @ direction * sign > 0.5)
        triangles = sampler.triangles[indices]
        nearby = np.all(triangles.max(axis=1) >= target.bounds[0] - tolerance, axis=1)
        nearby &= np.all(triangles.min(axis=1) <= target.bounds[1] + tolerance, axis=1)
        indices = indices[nearby]
        indices = indices[np.argsort(-sampler.area_faces[indices])]
        locator = vtk.vtkStaticCellLocator()
        locator.SetDataSet(polydata(target))
        locator.BuildLocator()
        seen_samples = set()
        for index in indices:
            for point in weights @ sampler.triangles[index]:
                sample_key = tuple(np.round(point, 9))
                if sample_key in seen_samples:
                    continue
                seen_samples.add(sample_key)
                if np.any(point < target.bounds[0] - tolerance) or np.any(
                    point > target.bounds[1] + tolerance
                ):
                    continue
                t, cell, sub = vtk.mutable(0.0), vtk.mutable(0), vtk.mutable(0)
                hit, pcoords = [0.0] * 3, [0.0] * 3
                found = locator.IntersectWithLine(
                    point - sign * direction * tolerance,
                    point + sign * direction * tolerance,
                    1e-10,
                    t,
                    hit,
                    pcoords,
                    sub,
                    cell,
                )
                if found and target.face_normals[int(cell)] @ direction * sign < -0.5:
                    assert np.linalg.norm(np.asarray(hit) - point) <= tolerance + 1e-8
                    # Return source-side positions in both directions so the
                    # caller can still verify the original shoulder plane.
                    witness = np.asarray(hit) if reverse else point
                    witness_key = tuple(np.round(witness, 9))
                    if witness_key in seen_witnesses:
                        continue
                    seen_witnesses.add(witness_key)
                    witnesses.append(witness)
                    if len(witnesses) >= 9:
                        projected = np.asarray(witnesses) - np.outer(
                            np.asarray(witnesses) @ direction, direction
                        )
                        singular = np.linalg.svd(projected - projected.mean(axis=0), compute_uv=False)
                        if np.ptp(projected, axis=0).max() > 0.005 and singular[1] > 1e-6:
                            return np.asarray(witnesses)
    raise AssertionError(("no separated actual support patch", len(witnesses), direction.tolist(), tolerance))


def completed_geometry_parts(spec):
    """Direct preceding rigid poses for an inspection, without executing tasks."""
    _, identifier, angle = next(row for row in ROTATIONS if row[0] == spec.scene_id)
    rotator = object_by_id(spec, identifier)
    _, source, target, _ = next(row for row in INSERTIONS if row[0] == spec.scene_id)
    moving, receiver = object_by_id(spec, source), object_by_id(spec, target)
    return actual_world_parts(
        spec,
        overrides={
            identifier: rotate_about(
                rotator.pose,
                rotator.interaction.rotation_axis_local,
                rotator.interaction.pivot_local_m,
                angle,
            ),
            source: mating_goal(moving, receiver, receiver.pose, "insert"),
        },
    )


def visible_surface_points(points, position, locator):
    """Return finite actual surface witnesses reached by the first scene triangle."""
    position = np.asarray(position)
    visible = []
    for point in points:
        direction = point - position
        direction /= np.linalg.norm(direction)
        t, cell, sub = vtk.mutable(0.0), vtk.mutable(0), vtk.mutable(0)
        hit, pcoords = [0.0] * 3, [0.0] * 3
        found = locator.IntersectWithLine(
            position, point + direction * 0.00001, 1e-10, t, hit, pcoords, sub, cell
        )
        if found and np.linalg.norm(np.asarray(hit) - point) < 1e-6:
            visible.append(point)
    return np.asarray(visible)


def visible_actual_face_centers(part, position, locator, face_mask):
    centers = part.triangles_center
    facing = np.einsum("ij,ij->i", part.face_normals, np.asarray(position) - centers) > 0
    return visible_surface_points(centers[facing & face_mask], position, locator)


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


@pytest.mark.parametrize("sid", SCENES)
def test_actual_bodies_fit_original_body_and_interface_envelopes(sid):
    spec = load_scene(sid)
    for obj in spec.objects:
        low, high = np.asarray(BASELINE[sid]["exported_object_bounds"][obj.object_id])
        # The saved export includes intentional head, pull-stud and inspection
        # allowances outside size_m. Mature sources may be smaller inside it.
        low = np.minimum(low, -np.asarray(obj.size_m) / 2)
        high = np.maximum(high, np.asarray(obj.size_m) / 2)
        for name, part in meshes(spec, obj, Pose()).items():
            if name.split("/")[-1].startswith("label_"):
                continue
            assert np.all(part.bounds[0] >= low - 1e-6), (sid, obj.object_id, name, part.bounds, low)
            assert np.all(part.bounds[1] <= high + 1e-6), (sid, obj.object_id, name, part.bounds, high)


@pytest.mark.parametrize(
    "sid,identifier,direction",
    [("engine_bay", name, [0, 0, 1]) for name in ["PLUG", "PLUGPORT", "OILCAP", "CONN"]]
    + [("engine_bay", name, [1, 0, 0]) for name in ["CLAMP", "TENSIONER"]]
    + [("cnc_toolchange", name, [0, 0, 1]) for name in ["T09", "POCKET9", "T03"]]
    + [("cnc_toolchange", name, [0, -1, 0]) for name in ["MODESWITCH", "MAG", "PANEL"]],
)
def test_initial_objects_have_actual_support_or_mount_contact(sid, identifier, direction):
    spec = load_scene(sid)
    source = combined(meshes(spec, object_by_id(spec, identifier)))
    support = combined(actual_world_parts(spec, environment_only=True))
    actual_contact_witnesses(source, support, direction)


@pytest.mark.parametrize("sid,source,target,position", INSERTIONS)
def test_original_inserted_endpoint_has_actual_shoulder_support(sid, source, target, position):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in [source, target])
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    np.testing.assert_allclose(goal.position_m, position, atol=1e-8)
    contacts = actual_contact_witnesses(
        combined(meshes(spec, moving, goal)), combined(meshes(spec, receiver)), [0, 0, 1], tolerance=0.0001
    )
    if sid == "cnc_toolchange":
        # This is the original flange contract, not the lower cutting-tool tip.
        np.testing.assert_allclose(contacts[:, 2], 1.24, atol=0.0001)


@pytest.mark.parametrize("sid,source,target,position", INSERTIONS)
def test_real_receiver_cavity_contains_the_inserted_lower_body(sid, source, target, position):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in [source, target])
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    body, bore = combined(meshes(spec, moving, goal)), combined(meshes(spec, receiver))
    contacts = actual_contact_witnesses(body, bore, [0, 0, 1], tolerance=0.0001)
    floor, seat = body.bounds[0, 2], contacts[:, 2].mean()
    assert seat - floor > 0.005, "A free lower electrode/tool must enter a real cavity"
    center = np.asarray(position[:2])
    top = bore.bounds[1, 2] + 0.01
    axial = ray_hits(bore, [*center, top], np.array([0.0, 0.0, -1.0]))
    assert not axial or axial[0]["point"][2] <= floor - 0.0001, "The central opening stops above the free tip"
    # At three depths and sixteen azimuths, compare the actual outer tool face
    # with the actual inner receiver wall. These are finite radial witnesses.
    outer = max(np.linalg.norm(body.vertices[:, :2] - center, axis=1)) + 0.02
    count = 0
    for z in np.linspace(floor, seat, 5)[1:-1]:
        for angle in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            radial = np.array([np.cos(angle), np.sin(angle), 0.0])
            origin = np.array([*center, z])
            source_hits = ray_hits(body, origin + radial * outer, -radial)
            receiver_hits = ray_hits(bore, origin, radial)
            assert source_hits and receiver_hits, (sid, z, angle, "missing lower body or real cavity wall")
            source_radius = (np.asarray(source_hits[0]["point"]) - origin) @ radial
            assert receiver_hits[0]["distance_m"] - source_radius >= 0.0001, (sid, z, angle)
            count += 1
    assert count == 48


@pytest.mark.parametrize("sid,identifier", [("engine_bay", "PLUGPORT"), ("cnc_toolchange", "POCKET9")])
def test_receiver_components_meet_without_duplicate_overlapping_solids(sid, identifier):
    spec = load_scene(sid)
    parts = meshes(spec, object_by_id(spec, identifier), Pose())
    for name, part in parts.items():
        if name.split("/")[-1].startswith("label_"):
            continue
        fixed = surface_obstacles({key: mesh for key, mesh in parts.items() if key != name})
        # Coplanar mating faces are allowed; duplicated overlapping rim solids
        # are not. Use the same complete-triangle/local-containment method and
        # unchanged 0.1 mm tolerance as the original-path body checks.
        assert_actual_surface_clearance(part, fixed, moving_parts=[part])


@pytest.mark.parametrize("sid", SCENES)
def test_every_nonlabel_environment_triangle_is_a_collision_obstacle(sid):
    parts = actual_world_parts(load_scene(sid), environment_only=True)
    expected = {name: part for name, part in parts.items() if not name.split("/")[-1].startswith("label_")}
    obstacles = surface_obstacles(parts)
    assert {name for name, *_ in obstacles} == set(expected)
    assert all(data.GetNumberOfCells() == len(part.faces) > 0 for _, part, data, _ in obstacles)
    assert sum(len(part.faces) for _, part, *_ in obstacles) == sum(
        len(part.faces) for part in expected.values()
    )


@pytest.mark.parametrize("sid,identifier,angle", ROTATIONS)
def test_entire_rotating_asset_clears_37_original_poses(sid, identifier, angle):
    spec = load_scene(sid)
    obj = object_by_id(spec, identifier)
    local_parts = list(meshes(spec, obj, Pose()).values())
    obstacles = surface_obstacles(actual_world_parts(spec, exclude=identifier))
    axis, pivot = obj.interaction.rotation_axis_local, obj.interaction.pivot_local_m
    world_axis = matrix(obj.pose)[:3, :3] @ axis
    np.testing.assert_allclose(world_axis, [1, 0, 0] if sid == "engine_bay" else [0, -1, 0], atol=1e-8)
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


@pytest.mark.parametrize("sid,source,target,position", INSERTIONS)
def test_entire_inserted_asset_clears_original_keyframes_and_61_poses(sid, source, target, position):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in [source, target])
    goal = mating_goal(moving, receiver, receiver.pose, "insert")
    cue = geometry_cue(moving, "insert", goal_pose=goal, reference_id=target)
    previous = next((identifier, angle) for scene, identifier, angle in ROTATIONS if scene == sid)
    rotator = object_by_id(spec, previous[0])
    prior_pose = rotate_about(
        rotator.pose, rotator.interaction.rotation_axis_local, rotator.interaction.pivot_local_m, previous[1]
    )
    obstacles = surface_obstacles(
        actual_world_parts(spec, exclude=source, overrides={previous[0]: prior_pose})
    )
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


@pytest.mark.parametrize("sid,identifier", [("engine_bay", "CONN"), ("cnc_toolchange", "T03")])
def test_original_inspection_prompt_clears_actual_exported_mesh(sid, identifier):
    check_inspection(sid, identifier)


def test_conn_has_real_open_terminals_visible_from_the_original_inspection_camera():
    spec = load_scene("engine_bay")
    obj = object_by_id(spec, "CONN")
    parts = meshes(spec, obj, Pose())
    # This is the documented contact-metal primitive of the retained mature
    # female source. The shell/insulator cannot substitute for terminal faces.
    terminals = [part for name, part in parts.items() if "Arrel_female_connector_Object_8" in name]
    assert terminals
    assert all(part.visual.material.metallicFactor > 0.5 for part in terminals)
    contacts = trimesh.util.concatenate(terminals)
    vertices, inverse = np.unique(contacts.vertices, axis=0, return_inverse=True)
    welded = trimesh.Trimesh(vertices, inverse[contacts.faces], process=False)
    groups = trimesh.graph.connected_components(welded.face_adjacency, nodes=np.arange(len(welded.faces)))
    assert len(groups) >= 2, "The source must retain distinct real terminals"
    whole = combined(parts)
    world = combined(completed_geometry_parts(spec))
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(polydata(world))
    locator.BuildLocator()
    position, _, _ = inspect_view(obj, obj.pose)
    for group in groups:
        terminal = welded.submesh([group], append=True, repair=False)
        origin = terminal.bounds.mean(axis=0)
        origin[1] = whole.bounds[1, 1] + 0.01
        hits = ray_hits(whole, origin, np.array([0.0, -1.0, 0.0]))
        metal = ray_hits(terminal, origin, np.array([0.0, -1.0, 0.0]))
        assert hits and metal
        assert terminal.bounds[1, 1] - hits[0]["point"][1] > 0.005, "A terminal mouth is capped or flattened"
        assert abs(hits[0]["distance_m"] - metal[0]["distance_m"]) < 1e-6
        # Inspect each actual barrel mouth, not just one convenient connector
        # point. Rear blind ends need not all be visible through deep holes.
        mouth = terminal.triangles_center[:, 1] >= terminal.bounds[1, 1] - 0.003
        world_terminal = terminal.copy().apply_transform(matrix(obj.pose))
        visible = visible_actual_face_centers(world_terminal, position, locator, mouth)
        assert len(visible) >= 3, (terminal.bounds.tolist(), len(visible))
        assert np.ptp(visible[:, [0, 2]], axis=0).max() > min(terminal.extents[[0, 2]]) / 4


def test_t03_inspection_shows_a_real_neck_and_wider_retention_head():
    spec = load_scene("cnc_toolchange")
    obj = object_by_id(spec, "T03")
    parts = meshes(spec, obj, Pose())
    features = {name: part for name, part in parts.items() if "pull_stud_neck_and_retention_head" in name}
    assert features, "The inspection feature must be a real retained stud, not a decal"
    assert all(part.visual.material.metallicFactor > 0.5 for part in features.values())
    stud = combined(features)
    neck_z = obj.interaction.inspect_point_local_m[2]
    assert stud.bounds[0, 2] < neck_z < stud.bounds[1, 2]
    head_z = stud.bounds[1, 2] - min(0.003, (stud.bounds[1, 2] - neck_z) / 4)
    normal = np.asarray(obj.interaction.inspect_normal_local)
    front_angle = np.arctan2(normal[1], normal[0])
    points = []
    for angle in front_angle + np.deg2rad([-35, 0, 35]):
        radial = np.array([np.cos(angle), np.sin(angle), 0.0])
        radii = []
        for z in (neck_z, head_z):
            center = np.array([0.0, 0.0, z])
            hits = ray_hits(stud, center + radial * 0.05, -radial)
            assert hits, (z, angle, "missing actual stud surface")
            point = np.asarray(hits[0]["point"])
            radii.append((point - center) @ radial)
            points.append(point)
        assert radii[1] - radii[0] > 0.001, "The retained head must extend beyond its actual neck"
    # Three distinct azimuths on both neck and head must be in the declared
    # inspection view and unobscured by the full scene after the preceding
    # rigid motions. This does not claim all faces of the stud are visible.
    world_points = transform_points(obj.pose, points)
    position, look, up = inspect_view(obj, obj.pose)
    projected, _ = project(world_points, position, look, aspect=1.6, up=up)
    assert np.abs(projected).max() <= 0.860001
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(polydata(combined(completed_geometry_parts(spec))))
    locator.BuildLocator()
    visible = visible_surface_points(world_points, position, locator)
    assert len(visible) == 6, ("obscured retention feature", len(visible))


def test_contact_witnesses_resolve_a_supported_flange_with_a_free_tip():
    flange = trimesh.creation.cylinder(radius=0.030, height=0.010)
    flange.apply_translation([0, 0, 0.005])
    shank = trimesh.creation.cylinder(radius=0.008, height=0.080)
    shank.apply_translation([0, 0, -0.040])
    body = trimesh.util.concatenate([flange, shank])
    seat = trimesh.creation.annulus(r_min=0.010, r_max=0.040, height=0.010)
    seat.apply_translation([0, 0, -0.005])
    witnesses = actual_contact_witnesses(body, seat, [0, 0, 1], tolerance=0.0001)
    np.testing.assert_allclose(witnesses[:, 2], 0, atol=1e-8)
    body.apply_translation([0, 0, 0.002])
    with pytest.raises(AssertionError, match="no separated actual support patch"):
        actual_contact_witnesses(body, seat, [0, 0, 1], tolerance=0.0001)


@pytest.mark.parametrize("small_source", [False, True])
def test_contact_witnesses_resolve_a_small_patch_on_coarse_faces(small_source):
    # A 12 x 18 mm contact inside a coarse 400 x 300 mm face falls between
    # its quarter-barycentric samples. Both meshes still have real contact.
    # Swap which side has the small patch: the result must be symmetric.
    large, small = (0.4, 0.3), (0.012, 0.018)
    source = trimesh.creation.box(extents=(*(small if small_source else large), 0.02))
    support = trimesh.creation.box(extents=(*(large if small_source else small), 0.01))
    source.apply_translation([*((0.043, 0.047) if small_source else (0, 0)), 0.01])
    support.apply_translation([*((0, 0) if small_source else (0.043, 0.047)), -0.005])
    witnesses = actual_contact_witnesses(source, support, [0, 0, 1], tolerance=0.0001)
    assert len(witnesses) >= 9
    np.testing.assert_allclose(witnesses[:, 2], 0, atol=1e-8)
    source.apply_translation([0, 0, 0.002])
    with pytest.raises(AssertionError, match="no separated actual support patch"):
        actual_contact_witnesses(source, support, [0, 0, 1], tolerance=0.0001)
    source.apply_translation([0, 0, -0.002])
    source = trimesh.Trimesh(
        vertices=source.vertices.copy(), faces=source.faces[:, ::-1].copy(), process=False
    )
    with pytest.raises(AssertionError, match="no separated actual support patch"):
        actual_contact_witnesses(source, support, [0, 0, 1], tolerance=0.0001)
