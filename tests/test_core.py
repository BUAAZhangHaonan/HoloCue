import asyncio,importlib.util,json,math,sys
from pathlib import Path
import numpy as np
import pytest
from pydantic import ValidationError
from holocue.config import root,load_scene,load_policy,list_scenes
from holocue.models import Decision,DisplayCue,RenderHints,SceneSpec,Session,UserMessage,Pose
from holocue.state import apply_decision,validate_decision,DomainError,ConflictError
from holocue.projection import allocate,packet
from holocue.store import Store
from holocue.geometry import primitive_pool,quaternion_matrix,display_pose
from holocue.provider import ReplayPlanner,OpenAICompatiblePlanner
from holocue.service import Service
from holocue.adapters import require_optical_calibration

FIX=json.loads((root()/'examples/replay.json').read_text())
def decision(i=0):return Decision.model_validate(FIX[i]['decision'])
def session():return Session(session_id='s',scene_id='control_panel',backend_mode='replay')
def message(text='x',rid='req',revision=0):return UserMessage(text=text,request_id=rid,expected_revision=revision)

def test_all_scenes_load():
    # The first three shipped scenes stay loadable; later kits (docs/09, docs/10) add configs, so only require that core.
    assert len(list_scenes())>=3
    for s in list_scenes():
        scene=load_scene(s['scene_id'])
        for obj in scene.objects:assert (root()/obj.asset).is_file()

@pytest.mark.parametrize('field',['sigma','N','n_gaussians','position_m'])
def test_llm_cannot_output_physical_parameters(field):
    x=decision().model_dump();x['cues'][0][field]=12
    with pytest.raises(ValidationError):Decision.model_validate(x)

def test_invalid_quaternion():
    with pytest.raises(ValidationError):Pose(wxyz=(2,0,0,0))

@pytest.mark.parametrize('weights,budget', [([5,2],6000),([1,1,1],10),([0,5,0],14),([5],0)])
def test_exact_budget(weights,budget):
    n=allocate(weights,budget)
    assert sum(n)==budget and all(x>=0 for x in n)
    for i,w in enumerate(weights):
        if not w:assert n[i]==0

def test_empty_budget():assert allocate([0,0],12)==[0,0] and allocate([],10)==[]

def test_negative_budget():
    with pytest.raises(ValueError):allocate([-1,2],10)

def test_interrupt_preserves_parameters_and_resume():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene)
    original=s.queue[0].model_dump()
    s=apply_decision(s,decision(1),scene)
    assert s.queue[0].semantic.target_id=='C' and len(s.suspended)==1
    assert s.suspended[0][0].model_dump()==original
    s=apply_decision(s,Decision(operation='complete',assistant_message='已确认'),scene)
    s=apply_decision(s,decision(2),scene)
    assert s.queue[0].model_dump()==original
    assert s.queue[0].semantic.angle_deg==30

def test_cannot_drop_temporary_task_by_resuming():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene);s=apply_decision(s,decision(1),scene)
    with pytest.raises(DomainError):apply_decision(s,decision(2),scene)

def test_nested_interrupt_stack():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene)
    s=apply_decision(s,decision(1),scene)
    x=decision(1).model_dump();x['cues'][0]['target_id']='A';d=Decision.model_validate(x)
    s=apply_decision(s,d,scene)
    assert len(s.suspended)==2
    s=apply_decision(s,Decision(operation='complete',assistant_message='已完成'),scene)
    s=apply_decision(s,decision(2),scene)
    assert s.queue[0].semantic.target_id=='C'

def test_unknown_target_is_rejected():
    x=decision().model_dump();x['cues'][0]['target_id']='Z'
    with pytest.raises(DomainError):validate_decision(Decision.model_validate(x),load_scene('control_panel'))

def test_missing_rotation_angle():
    x=decision().model_dump();x['cues'][0]['angle_deg']=None
    with pytest.raises(ValidationError):Decision.model_validate(x)

def test_unsupported_action():
    x=decision().model_dump();x['cues'][0]['target_id']='C';x['cues']=x['cues'][:1]
    with pytest.raises(DomainError):validate_decision(Decision.model_validate(x),load_scene('control_panel'))

def test_optical_provenance_guard():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene)
    p=packet(s,scene,load_policy())
    assert sum(c.n_gaussians for c in p.cues)==6000
    assert p.cues[0].sigma_units=='relative'
    with pytest.raises(ValueError):require_optical_calibration(p)

