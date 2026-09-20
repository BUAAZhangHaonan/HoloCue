"""Exact preservation whitelist plus real recess/bore and declared-motion checks."""
from pathlib import Path
import hashlib,json
import numpy as np
import pytest
from holocue import modeling
from holocue.config import root,load_scene
from holocue.assets import load_asset
from panel_optical_geometry import mesh_map,fingerprint,material,cavity_evidence,latch_seat_evidence,bottom_contacts,exterior_evidence,sweep

FIXTURE_DIR=Path(__file__).parent/'fixtures/panel_optical_mounts'
BASELINE=json.loads((FIXTURE_DIR/'baseline.json').read_text())
def find(meshes,suffix):
    found=[m for n,m in meshes.items() if n.endswith(suffix)];assert len(found)==1,(suffix,len(found));return found[0]

@pytest.fixture(scope='module',params=['control_panel','optical_bench','drone_bench'])
def pack(request,tmp_path_factory):
    sid=request.param;directory=tmp_path_factory.mktemp(sid+'_mounts');spec=load_scene(sid);raw={};loaded={};world={};raw_world={}
    for obj in spec.objects:
        assembly=modeling.make_object(obj);path=directory/(obj.object_id+'.glb');assembly.save(path);raw[obj.object_id]=mesh_map(assembly.scene);loaded[obj.object_id]=mesh_map(load_asset(str(path),spec.asset_axes));world.update({obj.object_id+'/'+n:m for n,m in mesh_map(load_asset(str(path),spec.asset_axes),obj.pose).items()});raw_world.update({obj.object_id+'/'+n:m for n,m in mesh_map(assembly.scene,obj.pose).items()})
    assembly=modeling.make_environment(spec);path=directory/'workstation.glb';assembly.save(path);raw['workstation']=mesh_map(assembly.scene);loaded['workstation']=mesh_map(load_asset(str(path),spec.asset_axes));world.update({'workstation/'+n:m for n,m in mesh_map(load_asset(str(path),spec.asset_axes),spec.environment[0].pose).items()});raw_world.update({'workstation/'+n:m for n,m in mesh_map(assembly.scene,spec.environment[0].pose).items()})
    return {'scene_id':sid,'spec':spec,'directory':directory,'raw':raw,'loaded':loaded,'world':world,'raw_world':raw_world}

def test_only_exact_whitelist_changes_geometry_and_all_contracts_survive(pack):
    sid=pack['scene_id'];old=BASELINE['scenes'][sid];spec=pack['spec'];assert spec.model_dump(mode='json')==old['scene_contract']
    for env in (pack['loaded']['workstation'],mesh_map(load_asset(str(root()/spec.environment[0].asset),spec.asset_axes))):
        assert set(env)==set(old['environment_fingerprints'])
        for name,digest in old['environment_fingerprints'].items():
            if name in old['changed_environment_nodes']:
                assert fingerprint(env[name])!=digest
                assert material(env[name])==old['environment_materials'][name]
            else:assert fingerprint(env[name])==digest,name
    for obj in spec.objects:
        expected=old['objects'][obj.object_id]
        lens_nodes=set();original_lens={}
        if sid=='optical_bench' and obj.object_id in ('L1','L2'):
            # The separate lens-seat regression constrains these two changed
            # surfaces, the real blind joint and the unobstructed optical face.
            path=FIXTURE_DIR.parent/'optical_lens_before_seat'/(obj.object_id+'.glb')
            expected_sha={'L1':'dd4236403f6b3cf62516d168f858b544fe7d32fd93d17f08eac6dd09b977230b',
                          'L2':'34ff1c0a6f67d13ed34cdc7bb97e533902c8a0375489b304852c63b63aa8f108'}
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha[obj.object_id]
            original_lens=mesh_map(load_asset(str(path),spec.asset_axes))
            lens_nodes={obj.object_id+'/0000_optic_retainer',obj.object_id+'/0002_mounting_post'}
            for name in lens_nodes:assert fingerprint(original_lens[name])==expected['nodes'][name]
        for actual in (pack['loaded'][obj.object_id],mesh_map(load_asset(str(root()/obj.asset),spec.asset_axes))):
            assert set(actual)==set(expected['nodes'])|set(expected['allowed_added_nodes'])
            for name,digest in expected['nodes'].items():
                if name in lens_nodes:
                    assert fingerprint(actual[name])!=digest,name
                    assert material(actual[name])==material(original_lens[name]),name
                else:assert fingerprint(actual[name])==digest,name

