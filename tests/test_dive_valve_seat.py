"""Real closed-mesh valve seat regression; no motion/contact exemptions."""

import hashlib
from pathlib import Path

import numpy as np
import pytest
import trimesh

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.modeling import make_environment, make_object
from holocue.spatial import matrix

PREFIX = "dive_fillstation_environment/"
CHANGED = {PREFIX + "0009_manifold", PREFIX + "0016_tube"}
START = np.array([0.34, 0.61, 1.25])
END = np.array([0.49, 0.53, 1.05])
JOINT = START + 0.16 * (END - START)
DIRECTION = (END - START) / np.linalg.norm(END - START)


def nodes(scene):
    result = {}
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        result[str(node)] = mesh
    return result


def closed(mesh):
    mesh = mesh.copy()
    mesh.process(validate=True)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    assert len(mesh.split(only_watertight=False)) == 1
    return mesh


def distances(mesh, points):
    return trimesh.proximity.closest_point_naive(mesh, np.asarray(points))[1]


def axis_hits(mesh, origin, direction):
    tri = mesh.triangles
    a = tri[:, 1] - tri[:, 0]
    b = tri[:, 2] - tri[:, 0]
    h = np.cross(direction, b)
    det = np.einsum("ij,ij->i", a, h)
    inv = np.divide(1.0, det, out=np.zeros_like(det), where=abs(det) > 1e-12)
    s = origin - tri[:, 0]
    u = np.einsum("ij,ij->i", s, h) * inv
    q = np.cross(s, a)
    v = (q @ direction) * inv
    t = np.einsum("ij,ij->i", b, q) * inv
    hit = (abs(det) > 1e-12) & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-8)
    return np.unique(np.round(t[hit], 9))


@pytest.fixture(scope="module")
def valve(tmp_path_factory):
    spec = load_scene("dive_fillstation")
    directory = tmp_path_factory.mktemp("dive_valve")
    fixture = Path(__file__).parent / "fixtures/dive_fillstation/environment_before_valve_seat.glb"
    assert (
        hashlib.sha256(fixture.read_bytes()).hexdigest()
        == "c230c299a439556c8015dc3094b0abf2d336d37dcf6ba4e21da883bada297b48"
    )
    path = directory / "workstation.glb"
    make_environment(spec).save(path)
    old = nodes(load_asset(str(fixture), spec.asset_axes))
    new = nodes(load_asset(str(path), spec.asset_axes))
    stem = next(obj for obj in spec.objects if obj.object_id == "STEM")
    path = directory / "STEM.glb"
    make_object(stem).save(path)
    # The complete v3 STEM must remain byte-identical, not just its pose.
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "00535b46361aa3f10a5392e5b2e4adc54f3c9277fe458026f7029201a61dd29f"
    )
    scene = load_asset(str(path), spec.asset_axes)
    scene.apply_transform(matrix(stem.pose))
    return spec, old, new, nodes(scene)


def test_only_two_named_environment_nodes_change_and_keep_materials(valve):
    _, old, new, _ = valve
    assert old.keys() == new.keys()
    changed = set()
    for name, before in old.items():
        after = new[name]
        if not (
            np.array_equal(before.vertices, after.vertices) and np.array_equal(before.faces, after.faces)
        ):
            changed.add(name)
        for attribute in ("name", "baseColorFactor", "metallicFactor", "roughnessFactor", "doubleSided"):
            np.testing.assert_array_equal(
                getattr(before.visual.material, attribute), getattr(after.visual.material, attribute)
            )
        for attribute in ("uv", "vertex_attributes"):
            if attribute == "uv":
                np.testing.assert_array_equal(
                    getattr(before.visual, attribute, None), getattr(after.visual, attribute, None)
                )
        a = getattr(before.visual.material, "baseColorTexture", None)
        b = getattr(after.visual.material, "baseColorTexture", None)
        assert (a is None) == (b is None)
        if a is not None:
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert changed == CHANGED


def test_valve_and_hose_are_single_closed_solids(valve):
    _, _, new, _ = valve
    for name in CHANGED:
        closed(new[name])


