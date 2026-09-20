"""Domain, database, mesh and response tests with real implementations and assets.

Task contracts enter at the semantic boundary. No model invocation is represented here.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError
from scipy.spatial.transform import Rotation

from holocue import camera
from holocue.assets import load_asset,resource,world_scene
from holocue.config import root,load_scene,list_scenes,load_policy
from holocue.models import CueSemantic,Decision,Pose,Session,UserMessage
from holocue.projection import packet,allocate
from holocue.response import profile,envelope,splat_arrays,camera_aligned_rgba,local_cue_pool
from holocue.spatial import compose,inverse,matrix,transform_points,trajectory,ActionClock,path_keyframes
from holocue.state import apply_decision,ConflictError
from holocue.store import Store

SCENES=[row['scene_id'] for row in list_scenes()]


def semantic_plan(spec):
    cues=[]
    for index,step in enumerate(spec.task_contract.ordered_steps):
        kind={'rotate':'ring_arrow','insert':'ghost_motion','assemble':'ghost_motion',
              'inspect_back':'highlight','point':'straight_arrow','wait':'label'}[step.action]
        cues.append(CueSemantic(target_id=step.target_id,action=step.action,cue_type=kind,
            task_role='current' if index==0 else 'next',priority=5 if index==0 else 2,
            depth_requirement=step.depth_requirement,instruction=step.action+' '+step.target_id,
            angle_deg=step.angle_deg,reference_id=step.reference_id))
    for oid in spec.task_contract.persistent_targets:
        cues.append(CueSemantic(target_id=oid,action='wait',cue_type='label',task_role='background',
            priority=1,depth_requirement='persistent',instruction='observe '+oid))
    return Decision(operation='replace',assistant_message='执行语义边界测试',cues=cues)


def task_session(spec):
    session=Session(session_id='domain-'+spec.scene_id,scene_id=spec.scene_id,backend_mode='domain_test')
    return apply_decision(session,semantic_plan(spec),spec)


def test_twelve_scenes():
    assert len(SCENES)==12


@pytest.mark.parametrize('scene_id',SCENES)
def test_assets_and_materials(scene_id):
    spec=load_scene(scene_id)
    assert spec.task_contract is not None
    for obj in [*spec.objects,*spec.environment]:
        scene=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
        assert len(scene.geometry)>0
        for mesh in scene.geometry.values():
            assert np.isfinite(mesh.vertices).all()
            assert len(mesh.faces)>0
            assert hasattr(mesh.visual,'material')
        assert (scene.extents>0).all()


@pytest.mark.parametrize('scene_id',SCENES)
@pytest.mark.parametrize('aspect',[.72,1.,16/9,2.1])
def test_perspective_camera_bounds(scene_id,aspect):
    spec=load_scene(scene_id)
    points=[]
    for obj in spec.objects:
        local=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
        points.extend(transform_points(obj.pose,camera.corners(local.bounds)))
    points=np.asarray(points)
    direction=np.asarray(spec.camera_position_m)-spec.camera_look_at_m
    position,look=camera.fit(points,direction,aspect=aspect)
    projected,depth=camera.project(points,position,look,aspect=aspect)
    assert np.abs(projected).max()<=.860001
    assert depth.min()>0
    step=spec.task_contract.ordered_steps[0]
    active=next(o for o in spec.objects if o.object_id==step.target_id)
    mesh=load_asset(str(resource(root(),active.asset)),spec.asset_axes)
    position,look,up=camera.detail_view(active,active.pose,mesh.bounds,direction,step.action,aspect=aspect)
    local_points=(np.asarray([active.interaction.inspect_point_local_m])
                  if step.action=='inspect_back' else camera.corners(mesh.bounds))
    points=transform_points(active.pose,local_points)
    projected,depth=camera.project(points,position,look,aspect=aspect,up=up)
    assert np.abs(projected).max()<=.860001
    assert depth.min()>0


@pytest.mark.parametrize('scene_id',SCENES)
def test_interruption_identity_and_completion(scene_id):
    spec=load_scene(scene_id)
    state=task_session(spec)
    original=[t.model_dump() for t in state.queue]
    current=state.queue[0]
    pause=Decision(operation='pause',assistant_message='暂停动作')
    resume=Decision(operation='resume',assistant_message='恢复任务')
    state=apply_decision(state,pause,spec)
    assert state.execution=='paused'
    state=apply_decision(state,resume,spec)
    target=spec.task_contract.interrupt_target
    interrupt=Decision(operation='interrupt',assistant_message='执行临时检查',cues=[
        CueSemantic(target_id=target,action='inspect_back',cue_type='highlight',task_role='current',
            priority=5,depth_requirement='persistent',instruction='temporary inspection '+target)])
    state=apply_decision(state,interrupt,spec)
    assert state.suspended[-1][0].task_id==current.task_id
    temporary_id=state.queue[0].task_id
    state=apply_decision(state,Decision(operation='complete',assistant_message='确认临时检查完成'),spec)
    assert state.completed[-1].task_id==temporary_id
    state=apply_decision(state,resume,spec)
    assert [t.model_dump() for t in state.queue]==original
    while state.queue:
        state=apply_decision(state,Decision(operation='complete',assistant_message='确认步骤完成'),spec)
    assert state.execution=='idle'
    assert len(state.completed)==len(spec.task_contract.ordered_steps)+1


@pytest.mark.parametrize('scene_id',SCENES)
def test_motion_budget_and_final_pose(scene_id):
    spec=load_scene(scene_id)
    state=task_session(spec)
    while state.queue:
        display=packet(state,spec,load_policy())
        assert sum(c.n_gaussians for c in display.cues)==display.budget_total
        assert len({c.target_id for c in display.cues})==len(display.cues)
        cue=display.cues[0]
        samples=[trajectory(cue,float(t)) for t in np.linspace(0,cue.interaction.duration_s,101)]
        assert np.allclose(matrix(samples[0]),matrix(cue.pose),atol=1e-7)
        assert np.allclose(matrix(trajectory(cue,100.)),matrix(samples[-1]),atol=1e-7)
        if cue.action in ('insert','assemble'):
            assert np.allclose(matrix(samples[-1]),matrix(cue.goal_pose),atol=1e-7)
            source=next(o for o in spec.objects if o.object_id==cue.target_id)
            target=next(o for o in spec.objects if o.object_id==cue.reference_id)
            anchor='insertion' if cue.action=='insert' else 'placement'
            receiver=target.frames[anchor] if anchor in target.frames else Pose(position_m=target.anchors[anchor])
            left=compose(cue.goal_pose,source.interaction.mating_pose)
            right=compose(display.object_poses[target.object_id],receiver)
            assert np.allclose(matrix(left),matrix(right),atol=1e-7)
        before=samples[-1]
        state=apply_decision(state,Decision(operation='complete',assistant_message='确认完成'),spec)
        after=packet(state,spec,load_policy()).object_poses[cue.target_id]
        assert np.allclose(matrix(before),matrix(after),atol=1e-7)


@pytest.mark.parametrize('scene_id',SCENES)
def test_sqlite_recovery_and_revision(scene_id,tmp_path):
    spec=load_scene(scene_id)
    store=Store(tmp_path/(scene_id+'.sqlite'))
    state=store.create(scene_id,'domain_test')
    msg=UserMessage(text='semantic boundary transaction',request_id='request-1',expected_revision=0)
    job,planning,created=store.begin(state.session_id,msg)
    assert created
    committed=store.commit(job['id'],semantic_plan(spec),spec,{'source':'domain_test'})
    restored=Store(store.path)
    assert restored.get(state.session_id)==committed
    restored.recover()
    recovered=restored.get(state.session_id)
    assert recovered.execution=='paused'
    assert [t.task_id for t in recovered.queue]==[t.task_id for t in committed.queue]
    with pytest.raises(ConflictError):
        restored.manual(state.session_id,0,Decision(operation='complete',assistant_message='确认'),spec)
    old_job,old_state,_=restored.begin(state.session_id,UserMessage(text='old',request_id='old',expected_revision=recovered.revision))
    new_job,_,_=restored.begin(state.session_id,UserMessage(text='new',request_id='new',expected_revision=old_state.revision))
    assert restored.commit(old_job['id'],semantic_plan(spec),spec,{'source':'domain_test'}) is None
    assert restored.commit(new_job['id'],semantic_plan(spec),spec,{'source':'domain_test'}) is not None


@pytest.mark.parametrize('scene_id',SCENES)
def test_splat_arrays_real_asset_pool(scene_id):
    spec=load_scene(scene_id)
    display=packet(task_session(spec),spec,load_policy())
    for cue in display.cues:
        args=splat_arrays(spec,cue,cue.pose,spec.camera_position_m,spec.camera_look_at_m,1.2)
        centers,covariances,rgbs,opacity=args
        assert len(centers)==cue.n_gaussians
        assert centers.shape==(cue.n_gaussians,3)
        assert covariances.shape==(cue.n_gaussians,3,3)
        assert np.linalg.eigvalsh(covariances).min()>0
        assert np.isfinite(centers).all()
        assert np.isfinite(covariances).all()
        assert (opacity>=0).all() and (opacity<=1).all()
        assert rgbs.shape==(cue.n_gaussians,3)
        dark=splat_arrays(spec,cue,cue.pose,spec.camera_position_m,spec.camera_look_at_m,1.2,0.)
        assert np.count_nonzero(dark[3])==0


def test_rotation_about_pivot():
    from holocue.spatial import rotate_about
    pose=Pose(position_m=(.2,.3,.4),wxyz=tuple(Rotation.from_euler('xyz',[.3,.2,.4]).as_quat(scalar_first=True)))
    pivot=(.1,.2,0.)
    result=rotate_about(pose,(1.,0.,0.),pivot,70.)
    assert np.allclose(transform_points(pose,np.asarray([pivot])),transform_points(result,np.asarray([pivot])))
    assert np.allclose(matrix(compose(pose,inverse(pose))),np.eye(4),atol=1e-8)


def test_clock_freezes_and_restores():
    clock=ActionClock()
    assert clock.advance('B',.8,True)==.8
    assert clock.advance('B',5,False)==.8
    assert clock.advance('C',1,True)==1
    assert clock.advance('B',.2,True)==1


def test_axial_response_relationship_and_raster():
    cal=profile()
    narrow,peak_n,z_n=envelope(1.,np.asarray([0.,.3]),cal)
    broad,peak_b,z_b=envelope(2.5,np.asarray([0.,.3]),cal)
    assert z_b/z_n==pytest.approx(2.5**2)
    assert narrow[1]/narrow[0]>broad[1]/broad[0]
    assert peak_n[1]/peak_n[0]<peak_b[1]/peak_b[0]
    assert np.allclose(narrow*narrow*peak_n,broad*broad*peak_b)
    spec=load_scene('control_panel')
    cue=packet(task_session(spec),spec,load_policy()).cues[0]
    pos=(.18,-.35,.44);look=cue.pose.position_m
    focus=float(np.linalg.norm(np.asarray(pos)-look))
    a=splat_arrays(spec,cue,cue.pose,pos,look,focus)
    b=splat_arrays(spec,cue,cue.pose,pos,look,focus+.4)
    image_a=camera_aligned_rgba(a[0],a[1],a[3],a[2],cue.pose,pos,look)
    image_b=camera_aligned_rgba(b[0],b[1],b[3],b[2],cue.pose,pos,look)
    assert np.abs(image_a.astype(float)-image_b).sum()>1000


def test_schema_rejects_unknown_numeric_controls():
    with pytest.raises(ValidationError):
        CueSemantic(target_id='B',action='rotate',cue_type='ring_arrow',task_role='current',priority=5,
                    depth_requirement='precise',instruction='rotate',angle_deg=30,n_gaussians=6000)
    with pytest.raises(ValidationError):
        Pose(wxyz=(1.,1.,0.,0.))


@pytest.mark.parametrize('budget',[0,1,3,17,6000])
def test_exact_budget(budget):
    result=allocate([5,2,1],budget)
    assert sum(result)==budget
    assert all(isinstance(n,int) and n>=0 for n in result)
