"""Run with the server's existing Blender, no add-on or pip package required.
blender -b --python scripts/build_blender_scene.py -- --scene control_panel --render
"""
import bpy,sys,json,argparse,math,os
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--scene',default='control_panel');p.add_argument('--render',action='store_true');p.add_argument('--out',default='')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
path=ROOT/'configs/scenes'/f'{a.scene}.json'
if path.parent!=ROOT/'configs/scenes':raise ValueError('invalid scene path')
spec=json.loads(path.read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
scene.render.threads_mode='FIXED';scene.render.threads=4
scene.render.resolution_x=1280;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.75,.78,.82)
for o in spec['objects']:
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/o['asset']))
    imported=list(set(bpy.data.objects)-before)
    parent=bpy.data.objects.new('HC_'+o['object_id'],None);scene.collection.objects.link(parent)
    for child in imported:
        if child.parent is None:child.parent=parent
    parent.location=o['pose']['position_m'];parent.rotation_mode='QUATERNION';parent.rotation_quaternion=o['pose']['wxyz']
    parent['holocue_object_id']=o['object_id']
    # Stable parent names provide the shared scene binding for the polling bridge.
    bpy.ops.object.text_add(location=Vector(o['pose']['position_m'])+Vector((-.026,-.065,.004)))
    text=bpy.context.object;text.name='HC_LABEL_'+o['object_id'];text.data.body=o['object_id'];text.data.size=.026
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,.08,-.015));bench=bpy.context.object;bench.name='Bench';bench.scale=(.67,.59,.018)
mat=bpy.data.materials.new('BenchSoft');mat.diffuse_color=(.72,.78,.82,1);bench.data.materials.append(mat)
for pos,power,size in [((.4,-.5,1.0),90,.7),((-.6,.3,.7),70,.6),((0,.6,1.),70,.4)]:
    bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light.data.energy=power;light.data.shape='DISK';light.data.size=size
    light.rotation_euler=(Vector((0,.1,.02))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=spec['camera_position_m']);camera=bpy.context.object
camera.rotation_euler=(Vector(spec['camera_look_at_m'])-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=.91;camera.data.lens=45;scene.camera=camera
scene['holocue_scene_id']=a.scene
scene['holocue_render_kind']='geometric_interaction_preview'
out=Path(a.out) if a.out else ROOT/'assets/blender'/f'{a.scene}.blend';out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
if a.render:
    scene.render.filepath=str(ROOT/'runs'/f'{a.scene}_blender.png');Path(scene.render.filepath).parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.render.render(write_still=True)
print(json.dumps({'saved':str(out),'scene_id':a.scene,'device':'CPU','rendered':a.render}))
