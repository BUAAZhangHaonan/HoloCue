"""Real GLB round trips for smooth surfaces, hard rims and textured labels."""

import numpy as np
import pytest
import trimesh
from pygltflib import GLTF2
from trimesh.exchange.gltf import load_glb

from holocue.modeling import Assembly
from holocue.gltf_validation import validate_glb, require_dense_accessors


def glb_contents(path):
    validate_glb(path)
    document = GLTF2().load(str(path))
    assert document.asset.version == "2.0"
    require_dense_accessors(document)
    with path.open("rb") as stream:
        decoded = load_glb(stream, ignore_broken=False, merge_primitives=False)
    return document, decoded


def geometry(decoded, node_name):
    edges = [edge for edge in decoded["graph"] if edge["frame_to"] == node_name]
    assert len(edges) == 1 and "geometry" in edges[0]
    return decoded["geometry"][edges[0]["geometry"]]


def primitive(document, node_name):
    node = next(node for node in document.nodes if node.name == node_name)
    primitives = document.meshes[node.mesh].primitives
    assert len(primitives) == 1
    return primitives[0]


def mesh_for_node(scene, name):
    _, geometry = scene.graph[name]
    return scene.geometry[geometry]


@pytest.fixture
def exported_probe(tmp_path):
    assembly = Assembly("normal_probe")
    assembly.cylinder(0.02, 0.10, color=(23, 81, 141), name="cylinder")
    assembly.add(
        trimesh.creation.box(extents=(0.01, 0.02, 0.03)),
        color=(201, 61, 22),
        position=(0.10, 0, 0),
        metal=0.37,
        rough=0.68,
        name="pbr_probe",
    )
    assembly.label("UV TEST", (0.15, 0, 0.10), 0.08, 0.03)
    label_name = "normal_probe/label_2"
    original_label = mesh_for_node(assembly.scene, label_name)
    expected_uv = original_label.visual.uv.copy()
    expected_image = np.asarray(original_label.visual.material.baseColorTexture.convert("RGBA")).copy()
    path = tmp_path / "normal_probe.glb"
    assembly.save(path)
    document, binary = glb_contents(path)
    reloaded = trimesh.load_scene(path, process=False)
    return document, binary, reloaded, expected_uv, expected_image


def test_exported_cylinder_smooth_sides_and_hard_flat_caps(exported_probe):
    document, binary, _, _, _ = exported_probe
    # Inspect actual exported NORMAL accessors, not normals recomputed by reload.
    for node in document.nodes:
        if node.mesh is not None:
            part = primitive(document, node.name)
            assert part.attributes.NORMAL is not None
            assert document.accessors[part.attributes.NORMAL].componentType == 5126
            raw = geometry(binary, node.name)
            normals = np.asarray(raw["vertex_normals"])
            positions = np.asarray(raw["vertices"])
            assert normals.shape == positions.shape
            assert np.isfinite(normals).all()
            np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, atol=2e-6)

    raw = geometry(binary, "normal_probe/0000_cylinder")
    positions = np.asarray(raw["vertices"])
    normals = np.asarray(raw["vertex_normals"])
    faces = np.asarray(raw["faces"])
    # The exporter may bake its Y-up conversion or put it in a node transform.
    # In either representation, this unrotated cylinder has a cardinal axis.
    axis = int(np.argmax(np.ptp(positions, axis=0)))
    radial_axes = [i for i in range(3) if i != axis]
    cap_face = np.ptp(positions[faces, axis], axis=1) < 1e-7
    assert int(cap_face.sum()) == 80  # Two 40-triangle fan caps.
    assert int((~cap_face).sum()) == 80  # Forty side panels, two triangles each.
    cap_indices = np.unique(faces[cap_face])
    side_indices = np.unique(faces[~cap_face])
    assert not np.intersect1d(cap_indices, side_indices).size
    np.testing.assert_allclose(normals[cap_indices][:, radial_axes], 0, atol=2e-6)
    np.testing.assert_allclose(normals[cap_indices, axis], np.sign(positions[cap_indices, axis]), atol=2e-6)
    np.testing.assert_allclose(normals[side_indices, axis], 0, atol=2e-6)
    radial = positions[side_indices][:, radial_axes]
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    alignment = np.einsum("ij,ij->i", radial, normals[side_indices][:, radial_axes])
    assert np.all(alignment > 0.999), (
        "Side normals must follow the cylinder radius, not individual flat panels"
    )

    corner_indices = faces[~cap_face].ravel()
    unique_positions, inverse = np.unique(np.round(positions[corner_indices], 7), axis=0, return_inverse=True)
    assert len(unique_positions) == 80
    for index in range(len(unique_positions)):
        shared = normals[corner_indices[inverse == index]]
        np.testing.assert_allclose(shared, np.broadcast_to(shared[0], shared.shape), atol=2e-6)


def test_exported_pbr_values_survive_smoothing_and_reload(exported_probe):
    document, _, reloaded, _, _ = exported_probe
    for node_name, color, metal, rough in [
        ("normal_probe/0000_cylinder", (23, 81, 141, 255), 0.1, 0.44),
        ("normal_probe/0001_pbr_probe", (201, 61, 22, 255), 0.37, 0.68),
    ]:
        part = primitive(document, node_name)
        material = document.materials[part.material].pbrMetallicRoughness
        assert material.baseColorFactor == pytest.approx(np.asarray(color) / 255)
        assert material.metallicFactor == pytest.approx(metal)
        assert material.roughnessFactor == pytest.approx(rough)
        actual = mesh_for_node(reloaded, node_name).visual.material
        np.testing.assert_array_equal(actual.baseColorFactor, color)
        assert actual.metallicFactor == pytest.approx(metal)
        assert actual.roughnessFactor == pytest.approx(rough)


def test_label_uv_and_embedded_texture_survive_normal_export(exported_probe):
    document, _, reloaded, expected_uv, expected_image = exported_probe
    part = primitive(document, "normal_probe/label_2")
    assert part.attributes.NORMAL is not None
    assert part.attributes.TEXCOORD_0 is not None
    pbr = document.materials[part.material].pbrMetallicRoughness
    texture = document.textures[pbr.baseColorTexture.index]
    assert document.images[texture.source].bufferView is not None, "Label image must be embedded in the GLB"
    actual = mesh_for_node(reloaded, "normal_probe/label_2").visual
    np.testing.assert_allclose(actual.uv, expected_uv, atol=1e-7)
    np.testing.assert_array_equal(
        np.asarray(actual.material.baseColorTexture.convert("RGBA")), expected_image
    )
    assert np.unique(expected_image.reshape(-1, 4), axis=0).shape[0] > 2, (
        "Use a real rendered label, not a solid-color placeholder"
    )