@pytest.mark.parametrize('flavor',['raw_world','world'])
def test_real_blind_cavities_support_original_parts_and_keep_radial_clearance(pack,flavor):
    sid=pack['scene_id'];meshes=pack[flavor];records=[]
    for data in BASELINE['measured_before']:
        if data['scene_id']!=sid:continue
        oid=data['object_id'];centre=data['position']
        if sid in ('control_panel','drone_bench'):
            stock=meshes[data['panel_node']];moving=meshes[data['flange_node']];radius=round(data['flange_radius_max_m'],8);seat=data['flange_bottom']['z'];bottom=data['panel_bottom']['z'];top=data['panel_top']['z']
            if sid=='control_panel':record=cavity_evidence(stock,moving,centre,seat,bottom,top,radius,radius+.00025)
            else:
                old_env=mesh_map(load_asset(str(FIXTURE_DIR/sid/'environment_before.glb'),pack['spec'].asset_axes),pack['spec'].environment[0].pose)
                before=old_env[data['panel_node'].removeprefix('workstation/')]
                record=latch_seat_evidence(stock,before,moving,centre,seat,bottom,top,radius,radius+.00025)
            neck=find(meshes,oid+'/0031_mount_neck');record['flange_to_neck']=bottom_contacts(neck,moving);record['neck_to_grip']=bottom_contacts(meshes[data['grip_node']],neck)
            assert record['residual_floor_thickness_m']>(.03675 if sid=='drone_bench' else .01579)
        else:
            stock=meshes[data['fixed_post_node']];moving=meshes[data['shaft_node']];radius=.007;seat=data['shaft_bottom']['z'];bottom=data['fixed_post_bottom']['z'];top=data['fixed_post_top']['z']
            record=cavity_evidence(stock,moving,centre,seat,bottom,top,radius,.00725)
            assert record['residual_floor_thickness_m']>.04899
            walls=[r['outer_wall_distance_m']-r['wall']['distance_m'] for r in record['radial_witnesses']];assert min(walls)>.0066;record['minimum_radial_wall_thickness_m']=min(walls)
        records.append({'object_id':oid,**record})
    (pack['directory']/('contacts_'+flavor+'.json')).write_text(json.dumps(records,indent=2)+'\n')

def test_changed_stock_keeps_outer_surfaces_and_material(pack):
    sid=pack['scene_id'];fixture=BASELINE['scenes'][sid];path=FIXTURE_DIR/sid/'environment_before.glb';assert hashlib.sha256(path.read_bytes()).hexdigest()==fixture['baseline_environment_sha256']
    old=mesh_map(load_asset(str(path),pack['spec'].asset_axes));records=[]
    for name in fixture['changed_environment_nodes']:
        cuts=[]
        for d in BASELINE['measured_before']:
            if d['scene_id']!=sid:continue
            if sid in ('control_panel','drone_bench'):cuts.append((d['position'],round(d['flange_radius_max_m'],8)+.00025,d['flange_bottom']['z']))
            elif d['fixed_post_node']=='workstation/'+name:cuts.append((d['position'],.00725,d['shaft_bottom']['z']))
        records.append({'node':name,**exterior_evidence(old[name],pack['loaded']['workstation'][name],cuts)})
    (pack['directory']/'unchanged_stock_exterior.json').write_text(json.dumps(records,indent=2)+'\n')

def test_complete_declared_action_protocol_has_no_sampled_penetrations(pack):
    spec=pack['spec'].model_copy(deep=True)
    for obj in spec.objects:obj.asset=str((pack['directory']/(obj.object_id+'.glb')).relative_to(root()))
    spec.environment[0].asset=str((pack['directory']/'workstation.glb').relative_to(root()))
    records=sweep(spec);(pack['directory']/'declared_motion_raw.json').write_text(json.dumps(records,indent=2)+'\n')
    assert all(row['passed'] for row in records),records
    if spec.scene_id=='optical_bench':
        assert [r['source_id'] for r in records]==['L1','M']
        assert len(records[1]['prior_completed'])==1
        assert records[1]['angle_deg']==-15
    elif spec.scene_id=='drone_bench':
        assert [r['source_id'] for r in records]==['BAT','GUARD']
        assert len(records[1]['prior_completed'])==1
        assert records[1]['angle_deg']==-30
    else:assert records[0]['angle_deg']==30
