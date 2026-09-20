"""Real semantic, persistence and camera-boundary tests without provider substitutes."""
import hashlib
import json

import numpy as np
import pytest

from holocue.assets import load_asset,resource
from holocue.bridge import atomic_json,frame
from holocue.camera import corners,fit,project,workspace_points
from holocue.config import load_scene,root,list_scenes,scene_fingerprint,load_policy
from holocue.models import CueSemantic,Decision,Session
from holocue.projection import packet
from holocue.spatial import ActionClock,trajectory,compose
from holocue.state import apply_decision
from holocue.store import Store
from holocue.versioning import VersionGate

SCENES=[s['scene_id'] for s in list_scenes()]


def test_acknowledged_command_blocks_older_snapshot():
    gate=VersionGate()
    assert gate.admit(2,1)
    gate.require(3,2)
    assert not gate.admit(2,1)
    assert not gate.current(2,1)
    assert gate.admit(3,2)
    assert gate.admit(4,2)
    assert not gate.admit(3,2)
    assert gate.current(4,2)


def test_required_imports_are_direct():
    import ast
    for path in (root()/'src/holocue').glob('*.py'):
        parsed=ast.parse(path.read_text())
        for node in ast.walk(parsed):
            if isinstance(node,ast.Try):
                for child in node.body:
                    assert not any(isinstance(x,(ast.Import,ast.ImportFrom)) for x in ast.walk(child)),path


@pytest.mark.parametrize('scene_id',SCENES)
def test_scene_fingerprint_persists(scene_id,tmp_path):
    spec=load_scene(scene_id);value=scene_fingerprint(spec)
    assert len(value)==64
    store=Store(tmp_path/'state.sqlite')
    state=store.create(scene_id,'domain_test',value)
    reread=Store(tmp_path/'state.sqlite').get(state.session_id)
    assert reread.scene_fingerprint==value


@pytest.mark.parametrize('scene_id',SCENES)
def test_declared_workspace_fits_portrait_and_wide_views(scene_id):
    spec=load_scene(scene_id);points=workspace_points(spec,np.zeros((0,3)))
    for aspect in (.65,1.,1.6,2.2):
        pos,look=fit(points,np.asarray(spec.camera_position_m)-spec.camera_look_at_m,aspect=aspect)
        xy,depth=project(points,pos,look,aspect=aspect)
        assert np.abs(xy).max()<1
        assert depth.min()>0


def test_shelf_departure_clears_shelf_before_lift():
    spec=load_scene('shelf_picking')
    decision=Decision(operation='replace',assistant_message='移动货物',cues=[CueSemantic(
        target_id='RED',action='assemble',reference_id='BASKET',cue_type='ghost_motion',
        priority=5,task_role='current',depth_requirement='precise',instruction='移动 RED 到 BASKET')])
    state=apply_decision(Session(session_id='departure',scene_id=spec.scene_id,backend_mode='domain_test'),decision,spec)
    cue=packet(state,spec,load_policy()).cues[0]
    from holocue.spatial import path_keyframes
    keys=path_keyframes(cue)
    assert keys[1].position_m[2]==pytest.approx(keys[0].position_m[2])
    parcel=next(o for o in spec.objects if o.object_id=='RED')
    assert keys[1].position_m[1]+parcel.size_m[1]/2<0
    assert keys[2].position_m[2]>keys[1].position_m[2]


def test_bridge_preserves_actual_splat_count_and_zero_brightness(tmp_path):
    spec=load_scene('control_panel')
    decision=Decision(operation='replace',assistant_message='旋转 B',cues=[CueSemantic(
        target_id='B',action='rotate',angle_deg=30,cue_type='ring_arrow',priority=5,
        task_role='current',depth_requirement='precise',instruction='逆时针转动 B 30 度')])
    state=apply_decision(Session(session_id='bridge',scene_id=spec.scene_id,backend_mode='domain_test'),decision,spec)
    display=packet(state,spec,load_policy())
    data=frame(spec,display,ActionClock(),.5,spec.camera_position_m,spec.camera_look_at_m,1.,0.)
    assert len(data['cues'][0]['centers_m'])==6000
    assert max(data['cues'][0]['opacities'])==0
    assert data['rgb_encoding']=='linear_0_1'
    assert np.allclose(data['cues'][0]['rgb'],[.12,.8,.64])
    path=tmp_path/'actual_frame.json';atomic_json(path,data)
    assert json.loads(path.read_text())['epoch']==state.epoch


def test_fixed_actions_reject_reference_ids():
    with pytest.raises(ValueError):
        CueSemantic(target_id='B',action='rotate',reference_id='C',angle_deg=30,
                    cue_type='ring_arrow',priority=5,task_role='current',
                    depth_requirement='precise',instruction='旋转 B')


def test_clockwise_arrow_reverses_the_visible_arrowhead():
    from holocue.response import splat_arrays,basis_from_normal
    spec=load_scene('control_panel')
    semantic=CueSemantic(target_id='B',action='rotate',angle_deg=30,cue_type='ring_arrow',
        priority=5,task_role='current',depth_requirement='precise',instruction='Rotate B')
    state=apply_decision(Session(session_id='direction',scene_id=spec.scene_id,backend_mode='domain_test'),
        Decision(operation='replace',assistant_message='Rotate B',cues=[semantic]),spec)
    cue=packet(state,spec,load_policy()).cues[0]
    positive=splat_arrays(spec,cue,cue.pose,spec.camera_position_m,spec.camera_look_at_m,1.)[0]
    negative=splat_arrays(spec,cue.model_copy(update={'angle_deg':-30}),cue.pose,
                          spec.camera_position_m,spec.camera_look_at_m,1.)[0]
    plane=basis_from_normal(cue.interaction.rotation_axis_local)
    origin=np.asarray(cue.interaction.cue_offset_local_m)
    first=(positive-origin)@plane;second=(negative-origin)@plane
    assert np.allclose(first[:,0],second[:,0],atol=1e-6)
    assert np.allclose(first[:,1],-second[:,1],atol=1e-6)
    assert not np.allclose(positive,negative)
