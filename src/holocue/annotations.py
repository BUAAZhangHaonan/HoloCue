"""Camera-space border labels with minimum-length assignment to scene anchors."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.optimize import linear_sum_assignment,isotonic_regression

from .camera import basis


@dataclass(frozen=True)
class Annotation:
    object_id: str
    world_position: tuple[float, float, float]
    text_height_m: float
    rectangle_ndc: tuple[float, float, float, float]
    leader: np.ndarray
    anchor: str


def annotation_metrics(identifiers, aspect: float):
    if not identifiers or aspect <= 0 or not np.isfinite(aspect):
        raise ValueError('annotations require IDs and a positive finite aspect')
    # Each label owns a border rectangle. Width includes a conservative
    # full-em bound for ASCII identifiers and a two-em inset.
    characters = max(map(len, identifiers)) + 2
    height = min(.030, .72 * aspect / characters)
    width = height * characters / aspect
    return height, width


def annotation_margin(identifiers, aspect: float, base: float) -> float:
    _, width = annotation_metrics(identifiers, aspect)
    return max(base, width + .065)


def border_annotations(anchors: dict[str, np.ndarray], position, look_at,
                       fov_y_deg: float, aspect: float, up=(0., 0., 1.)) -> list[Annotation]:
    """Assign each in-view object to a nonoverlapping perimeter label slot.

    Labels and leader endpoints lie in one camera plane. Their projections are
    invariant to scene scale. An object's actual anchor remains unchanged.
    """
    ids = sorted(anchors)
    height, width = annotation_metrics(ids, aspect)
    eye = np.asarray(position, float)
    right, vertical, forward = basis(eye, look_at, up)
    points = np.asarray([anchors[key] for key in ids], float)
    if points.shape != (len(ids), 3) or not np.isfinite(points).all():
        raise ValueError('annotation anchors must be finite three-dimensional points')
    local = points-eye
    depths = local @ forward
    visible = depths > .002
    if not visible.any():
        return []
    ids = [key for key, keep in zip(ids, visible) if keep]
    points = points[visible]; local = local[visible]; depths = depths[visible]
    tangent = np.tan(np.deg2rad(fov_y_deg)/2)
    projected = np.column_stack((local@right/(depths*tangent*aspect),
                                 local@vertical/(depths*tangent)))
    in_frame = np.all(np.abs(projected) < 1., axis=1)
    ids = [key for key, keep in zip(ids, in_frame) if keep]
    points = points[in_frame]; projected = projected[in_frame]
    if not ids:
        return []
    rows = (len(ids)+1)//2
    ys = np.linspace(.80, -.80, rows) if rows > 1 else np.array([0.])
    x = .96-width/2
    slots = np.asarray([(side*x, y) for side in (-1, 1) for y in ys])
    if rows > 1 and 1.6/(rows-1) <= height*1.8:
        raise ValueError('too many objects for the configured annotation rows')
    cost = np.sum((projected[:, None]-slots[None])**2, axis=2)
    row, col = linear_sum_assignment(cost)
    assigned=slots[col].copy()
    for side in (-1,1):
        members=np.flatnonzero(np.sign(assigned[:,0])==side)
        if len(members)==0:
            continue
        ordered=members[np.argsort(projected[members,1])]
        gap=height*2.2
        offsets=np.arange(len(ordered))*gap
        fitted=isotonic_regression(projected[ordered,1]-offsets,increasing=True).x
        fitted=np.clip(fitted,-.86,.86-gap*max(len(ordered)-1,0))
        assigned[ordered,1]=fitted+offsets
    depth = float(np.linalg.norm(np.asarray(look_at)-eye))
    if depth <= .002:
        raise ValueError('annotation plane must be in front of the camera')
    half_height = depth*tangent
    center = eye+forward*depth
    results = []
    for i, (sx,sy) in zip(row,assigned):
        inner_x = sx-np.sign(sx)*width/2
        end = center+right*inner_x*half_height*aspect+vertical*sy*half_height
        results.append(Annotation(ids[i], tuple(end), height*half_height,
            (sx-width/2, sy-height*.9, sx+width/2, sy+height*.9),
            np.asarray([points[i], end], dtype=np.float32),
            'center-right' if sx<0 else 'center-left'))
    return results
