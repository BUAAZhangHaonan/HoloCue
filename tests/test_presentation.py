"""Operator wording follows actual domain transitions and confirmed geometry."""
import pytest
from holocue.config import load_scene,load_policy
from holocue.models import CueSemantic,Decision,Session
from holocue.presentation import object_summary,session_status
from holocue.projection import packet
from holocue.state import apply_decision


def installation(scene_id,target,receiver):
    spec=load_scene(scene_id)
    state=Session(session_id='presentation-test',scene_id=scene_id,backend_mode='domain_test')
    cue=CueSemantic(target_id=target,reference_id=receiver,action='insert',
        cue_type='ghost_motion',task_role='current',priority=5,depth_requirement='precise',
        instruction=f'将 {target} 装入 {receiver}')
    state=apply_decision(state,Decision(operation='replace',assistant_message='安装步骤',cues=[cue]),spec)
    return spec,state


@pytest.mark.parametrize('sid,source,receiver',[('optical_bench','L1','POST2'),('server_rack','SPARE','SLOT4')])
def test_confirmed_placement_updates_both_objects(sid,source,receiver):
    spec,state=installation(sid,source,receiver)
    before=state.model_dump_json()
    assert '已确认放置到' not in object_summary(spec,state,source).markdown
    assert '已接收对象' not in object_summary(spec,state,receiver).markdown
    assert state.model_dump_json()==before
    state=apply_decision(state,Decision(operation='complete',assistant_message='已确认完成'),spec)
    before=state.model_dump_json()
    assert f'已确认放置到 {receiver}' in object_summary(spec,state,source).markdown
    assert f'已接收对象　{source}' in object_summary(spec,state,receiver).markdown
    assert '待装' not in object_summary(spec,state,source).markdown
    assert '空槽' not in object_summary(spec,state,receiver).markdown
    assert state.model_dump_json()==before
    assert packet(state,spec,load_policy()).object_poses[source]!=next(o.pose for o in spec.objects if o.object_id==source)
    assert '当前计划已完成' in session_status(spec,state)


def test_pause_interrupt_and_resume_keep_task_identity():
    spec,state=installation('optical_bench','L1','POST2')
    original=state.queue[0].model_dump()
    state=apply_decision(state,Decision(operation='pause',assistant_message='暂停'),spec)
    assert object_summary(spec,state,'L1').status=='任务已暂停'
    cue=CueSemantic(target_id='M',action='inspect_back',cue_type='highlight',
        task_role='current',priority=5,depth_requirement='persistent',instruction='临时检查 M')
    state=apply_decision(state,Decision(operation='interrupt',assistant_message='检查镜架',cues=[cue]),spec)
    assert object_summary(spec,state,'L1').status=='等待恢复'
    state=apply_decision(state,Decision(operation='complete',assistant_message='检查完成'),spec)
    assert '等待恢复原任务' in session_status(spec,state)
    state=apply_decision(state,Decision(operation='resume',assistant_message='继续安装'),spec)
    assert state.queue[0].model_dump()==original
    assert object_summary(spec,state,'L1').status=='任务执行中'


def test_unrecognized_or_wrong_scene_is_rejected():
    spec,state=installation('optical_bench','L1','POST2')
    with pytest.raises(KeyError):object_summary(spec,state,'MISSING')
    with pytest.raises(ValueError):object_summary(load_scene('blocks'),state,'A')
