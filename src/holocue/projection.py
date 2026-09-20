"""Deterministic baseline mapping; calibration values are explicitly provenance-tagged."""
from __future__ import annotations
import math
from .models import DisplayCue,DisplayPacket,Pose,SceneSpec,Session
from .spatial import mating_goal,rotate_about

def allocate(weights:list[int],budget:int)->list[int]:
    if budget<0 or any(w<0 for w in weights):raise ValueError('negative budget/weight')
    total=sum(weights)
    if total==0:return [0]*len(weights)
    # Largest-remainder allocation is exact, stable in input order and budget conserving.
    quotients=[budget*w/total for w in weights]
    out=[math.floor(v) for v in quotients]
    order=sorted(range(len(weights)),key=lambda i:(-(quotients[i]-out[i]),i))
    for i in order[:budget-sum(out)]:out[i]+=1
    return out

def packet(s:Session,scene:SceneSpec,policy:dict)->DisplayPacket:
    objects={o.object_id:o for o in scene.objects}
    poses={o.object_id:o.pose.model_copy(deep=True) for o in scene.objects}
    for task in s.completed:
        semantic=task.semantic
        obj=objects[semantic.target_id]
        if semantic.action=='rotate':
            poses[obj.object_id]=rotate_about(poses[obj.object_id],obj.interaction.rotation_axis_local,
                obj.interaction.pivot_local_m,semantic.angle_deg)
        elif semantic.action in ('insert','assemble'):
            reference=objects[semantic.reference_id]
            poses[obj.object_id]=mating_goal(obj,reference,poses[reference.object_id],semantic.action)
    # A target receives its earliest remaining cue. All steps stay in the task queue.
    tasks=[]
    displayed=set()
    for task in s.queue:
        if task.semantic.target_id not in displayed:
            tasks.append(task)
            displayed.add(task.semantic.target_id)
    weights=[t.semantic.priority for t in tasks]
    n=allocate(weights,int(policy['n_budget']))
    calibration=policy['calibration']
    if calibration['kind'] not in ('analytic_preview','illustrative','measured'):
        raise ValueError('Unknown calibration provenance')
    cues=[]
    for t,ni in zip(tasks,n):
        c=t.semantic;obj=objects[c.target_id]
        prof=policy['profiles'][c.depth_requirement]
        goal=None
        if c.reference_id:
            reference=objects[c.reference_id]
            goal=mating_goal(obj,reference,poses[reference.object_id],c.action)
        cues.append(DisplayCue(task_id=t.task_id,target_id=c.target_id,task_role=c.task_role,
            cue_type=c.cue_type,action=c.action,instruction=c.instruction,priority=c.priority,
            depth_requirement=c.depth_requirement,n_gaussians=ni,sigma_value=prof['sigma'],
            sigma_units=calibration['sigma_units'],sigma_profile=prof['name'],pose=poses[obj.object_id],
            goal_pose=goal,angle_deg=c.angle_deg,reference_id=c.reference_id,
            interaction=obj.interaction,cue_extent_m=max(obj.size_m)))
    return DisplayPacket(session_id=s.session_id,scene_id=s.scene_id,revision=s.revision,epoch=s.epoch,
        execution=s.execution,renderer_kind='semantic_preview',
        calibration_id=calibration['id'],budget_total=policy['n_budget'],cues=cues,object_poses=poses)
