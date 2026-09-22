"""Host policy boundaries and real CLI/environment propagation."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import psutil
import pytest

PROJECT = Path(__file__).resolve().parents[1]
GUARD = PROJECT / "scripts/guard/resource_guard.py"
spec = importlib.util.spec_from_file_location("memory_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_default_policy_preserved():
    assert guard.host_memory_reserve(252 * guard.GIB, 32) == pytest.approx(50.4 * guard.GIB)
    assert guard.host_memory_reserve(64 * guard.GIB, 32) == 32 * guard.GIB


def test_explicit_ninety_percent_policy():
    assert guard.host_memory_reserve(252 * guard.GIB, 32, 0.90) == pytest.approx(25.2 * guard.GIB)


@pytest.mark.parametrize("fraction", [0, -0.1, 0.9001, 1, float("nan"), float("inf")])
def test_reject_policy_above_authorized_limit(fraction):
    with pytest.raises(ValueError):
        guard.host_memory_reserve(252 * guard.GIB, 32, fraction)


def test_environment_policy_reaches_actual_guard():
    environment = os.environ.copy()
    environment["HOLOCUE_HOST_MAX_USED_FRACTION"] = "0.90"
    result = subprocess.run(
        [sys.executable, str(GUARD), "--host-reserve-gb", "32"],
        env=environment,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(result.stdout)
    assert info["host_reserve_gib"] == pytest.approx(psutil.virtual_memory().total / guard.GIB * 0.10)
    assert info["host_max_used_fraction"] == 0.90
    assert info["host_reserve_policy"] == "explicit-used-fraction"


def test_cli_policy_propagates_to_nested_guard(tmp_path):
    assert tmp_path.resolve().is_relative_to(PROJECT)
    environment = os.environ.copy()
    environment.pop("HOLOCUE_HOST_MAX_USED_FRACTION", None)
    result = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--host-max-used-fraction",
            ".90",
            "--log",
            str(tmp_path / "guard.jsonl"),
            "--execute",
            "--",
            sys.executable,
            str(GUARD),
        ],
        env=environment,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=True,
    )
    decoder = json.JSONDecoder()
    text = result.stdout
    records = []
    while text.strip():
        info, end = decoder.raw_decode(text.lstrip())
        records.append(info)
        text = text.lstrip()[end:]
    assert len(records) == 2
    assert all(row["host_max_used_fraction"] == 0.90 for row in records)
    assert all(
        row["host_reserve_gib"] == pytest.approx(psutil.virtual_memory().total / guard.GIB * 0.10)
        for row in records
    )
