"""Validate real request serialization without generating model responses."""
import base64
import io
import json

from PIL import Image
import pytest
from pydantic import ValidationError

from holocue.config import load_scene,list_scenes,load_policy
from holocue.models import Session,UserMessage,CueSemantic,Task,Decision
from holocue.provider import OpenAICompatiblePlanner,decision_schema,permitted_operations,committed_history,validate_model_decision
from holocue.projection import packet


def test_current_message_occurs_once_and_history_is_preserved():
    text='把 B 逆时针转 30 度。'
    session=Session(session_id='request',scene_id='control_panel',backend_mode='live',
                    history=[{'role':'assistant','content':'请选择任务。'},
                             {'role':'user','content':text}])
    body=OpenAICompatiblePlanner().request_body(session,load_scene('control_panel'),
        UserMessage(text=text,request_id='request',expected_revision=0))
    context=json.loads(body['messages'][1]['content'][0]['text'])
    assert context['history']==[{'role':'assistant','content':'请选择任务。'}]
    assert context['user_instruction']==text
    assert len(session.history)==2
    assert 'ordered_steps' not in context
    assert body['response_format']['json_schema']['strict'] is True


def test_encoded_image_mime_is_validated():
    stream=io.BytesIO()
    Image.new('RGB',(32,32),'white').save(stream,format='PNG')
    msg=UserMessage(text='检查对象。',request_id='image',expected_revision=0,
                    image_base64=base64.b64encode(stream.getvalue()).decode(),image_mime='image/jpeg')
    session=Session(session_id='request',scene_id='control_panel',backend_mode='live')
    with pytest.raises(ValueError,match='MIME'):
        OpenAICompatiblePlanner().request_body(session,load_scene('control_panel'),msg)


def task():
    return Task(task_id='saved-rotation',semantic=CueSemantic(target_id='B',action='rotate',
        cue_type='ring_arrow',task_role='current',priority=3,depth_requirement='precise',
        instruction='逆时针转动三十度',angle_deg=30))


@pytest.mark.parametrize('has_queue,has_suspended,allowed',[
    (False,False,{'replace','pause','clarify'}),
    (True,False,{'replace','interrupt','complete','pause','resume','clarify'}),
    (True,True,{'replace','interrupt','complete','pause','clarify'}),
    (False,True,{'replace','interrupt','pause','resume','clarify'}),
])
def test_decoding_operations_follow_persisted_queue_not_planning_status(has_queue,has_suspended,allowed):
    state=Session(session_id='schema',scene_id='control_panel',backend_mode='live',execution='planning',
        queue=[task()] if has_queue else [],suspended=[[task()]] if has_suspended else [])
    assert set(permitted_operations(state))==allowed
    schema=decision_schema(state,load_scene(state.scene_id))
    exposed={operation for branch in schema['anyOf']
             for operation in branch['properties']['operation']['enum']}
    assert exposed==allowed
    assert all(branch['additionalProperties'] is False and 'cues' in branch['required']
               for branch in schema['anyOf'])


def test_decoder_rejects_all_next_roles_and_empty_plan_without_rewriting():
    state=Session(session_id='schema',scene_id='control_panel',backend_mode='live')
    schema=decision_schema(state,load_scene(state.scene_id))
    plan,control,clarification=schema['anyOf']
    array=plan['properties']['cues']
    assert array['minItems']==1 and array['maxItems']==8
    current=schema['$defs'][array['prefixItems'][0]['$ref'].split('/')[-1]]['anyOf']
    following=schema['$defs'][array['items']['$ref'].split('/')[-1]]['anyOf']
    assert all(cue['properties']['task_role']['enum']==['current'] for cue in current)
    assert all(cue['properties']['priority']['minimum']==1 for cue in current)
    assert {tuple(cue['properties']['task_role']['enum']) for cue in following}=={('next',),('background',)}
    assert control['properties']['cues']['maxItems']==0
    first=task().semantic.model_dump()
    next_step={**first,'target_id':'A','task_role':'next'}
    data={'operation':'replace','assistant_message':'按顺序操作','cues':[first,next_step]}
    assert Decision.model_validate(data).cues[0].task_role=='current'
    for invalid_cues in ([],[next_step],[next_step,next_step],[first,first]):
        with pytest.raises(ValidationError):
            Decision.model_validate({**data,'cues':invalid_cues})
    zero_priority={**first,'priority':0}
    with pytest.raises(ValidationError):
        Decision.model_validate({**data,'cues':[zero_priority]})
    with pytest.raises(ValidationError):
        Decision.model_validate({**data,'operation':'pause'})
    assert Decision.model_validate({**data,'operation':'pause','cues':[]}).cues==[]
    assert first['task_role']=='current' and next_step['task_role']=='next'


