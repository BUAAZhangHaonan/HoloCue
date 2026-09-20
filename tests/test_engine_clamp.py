"""Generated/GLB geometry regressions for the locally molded engine hose seat."""
from pathlib import Path
import hashlib,json
import numpy as np
import pytest
import trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk,vtk_to_numpy
from holocue.assets import load_asset
from holocue.config import load_scene
from holocue.glb_attributes import exported_normals
from holocue.modeling import make_environment,make_object
from holocue.models import SceneSpec
from holocue.spatial import matrix,trajectory
from holocue.render_validation import polydata
from scripts.tests.audit_geometry import ordered_steps,parts


def meshes(scene,pose=None):
    result={}
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node];mesh=scene.geometry[name].copy()
        mesh.apply_transform(transform if pose is None else matrix(pose)@transform)
        result[str(node)]=mesh
    return result


def fingerprint(mesh):
    result={key:hashlib.sha256(np.asarray(getattr(mesh,key),dtype=dtype).tobytes()).hexdigest()
            for key,dtype in [('vertices','<f8'),('faces','<i8'),('vertex_normals','<f8')]}
    material=mesh.visual.material;texture=getattr(material,'baseColorTexture',None)
    result['material']={'name':material.name,'baseColorFactor':np.asarray(material.baseColorFactor).tolist(),
        'metallicFactor':material.metallicFactor,'roughnessFactor':material.roughnessFactor,
        'doubleSided':material.doubleSided,'alphaMode':material.alphaMode,
        'texture_sha256':None if texture is None else hashlib.sha256(np.asarray(texture).tobytes()).hexdigest()}
    result['uv']=None if mesh.visual.uv is None else hashlib.sha256(np.asarray(mesh.visual.uv,dtype='<f8').tobytes()).hexdigest()
    return result


def field(mesh):
    copy=mesh.copy();copy.process(validate=True)
    result=vtk.vtkImplicitPolyDataDistance();result.SetInput(polydata(copy));return result


def distances(distance_field,points):
    values=vtk.vtkDoubleArray()
    distance_field.EvaluateFunction(numpy_to_vtk(np.ascontiguousarray(points),deep=True),values)
    return vtk_to_numpy(values)


def part(collection,suffix):
    return next(mesh for name,mesh in collection.items() if name.endswith(suffix))


def roof(y):
    y=np.asarray(y);result=np.full(y.shape,1.122)
    left=(y>-.166)&(y<-.116);t=(y[left]+.166)/.05
    result[left]=1.122-.035*(3*t*t-2*t*t*t)
    result[(y>=-.116)&(y<=-.084)]=1.087
    right=(y>-.084)&(y<-.034);t=(y[right]+.084)/.05
    result[right]=1.087+.035*(3*t*t-2*t*t*t)
    return result


def line_hits(mesh,start,end):
    """Actual triangle-line intersections, including the axial blind-end faces."""
    start=np.asarray(start);delta=np.asarray(end)-start
    tri=mesh.triangles;e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
    cross=np.cross(delta,e2);det=np.einsum('ij,ij->i',e1,cross)
    mask=np.abs(det)>1e-15;tri=tri[mask];e1=e1[mask];e2=e2[mask];cross=cross[mask];det=det[mask]
    offset=start-tri[:,0];u=np.einsum('ij,ij->i',offset,cross)/det
    q=np.cross(offset,e1);v=q@delta/det;t=np.einsum('ij,ij->i',e2,q)/det
    t=np.sort(t[(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)&(t>=0)&(t<=1)])
    if not len(t):return np.empty((0,3))
    t=t[np.r_[True,np.diff(t)>1e-7]]
    return start+t[:,None]*delta


