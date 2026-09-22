"""Numerical/image regressions only; these are not live browser acceptance."""

import copy

import numpy as np
import pytest
from PIL import Image
from scipy.spatial.transform import Rotation

from holocue.camera import basis
from scripts.tests.audit_viewer_live import canvas_pixels, client_view_errors, settled_canvas_pixels


def test_camera_readback_accounts_for_root_pose_and_rejects_stale_inverse():
    # A translated, rotated Viser root exercises more than the usual Z/Y-up swap.
    position = np.array([1.2, -2.1, 1.8])
    target = np.array([0.2, 0.3, 0.9])
    up = np.array([0.0, 0.0, 1.0])
    right, vertical, forward = basis(position, target, up)
    root_rotation = Rotation.from_euler("xyz", [25, -15, 70], degrees=True)
    root_position = np.array([0.4, -0.2, 0.1])
    orientation = root_rotation * Rotation.from_matrix(np.column_stack((right, vertical, -forward)))
    world = np.eye(4)
    world[:3, :3] = orientation.as_matrix()
    world[:3, 3] = root_rotation.apply(position) + root_position
    client = {
        "ready": True,
        "root": {
            "wxyz": root_rotation.as_quat(scalar_first=True).tolist(),
            "position": root_position.tolist(),
        },
        "camera": {
            "position": world[:3, 3].tolist(),
            "target": (root_rotation.apply(target) + root_position).tolist(),
            "up": root_rotation.apply(up).tolist(),
            "quaternion": orientation.as_quat().tolist(),
            "matrix_world": world.T.ravel().tolist(),
            "matrix_world_inverse": np.linalg.inv(world).T.ravel().tolist(),
            "fov_rad": np.deg2rad(42),
            "aspect": 1.6,
        },
        "canvas": {
            "box": {"width": 800, "height": 500},
            "drawing_buffer": [700, 437],
            "width": 700,
            "height": 437,
            "default_framebuffer": True,
        },
    }
    view = {
        "position_m": position.tolist(),
        "look_at_m": target.tolist(),
        "up_direction": up.tolist(),
        "fov_rad": np.deg2rad(42),
        "aspect": 1.6,
    }
    measured = client_view_errors(client, view)
    assert measured["passed"]
    assert max(measured["errors"].values()) < 1e-12
    stale = copy.deepcopy(client)
    stale["camera"]["matrix_world_inverse"] = np.eye(4).T.ravel().tolist()
    measured = client_view_errors(stale, view)
    assert not measured["passed"]
    assert measured["errors"]["matrix_world_inverse"] > 0.1
    assert measured["errors"]["position_m"] < 1e-12


def test_canvas_pixels_respects_css_scale_and_excludes_sidebar(tmp_path):
    # Actual image files at 2 screenshot pixels per CSS pixel, with a sidebar.
    pixels = np.zeros((120, 200, 4), dtype=np.uint8)
    pixels[:] = [20, 40, 60, 255]
    base = tmp_path / "base.png"
    Image.fromarray(pixels).save(base)
    box = {"x": 10, "y": 5, "width": 60, "height": 40}
    viewport = {"width": 100, "height": 60}
    first = canvas_pixels(base, box, viewport)
    assert first["shape"] == [80, 120, 4]
    assert first["crop"] == [20, 10, 140, 90]
    pixels[:, 150:] = [255, 0, 0, 255]
    sidebar = tmp_path / "sidebar.png"
    Image.fromarray(pixels).save(sidebar)
    assert canvas_pixels(sidebar, box, viewport)["sha256"] == first["sha256"]
    pixels[20, 30] = [0, 255, 0, 255]
    changed = tmp_path / "changed.png"
    Image.fromarray(pixels).save(changed)
    assert canvas_pixels(changed, box, viewport)["sha256"] != first["sha256"]
    clipped = tmp_path / "clipped.png"
    Image.fromarray(pixels[10:90, 20:140]).save(clipped)
    assert (
        canvas_pixels(clipped, box, viewport, clip=box)["sha256"]
        == canvas_pixels(changed, box, viewport)["sha256"]
    )
    fractional = {"x": 10.1, "y": 5.2, "width": 60.3, "height": 40.2}
    readback = canvas_pixels(clipped, fractional, viewport, clip=fractional)
    assert readback["crop"] == [0, 0, 120, 80]
    assert readback["sha256"] == canvas_pixels(clipped, box, viewport, clip=box)["sha256"]


def test_resize_transition_is_not_cropped_using_stale_bounds(tmp_path):
    # Real PNG and the dimensions observed in drone_bench's failed live shot.
    path = tmp_path / "narrow.png"
    Image.new("RGBA", (1100, 800), (20, 40, 60, 255)).save(path)
    before = {
        "ready": True,
        "root": {},
        "camera": {"aspect": 1.276},
        "canvas": {
            "width": 1276,
            "height": 1000,
            "box": {"x": 0, "y": 0, "width": 1276, "height": 1000},
            "viewport": {"width": 1100, "height": 800},
        },
    }
    after = copy.deepcopy(before)
    after["camera"]["aspect"] = 0.97
    after["canvas"].update(width=776, height=800, box={"x": 0, "y": 0, "width": 776, "height": 800})
    assert settled_canvas_pixels(path, before, after) is None
    assert settled_canvas_pixels(path, after, after)["shape"] == [800, 776, 4]
    # A stable but clipped canvas is still an error, never accepted as settled.
    with pytest.raises(AssertionError, match="entire observed canvas"):
        settled_canvas_pixels(path, before, before)
