"""Preserved baseline behavior at real semantic, storage and serialization boundaries.

These tests do not stand in for model execution and never fabricate model responses.
"""

import json

import numpy as np
import pytest
import trimesh
from pydantic import ValidationError

from holocue.config import load_policy, load_scene
from holocue.models import CueSemantic, Decision, SceneSpec, Session, Task, UserMessage
from holocue.projection import allocate, packet
from holocue.provider import OpenAICompatiblePlanner, decision_schema
from holocue.response import local_cue_pool
from holocue.spatial import matrix, trajectory
from holocue.state import ConflictError, DomainError, apply_decision, validate_decision
from holocue.store import Store


def rotation(target="B", role="current", depth="precise"):
    return CueSemantic(
        target_id=target,
        action="rotate",
        angle_deg=30,
        cue_type="ring_arrow",
        task_role=role,
        priority=2,
        depth_requirement=depth,
        instruction="逆时针转动三十度",
    )


def plan():
    return Decision(operation="replace", assistant_message="执行旋转任务", cues=[rotation()])


def command(operation):
    return Decision(operation=operation, assistant_message="用户确认操作")


def temporary(target="C", action="inspect_back"):
    return Decision(
        operation="interrupt",
        assistant_message="执行临时任务",
        cues=[
            CueSemantic(
                target_id=target,
                action=action,
                cue_type="highlight",
                task_role="current",
                priority=2,
                depth_requirement="persistent",
                instruction="临时查看对象",
            )
        ],
    )


def session():
    return Session(session_id="domain", scene_id="control_panel", backend_mode="domain_test")


def message(text="请求任务", request_id="request", revision=0):
    return UserMessage(text=text, request_id=request_id, expected_revision=revision)


def test_nullable_model_message_persists_structured_decision_and_keeps_old_history(tmp_path):
    scene = load_scene("control_panel")
    store = Store(tmp_path / "question.sqlite")
    state = store.create(scene.scene_id, "domain_test")
    old = {"role": "assistant", "content": "旧版本记录的实际文字"}
    state.history.append(old)
    state.assistant_message = old["content"]
    with store.connection() as connection:
        store._save(connection, state)
    decision = Decision(operation="replace", assistant_message=None, cues=[rotation()])
    result = store.manual(state.session_id, state.revision, decision, scene)
    reopened = Store(store.path).get(state.session_id)
    assert reopened.model_dump() == result.model_dump()
    assert reopened.assistant_message is None
    assert reopened.history[0] == old
    assert json.loads(reopened.history[-1]["content"]) == decision.model_dump()
    assert reopened.queue[0].semantic.instruction == decision.cues[0].instruction
    planner = OpenAICompatiblePlanner()
    context = json.loads(
        planner.request_body(reopened, scene, message(revision=reopened.revision))["messages"][1]["content"][
            0
        ]["text"]
    )
    assert context["history"] == reopened.history
    paused = store.manual(
        reopened.session_id,
        reopened.revision,
        Decision(operation="pause", assistant_message="已暂停任务"),
        scene,
    )
    assert paused.execution == "paused" and paused.assistant_message == "已暂停任务"
    assert json.loads(paused.history[-1]["content"])["operation"] == "pause"


@pytest.mark.parametrize("field", ["sigma", "N", "n_gaussians", "position_m"])
def test_model_cannot_supply_physical_controls(field):
    data = plan().model_dump()
    data["cues"][0][field] = 12
    with pytest.raises(ValidationError):
        Decision.model_validate(data)


def test_rotation_requires_explicit_angle():
    data = rotation().model_dump()
    data["angle_deg"] = None
    with pytest.raises(ValidationError):
        CueSemantic.model_validate(data)


def test_temporary_task_cannot_be_dropped_by_resume():
    scene = load_scene("control_panel")
    state = apply_decision(session(), plan(), scene)
    state = apply_decision(state, temporary(), scene)
    before = state.model_dump_json()
    with pytest.raises(DomainError, match="Complete the temporary task"):
        apply_decision(state, command("resume"), scene)
    assert state.model_dump_json() == before


