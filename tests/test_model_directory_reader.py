"""Read actual tiny safetensors files through the production metadata validator."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from safetensors import SafetensorError
from safetensors.numpy import save_file

MODULE = Path(__file__).resolve().parents[1] / "scripts/ops/validate_model_dir.py"
SPEC = importlib.util.spec_from_file_location("holocue_model_directory_reader", MODULE)
assert SPEC is not None and SPEC.loader is not None
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


@pytest.fixture
def model_directory(tmp_path):
    directory = tmp_path / "model_directory_input"
    directory.mkdir()
    for name, content in (
        ("config.json", {"model_type": "qwen3_5"}),
        ("tokenizer_config.json", {}),
        ("tokenizer.json", {}),
    ):
        (directory / name).write_text(json.dumps(content), encoding="utf-8")
    save_file({"weight": np.arange(16, dtype=np.float32).reshape(4, 4)}, directory / "model.safetensors")
    return directory


def test_real_metadata_reader(model_directory):
    result = READER.validate(model_directory)
    assert result["shards"] == 1 and result["tensor_count"] == 1
    assert result["total_bytes"] == (model_directory / "model.safetensors").stat().st_size
    assert result["content_hash_verified"] is False


def test_real_index_is_checked(model_directory):
    path = model_directory / "model.safetensors.index.json"
    path.write_text(json.dumps({"weight_map": {"weight": "model.safetensors"}}), encoding="utf-8")
    assert READER.validate(model_directory)["tensor_count"] == 1


def test_index_tensor_mismatch_fails(model_directory):
    path = model_directory / "model.safetensors.index.json"
    path.write_text(json.dumps({"weight_map": {"missing": "model.safetensors"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="mapping disagree"):
        READER.validate(model_directory)


def test_incomplete_shard_fails_in_library(model_directory):
    path = model_directory / "model.safetensors"
    path.write_bytes(path.read_bytes()[:-9])
    with pytest.raises(SafetensorError):
        READER.validate(model_directory)


def test_index_path_escape_fails(model_directory):
    path = model_directory / "model.safetensors.index.json"
    path.write_text(json.dumps({"weight_map": {"weight": "../outside.safetensors"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        READER.validate(model_directory)


def test_empty_index_fails(model_directory):
    path = model_directory / "model.safetensors.index.json"
    path.write_text(json.dumps({"weight_map": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty"):
        READER.validate(model_directory)
