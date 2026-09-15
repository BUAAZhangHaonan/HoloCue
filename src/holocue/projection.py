"""Deterministic baseline mapping; calibration values are explicitly provenance-tagged."""
from __future__ import annotations
import math
from .models import DisplayCue,DisplayPacket,Pose,SceneSpec,Session

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
    tasks=list(s.queue)
    # A paused frame remains visible; motion is controlled by packet.execution.
    weights=[t.semantic.priority for t in tasks]
    n=allocate(weights,int(policy['n_budget']))
    calibration=policy['calibration']
    if calibration['kind'] not in ('illustrative','measured'):raise ValueError('Unknown calibration provenance')
    cues=[]
    for t,ni in zip(tasks,n):
        c=t.semantic;obj=objects[c.target_id]
        prof=policy['profiles'][c.depth_requirement]
        goal=None
        if c.reference_id:
            reference=objects[c.reference_id]
            local=reference.anchors.get('insertion' if c.action=='insert' else 'placement',(0,0,0))
            # Scene anchors are object-local. Rotate them before translation.
            import numpy as np
            from .geometry import quaternion_matrix
            xyz=quaternion_matrix(reference.pose.wxyz)@np.asarray(local)+reference.pose.position_m
            goal=Pose(position_m=tuple(float(x) for x in xyz),wxyz=reference.pose.wxyz)
        cues.append(DisplayCue(task_id=t.task_id,target_id=c.target_id,task_role=c.task_role,
            cue_type=c.cue_type,action=c.action,instruction=c.instruction,priority=c.priority,
            depth_requirement=c.depth_requirement,n_gaussians=ni,sigma_value=prof['sigma'],
            sigma_units=calibration['sigma_units'],sigma_profile=prof['name'],pose=obj.pose,
            goal_pose=goal,angle_deg=c.angle_deg,reference_id=c.reference_id))
    return DisplayPacket(session_id=s.session_id,scene_id=s.scene_id,revision=s.revision,epoch=s.epoch,
        execution=s.execution,renderer_kind='semantic_preview',
        calibration_id=calibration['id'],budget_total=policy['n_budget'],cues=cues)
