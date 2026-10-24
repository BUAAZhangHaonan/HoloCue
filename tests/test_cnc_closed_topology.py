"""Actual CNC solid exports, retained source surfaces, and open interface voids."""

from collections import Counter
from io import BytesIO

import numpy as np
import pytest
import trimesh
import vtk
from scipy.spatial import cKDTree

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.render_validation import polydata
from holocue.spatial import matrix
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


def triangle_keys(vertices, faces, uv=None, normals=None):
    values = vertices if uv is None else np.c_[vertices, uv]
    if normals is not None:
        values = np.c_[values, normals]
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


@pytest.mark.parametrize("asset_id", ["tool_cart", "WoodenTable_03", "metal_toolbox", "lubricant_spray"])
def test_original_source_corner_normals_survive_repairs_and_packing(asset_id):
    source = mature_asset(asset_id)
    repaired = repair_mature_scene(source, asset_id)
    original, retained = Counter(), Counter()
    for mesh in source.geometry.values():
        original += triangle_keys(mesh.vertices, mesh.faces, mesh.visual.uv, mesh.vertex_normals)
    for mesh in repaired.geometry.values():
        retained += triangle_keys(mesh.vertices, mesh.faces, mesh.visual.uv, mesh.vertex_normals)
        added = ~mesh.face_attributes["cnc_source_surface"]
        np.testing.assert_allclose(
            np.linalg.norm(mesh.vertex_normals[mesh.faces[added]], axis=2), 1, atol=1e-6
        )
    assert not (original - retained), asset_id


def test_workbench_source_normals_survive_real_gltf_serialization():
    # This source's front metal door exposed the regression in the real Blender
    # view: recalculated normals made a broad black/white triangular seam.
    source = mature_asset("WoodenTable_03")
    repaired = repair_mature_scene(source, "WoodenTable_03")
    exported = trimesh.load_scene(BytesIO(repaired.export(file_type="glb")), file_type="glb", process=False)
    candidates = {}
    for mesh in exported.geometry.values():
        for corner, normal in zip(np.c_[mesh.vertices, mesh.visual.uv], mesh.vertex_normals):
            candidates.setdefault(tuple(np.round(corner, 6)), []).append(normal)
    for key, mesh in source.geometry.items():
        source_normals = trimesh.util.unitize(mesh.vertex_normals)
        for corner, normal in zip(np.c_[mesh.vertices, mesh.visual.uv], source_normals):
            matches = np.asarray(candidates[tuple(np.round(corner, 6))])
            assert np.linalg.norm(matches - normal, axis=1).min() < 3e-7, (key, corner, normal)

    # Read NORMAL directly from the actual final workstation GLB. Trimesh's
    # default .copy() drops imported normals from its cache, so using that test
    # helper here would measure recalculated normals instead of disk attributes.
    spec = load_scene("cnc_toolchange")
    entry = spec.environment[0]
    actual = load_asset(str(root() / entry.asset), spec.asset_axes)
    environment = matrix(entry.pose) @ np.diag([*entry.scale_m, 1.0])
    corners, normals = [], []
    for node in actual.graph.nodes_geometry:
        if "mature_workbench" not in node:
            continue
        transform, key = actual.graph[node]
        transform = environment @ transform
        mesh = actual.geometry[key]
        corners.append(np.c_[trimesh.transform_points(mesh.vertices, transform), mesh.visual.uv])
        normals.append(trimesh.util.unitize(mesh.vertex_normals @ np.linalg.inv(transform[:3, :3])))
    assert corners
    corners, normals = np.concatenate(corners), np.concatenate(normals)
    tree = cKDTree(corners)
    scale = 0.980 / repaired.extents[2]
    scaled_bounds = repaired.bounds * scale
    placement = np.diag([scale, scale, scale, 1.0])
    placement[:3, 3] = np.array([0.03, 0.02, 0.0]) - np.r_[scaled_bounds.mean(0)[:2], scaled_bounds[0, 2]]
    checked = 0
    for node in source.graph.nodes_geometry:
        transform, key = source.graph[node]
        transform = environment @ placement @ transform
        mesh = source.geometry[key]
        positions = trimesh.transform_points(mesh.vertices, transform)
        expected = trimesh.util.unitize(mesh.vertex_normals @ np.linalg.inv(transform[:3, :3]))
        for point, normal in zip(np.c_[positions, mesh.visual.uv], expected):
            nearby = tree.query_ball_point(point, 1e-6)
            assert nearby, ("final workstation missing source corner", key, point)
            nearby = np.asarray(nearby)
            matched = nearby[(np.abs(corners[nearby] - point) < 2e-7).all(1)]
            assert len(matched), (key, point)
            assert np.linalg.norm(normals[matched] - normal, axis=1).min() < 3e-7, (key, point, normal)
            checked += 1
    assert checked > 1000


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
