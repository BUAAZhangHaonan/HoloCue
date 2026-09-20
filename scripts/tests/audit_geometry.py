"""Independent mesh-distance inspection of declared rigid-body task trajectories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import vtk
from scipy.spatial.transform import Rotation
from vtk.util.numpy_support import numpy_to_vtk,vtk_to_numpy

from holocue.assets import load_asset,resource
from holocue.config import root,list_scenes,load_scene,load_policy
from holocue.models import CueSemantic,Decision,Session,Pose
from holocue.projection import packet
from holocue.render_validation import polydata
from holocue.spatial import trajectory
from holocue.state import apply_decision


def transform(pose):
    result=np.eye(4)
    result[:3,:3]=Rotation.from_quat(pose.wxyz,scalar_first=True).as_matrix()
    result[:3,3]=pose.position_m
    return result


def parts(spec,objects):
    result=[];coverage=[]
    for obj in objects:
        scene=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
        pose=transform(obj.pose)
        if hasattr(obj,'scale_m'):
            pose=pose@np.diag([*obj.scale_m,1.])
        identifier=obj.object_id if hasattr(obj,'object_id') else obj.prop_id
        for node in scene.graph.nodes_geometry:
            local,name=scene.graph[node]
            mesh=scene.geometry[name].copy()
            record={'object_id':identifier,'part':str(node),
                    'raw_vertices':len(mesh.vertices),'raw_faces':len(mesh.faces),
                    'raw_watertight':bool(mesh.is_watertight)}
            # glTF can retain zero-area CAD tessellation faces and split
            # vertices. Normalize only the private collision copy; never fill
            # holes or silently exclude a solid obstacle on that account.
            mesh.process(validate=True)
            record.update(vertices=len(mesh.vertices),faces=len(mesh.faces),
                          watertight=bool(mesh.is_watertight),
                          winding_consistent=bool(mesh.is_winding_consistent))
            label_surface=(str(node).split('/')[-1].startswith('label_') and
                isinstance(mesh.visual,trimesh.visual.TextureVisuals) and
                getattr(mesh.visual.material,'baseColorTexture',None) is not None and
                np.linalg.matrix_rank(mesh.vertices-mesh.vertices.mean(axis=0),tol=1e-8)<=2)
            if label_surface:
                record['status']='excluded_textured_label_surface'
                coverage.append(record)
                continue
            if not mesh.is_watertight or not mesh.is_winding_consistent:
                record['status']='invalid_solid_topology'
                coverage.append(record)
                continue
            record['status']='included_closed_solid'
            coverage.append(record)
            mesh.apply_transform(pose@local)
            field=vtk.vtkImplicitPolyDataDistance();field.SetInput(polydata(mesh))
            result.append((identifier,str(node),mesh.bounds,field))
    return result,coverage


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=root()/'runs/simulation/geometry_audit.json')
    parser.add_argument('--scenes',nargs='*')
    args=parser.parse_args();rows=[]
    selected=args.scenes or [s['scene_id'] for s in list_scenes()]
    for sid in selected:
        spec=load_scene(sid);objects={o.object_id:o for o in spec.objects}
        for step in spec.task_contract.ordered_steps:
            if step.action not in ('insert','assemble'):
                continue
            source=objects[step.target_id];receiver=objects[step.reference_id]
            semantic=CueSemantic(target_id=step.target_id,action=step.action,
                reference_id=step.reference_id,cue_type='ghost_motion',task_role='current',
                priority=5,depth_requirement=step.depth_requirement,instruction='Geometric trajectory evaluation')
            state=apply_decision(Session(session_id='geometry',scene_id=sid,backend_mode='geometry_validation'),
                Decision(operation='replace',assistant_message='Evaluate declared trajectory',cues=[semantic]),spec)
            cue=packet(state,spec,load_policy()).cues[0]
            key='insertion' if step.action=='insert' else 'placement'
            receiver_frame=receiver.frames[key] if key in receiver.frames else Pose(position_m=receiver.anchors[key])
            goal=transform(receiver.pose)@transform(receiver_frame)@np.linalg.inv(transform(source.interaction.mating_pose))
            error=float(np.abs(goal-transform(cue.goal_pose)).max())
            if error>1e-8:
                raise AssertionError(f'{sid} mating transform mismatch {error}')
            mesh=load_asset(str(resource(root(),source.asset)),spec.asset_axes).to_geometry()
            sampled,_=trimesh.sample.sample_surface(mesh,1536,seed=4701)
            obstacle,coverage=parts(spec,[o for o in spec.objects if o.object_id!=source.object_id]+spec.environment)
            hits=[]
            for index,t in enumerate(np.linspace(0,source.interaction.duration_s,41)):
                pose=transform(trajectory(cue,float(t)))
                points=trimesh.transform_points(sampled,pose)
                lo=points.min(axis=0);hi=points.max(axis=0)
                for oid,name,bounds,field in obstacle:
                    if np.any(lo>bounds[1]) or np.any(hi<bounds[0]):
                        continue
                    selection=((points>bounds[0]+.00075)&(points<bounds[1]-.00075)).all(axis=1)
                    if not selection.any():
                        continue
                    values=vtk.vtkDoubleArray()
                    field.EvaluateFunction(numpy_to_vtk(np.ascontiguousarray(points[selection]),deep=True),values)
                    distances=vtk_to_numpy(values)
                    penetration=distances<-.00075
                    if penetration.any():
                        hits.append({'frame':index,'elapsed_s':float(t),'obstacle':oid,'part':name,
                            'points':int(penetration.sum()),'max_depth_m':float(-distances.min())})
            rows.append({'scene_id':sid,'source_id':source.object_id,'receiver_id':receiver.object_id,
                         'independent_mating_error':error,'sampled_surface_points':1536,
                         'trajectory_samples':41,'penetration_threshold_m':.00075,'penetrations':hits,
                         'obstacle_coverage':coverage,
                         'passed':not hits and not any(c['status']=='invalid_solid_topology' for c in coverage)})
            print(sid,source.object_id,'penetrating samples',len(hits),flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    passed=all(row['passed'] for row in rows)
    args.out.write_text(json.dumps({'status':'passed' if passed else 'failed',
        'method':'VTK signed distances on validated closed mesh copies; only explicit textured label surfaces are excluded',
        'coverage':'sampled moving-source surface points; contact between unsampled surfaces remains untested',
        'model_backend_exercised':False,'results':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    if not passed:
        raise SystemExit('Geometry audit failed: penetrations or uncovered solid obstacles; inspect the saved report')


if __name__=='__main__':
    main()
