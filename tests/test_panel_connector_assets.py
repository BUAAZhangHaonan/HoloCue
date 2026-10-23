"""Exported electrical and survey assets; static geometry, no task execution."""

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from holocue.config import load_scene
from holocue.models import Pose, SceneSpec
from holocue.spatial import mating_goal, matrix, path_keyframes, rotate_about, trajectory, transform_points
from panel_optical_geometry import distances, ray_hits
from test_asset_reconstruction import (
    BASELINE,
    PHYSICAL_FIELDS,
    assert_supported,
    environment_triangles,
    intersecting_box_triangles,
    meshes,
    triangles,
    vertical_hits,
)
from test_optical_dig_assets import (
    object_by_id,
    geometry_cue,
    test_reconstructed_glbs_embed_usable_materials_and_uvs as check_embedded_materials,
    test_static_inspection_ring_clears_actual_mesh_without_a_task_session as check_inspection_ring,
)


@pytest.mark.parametrize("sid", ["control_panel", "connector"])
def test_physical_objects_and_complete_task_contract_unchanged(sid):
    spec = load_scene(sid)
    if sid == "control_panel":
        old = BASELINE["scenes"][sid]
    else:
        baseline = SceneSpec.model_validate(
            json.loads((Path(__file__).parent / "fixtures/connector_before_reconstruction.json").read_text())
        )
        old = {
            "objects": [obj.model_dump(mode="json") for obj in baseline.objects],
            "task_contract": baseline.task_contract.model_dump(mode="json"),
        }
    previous = {obj["object_id"]: obj for obj in old["objects"]}
    assert {obj.object_id for obj in spec.objects} == set(previous)
    for obj in spec.objects:
        current = obj.model_dump(mode="json")
        assert {key: current[key] for key in PHYSICAL_FIELDS} == {
            key: previous[obj.object_id][key] for key in PHYSICAL_FIELDS
        }
    assert spec.task_contract.model_dump(mode="json") == old["task_contract"]
    assert spec.asset_axes == "gltf_y_up"


@pytest.mark.parametrize("sid", ["control_panel", "connector", "dig_site"])
def test_final_assets_embed_valid_materials_uv_and_normals(sid):
    check_embedded_materials(sid)


@pytest.mark.parametrize("sid", ["control_panel", "connector"])
def test_replacement_objects_fit_original_envelopes_and_inspection_planes(sid):
    spec = load_scene(sid)
    for obj in spec.objects:
        half = np.asarray(obj.size_m) / 2
        low, high = -half, half.copy()
        point = obj.interaction.inspect_point_local_m
        if point is not None:
            low = np.minimum(low, point)
            high = np.maximum(high, point)
        for name, part in meshes(spec, obj, Pose()).items():
            assert np.all(part.bounds[0] >= low - 1e-6), (sid, obj.object_id, name, part.bounds)
            assert np.all(part.bounds[1] <= high + 1e-6), (sid, obj.object_id, name, part.bounds)


@pytest.mark.parametrize(
    "sid,identifier",
    [("control_panel", name) for name in ("A", "B", "C")]
    + [("connector", name) for name in ("P", "S", "C")]
    + [("dig_site", "STAY")],
)
def test_actual_low_surfaces_have_real_support(sid, identifier):
    spec = load_scene(sid)
    source = triangles(meshes(spec, object_by_id(spec, identifier)))
    assert_supported(source, environment_triangles(sid))


@pytest.mark.parametrize("sid", ["control_panel", "connector"])
def test_module_back_inspection_prompt_clears_real_mesh(sid):
    check_inspection_ring(sid, "C")


def test_b_rotation_preserves_vertical_axis_pivot_and_positive_ccw():
    spec = load_scene("control_panel")
    knob = object_by_id(spec, "B")
    axis = np.asarray(knob.interaction.rotation_axis_local)
    pivot = np.asarray([knob.interaction.pivot_local_m])
    expected_pivot = transform_points(knob.pose, pivot)
    for angle in np.linspace(0, 30, 13):
        pose = rotate_about(knob.pose, axis, pivot[0], angle)
        np.testing.assert_allclose(matrix(pose)[:3, :3] @ axis, [0, 0, 1], atol=1e-8)
        np.testing.assert_allclose(transform_points(pose, pivot), expected_pivot, atol=1e-8)
        direction = matrix(pose)[:3, :3] @ [1, 0, 0]
        np.testing.assert_allclose(
            direction, [np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle)), 0], atol=1e-8
        )


def one_part(parts, fragment):
    selected = [part for name, part in parts.items() if fragment in name]
    assert len(selected) == 1, (fragment, len(selected))
    return selected[0]


