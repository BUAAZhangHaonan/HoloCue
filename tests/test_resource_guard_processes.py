"""Real Linux lifecycle checks for owned descendants with independent sessions.

The worker is this checked-in file, never generated source. Tests use project
temporary storage and do not signal process groups or unrelated descendants.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil
import pytest


PROJECT = Path(__file__).resolve().parents[1]


def wait_for(read, predicate, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = read()
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"Process lifecycle condition timed out: {last}")


def identities(directory):
    return [json.loads(path.read_text()) for path in directory.glob("*_identity.json")]


def active(identity):
    try:
        process = psutil.Process(identity["pid"])
        return process.create_time() == identity["create_time"] and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def cleanup(records):
    owned = []
    for record in records:
        if active(record):
            process = psutil.Process(record["pid"])
            if process.create_time() == record["create_time"]:
                process.terminate()
                owned.append(process)
    _, alive = psutil.wait_procs(owned, timeout=3)
    for process in alive:
        expected = next(row for row in records if row["pid"] == process.pid)
        if active(expected):
            process.kill()
    psutil.wait_procs(alive, timeout=3)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process sessions and resource guard")
@pytest.mark.parametrize("termination", ["interrupt", "normal_exit", "quick_exit"])
def test_guard_cleans_owned_independent_process_sessions(tmp_path, termination):
    for key in ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "PIP_CACHE_DIR", "PLAYWRIGHT_BROWSERS_PATH"):
        assert key in os.environ and Path(os.environ[key]).resolve().is_relative_to(PROJECT)
    assert tmp_path.resolve().is_relative_to(PROJECT)
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert Path("/usr/share/glvnd/egl_vendor.d/50_mesa.json").is_file()
    worker = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    log_path = tmp_path / "guard.jsonl"
    root_role = "root_quick" if termination == "quick_exit" else "root"
    guard_command = [
        sys.executable,
        str(PROJECT / "scripts/guard/resource_guard.py"),
        "--rss-limit-gb",
        "8",
        "--log",
        str(log_path),
        "--execute",
        "--",
        *worker,
        root_role,
        str(tmp_path),
    ]
    sentinel_dir = tmp_path / "unrelated_sibling"
    sentinel_dir.mkdir()
    sentinel = subprocess.Popen([*worker, "sentinel", str(sentinel_dir)], start_new_session=True)
    guard = None
    records = []
    try:
        wait_for(lambda: identities(sentinel_dir), lambda rows: len(rows) == 1)
        with (tmp_path / "guard_stdout.log").open("wb") as output:
            guard = subprocess.Popen(
                guard_command, cwd=PROJECT, stdout=output, stderr=subprocess.STDOUT, start_new_session=True
            )
            roles = {root_role, "orphan"} if termination == "quick_exit" else {root_role, "child", "leaf"}
            records = wait_for(
                lambda: identities(tmp_path), lambda rows: {row["role"] for row in rows} == roles
            )
            assert len({row["pgid"] for row in records}) == len(roles)
            assert all(row["cuda_visible_devices"] == "" for row in records)
            by_role = {row["role"]: row for row in records}
            assert by_role[root_role]["ppid"] == guard.pid
            assert all(row["pgid"] == row["pid"] for row in records)
            if termination == "quick_exit":
                ready_path = tmp_path / "root_quick_exit_ready.json"
                wait_for(ready_path.exists, bool)
                ready = json.loads(ready_path.read_text())
                # Popen's setsid completes before it returns. The parent records
                # the actual child's identity before exiting; the guard may
                # then clean it before its Python module has finished loading.
                assert by_role["orphan"]["ppid"] == by_role[root_role]["pid"]
                assert by_role["orphan"]["recorded_by_pid"] == by_role[root_role]["pid"]
                assert by_role["orphan"]["identity_source"] == "parent_verified_child"
                assert ready["orphan_alive_before_root_exit"]
                assert ready["orphan_pid"] == by_role["orphan"]["pid"]
            else:
                assert all(row["identity_source"] == "worker_self" for row in records)
                assert by_role["child"]["ppid"] == by_role[root_role]["pid"]
                assert by_role["leaf"]["ppid"] == by_role["child"]["pid"]
            if termination != "quick_exit":
                wait_for(
                    lambda: log_path.read_text().splitlines() if log_path.exists() else [],
                    lambda rows: len(rows) >= 2,
                )
            assert sentinel.poll() is None
            if termination == "interrupt":
                guard.send_signal(signal.SIGINT)
            elif termination == "normal_exit":
                (tmp_path / "root_exit_requested").write_text("normal exit requested\n")
            returncode = guard.wait(timeout=25)
        assert returncode == (1 if termination == "interrupt" else 0)
        surviving = [row for row in records if active(row)]
        (tmp_path / "survivors_at_guard_exit.json").write_text(json.dumps(surviving, indent=2))
        wait_for(lambda: [row for row in records if active(row)], lambda rows: not rows, timeout=3)
        assert sentinel.poll() is None, "Unrelated sibling was stopped by resource guard"
        evidence = {
            "guard_command": guard_command,
            "termination": termination,
            "returncode": returncode,
            "owned": records,
            "all_owned_stopped": True,
            "unrelated_sibling": identities(sentinel_dir)[0],
            "unrelated_sibling_alive": True,
            "guard_samples": [json.loads(line) for line in log_path.read_text().splitlines()],
        }
        if termination == "quick_exit":
            evidence["quick_exit_event"] = ready
            evidence["quick_exit_scope"] = (
                "Immediate root exit after verified independent-session orphan spawn"
            )
        (tmp_path / "lifecycle_evidence.json").write_text(json.dumps(evidence, indent=2))
    finally:
        if guard is not None and guard.poll() is None:
            guard.send_signal(signal.SIGINT)
            guard.wait(timeout=25)
        cleanup(records + identities(tmp_path) + identities(sentinel_dir))
        sentinel.wait(timeout=5)


def record_identity(process, role, directory, observation=False):
    identity = {
        "role": role,
        "pid": process.pid,
        "create_time": process.create_time(),
        "pgid": os.getpgid(process.pid),
        "ppid": process.ppid(),
        "cuda_visible_devices": process.environ().get("CUDA_VISIBLE_DEVICES"),
        "recorded_by_pid": os.getpid(),
        "recorded_at": time.time(),
        "identity_source": "worker_self" if process.pid == os.getpid() else "parent_verified_child",
    }
    suffix = "observation" if observation else "identity"
    pending = directory / f"{role}_{suffix}.{os.getpid()}.pending"
    pending.write_text(json.dumps(identity))
    pending.replace(directory / f"{role}_{suffix}.json")
    return identity


def worker(role, directory):
    own = psutil.Process()
    record_identity(own, role, directory, observation=role == "orphan")
    if role == "root_quick":
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", "orphan", str(directory)],
            start_new_session=True,
        )
        identity = record_identity(psutil.Process(child.pid), "orphan", directory)
        assert identity["ppid"] == own.pid and identity["pgid"] == child.pid
        ready = {
            "time": time.time(),
            "orphan_pid": child.pid,
            "orphan_alive_before_root_exit": child.poll() is None,
        }
        pending = directory / "root_quick_exit_ready.pending"
        pending.write_text(json.dumps(ready))
        pending.replace(directory / "root_quick_exit_ready.json")
        return
    if role in ("root", "child"):
        child_role = "child" if role == "root" else "leaf"
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", child_role, str(directory)],
            start_new_session=True,
        )
    while True:
        if role == "root" and (directory / "root_exit_requested").exists():
            return
        time.sleep(0.05)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("Only the real lifecycle test worker may execute this module directly")
    worker(sys.argv[2], Path(sys.argv[3]))
