"""Analytical Gaussian envelope preview shared by interactive and offline renderers.

The width controls are simulation parameters. They carry no measured SLM calibration.
The analytical width/peak relationship is evaluated before a declared display scale.
"""

from __future__ import annotations

from functools import lru_cache
import json
import numpy as np
import trimesh
from pydantic import Field
from scipy.spatial.transform import Rotation

from .assets import load_asset, resource
from .config import root, load_scene, scene_fingerprint
from .models import Strict, DisplayCue, SceneSpec, Pose
from .spatial import transform_points


class ResponseProfile(Strict):
    profile_id: str
    provenance: str
    wavelength_m: float = Field(gt=0)
    relative_sigma_to_waist_m: float = Field(gt=0)
    visual_magnification: float = Field(gt=0)
    reference_sigma: float = Field(gt=0)
    reference_count: int = Field(gt=0)
    per_splat_optical_depth: float = Field(gt=0)


@lru_cache(maxsize=1)
def profile() -> ResponseProfile:
    return ResponseProfile.model_validate(json.loads((root() / "configs/preview_response.json").read_text()))


def envelope(sigma: float, defocus_m: np.ndarray | float, calibration: ResponseProfile):
    if sigma <= 0:
        raise ValueError("Gaussian width must be positive")
    waist = sigma * calibration.relative_sigma_to_waist_m
    rayleigh = np.pi * waist**2 / calibration.wavelength_m
    width = waist * np.sqrt(1 + (np.asarray(defocus_m) / rayleigh) ** 2)
    reference_waist = calibration.reference_sigma * calibration.relative_sigma_to_waist_m
    peak = reference_waist**2 / width**2
    return width, peak, float(rayleigh)


def basis_from_normal(normal):
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    helper = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = np.cross(helper, n)
    x /= np.linalg.norm(x)
    y = np.cross(n, x)
    return np.column_stack([x, y, n])


def local_cue_pool(scene_id: str, target_id: str, kind: str, count: int = 8192) -> np.ndarray:
    fingerprint = scene_fingerprint(load_scene(scene_id))
    return _local_cue_pool(scene_id, target_id, kind, fingerprint, count)


@lru_cache(maxsize=256)
def _local_cue_pool(scene_id: str, target_id: str, kind: str, fingerprint: str, count: int) -> np.ndarray:
    scene = load_scene(scene_id)
    obj = next(o for o in scene.objects if o.object_id == target_id)
    if kind == "ghost_motion":
        mesh = load_asset(str(resource(root(), obj.asset)), scene.asset_axes).to_geometry()
        points, _ = trimesh.sample.sample_surface(mesh, count, seed=917)
        return points.astype(np.float32)
    rng = np.random.default_rng(917)
    u = rng.random(count)
    radius = max(min(obj.size_m) * 0.72, 0.014)
    if kind == "ring_arrow":
        angle = (0.15 + 1.65 * u) * np.pi
        points = np.column_stack([radius * np.cos(angle), radius * np.sin(angle), np.zeros(count)])
        head = u > 0.88
        a = 1.80 * np.pi
        tip = np.array([np.cos(a), np.sin(a)]) * radius
        back = tip + np.array([np.sin(a), -np.cos(a)]) * radius * 0.42
        side = np.array([np.cos(a), np.sin(a)]) * radius * 0.22
        v = rng.random(head.sum())
        w = rng.random(head.sum())
        points[head, :2] = (
            tip + (back - tip) * np.sqrt(v)[:, None] + side * (2 * w - 1)[:, None] * np.sqrt(v)[:, None]
        )
        basis = basis_from_normal(obj.interaction.rotation_axis_local)
    elif kind == "straight_arrow":
        points = np.column_stack([np.zeros(count), radius * (2 * u - 1), np.zeros(count)])
        head = u > 0.72
        points[head, 0] = (rng.random(head.sum()) * 2 - 1) * (1 - u[head]) * radius * 1.8
        basis = basis_from_normal(obj.interaction.inspect_normal_local)
    elif kind in ("highlight", "label"):
        angle = u * 2 * np.pi
        points = np.column_stack([radius * np.cos(angle), radius * np.sin(angle), np.zeros(count)])
        basis = basis_from_normal(obj.interaction.inspect_normal_local)
    else:
        raise ValueError(f"unsupported cue type {kind}")
    points = points @ basis.T + np.asarray(obj.interaction.cue_offset_local_m)
    return points[rng.permutation(count)].astype(np.float32)


