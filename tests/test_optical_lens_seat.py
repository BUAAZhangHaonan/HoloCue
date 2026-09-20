"""Original lens surfaces and real post seats, read from exported triangles."""
import hashlib,json
from pathlib import Path
import numpy as np
import pytest
import trimesh
from holocue.assets import load_asset
from holocue.config import root,load_scene
from holocue.modeling import make_object
from holocue.models import Pose,SceneSpec
from holocue.spatial import matrix

FIXTURE=Path(__file__).parent/'fixtures/optical_lens_before_seat'
HASHES={'L1.glb':'dd4236403f6b3cf62516d168f858b544fe7d32fd93d17f08eac6dd09b977230b',
    'L2.glb':'34ff1c0a6f67d13ed34cdc7bb97e533902c8a0375489b304852c63b63aa8f108',
    'scene.json':'1936c299bf9b2411772b50012882012c9845bcfdfcdf43d9387977039943c4b7',
    'L1_view.json':'73652ad7e339a8f77952cbbc59fe21080f1b2ac441f114051a04c95cb35cda35',
    'L2_view.json':'1f2664935285153004f470b64df6e8a26b667780cf77fa95df5ad0834c802c3b',
    'visible_rays.json':'fe56fdb48cc685085a04579e5b0d5742111bc07e8a5cbb9d01fa8f98fde57df8'}

def nodes(scene,pose=np.eye(4)):
    result={}
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node];mesh=scene.geometry[name].copy();mesh.apply_transform(pose@transform);result[str(node)]=mesh
    return result

def hits(mesh,origin,direction):
    tri=mesh.triangles;a=tri[:,1]-tri[:,0];b=tri[:,2]-tri[:,0];h=np.cross(direction,b);det=np.einsum('ij,ij->i',a,h)
    inv=np.divide(1.,det,out=np.zeros_like(det),where=abs(det)>1e-12);s=origin-tri[:,0]
    u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,a);v=(q@direction)*inv;t=np.einsum('ij,ij->i',b,q)*inv
    selected=np.flatnonzero((abs(det)>1e-12)&(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>1e-9))
    return [(float(t[i]),int(i)) for i in selected[np.argsort(t[selected])]]

def closed(mesh):
    mesh=mesh.copy();mesh.process(validate=True)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
    assert len(mesh.split(only_watertight=False))==1
    return mesh

def distances(mesh,points):
    # Trimesh's absolute triangle-region tolerance misclassifies the edge of a
    # small seat-intersection triangle in metres. Compute in millimetres and
    # return metres; all physical thresholds and sample points stay unchanged.
    # The retained r1 witness has positive barycentric coordinates and a true
    # plane distance of 0.803 nm, independently verified against face 159.
    scaled=trimesh.Trimesh(mesh.vertices*1000,mesh.faces,process=False)
    return trimesh.proximity.closest_point_naive(scaled,np.asarray(points)*1000)[1]/1000

@pytest.fixture(scope='module')
def lenses(tmp_path_factory):
    for name,digest in HASHES.items():assert hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest()==digest,name
    spec=load_scene('optical_bench');directory=tmp_path_factory.mktemp('optical-lens-seats');result={}
    for oid in ('L1','L2'):
        obj=next(o for o in spec.objects if o.object_id==oid);path=directory/(oid+'.glb');make_object(obj).save(path)
        result[oid]=(nodes(load_asset(str(FIXTURE/(oid+'.glb')),spec.asset_axes)),nodes(load_asset(str(path),spec.asset_axes)),path)
    return spec,result,directory

def test_original_optical_task_camera_and_object_contracts_are_unchanged(lenses):
    spec,_,_=lenses
    original=SceneSpec.model_validate(json.loads((FIXTURE/'scene.json').read_text()))
    assert spec==original

@pytest.mark.parametrize('oid',['L1','L2'])
def test_only_retainer_and_post_change_with_all_materials_preserved(lenses,oid):
    _,data,_=lenses;old,new,_=data[oid];assert old.keys()==new.keys();changed=set()
    for name,before in old.items():
        after=new[name]
        equal=np.array_equal(before.vertices,after.vertices) and np.array_equal(before.faces,after.faces)
        if not equal:changed.add(name)
        else:np.testing.assert_array_equal(before.vertex_normals,after.vertex_normals)
        for key in ('name','baseColorFactor','metallicFactor','roughnessFactor','doubleSided','alphaMode'):
            np.testing.assert_array_equal(getattr(before.visual.material,key),getattr(after.visual.material,key))
        np.testing.assert_array_equal(before.visual.uv,after.visual.uv)
    assert changed=={oid+'/0000_optic_retainer',oid+'/0002_mounting_post'}