@pytest.mark.parametrize("sid", ["control_panel", "connector"])
def test_original_c_inspection_ray_hits_the_real_yellow_key(sid):
    spec = load_scene(sid)
    obj = object_by_id(spec, "C")
    parts = meshes(spec, obj, Pose())
    key = one_part(parts, "rear_yellow_locating_key")
    point = np.asarray(obj.interaction.inspect_point_local_m)
    normal = np.asarray(obj.interaction.inspect_normal_local)
    hits = ray_hits(key, point + 0.1 * normal, -normal)
    assert hits and hits[0]["distance_m"] == pytest.approx(0.1, abs=1e-6)
    assert key.face_normals[hits[0]["triangle_index"]] @ normal > 0.99
    color = key.visual.material.baseColorFactor
    assert color[0] > color[2] * 2 and color[1] > color[2] * 2
    terminals = [
        part
        for name, part in parts.items()
        if "insulator" not in name and ("rear_metal_terminal" in name or "rear_terminal_" in name)
    ]
    assert len(terminals) == 4
    assert all(part.extents[1] > 0.01 for part in terminals)


def test_b_white_indicator_rests_on_cap_and_remains_visible_while_rotating():
    spec = load_scene("control_panel")
    knob = object_by_id(spec, "B")
    parts = meshes(spec, knob, Pose())
    marker = one_part(parts, "white_rotation_indicator")
    cap = one_part(parts, "emaitee_fluted_knob")
    assert_supported(marker.triangles, cap.triangles, tolerance=1e-6)
    low, high = marker.bounds
    for x in np.linspace(low[0] + 0.0001, high[0] - 0.0001, 3):
        for y in np.linspace(low[1] + 0.0001, high[1] - 0.0001, 3):
            cap_hits = vertical_hits(cap.triangles, [x, y])
            assert len(cap_hits) and cap_hits.max() <= low[2] + 1e-6
    center = marker.bounds.mean(axis=0)
    for angle in np.linspace(0, 30, 13):
        pose = rotate_about(
            knob.pose, knob.interaction.rotation_axis_local, knob.interaction.pivot_local_m, angle
        )
        point = transform_points(pose, [center])[0]
        assert point[2] == pytest.approx(knob.pose.position_m[2] + center[2])


def test_rotating_b_surfaces_do_not_enter_nearby_fixed_parts():
    spec = load_scene("control_panel")
    knob = object_by_id(spec, "B")
    moving = meshes(spec, knob, Pose())
    local_points = np.concatenate(
        [np.concatenate([part.vertices, part.triangles_center]) for part in moving.values()]
    )
    samples = []
    for angle in np.linspace(0, 30, 13):
        pose = rotate_about(
            knob.pose, knob.interaction.rotation_axis_local, knob.interaction.pivot_local_m, angle
        )
        samples.append(transform_points(pose, local_points))
    samples = np.concatenate(samples)
    low, high = samples.min(axis=0), samples.max(axis=0)
    checked = []
    for entry in spec.environment:
        for name, part in meshes(spec, entry).items():
            if np.all(part.bounds[0] <= high) and np.all(part.bounds[1] >= low):
                if "stator" in name:
                    # The imported stator has an open tessellation seam, and
                    # its top coincides with the shaft's lowest plane. Actual
                    # vertex Z ranges prove no penetration throughout this
                    # vertical-axis rotation, without assuming closed meshes.
                    assert low[2] >= part.bounds[1, 2] - 1e-7
                else:
                    # Signed distances are valid for these closed drilled
                    # shell and annular bearing meshes, including contact.
                    separation = distances(part, samples)
                    assert separation.min() >= -0.0001, (name, float(separation.min()))
                checked.append(name)
    assert any("stationary_bearing" in name for name in checked)
    assert any("stator" in name for name in checked)
    assert any("drilled_shell" in name for name in checked)


def axial_ring_center(part):
    """Fit the real circular end ring; polygon AABB centers are biased."""
    vertices = part.vertices
    section = vertices[np.abs(vertices[:, 1] - part.bounds[0, 1]) < 1e-7]
    xz = section[:, [0, 2]]
    rough = (xz.min(axis=0) + xz.max(axis=0)) / 2
    radius = np.linalg.norm(xz - rough, axis=1)
    # A socket end has both inner and outer rings. Use its outer boundary.
    xz = xz[radius > 0.95 * radius.max()]
    assert len(xz) >= 12
    coefficients = np.linalg.lstsq(
        np.column_stack((2 * xz, np.ones(len(xz)))), np.sum(xz * xz, axis=1), rcond=None
    )[0]
    center = coefficients[:2]
    assert np.ptp(np.linalg.norm(xz - center, axis=1)) < 1e-7
    return center