def splat_arrays(
    scene: SceneSpec,
    cue: DisplayCue,
    pose: Pose,
    camera_position,
    look_at,
    focus_m: float,
    brightness: float = 1.0,
    calibration: ResponseProfile | None = None,
):
    if not 0 <= brightness <= 4:
        raise ValueError("preview brightness must be within [0,4]")
    if focus_m <= 0:
        raise ValueError("focus distance must be positive")
    if cue.n_gaussians > 8192:
        raise ValueError("cue budget exceeds the declared nested pool capacity")
    cal = profile() if calibration is None else calibration
    centers = local_cue_pool(scene.scene_id, cue.target_id, cue.cue_type)[: cue.n_gaussians].copy()
    if cue.action == "inspect_back":
        # The cached highlight pool defines the ring shape. Translate only this
        # private copy to the contracted inspection surface, leaving point cues
        # and their shared cached pool unchanged.
        centers -= np.asarray(cue.interaction.cue_offset_local_m, dtype=np.float32)
        centers += np.asarray(cue.interaction.inspect_point_local_m, dtype=np.float32)
        centers += (
            np.asarray(cue.interaction.inspect_normal_local, dtype=np.float32)
            * cue.interaction.inspect_cue_clearance_m
        )
    if cue.cue_type == "ring_arrow" and cue.angle_deg is not None and cue.angle_deg < 0:
        plane = basis_from_normal(cue.interaction.rotation_axis_local)
        origin = np.asarray(cue.interaction.cue_offset_local_m)
        planar = (centers - origin) @ plane
        planar[:, 1] *= -1
        centers = (planar @ plane.T + origin).astype(np.float32)
    world = transform_points(pose, centers)
    forward = np.asarray(look_at, float) - camera_position
    length = np.linalg.norm(forward)
    if length <= 0:
        raise ValueError("camera position and target coincide")
    forward /= length
    depth = (world - np.asarray(camera_position)) @ forward
    widths, peaks, _ = envelope(cue.sigma_value, depth - focus_m, cal)
    # Isotropic preview Gaussians use variance of the intensity envelope.
    variance = (widths * cal.visual_magnification / 2) ** 2
    covariance = variance[:, None, None] * np.eye(3)[None, :, :]
    optical_depth = (
        cal.per_splat_optical_depth * cal.reference_count / max(cue.n_gaussians, 1) * peaks * brightness
    )
    opacity = -np.expm1(-optical_depth)
    rgb = np.tile(np.array([[0.12, 0.80, 0.64]], np.float32), (cue.n_gaussians, 1))
    return centers, covariance.astype(np.float32), rgb, opacity[:, None].astype(np.float32)


def camera_aligned_rgba(
    centers, covariances, opacities, rgbs, world_pose, position, look_at, size=(640, 400), fov_y_deg=42.0
):
    """Reference image from the same splat arrays, using a normal Gaussian rasterizer."""
    from scipy.ndimage import gaussian_filter
    from .camera import basis

    width, height = size
    right, up, forward = basis(position, look_at)
    points = transform_points(world_pose, centers) - np.asarray(position)
    depth = points @ forward
    valid = depth > 0.001
    image = np.zeros((height, width), np.float64)
    focal = height / (2 * np.tan(np.deg2rad(fov_y_deg) / 2))
    px = points @ right / np.maximum(depth, 0.001) * focal + width / 2
    py = height / 2 - points @ up / np.maximum(depth, 0.001) * focal
    std = np.sqrt(covariances[:, 0, 0]) / np.maximum(depth, 0.001) * focal
    # Quantize only the reference rasterizer's filter radius; 3D arrays remain continuous.
    bins = np.round(std * 4) / 4
    for value in np.unique(bins[valid]):
        take = valid & (bins == value) & (px >= 0) & (px < width) & (py >= 0) & (py < height)
        if not take.any():
            continue
        impulse = np.zeros_like(image)
        alpha = opacities[take, 0].astype(float)
        optical = -np.log1p(-np.minimum(alpha, 1 - 1e-7))
        radius = max(float(value), 0.5)
        np.add.at(impulse, (py[take].astype(int), px[take].astype(int)), optical * 2 * np.pi * radius**2)
        image += gaussian_filter(impulse, radius, mode="constant")
    alpha = -np.expm1(-image)
    result = np.zeros((height, width, 4), np.uint8)
    color = rgbs[0] if len(rgbs) else np.zeros(3)
    result[:, :, :3] = np.round(color * 255).astype(np.uint8)
    result[:, :, 3] = np.round(alpha * 255).astype(np.uint8)
    return result
