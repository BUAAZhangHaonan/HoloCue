"""Native bridge command selection; tests never start Blender, a browser or a model."""

from pathlib import Path

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
