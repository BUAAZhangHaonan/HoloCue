"""Camera regressions using real assets and domain state, not live model tests."""

import numpy as np
import pytest

from holocue import camera
from holocue.assets import load_asset, resource
from holocue.config import load_policy, load_scene, root
from holocue.models import CueSemantic, Decision, Session
from holocue.projection import packet
from holocue.response import splat_arrays
from holocue.spatial import trajectory, transform_points
from holocue.state import apply_decision
from holocue.viewer_scene import selected_cue_view


def cnc_packet(target, action):
    scene = load_scene("cnc_toolchange")
    state = apply_decision(
        Session(session_id="camera-domain", scene_id=scene.scene_id, backend_mode="domain_test"),
        Decision(
            operation="replace",
            assistant_message="领域取景测试",
            cues=[
                CueSemantic(
                    target_id=target,
                    action=action,
                    cue_type="ring_arrow" if action == "rotate" else "highlight",
                    task_role="current",
                    priority=3,
                    depth_requirement="persistent",
                    instruction="检查相机取景",
                    angle_deg=-90 if action == "rotate" else None,
                )
            ],
        ),
        scene,
    )
    return scene, packet(state, scene, load_policy())


def original_view(scene, display, target, mode, aspect):
    obj = next(o for o in scene.objects if o.object_id == target)
    pose = display.object_poses[target]
    if mode == "inspection":
        return camera.inspect_view(obj, pose, scene.render_hints.fov_y_deg, aspect)
    mesh = load_asset(str(resource(root(), obj.asset)), scene.asset_axes)
    first = next((cue for cue in display.cues if cue.target_id == target), None)
    return camera.detail_view(
        obj,
        pose,
        mesh.bounds,
        np.asarray(scene.camera_position_m) - scene.camera_look_at_m,
        first.action if first else None,
        scene.render_hints.fov_y_deg,
        aspect,
        scene.render_hints.viewport_margin,
    )


def rendered_quads(scene, display, cue, elapsed, mode, position, look, up):
    """Project the actual response's native three-sigma quads, not a fake cue."""
    obj = next(o for o in scene.objects if o.object_id == cue.target_id)
    right, vertical, forward = camera.basis(position, look, up)
    inspection = mode == "inspection" or any(
        c.target_id == cue.target_id and c.action == "inspect_back" for c in display.cues
    )
    anchor = camera.focus_point(obj, display.object_poses[cue.target_id], inspection)
    focus = float((anchor - position) @ forward)
    pose = trajectory(cue, elapsed)
    arrays = splat_arrays(scene, cue, pose, position, look, focus)
    centers, covariance, _, _ = arrays
    world = transform_points(pose, centers)
    radius = 3 * np.sqrt(covariance[:, 0, 0])
    directions = np.asarray([-right - vertical, right - vertical, right + vertical, -right + vertical])
    points = (world[:, None, :] + radius[:, None, None] * directions).reshape(-1, 3)
    return points, arrays


@pytest.mark.parametrize("aspect", [1.276, 0.97])
@pytest.mark.parametrize(
    "target,action,mode",
    [
        ("MODESWITCH", "rotate", "detail"),
        ("T03", "inspect_back", "inspection"),
        ("T03", "inspect_back", "detail"),
    ],
)
def test_cnc_framing_keeps_real_cue_visible_without_changing_response(target, action, mode, aspect):
    scene, display = cnc_packet(target, action)
    cue = display.cues[0]
    elapsed = cue.interaction.duration_s * 0.4 if action == "rotate" else 0.0
    position, look, up = original_view(scene, display, target, mode, aspect)
    old_points, old_arrays = rendered_quads(scene, display, cue, elapsed, mode, position, look, up)
    before, _ = camera.project(old_points, position, look, scene.render_hints.fov_y_deg, aspect, up)
    assert np.abs(before).max() > 1.0, "This real CNC case must exercise previously clipped guidance"

    new_position, new_look = selected_cue_view(
        scene, display, display.object_poses, {cue.task_id: elapsed}, target, mode, position, look, up, aspect
    )
    points, arrays = rendered_quads(scene, display, cue, elapsed, mode, new_position, new_look, up)
    projected, depth = camera.project(
        points, new_position, new_look, scene.render_hints.fov_y_deg, aspect, up
    )
    assert depth.min() > 0
    assert np.abs(projected).max() <= 1 - scene.render_hints.viewport_margin + 1e-6
    assert np.allclose(camera.basis(new_position, new_look, up), camera.basis(position, look, up), atol=1e-12)
    for original, actual in zip(old_arrays, arrays):
        np.testing.assert_array_equal(actual, original)

    if target == "T03":
        # Inspecting the pull stud is a local view, including when selected via
        # detail while the first visible cue is inspect_back. Fitting the entire
        # long tool would destroy this intended local view.
        obj = next(o for o in scene.objects if o.object_id == target)
        region = camera.inspection_points(obj, display.object_poses[target])
        region_ndc, _ = camera.project(
            region, new_position, new_look, scene.render_hints.fov_y_deg, aspect, up
        )
        assert np.abs(region_ndc).max() <= 1 - scene.render_hints.viewport_margin + 1e-6
        mesh = load_asset(str(resource(root(), obj.asset)), scene.asset_axes)
        full_tool = transform_points(display.object_poses[target], camera.corners(mesh.bounds))
        full_tool_ndc, _ = camera.project(
            full_tool, new_position, new_look, scene.render_hints.fov_y_deg, aspect, up
        )
        assert np.abs(full_tool_ndc).max() > 1.0, "The pull-stud view must not become a whole-tool overview"