@pytest.fixture(scope='module')
def engine(tmp_path_factory):
    directory=tmp_path_factory.mktemp('engine-clamp')
    spec=load_scene('engine_bay');fixtures=Path(__file__).parent/'fixtures'
    baseline=json.loads((fixtures/'engine_clamp_baseline.json').read_text())
    generated={};roundtrip={};local={};paths={}
    for obj in [*spec.objects,*spec.environment]:
        identifier=obj.object_id if hasattr(obj,'object_id') else 'workstation'
        assembly=make_object(obj) if hasattr(obj,'object_id') else make_environment(spec)
        path=directory/f'{identifier}.glb';assembly.save(path);paths[identifier]=path
        loaded=load_asset(str(path),spec.asset_axes)
        generated.update(meshes(assembly.scene,obj.pose));roundtrip.update(meshes(loaded,obj.pose))
        local[identifier]=meshes(loaded)
    old=meshes(load_asset(str(fixtures/'engine_hose_before.glb'),spec.asset_axes),spec.environment[0].pose)
    old.update(meshes(load_asset(str(fixtures/'engine_clamp_before.glb'),spec.asset_axes),spec.objects[0].pose))
    return dict(spec=spec,directory=directory,baseline=baseline,old=old,generated=generated,roundtrip=roundtrip,local=local,paths=paths,fixtures=fixtures)


def test_engine_contract_unchanged(engine):
    assert engine['spec']==SceneSpec.model_validate(engine['baseline']['scene'])


