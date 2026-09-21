"""Client-scoped scene renderer with shared geometric and response contracts."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation
import viser

from .assets import load_asset,resource
from .camera import corners,fit,inspect_view,workspace_points,detail_view,basis,focus_point,retreat_to_fit,inspection_points
from .config import root
from .models import SceneSpec,DisplayPacket
from .response import splat_arrays,profile,envelope
from .spatial import transform_points,trajectory,ActionClock
from .annotations import annotation_margin,border_annotations


def selected_cue_view(spec,packet,current_poses,elapsed,object_id,mode,
                               position,look_at,up,aspect,brightness=1.):
    """One view selection fits actual centers with nominal focused cue width.

    The camera basis remains fixed. Original uncut views are unchanged; clipped
    cues trigger a fit of target geometry plus nominal cue envelope. Moving the
    camera and focus plane together leaves relative defocus intact.
    Only camera framing uses the same profile's zero-defocus width; the actual
    arrays still use their original per-point optical response. This function
    is never called by a user focus/brightness change or tick.
    """
    if mode not in ('detail','inspection') or packet is None:
        return position,look_at
    obj=next(o for o in spec.objects if o.object_id==object_id)
    inspection=mode=='inspection' or any(c.target_id==object_id and c.action=='inspect_back' for c in packet.cues)
    right,vertical,forward=basis(position,look_at,up)
    point=focus_point(obj,current_poses[object_id],inspection)
    focus=float((point-np.asarray(position))@forward)
    if focus<=0:
        raise ValueError('selected target lies behind the camera')
    directions=np.asarray([-right-vertical,right-vertical,right+vertical,-right+vertical])
    envelopes=[]
    for cue in packet.cues:
        if cue.target_id!=object_id or cue.n_gaussians<=0:
            continue
        pose=trajectory(cue,elapsed.get(cue.task_id,0.))
        centers,covariance,_,opacity=splat_arrays(spec,cue,pose,position,look_at,focus,brightness)
        visible=opacity[:,0]>0
        centers=transform_points(pose,centers[visible])
        calibration=profile()
        nominal_width,_,_=envelope(cue.sigma_value,0.,calibration)
        radius=3*float(nominal_width)*calibration.visual_magnification/2
        envelopes.append((centers[:,None,:]+radius*directions).reshape(-1,3))
    if not envelopes:
        return position,look_at
    points=np.concatenate(envelopes)
    necessary=retreat_to_fit(points,position,look_at,spec.render_hints.fov_y_deg,aspect,up)
    if np.array_equal(np.asarray(necessary),np.asarray(position)):
        return position,look_at
    first_cue=next((c for c in packet.cues if c.target_id==object_id),None)
    if mode=='inspection' or (mode=='detail' and first_cue is not None and first_cue.action=='inspect_back'):
        target_points=inspection_points(obj,current_poses[object_id])
    else:
        asset=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
        target_points=transform_points(current_poses[object_id],corners(asset.bounds))
    return fit(np.concatenate([target_points,points]),-forward,spec.render_hints.fov_y_deg,
               aspect,spec.render_hints.viewport_margin,up)


class SceneRenderer:
    def __init__(self,client: viser.ClientHandle,spec: SceneSpec):
        self.client=client
        self.spec=spec
        self.objects={o.object_id:o for o in spec.objects}
        self.frames={}
        self.labels={}
        self.label_anchors={}
        self.annotation_key=None
        self.cues={}
        self.packet=None
        self.clock=ActionClock()
        self.view_mode='workspace'
        self.selected_id=spec.objects[0].object_id
        self.last_response=-1.
        self.response_key=None
        self.guidance_enabled=True
        self.guidance_brightness=1.
        self.current_poses={o.object_id:o.pose for o in spec.objects}
        self.handles=[]
        scene=client.scene
        scene.set_up_direction('+z')
        # Modest HDR fill preserves white markings and recessed surface contrast.
        scene.configure_environment_map('studio',background=False,environment_intensity=.1,
            environment_wxyz=spec.render_hints.environment_wxyz)
        # Direct lighting keeps material shading without approximate cascade
        # shadow bands obscuring small inspection surfaces and printed labels.
        scene.configure_default_lights(enabled=True,cast_shadow=False)
        self.environment=scene.add_frame('/workspace/environment',show_axes=False)
        self.handles.append(self.environment)
        correction=Rotation.from_euler('x',90,degrees=True).as_quat(scalar_first=True)
        if spec.asset_axes=='project_z_up':
            correction=(1.,0.,0.,0.)
        for p in spec.environment:
            path=f'/workspace/environment/{p.prop_id}'
            parent=scene.add_frame(path,show_axes=False,position=p.pose.position_m,
                                   wxyz=p.pose.wxyz,scale=p.scale_m)
            child=scene.add_glb(path+'/asset',resource(root(),p.asset).read_bytes(),
                               wxyz=correction,cast_shadow=True,receive_shadow=True)
            self.handles.extend([parent,child])
        for obj in spec.objects:
            path=f'/workspace/objects/{obj.object_id}'
            parent=scene.add_frame(path,show_axes=False,position=obj.pose.position_m,wxyz=obj.pose.wxyz)
            child=scene.add_glb(path+'/asset',resource(root(),obj.asset).read_bytes(),
                               wxyz=correction,cast_shadow=True,receive_shadow=True)
            local=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
            point=np.array([(local.bounds[0,0]+local.bounds[1,0])/2,
                            (local.bounds[0,1]+local.bounds[1,1])/2,local.bounds[1,2]+.018])
            point=np.asarray(obj.anchors.get('label',point),dtype=float)
            label=scene.add_label('/annotations/'+obj.object_id,obj.object_id,
                visible=False,font_size_mode='scene',font_scene_height=.02,
                depth_test=False,anchor='center-center')
            self.label_anchors[obj.object_id]=point
            self.frames[obj.object_id]=parent;self.labels[obj.object_id]=label
            self.handles.extend([parent,child,label])
        self.leaders=scene.add_line_segments('/annotations/leaders',
            points=np.empty((0,2,3),dtype=np.float32),colors=(109,126,138),
            thickness=1.,thickness_units='screen',visible=False)
        self.handles.append(self.leaders)

    def update_annotations(self):
        visible=self.view_mode=='workspace'
        if not visible:
            for label in self.labels.values():
                label.visible=False
            self.leaders.visible=False
            self.annotation_key=None
            return
        cam=self.client.camera
        key=(tuple(cam.position),tuple(cam.look_at),tuple(cam.up_direction),
             cam.aspect,cam.fov,tuple((oid,pose.position_m,pose.wxyz)
                                      for oid,pose in sorted(self.current_poses.items())))
        if key==self.annotation_key:
            return
        anchors={oid:transform_points(self.current_poses[oid],np.asarray([point]))[0]
                 for oid,point in self.label_anchors.items()}
        layout=border_annotations(anchors,cam.position,cam.look_at,
                                  np.rad2deg(cam.fov),cam.aspect,cam.up_direction)
        for label in self.labels.values():
            label.visible=False
        for item in layout:
            label=self.labels[item.object_id]
            label.position=item.world_position
            label.font_scene_height=item.text_height_m
            label.anchor=item.anchor
            label.visible=True
        self.leaders.points=np.asarray([item.leader for item in layout],
                                       dtype=np.float32).reshape(-1,2,3)
        self.leaders.visible=bool(layout)
        self.annotation_key=key

    def close(self):
        for handle in self.cues.values():
            handle.remove()
        for handle in reversed(self.handles):
            handle.remove()

    def points(self,object_ids=None):
        ids=list(self.objects) if object_ids is None else object_ids
        result=[]
        for oid in ids:
            obj=self.objects[oid]
            mesh=load_asset(str(resource(root(),obj.asset)),self.spec.asset_axes)
            result.extend(transform_points(self.current_poses[oid],corners(mesh.bounds)))
        return np.asarray(result)

    def select_view(self,mode,object_id=None):
        if object_id is not None:
            if object_id not in self.objects:
                raise KeyError(object_id)
            self.selected_id=object_id
        if mode not in ('workspace','detail','inspection'):
            raise ValueError(mode)
        self.view_mode=mode
        self.annotation_key=None
        self.environment.visible=mode!='inspection'
        for oid,handle in self.frames.items():
            handle.visible=mode!='inspection' or oid==self.selected_id
            self.labels[oid].visible=False
        targets={c.task_id:c.target_id for c in self.packet.cues} if self.packet else {}
        for tid,handle in self.cues.items():
            handle.visible=mode!='inspection' or targets[tid]==self.selected_id
        cam=self.client.camera
        cam.fov=np.deg2rad(self.spec.render_hints.fov_y_deg)
        cam.near=.002;cam.far=100.
        if mode=='inspection':
            pos,look,up=inspect_view(self.objects[self.selected_id],self.current_poses[self.selected_id],
                                   self.spec.render_hints.fov_y_deg,cam.aspect)
        elif mode=='detail':
            obj=self.objects[self.selected_id]
            asset=load_asset(str(resource(root(),obj.asset)),self.spec.asset_axes)
            cue=next((c for c in self.packet.cues if c.target_id==self.selected_id),None) if self.packet else None
            direction=np.asarray(self.spec.camera_position_m)-self.spec.camera_look_at_m
            pos,look,up=detail_view(obj,self.current_poses[self.selected_id],asset.bounds,direction,
                cue.action if cue else None,self.spec.render_hints.fov_y_deg,cam.aspect,
                self.spec.render_hints.viewport_margin)
        else:
            direction=np.asarray(self.spec.camera_position_m)-self.spec.camera_look_at_m
            points=workspace_points(self.spec,self.points())
            pos,look=fit(points,direction,self.spec.render_hints.fov_y_deg,
                         cam.aspect,annotation_margin(list(self.objects),cam.aspect,
                                                     self.spec.render_hints.viewport_margin))
            up=(0.,0.,1.)
        if self.guidance_enabled:
            pos,look=selected_cue_view(self.spec,self.packet,self.current_poses,self.clock.elapsed,
                self.selected_id,mode,pos,look,up,cam.aspect,self.guidance_brightness)
        cam.up_direction=up
        cam.position=pos
        cam.look_at=look
        self.update_annotations()

    def update_packet(self,packet: DisplayPacket):
        if packet.scene_id!=self.spec.scene_id:
            raise ValueError('display packet and scene disagree')
        self.packet=packet
        if not packet.object_poses:
            raise ValueError('simulation requires versioned object poses')
        self.current_poses=packet.object_poses
        for oid,pose in packet.object_poses.items():
            self.frames[oid].position=pose.position_m
            self.frames[oid].wxyz=pose.wxyz
        keep={c.task_id for c in packet.cues if c.n_gaussians>0}
        for tid in list(self.cues):
            if tid not in keep:
                self.cues.pop(tid).remove()
        self.response_key=None
        self.annotation_key=None
        self.update_annotations()

    def focus_distance(self,object_id):
        cam=self.client.camera
        forward=np.asarray(cam.look_at)-cam.position
        forward/=np.linalg.norm(forward)
        obj=self.objects[object_id]
        inspection_focus=self.view_mode=='inspection' or (self.packet is not None and any(
            cue.target_id==object_id and cue.action=='inspect_back' for cue in self.packet.cues))
        point=focus_point(obj,self.current_poses[object_id],inspection_focus)
        depth=float((point-cam.position)@forward)
        if depth<=0:
            raise ValueError('selected target lies behind the camera')
        return depth

    def tick(self,dt,now,focus_m,brightness,enabled,running):
        self.update_annotations()
        self.guidance_enabled=enabled
        self.guidance_brightness=brightness
        if self.packet is None:
            return
        cam=self.client.camera
        moving=running and any(c.task_role=='current' and c.action in ('rotate','insert','assemble')
            and self.clock.elapsed.get(c.task_id,0.)<c.interaction.duration_s for c in self.packet.cues)
        for cue in self.packet.cues:
            self.clock.advance(cue.task_id,dt,running and cue.task_role=='current')
        refresh=(moving and now-self.last_response>=.15) or self.response_key is None
        key=(round(focus_m,4),round(brightness,3),enabled,tuple(np.round(cam.position,4)),
             tuple(np.round(cam.look_at,4)))
        refresh=refresh or key!=self.response_key
        if not refresh and not moving:
            return
        with self.client.atomic():
            for cue in self.packet.cues:
                if cue.n_gaussians<=0:
                    continue
                elapsed=self.clock.elapsed[cue.task_id]
                pose=trajectory(cue,elapsed)
                if refresh or cue.task_id not in self.cues:
                    centers,covariances,rgbs,opacities=splat_arrays(self.spec,cue,pose,cam.position,
                        cam.look_at,focus_m,brightness)
                    if cue.task_id not in self.cues:
                        self.cues[cue.task_id]=self.client.scene.add_gaussian_splats(
                            f'/guidance/{cue.task_id}',centers=centers,covariances=covariances,
                            rgbs=rgbs,opacities=opacities)
                    else:
                        self.cues[cue.task_id].set_gaussians(centers,covariances,rgbs,opacities)
                handle=self.cues[cue.task_id]
                handle.position=pose.position_m
                handle.wxyz=pose.wxyz
                handle.visible=enabled and (self.view_mode!='inspection' or cue.target_id==self.selected_id)
        if refresh:
            self.last_response=now
            self.response_key=key