@pytest.mark.parametrize("empty", [True, False])
def test_no_visible_cue_preserves_exact_camera(empty):
    scene, display = cnc_packet("T03", "inspect_back")
    position, look, up = original_view(scene, display, "T03", "inspection", 0.97)
    if empty:
        state = Session(session_id="empty-camera", scene_id=scene.scene_id, backend_mode="domain_test")
        display = packet(state, scene, load_policy())
        brightness = 1.0
        assert not display.cues
    else:
        brightness = 0.0
        cue = display.cues[0]
        _, _, _, alpha = splat_arrays(scene, cue, cue.pose, position, look, 0.2, brightness)
        assert np.count_nonzero(alpha) == 0
    actual = selected_cue_view(
        scene, display, display.object_poses, {}, "T03", "inspection", position, look, up, 0.97, brightness
    )
    np.testing.assert_array_equal(actual[0], position)
    np.testing.assert_array_equal(actual[1], look)


def test_repeated_object_keeps_rotate_as_first_visible_detail_action():
    # The domain queue has two M steps. Production projection emits one visible
    # M cue, matching the saved live-packet observation; no duplicate display
    # cue or claimed model reply is fabricated here.
    scene = load_scene("optical_bench")
    steps = [step for step in scene.task_contract.ordered_steps if step.target_id == "M"]
    assert [step.action for step in steps] == ["rotate", "inspect_back"]
    semantic = [
        CueSemantic(
            target_id=step.target_id,
            action=step.action,
            cue_type="ring_arrow" if step.action == "rotate" else "highlight",
            task_role="current" if index == 0 else "next",
            priority=3,
            depth_requirement=step.depth_requirement,
            instruction="领域有序步骤测试",
            angle_deg=step.angle_deg,
            reference_id=step.reference_id,
        )
        for index, step in enumerate(steps)
    ]
    state = apply_decision(
        Session(session_id="repeat-camera", scene_id=scene.scene_id, backend_mode="domain_test"),
        Decision(operation="replace", assistant_message="领域测试", cues=semantic),
        scene,
    )
    assert [task.semantic.action for task in state.queue] == ["rotate", "inspect_back"]
    display = packet(state, scene, load_policy())
    matching = [cue for cue in display.cues if cue.target_id == "M"]
    assert [cue.action for cue in matching] == ["rotate"]
    position, look, up = original_view(scene, display, "M", "detail", 0.97)
    new_position, new_look = selected_cue_view(
        scene, display, display.object_poses, {}, "M", "detail", position, look, up, 0.97
    )
    obj = next(o for o in scene.objects if o.object_id == "M")
    mesh = load_asset(str(resource(root(), obj.asset)), scene.asset_axes)
    points = transform_points(display.object_poses["M"], camera.corners(mesh.bounds))
    ndc, depth = camera.project(points, new_position, new_look, scene.render_hints.fov_y_deg, 0.97, up)
    assert depth.min() > 0 and np.abs(ndc).max() <= 1.0 + 1e-6
