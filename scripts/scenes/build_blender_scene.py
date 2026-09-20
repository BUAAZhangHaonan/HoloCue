"""Import a standard glTF workstation and build a CPU-rendered Blender scene."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[2]


def transform(data):
    return Matrix.Translation(Vector(data['position_m'])) @ Quaternion(data['wxyz']).to_matrix().to_4x4()


def import_asset(label,asset,pose,scale=(1,1,1)):
    path=(ROOT/asset).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise FileNotFoundError(path)
    previous=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported=set(bpy.data.objects)-previous
    parent=bpy.data.objects.new(label,None)
    bpy.context.scene.collection.objects.link(parent)
    for obj in imported:
        if obj.parent not in imported:
            local=obj.matrix_world.copy()
            obj.parent=parent
            obj.matrix_parent_inverse=Matrix.Identity(4)
            obj.matrix_basis=local
    parent.matrix_world=transform(pose)
    parent.scale=scale
    return parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True)
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    temp=Path(os.environ['TMPDIR']).resolve()
    if not temp.is_relative_to(ROOT):
        raise ValueError('TMPDIR must be inside the project directory')
    temp.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.temporary_directory=str(temp)
    bpy.context.preferences.filepaths.save_version=0
    payload=json.loads((ROOT/'runs/simulation/blender_payloads'/f'{args.scene}.json').read_text())
    spec=payload['scene']
    if spec['asset_axes']!='gltf_y_up':
        raise ValueError('Blender builder requires standard Y-up glTF')
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for obj in spec['objects']:
        import_asset('HC_OBJECT_'+obj['object_id'],obj['asset'],obj['pose'])
    for env in spec['environment']:
        import_asset('HC_ENV_'+env['prop_id'],env['asset'],env['pose'],env['scale_m'])
    camera_data=bpy.data.cameras.new('HoloCueCamera')
    camera=bpy.data.objects.new('HoloCueCamera',camera_data)
    bpy.context.scene.collection.objects.link(camera)
    position=Vector(payload['camera']['position_m']);look=Vector(payload['camera']['look_at_m'])
    camera.location=position
    camera.rotation_mode='QUATERNION';camera.rotation_quaternion=(look-position).to_track_quat('-Z','Y')
    camera_data.type='PERSP';camera_data.sensor_fit='VERTICAL'
    camera_data.angle_y=math.radians(spec['render_hints']['fov_y_deg'])
    camera_data.clip_start=.002;camera_data.clip_end=100.
    scene=bpy.context.scene;scene.camera=camera
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.transparent_max_bounces=128
    scene.render.resolution_x=payload['width'];scene.render.resolution_y=payload['height']
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.70,.76,.82,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45
    radius=max((position-look).length,.5)
    for index,(offset,energy,color) in enumerate([((1,-1.2,2),15,(1.,.94,.84)),((-1,-.2,1.4),10,(.82,.91,1.)),((0,1,1.8),12,(1.,1.,1.))]):
        data=bpy.data.lights.new('Softbox_'+str(index),'AREA')
        light=bpy.data.objects.new('Softbox_'+str(index),data);scene.collection.objects.link(light)
        light.location=look+Vector(offset)*radius
        light.rotation_euler=(look-light.location).to_track_quat('-Z','Y').to_euler()
        data.energy=energy*radius**2;data.size=radius*.9;data.color=color
    scene.view_settings.view_transform='Filmic'
    scene.view_settings.look='Medium High Contrast'
    scene['holocue_scene_id']=spec['scene_id']
    scene['holocue_asset_axes']='gltf_y_up'
    scene['holocue_renderer']='analytic_gaussian_preview'
    output=ROOT/'scenes'/spec['scene_id']/'scene.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    if args.render:
        scene.render.filepath=str(ROOT/'runs/simulation'/f'{spec["scene_id"]}_blender.png')
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
