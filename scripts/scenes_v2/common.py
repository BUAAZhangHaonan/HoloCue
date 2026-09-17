"""Shared Blender-side helpers for v2 scene kit builds (Blender 3.1.2 API).
Importable inside kit scripts:  from common import *
Everything runs CPU-only; kit scripts are launched via scripts/resource_guard.py.
"""
import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector, Euler, Quaternion

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT/'assets/downloads/polyhaven/textures'
ENV = ROOT/'assets/meshes/env'
OUT_RUNS = ROOT/'runs/scene_v2'

# Project GLBs store Z-up world-frame geometry (the trimesh/Viser contract). Blender's
# glTF importer always applies -90 deg X, so every re-import is counter-rotated on its
# parent empty; exports disable the exporter's Y-up conversion to keep files Z-up.
CORR = Quaternion((2**-.5, -2**-.5, 0., 0.))

_img_cache = {}
def _img(tex_id: str, prefix: str):
    key = (tex_id, prefix)
    if key in _img_cache and _img_cache[key]:
        return _img_cache[key]
    path = TEX/tex_id/f'{prefix}_1k.jpg'
    if not path.exists():
        return None
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = 'sRGB' if prefix == 'Diffuse' else 'Non-Color'
    _img_cache[key] = img
    return img

def pbr(name: str, tex_id: str, scale=1.0, metallic=None, roughness=None):
    """Principled material from a PolyHaven texture set. scale = UV tiling multiplier."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeTexCoord'); uv.location = (-1400, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-1200, 0)
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(uv.outputs['UV'], mp.inputs['Vector'])
    def slot(prefix, target, non_color_ok=True):
        img = _img(tex_id, prefix)
        if img is None:
            return None
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.location = (-1000, -300*len(nt.nodes) % 1200 - 300)
        nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
        if target == 'Normal':
            nrm = nt.nodes.new('ShaderNodeNormalMap'); nrm.location = (-600, -700)
            nt.links.new(tex.outputs['Color'], nrm.inputs['Color'])
            nt.links.new(nrm.outputs['Normal'], bsdf.inputs['Normal'])
        else:
            nt.links.new(tex.outputs['Color'], bsdf.inputs[target])
        return tex
    slot('Diffuse', 'Base Color')
    slot('nor_gl', 'Normal')
    slot('Rough', 'Roughness')
    slot('Metal', 'Metallic')
    if metallic is not None:
        bsdf.inputs['Metallic'].default_value = metallic
    if roughness is not None:
        bsdf.inputs['Roughness'].default_value = roughness
    return mat

def flat(name: str, rgba, metallic=0.0, roughness=0.55, emissive=None, emission_strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = tuple(rgba)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emissive is not None:
        bsdf.inputs['Emission'].default_value = tuple(emissive)
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    return mat

def box(name, size, location, mat, bevel=0.004, **kw):
    # Create at the origin so transform_apply cannot bake a translation into the
    # mesh (Blender 3.1: applying scale with location != 0 displaced boxes to 2x
    # their location), then move the object. A size=1 primitive spans +-0.5, so
    # the object scale needed for a total dimension of `size` is `size` itself.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    o.scale = (size[0], size[1], size[2])
    if bevel:
        m = o.modifiers.new('Bevel', 'BEVEL'); m.width = bevel; m.segments = 2; m.limit_method = 'ANGLE'
    if mat: o.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.location = location
    return o

def cyl(name, radius, depth, location, mat, rot=(0, 0, 0), vertices=48, **kw):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location, rotation=rot, vertices=vertices)
    o = bpy.context.object; o.name = name
    if mat: o.data.materials.append(mat)
    return o

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for x in list(blk):
            if not x.users:
                blk.remove(x)

def deselect_all():
    for o in bpy.data.objects:
        o.select_set(False)

def export_glb(objs, out_path: Path):
    """Export the given objects as one GLB storing Z-up world-frame geometry."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(out_path), export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=False)
    deselect_all()
    return out_path

def import_glb(path: Path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]

