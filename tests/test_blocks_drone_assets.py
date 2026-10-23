"""Real exported teaching assets, using direct geometry without task execution."""

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from holocue.config import load_scene, root, scene_dir, scene_set
from holocue.render_validation import polydata
from holocue.models import Pose
from holocue.spatial import mating_goal, matrix, path_keyframes, rotate_about, trajectory, transform_points
from panel_optical_geometry import distances, ray_hits
from test_asset_reconstruction import assert_supported, environment_triangles, meshes, triangles
from test_optical_dig_assets import (
    geometry_cue,
    object_by_id,
    test_reconstructed_glbs_embed_usable_materials_and_uvs as check_materials,
    test_static_inspection_ring_clears_actual_mesh_without_a_task_session as check_inspection,
)


BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/blocks_drone_before_reconstruction.json").read_text()
)["scenes"]


@pytest.mark.parametrize("sid", ["blocks", "drone_bench"])
def test_complete_scene_contract_is_unchanged(sid):
    current = json.loads((scene_dir(sid) / "scene.json").read_text())
    for entry in current["objects"] + current["environment"]:
        prefix = f"scenes/{scene_set()}/{sid}/"
        assert entry["asset"].startswith(prefix)
        entry["asset"] = entry["asset"].replace(prefix, f"scenes/{sid}/", 1)
    assert current == BASELINE[sid]["scene_json"]


@pytest.mark.parametrize("sid", ["blocks", "drone_bench"])
def test_embedded_materials_uvs_and_normals(sid):
    check_materials(sid)


@pytest.mark.parametrize("sid", ["blocks", "drone_bench"])
def test_assets_fit_declared_body_and_existing_interface_envelopes(sid):
    spec = load_scene(sid)
    for obj in spec.objects:
        low, high = np.asarray(BASELINE[sid]["exported_object_bounds"][obj.object_id])
        # Some existing interfaces extend beyond the declared main body:
        # studs, battery rails and the M3 inspection face. Preserve those
        # observed allowances instead of crushing a mature source to size_m.
        low = np.minimum(low, -np.asarray(obj.size_m) / 2)
        high = np.maximum(high, np.asarray(obj.size_m) / 2)
        for name, part in meshes(spec, obj, Pose()).items():
            if name.split("/")[-1].startswith("label_"):
                continue  # Decal faces do not change the physical body/interface envelope.
            assert np.all(part.bounds[0] >= low - 1e-6), (sid, obj.object_id, name, part.bounds, low)
            assert np.all(part.bounds[1] <= high + 1e-6), (sid, obj.object_id, name, part.bounds, high)


