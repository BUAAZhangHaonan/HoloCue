"""Screen-space label rectangles and camera fit on all real scene contracts."""
import itertools
import numpy as np
import pytest
from holocue.assets import load_asset
from holocue.annotations import border_annotations,annotation_margin
from holocue.camera import corners,fit,project,workspace_points
from holocue.config import load_scene,list_scenes,root
from holocue.spatial import transform_points


@pytest.mark.parametrize('scene_id',[item['scene_id'] for item in list_scenes()])
@pytest.mark.parametrize('aspect',[.4,.45,.75,1.,1.6,2.4])
def test_all_object_labels_are_inside_frame_and_disjoint(scene_id,aspect):
    spec=load_scene(scene_id);points=[];anchors={}
    for obj in spec.objects:
        mesh=load_asset(str(root()/obj.asset),spec.asset_axes)
        points.extend(transform_points(obj.pose,corners(mesh.bounds)))
        anchor=(mesh.bounds[0]+mesh.bounds[1])/2;anchor[2]=mesh.bounds[1,2]+.018
        anchors[obj.object_id]=transform_points(obj.pose,np.asarray([obj.anchors.get('label',anchor)]))[0]
    direction=np.asarray(spec.camera_position_m)-spec.camera_look_at_m
    pos,look=fit(workspace_points(spec,points),direction,spec.render_hints.fov_y_deg,aspect,
        annotation_margin(list(anchors),aspect,spec.render_hints.viewport_margin))
    labels=border_annotations(anchors,pos,look,spec.render_hints.fov_y_deg,aspect)
    assert {label.object_id for label in labels}==set(anchors)
    geometry,_=project(points,pos,look,spec.render_hints.fov_y_deg,aspect)
    for label in labels:
        x0,y0,x1,y1=label.rectangle_ndc
        assert -1<x0<x1<1 and -1<y0<y1<1
        assert not np.any((geometry[:,0]>x0)&(geometry[:,0]<x1)&(geometry[:,1]>y0)&(geometry[:,1]<y1))
        np.testing.assert_allclose(label.leader[0],anchors[label.object_id],atol=1e-7)
        xy,_=project([label.world_position],pos,look,spec.render_hints.fov_y_deg,aspect)
        endpoint=x1 if label.anchor=='center-right' else x0
        np.testing.assert_allclose(xy[0],[endpoint,(y0+y1)/2],atol=1e-7)
    for a,b in itertools.combinations(labels,2):
        a=a.rectangle_ndc;b=b.rectangle_ndc
        assert a[2]<=b[0] or b[2]<=a[0] or a[3]<=b[1] or b[3]<=a[1]


def test_single_visible_annotation_has_valid_border_anchor():
    anchors={'A':np.array([0.,0.,0.]),'B':np.array([0.,-2.,0.])}
    rows=border_annotations(anchors,(0.,-1.,0.),(0.,0.,0.),42.,1.6)
    assert len(rows)==1 and rows[0].object_id=='A'
    assert rows[0].anchor in ('center-left','center-right')
    assert np.isfinite(rows[0].leader).all()


def test_outside_view_annotations_are_absent():
    anchors={'A':np.array([0.,-2.,0.]),'B':np.array([20.,0.,0.])}
    assert border_annotations(anchors,(0.,-1.,0.),(0.,0.,0.),42.,1.6)==[]