def test_four_real_pins_enter_four_open_bores_with_radial_clearance():
    spec = load_scene("connector")
    plug, socket = (object_by_id(spec, name) for name in ("P", "S"))
    goal = mating_goal(plug, socket, socket.pose, "insert")
    np.testing.assert_allclose(goal.position_m, [-0.1, 0.103, 0.055], atol=1e-8)
    moving = meshes(spec, plug, goal)
    fixed = meshes(spec, socket)
    receiver = trimesh.util.concatenate(list(fixed.values()))
    assert sum("contact_pin_" in name for name in moving) == 4
    assert sum("contact_socket_bore_" in name for name in fixed) == 4
    for index in range(1, 5):
        pin = one_part(moving, f"contact_pin_{index}")
        bore = one_part(fixed, f"contact_socket_bore_{index}")
        center = pin.bounds.mean(axis=0)
        center[[0, 2]] = axial_ring_center(pin)
        np.testing.assert_allclose(center[[0, 2]], axial_ring_center(bore), atol=1e-7)
        begin = max(pin.bounds[0, 1], bore.bounds[0, 1]) + 0.001
        end = min(pin.bounds[1, 1], bore.bounds[1, 1]) - 0.001
        assert end - begin > 0.01
        front = receiver.bounds[0, 1] - 0.01
        hits = ray_hits(receiver, [center[0], front, center[2]], np.array([0.0, 1.0, 0.0]))
        assert not hits or hits[0]["point"][1] > pin.bounds[1, 1] + 0.0001
        for y in np.linspace(begin, end, 3):
            for angle in np.linspace(0, 2 * np.pi, 24, endpoint=False):
                direction = np.array([np.cos(angle), 0.0, np.sin(angle)])
                origin = np.array([center[0], y, center[2]])
                pin_hits = ray_hits(pin, origin, direction)
                bore_hits = ray_hits(receiver, origin, direction)
                assert pin_hits and bore_hits
                assert bore_hits[0]["distance_m"] - pin_hits[0]["distance_m"] > 0.0001
    # Test the actual key against actual receiver triangles, not a drawn slot.
    key = one_part(moving, "top_alignment_key")
    low, high = key.bounds
    assert not len(intersecting_box_triangles(receiver.triangles, low, high))


def test_inserted_plug_feet_have_actual_final_support():
    spec = load_scene("connector")
    plug, socket = (object_by_id(spec, name) for name in ("P", "S"))
    goal = mating_goal(plug, socket, socket.pose, "insert")
    parts = meshes(spec, plug, goal)
    feet = [part for name, part in parts.items() if "rubber_support" in name]
    assert len(feet) == 2
    support = environment_triangles("connector")
    for foot in feet:
        assert_supported(foot.triangles, support, tolerance=0.0001)


def test_plug_body_and_key_clear_the_sampled_geometric_insertion_path():
    spec = load_scene("connector")
    plug, socket = (object_by_id(spec, name) for name in ("P", "S"))
    goal = mating_goal(plug, socket, socket.pose, "insert")
    cue = geometry_cue(plug, "insert", goal_pose=goal, reference_id="S")
    obstacle = np.concatenate(
        [
            environment_triangles("connector"),
            *[triangles(meshes(spec, obj)) for obj in spec.objects if obj.object_id != "P"],
        ]
    )
    parts = meshes(spec, plug, Pose())
    # The bored contacts have their own surface-ray checks above. Boxes are
    # conservative for the outer case, supports, insulator and solid top key.
    selected = {
        name: part
        for name, part in parts.items()
        if any(
            fragment in name
            for fragment in ("Adafruit_2230", "rubber_support", "four_contact_insulator", "top_alignment_key")
        )
    }
    assert len(selected) >= 6
    poses = path_keyframes(cue) + [
        trajectory(cue, float(t)) for t in np.linspace(0, cue.interaction.duration_s, 61)
    ]
    for index, pose in enumerate(poses):
        inverse = np.linalg.inv(matrix(pose))
        local = obstacle @ inverse[:3, :3].T + inverse[:3, 3]
        for name, part in selected.items():
            low, high = part.bounds.copy()
            if "rubber_support" in name:
                low[2] += 0.00075
            hits = intersecting_box_triangles(local, low, high)
            assert not len(hits), (index, name, pose.position_m, len(hits))


def test_scanned_tripod_has_three_separated_feet_on_actual_soil():
    spec = load_scene("dig_site")
    parts = {}
    for entry in spec.environment:
        parts.update(meshes(spec, entry))
    soil = triangles(
        {
            name: mesh
            for name, mesh in parts.items()
            if any(side + "_rim" in name for side in ("west", "east", "south", "north"))
        }
    )
    contacts = []
    for index in range(3):
        foot = one_part(parts, f"artec_scanned_tripod_foot_{index}")
        # Scanned pointed feet have point contacts, not broad flat bearings.
        # Require three actual source vertices on the soil, then measure their
        # combined support triangle rather than inventing a flat foot patch.
        point = foot.vertices[np.argmin(foot.vertices[:, 2])]
        hits = vertical_hits(soil, point[:2])
        assert len(hits) and np.abs(hits - point[2]).min() < 0.001
        assert not (-0.70 < point[0] < 0.70 and -0.50 < point[1] < 0.90)
        contacts.append(point)
    a, b, c = np.asarray(contacts)
    assert np.linalg.norm(np.cross(b - a, c - a)) / 2 > 0.1
