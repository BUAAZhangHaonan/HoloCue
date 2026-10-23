"""Native bridge command selection; tests never start Blender, a browser or a model."""

from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess
import sys

import pytest

from scripts.tests import audit_bridge_live as bridge


def option(command, name):
    return command[command.index(name) + 1]


def test_bridge_default_render_policy_and_scoped_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "runtime_dir", lambda: tmp_path / "run")
    monkeypatch.setattr(bridge, "scene_dir", lambda scene_id: tmp_path / "scenes/reconstructed" / scene_id)
    args = bridge.argument_parser().parse_args([])
    assert (args.render_gpu, args.render_device) == (2, "CUDA")
    assert args.out == tmp_path / "run/bridge_live"
    command = bridge.native_capture_command(
        args, Path("/existing/blender"), "infusion_ward", tmp_path / "frame.json", tmp_path / "capture"
    )
    assert option(command, "--gpus") == "2"
    assert option(command, "--device") == "CUDA"
    assert option(command, "-b") == str(tmp_path / "scenes/reconstructed/infusion_ward/scene.blend")
    assert option(command, "--rss-limit-gb") == "12"
    assert option(command, "-t") == "4"
    assert option(command, "--frames") == "1"
    assert option(command, "--frame-file") == str(tmp_path / "frame.json")
    assert "--samples" not in command


@pytest.mark.parametrize("device,expected_gpus", [("CUDA", "4"), ("CPU", "")])
def test_explicit_render_device_and_gpu_reach_native_command(monkeypatch, tmp_path, device, expected_gpus):
    monkeypatch.setattr(bridge, "runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(bridge, "scene_dir", lambda scene_id: tmp_path / scene_id)
    args = bridge.argument_parser().parse_args(["--render-gpu", "4", "--render-device", device])
    command = bridge.native_capture_command(
        args, Path("/existing/blender"), "blocks", tmp_path / "frame.json", tmp_path
    )
    assert option(command, "--gpus") == expected_gpus
    assert option(command, "--device") == device


@pytest.mark.parametrize(
    "arguments", [["--render-gpu=-1"], ["--render-gpu=1.5"], ["--render-gpu=+1"], ["--render-device=OPTIX"]]
)
def test_unsupported_render_cli_rejected(arguments):
    with pytest.raises(SystemExit) as error:
        bridge.argument_parser().parse_args(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize("outside_cache", [False, True])
def test_bridge_validates_active_environment_without_historical_env_file(
    monkeypatch, tmp_path, outside_cache
):
    project = tmp_path / "project"
    task = project / ".work/current_task"
    task.mkdir(parents=True)
    blender = task / "blender"
    blender.touch()
    monkeypatch.setattr(bridge, "root", lambda: project)
    names = ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "PIP_CACHE_DIR", "PLAYWRIGHT_BROWSERS_PATH")
    for name in names:
        monkeypatch.setenv(name, str(task / name.lower()))
    monkeypatch.setenv("BLENDER_BIN", str(blender))
    assert not (project / ".work/task_env.sh").exists()
    output = project / "runs/simulation/current"
    if outside_cache:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "outside"))
        with pytest.raises(ValueError, match="XDG_CACHE_HOME must resolve inside"):
            bridge.check_environment(output)
    else:
        settings, executable = bridge.check_environment(output)
        assert executable == blender
        assert settings == {name: str(task / name.lower()) for name in names}


@pytest.mark.parametrize("external_launch", [False, True])
def test_native_command_resolves_entries_when_cwd_changes(monkeypatch, tmp_path, external_launch):
    """Execute the generated argv; the renderer probe changes cwd before loading Python."""
    project = tmp_path / "project"
    external = tmp_path / "external_launch"
    renderer_cwd = tmp_path / "renderer_changed_cwd"
    capture = project / "capture"
    for directory in (
        project / "scripts/guard",
        project / "scripts/capture",
        external,
        renderer_cwd,
        capture,
    ):
        directory.mkdir(parents=True)
    guard = project / "scripts/guard/resource_guard.py"
    guard.write_text(
        "import subprocess,sys\nraise SystemExit(subprocess.call(sys.argv[sys.argv.index('--')+1:]))\n"
    )
    bridge_script = project / "scripts/capture/blender_simulation_bridge.py"
    bridge_script.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "Path(os.environ['BRIDGE_PATH_PROBE']).write_text(json.dumps({'script':str(Path(__file__).resolve()),'cwd':str(Path.cwd())}))\n"
    )
    renderer = project / "renderer_probe"
    renderer.write_text(
        f"#!{sys.executable}\n"
        "import os,runpy,sys\n"
        "os.chdir(os.environ['BRIDGE_PROBE_RENDERER_CWD'])\n"
        "runpy.run_path(sys.argv[sys.argv.index('--python')+1],run_name='__main__')\n"
    )
    renderer.chmod(0o755)
    monkeypatch.setattr(bridge, "root", lambda: project)
    monkeypatch.setattr(bridge, "scene_dir", lambda scene_id: project / "scenes" / scene_id)
    args = bridge.argument_parser().parse_args(["--render-device", "CPU"])
    command = bridge.native_capture_command(args, renderer, "blocks", project / "frame.json", capture)
    receipt = capture / "resolved_paths.json"
    environment = dict(
        os.environ, BRIDGE_PATH_PROBE=str(receipt), BRIDGE_PROBE_RENDERER_CWD=str(renderer_cwd)
    )
    result = subprocess.run(
        command,
        cwd=external if external_launch else project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(receipt.read_text()) == {"script": str(bridge_script), "cwd": str(renderer_cwd)}
    assert Path(command[1]).is_absolute()
    assert Path(option(command, "--python")).is_absolute()


def test_exporter_owned_process_uses_project_absolute_entry(monkeypatch, tmp_path):
    project = tmp_path / "project"
    external = tmp_path / "external_launch"
    output = project / "capture"
    for directory in (project / "scripts/scenes", external, output):
        directory.mkdir(parents=True)
    exporter = project / "scripts/scenes/export_live_frames.py"
    exporter.write_text(
        "import json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['BRIDGE_PATH_PROBE']).write_text(json.dumps({'script':sys.argv[0],'cwd':str(Path.cwd()),'arguments':sys.argv[1:]}))\n"
    )
    receipt = output / "exporter_probe.json"
    monkeypatch.setattr(bridge, "root", lambda: project)
    monkeypatch.setenv("BRIDGE_PATH_PROBE", str(receipt))
    monkeypatch.chdir(external)
    audit = SimpleNamespace(
        sid="probe-session",
        args=SimpleNamespace(api="http://unused.invalid"),
        view_path=project / "view.json",
        out=output,
    )
    bridge.Audit.start_exporter(audit)
    try:
        assert audit.exporter.process.wait(timeout=20) == 0
    finally:
        audit.exporter.close()
    observed = json.loads(receipt.read_text())
    assert observed["script"] == str(exporter)
    assert observed["cwd"] == str(project)
    assert observed["arguments"] == [
        "--session",
        "probe-session",
        "--api",
        "http://unused.invalid",
        "--view-state",
        str(project / "view.json"),
        "--seconds",
        "21600",
        "--hz",
        "10",
    ]
