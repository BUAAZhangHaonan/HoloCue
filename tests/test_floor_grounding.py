"""Immutable physical contracts and real generated/deployed floor connections."""
from pathlib import Path
import copy,json
import pytest
from holocue import modeling
from holocue.assets import load_asset
from holocue.config import load_scene,root
from holocue.spatial import matrix
from floor_grounding_support import SCENES,mesh_map,fingerprint,contacts,floor_contact,horizontal_contact

FIXTURE=json.loads((Path(__file__).parent/'fixtures/floor_grounding_baseline.json').read_text())

def physical_objects(sid,objects):
    result=copy.deepcopy(objects)
    if sid=='dive_fillstation':
        # The separate dive view regression owns this approved camera-only
        # update. Every pose, dimension, axis, angle and other field is retained.
        bottle=next(obj for obj in result if obj['object_id']=='BOTTLE3')
        bottle['interaction'].pop('detail_direction_local',None)
    return result

@pytest.mark.parametrize('sid',SCENES)
def test_authored_nodes_frames_and_real_glb_floor_connections(sid,tmp_path):
    fixture=FIXTURE['scenes'][sid];spec=load_scene(sid)
    assert physical_objects(sid,[o.model_dump(mode='json') for o in spec.objects])==physical_objects(sid,fixture['objects'])
    assert spec.task_contract.model_dump(mode='json')==fixture['task_contract']
    poses=json.loads(json.dumps([{'pose':p.pose.model_dump(mode='json'),'scale_m':p.scale_m} for p in spec.environment]))
    assert poses==fixture['environment_poses']
    generated=tmp_path/'workstation.glb';modeling.make_environment(spec).save(generated)
    for path in (generated,root()/spec.environment[0].asset):
        meshes=mesh_map(load_asset(str(path),spec.asset_axes))
        # These two authored nodes now form the real blind valve seat and its
        # hose joint. test_dive_valve_seat checks their immutable old surfaces,
        # materials, bore, wall thickness and actual contacts independently.
        valve_nodes={'dive_fillstation_environment/0009_manifold',
                     'dive_fillstation_environment/0016_tube'} if sid=='dive_fillstation' else set()
        assert valve_nodes<=set(meshes)
        # Exact old-to-new cavity/contact/exterior checks for these three
        # nodes live in test_panel_optical_mounts with immutable old GLBs.
        mount_nodes={
            'control_panel':{'control_panel_environment/0025_instrument_panel'},
            'optical_bench':{'optical_bench_environment/0587_fixed_post',
                             'optical_bench_environment/0589_fixed_post'},
        }.get(sid,set())
        assert mount_nodes<=set(meshes)
        for node in mount_nodes:assert fingerprint(meshes[node])!=fixture['original_nodes'][node]
        # Only these four engine nodes form the molded hose and real metal
        # seat. test_engine_clamp owns their immutable old exterior/material,
        # lumen/wall/bore/contact checks and unchanged full CLAMP/PLUG sweeps.
        clamp_nodes={'engine_bay_environment/'+suffix for suffix in
                     ('0052_tube','0053_tube','0054_rounded_part','0055_clamp_band')} if sid=='engine_bay' else set()
        assert clamp_nodes<=set(meshes)
        for node in clamp_nodes:assert fingerprint(meshes[node])!=fixture['original_nodes'][node]
        for node,expected in fixture['original_nodes'].items():
            if node not in valve_nodes|mount_nodes|clamp_nodes:assert fingerprint(meshes[node])==expected,(path,node)
        assert len(set(meshes)-set(fixture['original_nodes']))==fixture['expected_added_nodes']
        if sid=='engine_bay':
            for obj in spec.objects:
                for name,mesh in mesh_map(load_asset(str(root()/obj.asset),spec.asset_axes)).items():
                    mesh.apply_transform(matrix(obj.pose));meshes['object/'+name]=mesh
        edges=contacts(meshes)
        assert edges
        assert all(edge['connected'] for edge in edges),[edge for edge in edges if not edge['connected']]

def test_oilcap_internal_collar_preserves_authored_geometry(tmp_path):
    fixture=json.loads((Path(__file__).parent/'fixtures/engine_mount_objects_baseline.json').read_text())
    spec=load_scene('engine_bay');obj=next(o for o in spec.objects if o.object_id=='OILCAP')
    path=tmp_path/'OILCAP.glb';modeling.make_object(obj).save(path)
    for asset in (path,root()/obj.asset):
        meshes=mesh_map(load_asset(str(asset),spec.asset_axes))
        for name,digest in fixture['original_nodes'].items():assert fingerprint(meshes[name])==digest
        assert len(set(meshes)-set(fixture['original_nodes']))==fixture['expected_added_nodes']
        flange=next(m for n,m in meshes.items() if n.endswith('flange'))
        collar=next(m for n,m in meshes.items() if n.endswith('cap_grip_collar'))
        grip=next(m for n,m in meshes.items() if n.endswith('grip'))
        assert floor_contact(flange,collar)['connected']
        assert horizontal_contact(collar,grip)['connected']