def test_nested_interruptions_resume_in_last_in_first_out_order():
    scene = load_scene("control_panel")
    state = apply_decision(session(), plan(), scene)
    original = [task.model_dump() for task in state.queue]
    state = apply_decision(state, temporary(), scene)
    first_temporary = [task.model_dump() for task in state.queue]
    state = apply_decision(state, temporary("A", "point"), scene)
    assert len(state.suspended) == 2
    state = apply_decision(state, command("complete"), scene)
    state = apply_decision(state, command("resume"), scene)
    assert [task.model_dump() for task in state.queue] == first_temporary
    state = apply_decision(state, command("complete"), scene)
    state = apply_decision(state, command("resume"), scene)
    assert [task.model_dump() for task in state.queue] == original
    assert state.queue[0].semantic.angle_deg == 30
    assert not state.suspended


def test_unknown_target_and_unsupported_action_are_rejected():
    scene = load_scene("control_panel")
    for target, error in [("UNKNOWN", "Unknown object"), ("C", "does not support rotate")]:
        with pytest.raises(DomainError, match=error):
            validate_decision(
                Decision(operation="replace", assistant_message="请求旋转", cues=[rotation(target)]), scene
            )


@pytest.mark.parametrize("role", ["next", "background"])
def test_new_plan_rejects_invisible_cues_without_changing_the_requested_weight(role):
    hidden = CueSemantic(
        target_id="A",
        action="point",
        cue_type="label",
        task_role=role,
        priority=0,
        depth_requirement="neutral",
        instruction="零权重记录",
    )
    decision = Decision(operation="replace", assistant_message="域边界检查", cues=[rotation(), hidden])
    with pytest.raises(DomainError, match="positive priority"):
        validate_decision(decision, load_scene("control_panel"))
    assert hidden.priority == 0


def test_positive_next_promotes_and_completes_through_real_store(tmp_path):
    store = Store(tmp_path / "positive.sqlite")
    scene = load_scene("control_panel")
    initial = store.create(scene.scene_id, "domain_test")
    following = rotation("A", "next")
    following.angle_deg = -15
    decision = Decision(operation="replace", assistant_message="两步旋转", cues=[rotation(), following])
    job, _, _ = store.begin(initial.session_id, message())
    planned = store.commit(job["id"], decision, scene, {"source": "domain_test"})
    ids = [task.task_id for task in planned.queue]
    first = store.manual(initial.session_id, planned.revision, command("complete"), scene)
    reloaded = Store(store.path).get(initial.session_id)
    assert reloaded == first
    assert reloaded.completed[0].task_id == ids[0]
    assert reloaded.queue[0].task_id == ids[1]
    assert reloaded.queue[0].semantic.task_role == "current"
    assert reloaded.queue[0].semantic.priority == following.priority
    assert reloaded.queue[0].semantic.angle_deg == -15
    assert packet(reloaded, scene, load_policy()).cues[0].n_gaussians > 0
    finished = store.manual(initial.session_id, reloaded.revision, command("complete"), scene)
    assert Store(store.path).get(initial.session_id) == finished
    assert finished.execution == "idle" and not finished.queue
    assert [task.task_id for task in finished.completed] == ids


def test_legacy_zero_next_completion_fails_atomically_and_remains_readable(tmp_path):
    store = Store(tmp_path / "legacy.sqlite")
    scene = load_scene("control_panel")
    legacy = store.create(scene.scene_id, "domain_test")
    hidden = rotation("A", "next")
    hidden.priority = 0
    legacy.queue = [
        Task(task_id="legacy-current", semantic=rotation()),
        Task(task_id="legacy-hidden", semantic=hidden),
    ]
    legacy.execution = "running"
    # Persist a real historical-format record without treating it as a new plan.
    with store.connection() as connection:
        store._save(connection, legacy)
    before = store.get(legacy.session_id).model_dump_json()
    events_before = store.events(legacy.session_id)
    with pytest.raises(DomainError, match="Cannot activate a zero-priority task"):
        store.manual(legacy.session_id, legacy.revision, command("complete"), scene)
    reopened = Store(store.path)
    assert reopened.get(legacy.session_id).model_dump_json() == before
    assert reopened.events(legacy.session_id) == events_before
    assert reopened.get(legacy.session_id).queue[1].semantic.priority == 0