def test_request_exposes_empty_task_state_without_leaking_expected_plan():
    state=Session(session_id='initial',scene_id='dig_site',backend_mode='live',execution='planning')
    spec=load_scene('dig_site')
    body=OpenAICompatiblePlanner().request_body(state,spec,
        UserMessage(text=spec.initial_instruction,request_id='initial',expected_revision=0))
    context=json.loads(body['messages'][1]['content'][0]['text'])
    assert context['task_state']=='empty'
    assert context['permitted_operations']==['replace','pause','clarify']
    assert context['queue']==context['suspended']==[]
    assert 'ordered_steps' not in context and 'persistent_targets' not in context
    assert body['temperature']==.2 and body['top_p']==.8 and body['max_tokens']==1600
    schema=body['response_format']['json_schema']['schema']
    assert schema['$defs']['CueSemantic']==Decision.model_json_schema()['$defs']['CueSemantic']


@pytest.mark.parametrize('execution',['paused','error','running','planning'])
def test_replacement_remains_available_in_every_execution_state(execution):
    state=Session(session_id='repair',scene_id='control_panel',backend_mode='live',
        execution=execution,queue=[task()],suspended=[[task()]])
    assert 'replace' in permitted_operations(state)


@pytest.mark.parametrize('scene_id',[scene['scene_id'] for scene in list_scenes()])
def test_decoding_requires_structured_action_parameters_not_instruction_only(scene_id):
    state=Session(session_id='schema',scene_id=scene_id,backend_mode='live')
    scene=load_scene(scene_id)
    schema=decision_schema(state,scene)
    for definition in ('CurrentCue','FollowingCue'):
        by_action={cue['properties']['action']['const']:cue for cue in schema['$defs'][definition]['anyOf']}
        assert set(by_action)=={action for obj in scene.objects for action in obj.capabilities}
        for action,cue in by_action.items():
            assert set(cue['properties']['target_id']['enum'])=={
                obj.object_id for obj in scene.objects if action in obj.capabilities}
            assert 'angle_deg' in cue['required'] and 'reference_id' in cue['required']
            angle=cue['properties']['angle_deg']
            reference=cue['properties']['reference_id']
            assert angle['type']==('number' if action=='rotate' else 'null')
            assert reference['type']==('string' if action in ('insert','assemble') else 'null')
        if 'rotate' in by_action:
            assert by_action['rotate']['properties']['cue_type']['enum']==['ring_arrow']
        if 'insert' in by_action:
            assert by_action['insert']['properties']['cue_type']['enum']==['ghost_motion']


def test_background_knob_label_uses_supported_point_not_unsupported_wait():
    scene=load_scene('control_panel')
    state=Session(session_id='label',scene_id=scene.scene_id,backend_mode='live')
    schema=decision_schema(state,scene)
    branches=schema['$defs']['FollowingCue']['anyOf']
    permitted=[cue for cue in branches if 'B' in cue['properties']['target_id']['enum']]
    assert {cue['properties']['action']['const'] for cue in permitted}=={'point','rotate'}
    point=next(cue for cue in permitted if cue['properties']['action']['const']=='point'
               and cue['properties']['task_role']['enum']==['background'])
    assert 'label' in point['properties']['cue_type']['enum']
    assert 'background' in point['properties']['task_role']['enum']


def test_decoder_places_executable_decision_before_the_nullable_question_field():
    scene=load_scene('control_panel')
    state=Session(session_id='ordering',scene_id=scene.scene_id,backend_mode='live')
    for branch in decision_schema(state,scene)['anyOf']:
        assert list(branch['properties'])==['operation','cues','assistant_message']
        assert branch['required']==['operation','cues','assistant_message']


@pytest.mark.parametrize('scene_id',[scene['scene_id'] for scene in list_scenes()])
def test_new_plan_background_and_actionable_steps_require_positive_weights(scene_id):
    scene=load_scene(scene_id)
    state=Session(session_id='visible',scene_id=scene_id,backend_mode='live')
    following=decision_schema(state,scene)['$defs']['FollowingCue']['anyOf']
    for cue in following:
        assert cue['properties']['priority']['minimum']==1


