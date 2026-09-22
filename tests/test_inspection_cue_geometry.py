"""Inspection cues must clear real meshes without mutating cached point cues."""

import numpy as np
import pytest
from holocue.assets import load_asset, resource
from holocue.config import root, load_scene, list_scenes, load_policy
from holocue.models import CueSemantic, Decision, Session
from holocue.state import apply_decision
from holocue.projection import packet
from holocue.response import splat_arrays, local_cue_pool, basis_from_normal
from holocue.camera import inspect_view

TARGETS = [
    (s["scene_id"], o.object_id)
    for s in list_scenes()
    for o in load_scene(s["scene_id"]).objects
    if "inspect_back" in o.capabilities
]


@pytest.mark.parametrize("scene_id,target", TARGETS)
def test_inspection_ring_clears_mesh_and_point_pool(scene_id, target):
    spec = load_scene(scene_id)
    obj = next(o for o in spec.objects if o.object_id == target)
    decision = Decision(
        operation="replace",
        assistant_message="geometry test",
        cues=[
            CueSemantic(
                target_id=target,
                action="inspect_back",
                cue_type="highlight",
                task_role="current",
                priority=1,
                depth_requirement="precise",
                instruction="inspect",
            )
        ],
    )
    state = apply_decision(
        Session(session_id="geometry", scene_id=scene_id, backend_mode="domain_test"), decision, spec
    )
    cue = packet(state, spec, load_policy()).cues[0]
    position, look, _ = inspect_view(obj, obj.pose)
    original = local_cue_pool(scene_id, target, "highlight").copy()
    centers, cov, rgb, alpha = splat_arrays(spec, cue, cue.pose, position, look, 0.2)
    assert len(centers) == cue.n_gaussians
    assert np.isfinite(cov).all() and np.isfinite(alpha).all()
    assert np.array_equal(local_cue_pool(scene_id, target, "highlight"), original)
    point = cue.model_copy(update={"action": "point"})
    point_centers, *_ = splat_arrays(spec, point, point.pose, position, look, 0.2)
    assert np.array_equal(point_centers, original[: cue.n_gaussians])

    # Test actual triangle geometry from the contracted inspection-normal side.
    basis = basis_from_normal(obj.interaction.inspect_normal_local)
    tri = load_asset(str(resource(root(), obj.asset)), spec.asset_axes).to_geometry().triangles @ basis
    a = tri[:, 0, :2]
    b = tri[:, 1, :2] - a
    c = tri[:, 2, :2] - a
    den = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    valid = np.abs(den) > 1e-12
    for center in (centers @ basis)[:: max(len(centers) // 64, 1)]:
        p = center[:2] - a
        u = np.divide(p[:, 0] * c[:, 1] - p[:, 1] * c[:, 0], den, out=np.full(len(den), np.nan), where=valid)
        v = np.divide(b[:, 0] * p[:, 1] - b[:, 1] * p[:, 0], den, out=np.full(len(den), np.nan), where=valid)
        hit = valid & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        depth = tri[:, 0, 2] + u * (tri[:, 1, 2] - tri[:, 0, 2]) + v * (tri[:, 2, 2] - tri[:, 0, 2])
        assert not hit.any() or center[2] > depth[hit].max(), (scene_id, target, center)