def test_n_changes_independent_from_depth_profile():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene)
    s.queue[0].semantic.priority=2
    p=packet(s,scene,load_policy())
    assert p.cues[0].n_gaussians==p.cues[1].n_gaussians
    assert p.cues[0].sigma_value!=p.cues[1].sigma_value

def test_nested_pool():
    a=primitive_pool('ring_arrow');b=primitive_pool('ring_arrow')
    np.testing.assert_array_equal(a,b)
    assert a.shape==(8192,3) and np.isfinite(a).all()
    np.testing.assert_array_equal(a[:1000],b[:2000][:1000])

def test_pose_and_animation_does_not_mutate_state():
    scene=load_scene('connector');s=Session(session_id='s',scene_id='connector',backend_mode='replay')
    s=apply_decision(s,decision(3),scene);p=packet(s,scene,load_policy());before=s.model_dump_json()
    start,_=display_pose(p.cues[0],0,True);end,_=display_pose(p.cues[0],2,True)
    assert start!=end and s.model_dump_json()==before and len(s.completed)==0

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'state.sqlite')

def test_store_duplicate_is_idempotent(store):
    s=store.create('control_panel','replay');j,_,new=store.begin(s.session_id,message())
    j2,_,new2=store.begin(s.session_id,message())
    assert j['id']==j2['id'] and new and not new2
    with pytest.raises(ConflictError):store.begin(s.session_id,message(text='changed'))

def test_stale_revision_rejected(store):
    s=store.create('control_panel','replay');store.begin(s.session_id,message())
    with pytest.raises(ConflictError):store.begin(s.session_id,message(rid='other'))

def test_late_response_cannot_commit(store):
    s=store.create('control_panel','replay');j,s1,_=store.begin(s.session_id,message())
    j2,s2,_=store.begin(s.session_id,message(rid='r2',revision=s1.revision))
    assert store.commit(j['id'],decision(),load_scene(s.scene_id),{}) is None
    out=store.commit(j2['id'],decision(1),load_scene(s.scene_id),{})
    assert out.queue[0].semantic.target_id=='C'

def test_manual_pause_invalidates_inflight_job(store):
    s=store.create('control_panel','replay');j,s1,_=store.begin(s.session_id,message())
    store.manual(s.session_id,s1.revision,Decision(operation='pause',assistant_message='暂停'),load_scene(s.scene_id))
    assert store.commit(j['id'],decision(),load_scene(s.scene_id),{}) is None
    assert store.get(s.session_id).execution=='paused'

def test_recovery_preserves_tasks_and_pauses(store):
    s=store.create('control_panel','replay');j,s1,_=store.begin(s.session_id,message())
    out=store.commit(j['id'],decision(),load_scene(s.scene_id),{})
    reopened=Store(store.path);reopened.recover();saved=reopened.get(s.session_id)
    assert saved.queue==out.queue and saved.execution=='paused' and saved.revision>out.revision

def test_replay_unknown_input_is_explicit_error(store):
    async def run():
        svc=Service(store,ReplayPlanner(root()/'examples/replay.json'));s=svc.create('control_panel')
        j=await svc.submit(s.session_id,message(text='This is not a fixture'))
        await asyncio.gather(*svc.tasks.values())
        assert store.job(j['id'])['status']=='error'
        assert store.get(s.session_id).backend_mode=='replay'
        await svc.close()
    asyncio.run(run())

def test_service_full_replay(store):
    async def run():
        svc=Service(store,ReplayPlanner(root()/'examples/replay.json'));s=svc.create('control_panel')
        j=await svc.submit(s.session_id,message(text=FIX[0]['input']))
        await asyncio.gather(*svc.tasks.values())
        assert store.job(j['id'])['status']=='done'
        assert svc.display(s.session_id).cues[0].target_id=='B'
        await svc.close()
    asyncio.run(run())

def test_provider_posts_strict_schema_and_disables_thinking(monkeypatch):
    import httpx
    actual=httpx.AsyncClient;captured={}
    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':decision().model_dump_json()}}],'usage':{'total_tokens':20}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(handler),**kw))
    d,trace=asyncio.run(OpenAICompatiblePlanner().decide(session(),load_scene('control_panel'),message()))
    assert captured['chat_template_kwargs']['enable_thinking'] is False
    assert captured['response_format']['json_schema']['strict']
    assert d.operation=='replace' and trace['backend_mode']=='live'

