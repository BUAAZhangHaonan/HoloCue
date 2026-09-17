"""Run with the server's existing Blender, no add-on or pip package required.
blender -b --python scripts/scenes/build_blender_scene.py -- --scene control_panel --render
"""
import bpy,sys,json,argparse,math,os
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
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
# Filmic keeps near-white objects and the light bench out of highlight clipping;
# labels are PIL overlays (annotate_render.py) so in-render hue fidelity is moot.
scene.view_settings.view_transform='Filmic'
# Project GLBs store Z-up world-frame geometry (the trimesh/Viser contract); Blender's
# glTF importer unconditionally applies a -90 deg X rotation, so every import is
# counter-rotated on its parent empty. Without this, objects render tipped sideways
# and displaced from their JSON pose (early renders had this defect).
from mathutils import Quaternion
CORR=Quaternion((2**-.5,-2**-.5,0.,0.))
scene.world.color=(.75,.78,.82)
ortho=spec.get('render_hints',{}).get('ortho_scale_m',.91);k=max(1.,ortho/.91)
label_mat=bpy.data.materials.new('HCLabelMat');label_mat.use_nodes=True
lb=label_mat.node_tree.nodes['Principled BSDF'];lb.inputs['Base Color'].default_value=(.85,.38,.06,1.)
lb.inputs['Emission'].default_value=(.98,.45,.08,1.);lb.inputs['Emission Strength'].default_value=1.
for o in spec['objects']:
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/o['asset']))
    imported=list(set(bpy.data.objects)-before)
    parent=bpy.data.objects.new('HC_'+o['object_id'],None);scene.collection.objects.link(parent)
    for child in imported:
        if child.parent is None:child.parent=parent
    parent.location=o['pose']['position_m'];parent.rotation_mode='QUATERNION'
    parent.rotation_quaternion=Quaternion(o['pose']['wxyz'])@CORR
    parent['holocue_object_id']=o['object_id']
    # Stable parent names provide the shared scene binding for the polling bridge.
    # Labels anchor to the imported mesh's real world bbox: glTF Y-up assets can sit
    # several cm away from the JSON pose inside Blender, which buried flat pose-based
    # labels inside the mesh (invisible in every early render). matrix_world needs a
    # depsgraph update after parenting or every bbox reads as the stale local one.
    bpy.context.view_layer.update()
    stack=list(parent.children);lo=Vector((1e9,)*3);hi=Vector((-1e9,)*3)
    while stack:
        n=stack.pop()
        stack.extend(n.children)
        if n.type=='MESH':
            for v in n.bound_box:
                w=n.matrix_world@Vector(v)
                lo.x=min(lo.x,w.x);lo.y=min(lo.y,w.y);lo.z=min(lo.z,w.z)
                hi.x=max(hi.x,w.x);hi.y=max(hi.y,w.y);hi.z=max(hi.z,w.z)
    if lo.x<1e8:
        label_pos=Vector((lo.x-.005,lo.y-.055*k,hi.z+.012))
    else:
        label_pos=Vector(o['pose']['position_m'])+Vector((-.03,-.07,.005))*k
    bpy.ops.object.text_add(location=label_pos)
    text=bpy.context.object;text.name='HC_LABEL_'+o['object_id'];text.data.body=o['object_id'];text.data.size=.055*k
    text.data.extrude=.006*k;text.data.offset=.0008*k
    text.data.materials.append(label_mat)
    # In-scene FONT labels proved unreliable under Cycles color transforms; they stay in
    # the file for the live bridge but are excluded from offline renders, which get
    # deterministic PIL annotations instead (scripts/annotate_render.py).
    text.hide_render=True
for p in spec.get('environment',[]):
    # Environment scenery: imported the same glTF way, scaled on the parent empty, no text labels.
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/p['asset']))
    imported=list(set(bpy.data.objects)-before)
    parent=bpy.data.objects.new('HC_ENV_'+p['prop_id'],None);scene.collection.objects.link(parent)
    for child in imported:
        if child.parent is None:child.parent=parent
    pose=p.get('pose',{});parent.location=pose.get('position_m',(0.,0.,0.));parent.rotation_mode='QUATERNION'
    parent.rotation_quaternion=Quaternion(pose.get('wxyz',(1.,0.,0.,0.)))@CORR
    parent.scale=p.get('scale_m',(1.,1.,1.));parent['holocue_prop_id']=p['prop_id']
if not spec.get('environment'):
    # Bench top at exactly z=0 so objects posed at z=0 read as seated on it.
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,.08,-.009));bench=bpy.context.object;bench.name='Bench';bench.scale=(.67,.59,.018)
    mat=bpy.data.materials.new('BenchSoft');mat.diffuse_color=(.72,.78,.82,1);bench.data.materials.append(mat)
# Fill lights track the scene look-at so off-origin scenes (rack/pit) stay lit.
# Enclosed scenes (engine_bay garage) may override via render_hints.fill_lights:
# the k-scaled legacy rig lands above/behind solid env geometry (garage ceiling
# z=2.98 occluded all three lights; official render mean luma 20 vs 74-121 for
# the open environment-rich scenes, evidence runs/engine_round/build_all_engine.log).
aim=Vector(spec['camera_look_at_m'])
rig=spec.get('render_hints',{}).get('fill_lights')
if rig:
    for x,y,z,power,size in rig:
        bpy.ops.object.light_add(type='AREA',location=Vector((x,y,z)));light=bpy.context.object
        light.data.energy=power;light.data.shape='DISK';light.data.size=size
        light.rotation_euler=(aim-light.location).to_track_quat('-Z','Y').to_euler()
else:
    for pos,power,size in [((.4,-.5,1.0),90,.7),((-.6,.3,.7),70,.6),((0,.6,1.),70,.4)]:
        bpy.ops.object.light_add(type='AREA',location=Vector(pos)*k+Vector((0,0,aim.z)));light=bpy.context.object;light.data.energy=power*k;light.data.shape='DISK';light.data.size=size*k
        light.rotation_euler=(aim-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=spec['camera_position_m']);camera=bpy.context.object
camera.rotation_euler=(Vector(spec['camera_look_at_m'])-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=ortho;camera.data.lens=45;scene.camera=camera
scene['holocue_scene_id']=a.scene
scene['holocue_render_kind']='geometric_interaction_preview'
out=Path(a.out) if a.out else ROOT/'assets/blender'/f'{a.scene}.blend';out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
if a.render:
    scene.render.filepath=str(ROOT/'runs'/f'{a.scene}_blender.png');Path(scene.render.filepath).parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.render.render(write_still=True)
    from bpy_extras import object_utils
    px={n.name[len('HC_LABEL_'):]:[round(object_utils.world_to_camera_view(scene,camera,o.location).x*1280),
        round((1-object_utils.world_to_camera_view(scene,camera,o.location).y)*900)]
        for n in bpy.data.objects for o in [n] if n.name.startswith('HC_LABEL_')}
    (ROOT/'runs'/f'{a.scene}_label_px.json').write_text(json.dumps(px))
print(json.dumps({'saved':str(out),'scene_id':a.scene,'device':'CPU','rendered':a.render}))
