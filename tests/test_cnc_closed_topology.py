"""Actual CNC solid exports, retained source surfaces, and open interface voids."""

from collections import Counter

import numpy as np
import pytest
import trimesh
import vtk

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.render_validation import polydata
from scripts.scenes.asset_composition import mature_asset
from scripts.scenes.cnc_topology import copy_mesh, repair_flange, repair_mature_scene, repair_post, topology


def local_parts(entry):
    spec = load_scene("cnc_toolchange")
    scene = load_asset(str(root() / entry.asset), spec.asset_axes)
    for node in scene.graph.nodes_geometry:
        transform, key = scene.graph[node]
        mesh = copy_mesh(scene.geometry[key])
        mesh.apply_transform(transform)
        yield node, mesh


def original_araki(name):
    scene = trimesh.load_scene(root() / "assets/downloads/cnc_reconstruction" / name, process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return scene.to_geometry()


def triangle_keys(vertices, faces, uv=None):
    values = vertices if uv is None else np.c_[vertices, uv]
    return Counter(tuple(sorted(map(tuple, values[face]))) for face in faces)


def assert_clear_axis(mesh, xy, low, high):
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(polydata(mesh))
    locator.BuildLocator()
    t, sub, cell = vtk.mutable(0.0), vtk.mutable(0), vtk.mutable(0)
    assert not locator.IntersectWithLine(
        [*xy, low], [*xy, high], 1e-10, t, [0.0] * 3, [0.0] * 3, sub, cell
    ), (xy, low, high)


def test_every_actual_cnc_export_component_is_closed_and_outward():
    spec = load_scene("cnc_toolchange")
    checked = 0
    for entry in [*spec.objects, *spec.environment]:
        for node, mesh in local_parts(entry):
            if node.split("/")[-1].startswith("label_"):
                # Declared text decals are surfaces; the existing geometry
                # audit uses this same distinction from physical solid parts.
                continue
            solid, _, _ = topology(mesh)
            assert solid.is_watertight, node
            assert solid.is_winding_consistent, node
            components = trimesh.graph.connected_components(
                solid.face_adjacency, nodes=np.arange(len(solid.faces)), min_len=1
            )
            for faces in components:
                component = solid.submesh([faces], append=True, repair=False)
                assert component.volume > 0, (node, component.volume)
            checked += 1
    assert checked > 100


def test_original_flange_groove_notch_walls_and_post_sides_are_retained():
    flange = original_araki("araki_bt_flange.glb")
    repaired = repair_flange(flange)
    original = flange.triangles
    planar = (np.abs(original[:, :, 2] - flange.bounds[0, 2]) < 1e-9).all(1)
    planar |= (np.abs(original[:, :, 2]) < 1e-9).all(1)
    for y in (-0.016299987211823463, 0.016299987211823463):
        planar |= (np.abs(original[:, :, 1] - y) < 1e-9).all(1)
    assert not (
        triangle_keys(flange.vertices, flange.faces[~planar])
        - triangle_keys(repaired.vertices, repaired.faces)
    )
    np.testing.assert_allclose(repaired.bounds, flange.bounds, atol=1e-12)

    post = original_araki("araki_3030_post.glb")
    repaired = repair_post(post)
    ends = (np.abs(post.triangles[:, :, 2]) < 1e-9).all(1)
    ends |= (np.abs(post.triangles[:, :, 2] - 1.5) < 1e-9).all(1)
    assert not (
        triangle_keys(post.vertices, post.faces[~ends]) - triangle_keys(repaired.vertices, repaired.faces)
    )
    np.testing.assert_allclose(repaired.bounds, post.bounds, atol=1e-12)


def test_actual_flange_bore_and_upright_t_slot_channels_stay_open():
    spec = load_scene("cnc_toolchange")
    tool = next(o for o in spec.objects if o.object_id == "T09")
    flange = next(m for n, m in local_parts(tool) if "Araki_BT_source_V_groove_flange" in n)
    np.testing.assert_allclose(flange.extents[:2], [0.063, 0.063], atol=1e-7)
    assert abs(flange.bounds[0, 2] + 0.015) < 1e-7
    assert_clear_axis(flange, (0, 0), -0.03, 0.03)
    posts = [m for n, m in local_parts(spec.environment[0]) if "Araki_3030_upright" in n]
    assert len(posts) == 2
    for post in posts:
        center = post.bounds.mean(0)
        for offset in [(0, 0), (0.014, 0), (-0.014, 0), (0, 0.014), (0, -0.014)]:
            xy = center[:2] + np.asarray(offset) * 1.11
            assert_clear_axis(post, xy, post.bounds[0, 2] - 0.01, post.bounds[1, 2] + 0.01)


@pytest.mark.parametrize("asset_id", ["tool_cart", "WoodenTable_03", "metal_toolbox", "lubricant_spray"])
def test_all_mature_source_triangle_positions_and_uv_corners_remain(asset_id):
    source = mature_asset(asset_id)
    repaired = repair_mature_scene(source, asset_id)
    original = Counter()
    for mesh in source.geometry.values():
        original += triangle_keys(mesh.vertices, mesh.faces, mesh.visual.uv)
    retained = Counter()
    for mesh in repaired.geometry.values():
        retained += triangle_keys(mesh.vertices, mesh.faces, mesh.visual.uv)
    assert not (original - retained), asset_id
    assert len(repaired.geometry) <= len(source.geometry) * 3


def test_actual_cutter_keeps_its_complete_closed_body_and_source_envelope():
    spec = load_scene("cnc_toolchange")
    tool = next(o for o in spec.objects if o.object_id == "T09")
    cutter = next(m for n, m in local_parts(tool) if "carbide_endmill" in n)
    assert len(cutter.faces) == 13996
    source = trimesh.load_scene(
        root() / "assets/downloads/cnc_reconstruction/ubc_er_components.glb", process=False
    )
    source.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    source.apply_translation([-0.3065, 0.131, 0])
    source.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    source.apply_scale(0.030)
    source.apply_translation([0, 0, -0.100 + 1.9337472915649414 * 0.030])
    for node in source.graph.nodes_geometry:
        transform, key = source.graph[node]
        if key == "vl002b_defaultMat.003_0.007":
            original = copy_mesh(source.geometry[key]).apply_transform(transform)
            np.testing.assert_allclose(cutter.bounds, original.bounds, atol=1e-8)
            assert len(original.faces) - len(cutter.faces) == 2
            return
    raise AssertionError("Original cutter source not found")
