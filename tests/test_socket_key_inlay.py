"""The connector roof and colored key marker occupy disjoint real volumes."""

import numpy as np
import pytest
import trimesh

from holocue.config import load_scene
from holocue.modeling import make_object


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def polygon_clip(subject, boundary):
    output = list(subject)
    for a, b in zip(boundary, np.roll(boundary, -1, axis=0)):
        before = output
        output = []
        if not before:
            break
        previous = before[-1]
        dp = cross(b - a, previous - a)
        for current in before:
            dc = cross(b - a, current - a)
            if (dc >= 0) != (dp >= 0):
                output.append(previous + (current - previous) * dp / (dp - dc))
            if dc >= 0:
                output.append(current)
            previous = current
            dp = dc
    return output


def area(poly):
    if len(poly) < 3:
        return 0.0
    p = np.asarray(poly)
    return abs(float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1)) * 0.5))


def horizontal_faces(mesh, z):
    return mesh.triangles[
        (np.abs(mesh.triangles[:, :, 2] - z).max(axis=1) < 1e-8) & (mesh.face_normals[:, 2] > 0.999)
    ]


def upward_hits(mesh, point):
    hits = []
    for triangle in mesh.triangles:
        a, b, c = triangle
        denominator = cross(b[:2] - a[:2], c[:2] - a[:2])
        if abs(denominator) < 1e-16:
            continue
        u = cross(point - a[:2], c[:2] - a[:2]) / denominator
        v = cross(b[:2] - a[:2], point - a[:2]) / denominator
        if u >= -1e-10 and v >= -1e-10 and u + v <= 1 + 1e-10:
            hits.append(float(a[2] + u * (b[2] - a[2]) + v * (c[2] - a[2])))
    return sorted(hits)


@pytest.mark.parametrize("roundtrip", [False, True], ids=["generated", "glb_roundtrip"])
def test_socket_marker_has_a_real_roof_recess_and_keeps_the_opening(tmp_path, roundtrip):
    spec = load_scene("connector")
    obj = next(o for o in spec.objects if o.object_id == "S")
    assembly = make_object(obj)
    scene = assembly.scene
    if roundtrip:
        path = tmp_path / "S.glb"
        assembly.save(path)
        scene = trimesh.load_scene(path, process=False)
        scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    parts = {}
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        parts[str(node)] = mesh
    roof = parts["S/0003_panel"]
    mark = parts["S/0009_key_channel_mark"]
    x, y, z = obj.size_m
    t = 0.005
    np.testing.assert_allclose(
        roof.bounds, [[-x / 2 + t, -y / 2, z / 2 - t], [x / 2 - t, y / 2, z / 2]], atol=1e-8
    )
    np.testing.assert_allclose(
        mark.bounds, [[-0.006, -y / 2, 0.47 * z - 0.0015], [0.006, y / 2, 0.47 * z + 0.0015]], atol=1e-8
    )
    for mesh in (roof, mark):
        topology = mesh.copy()
        topology.merge_vertices(merge_tex=True, merge_norm=True)
        assert topology.is_watertight and topology.is_winding_consistent
        assert topology.volume > 0 and np.isfinite(mesh.vertex_normals).all()
    top_roof = horizontal_faces(roof, z / 2)
    top_mark = horizontal_faces(mark, z / 2)
    assert len(top_roof) and len(top_mark)
    overlap = sum(area(polygon_clip(a[:, :2], b[:, :2])) for a in top_roof for b in top_mark)
    assert overlap < 1e-12, "Two different materials must not share the visible top surface"

    # Real triangle intersections: the supporting roof remains under the inlay,
    # and its upper surface meets the mark underside without interior overlap.
    for xx in (-0.004, 0, 0.004):
        for yy in (-y * 0.35, 0, y * 0.35):
            point = np.array([xx, yy])
            rh = upward_hits(roof, point)
            mh = upward_hits(mark, point)
            assert rh and mh
            assert min(rh) == pytest.approx(z / 2 - t, abs=1e-8)
            assert max(rh) == pytest.approx(min(mh), abs=1e-8)
            assert min(mh) > min(rh) + 0.0019
            assert max(mh) == pytest.approx(z / 2, abs=1e-8)
    # Physical -Y opening, rear plate, four contact sockets and back label remain.
    assert len([name for name in parts if name.endswith("_contact_socket")]) == 4
    assert "S/label_10" in parts
    np.testing.assert_array_equal(mark.visual.material.baseColorFactor, [219, 132, 47, 255])
    np.testing.assert_array_equal(roof.visual.material.baseColorFactor, [*obj.color, 255])
    assert obj.anchors["insertion"] == (0.0, -0.002, 0.0)