@pytest.mark.parametrize(
    "sid,identifier",
    [("blocks", x) for x in ["A", "B", "BASE"]]
    + [("drone_bench", x) for x in ["BAT", "BAY", "GUARD", "M1", "M2", "M3", "M4", "VOLTMETER"]],
)
def test_actual_initial_low_surfaces_are_supported(sid, identifier):
    spec = load_scene(sid)
    obj = object_by_id(spec, identifier)
    source = triangles(meshes(spec, obj))
    if sid == "drone_bench" and identifier == "BAY":
        # Refine the unchanged large floor triangles: the coarse quarter-grid
        # skips its two narrow real support bridges. Midpoint subdivision adds
        # surface witnesses without changing geometry or the contact tolerance.
        vertices, faces = trimesh.remesh.subdivide(
            source.reshape(-1, 3), np.arange(source.size // 3).reshape(-1, 3)
        )
        source = vertices[faces]
    assert_supported(source, environment_triangles(sid))


@pytest.mark.parametrize(
    "sid,source,target,action,position",
    [
        ("blocks", "A", "BASE", "assemble", [-0.032, 0.14, 0.046]),
        ("drone_bench", "BAT", "BAY", "insert", [0, 0.025, 0.155]),
    ],
)
def test_original_mating_endpoint_has_real_support(sid, source, target, action, position):
    spec = load_scene(sid)
    moving, fixed = (object_by_id(spec, identifier) for identifier in [source, target])
    goal = mating_goal(moving, fixed, fixed.pose, action)
    np.testing.assert_allclose(goal.position_m, position, atol=1e-8)
    assert_supported(triangles(meshes(spec, moving, goal)), triangles(meshes(spec, fixed)), tolerance=0.0001)


@pytest.mark.parametrize("sid,identifier", [("blocks", "B"), ("drone_bench", "M3")])
def test_original_inspection_prompt_clears_exported_surfaces(sid, identifier):
    check_inspection(sid, identifier)


def test_b_has_three_open_tubes_and_an_open_underside():
    spec = load_scene("blocks")
    brick = trimesh.util.concatenate(list(meshes(spec, object_by_id(spec, "B"), Pose()).values()))
    for x in [-0.016, 0, 0.016]:
        # The tube centre stays open from below up to the brick roof. Radial
        # rays from inside it must meet a genuine cylindrical tube wall.
        up = ray_hits(brick, [x, 0, -0.020], np.array([0.0, 0.0, 1.0]))
        assert up and up[0]["point"][2] > 0.005
        for angle in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            radial = ray_hits(brick, [x, 0, -0.004], np.array([np.cos(angle), np.sin(angle), 0.0]))
            assert radial and 0.0035 < radial[0]["distance_m"] < 0.0055
    # Space beside the tubes is a real cavity rather than a closed bottom.
    for x in [-0.024, -0.008, 0.008, 0.024]:
        up = ray_hits(brick, [x, 0.009, -0.020], np.array([0.0, 0.0, 1.0]))
        assert up and up[0]["point"][2] > 0.005


def closed_mesh_copy(part):
    # Weld only exactly equal positions on a private geometry copy. UV seams
    # and hard normals do not create holes, and no source face is filled.
    vertices, inverse = np.unique(part.vertices, axis=0, return_inverse=True)
    solid = trimesh.Trimesh(vertices=vertices, faces=inverse[part.faces], process=False)
    if not (solid.is_watertight and solid.is_winding_consistent):
        return None
    if solid.volume < 0:
        solid.invert()
    return solid


def surface_obstacles(parts):
    # All triangle surfaces participate, including intentionally open source
    # primitives. Closed solids additionally support signed containment tests.
    return [
        (name, part, polydata(part), closed_mesh_copy(part))
        for name, part in parts.items()
        if not name.split("/")[-1].startswith("label_")
    ]


def oriented_surface_field(data):
    field = vtk.vtkImplicitPolyDataDistance()
    field.SetInput(data)
    return field


def local_surface_crosses(point, direction, step, own_field, other_field, tolerance):
    # The contact is already known to lie on both surfaces. Probe the complete
    # mesh on either side, crossing triangle seams without extending a single
    # triangle's plane into empty space. Intermediate closest-point checks
    # keep the probes on this local surface instead of jumping over an edge.
    signs = []
    for sign in (-1, 1):
        closest = [0.0, 0.0, 0.0]
        for fraction in (0.25, 0.5, 1.0):
            probe = point + sign * fraction * step * direction
            own_field.EvaluateFunctionAndGetClosestPoint(probe, closest)
            if np.linalg.norm(np.asarray(closest) - probe) > tolerance / 4:
                return False
        # For an open mesh this sign is used only around an actual contact,
        # never as a global assertion that a point is inside the open object.
        signs.append(other_field.EvaluateFunction(closest))
    return min(signs) < -tolerance and max(signs) > tolerance


def assert_actual_surface_clearance(moving, obstacles, tolerance=0.0001, moving_parts=None):
    """Finite-pose, local surface witnesses plus bidirectional closed containment.

    This is not continuous collision detection or an exhaustive proof of
    clearance: contact-neighbourhood probes and containment witnesses are finite.
    """
    moving_poly = polydata(moving)
    moving_field = None
    samples = np.concatenate([moving.vertices, moving.triangles_center])
    # Preserve independently closed pieces even when other source primitives
    # are open, making the concatenated render mesh non-watertight.
    moving_solids = [
        solid
        for part in ([moving] if moving_parts is None else moving_parts)
        if (solid := closed_mesh_copy(part)) is not None
    ]
    for name, fixed, fixed_poly, solid in obstacles:
        low = np.maximum(moving.bounds[0], fixed.bounds[0])
        high = np.minimum(moving.bounds[1], fixed.bounds[1])
        if np.any(high < low - tolerance):
            continue
        collision = vtk.vtkCollisionDetectionFilter()
        collision.SetInputData(0, moving_poly)
        collision.SetInputData(1, fixed_poly)
        collision.SetTransform(0, vtk.vtkTransform())
        collision.SetTransform(1, vtk.vtkTransform())
        collision.SetCollisionModeToAllContacts()
        collision.SetBoxTolerance(0.0)
        collision.SetCellTolerance(0.0)
        collision.Update()
        if collision.GetNumberOfContacts():
            ai = vtk_to_numpy(collision.GetContactCells(0))
            bi = vtk_to_numpy(collision.GetContactCells(1))
            contacts = collision.GetContactsOutput()
            ends = vtk_to_numpy(contacts.GetLines().GetConnectivityArray()).reshape(-1, 2)
            vertices = vtk_to_numpy(contacts.GetPoints().GetData())
            segments = vertices[ends]
            length = np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1)
            # Nominally tangent studs produced ~15 nm contact segments after
            # float32 export. Retain the original 0.1 mm contact tolerance.
            candidates = np.flatnonzero(length > tolerance)
            if len(candidates):
                moving_field = moving_field or oriented_surface_field(moving_poly)
                fixed_field = oriented_surface_field(fixed_poly)
                for index in candidates:
                    an, bn = moving.face_normals[ai[index]], fixed.face_normals[bi[index]]
                    line = np.cross(an, bn)
                    sine = np.linalg.norm(line)
                    if sine < 1e-10:
                        continue  # Parallel/coplanar surface contact.
                    line /= sine
                    point = segments[index].mean(axis=0)
                    # Move far enough in each tangent plane to resolve the
                    # same 0.1 mm transverse tolerance, including oblique faces.
                    step = 2 * tolerance / sine
                    crosses = local_surface_crosses(
                        point, np.cross(line, an), step, moving_field, fixed_field, tolerance
                    ) and local_surface_crosses(
                        point, np.cross(line, bn), step, fixed_field, moving_field, tolerance
                    )
                    assert not crosses, (name, "actual triangle crossings", int(index))
        if solid is not None:
            selected = samples[
                ((samples > solid.bounds[0] + tolerance) & (samples < solid.bounds[1] - tolerance)).all(
                    axis=1
                )
            ]
            if len(selected):
                separation = distances(solid, selected)
                assert separation.min() >= -tolerance, (
                    name,
                    "moving surface contained",
                    float(separation.min()),
                )
        fixed_samples = np.concatenate([fixed.vertices, fixed.triangles_center])
        for moving_solid in moving_solids:
            selected = fixed_samples[
                (
                    (fixed_samples > moving_solid.bounds[0] + tolerance)
                    & (fixed_samples < moving_solid.bounds[1] - tolerance)
                ).all(axis=1)
            ]
            if len(selected):
                separation = distances(moving_solid, selected)
                assert separation.min() >= -tolerance, (
                    name,
                    "fixed surface contained",
                    float(separation.min()),
                )