def test_only_authorized_nodes_change_and_materials_stay(engine):
    changed={'workstation':{'0052_tube','0053_tube','0054_rounded_part','0055_clamp_band'},
             'CLAMP':{'0000_threaded_shank','0010_hex_head','0011_driver_slot'}}
    for identifier,expected in engine['baseline']['fingerprints'].items():
        actual=engine['local'][identifier]
        assert set(actual)==set(expected)
        for name,old in expected.items():
            new=fingerprint(actual[name])
            assert new['material']==old['material'],name
            if name.split('/')[-1] not in changed.get(identifier,set()):
                assert new==old,(identifier,name)


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_molded_hose_and_metal_seat_are_closed_connected_solids(engine,version):
    records=[]
    for suffix in ('0052_tube','0053_tube','0054_rounded_part','0055_clamp_band'):
        mesh=part(engine[version],suffix).copy();mesh.process(validate=True)
        records.append({'node':suffix,'watertight':bool(mesh.is_watertight),'volume_m3':float(mesh.volume),'components':len(mesh.split())})
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
        assert len(mesh.split())==1
    (engine['directory']/f'topology_{version}.json').write_text(json.dumps(records,indent=2))


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_head_slot_and_shaft_preserve_real_dimensions_and_connections(engine,version):
    actual=engine[version]
    for suffix in ('0010_hex_head','0011_driver_slot'):
        new=part(actual,suffix);old=part(engine['old'],suffix)
        assert np.array_equal(new.faces,old.faces)
        assert np.allclose(new.vertices-[.019,0,0],old.vertices,atol=8e-8,rtol=0)
        # World-coordinate triangle recomputation amplifies float32 POSITION
        # rounding on this 1mm slot; compare the actual shader normals instead.
        name=next(name for name in engine['local']['CLAMP'] if name.endswith(suffix))
        normals=exported_normals(engine['paths']['CLAMP'],name)
        old_normals=exported_normals(engine['fixtures']/'engine_clamp_before.glb',name)
        assert np.allclose(normals,old_normals,atol=1e-6,rtol=0)
    shaft=part(actual,'0000_threaded_shank');old=part(engine['old'],'0000_threaded_shank')
    assert abs(shaft.bounds[0,0]-old.bounds[0,0])<8e-8
    assert abs(shaft.bounds[1,0]-old.bounds[1,0]-.019)<8e-8
    assert np.allclose(shaft.bounds[:,1:],old.bounds[:,1:],atol=8e-8,rtol=0)
    assert shaft.bounds[1,0]>part(actual,'0010_hex_head').bounds[0,0]+.0058
    # Interior joint points certify that the long shaft reaches the original head.
    witness=np.array([[-.270,-.100,1.100]])
    assert distances(field(shaft),witness)[0]<-.001
    assert distances(field(part(actual,'0010_hex_head')),witness)[0]<-.001


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_actual_metal_blind_bore_ring_grooves_and_band_union(engine,version):
    mesh=part(engine[version],'0055_clamp_band');seat_field=field(mesh)
    axial=line_hits(mesh,[-.34,-.1,1.1],[-.25,-.1,1.1])[:,0]
    assert np.allclose(axial,[-.32421,-.32021],atol=2e-6,rtol=0),axial
    sections=[]
    for xx in np.linspace(-.3188,-.29154,9):
        hits=line_hits(mesh,[xx,-.1,1.075],[xx,-.1,1.13])[:,2]
        assert len(hits)==4,(xx,hits)
        assert abs(hits[1]-1.0934)<3e-5 and abs(hits[2]-1.1066)<3e-5,(xx,hits)
        assert hits[3]-hits[2]>.00435,(xx,hits)
        sections.append({'x_m':float(xx),'actual_z_intersections_m':hits.tolist()})
    bore=line_hits(mesh,[-.28,-.1,1.075],[-.28,-.1,1.13])[:,2]
    assert np.allclose(bore,[1.089,1.0948,1.1052,1.111],atol=3e-5,rtol=0),bore
    witness=np.array([[-.285,-.110,1.1]])
    assert distances(field(part(engine['old'],'0055_clamp_band')),witness)[0]<-.00149
    assert distances(seat_field,witness)[0]<-.0009
    # Actual shoe, seat and band occupy one closed component; retained old band
    # samples stay in/on the union rather than being replaced by a named brace.
    old=part(engine['old'],'0055_clamp_band');points,_=trimesh.sample.sample_surface(old,1536,seed=4701)
    assert distances(seat_field,points).max()<2e-6
    assert distances(seat_field,np.array([[-.306,-.1,1.088]]))[0]<-.0005
    (engine['directory']/f'metal_sections_{version}.json').write_text(json.dumps({'ring_grooves':sections,'blind_bore_x_m':axial.tolist(),'plain_bore_z_m':bore.tolist()},indent=2))


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_real_hose_sections_have_flattened_lumen_and_ten_mm_roof(engine,version):
    hose=[part(engine[version],suffix) for suffix in ('0052_tube','0053_tube','0054_rounded_part')]
    records=[]
    for yy in (-.116,-.114,-.1,-.086,-.084):
        xx=-.32+(yy+.12)*.05/.18
        hits=np.concatenate([line_hits(mesh,[xx,yy,1.05],[xx,yy,1.12])[:,2] for mesh in hose])
        assert len(hits)>0
        assert np.any(np.abs(hits-1.077)<2e-6),(yy,hits)
        assert np.any(np.abs(hits-1.087)<2e-6),(yy,hits)
        for mesh in hose:
            f=field(mesh)
            assert distances(f,np.array([[xx,yy,1.076]]))[0]>0
        records.append({'y_m':yy,'x_m':xx,'actual_z_intersections_m':hits.tolist()})
    (engine['directory']/f'hose_roof_sections_{version}.json').write_text(json.dumps(records,indent=2))


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_unchanged_hose_exterior_and_endpoints(engine,version):
    records=[]
    old_fields=[field(part(engine['old'],suffix)) for suffix in ('0052_tube','0053_tube','0054_rounded_part')]
    for suffix in ('0052_tube','0053_tube','0054_rounded_part'):
        old=part(engine['old'],suffix);new=part(engine[version],suffix)
        points,faces=trimesh.sample.sample_surface(old,4096,seed=4701)
        # Old outer faces below the molded roof remain at their exact locations.
        # End cap centers become lumen openings, but their outer rims remain.
        keep=(points[:,2]<roof(points[:,1])-.0001)
        # Surfaces already inside another old tube are internal overlap faces,
        # not retained exterior; the common lumen necessarily removes them.
        keep&=np.min([distances(f,points) for f in old_fields],axis=0)>-2e-6
        if suffix!='0054_rounded_part':
            segment=np.array([[-.46,-.25,1.04],[-.32,-.12,1.06],[-.27,.06,1.03]])
            index=0 if suffix=='0052_tube' else 1
            axis=segment[index+1]-segment[index];axis/=np.linalg.norm(axis)
            keep&=np.abs(old.face_normals[faces]@axis)<.01
            endpoint=segment[0] if index==0 else segment[2]
            near_end=np.abs((old.vertices-endpoint)@axis)<1e-7
            rim=old.vertices[near_end]
            rim=rim[np.linalg.norm(rim-endpoint,axis=1)>.05]
            assert len(rim)>0
            assert np.abs(distances(field(new),rim)).max()<3e-6
        error=np.abs(distances(field(new),points[keep]))
        assert error.max()<3e-6,(suffix,error.max())
        records.append({'node':suffix,'surface_samples':int(keep.sum()),'max_exterior_error_m':float(error.max())})
    (engine['directory']/f'exterior_{version}.json').write_text(json.dumps(records,indent=2))


