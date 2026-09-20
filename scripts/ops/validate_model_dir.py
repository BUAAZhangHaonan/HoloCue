"""Inspect Qwen model metadata with the official lazy safetensors reader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from safetensors import safe_open


def validate(path):
    path = Path(path).resolve()
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    if config.get("model_type") != "qwen3_5":
        raise ValueError("Expected official Qwen3.5 dense multimodal configuration")
    for filename in ("tokenizer_config.json", "tokenizer.json"):
        if not (path / filename).is_file():
            raise FileNotFoundError(filename)
    index_path = path / "model.safetensors.index.json"
    weight_map = None
    if index_path.is_file():
        weight_map = json.loads(index_path.read_text(encoding="utf-8"))["weight_map"]
        if not isinstance(weight_map, dict) or not weight_map:
            raise ValueError("Model weight_map must be a nonempty object")
        names = sorted(set(weight_map.values()))
    else:
        names = sorted(file.name for file in path.glob("*.safetensors"))
    if not names:
        raise ValueError("No safetensors shards found")
    total_bytes, tensor_count = 0, 0
    tensor_shards = {}
    for name in names:
        shard = (path / name).resolve()
        if not shard.is_relative_to(path):
            raise ValueError("Shard path escapes the model directory")
        if not shard.is_file():
            raise FileNotFoundError(shard)
        with safe_open(shard, framework="numpy", device="cpu") as reader:
            keys = list(reader.keys())
            if not keys:
                raise ValueError("Empty model shard: " + name)
            for key in keys:
                if key in tensor_shards:
                    raise ValueError("Tensor occurs in multiple shards: " + key)
                tensor_shards[key] = name
                reader.get_slice(key).get_shape()
            tensor_count += len(keys)
        total_bytes += shard.stat().st_size
    if weight_map is not None and weight_map != tensor_shards:
        raise ValueError("Model index and actual tensor-to-shard mapping disagree")
    return {"path": str(path), "model_type": config["model_type"],
            "architectures": config.get("architectures"), "shards": len(names),
            "total_bytes": total_bytes, "tensor_count": tensor_count,
            "validation": "metadata_and_lengths", "content_hash_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    print(json.dumps(validate(args.path), indent=2))