@pytest.mark.parametrize("sid", ["blocks", "drone_bench"])
def test_production_environment_uses_every_nonlabel_triangle_surface(sid):
    spec = load_scene(sid)
    all_parts = {}
    for entry in spec.environment:
        all_parts.update(meshes(spec, entry))
    obstacles = surface_obstacles(all_parts)
    expected = {n: p for n, p in all_parts.items() if not n.split("/")[-1].startswith("label_")}
    assert {name for name, *_ in obstacles} == set(expected)
    assert all(pd.GetNumberOfCells() == len(mesh.faces) > 0 for _, mesh, pd, _ in obstacles)
    assert sum(len(mesh.faces) for _, mesh, _, _ in obstacles) == sum(len(p.faces) for p in expected.values())


@pytest.mark.parametrize(
    "sid,source,target,action", [("blocks", "A", "BASE", "assemble"), ("drone_bench", "BAT", "BAY", "insert")]
)
def test_full_exported_body_clears_sampled_original_mating_path(sid, source, target, action):
    spec = load_scene(sid)
    moving, receiver = (object_by_id(spec, identifier) for identifier in [source, target])
    goal = mating_goal(moving, receiver, receiver.pose, action)
    cue = geometry_cue(moving, action, goal_pose=goal, reference_id=target)
    local_parts = list(meshes(spec, moving, Pose()).values())
    local = trimesh.util.concatenate(local_parts)
    fixed = {}
    for entry in [*spec.environment, *[obj for obj in spec.objects if obj.object_id != source]]:
        fixed.update(meshes(spec, entry))
    poses = path_keyframes(cue) + [
        trajectory(cue, float(t)) for t in np.linspace(0, cue.interaction.duration_s, 61)
    ]
    obstacles = surface_obstacles(fixed)
    for pose in poses:
        transformed = local.copy()
        transformed.apply_transform(matrix(pose))
        transformed_parts = [part.copy().apply_transform(matrix(pose)) for part in local_parts]
        assert_actual_surface_clearance(transformed, obstacles, moving_parts=transformed_parts)


