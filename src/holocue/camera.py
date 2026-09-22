"""Viewport-aware task framing and explicit inspection views."""

from __future__ import annotations

import itertools
import numpy as np

from .models import Pose, SceneObject
from .spatial import rotation, transform_points


def corners(bounds: np.ndarray) -> np.ndarray:
    return np.asarray(list(itertools.product(*zip(bounds[0], bounds[1]))), dtype=float)


def basis(position, look_at, up=(0.0, 0.0, 1.0)):
    f = np.asarray(look_at, float) - np.asarray(position, float)
    if np.linalg.norm(f) < 1e-8:
        raise ValueError("camera position and target coincide")
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    if np.linalg.norm(r) < 1e-6:
        raise ValueError("camera up direction is parallel to view direction")
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def fit(points: np.ndarray, direction, fov_y_deg=42.0, aspect=1.6, margin=0.14, up=(0.0, 0.0, 1.0)):
    if len(points) == 0 or aspect <= 0:
        raise ValueError("camera framing requires points and a positive aspect ratio")
    center = (points.min(axis=0) + points.max(axis=0)) / 2
    direction = np.asarray(direction, float)
    if np.linalg.norm(direction) < 1e-8:
        raise ValueError("camera direction must be nonzero")
    direction /= np.linalg.norm(direction)
    r, u, f = basis(center + direction, center, up)
    relative = points - center
    x, y, z = relative @ r, relative @ u, relative @ f
    ty = np.tan(np.deg2rad(fov_y_deg) / 2) * (1 - margin)
    distance = max(float(np.max(np.abs(y) / ty - z)), float(np.max(np.abs(x) / (ty * aspect) - z)), 0.1)
    return tuple(center + direction * distance), tuple(center)


def workspace_points(spec, task_points):
    points = np.asarray(task_points, float)
    if spec.render_hints.workspace_bounds_m is not None:
        bounds = np.asarray(spec.render_hints.workspace_bounds_m, float)
        if np.any(bounds[1] <= bounds[0]):
            raise ValueError("workspace bounds must have positive extents")
        points = np.concatenate([points, corners(bounds)], axis=0)
    return points


def project(points, position, look_at, fov_y_deg=42.0, aspect=1.6, up=(0.0, 0.0, 1.0)):
    r, u, f = basis(position, look_at, up)
    relative = np.asarray(points) - position
    depth = relative @ f
    if np.any(depth <= 0):
        raise ValueError("projected points lie behind the camera")
    t = np.tan(np.deg2rad(fov_y_deg) / 2)
    return np.column_stack([relative @ r / (depth * t * aspect), relative @ u / (depth * t)]), depth


def focus_point(obj: SceneObject, pose: Pose, inspection: bool):
    """The existing selected-target focus anchor, shared with cue framing."""
    local = obj.interaction.inspect_point_local_m if inspection else obj.interaction.cue_offset_local_m
    if inspection:
        local = (
            np.asarray(local)
            + np.asarray(obj.interaction.inspect_normal_local) * obj.interaction.inspect_cue_clearance_m
        )
    return transform_points(pose, np.asarray([local]))[0]


def retreat_to_fit(points, position, look_at, fov_y_deg, aspect, up):
    """Fit an envelope by retreating only; preserve any already uncut view."""
    points = np.asarray(points, float)
    if len(points) == 0:
        return position
    if aspect <= 0:
        raise ValueError("camera framing requires a positive aspect ratio")
    right, vertical, forward = basis(position, look_at, up)
    relative = points - np.asarray(position)
    depth = relative @ forward
    tangent = np.tan(np.deg2rad(fov_y_deg) / 2)
    retreat = max(
        0.0,
        float(np.max(np.abs(relative @ right) / (tangent * aspect) - depth)),
        float(np.max(np.abs(relative @ vertical) / tangent - depth)),
    )
    if retreat == 0.0:
        return position
    return tuple(np.asarray(position) - forward * retreat)


def detail_view(
    obj: SceneObject,
    pose: Pose,
    bounds,
    default_direction,
    action=None,
    fov_y_deg=42.0,
    aspect=1.6,
    margin=0.14,
):
    if action == "inspect_back":
        return inspect_view(obj, pose, fov_y_deg, aspect, margin)
    direction = np.asarray(default_direction, float)
    if obj.interaction.detail_direction_local is not None:
        direction = rotation(pose).apply(obj.interaction.detail_direction_local)
    if action == "rotate":
        direction = rotation(pose).apply(obj.interaction.rotation_axis_local)
    direction = direction / np.linalg.norm(direction)
    up = (0.0, 1.0, 0.0) if abs(direction[2]) > 0.95 else (0.0, 0.0, 1.0)
    points = transform_points(pose, corners(np.asarray(bounds)))
    position, look = fit(points, direction, fov_y_deg, aspect, margin, up)
    return position, look, up


def inspection_region(obj: SceneObject, pose: Pose):
    point = transform_points(pose, np.asarray([obj.interaction.inspect_point_local_m]))[0]
    normal = rotation(pose).apply(obj.interaction.inspect_normal_local)
    up = np.array([0.0, 0.0, 1.0])
    if abs(normal @ up) > 0.95:
        up = np.array([0.0, 1.0, 0.0])
    right, vertical, _ = basis(point + normal, point, up)
    axes = rotation(pose).as_matrix()
    if obj.interaction.inspect_extent_m is None:
        width = float(np.abs(right @ axes) @ np.asarray(obj.size_m))
        height = float(np.abs(vertical @ axes) @ np.asarray(obj.size_m))
    else:
        width, height = obj.interaction.inspect_extent_m
    return point, normal, up, right, vertical, width, height


def inspection_points(obj: SceneObject, pose: Pose):
    point, _, _, right, vertical, width, height = inspection_region(obj, pose)
    return point + np.asarray(
        [
            -right * width / 2 - vertical * height / 2,
            right * width / 2 - vertical * height / 2,
            right * width / 2 + vertical * height / 2,
            -right * width / 2 + vertical * height / 2,
        ]
    )


def inspect_view(obj: SceneObject, pose: Pose, fov_y_deg=42.0, aspect=1.6, margin=0.16):
    point, normal, up, _, _, width, height = inspection_region(obj, pose)
    tangent = np.tan(np.deg2rad(fov_y_deg) / 2) * (1 - margin)
    distance = max(height / (2 * tangent), width / (2 * tangent * aspect), 0.05)
    return tuple(point + normal * distance), tuple(point), tuple(up)