def test_legacy_zero_next_remains_readable_and_keeps_zero_budget():
    scene=load_scene('dig_site')
    cues=[CueSemantic(target_id='POT3',action='inspect_back',cue_type='highlight',
            task_role='current',priority=1,depth_requirement='precise',instruction='检查内壁'),
          CueSemantic(target_id='FLAG',action='assemble',reference_id='BONE',cue_type='ghost_motion',
            task_role='next',priority=0,depth_requirement='precise',instruction='随后放置标记'),
          CueSemantic(target_id='STAY',action='wait',cue_type='label',
            task_role='background',priority=1,depth_requirement='persistent',instruction='保留测站提示')]
    state=Session(session_id='visible',scene_id=scene.scene_id,backend_mode='domain_test',
                  queue=[Task(task_id=f'visibility-{i}',semantic=cue) for i,cue in enumerate(cues)])
    display=packet(state,scene,load_policy())
    counts={cue.target_id:cue.n_gaussians for cue in display.cues}
    assert counts=={'POT3':3000,'FLAG':0,'STAY':3000}
    assert sum(counts.values())==display.budget_total==6000


def test_superseded_uncommitted_request_cannot_become_latest_model_instruction():
    previous_user={'role':'user','content':'旋转 B 三十度。'}
    previous_assistant={'role':'assistant','content':'已设置旋转任务。'}
    cancelled={'role':'user','content':'先检查 C，保留 B 的任务。'}
    latest={'role':'user','content':'把 B 逆时针转三十度，然后检查 C。'}
    state=Session(session_id='cancelled',scene_id='control_panel',backend_mode='live',
        history=[previous_user,previous_assistant,cancelled,latest],execution='planning')
    before=state.model_dump_json()
    body=OpenAICompatiblePlanner().request_body(state,load_scene('control_panel'),
        UserMessage(text=latest['content'],request_id='new',expected_revision=0))
    context=json.loads(body['messages'][1]['content'][0]['text'])
    assert context['history']==[previous_user,previous_assistant]
    assert context['user_instruction']==latest['content']
    assert state.model_dump_json()==before


def test_history_keeps_the_committed_request_after_an_earlier_superseded_request():
    cancelled={'role':'user','content':'已被替代的请求。'}
    accepted={'role':'user','content':'最终提交的请求。'}
    reply={'role':'assistant','content':'已提交最终计划。'}
    state=Session(session_id='history',scene_id='control_panel',backend_mode='live',
        history=[cancelled,accepted,reply])
    assert committed_history(state)==[accepted,reply]


def test_model_schema_separates_real_question_from_absent_narrative():
    state=Session(session_id='question',scene_id='control_panel',backend_mode='domain_test',queue=[task()])
    branches=decision_schema(state,load_scene(state.scene_id))['anyOf']
    for branch in branches:
        operations=branch['properties']['operation']['enum']
        message=branch['properties']['assistant_message']
        if operations==['clarify']:
            assert message=={'type':'string','minLength':1,'maxLength':300}
            assert branch['properties']['cues']['maxItems']==0
        else:
            assert 'clarify' not in operations
            assert message=={'type':'null'}
        assert 'assistant_message' in branch['required']


@pytest.mark.parametrize('operation',['replace','interrupt','pause','resume','complete'])
def test_model_boundary_rejects_prose_without_erasing_it(operation):
    decision=Decision(operation=operation,assistant_message='Domain boundary input: retain this string.',
        cues=[task().semantic] if operation in ('replace','interrupt') else [])
    before=decision.model_dump_json()
    with pytest.raises(ValueError,match='must be null'):
        validate_model_decision(decision)
    assert decision.model_dump_json()==before
    without_narrative=Decision.model_validate({**decision.model_dump(),'assistant_message':None})
    validate_model_decision(without_narrative)
    assert without_narrative.assistant_message is None


@pytest.mark.parametrize('message',[None,'','   '])
def test_clarification_cannot_omit_the_question(message):
    with pytest.raises(ValidationError):
        Decision(operation='clarify',assistant_message=message)


def test_clarification_keeps_the_actual_question():
    question='请指定旋转角度和方向。'
    decision=Decision(operation='clarify',assistant_message=question)
    validate_model_decision(decision)
    assert decision.assistant_message==question