def test_full_guard_rotates_clockwise_clear_of_installed_battery_and_frame():
    spec = load_scene("drone_bench")
    guard, battery, bay = (object_by_id(spec, name) for name in ["GUARD", "BAT", "BAY"])
    final_battery = mating_goal(battery, bay, bay.pose, "insert")
    local_parts = list(meshes(spec, guard, Pose()).values())
    local = trimesh.util.concatenate(local_parts)
    fixed = {}
    for entry in [*spec.environment, *[obj for obj in spec.objects if obj.object_id != "GUARD"]]:
        pose = final_battery if getattr(entry, "object_id", None) == "BAT" else None
        fixed.update(meshes(spec, entry, pose))
    axis, pivot = guard.interaction.rotation_axis_local, guard.interaction.pivot_local_m
    obstacles = surface_obstacles(fixed)
    for angle in np.linspace(0, -30, 13):
        pose = rotate_about(guard.pose, axis, pivot, float(angle))
        np.testing.assert_allclose(
            matrix(pose)[:3, :3] @ [1, 0, 0],
            [np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle)), 0],
            atol=1e-8,
        )
        np.testing.assert_allclose(
            transform_points(pose, [pivot]), transform_points(guard.pose, [pivot]), atol=1e-8
        )
        transformed = local.copy()
        transformed.apply_transform(matrix(pose))
        transformed_parts = [part.copy().apply_transform(matrix(pose)) for part in local_parts]
        assert_actual_surface_clearance(transformed, obstacles, moving_parts=transformed_parts)


def test_m3_orange_annulus_is_visible_at_the_original_inspection_face():
    spec = load_scene("drone_bench")
    motor = object_by_id(spec, "M3")
    parts = meshes(spec, motor, Pose())
    orange = [
        p
        for p in parts.values()
        if (lambda c: c[0] > 150 and 30 < c[1] < 180 and c[2] < 90)(p.visual.material.baseColorFactor)
    ]
    assert orange
    annulus = trimesh.util.concatenate(orange)
    entire = trimesh.util.concatenate(list(parts.values()))
    for angle in np.linspace(0, 2 * np.pi, 16, endpoint=False):
        # The inspection anchor is in the open centre; sample its actual ring.
        origin = [0.060, 0.008 * np.cos(angle), -0.005 + 0.008 * np.sin(angle)]
        direction = np.array([-1.0, 0.0, 0.0])
        hit, visible = ray_hits(annulus, origin, direction), ray_hits(entire, origin, direction)
        assert hit and visible
        assert abs(hit[0]["point"][0] - 0.036) < 0.0001
        assert abs(hit[0]["distance_m"] - visible[0]["distance_m"]) < 0.0001


def test_surface_crossing_check_rejects_open_mesh_intersection():
    wall = trimesh.Trimesh(
        vertices=[[0, -1, -1], [0, 1, -1], [0, 1, 1], [0, -1, 1]], faces=[[0, 1, 2], [0, 2, 3]], process=False
    )
    assert not wall.is_watertight
    obstacles = surface_obstacles({"open_wall": wall})
    crossing = trimesh.creation.box([0.1, 0.2, 0.2])
    with pytest.raises(AssertionError, match="actual triangle crossings"):
        assert_actual_surface_clearance(crossing, obstacles)
    crossing.apply_translation([0.06, 0, 0])
    assert_actual_surface_clearance(crossing, obstacles)