def test_blind_bore_has_actual_radial_clearance_wall_and_end_contact(valve):
    _, _, new, stem = valve
    body = closed(new[PREFIX + "0009_manifold"])
    shaft = stem["STEM/0000_spindle"]
    # Rays intersect actual triangles, including the tessellated inner wall.
    walls = []
    radii = []
    for y in (0.586, 0.590, 0.600, 0.612, 0.624):
        for angle in np.linspace(0, 2 * np.pi, 80, endpoint=False):
            hits = axis_hits(body, np.array([0.34, y, 1.25]), np.array([np.cos(angle), 0, np.sin(angle)]))
            assert len(hits) >= 2
            radii.append(hits[0])
            walls.append(hits[1] - hits[0])
    assert min(radii) > 0.01620 and max(radii) < 0.016251
    assert min(walls) > 0.00570
    # The exact rear end of the unchanged shaft rests on the real bore floor.
    cap = shaft.triangles[np.max(abs(shaft.triangles[:, :, 1] - 0.626), axis=1) < 1e-7]
    assert len(cap) == 40
    assert distances(body, cap.mean(axis=1)).max() < 1e-7
    hits = axis_hits(body, np.array([0.34, 0.570, 1.25]), np.array([0.0, 1.0, 0.0]))
    assert hits[0] == pytest.approx(0.056, abs=1e-7)
    assert hits[1] - hits[0] >= 0.0099
    # Explicit real shaft side samples avoid treating end contact as clearance.
    side = []
    for y in (0.590, 0.600, 0.612, 0.620):
        for angle in np.linspace(0, 2 * np.pi, 40, endpoint=False):
            side.append([0.34 + 0.016 * np.cos(angle), y, 1.25 + 0.016 * np.sin(angle)])
    assert distances(body, side).min() > 0.00020


def test_side_branch_and_original_hose_meet_on_full_original_cross_section(valve):
    _, old, new, _ = valve
    body = closed(new[PREFIX + "0009_manifold"])
    hose = closed(new[PREFIX + "0016_tube"])
    former = old[PREFIX + "0016_tube"]
    # Both genuine cap surfaces cover the same polygonal disk, with no gap.
    cap = hose.triangles[np.max(abs((hose.triangles - JOINT) @ DIRECTION), axis=1) < 1e-7]
    assert len(cap) == 20
    assert distances(body, cap.mean(axis=1)).max() < 1e-7
    assert distances(body, JOINT[None]).max() < 1e-7
    assert np.sum(
        np.linalg.norm(np.cross(cap[:, 1] - cap[:, 0], cap[:, 2] - cap[:, 0]), axis=1) / 2
    ) == pytest.approx(10 * 0.012**2 * np.sin(np.pi / 10), abs=1e-9)
    # Remaining centerline, radius, far endpoint and original faceted section.
    length = np.linalg.norm(END - START)
    parameter = (hose.vertices - START) @ DIRECTION / length
    assert parameter.min() == pytest.approx(0.16, abs=2e-7)
    assert parameter.max() == pytest.approx(1.0, abs=2e-7)
    radial = hose.vertices - START - ((hose.vertices - START) @ DIRECTION)[:, None] * DIRECTION
    assert np.max(np.linalg.norm(radial, axis=1)) == pytest.approx(0.012, abs=1e-7)
    old_end = former.vertices[abs((former.vertices - END) @ DIRECTION) < 1e-7]
    new_end = hose.vertices[abs((hose.vertices - END) @ DIRECTION) < 1e-7]
    assert max(min(np.linalg.norm(new_end - point, axis=1)) for point in old_end) < 1e-7
    # Samples in the old branch centerline are actually inside the single
    # manifold/valve solid before the joint, then inside the remaining hose.
    for mesh, t0, t1 in ((body, 0.10, 0.159), (hose, 0.161, 0.99)):
        for t in np.linspace(t0, t1, 10):
            hits = axis_hits(mesh, START + t * (END - START), np.array([1.0, 0.0, 0.0]))
            assert len(hits) % 2 == 1


def test_original_manifold_exterior_is_preserved_outside_local_junction(valve):
    _, old, new, _ = valve
    before = closed(old[PREFIX + "0009_manifold"])
    after = closed(new[PREFIX + "0009_manifold"])
    for source, target in ((before, after), (after, before)):
        # Keep the two distant ends plus actual lateral triangles. No bounding
        # boxes are used to infer contact or collision here.
        points = source.triangles_center[abs(source.triangles_center[:, 0] - 0.34) > 0.055]
        assert len(points) >= 40
        assert distances(target, points).max() < 1e-7
