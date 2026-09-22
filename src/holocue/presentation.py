"""Read-only operator text derived from committed task state."""

from __future__ import annotations

from dataclasses import dataclass

from .models import SceneSpec, Session


EXECUTION_TEXT = {
    "idle": "等待任务",
    "running": "任务执行中",
    "paused": "任务已暂停",
    "planning": "正在理解指令",
    "error": "执行出现错误",
}
ROLE_TEXT = {"current": "当前步骤", "next": "后续步骤", "background": "持续提示"}


@dataclass(frozen=True)
class ObjectSummary:
    object_id: str
    status: str
    details: tuple[str, ...]

    @property
    def markdown(self) -> str:
        return "\n\n".join((f"**{self.object_id}**　{self.status}", *self.details))


def object_summary(spec: SceneSpec, state: Session, object_id: str) -> ObjectSummary:
    """Describe confirmed work and pending work without changing task identity."""
    if state.scene_id != spec.scene_id:
        raise ValueError("presentation scene and session must agree")
    objects = {obj.object_id: obj for obj in spec.objects}
    if object_id not in objects:
        raise KeyError(object_id)
    placements = {}
    for task in state.completed:
        cue = task.semantic
        if cue.action in ("insert", "assemble"):
            placements[cue.target_id] = cue.reference_id
    completed = [task for task in state.completed if task.semantic.target_id == object_id]
    queued = [task for task in state.queue if task.semantic.target_id == object_id]
    suspended = [task for group in state.suspended for task in group if task.semantic.target_id == object_id]
    occupants = sorted(source for source, receiver in placements.items() if receiver == object_id)
    details = []
    if object_id in placements:
        details.append(f"已确认放置到 {placements[object_id]}")
    if occupants:
        details.append("已接收对象　" + "、".join(occupants))
    if completed:
        details.append("最近确认　" + completed[-1].semantic.instruction)
    for task in queued:
        details.append(ROLE_TEXT[task.semantic.task_role] + "　" + task.semantic.instruction)
    if suspended:
        details.append(f"保留 {len(suspended)} 个挂起步骤")
    if queued:
        first = queued[0].semantic
        status = (
            EXECUTION_TEXT[state.execution] if first.task_role == "current" else ROLE_TEXT[first.task_role]
        )
    elif suspended:
        status = "等待恢复"
    elif occupants:
        status = "已有放置对象"
    elif completed:
        status = "相关步骤已确认"
    else:
        status = "场景对象"
    if not details:
        details.append(objects[object_id].description or objects[object_id].label)
    return ObjectSummary(object_id, status, tuple(details))


def session_status(spec: SceneSpec, state: Session) -> str:
    if state.scene_id != spec.scene_id:
        raise ValueError("presentation scene and session must agree")
    execution = EXECUTION_TEXT[state.execution]
    if state.execution == "idle" and state.suspended:
        execution = "临时步骤已确认，等待恢复原任务"
    elif state.execution == "idle" and state.completed:
        execution = "当前计划已完成"
    return f"**{spec.title}**\n\n{execution}\n\n模型模式 {state.backend_mode}　任务版本 {state.revision}"