def test_background_cannot_precede_an_actionable_step():
    background = CueSemantic(
        target_id="C",
        action="point",
        cue_type="highlight",
        task_role="background",
        priority=1,
        depth_requirement="persistent",
        instruction="观察模块",
    )
    with pytest.raises(ValidationError, match="background cues must follow"):
        Decision(
            operation="replace",
            assistant_message="错误顺序",
            cues=[rotation(), background, rotation("A", "next")],
        )


@pytest.mark.parametrize("weights,budget", [([5, 2], 6000), ([1, 1, 1], 10), ([0, 5, 0], 14), ([5], 0)])
def test_budget_preserves_exact_sum_and_zero_weight_exclusion(weights, budget):
    counts = allocate(weights, budget)
    assert sum(counts) == budget
    assert all(count >= 0 for count in counts)
    assert all(counts[index] == 0 for index, weight in enumerate(weights) if weight == 0)


def test_empty_and_invalid_budget_inputs():
    assert allocate([0, 0], 12) == [0, 0]
    assert allocate([], 10) == []
    with pytest.raises(ValueError):
        allocate([-1, 2], 10)
    with pytest.raises(ValueError):
        allocate([1], -1)


def test_count_and_depth_profile_are_independent():
    scene = load_scene("control_panel")
    decision = Decision(
        operation="replace",
        assistant_message="相同优先级的不同焦深需求",
        cues=[rotation(), rotation("A", "next", "persistent")],
    )
    display = packet(apply_decision(session(), decision, scene), scene, load_policy())
    assert display.cues[0].n_gaussians == display.cues[1].n_gaussians
    assert display.cues[0].sigma_value != display.cues[1].sigma_value


def test_real_cue_pool_is_deterministic_and_prefix_nested():
    first = local_cue_pool("control_panel", "B", "ring_arrow")
    second = local_cue_pool("control_panel", "B", "ring_arrow")
    assert first.shape == (8192, 3)
    assert np.isfinite(first).all()
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(first[:1000], second[:2000][:1000])


def test_animation_does_not_complete_or_mutate_task_state():
    scene = load_scene("control_panel")
    state = apply_decision(session(), plan(), scene)
    before = state.model_dump_json()
    cue = packet(state, scene, load_policy()).cues[0]
    start = trajectory(cue, 0.0)
    end = trajectory(cue, cue.interaction.duration_s)
    assert not np.allclose(matrix(start), matrix(end))
    assert state.model_dump_json() == before
    assert not state.completed
    assert len(state.queue) == 1


@pytest.mark.parametrize("angle", [-90.0, 90.0])
def test_rotation_end_value_and_sign_follow_declared_axis(angle):
    scene = load_scene("control_panel")
    semantic = rotation().model_copy(update={"angle_deg": angle})
    state = apply_decision(
        session(), Decision(operation="replace", assistant_message="旋转角度测试", cues=[semantic]), scene
    )
    cue = packet(state, scene, load_policy()).cues[0]
    end = trajectory(cue, cue.interaction.duration_s)
    radians = np.deg2rad(angle)
    expected = np.array(
        [[np.cos(radians), -np.sin(radians), 0.0], [np.sin(radians), np.cos(radians), 0.0], [0.0, 0.0, 1.0]]
    )
    np.testing.assert_allclose(matrix(end)[:3, :3], expected, atol=1e-12)
    np.testing.assert_allclose(matrix(trajectory(cue, 100.0)), matrix(end), atol=1e-12)


def test_repeated_object_steps_keep_distinct_ordered_task_ids():
    scene = load_scene("control_panel")
    second = CueSemantic(
        target_id="B",
        action="point",
        cue_type="highlight",
        task_role="next",
        priority=2,
        depth_requirement="persistent",
        instruction="随后检查旋钮刻线",
    )
    state = apply_decision(
        session(),
        Decision(operation="replace", assistant_message="先旋转再检查", cues=[rotation(), second]),
        scene,
    )
    task_ids = [task.task_id for task in state.queue]
    assert len(task_ids) == len(set(task_ids)) == 2
    assert [task.semantic.action for task in state.queue] == ["rotate", "point"]
    assert packet(state, scene, load_policy()).cues[0].task_id == task_ids[0]
    state = apply_decision(state, command("complete"), scene)
    assert state.queue[0].task_id == task_ids[1]
    assert state.queue[0].semantic.action == "point"
    assert packet(state, scene, load_policy()).cues[0].task_id == task_ids[1]