def parent_to(name, objs, location=(0, 0, 0), wxyz=(1, 0, 0, 0)):
    """Group imported GLB contents under an empty at the JSON pose, canceling the
    glTF importer's -90 deg X rotation (project GLBs are authored Z-up-as-stored)."""
    p = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(p)
    p.location = location
    p.rotation_mode = 'QUATERNION'
    p.rotation_quaternion = Quaternion(wxyz) @ CORR
    for o in objs:
        if o.parent is None:
            o.parent = p
    return p

def world_bg(color=(0.62, 0.66, 0.72, 1.0), strength=0.85):
    world = bpy.context.scene.world or bpy.data.worlds.new('World')
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = color
    bg.inputs['Strength'].default_value = strength

def _framed_extents(objs):
    """World bbox of the given objects."""
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for o in objs:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, w.x); lo.y = min(lo.y, w.y); lo.z = min(lo.z, w.z)
            hi.x = max(hi.x, w.x); hi.y = max(hi.y, w.y); hi.z = max(hi.z, w.z)
    return lo, hi

def _projected_size(lo, hi, cam_pos, look_at):
    """Extent of the bbox projected onto the camera plane (width, height) in meters."""
    import mathutils
    fwd = (look_at - cam_pos).normalized()
    ref = Vector((0, 0, 1)).cross(fwd)
    if ref.length < 1e-6:
        ref = Vector((1, 0, 0)).cross(fwd)
    right = ref.normalized()
    up = fwd.cross(right).normalized()
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    # no abs() before max-min: the projected extent must span corners on both
    # sides of the camera axis, otherwise the auto-fit silently under-frames.
    u = [(c - cam_pos) @ right for c in corners]
    v = [(c - cam_pos) @ up for c in corners]
    return max(u)-min(u), max(v)-min(v)

def light_rig(center: Vector, extent: float, energy=2.2):
    """Three-point area rig scaled to the scene extent (indoor look)."""
    k = max(extent, 0.4)
    for pos, e, size in [((center.x+.8*k, center.y-1.1*k, center.z+1.3*k), energy*140*k, .8*k),
                         ((center.x-1.1*k, center.y+.4*k, center.z+.9*k), energy*80*k, .7*k),
                         ((center.x+.1*k, center.y+1.2*k, center.z+1.5*k), energy*60*k, .5*k)]:
        bpy.ops.object.light_add(type='AREA', location=pos)
        l = bpy.context.object
        l.data.energy = e; l.data.shape = 'DISK'; l.data.size = size
        l.rotation_euler = (center - l.location).to_track_quat('-Z', 'Y').to_euler()

def sun(energy=2.5, rotation_deg=(45, 0, 30)):
    bpy.ops.object.light_add(type='SUN', rotation=Euler([math.radians(a) for a in rotation_deg], 'XYZ'))
    bpy.context.object.data.energy = energy

def render_preview(out_name: str, cam_pos, look_at, objs=None, ortho=None, persp_fov=None,
                   res=(1600, 1120), samples=96, engine='CYCLES'):
    """Render a preview PNG; auto-fit ortho scale when ortho=='auto'. Returns dict of settings."""
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.cycles.device = 'CPU'; sc.cycles.samples = samples
    sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    cam.rotation_euler = (Vector(look_at) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    used = {}
    if persp_fov:
        cam.data.type = 'PERSP'; cam.data.lens = persp_fov
        used['projection'] = f'persp lens {persp_fov}mm'
    else:
        cam.data.type = 'ORTHO'
        if ortho in (None, 'auto'):
            lo, hi = _framed_extents(objs if objs else bpy.data.objects)
            w, h = _projected_size(lo, hi, Vector(cam_pos), Vector(look_at))
            aspect = res[0]/res[1]
            ortho = max(w, h*aspect)*1.08
        cam.data.ortho_scale = ortho
        used['projection'] = f'ortho {ortho:.2f}'
    OUT_RUNS.mkdir(parents=True, exist_ok=True)
    out = OUT_RUNS/out_name
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    used['path'] = str(out); used['res'] = res; used['samples'] = samples
    print(json.dumps({'render': used}), flush=True)
    return used

def write_scene_json(scene_id: str, spec: dict):
    path = ROOT/'configs/scenes'/f'{scene_id}.json'
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'scene_json': str(path)}), flush=True)
    return path
