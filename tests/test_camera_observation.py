import base64
import io
import json
import threading
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from holocue.observation import camera_spec, capture_camera
from holocue.viewer import Operator
from holocue.versioning import VersionGate


def camera():
    return SimpleNamespace(
        aspect=1.276,
        fov=0.733,
        near=0.002,
        far=100.0,
        update_timestamp=0.0,
        position=np.array([1.0, -2.0, 3.0]),
        wxyz=np.array([1.0, 0, 0, 0]),
    )


def test_camera_uses_exact_projection_and_lossless_pixels(tmp_path):
    cam = camera()
    calls = []

    def render(height, width, **kwargs):
        calls.append(kwargs)
        image = np.zeros((height, width, 4), dtype=np.uint8)
        image[:] = [19, 71, 203, 255]
        return image

    client = SimpleNamespace(camera=cam, get_render=render)
    identity = dict(request_id="unit_1", session_id="s1", revision=4, epoch=2)
    metadata, encoded = capture_camera(client, tmp_path, identity, ["/workspace/objects/A/asset"])
    decoded = np.asarray(Image.open(io.BytesIO(base64.b64decode(encoded))))
    assert tuple(decoded[0, 0]) == (19, 71, 203)
    assert decoded.shape[2] == 3
    assert calls[0]["near"] == 0.002 and calls[0]["far"] == 100
    assert calls[0]["projection_aspect"] == 1.276
    assert calls[0]["expected_node_names"] == ("/workspace/objects/A/asset",)
    assert calls[0]["transparent_background"] is False
    assert metadata["revision"] == 4
    assert (tmp_path / "unit_1.png").read_bytes() == base64.b64decode(encoded)
    assert json.loads((tmp_path / "unit_1.json").read_text())["image_sha256"] == metadata["image_sha256"]


def test_observation_rejects_transparent_or_wrong_frame(tmp_path):
    client = SimpleNamespace(camera=camera(), get_render=lambda h, w, **k: np.zeros((h, w, 4), np.uint8))
    with pytest.raises(ValueError, match="transparent"):
        capture_camera(client, tmp_path, {"request_id": "bad"}, ["/workspace/objects/A/asset"])
    assert list(tmp_path.iterdir()) == []


def test_observation_timeout_is_visible_without_fallback(tmp_path):
    def render(*args, **kwargs):
        raise TimeoutError("asset not ready")

    client = SimpleNamespace(camera=camera(), get_render=render)
    with pytest.raises(TimeoutError, match="asset not ready"):
        capture_camera(client, tmp_path, {"request_id": "bad"}, ["/workspace/objects/A/asset"], timeout=1)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("field,value", [("near", 0), ("aspect", 0), ("fov", np.nan), ("far", 0.001)])
def test_invalid_camera_projection_is_rejected(field, value):
    cam = camera()
    setattr(cam, field, value)
    with pytest.raises(ValueError):
        camera_spec(cam)


def operator(tmp_path):
    op = Operator.__new__(Operator)
    op.lock = threading.RLock()
    op.sid, op.generation = "s1", 3
    op.loaded, op.capture_active = True, False
    op.revision, op.epoch = 4, 2
    op.client = SimpleNamespace(client_id=7, camera=camera())
    op.camera_aspect = op.client.camera.aspect
    op.log_dir = tmp_path
    op.focus = SimpleNamespace(value=1.0)
    op.brightness = SimpleNamespace(value=1.0)
    op.enabled = SimpleNamespace(value=True)
    op.packet = SimpleNamespace(execution="paused")
    op.renderer = SimpleNamespace(
        tick=lambda *args: None,
        spec=SimpleNamespace(scene_id="blocks", scene_set="reconstructed"),
        clock=SimpleNamespace(elapsed={"task1": 0.7}),
        view_mode="workspace",
        selected_id="A",
        current_poses={},
        visible_asset_paths=lambda: ("/workspace/objects/A/asset",),
    )
    op.record = lambda *args: None
    op.request = lambda *a, **k: {"state": {"revision": 4, "epoch": 2}}
    op.accept = lambda *args: None
    return op


def test_camera_wait_releases_operator_lock_and_preserves_clock(tmp_path, monkeypatch):
    op = operator(tmp_path)
    results = []

    def capture(*args, **kwargs):
        def callback():
            acquired = op.lock.acquire(timeout=0.3)
            results.append(acquired)
            if acquired:
                op.lock.release()

        thread = threading.Thread(target=callback, daemon=True)
        thread.start()
        thread.join(timeout=0.5)
        assert op.capture_active
        return {"image_sha256": "unit"}, "unit"

    monkeypatch.setattr("holocue.viewer.capture_camera", capture)
    op.capture_observation("unit", "model_input")
    assert results == [True]
    assert not op.capture_active
    assert op.renderer.clock.elapsed == {"task1": 0.7}


def test_frozen_camera_does_not_follow_a_later_browser_resize(tmp_path):
    cam = camera()
    frozen = camera_spec(cam)
    cam.aspect = 3.0
    received = []

    def render(h, w, **kwargs):
        received.append(kwargs)
        return np.full((h, w, 4), 255, dtype=np.uint8)

    capture_camera(
        SimpleNamespace(camera=cam, get_render=render),
        tmp_path,
        {"request_id": "frozen"},
        ["/workspace/objects/A/asset"],
        frozen_camera=frozen,
    )
    assert received[0]["projection_aspect"] == 1.276


def test_camera_motion_during_prepare_is_rejected(tmp_path, monkeypatch):
    op = operator(tmp_path)

    def tick(*args):
        op.client.camera.update_timestamp = 1.0

    op.renderer.tick = tick
    with pytest.raises(RuntimeError, match="Camera moved"):
        op.capture_observation("unit", "model_input")
    assert not op.capture_active


def test_scene_change_during_observation_is_rejected(tmp_path, monkeypatch):
    op = operator(tmp_path)

    def capture(*args, **kwargs):
        op.generation += 1
        return {}, "unit"

    monkeypatch.setattr("holocue.viewer.capture_camera", capture)
    with pytest.raises(RuntimeError, match="changed during"):
        op.capture_observation("unit", "model_input")
    assert not op.capture_active


def test_camera_submit_sends_captured_revision_and_image(tmp_path):
    op = operator(tmp_path)
    op.observation_mode = "camera_rgb"
    op.gate = VersionGate()
    calls = []
    op.capture_observation = lambda *a: ({"revision": 4}, {"image_sha256": "unit"}, "real_png_bytes")

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"id": "job1", "epoch": 3}

    op.request = request
    op.submit("inspect A")
    body = calls[0][2]["json"]
    assert body["image_base64"] == "real_png_bytes"
    assert body["image_mime"] == "image/png"
    assert body["expected_revision"] == 4
    assert len(calls) == 1


def test_camera_failure_does_not_submit_a_text_only_request(tmp_path):
    op = operator(tmp_path)
    op.observation_mode = "camera_rgb"
    calls = []

    def fail(*args):
        raise TimeoutError("camera unavailable")

    op.capture_observation = fail
    op.request = lambda *a, **k: calls.append(a)
    with pytest.raises(TimeoutError):
        op.submit("inspect A")
    assert not calls
