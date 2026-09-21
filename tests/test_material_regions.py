"""Actual exported material partitions, exterior rays and CAD union invariants."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import trimesh
import vtk

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.modeling import engine_hose_solids, partition_cad_parts,CAD_TESSELLATION_M
from holocue.render_validation import polydata
from panel_optical_geometry import mesh_map, material


FIXTURES = Path(__file__).parent/'fixtures/material_regions'
REFERENCE = json.loads((FIXTURES/'manifest.json').read_text())


def reference(oid, axes):
    path = FIXTURES/(oid+'.glb')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == REFERENCE[oid]['sha256']
    return mesh_map(load_asset(str(path), axes))


def ray_tree(mesh):
    mesh = mesh.copy(); mesh.process(validate=True)
    tree = vtk.vtkOBBTree(); tree.SetDataSet(polydata(mesh)); tree.BuildLocator()
    return tree


def first_hit(trees, start, end):
    distances = []
    for tree in trees:
        points = vtk.vtkPoints(); ids = vtk.vtkIdList()
        tree.IntersectWithLine(start, end, points, ids)
        distances.extend(np.linalg.norm(np.asarray(points.GetPoint(i))-start)
                         for i in range(points.GetNumberOfPoints()))
    return min(distances) if distances else None


def assert_exterior_rays(old, new, tolerance_m=3e-6):
    bounds = np.asarray([mesh.bounds for mesh in old.values()])
    lo, hi = bounds[:, 0].min(axis=0), bounds[:, 1].max(axis=0)
    trees = [ray_tree(mesh) for mesh in old.values()]
    candidate = [ray_tree(mesh) for mesh in new.values()]
    observed = []
    for axis in range(3):
        others = [i for i in range(3) if i != axis]
        for u, v in itertools.product(np.linspace(.10, .90, 7), repeat=2):
            point = (lo+hi)/2
            point[others] = lo[others]+np.asarray([u, v])*(hi-lo)[others]
            for sign in (-1, 1):
                start = point.copy(); end = point.copy()
                start[axis] = lo[axis]-.10 if sign==1 else hi[axis]+.10
                end[axis] = hi[axis]+.10 if sign==1 else lo[axis]-.10
                before = first_hit(trees, start, end)
                after = first_hit(candidate, start, end)
                assert (before is None) == (after is None)
                if before is not None:
                    observed.append(abs(before-after))
    assert len(observed) >= 100
    assert max(observed) < tolerance_m, max(observed)
    return {'ray_hits':len(observed),'max_distance_change_m':float(max(observed)),
            'tolerance_m':tolerance_m}


def assert_container_partition(spec, obj, actual):
    old = reference(obj.object_id, spec.asset_axes)
    expected_nodes = {f'{obj.object_id}/{i:04d}_panel' for i in range(5)}
    assert expected_nodes.issubset(actual)
    for name in expected_nodes:
        assert material(actual[name]) == material(old[name])
        candidate = actual[name].copy(); candidate.process(validate=True)
        assert candidate.is_watertight and candidate.is_winding_consistent
        assert candidate.volume > 0 and len(candidate.split()) == 1
    assert_exterior_rays({key: old[key] for key in expected_nodes},
                         {key: actual[key] for key in expected_nodes})


@pytest.mark.parametrize('sid,oid',[('drone_bench','BAY'),('shelf_picking','BLUE'),
                                  ('shelf_picking','BASKET')])
def test_exported_container_union_and_materials(sid,oid):
    spec=load_scene(sid);obj=next(obj for obj in spec.objects if obj.object_id==oid)
    actual=mesh_map(load_asset(str(root()/obj.asset),spec.asset_axes))
    assert_container_partition(spec,obj,actual)
    old=reference(oid,spec.asset_axes)
    assert set(actual)==set(old)
    for name in actual:
        if name not in {f'{oid}/{i:04d}_panel' for i in range(5)}:
            np.testing.assert_array_equal(actual[name].vertices,old[name].vertices)
            np.testing.assert_array_equal(actual[name].faces,old[name].faces)
            assert material(actual[name])==material(old[name])


@pytest.mark.parametrize('oid',['BAY','BLUE','BASKET','workstation'])
def test_cad_partition_conserves_union_volume_and_has_disjoint_interiors(oid,tmp_path):
    if oid=='workstation':
        shapes=engine_hose_solids()
    else:
        spec=load_scene(REFERENCE[oid]['scene_id'])
        obj=next(obj for obj in spec.objects if obj.object_id==oid)
        x,y,z=obj.size_m;t=min(x,y,z)*.075
        panels=[((x,y,t),(0,0,-z/2+t/2)),((t,y,z),(-x/2+t/2,0,0)),
                ((t,y,z),(x/2-t/2,0,0)),((x-2*t,t,z),(0,-y/2+t/2,0)),
                ((x-2*t,t,z),(0,y/2-t/2,0))]
        shapes=[cq.Workplane('XY').box(*size).edges().fillet(min(min(size)*.16,.006))
                .translate(position) for size,position in panels]
    regions=list(partition_cad_parts(shapes))
    whole=shapes[0]
    for shape in shapes[1:]:whole=whole.union(shape)
    assert whole.val().isValid() and len(whole.solids().vals())==1
    total=sum(region.val().Volume(tol=1e-12) for region in regions)
    rebuilt=regions[0]
    for region in regions[1:]:
        rebuilt=rebuilt.union(region)
    # Set equality measures conservation independently of numerical volume
    # integration on differently subdivided trimmed surfaces.
    assert not whole.cut(rebuilt).solids().vals()
    assert not rebuilt.cut(whole).solids().vals()
    (tmp_path/(oid+'_cad_conservation.json')).write_text(json.dumps({
        'missing_solids':0,'added_solids':0,
        'partition_volume_m3':total,'union_volume_m3':whole.val().Volume(tol=1e-12),
        'volume_integration_difference_m3':abs(total-whole.val().Volume(tol=1e-12))},indent=2))
    for a,b in itertools.combinations(regions,2):
        assert sum(solid.Volume() for solid in a.intersect(b).solids().vals())<1e-12


def test_exported_engine_exterior_rays_and_unaffected_components(tmp_path):
    spec=load_scene('engine_bay')
    old=reference('workstation',spec.asset_axes)
    new=mesh_map(load_asset(str(root()/spec.environment[0].asset),spec.asset_axes))
    parts={key for key in old if key.endswith(('0052_tube','0053_tube','0054_rounded_part'))}
    assert len(parts)==3 and old.keys()==new.keys()
    # Boolean face subdivision retessellates curved roof patches within the
    # declared CAD mesh deflection. Planar container faces retain the 3 um check.
    result=assert_exterior_rays({key:old[key] for key in parts},{key:new[key] for key in parts},
                               CAD_TESSELLATION_M)
    (tmp_path/'exterior_readback.json').write_text(json.dumps(result,indent=2))
    for key in old:
        assert material(old[key])==material(new[key])
        if key not in parts:
            np.testing.assert_array_equal(old[key].vertices,new[key].vertices)
            np.testing.assert_array_equal(old[key].faces,new[key].faces)