@pytest.mark.parametrize("xs", [[-0.01, 0.01], [-0.01, 0, 0.01], np.linspace(-0.010025, 0.010025, 402)])
def test_open_surface_crossing_is_unchanged_by_triangle_subdivision(xs):
    wall = trimesh.Trimesh(
        vertices=[[0, -0.01, -0.01], [0, 0.01, -0.01], [0, 0.01, 0.01], [0, -0.01, 0.01]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    faces = []
    for index in range(len(xs) - 1):
        k = 2 * index
        faces.extend([[k, k + 2, k + 3], [k, k + 3, k + 1]])
    sheet = trimesh.Trimesh(
        vertices=[[x, y, 0] for x in xs for y in (-0.01, 0.01)],
        faces=faces,
        process=False,
    )
    # The same 20 mm transverse sheet intersection must remain detectable
    # when its line coincides with an edge or crosses 50 micrometre strips.
    with pytest.raises(AssertionError, match="actual triangle crossings"):
        assert_actual_surface_clearance(sheet, surface_obstacles({"wall": wall}))


@pytest.mark.parametrize("outer_moves", [False, True])
def test_closed_containment_checks_both_directions_and_independent_parts(outer_moves):
    outer = trimesh.creation.box([0.02, 0.02, 0.02])
    inner = trimesh.creation.box([0.002, 0.002, 0.002])
    moving, fixed = (outer, inner) if outer_moves else (inner, outer)
    open_part = trimesh.Trimesh(
        vertices=[[0.04, 0, 0], [0.04, 0.01, 0], [0.04, 0, 0.01]],
        faces=[[0, 1, 2]],
        process=False,
    )
    combined = trimesh.util.concatenate([moving, open_part])
    assert not combined.is_watertight
    with pytest.raises(AssertionError, match="surface contained"):
        assert_actual_surface_clearance(
            combined, surface_obstacles({"fixed": fixed}), moving_parts=[moving, open_part]
        )


def closed_box_with_fine_face():
    """Subdivide one real planar face without changing the box boundary."""
    box = trimesh.creation.box([0.02, 0.02, 0.02])
    a, b, c = box.faces[0]
    midpoint = (box.vertices[a] + box.vertices[b]) / 2
    # The point is strictly inside the face, 2 nm from its long edge. It is
    # not a duplicate vertex and all three replacement triangles are needed
    # to close the surface. validate=True used to remove the thin triangle.
    point = midpoint + 1e-7 * (box.vertices[c] - midpoint)
    vertices = np.vstack([box.vertices, point])
    p = len(vertices) - 1
    faces = np.vstack([box.faces[1:], [a, b, p], [b, c, p], [c, a, p]])
    result = trimesh.Trimesh(vertices, faces, process=False)
    assert result.is_watertight and result.is_winding_consistent
    return result


@pytest.mark.parametrize("inverted", [False, True])
def test_signed_distance_preserves_closed_fine_faces(inverted):
    solid = closed_box_with_fine_face()
    if inverted:
        solid.invert()
    vertices, faces = solid.vertices.copy(), solid.faces.copy()
    actual = distances(solid, np.asarray([[0.0, 0.0, 0.0], [0.03, 0.0, 0.0]]))
    np.testing.assert_allclose(actual, [-0.01, 0.02], atol=1e-8)
    np.testing.assert_array_equal(solid.vertices, vertices)
    np.testing.assert_array_equal(solid.faces, faces)


def test_signed_distance_still_resolves_unwelded_export_seams():
    box = trimesh.creation.box([0.02, 0.02, 0.02])
    seamed = trimesh.Trimesh(box.triangles.reshape(-1, 3), np.arange(36).reshape(-1, 3), process=False)
    assert not seamed.is_watertight
    actual = distances(seamed, np.asarray([[0.0, 0.0, 0.0], [0.03, 0.0, 0.0]]))
    np.testing.assert_allclose(actual, [-0.01, 0.02], atol=1e-8)
    assert not seamed.is_watertight  # The caller's source was not repaired in place.


@pytest.mark.parametrize("outer_moves", [False, True])
def test_fine_closed_surface_retains_bidirectional_containment(outer_moves):
    outer = closed_box_with_fine_face()
    inner = trimesh.creation.box([0.002, 0.002, 0.002])
    moving, fixed = (outer, inner) if outer_moves else (inner, outer)
    open_part = trimesh.Trimesh(
        vertices=[[0.04, 0, 0], [0.04, 0.01, 0], [0.04, 0, 0.01]],
        faces=[[0, 1, 2]],
        process=False,
    )
    # A render object may also have open primitives. The independently closed
    # fine-faced component must still reject contained geometry in both roles.
    with pytest.raises(AssertionError, match="surface contained"):
        assert_actual_surface_clearance(
            trimesh.util.concatenate([moving, open_part]),
            surface_obstacles({"contained_or_container": fixed}),
            moving_parts=[moving, open_part],
        )
