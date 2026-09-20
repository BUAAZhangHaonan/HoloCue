"""Rigid transforms and finite, frame-correct guidance trajectories in metres."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .models import DisplayCue, Pose, SceneObject


def rotation(pose: Pose) -> Rotation:
    return Rotation.from_quat(pose.wxyz, scalar_first=True)


def pose_from(position: np.ndarray, orient: Rotation) -> Pose:
    return Pose(position_m=tuple(position.tolist()), wxyz=tuple(orient.as_quat(scalar_first=True).tolist()))


def compose(a: Pose, b: Pose) -> Pose:
    ra = rotation(a)
    return pose_from(np.asarray(a.position_m) + ra.apply(b.position_m), ra * rotation(b))


def inverse(pose: Pose) -> Pose:
    r = rotation(pose).inv()
    return pose_from(-r.apply(pose.position_m), r)


def matrix(pose: Pose) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = rotation(pose).as_matrix()
    result[:3, 3] = pose.position_m
    return result


def transform_points(pose: Pose, points: np.ndarray) -> np.ndarray:
    return rotation(pose).apply(points) + np.asarray(pose.position_m)


def mating_goal(source: SceneObject, target: SceneObject, target_pose: Pose, action: str) -> Pose:
    key = 'insertion' if action == 'insert' else 'placement'
    if key in target.frames:
        receiver = target.frames[key]
    else:
        receiver = Pose(position_m=target.anchors[key])
    return compose(compose(target_pose, receiver), inverse(source.interaction.mating_pose))


def rotate_about(pose: Pose, axis: tuple, pivot: tuple, degrees: float) -> Pose:
    r = rotation(pose)
    delta = Rotation.from_rotvec(np.asarray(axis) * np.deg2rad(degrees))
    p = np.asarray(pivot)
    position = np.asarray(pose.position_m) + r.apply(p - delta.apply(p))
    return pose_from(position, r * delta)


def interpolate(a: Pose, b: Pose, fraction: float) -> Pose:
    if not 0 <= fraction <= 1:
        raise ValueError('interpolation fraction must be in [0, 1]')
    r = Slerp([0., 1.], Rotation.concatenate([rotation(a), rotation(b)]))([fraction])[0]
    return pose_from((1-fraction)*np.asarray(a.position_m)+fraction*np.asarray(b.position_m), r)


def path_keyframes(cue: DisplayCue) -> list[Pose]:
    if cue.goal_pose is None:
        raise ValueError('translation requires a goal pose')
    a, b = cue.pose, cue.goal_pose
    departure = np.asarray(a.position_m) + rotation(a).apply(cue.interaction.departure_axis_local)*cue.interaction.departure_distance_m
    axis = rotation(b).apply(cue.interaction.approach_axis_local)
    approach = np.asarray(b.position_m) + axis * cue.interaction.approach_distance_m
    height = max(departure[2], approach[2]) + cue.interaction.transit_height_m
    leave = Pose(position_m=tuple(departure), wxyz=a.wxyz)
    lift = Pose(position_m=(departure[0], departure[1], height), wxyz=a.wxyz)
    transit = Pose(position_m=(approach[0], approach[1], height), wxyz=b.wxyz)
    return [a, leave, lift, transit, Pose(position_m=tuple(approach), wxyz=b.wxyz), b]


def trajectory(cue: DisplayCue, elapsed_s: float) -> Pose:
    """Hold the final pose until explicit completion; pause is controlled by the clock."""
    if elapsed_s < 0:
        raise ValueError('elapsed time must be nonnegative')
    fraction = min(elapsed_s / cue.interaction.duration_s, 1.)
    if cue.action == 'rotate':
        if cue.angle_deg is None:
            raise ValueError('rotation angle is required')
        return rotate_about(cue.pose, cue.interaction.rotation_axis_local,
                            cue.interaction.pivot_local_m, cue.angle_deg * fraction)
    if cue.action in ('insert', 'assemble'):
        keys = path_keyframes(cue)
        lengths = np.asarray([np.linalg.norm(np.asarray(b.position_m)-a.position_m)+.01
                              for a,b in zip(keys,keys[1:])])
        cumulative = np.concatenate([[0.], np.cumsum(lengths)]) / lengths.sum()
        segment = min(int(np.searchsorted(cumulative, fraction, side='right')-1), len(keys)-2)
        u = (fraction-cumulative[segment])/(cumulative[segment+1]-cumulative[segment])
        u = float(np.clip(u,0,1))
        return interpolate(keys[segment], keys[segment+1], u*u*(3-2*u))
    return cue.pose


class ActionClock:
    """Monotonic action time retained across task interruption and restoration."""
    def __init__(self) -> None:
        self.elapsed: dict[str,float] = {}

    def advance(self, task_id: str, dt: float, running: bool) -> float:
        if dt < 0:
            raise ValueError('clock step must be nonnegative')
        self.elapsed.setdefault(task_id, 0.)
        if running:
            self.elapsed[task_id] += dt
        return self.elapsed[task_id]
