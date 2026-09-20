"""Material-preserving glTF loading with an explicit coordinate convention."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import trimesh

from .models import SceneSpec, Pose
from .spatial import matrix


def resource(root: Path, relative: str) -> Path:
    path = (root/relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('asset path escapes project root')
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


@lru_cache(maxsize=160)
def _load_asset(path: str, axes: str,mtime_ns: int,size: int) -> trimesh.Scene:
    result = trimesh.load_scene(path, process=False)
    if axes == 'gltf_y_up':
        result.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1,0,0]))
    elif axes != 'project_z_up':
        raise ValueError(f'unsupported asset axes {axes}')
    if not result.geometry:
        raise ValueError(f'empty asset {path}')
    return result


def load_asset(path: str,axes: str) -> trimesh.Scene:
    stat=Path(path).stat()
    return _load_asset(path,axes,stat.st_mtime_ns,stat.st_size)


def world_scene(root: Path, spec: SceneSpec, poses: dict[str,Pose] | None = None) -> trimesh.Scene:
    result = trimesh.Scene()
    poses = {} if poses is None else poses
    entries = [(o.object_id,o.asset,poses.get(o.object_id,o.pose),(1.,1.,1.)) for o in spec.objects]
    entries += [(p.prop_id,p.asset,p.pose,p.scale_m) for p in spec.environment]
    for name,asset,pose,scale in entries:
        local = load_asset(str(resource(root,asset)), spec.asset_axes)
        transform = matrix(pose) @ np.diag([*scale,1.])
        for node in local.graph.nodes_geometry:
            node_transform, geometry_name = local.graph[node]
            result.add_geometry(local.geometry[geometry_name].copy(),
                                node_name=f'{name}/{node}',
                                geom_name=f'{name}/{geometry_name}',
                                transform=transform@node_transform)
    return result