@pytest.mark.parametrize('oid',['L1','L2'])
def test_real_blind_seat_walls_and_post_end_contact(lenses,oid):
    _,data,directory=lenses;_,new,_=data[oid]
    ring=closed(new[oid+'/0000_optic_retainer']);post=closed(new[oid+'/0002_mounting_post'])
    assert post.vertices[:,2].min()==pytest.approx(-.065,abs=1e-7)
    assert post.vertices[:,2].max()==pytest.approx(-.020,abs=1e-7)
    np.testing.assert_allclose(post.bounds[:,:2],[[-.007,-.007],[.007,.007]],atol=1e-7)
    cap=post.triangles[np.max(abs(post.triangles[:,:,2]+.020),axis=1)<1e-7]
    assert len(cap)==40
    closest,distance,faces=trimesh.proximity.closest_point_naive(ring,cap.mean(axis=1))
    assert distance.max()<1e-7
    axis=hits(ring,np.array([0.,0.,-.070]),np.array([0.,0.,1.]))
    z=np.unique(np.round([value-.070 for value,_ in axis],9))
    assert z[0]==pytest.approx(-.020,abs=1e-7)
    assert z[1]-z[0]>.0067
    rays=[]
    for height in (-.024,-.022,-.0205):
        for theta in np.linspace(0,2*np.pi,80,endpoint=False):
            direction=np.array([np.cos(theta),np.sin(theta),0.])
            values=np.unique(np.round([value for value,_ in hits(ring,np.array([0.,0.,height]),direction)],9))
            assert len(values)>=2 and .007075<values[0]<.007101
            assert values[1]-values[0]>.0063
            rays.append({'z':height,'direction':direction.tolist(),'intersections':values.tolist()})
    report={'cap_triangles':cap.tolist(),'nearest_ring_points':closest.tolist(),'ring_face_indices':faces.tolist(),
        'nearest_ring_triangles':ring.triangles[faces].tolist(),'contact_distances':distance.tolist(),
        'axis_intersections_z':z.tolist(),'radial_rays':rays,'ring_volume_m3':float(ring.volume)}
    (directory/(oid+'_seat_readback.json')).write_text(json.dumps(report,indent=2)+'\n')

@pytest.mark.parametrize('oid',['L1','L2'])
def test_post_clears_all_lens_triangles_and_preserves_the_lower_insertion_end(lenses,oid):
    _,data,_=lenses;old,new,_=data[oid]
    post=new[oid+'/0002_mounting_post'];lens=new[oid+'/0001_convex_lens'];before=old[oid+'/0002_mounting_post']
    # Every linear triangle lies between its vertex z extrema: a separating
    # plane here is a rigorous lower clearance bound, not an overlap inference.
    assert lens.vertices[:,2].min()-post.vertices[:,2].max()>.0057
    assert distances(lens,post.vertices).min()>.0057
    old_bottom=before.vertices[abs(before.vertices[:,2]+.065)<1e-7]
    bottom=post.vertices[abs(post.vertices[:,2]+.065)<1e-7]
    np.testing.assert_array_equal(old_bottom,bottom)

@pytest.mark.parametrize('oid',['L1','L2'])
def test_original_retainer_surface_outside_the_local_blind_seat_is_preserved(lenses,oid):
    _,data,_=lenses;old,new,_=data[oid]
    for source,target in ((old[oid+'/0000_optic_retainer'],new[oid+'/0000_optic_retainer']),
                          (new[oid+'/0000_optic_retainer'],old[oid+'/0000_optic_retainer'])):
        samples=np.concatenate([source.vertices,source.triangles_center])
        untouched=(np.linalg.norm(samples[:,:2],axis=1)>.0072)|(samples[:,2]>-.0199)
        assert untouched.sum()>100
        assert distances(target,samples[untouched]).max()<1e-7

@pytest.mark.parametrize('oid',['L1','L2'])
def test_optical_aperture_and_archived_camera_rays_hit_the_lens_not_the_post(lenses,oid):
    spec,data,directory=lenses;old,new,path=data[oid]
    for x in (-.004,0.,.004):
        for z in (-.012,-.009,-.006,-.003,-.0005):
            origin=np.array([x,-.1,z]);direction=np.array([0.,1.,0.]);nearest=[]
            for name,mesh in new.items():
                value=hits(mesh,origin,direction)
                if value:nearest.append((value[0][0],name))
            assert min(nearest)[1]==oid+'/0001_convex_lens'
    frame=json.loads((FIXTURE/(oid+'_view.json')).read_text());world={}
    for obj in spec.objects:
        asset=path if obj.object_id==oid else root()/obj.asset
        world.update(nodes(load_asset(str(asset),spec.asset_axes),matrix(Pose.model_validate(frame['object_poses'][obj.object_id]))))
    for prop in spec.environment:world.update(nodes(load_asset(str(root()/prop.asset),spec.asset_axes),matrix(prop.pose)@np.diag([*prop.scale_m,1.])))
    original_rays=json.loads((FIXTURE/'visible_rays.json').read_text())[oid];result=[]
    assert len(original_rays)==8
    for ray in original_rays:
        origin=np.asarray(ray['camera_world']);direction=np.asarray(ray['direction_world']);nearest=[]
        for name,mesh in world.items():
            value=hits(mesh,origin,direction)
            if value:nearest.append((value[0][0],name,value[0][1]))
        distance,name,face=min(nearest)
        assert name==oid+'/0001_convex_lens'
        result.append({'origin':origin.tolist(),'direction':direction.tolist(),'old_first_node':ray['world_first_hit_node'],
            'new_first_node':name,'distance_m':distance,'new_face_index':face,'new_triangle':world[name].triangles[face].tolist()})
    (directory/(oid+'_visible_ray_readback.json')).write_text(json.dumps(result,indent=2)+'\n')