def test_request_id_is_idempotent_and_cannot_change_content(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    initial = store.create("control_panel", "domain_test")
    job, planning, created = store.begin(initial.session_id, message())
    repeated, current, created_again = store.begin(initial.session_id, message())
    assert job["id"] == repeated["id"]
    assert created and not created_again
    assert current == planning
    with pytest.raises(ConflictError, match="different content"):
        store.begin(initial.session_id, message(text="不同请求内容"))
    assert store.get(initial.session_id) == planning


def test_new_request_rejects_stale_revision(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    initial = store.create("control_panel", "domain_test")
    store.begin(initial.session_id, message())
    with pytest.raises(ConflictError, match="stale expected_revision"):
        store.begin(initial.session_id, message(request_id="second"))


def test_manual_pause_invalidates_inflight_commit(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    scene = load_scene("control_panel")
    initial = store.create(scene.scene_id, "domain_test")
    job, planning, _ = store.begin(initial.session_id, message())
    paused = store.manual(initial.session_id, planning.revision, command("pause"), scene)
    assert store.job(job["id"])["status"] == "superseded"
    assert store.commit(job["id"], plan(), scene, {"source": "domain_test"}) is None
    assert store.get(initial.session_id) == paused
    assert paused.execution == "paused"
    assert not paused.queue


def test_restart_pauses_preserved_tasks_until_explicit_resume(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    scene = load_scene("control_panel")
    initial = store.create(scene.scene_id, "domain_test")
    job, _, _ = store.begin(initial.session_id, message())
    committed = store.commit(job["id"], plan(), scene, {"source": "domain_test"})
    reopened = Store(store.path)
    reopened.recover()
    recovered = reopened.get(initial.session_id)
    assert recovered.queue == committed.queue
    assert recovered.execution == "paused"
    assert recovered.revision > committed.revision
    resumed = reopened.manual(initial.session_id, recovered.revision, command("resume"), scene)
    assert resumed.execution == "running"
    assert resumed.queue == committed.queue


def test_environment_ids_still_obey_identifier_contract():
    data = load_scene("control_panel").model_dump()
    data["environment"][0]["prop_id"] = "9bench"
    with pytest.raises(ValidationError):
        SceneSpec.model_validate(data)


def test_environment_ids_are_unique_and_not_planner_targets():
    scene = load_scene("control_panel")
    data = scene.model_dump()
    data["environment"].append(data["environment"][0].copy())
    with pytest.raises(ValidationError, match="duplicate environment prop IDs"):
        SceneSpec.model_validate(data)
    prop_id = scene.environment[0].prop_id
    with pytest.raises(DomainError, match="Unknown object"):
        validate_decision(
            Decision(operation="replace", assistant_message="无效目标", cues=[rotation(prop_id)]), scene
        )
    body = OpenAICompatiblePlanner().request_body(session(), scene, message())
    context = json.loads(body["messages"][1]["content"][0]["text"])
    assert prop_id not in {obj["object_id"] for obj in context["objects"]}
    assert len(context["objects"]) == len(scene.objects)


def test_strict_request_disables_thinking_and_preserves_schema():
    body = OpenAICompatiblePlanner().request_body(session(), load_scene("control_panel"), message())
    assert body["chat_template_kwargs"]["enable_thinking"] is False
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == decision_schema(
        session(), load_scene("control_panel")
    )


def test_measured_profile_does_not_claim_optical_execution():
    scene = load_scene("control_panel")
    state = apply_decision(session(), plan(), scene)
    policy = load_policy()
    policy["calibration"] = {"id": "lab-profile", "kind": "measured", "sigma_units": "m"}
    assert packet(state, scene, policy).renderer_kind == "semantic_preview"


def authored_object(scene_id, object_id):
    from holocue.modeling import make_object

    obj = next(obj for obj in load_scene(scene_id).objects if obj.object_id == object_id)
    return obj, make_object(obj).scene


def named_parts(scene, suffix):
    return [
        scene.geometry[scene.graph[node][1]]
        for node in scene.graph.nodes_geometry
        if node.endswith("_" + suffix)
    ]


def test_node3_has_open_fiber_ports_and_supported_cable_tails():
    obj, scene = authored_object("server_rack", "NODE3")
    ports = named_parts(scene, "fiber_socket")
    assert len(ports) == 4
    for mesh in ports:
        centered = mesh.vertices - mesh.bounds.mean(axis=0)
        # Annular ports have a real aperture, not a dark solid painted disk.
        radial = np.linalg.norm(centered[:, [0, 2]], axis=1)
        assert radial.min() > 0.004
        assert radial.max() - radial.min() > 0.002
        assert mesh.bounds[0, 1] >= obj.size_m[1] / 2
    live = named_parts(scene, "fiber_live_collar")
    assert len(live) == 1
    assert live[0].visual.material.baseColorFactor[1] > live[0].visual.material.baseColorFactor[0]
    tails = named_parts(scene, "fiber_cable_tail")
    assert tails
    assert min(mesh.bounds[0, 2] for mesh in tails) > -obj.size_m[2] / 2


def test_motor_isolator_has_an_open_center_on_actual_inspection_face():
    obj, scene = authored_object("drone_bench", "M3")
    rings = named_parts(scene, "isolator_ring")
    assert len(rings) == 1
    ring = rings[0]
    point = np.asarray(obj.interaction.inspect_point_local_m)
    radial = np.linalg.norm(ring.vertices[:, 1:] - point[1:], axis=1)
    assert radial.min() > 0.003
    assert radial.max() > 0.010
    assert ring.bounds[1, 0] == pytest.approx(point[0])
    assert ring.visual.material.metallicFactor == 0
    assert ring.visual.material.roughnessFactor > 0.8


def test_pot3_has_closed_finite_wall_with_three_recessed_inner_bands():
    obj, scene = authored_object("dig_site", "POT3")
    mesh = named_parts(scene, "incised_inner_wall")[0]
    # Exported hard normals split coincident vertices. Test physical closure
    # after exact coordinate welding, without rounding or removing any face.
    vertices, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
    surface = trimesh.Trimesh(vertices=vertices, faces=inverse[mesh.faces], process=False)
    np.testing.assert_array_equal(surface.triangles, mesh.triangles)
    mesh = surface
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0
    # Sample the authored cross section; no geometry raycaster or image surrogate.
    center = mesh.vertices[np.isclose(mesh.vertices[:, 0], 0.0, atol=1e-9)]
    inner = center[center[:, 1] > 0]
    inner = inner[np.argsort(inner[:, 2])]
    minima = np.flatnonzero((inner[1:-1, 1] < inner[:-2, 1]) & (inner[1:-1, 1] < inner[2:, 1])) + 1
    assert len(minima) == 3
    np.testing.assert_allclose(inner[minima, 2] / obj.size_m[2], [-0.22, 0, 0.22], atol=0.015)
    assert inner[:, 1].max() - inner[:, 1].min() > 0.002
    outer = center[center[:, 1] < 0]
    assert inner[:, 1].min() - outer[:, 1].max() > 0.010


def test_mirror_scale_and_support_are_below_optic_and_rear_label_is_textured():
    obj, scene = authored_object("optical_bench", "M")
    ticks = named_parts(scene, "degree_tick")
    pointer = named_parts(scene, "degree_pointer")
    fork = named_parts(scene, "gimbal_fork")
    assert len(ticks) >= 13 and len(pointer) == 1 and len(fork) == 2
    assert max(part.bounds[1, 2] for part in ticks) < 0
    assert fork[0].bounds.mean(axis=0)[0] * fork[1].bounds.mean(axis=0)[0] < 0
    labels = [mesh for mesh in scene.geometry.values() if mesh.visual.material.baseColorTexture is not None]
    assert labels
    assert any(mesh.bounds.mean(axis=0)[1] > 0 for mesh in labels)


def test_added_cassette_locks_and_tool_insert_preserve_receiver_clearance():
    cassette, scene = authored_object("infusion_ward", "PUMPCASSETTE")
    receiver = next(obj for obj in load_scene("infusion_ward").objects if obj.object_id == "SLOT2")
    assert named_parts(scene, "cassette_side_lock")
    assert scene.extents[0] < receiver.size_m[0] - 0.012
    tool, scene = authored_object("cnc_toolchange", "T09")
    inserts = named_parts(scene, "carbide_insert")
    assert inserts
    assert max(np.linalg.norm(mesh.vertices[:, :2], axis=1).max() for mesh in inserts) < 0.020
