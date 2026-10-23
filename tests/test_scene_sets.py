"""Scene selection and isolation checks; no model requests or service processes."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from holocue.api import create_app
from holocue.bridge import frame
from holocue.config import list_scenes, load_scene, root, runtime_dir, scene_dir, scene_fingerprint, scene_set
from holocue.projection import packet
from holocue.response import local_cue_pool
from holocue.service import Service
from holocue.spatial import ActionClock
from holocue.store import Store


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_complete_scene_set_has_explicit_resource_paths(selected):
    rows = list_scenes(selected)
    assert len(rows) == 12
    for row in rows:
        spec = load_scene(row["scene_id"], selected)
        directory = scene_dir(spec.scene_id, selected)
        assert row["scene_set"] == spec.scene_set == selected
        assert (directory / "scene.json").is_file()
        assert (directory / "scene.blend").stat().st_size > 1000
        assert (directory / "meshes").is_dir()
        for item in [*spec.objects, *spec.environment]:
            path = (root() / item.asset).resolve()
            assert path.is_relative_to(directory / "meshes")
            assert path.is_file()


def test_scene_set_selection_and_runtime_are_explicit(monkeypatch):
    monkeypatch.delenv("HOLOCUE_SCENE_SET", raising=False)
    monkeypatch.delenv("RUN_DIR", raising=False)
    assert scene_set() == "reconstructed"
    assert runtime_dir() == root() / "runs/simulation/reconstructed"
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "legacy")
    assert load_scene("blocks").scene_set == "legacy"
    assert runtime_dir() == root() / "runs/simulation/legacy"
    assert scene_dir("blocks", "reconstructed") == root() / "scenes/reconstructed/blocks"
    monkeypatch.setenv("RUN_DIR", "runs/simulation/selected_run")
    assert runtime_dir() == root() / "runs/simulation/selected_run"
    monkeypatch.setenv("RUN_DIR", str(root().parent / "outside_project"))
    with pytest.raises(ValueError, match="inside the project"):
        runtime_dir()
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "other")
    with pytest.raises(ValueError, match="Unknown scene set"):
        scene_set()
    with pytest.raises(ValueError, match="Invalid scene ID"):
        scene_dir("../blocks", "legacy")


@pytest.mark.parametrize("sid", [item["scene_id"] for item in list_scenes("reconstructed")])
def test_paired_scene_sets_preserve_interaction_contract(sid):
    old, new = load_scene(sid, "legacy"), load_scene(sid, "reconstructed")
    assert [o.object_id for o in old.objects] == [o.object_id for o in new.objects]
    for before, after in zip(old.objects, new.objects, strict=True):
        for field in ("pose", "size_m", "capabilities", "anchors", "frames", "interaction"):
            assert getattr(before, field) == getattr(after, field), (sid, before.object_id, field)
    assert old.task_contract.ordered_steps == new.task_contract.ordered_steps
    assert old.task_contract.persistent_targets == new.task_contract.persistent_targets
    assert old.task_contract.interrupt_target == new.task_contract.interrupt_target


def test_same_scene_id_uses_selected_mesh_and_separate_cache():
    old, new = load_scene("blocks", "legacy"), load_scene("blocks", "reconstructed")
    assert scene_fingerprint(old) != scene_fingerprint(new)
    old_pool = local_cue_pool("blocks", "B", "ghost_motion", 128, selected_set="legacy")
    new_pool = local_cue_pool("blocks", "B", "ghost_motion", 128, selected_set="reconstructed")
    assert not np.array_equal(old_pool, new_pool)
    assert np.array_equal(old_pool, local_cue_pool("blocks", "B", "ghost_motion", 128, selected_set="legacy"))


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_api_state_display_and_frame_reject_cross_set(monkeypatch, tmp_path, selected):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", selected)
    service = Service(Store(tmp_path / "state.sqlite"), SimpleNamespace(mode="live"))
    with TestClient(create_app(service)) as client:
        assert client.get("/health").json()["scene_set"] == selected
        state = client.post("/api/v1/sessions", json={"scene_id": "blocks"}).json()
        assert state["scene_set"] == selected
        route = f"/api/v1/sessions/{state['session_id']}/snapshot"
        snapshot = client.get(route)
        assert snapshot.status_code == 200
        assert snapshot.json()["display"]["scene_set"] == selected
        opposite = "legacy" if selected == "reconstructed" else "reconstructed"
        spec = load_scene("blocks", selected)
        display = packet(service.store.get(state["session_id"]), spec, service.policy)
        with pytest.raises(ValueError, match="frame scene mismatch"):
            frame(load_scene("blocks", opposite), display, ActionClock(), 0, [0, -1, 1], [0, 0, 0], 1)
        monkeypatch.setenv("HOLOCUE_SCENE_SET", opposite)
        mismatch = client.get(route)
        assert mismatch.status_code == 422
        assert "another scene set" in mismatch.json()["detail"]


def test_explicit_legacy_build_uses_original_recipes(monkeypatch, tmp_path):
    from scripts.scenes import build_simulation_assets as builder

    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    spec = load_scene("blocks", "legacy")
    spec.objects = spec.objects[:1]
    spec.environment = spec.environment[:1]
    fake_scene = SimpleNamespace(geometry={"part": SimpleNamespace(faces=[(0, 1, 2)])})
    calls = []

    class Assembly:
        scene = fake_scene

        def save(self, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test legacy output")

    def original_object(obj):
        calls.append(("object", obj.object_id))
        return Assembly()

    def original_environment(scene):
        calls.append(("environment", scene.scene_id))
        return Assembly()

    def reconstructed(_):
        raise AssertionError("legacy build reached reconstructed builder")

    monkeypatch.setitem(
        sys.modules, "scripts.scenes.rebuild_blocks_assets", SimpleNamespace(build=reconstructed)
    )
    monkeypatch.setattr(builder, "root", lambda: tmp_path)
    monkeypatch.setattr(builder, "list_scenes", lambda: [{"scene_id": "blocks"}])
    monkeypatch.setattr(builder, "load_scene", lambda sid: spec)
    monkeypatch.setattr(builder, "make_object", original_object)
    monkeypatch.setattr(builder, "make_environment", original_environment)
    monkeypatch.setattr(builder, "load_asset", lambda *args: fake_scene)
    monkeypatch.setattr(builder, "inputs", lambda scene: {})
    monkeypatch.setattr(
        sys, "argv", ["builder", "--scene-set", "legacy", "--scenes", "blocks", "--report", "report.json"]
    )
    builder.main()
    assert calls == [("object", spec.objects[0].object_id), ("environment", "blocks")]
    provenance = json.loads((tmp_path / "report.provenance.json").read_text())
    assert provenance["scene_set"] == "legacy" and provenance["complete"]


def test_serialized_schemas_include_scene_set():
    for filename in ("scene.schema.json", "display_packet.schema.json"):
        schema = json.loads((root() / "schemas" / filename).read_text())
        assert schema["properties"]["scene_set"]["enum"] == ["legacy", "reconstructed"]


@pytest.mark.parametrize(
    "options", [["--scene-set", "legacy", "--port", "8751"], ["--port", "8751", "--scene-set=legacy"]]
)
def test_service_launcher_preserves_caller_paths_and_cli_selection(tmp_path, options):
    recorder = tmp_path / "python-recorder"
    recorder.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['RECORDER_OUTPUT']).write_text(json.dumps({'argv': sys.argv[1:], 'env': dict(os.environ)}))\n"
    )
    recorder.chmod(0o755)
    output = tmp_path / "launch.json"
    supplied = {
        "APP_PYTHON": str(recorder),
        "RECORDER_OUTPUT": str(output),
        "RUN_DIR": str(tmp_path / "run"),
        "TMPDIR": str(tmp_path / "tmp"),
        "TMP": str(tmp_path / "tmp"),
        "TEMP": str(tmp_path / "tmp"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PIP_CACHE_DIR": str(tmp_path / "cache/pip"),
        "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "browsers"),
        "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOLOCUE_SCENE_SET": "reconstructed",
    }
    subprocess.run(
        ["bash", str(root() / "scripts/run_simulation.sh"), "api", *options],
        env={**os.environ, **supplied},
        check=True,
    )
    captured = json.loads(output.read_text())
    assert captured["env"]["HOLOCUE_SCENE_SET"] == "legacy"
    for name, value in supplied.items():
        if name != "HOLOCUE_SCENE_SET":
            assert captured["env"][name] == value
    assert captured["argv"][-4:] == ["--scene-set", "legacy", "--port", "8751"]
