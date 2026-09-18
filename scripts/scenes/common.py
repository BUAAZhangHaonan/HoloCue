"""Shared Blender-side helpers for scene kit builds (Blender 3.1.2 API).
Importable inside kit scripts:  from common import *
Everything runs CPU-only; kit scripts are launched via scripts/guard/resource_guard.py.
"""
import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector, Euler, Quaternion

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT/'assets/downloads/polyhaven/textures'
ENV = ROOT/'assets/meshes/env'  # shared pool; scene-owned env props live in scenes/<id>/meshes/env
OUT_RUNS = ROOT/'runs/scene_v2'


def scene_kit(scene_id: str) -> Path:
    """Per-scene kit folder (config, meshes, blend, docs, reviews)."""
    return ROOT/'scenes'/scene_id


def scene_env(scene_id: str) -> Path:
    """Scene-owned environment props inside the kit."""
    return scene_kit(scene_id)/'meshes/env'


# --------------------------------------------------------------------------
# Generic as-built assertions shared by the kit builders (reviewed-design
# evidence): depth layering, ortho framing, sightline occlusion, radial-face
# back views. All checks print a JSON evidence line and raise on failure.
# --------------------------------------------------------------------------

def screen_basis(cam_pos, look):
    """(fwd, right, up) basis for a view axis from cam_pos toward look."""
    fwd = (Vector(look) - Vector(cam_pos)).normalized()
    ref = Vector((0, 0, 1)).cross(fwd)
    if ref.length < 1e-6:
        ref = Vector((1, 0, 0)).cross(fwd)
    right = ref.normalized()
    return fwd, right, fwd.cross(right).normalized()


def objs_bbox(objs):
    """World bbox of objects; caller is responsible for the depsgraph update."""
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for o in objs:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, w.x); lo.y = min(lo.y, w.y); lo.z = min(lo.z, w.z)
            hi.x = max(hi.x, w.x); hi.y = max(hi.y, w.y); hi.z = max(hi.z, w.z)
    return lo, hi


def verify_depths(cam_pos, look, rows, expect, tol=0.06, min_gap=0.3):
    """rows: {label: world point}; expect: {label: design depth m}. Asserts the
    as-built depths match the reviewed design table, and that the DISTINCT
    design layers (same-layer dual roles allowed) stay >=min_gap apart."""
    fwd = screen_basis(cam_pos, look)[0]
    got = {k: float((Vector(p) - Vector(cam_pos)) @ fwd) for k, p in rows.items()}
    for k, want in expect.items():
        assert abs(got[k] - want) <= tol, f'{k}: depth {got[k]:.3f} vs design {want}'
    layers = sorted({round(w, 1) for w in expect.values()}, reverse=True)
    gaps = {f'{a:g}m-{b:g}m': round(a - b, 3) for a, b in zip(layers, layers[1:])}
    print(json.dumps({'depth_verification': {'depths_m': {k: round(v, 3) for k, v in got.items()},
                                              'design_m': expect, 'layer_gaps_m': gaps}},
                     ensure_ascii=False), flush=True)
    assert all(g >= min_gap for g in gaps.values()), f'design layer gap < {min_gap}m: {gaps}'
    return got


def _px_range(lo, hi, cam_pos, right, up, ortho, res):
    half_v = ortho / 2 * res[1] / res[0]
    cs = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    u = [(c - cam_pos) @ right for c in cs]
    v = [(c - cam_pos) @ up for c in cs]
    px0 = int(round((min(u) + ortho / 2) / ortho * res[0]))
    px1 = int(round((max(u) + ortho / 2) / ortho * res[0]))
    py0 = int(round((half_v - max(v)) / (2 * half_v) * res[1]))
    py1 = int(round((half_v - min(v)) / (2 * half_v) * res[1]))
    return px0, py0, px1, py1


