"""Compose the two asset-led workstations from licensed, material-preserving sources."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
import trimesh

from holocue.config import root


@lru_cache(maxsize=32)
def mature_asset(asset_id):
    """The existing shared pool was exported explicitly with export_yup=False."""
    return trimesh.load_scene(root() / "assets/meshes/env" / f"{asset_id}.glb", process=False)


def place_scene(assembly, source, size, center, rz=0, label="asset"):
    source = source.copy()
    if rz:
        source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    source.apply_translation(-source.bounds.mean(axis=0))
    if size is not None:
        source.apply_scale(np.asarray(size) / source.extents)
    source.apply_translation(center)
    for node in source.graph.nodes_geometry:
        transform, geometry_name = source.graph[node]
        name = f"{assembly.name}/{assembly.index:04d}_{label}_{node}"
        assembly.scene.add_geometry(
            source.geometry[geometry_name].copy(), node_name=name, geom_name=name, transform=transform
        )
        assembly.index += 1
    return source.bounds.copy()


def place_asset(assembly, asset_id, size, center, rz=0, label=None):
    return place_scene(assembly, mature_asset(asset_id), size, center, rz, label or asset_id)


@lru_cache(maxsize=12)
def surface_material(texture_id):
    directory = root() / "assets/downloads/polyhaven/textures" / texture_id

    def image(name):
        with Image.open(directory / name) as im:
            return im.convert("RGB").copy()

    arm = directory / "arm_1k.jpg"
    material = trimesh.visual.material.PBRMaterial(
        name="PolyHaven_" + texture_id,
        baseColorTexture=image("Diffuse_1k.jpg"),
        normalTexture=image("nor_gl_1k.jpg"),
        metallicRoughnessTexture=image(arm.name),
        occlusionTexture=image("AO_1k.jpg"),
        metallicFactor=1.0,
        roughnessFactor=1.0,
    )
    return material


def textured_box(assembly, size, center, texture_id, tile_m=1.0, name=None):
    """Physical-scale UVs, split face normals, embedded albedo/normal/ARM maps."""
    mesh = trimesh.creation.box(extents=size)
    vertices, uv, faces, normals = [], [], [], []
    for face, normal in zip(mesh.faces, mesh.face_normals):
        triangle = mesh.vertices[face]
        axis = int(np.argmax(np.abs(normal)))
        axes = [i for i in range(3) if i != axis]
        begin = len(vertices)
        vertices.extend(triangle)
        normals.extend([normal] * 3)
        uv.extend(triangle[:, axes] / tile_m)
        faces.append([begin, begin + 1, begin + 2])
    item = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        vertex_normals=normals,
        process=False,
        visual=trimesh.visual.TextureVisuals(uv=uv, material=surface_material(texture_id)),
    )
    item.apply_translation(center)
    key = f"{assembly.name}/{assembly.index:04d}_{name or texture_id}"
    assembly.scene.add_geometry(item, node_name=key, geom_name=key)
    assembly.index += 1
    return item
