"""Read stored glTF vertex attributes through Trimesh's public GLB loader."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from trimesh.exchange.gltf import load_glb


def exported_normals(path: Path | str, node_name: str) -> np.ndarray:
    """Read one component's stored NORMAL values in mesh-local coordinates.

    HoloCue exports one primitive per named component. Trimesh handles container
    decoding, accessor offsets, and buffer strides. Constructor arguments retain
    the exported values and ordering before any mesh processing occurs.
    """
    source = Path(path)
    if not node_name:
        raise ValueError("A component node name is required")
    if source.suffix.lower() != ".glb":
        raise ValueError("The input must be a GLB asset")
    with source.open("rb") as stream:
        decoded = load_glb(stream, ignore_broken=False, merge_primitives=False, skip_materials=True)
    matches = [edge for edge in decoded["graph"] if edge["frame_to"] == node_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one named component {node_name!r}, found {len(matches)}")
    edge = matches[0]
    if "geometry" not in edge:
        raise ValueError(f"Component {node_name!r} must contain exactly one mesh primitive")
    geometry = decoded["geometry"][edge["geometry"]]
    if "vertex_normals" not in geometry:
        raise ValueError(f"Component {node_name!r} has no stored NORMAL accessor")
    normals = np.asarray(geometry["vertex_normals"])
    vertices = np.asarray(geometry["vertices"])
    if normals.ndim != 2 or normals.shape[1] != 3 or normals.shape != vertices.shape:
        raise ValueError(f"NORMAL and POSITION shapes disagree for {node_name!r}")
    if normals.dtype.kind != "f" or normals.dtype.itemsize != 4:
        raise ValueError(f"NORMAL must use float32 components for {node_name!r}")
    if not np.isfinite(normals).all():
        raise ValueError(f"NORMAL contains nonfinite values for {node_name!r}")
    return normals.copy()
