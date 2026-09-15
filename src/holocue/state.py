"""Pure state transitions shared by the server, replay tests, and future display adapters."""
from __future__ import annotations
from uuid import uuid4
from .models import Decision,SceneSpec,Session,Task

class DomainError(ValueError): pass
class ConflictError(DomainError): pass


def validate_decision(d:Decision,scene:SceneSpec)->None:
    objects={o.object_id:o for o in scene.objects}
    for c in d.cues:
        if c.target_id not in objects:raise DomainError(f'Unknown object {c.target_id}')
        if c.action not in objects[c.target_id].capabilities:
            raise DomainError(f'{c.target_id} does not support {c.action}')
        if c.reference_id is not None and c.reference_id not in objects:
            raise DomainError(f'Unknown reference {c.reference_id}')
        if c.reference_id==c.target_id:raise DomainError('target and reference must differ')
        if c.cue_type=='ring_arrow' and c.action!='rotate':
            raise DomainError('ring_arrow requires rotate')
        if c.action=='insert' and 'insertion' not in objects[c.reference_id].anchors:
            raise DomainError('insertion anchor missing in scene manifest')
        if c.action=='assemble' and 'placement' not in objects[c.reference_id].anchors:
            raise DomainError('placement anchor missing in scene manifest')


def _normalize_queue(s:Session)->None:
    # Current/next describes task order, not additional model reasoning.
    for i,t in enumerate(s.queue):
        if t.semantic.task_role!='background':
            t.semantic.task_role='current' if i==0 else 'next'


def apply_decision(s:Session,d:Decision,scene:SceneSpec)->Session:
    validate_decision(d,scene)
    out=s.model_copy(deep=True)
    if d.operation in ('replace','interrupt'):
        if d.operation=='interrupt' and out.queue:
            out.suspended.append(out.queue)
        if d.operation=='replace':
            out.suspended=[]
        out.queue=[Task(task_id=uuid4().hex[:16],semantic=c.model_copy(deep=True)) for c in d.cues]
        out.execution='running'
    elif d.operation=='resume':
        if out.suspended:
            if out.queue:raise DomainError('Complete the temporary task before resuming the suspended plan')
            out.queue=out.suspended.pop()
            out.execution='running' if out.queue else 'idle'
        elif out.queue:
            out.execution='running'
        else:raise DomainError('No paused task to resume')
    elif d.operation=='complete':
        if not out.queue:raise DomainError('No active task to complete')
        out.completed.append(out.queue.pop(0))
        # Background cues are context, never steps that must be "completed".
        if out.queue and all(t.semantic.task_role=='background' for t in out.queue):out.queue=[]
        _normalize_queue(out)
        out.execution='running' if out.queue else 'idle'
    elif d.operation=='pause':
        out.execution='paused'
    elif d.operation=='clarify':
        out.execution='paused'
    out.revision+=1
    out.assistant_message=d.assistant_message
    out.last_error=None
    out.history.append({'role':'assistant','content':d.assistant_message})
    return out