@pytest.mark.parametrize('version',['generated','roundtrip'])
def test_actual_flow_sections_and_wall_measurements(engine,version):
    hose=[part(engine[version],suffix).copy() for suffix in ('0052_tube','0053_tube','0054_rounded_part')]
    for mesh in hose:mesh.process(validate=True)
    trees=[]
    for mesh in hose:
        tree=vtk.vtkOBBTree();tree.SetDataSet(polydata(mesh));tree.BuildLocator();trees.append(tree)
    hose_fields=[field(mesh) for mesh in hose]
    path=np.array([[-.46,-.25,1.04],[-.32,-.12,1.06],[-.27,.06,1.03]])
    rows=[]
    for segment,(aa,bb) in enumerate(zip(path,path[1:])):
        axis=(bb-aa)/np.linalg.norm(bb-aa)
        u=np.cross(axis,[0,0,1.]);u/=np.linalg.norm(u);v=np.cross(axis,u)
        for t in np.linspace(.001,.999,25):
            center=aa+t*(bb-aa);radii=[]
            assert all(distances(f,center[None])[0]>0 for f in hose_fields)
            for theta in np.linspace(0,2*np.pi,180,endpoint=False):
                direction=u*np.cos(theta)+v*np.sin(theta);end=center+.10*direction
                hits=[]
                for tree in trees:
                    points=vtk.vtkPoints();ids=vtk.vtkIdList();tree.IntersectWithLine(center,end,points,ids)
                    hits.extend(np.linalg.norm(np.array(points.GetPoint(i))-center) for i in range(points.GetNumberOfPoints()))
                assert hits,('unbounded or broken flow wall',segment,t,theta)
                radii.append(min(hits))
            radii=np.array(radii)
            area=float(np.pi*np.mean(radii*radii))
            assert radii.min()>.0168,(segment,t,radii.min())
            assert area>.00460,(segment,t,area)
            rows.append({'segment':segment,'t':float(t),'center_m':center.tolist(),'actual_normal_flow_area_m2':area,'actual_inner_radii_m':radii.tolist()})
    # Identify real exposed inner and outer triangles from the generated wall
    # union, then measure their separation. Internal old overlaps are excluded
    # from this wall-thickness measurement only, never from the collision audit.
    outer_roof=[];inner=[]
    old_fields=[field(part(engine['old'],suffix)) for suffix in ('0052_tube','0053_tube','0054_rounded_part')]
    for mesh in hose:
        centers=mesh.triangles_center;nearest=[]
        for aa,bb in zip(path,path[1:]):
            axis=bb-aa;t=np.clip((centers-aa)@axis/(axis@axis),0,1)
            nearest.append(aa+t[:,None]*axis)
        radial=np.stack([centers-p for p in nearest])
        choose=np.linalg.norm(radial,axis=2).argmin(axis=0)
        radial=radial[choose,np.arange(len(centers))]
        sign=np.einsum('ij,ij->i',mesh.face_normals,radial)
        exposed=np.min([distances(f,centers) for f in hose_fields],axis=0)>-2e-5
        is_roof=(np.abs(centers[:,2]-roof(centers[:,1]))<.0007)&(mesh.face_normals[:,2]>.3)
        outer_roof.extend(mesh.triangles[is_roof])
        selected=exposed&(sign<-.001)&(centers[:,1]>-.15)&(centers[:,1]<-.05)
        inner.extend(mesh.triangles[selected])
    outer_roof=np.asarray(outer_roof);inner=np.asarray(inner)
    assert len(outer_roof)>10 and len(inner)>100
    outer_mesh=trimesh.Trimesh(vertices=outer_roof.reshape(-1,3),faces=np.arange(outer_roof.size//3).reshape(-1,3),process=True)
    samples=np.concatenate([inner.mean(axis=1),inner.reshape(-1,3)])
    # Classify each sample, not only its triangle center: old overlapping tube
    # triangles span internal seam vertices and cannot all be treated as the
    # outside boundary of the combined hose. No motion obstacle is excluded.
    exposed=np.min([distances(f,samples) for f in hose_fields],axis=0)>-2e-6
    original_union=load_asset(str(engine['fixtures']/'engine_hose_outer_union_before.glb'),'project_z_up').to_geometry()
    original_union.apply_transform(matrix(engine['spec'].environment[0].pose))
    old_depth=-distances(field(original_union),samples)
    selected=exposed&(old_depth>2e-5)
    samples=samples[selected];old_depth=old_depth[selected]
    roof_gap=np.abs(distances(field(outer_mesh),samples))
    # The immutable original CAD union removes internal old end caps. Its
    # actual exterior distance avoids understating thickness near the bend.
    # Combine it with the distance to the actual generated roof triangles.
    gaps=np.minimum(old_depth,roof_gap)
    evidence={'normal_sections':rows,'actual_sampled_minimum_wall_m':float(gaps.min()),
              'inner_sample_count':len(samples),'outer_roof_triangle_count':len(outer_roof),
              'minimum_wall_point_m':samples[gaps.argmin()].tolist(),
              'wall_method':'actual inner mesh points to immutable original outer union / actual new roof triangles; per-point exposure excludes internal component seams only from wall measurement',
              'limitations':'Finite 50 normal sections/180 rays and exposed inner triangle samples; actual geometry evidence, not a continuous hydraulic certification.'}
    (engine['directory']/f'flow_wall_{version}.json').write_text(json.dumps(evidence,indent=2))
    assert gaps.min()>.006,float(gaps.min())


def test_original_full_ordered_clamp_and_plug_sweep(engine,monkeypatch):
    """Same 1536/4701/41/.75mm protocol; every new seat surface is an obstacle."""
    spec=engine['spec'];objects={obj.object_id:obj for obj in spec.objects}
    assets={obj.asset:engine['paths'][obj.object_id] for obj in spec.objects}
    assets[spec.environment[0].asset]=engine['paths']['workstation']
    monkeypatch.setattr('scripts.tests.audit_geometry.resource',lambda unused,asset:assets[asset])
    rows=[]
    for step_index,step,display,cue,prior_completed in ordered_steps(spec):
        if step.action not in ('rotate','insert','assemble'):continue
        source=objects[step.target_id]
        mesh=load_asset(str(engine['paths'][source.object_id]),spec.asset_axes).to_geometry()
        sampled,face_indices=trimesh.sample.sample_surface(mesh,1536,seed=4701)
        static=[obj.model_copy(update={'pose':display.object_poses[obj.object_id]},deep=True) for obj in spec.objects if obj.object_id!=source.object_id]
        obstacles,coverage=parts(spec,static+spec.environment);hits=[]
        for frame,t in enumerate(np.linspace(0,source.interaction.duration_s,41)):
            points=trimesh.transform_points(sampled,matrix(trajectory(cue,float(t))))
            lo=points.min(axis=0);hi=points.max(axis=0)
            for oid,name,bounds,f in obstacles:
                if np.any(lo>bounds[1]) or np.any(hi<bounds[0]):continue
                selection=((points>bounds[0]+.00075)&(points<bounds[1]-.00075)).all(axis=1)
                if not selection.any():continue
                d=distances(f,points[selection]);penetration=d<-.00075
                if penetration.any():hits.append({'frame':frame,'elapsed_s':float(t),'obstacle':oid,'part':name,'points':int(penetration.sum()),'max_depth_m':float(-d.min())})
        rows.append({'source_id':source.object_id,'step_index':step_index,'prior_completed':prior_completed,
            'sampled_surface_points':1536,'seed':4701,'trajectory_samples':41,'threshold_m':.00075,
            'sample_face_indices':face_indices.tolist(),'raw_hits':hits,'coverage':coverage})
    (engine['directory']/'raw_ordered_sweep.json').write_text(json.dumps(rows,indent=2))
    assert {row['source_id'] for row in rows}=={'CLAMP','PLUG'}
    assert all(any(c['part'].endswith('0055_clamp_band') and c['status']=='included_closed_solid' for c in row['coverage']) for row in rows)
    assert not any(row['raw_hits'] for row in rows),rows
    assert not any(c['status']=='invalid_solid_topology' for row in rows for c in row['coverage'])
