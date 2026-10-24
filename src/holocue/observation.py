"""Version-bound camera observations from the real Viser renderer."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
import time

import numpy as np
from PIL import Image

from .bridge import atomic_json


def camera_spec(camera, max_edge=1024):
    """Preserve the actual projection; the pixel shape is recorded separately."""
    timestamp = getattr(camera, "update_timestamp", None)
    aspect = float(camera.aspect)
    fov = float(camera.fov)
    near, far = float(camera.near), float(camera.far)
    if not np.isfinite([aspect, fov, near, far]).all():
        raise ValueError("Camera projection contains non-finite values")
    if aspect <= 0 or not 0 < fov < np.pi or not 0 < near < far:
        raise ValueError("Camera projection is not ready")
    if not 64 <= max_edge <= 1024:
        raise ValueError("Camera observation max edge must be between 64 and 1024")
    width, height = (
        (max_edge, max(1, round(max_edge / aspect)))
        if aspect >= 1
        else (max(1, round(max_edge * aspect)), max_edge)
    )
    position = [float(x) for x in camera.position]
    wxyz = [float(x) for x in camera.wxyz]
    if not np.isfinite(position + wxyz).all() or not np.isclose(np.linalg.norm(wxyz), 1):
        raise ValueError("Camera pose is invalid")
    if getattr(camera, "update_timestamp", None) != timestamp:
        raise RuntimeError("Camera changed while reading its projection")
    tangent = np.tan(fov / 2)
    return {
        "width": width,
        "height": height,
        "position_m": position,
        "wxyz": wxyz,
        "fov_y_rad": fov,
        "near_m": near,
        "far_m": far,
        "projection_aspect": aspect,
        "intrinsics_px": [
            [width / (2 * tangent * aspect), 0, width / 2],
            [0, height / (2 * tangent), height / 2],
            [0, 0, 1],
        ],
        "pose_convention": "Viser/OpenCV: camera +x right, +y down, +z forward",
    }


def capture_camera(
    client, directory: Path, identity: dict, expected_nodes, *, timeout=20.0, frozen_camera=None
):
    """Request lossless scene RGB, never a screenshot or a synthetic fallback."""
    camera = camera_spec(client.camera) if frozen_camera is None else frozen_camera
    if not expected_nodes or any(not name.startswith("/workspace/") for name in expected_nodes):
        raise ValueError("Camera capture requires the current scene's visible asset paths")
    if not 0 < timeout <= 120:
        raise ValueError("Camera capture requires a finite timeout of at most 120 seconds")
    request_id = identity["request_id"]
    if not request_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid observation request ID")
    started_at, started = time.time(), time.perf_counter()
    image = np.asarray(
        client.get_render(
            camera["height"],
            camera["width"],
            wxyz=tuple(camera["wxyz"]),
            position=tuple(camera["position_m"]),
            fov=camera["fov_y_rad"],
            near=camera["near_m"],
            far=camera["far_m"],
            projection_aspect=camera["projection_aspect"],
            expected_node_names=tuple(expected_nodes),
            transport_format="png",
            transparent_background=False,
            timeout=timeout,
        )
    )
    render_elapsed = time.perf_counter() - started
    if image.dtype != np.uint8 or image.shape != (camera["height"], camera["width"], 4):
        raise ValueError("Viser did not return the requested lossless RGBA camera frame")
    if not np.all(image[:, :, 3] == 255):
        raise ValueError("Camera frame is unexpectedly transparent")
    # Opaque alpha is verified; this drops a constant channel without changing RGB.
    output = io.BytesIO()
    Image.fromarray(image[:, :, :3]).save(output, format="PNG")
    png = output.getvalue()
    if len(png) > 1_500_000:
        raise ValueError("Camera PNG exceeds the existing model-input byte limit")
    directory.mkdir(parents=True, exist_ok=True)
    image_path = directory / f"{request_id}.png"
    image_path.write_bytes(png)
    metadata = {
        **identity,
        "protocol": "runtime_camera_v1",
        "source": "viser.ClientHandle.get_render",
        "color_mode": "RGB",
        "image_mime": "image/png",
        "image_file": image_path.name,
        "image_sha256": hashlib.sha256(png).hexdigest(),
        "image_bytes": len(png),
        "camera": camera,
        "expected_asset_nodes": list(expected_nodes),
        "started_at": started_at,
        "finished_at": time.time(),
        "render_roundtrip_s": render_elapsed,
        "capture_and_save_s": time.perf_counter() - started,
    }
    atomic_json(directory / f"{request_id}.json", metadata)
    return metadata, base64.b64encode(png).decode("ascii")
