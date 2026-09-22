"""Real container validation with the official Khronos validator."""

import pytest
import trimesh
from pygltflib import GLTF2, Accessor, Sparse

from holocue.gltf_validation import validate_glb, require_dense_accessors


def test_valid_glb_and_trailing_or_truncated_bytes(tmp_path):
    path = tmp_path / "box.glb"
    trimesh.Scene(trimesh.creation.box()).export(path, file_type="glb")
    report = validate_glb(path)
    assert report["report"]["issues"]["numErrors"] == 0
    original = path.read_bytes()
    for name, data in [("trailing", original + b"bad!"), ("truncated", original[:-1])]:
        damaged = tmp_path / (name + ".glb")
        damaged.write_bytes(data)
        with pytest.raises(ValueError):
            validate_glb(damaged)


def test_dense_and_sparse_accessor_contract():
    document = GLTF2(accessors=[Accessor(componentType=5126, count=1, type="VEC3")])
    require_dense_accessors(document)
    document.accessors[0].sparse = Sparse(count=1)
    with pytest.raises(ValueError, match="must be dense"):
        require_dense_accessors(document)
