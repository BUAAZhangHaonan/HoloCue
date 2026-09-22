from __future__ import annotations
import numpy as np


def quaternion_matrix(q):
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def quaternion_product(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return (
        w * v - x * i - y * j - z * k,
        w * i + x * v + y * k - z * j,
        w * j - x * k + y * v + z * i,
        w * k + x * j - y * i + z * v,
    )


def display_pose(cue, elapsed: float, running: bool):
    """The caller freezes elapsed time whenever execution is paused."""
    from .spatial import trajectory

    pose = trajectory(cue, max(elapsed, 0.0))
    return pose.position_m, pose.wxyz


def primitive_pool(kind: str, count: int = 8192, seed: int = 7) -> np.ndarray:
    """Fixed-seed, nested sampling of cue geometry, not learned optical Gaussians."""
    rng = np.random.default_rng(seed)
    u = rng.random(count)
    if kind == "ring_arrow":
        a = (0.2 + 1.65 * u) * np.pi
        p = np.stack([0.052 * np.cos(a), 0.052 * np.sin(a), np.full(count, 0.065)], axis=1)
        end = int(0.12 * count)
        # Arrow tip portion.
        p[:end] = np.stack(
            [0.034 + 0.018 * rng.random(end), -0.036 + 0.018 * rng.random(end), np.full(end, 0.065)], axis=1
        )
    elif kind == "straight_arrow":
        p = np.stack([np.zeros(count), 0.09 * u, np.full(count, 0.075)], axis=1)
        mask = u > 0.7
        v = rng.random(mask.sum())
        p[mask, 0] = np.where(v < 0.5, -1.0, 1.0) * (1 - (u[mask] - 0.7) / 0.3) * 0.023
    else:
        a = u * 2 * np.pi
        p = np.stack([0.054 * np.cos(a), 0.054 * np.sin(a), np.full(count, 0.065)], axis=1)
    # A fixed shuffle makes every prefix cover the full cue rather than just its tip.
    p = p[rng.permutation(count)]
    return p.astype("float32")