def verify_frame(cam_pos, look, ortho, items, res=(1280, 900), margin=0.06):
    """items: {label: (lo, hi) world bboxes}; asserts every item inside the
    ortho frame with >=margin*100%% border on each side. Returns the report."""
    _, right, up = screen_basis(cam_pos, look)
    out = {}
    for name, (lo, hi) in items.items():
        px0, py0, px1, py1 = _px_range(lo, hi, Vector(cam_pos), right, up, ortho, res)
        out[name] = {'px': [px0, py0, px1, py1],
                     'margin_pct': {'left': round(px0 / res[0] * 100, 1),
                                    'right': round((res[0] - px1) / res[0] * 100, 1),
                                    'top': round(py0 / res[1] * 100, 1),
                                    'bottom': round((res[1] - py1) / res[1] * 100, 1)}}
    worst = min(min(v['margin_pct'].values()) for v in out.values())
    print(json.dumps({'frame_verification': {'res': list(res), 'ortho_scale_m': round(ortho, 3),
                                              'items': out, 'worst_margin_pct': worst}},
                     ensure_ascii=False), flush=True)
    assert worst >= margin * 100 - 0.5, f'framing margin below {margin*100:.0f}%: {out}'
    return out


def _obj_bvh(obj):
    """World-space BVH for one mesh object (matrix_world baked in, so ray_cast
    takes world-frame origins/directions)."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(obj.matrix_world)
    bv = BVHTree.FromBMesh(bm)
    bm.free()
    ev.to_mesh_clear()
    return bv


def _bbox_grid(lo, hi, nu=5, nv=3, nw=5):
    def fr(a, b, n):
        return [a] if n == 1 else [a + (b - a) * k / (n - 1) for k in range(n)]
    return [Vector((x, y, z)) for x in fr(lo.x, hi.x, nu)
            for y in fr(lo.y, hi.y, nv) for z in fr(lo.z, hi.z, nw)]


def verify_visibility(cam_pos, subjects, blockers, min_frac=0.55):
    """subjects: {label: (lo, hi, own_meshes)}; blockers: mesh objects. Perspective
    rays from the camera to a bbox grid per subject; a ray is blocked when a
    blocker BVH (the subject's own meshes excluded) is hit first. Asserts each
    subject keeps >=min_frac of its grid visible."""
    bvhs = [(_obj_bvh(o), o) for o in blockers if o.type == 'MESH']
    report = {}
    for name, (lo, hi, own) in subjects.items():
        own = set(own)
        rays = [(bv, o) for bv, o in bvhs if o not in own]
        pts = _bbox_grid(lo, hi)
        vis = 0
        for p in pts:
            d = p - Vector(cam_pos)
            dist = d.length
            d = d.normalized()  # normalized() returns a copy; BVH distances are world units
            hit = False
            for bv, o in rays:
                loc, nrm, idx, dst = bv.ray_cast(Vector(cam_pos), d)
                if loc is not None and dst < dist - 1e-3:
                    hit = True
                    break
            vis += 0 if hit else 1
        frac = vis / len(pts)
        report[name] = round(frac, 3)
        assert frac >= min_frac, f'{name} visibility {frac:.2f} < {min_frac} (occluded)'
    print(json.dumps({'visibility_verification': report}), flush=True)
    return report


def verify_back_radial(name, pose, center_local, normal_local, cam_pos, tol=0.08):
    """inspect_back evidence for a subject whose info face must be a radial
    face (normal ⟂ local Z): asserts perpendicularity and that the ghost copy
    rotated 180° about local Z turns the face toward the camera."""
    pos, wxyz = pose
    pos = Vector(pos)
    q = Quaternion(wxyz)
    z = q @ Vector((0, 0, 1))
    n = q @ Vector(normal_local)
    perp = abs(n.normalized() @ z.normalized())
    assert perp <= tol, f'{name}: info face normal not radial (dot|n.z|={perp:.3f})'
    flip = Quaternion(z, math.pi) @ q
    n2 = (flip @ Vector(normal_local)).normalized()
    c2 = pos + flip @ Vector(center_local)
    toward = (Vector(cam_pos) - c2).normalized()
    facing = float(n2 @ toward)
    assert facing > 0.2, f'{name}: flipped info face does not face camera (dot={facing:.3f})'
    print(json.dumps({'back_view_verification': {name: {
        'normal_local_z_dot': round(perp, 4), 'flip_faces_camera_dot': round(facing, 3),
        'flipped_center_m': [round(v, 3) for v in c2]}}}, ensure_ascii=False), flush=True)

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
    path = ROOT/'scenes'/scene_id/'scene.json'
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'scene_json': str(path)}), flush=True)
    return path
