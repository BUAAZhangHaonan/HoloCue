"""Functional checks using actual GLB exports and authored normal arrays."""

from pathlib import Path

import numpy as np
import pytest
import trimesh
from trimesh.exchange.gltf import export_glb

from holocue.glb_attributes import exported_normals


def write_asset(directory: Path, include_normals: bool = True):
    mesh = trimesh.creation.box(extents=(0.004, 0.007, 0.009))
    normals = np.tile(np.array([0.6, 0.8, 0.0], dtype=np.float32), (len(mesh.vertices), 1))
    mesh.vertex_normals = normals
    scene = trimesh.Scene()
    scene.add_geometry(
        mesh,
        geom_name="mesh_payload",
        node_name="CLAMP/component",
        transform=trimesh.transformations.rotation_matrix(0.7, [1, 0, 0]),
    )
    path = directory / "component.glb"
    path.write_bytes(export_glb(scene, include_normals=include_normals, unitize_normals=False))
    return path, normals


def test_stored_values_and_order_survive_export(tmp_path):
    path, expected = write_asset(tmp_path)
    result = exported_normals(path, "CLAMP/component")
    np.testing.assert_array_equal(result, expected)
    assert result.dtype == np.dtype("float32")


def test_local_normals_are_independent_of_node_rotation(tmp_path):
    path, expected = write_asset(tmp_path)
    result = exported_normals(path, "CLAMP/component")
    np.testing.assert_array_equal(result, expected)
    rotation = trimesh.transformations.rotation_matrix(0.7, [1, 0, 0])[:3, :3]
    assert not np.allclose(result, expected @ rotation.T)


def test_missing_normals_fail_at_the_reader(tmp_path):
    path, _ = write_asset(tmp_path, include_normals=False)
    with pytest.raises(ValueError, match="no stored NORMAL"):
        exported_normals(path, "CLAMP/component")


def test_missing_node_fails(tmp_path):
    path, _ = write_asset(tmp_path)
    with pytest.raises(ValueError, match="found 0"):
        exported_normals(path, "missing")


def test_returned_array_owns_its_values(tmp_path):
    path, expected = write_asset(tmp_path)
    first = exported_normals(path, "CLAMP/component")
    first[:] = 0
    np.testing.assert_array_equal(exported_normals(path, "CLAMP/component"), expected)


def test_invalid_extension_fails(tmp_path):
    with pytest.raises(ValueError, match="GLB"):
        exported_normals(tmp_path / "component.obj", "component")


def test_empty_node_name_fails(tmp_path):
    with pytest.raises(ValueError, match="node name"):
        exported_normals(tmp_path / "component.glb", "")


def test_missing_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        exported_normals(tmp_path / "missing.glb", "component")


def test_multiple_named_meshes_are_resolved_separately(tmp_path):
    scene = trimesh.Scene()
    expected = {}
    for index, direction in enumerate(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))):
        mesh = trimesh.creation.icosphere(subdivisions=1, radius=0.01)
        values = np.tile(np.asarray(direction, dtype=np.float32), (len(mesh.vertices), 1))
        mesh.vertex_normals = values
        name = f"assembly/part_{index}"
        expected[name] = values
        scene.add_geometry(mesh, geom_name=f"geometry_{index}", node_name=name)
    path = tmp_path / "assembly.glb"
    path.write_bytes(export_glb(scene, include_normals=True, unitize_normals=False))
    for name, values in expected.items():
        np.testing.assert_array_equal(exported_normals(path, name), values)
