"""Run-scoped GPU authorization and caller cache propagation, without GPU work."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT = Path(__file__).resolve().parents[1]
GUARD = PROJECT / "scripts/guard/resource_guard.py"
spec = importlib.util.spec_from_file_location("gpu_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_default_and_explicit_run_authorization():
    assert guard.parse_selection("1,2") == [1, 2]
    assert guard.parse_selection("") == []
    assert guard.parse_selection("7, 4,1", "1,2,4,5,6,7") == [7, 4, 1]
    assert guard.parse_selection("", "") == []
    with pytest.raises(ValueError, match="subset"):
        guard.parse_selection("4")
    with pytest.raises(ValueError, match="subset"):
        guard.parse_selection("3", "1,2,4,5,6,7")


@pytest.mark.parametrize("value", ["-1", "+1", "1.0", "1e0", "1,,2", "1,", " ", "all", "１", "1,01"])
def test_reject_non_integer_or_duplicate_physical_indices(value):
    with pytest.raises(ValueError):
        guard.parse_selection(value, "1,2,4,5,6,7")
    with pytest.raises(ValueError):
        guard.parse_selection("", value)


def json_stream(text):
    decoder = json.JSONDecoder()
    rows = []
    while text.strip():
        row, end = decoder.raw_decode(text.lstrip())
        rows.append(row)
        text = text.lstrip()[end:]
    return rows


def test_allowlist_and_cache_reach_real_nested_guard(tmp_path):
    assert tmp_path.resolve().is_relative_to(PROJECT)
    cache = tmp_path / "caller_pycache"
    environment = os.environ.copy()
    environment.update(
        PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(cache), HOLOCUE_AUTHORIZED_GPUS="1,2"
    )
    worker = "import json, os; print(json.dumps({key: os.environ[key] for key in ('HOLOCUE_AUTHORIZED_GPUS', 'PYTHONPYCACHEPREFIX', 'CUDA_VISIBLE_DEVICES')}))"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GUARD),
            "--authorized-gpus",
            "1,2,4,5,6,7",
            "--rss-limit-gb",
            "1",
            "--log",
            str(tmp_path / "outer.jsonl"),
            "--execute",
            "--",
            sys.executable,
            "-B",
            str(GUARD),
            "--rss-limit-gb",
            "1",
            "--log",
            str(tmp_path / "inner.jsonl"),
            "--execute",
            "--",
            sys.executable,
            "-B",
            "-c",
            worker,
        ],
        env=environment,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    records = json_stream(result.stdout)
    assert len(records) == 3
    policies = [row for row in records if "authorized_physical_gpus" in row]
    assert len(policies) == 2
    assert all(row["authorized_physical_gpus"] == [1, 2, 4, 5, 6, 7] for row in policies)
    assert all(row["selected_physical_gpus"] == [] for row in policies)
    assert next(row for row in records if "PYTHONPYCACHEPREFIX" in row) == {
        "HOLOCUE_AUTHORIZED_GPUS": "1,2,4,5,6,7",
        "PYTHONPYCACHEPREFIX": str(cache),
        "CUDA_VISIBLE_DEVICES": "",
    }


def test_default_cache_only_when_caller_did_not_supply_one(tmp_path):
    assert tmp_path.resolve().is_relative_to(PROJECT)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPYCACHEPREFIX", None)
    environment.pop("HOLOCUE_AUTHORIZED_GPUS", None)
    worker = "import json, os; print(json.dumps({'prefix': os.environ['PYTHONPYCACHEPREFIX']}))"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GUARD),
            "--rss-limit-gb",
            "1",
            "--log",
            str(tmp_path / "guard.jsonl"),
            "--execute",
            "--",
            sys.executable,
            "-B",
            "-c",
            worker,
        ],
        env=environment,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    records = json_stream(result.stdout)
    assert next(row for row in records if "authorized_physical_gpus" in row)["authorized_physical_gpus"] == [
        1,
        2,
    ]
    assert next(row for row in records if "prefix" in row)["prefix"] == str(PROJECT / ".work/pycache")


@pytest.mark.parametrize(
    "arguments",
    [["--gpus", "4"], ["--authorized-gpus", "1,2,4", "--gpus", "5"], ["--authorized-gpus", "1,-2"]],
)
def test_invalid_cli_rejected_before_gpu_inventory(arguments):
    environment = os.environ.copy()
    environment.pop("HOLOCUE_AUTHORIZED_GPUS", None)
    result = subprocess.run(
        [sys.executable, "-B", str(GUARD), *arguments],
        env=environment,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert not result.stdout.strip()
