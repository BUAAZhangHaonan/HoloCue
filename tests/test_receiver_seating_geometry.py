"""Real receiver solids must meet at an internal joint, not overlap at the visible rim."""
import numpy as np
import pytest
import trimesh

from holocue.config import load_scene
from holocue.modeling import make_object


def parts(scene):
    result={}
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node]
        mesh=scene.geometry[name].copy();mesh.apply_transform(transform)
        result[str(node).split('_',1)[1]]=mesh
    return result


@pytest.mark.parametrize('scene_id,oid,inner',[
    ('cnc_toolchange','POCKET9',.020),('engine_bay','PLUGPORT',.012)])
@pytest.mark.parametrize('roundtrip',[False,True],ids=['generated','glb_roundtrip'])
def test_receiver_has_closed_nonoverlapping_body_and_seating_collar(tmp_path,scene_id,oid,inner,roundtrip):
    spec=load_scene(scene_id);obj=next(o for o in spec.objects if o.object_id==oid)
    assembly=make_object(obj)
    scene=assembly.scene
    if roundtrip:
        path=tmp_path/f'{oid}.glb';assembly.save(path)
        scene=trimesh.load_scene(path,process=False)
        scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
    meshes=parts(scene)
    assert set(meshes)=={'receiver_bore','seating_face'}
    body,seat=meshes['receiver_bore'],meshes['seating_face']
    height=obj.size_m[2];outer=obj.size_m[0]/2;rim=obj.size_m[0]*.55
    for mesh in meshes.values():
        assert np.isfinite(mesh.vertices).all() and np.isfinite(mesh.vertex_normals).all()
        # Export splits normal seams: weld only an inspection copy, never fill or repair holes.
        topology=mesh.copy();topology.merge_vertices(merge_norm=True,merge_tex=True)
        assert topology.is_watertight and topology.is_winding_consistent
        assert topology.volume>0
        radial=np.linalg.norm(mesh.vertices[:,:2],axis=1)
        assert radial.min()==pytest.approx(inner,abs=1e-8)
    np.testing.assert_allclose(body.bounds[0],[-outer,-outer,-height/2],atol=1e-8)
    np.testing.assert_allclose(seat.bounds[1],[rim,rim,height/2],atol=1e-8)
    assert body.bounds[1,2]==pytest.approx(seat.bounds[0,2],abs=1e-8)
    assert seat.extents[2]==pytest.approx(.006,abs=1e-8)
    assert min(body.bounds[1,2],seat.bounds[1,2])-max(body.bounds[0,2],seat.bounds[0,2])<=1e-8

    # Count actual faces exposed on the top support plane. Previously both materials occupied it.
    top_area={}
    for name,mesh in meshes.items():
        top=(np.abs(mesh.triangles[:,:,2]-height/2).max(axis=1)<1e-8)&(mesh.face_normals[:,2]>.999999)
        top_area[name]=float(mesh.area_faces[top].sum())
        if top.any():
            assert np.all(mesh.vertex_normals[mesh.faces[top],2]>.999999)
    assert top_area['receiver_bore']==0
    # Exact area for the real 48-segment annulus, not an idealized smooth circle.
    assert top_area['seating_face']==pytest.approx(24*np.sin(2*np.pi/48)*(rim**2-inner**2),rel=2e-6)
    assert meshes['receiver_bore'].visual.material.name=='receiver_bore_material'
    assert meshes['seating_face'].visual.material.name=='seating_face_material'

    # Two solids tile the intended stepped bore without changing the original external envelope.
    area_body=24*np.sin(2*np.pi/48)*(outer**2-inner**2)
    area_seat=24*np.sin(2*np.pi/48)*(rim**2-inner**2)
    assert body.volume+seat.volume==pytest.approx(area_body*(height-.006)+area_seat*.006,rel=3e-6)