def test_provider_history_excludes_current_instruction(monkeypatch):
    """Store.begin() appends the current text to history; the planner context must not repeat it,
    otherwise the live model reads a first-turn session as a continuation and answers resume."""
    import httpx
    actual=httpx.AsyncClient;captured={}
    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':decision().model_dump_json()}}],'usage':{'total_tokens':20}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(handler),**kw))
    s=session();s.history=[{'role':'user','content':'把 B 逆时针转 30 度，接着检查 C 的背面。'}]
    asyncio.run(OpenAICompatiblePlanner().decide(s,load_scene('control_panel'),message(text='把 B 逆时针转 30 度，接着检查 C 的背面。')))
    context=json.loads(captured['messages'][1]['content'][0]['text'])
    assert context['history']==[]
    assert context['user_instruction']=='把 B 逆时针转 30 度，接着检查 C 的背面。'

def test_provider_invalid_json_is_not_repaired(monkeypatch):
    import httpx
    actual=httpx.AsyncClient
    def handler(r):return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'```json\n{}\n```'}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(transport=httpx.MockTransport(handler),**kw))
    from holocue.provider import PlannerError
    with pytest.raises(PlannerError) as caught:
        asyncio.run(OpenAICompatiblePlanner().decide(session(),load_scene('control_panel'),message()))
    assert caught.value.trace['raw_response']=='```json\n{}\n```'
    assert caught.value.trace['http_status']==200

def test_api_smoke_and_revisions(tmp_path):
    from fastapi.testclient import TestClient
    from holocue.api import create_app
    svc=Service(Store(tmp_path/'s.sqlite'),ReplayPlanner(root()/'examples/replay.json'))
    with TestClient(create_app(svc)) as client:
        assert client.get('/health').json()['backend_mode']=='replay'
        s=client.post('/api/v1/sessions',json={'scene_id':'control_panel'}).json()
        body={'text':FIX[0]['input'],'request_id':'api1','expected_revision':0}
        r=client.post(f"/api/v1/sessions/{s['session_id']}/messages",json=body)
        assert r.status_code==202
        import time
        for _ in range(50):
            j=client.get('/api/v1/jobs/'+r.json()['id']).json()
            if j['status']!='planning':break
            time.sleep(.01)
        assert j['status']=='done'
        p=client.get(f"/api/v1/sessions/{s['session_id']}/display").json()
        assert p['budget_total']==6000 and p['cues'][0]['target_id']=='B'
        r=client.post(f"/api/v1/sessions/{s['session_id']}/control/pause",json={'expected_revision':0})
        assert r.status_code==409

