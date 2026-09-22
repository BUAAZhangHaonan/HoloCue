"""Renderer-neutral frames for Blender and future optical transport adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

import numpy as np

from .models import DisplayPacket, SceneSpec
from .response import splat_arrays, profile
from .spatial import ActionClock, trajectory, transform_points


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    with partial.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, separators=(",", ":"))
        file.flush()
    os.replace(partial, path)


def frame(
    spec: SceneSpec,
    packet: DisplayPacket,
    clock: ActionClock,
    dt: float,
    camera_position,
    look_at,
    focus_m: float,
    brightness=1.0,
) -> dict:
    if packet.scene_id != spec.scene_id:
        raise ValueError("frame scene mismatch")
    cues = []
    for cue in packet.cues:
        if cue.n_gaussians == 0:
            continue
        elapsed = clock.advance(cue.task_id, dt, packet.execution == "running" and cue.task_role == "current")
        pose = trajectory(cue, elapsed)
        centers, covariance, rgb, opacity = splat_arrays(
            spec, cue, pose, camera_position, look_at, focus_m, brightness
        )
        cues.append(
            {
                "task_id": cue.task_id,
                "target_id": cue.target_id,
                "n_gaussians": len(centers),
                "centers_m": transform_points(pose, centers).tolist(),
                "radii_m": (3 * np.sqrt(covariance[:, 0, 0])).tolist(),
                "opacities": opacity[:, 0].tolist(),
                "rgb": rgb[0].tolist(),
                "pose": pose.model_dump(),
                "elapsed_s": elapsed,
            }
        )
    return {
        "schema_version": "1.1",
        "scene_id": spec.scene_id,
        "session_id": packet.session_id,
        "revision": packet.revision,
        "epoch": packet.epoch,
        "execution": packet.execution,
        "generated_at": time.time(),
        "renderer_kind": "analytic_gaussian_preview",
        "response_profile": profile().model_dump(),
        "rgb_encoding": "linear_0_1",
        "camera": {
            "position_m": list(camera_position),
            "look_at_m": list(look_at),
            "focus_m": focus_m,
            "brightness": brightness,
        },
        "object_poses": {k: v.model_dump() for k, v in packet.object_poses.items()},
        "cues": cues,
    }