def test_resource_gpu_allowlist():
    spec=importlib.util.spec_from_file_location('guard',root()/'scripts/guard/resource_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert m.parse_selection('1,2')==[1,2] and m.parse_selection('')==[]
    for value in ['0','1,3','all','1,1','-1']:
        with pytest.raises(ValueError):m.parse_selection(value)

def test_asset_glbs_are_readable():
    import trimesh
    files=list((root()/'assets/meshes/common').glob('*.glb'));assert len(files)==9
    for p in files:
        m=trimesh.load(p,force='mesh');assert len(m.vertices)>0 and len(m.faces)>0
        assert np.isfinite(m.vertices).all()

@pytest.mark.integration
def test_langgraph_integration():
    pytest.importorskip('langgraph')
    from holocue.graph import GraphPlanner
    planner=GraphPlanner(ReplayPlanner(root()/'examples/replay.json'))
    d,_=asyncio.run(planner.decide(session(),load_scene('control_panel'),message(text=FIX[0]['input'])))
    assert d.operation=='replace'


def test_background_cannot_precede_next_step():
    x=decision().model_dump()
    background=x['cues'][1].copy();background['task_role']='background';background['target_id']='A'
    x['cues'].insert(1,background)
    with pytest.raises(ValidationError): Decision.model_validate(x)

def test_measured_parameters_do_not_claim_optical_execution():
    scene=load_scene('control_panel');s=apply_decision(session(),decision(),scene)
    policy=load_policy();policy['calibration']={'id':'lab-profile','kind':'measured','sigma_units':'m'}
    assert packet(s,scene,policy).renderer_kind=='semantic_preview'

def scene_with_environment():
    x=json.loads((root()/'scenes/control_panel/scene.json').read_text(encoding='utf-8'))
    x['environment']=[{'prop_id':'bench_top','asset':'assets/meshes/baseplate.glb','pose':{'position_m':[0,.08,-.012],'wxyz':[1,0,0,0]},'scale_m':[2.,1.6,.02]},
                      {'prop_id':'side_rail','asset':'assets/meshes/brick.glb'}]
    x['render_hints']={'ortho_scale_m':1.4,'grid_extent_m':2.2,'cue_scale':.8,'label_offset_m':.2}
    return x

def test_scene_spec_accepts_environment_and_render_hints():
    s=SceneSpec.model_validate(scene_with_environment())
    assert len(s.objects)==3 and len(s.environment)==2
    assert s.environment[1].pose.wxyz==(1.,0.,0.,0.) and s.environment[1].scale_m==(1.,1.,1.)
    assert (s.render_hints.ortho_scale_m,s.render_hints.grid_extent_m,s.render_hints.cue_scale,s.render_hints.label_offset_m)==(1.4,2.2,.8,.2)

def test_scene_prop_id_pattern_is_enforced():
    x=scene_with_environment();x['environment'][0]['prop_id']='9bench'
    with pytest.raises(ValidationError):SceneSpec.model_validate(x)

def test_environment_prop_ids_must_be_unique():
    x=scene_with_environment();x['environment'][1]['prop_id']=x['environment'][0]['prop_id']
    with pytest.raises(ValidationError):SceneSpec.model_validate(x)

def test_render_hints_defaults_equal_first_scene_constants():
    assert (RenderHints().ortho_scale_m,RenderHints().grid_extent_m,RenderHints().cue_scale,RenderHints().label_offset_m)==(.91,1.,1.,.12)
    assert RenderHints().fit_camera is False
    first=load_scene('control_panel');assert first.render_hints==RenderHints() and first.environment==[]

def test_camera_fit_backsoff_along_axis_and_preserves_default():
    from holocue.viewer import Viewer
    import numpy as np
    spec=load_scene('control_panel')
    # Default (fit_camera False): JSON camera returned untouched.
    pos,look=Viewer._camera(object.__new__(Viewer),spec,[])
    assert list(pos)==list(spec.camera_position_m) and list(look)==list(spec.camera_look_at_m)
    # fit_camera True: same axis, distance = radius/tan(25°)/0.7 from look_at.
    spec=spec.model_copy(deep=True);spec.render_hints.fit_camera=True
    bounds=[(np.array([-.3,-.3,0.]),np.array([.3,.2,.1]))]
    pos,look=Viewer._camera(object.__new__(Viewer),spec,bounds)
    import math
    direction=np.asarray(spec.camera_position_m)-np.asarray(spec.camera_look_at_m)
    expect=np.asarray(spec.camera_look_at_m)+direction/np.linalg.norm(direction)*(math.hypot(.6,.5,.1)/2/math.tan(math.radians(25.))/.7)
    assert np.allclose(pos,expect) and np.allclose(look,spec.camera_look_at_m)

def test_display_pose_rotate_end_value_and_sign_about_z():
    c=DisplayCue(task_id='t',target_id='B',task_role='current',cue_type='ring_arrow',action='rotate',instruction='转 90 度',priority=3,depth_requirement='precise',n_gaussians=10,sigma_value=.01,sigma_units='relative',sigma_profile='fine',pose=Pose(),angle_deg=90)
    _,q=display_pose(c,2.,True)
    np.testing.assert_allclose(q,(math.cos(math.pi/4),0.,0.,math.sin(math.pi/4)),atol=1e-12)

def test_display_pose_inspect_back_ends_at_180():
    c=DisplayCue(task_id='t',target_id='C',task_role='current',cue_type='ghost_motion',action='inspect_back',instruction='查背面',priority=3,depth_requirement='precise',n_gaussians=10,sigma_value=.01,sigma_units='relative',sigma_profile='fine',pose=Pose())
    _,q=display_pose(c,2.,True)
    np.testing.assert_allclose(q,(math.cos(math.pi/2),0.,0.,math.sin(math.pi/2)),atol=1e-12)

def test_environment_props_are_not_planner_objects():
    scene=SceneSpec.model_validate(scene_with_environment())
    assert len(scene.objects)==3  # environment does not extend the planner-visible object list
    x=decision().model_dump();x['cues'][0]['target_id']='bench_top'
    with pytest.raises(DomainError) as caught:validate_decision(Decision.model_validate(x),scene)
    assert 'Unknown object' in str(caught.value)
