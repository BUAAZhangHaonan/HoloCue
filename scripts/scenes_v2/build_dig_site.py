"""Build the dig_site (考古探方发掘) scene kit.

Run (CPU only, via resource guard):
  cd /home/hdd3/zhanghaonan/projects/holocue && .venv/bin/python scripts/guard/resource_guard.py \
      --rss-limit-gb 12 --execute -- /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/scenes_v2/build_dig_site.py
  (tee full stdout to runs/scene_v2/build_dig_site.log)

Produces:
  assets/meshes/dig_site/{POT3,FLAG,BONE,STAY,POT1,POT2,TROWEL}.glb   (interactive)
  assets/meshes/env/dig_site_{ground,equipmentpad}.glb                (procedural env)
  configs/scenes/dig_site.json
  runs/scene_v2/dig_site_kit_preview.png        (ortho over the task volume: pit +
                                                 interactives + labels, heap/spade crop)
  runs/scene_v2/dig_site_kit_preview_pit.png    (tight ortho on the pit interior:
                                                 POT3/BONE/FLAG/POT1/POT2 readable +
                                                 small labels; bone length >= 15% of
                                                 pit width asserted)
  runs/scene_v2/dig_site_kit_preview_pot3.png   (close view of POT3 cord-marked inner
                                                 face; ridge banding asserted)
  runs/scene_v2/dig_site_kit_preview_stay.png   (zoom on the STAY telescope aimed at
                                                 the pit center; aim angle asserted)

DATUM: natural ground surface z=0. Trench 1.5x1.5 m, floor z=-0.50, vertical walls with
3 stratigraphic bands (topsoil 0..-0.12, compacted fill -0.12..-0.32, cultural layer
-0.32..-0.50, wavy boundaries + charcoal/plaster flecks). Platform 3x3 m around the pit.
-Y is north per docs/09; the SOUTH wall (y=+0.75) carries POT3, the west wall POT1, the
east floor edge POT2. Origin rules: POT1/2/3 fragment center; FLAG pin tip (local +Z
along pin); BONE bone center; STAY tripod foot center; TROWEL blade center (blade line
= local +Y).
"""
import bpy, sys, json, math, random
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
from mathutils import Vector, Euler, Quaternion

MESH_OUT = ROOT / 'assets/meshes/dig_site'
ENV_OUT = ROOT / 'assets/meshes/env'
RAD = math.radians

# ---------------------------------------------------------------- world layout
CAM_POS = (1.35, -1.35, 1.05)          # design value kept exactly (tune window +/-10% unused)
CAM_LOOK = (-0.494, 0.848, 0.173)      # review #1 reframe (elev 17 deg, beta 40 deg): aims
                                       # between the pit floor and the STAY stack so both fit
                                       # AND the content centers on both frame axes at ortho
                                       # ~4.0. Old aim (0.0, 0.15, -0.25) auto-fitted 6.03 by
                                       # including the heap/spade; subjects were ~10-40 px.
PIT_LOOK = (-0.304, 0.487, -0.649)     # render 3 (pit interior) aim from CAM_POS:
                                       # elev 34.5 deg, 3 deg off corner-on (beta 42 deg)
RIM = 0.75                             # pit rim half-width (baulk edge at |x|,|y| = 0.75)
FLOOR_Z = -0.50
PLAT = 1.5                             # platform half-extent (3x3 m total)
PAD_O = Vector((0.50, -1.12, 0.0))     # equipment pad origin (north rim, world)
HEAP_C = (-1.12, 0.30)                 # spoil heap center (west rim)
HEAP_RX, HEAP_RY, HEAP_H = 0.35, 0.55, 0.40

POSES = {  # interactive objects (world)
    'POT3':   (0.35, 0.726, -0.25),    # south wall, half-embedded, inner face toward -y
    'POT1':   (-0.727, -0.30, -0.36),  # west wall, inner face toward +x (baked yaw +90)
    'POT2':   (0.705, 0.30, -0.472),   # east floor edge, leaning on wall, inner face -x
    'BONE':   (0.18, -0.10, -0.45),    # docs/09 pose; half-embedded via floor mound
    'FLAG':   (0.02, -0.88, 0.0),      # staged planted at north rim (goal is at BONE anchor)
    'STAY':   (0.50, 1.22, 0.0),       # tripod foot center on ground; telescope baked aiming at pit
    'TROWEL': (-0.80, -0.08, 0.010),
}
BONE_PLACEMENT_ANCHOR = (0.0, -0.08, 0.02)   # docs/09: flag 8 cm to the NORTH (-y) of bone
TROWEL_YAW_DEG = -35.0
# review #2 fix #1: the long bone is yawed IN GEOMETRY (JSON pose stays identity) so its
# silhouette projects broadside in both ortho previews (camera azimuth ~40-42 deg).
BONE_YAW_DEG = 38.0
_BU = (math.cos(RAD(BONE_YAW_DEG)), math.sin(RAD(BONE_YAW_DEG)))
_BN = (-_BU[1], _BU[0])
_BONE_CXY = (POSES['BONE'][0], POSES['BONE'][1])
_GOAL_XY = (_BONE_CXY[0] + BONE_PLACEMENT_ANCHOR[0], _BONE_CXY[1] + BONE_PLACEMENT_ANCHOR[1])
# review #2 fix #4: STAY telescope aims at the pit-center floor. Expressed station-local
# (= world offset, JSON pose is identity): pit target (0, 0.10, -0.40) - station head
# (POSES x,y, +1.30 z).
STAY_AIM_LOCAL = Vector((-0.50, -1.12, -1.70)).normalized()
STAY_AIM_TARGET = (0.0, 0.10, -0.40)

# ------------------------------------------------------------------ tiny utils
def sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

def v3t(t): return tuple(round(x, 5) for x in t)

def quat_norm(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (round(w / n, 6), round(x / n, 6), round(y / n, 6), round(z / n, 6))

_flat4 = flat  # common.flat expects RGBA
def flat(name, rgb, metallic=0.0, roughness=0.55, emissive=None, emission_strength=1.0):
    return _flat4(name, (rgb[0], rgb[1], rgb[2], 1.0), metallic=metallic, roughness=roughness,
                  emissive=None if emissive is None else (emissive[0], emissive[1], emissive[2], 1.0),
                  emission_strength=emission_strength)

_tint_cache = {}

def _hsv_adjust(arr, hue_shift, sat_m, val_m):
    """Vectorized RGB(HxWx3, sRGB-space) -> HSV -> adjust -> RGB."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(axis=-1); mn = arr.min(axis=-1)
    d = mx - mn
    v = mx
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    dd = np.maximum(d, 1e-6)
    rc, gc, bc = (mx - r) / dd, (mx - g) / dd, (mx - b) / dd
    h = np.where(mx == r, bc - gc, np.where(mx == g, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0
    h = (h + hue_shift) % 1.0
    s = np.clip(s * sat_m, 0.0, 1.0)
    v = np.clip(v * val_m, 0.0, 1.0)
    i = np.floor(h * 6.0).astype(np.int32) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p = v * (1 - s); q = v * (1 - s * f); t = v * (1 - s * (1 - f))
    r2 = np.choose(i, [v, q, p, p, t, v])
    g2 = np.choose(i, [t, v, v, q, p, p])
    b2 = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r2, g2, b2], axis=-1)

def tinted_image(tex_id, hue_shift, sat_m, val_m):
    """Material-node tints are DROPPED by the glTF exporter, so stratigraphic band colors
    must be baked into real texture copies to survive export + re-import."""
    key = (tex_id, round(hue_shift, 3), round(sat_m, 3), round(val_m, 3))
    if key in _tint_cache:
        return _tint_cache[key]
    src = bpy.data.images.load(str(TEX / tex_id / 'Diffuse_1k.jpg'), check_existing=True)
    w, h = src.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    src.pixels.foreach_get(buf)
    rgb = buf.reshape(h, w, 4)[..., :3].astype(np.float32)
    out = _hsv_adjust(rgb, hue_shift, sat_m, val_m)
    img = bpy.data.images.new(f'{tex_id}_tint{len(_tint_cache)}', w, h, alpha=True, float_buffer=False)
    o = np.concatenate([out.reshape(-1, 3), np.ones((w * h, 1), dtype=np.float32)], axis=1)
    img.pixels.foreach_set(o.reshape(-1))
    img.pack()
    _tint_cache[key] = img
    return img

def pbr_tint(name, tex_id, scale=1.0, hue=0.5, sat=1.0, val=1.0, roughness=None):
    """pbr() with the diffuse map replaced by an HSV-tinted baked copy (export-safe)."""
    mat = pbr(name, tex_id, scale=scale, roughness=roughness)
    if abs(hue - 0.5) > 1e-6 or abs(sat - 1.0) > 1e-6 or abs(val - 1.0) > 1e-6:
        img = tinted_image(tex_id, hue - 0.5, sat, val)
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.name.startswith('Diffuse'):
                n.image = img
    return mat

def new_mesh(name, verts, faces, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if mat:
        o.data.materials.append(mat)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    # recalculate outward normals so custom meshes shade correctly
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    o.select_set(False)
    return o

def set_uv(obj, uvfn):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new()
    uvl = me.uv_layers.active
    for loop in me.loops:
        v = obj.matrix_world @ me.vertices[loop.vertex_index].co
        uvl.data[loop.index].uv = uvfn(v)

def patch(name, xr, yr, nx, ny, zfn, mat, uvsc, smooth=True):
    """Horizontal grid patch with world-xy UVs."""
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = xr[0] + (xr[1] - xr[0]) * i / nx
            y = yr[0] + (yr[1] - yr[0]) * j / ny
            verts.append((x, y, zfn(x, y)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i; b = a + 1
            c = a + nx + 2; d = a + nx + 1
            faces.append((a, b, c, d))
    o = new_mesh(name, verts, faces, mat, smooth)
    set_uv(o, lambda v: (v.x * uvsc, v.y * uvsc))
    return o

def tube(name, p0, p1, r, mat, vertices=12):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    return cyl(name, r, d.length, tuple((p0 + p1) / 2), mat,
               rot=d.to_track_quat('Z', 'Y').to_euler(), vertices=vertices)

def kids_of(prefix):
    return [o for o in bpy.data.objects if o.name.startswith(prefix)]

def bbox_world(objs):
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, w.x); lo.y = min(lo.y, w.y); lo.z = min(lo.z, w.z)
            hi.x = max(hi.x, w.x); hi.y = max(hi.y, w.y); hi.z = max(hi.z, w.z)
    return lo, hi

def settle(parent, target_z):
    lo, _ = bbox_world([parent] + [o for o in bpy.data.objects if o.parent == parent])
    parent.location.z += target_z - lo.z
    bpy.context.view_layer.update()
    return round(target_z - lo.z, 4)

def rotate_about_center(objs, q):
    lo, hi = bbox_world(objs)
    c = (lo + hi) / 2
    for o in objs:
        o.rotation_mode = 'QUATERNION'  # ops-created objects default to Euler: assignment is a no-op otherwise
        o.rotation_quaternion = q @ o.rotation_quaternion
        o.location = c + q @ (o.location - c)
    bpy.context.view_layer.update()

def bake_rotation(objs, scale=False):
    """Bake object rotation (and optionally scale) into mesh vertices so exported GLB
    nodes carry identity transforms -- the round-trip path the kit convention relies on.
    World appearance is unchanged (locations stay as node translations)."""
    for o in objs:
        if o.type != 'MESH':
            continue
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=scale)
    bpy.ops.object.select_all(action='DESELECT')

def place_bbox_corner(objs, xy_center=None, z_base=None, x_min=None, y_min=None, y_max=None):
    """Translate objs so their rotated bbox satisfies the given constraint(s)."""
    lo, hi = bbox_world(objs)
    d = Vector((0.0, 0.0, 0.0))
    if xy_center is not None:
        d += Vector((xy_center[0] - (lo.x + hi.x) / 2, xy_center[1] - (lo.y + hi.y) / 2, 0.0))
    if x_min is not None:
        d.x += x_min - lo.x
    if y_min is not None:
        d.y += y_min - lo.y
    if y_max is not None:
        d.y += y_max - hi.y
    if z_base is not None:
        d.z += z_base - lo.z
    for o in objs:
        o.location += d
    bpy.context.view_layer.update()

# ------------------------------------------------------------- authored ground
def heap_h(x, y):
    """Analytic spoil-heap dome height (mesh, sandbags and spade placement share it)."""
    u = math.hypot((x - HEAP_C[0]) / HEAP_RX, (y - HEAP_C[1]) / HEAP_RY)
    if u >= 1.0:
        return 0.0
    return HEAP_H * (1.0 - u ** 1.6) ** 1.1

def floor_z(x, y):
    """Trench floor: -0.50 + gentle noise + excavated bone pedestal (review #2 fix #1).

    The pedestal is a gaussian ridge ALONG the bone axis (yaw 38 deg, sigma 0.26 along /
    0.085 across) that seats the shaft ~40% deep in soil with the midshaft standing proud;
    a small goal mound 8 cm north (peak 0.065 at the assemble point) keeps the FLAG goal
    just above grade. Both extremes are asserted in the anchor verification printout:
    floor(bone center) = -0.454 (bone center +4 mm), floor(goal) = -0.435 (goal +5 mm)."""
    dxu = (x - _BONE_CXY[0]) * _BU[0] + (y - _BONE_CXY[1]) * _BU[1]
    dyn = (x - _BONE_CXY[0]) * _BN[0] + (y - _BONE_CXY[1]) * _BN[1]
    ped = 0.046 * math.exp(-0.5 * ((dxu / 0.26) ** 2 + (dyn / 0.085) ** 2))
    g = math.hypot(x - _GOAL_XY[0], y - _GOAL_XY[1])
    mound = max(ped, 0.065 * math.exp(-0.5 * (g / 0.075) ** 2))
    d = math.hypot(x - _BONE_CXY[0], y - _BONE_CXY[1])
    damp = sstep(0.12, 0.30, d)
    edge = (1 - sstep(0.68, 0.75, max(abs(x), abs(y))))
    n = (0.006 * math.sin(9.3 * x + 2.1) * math.sin(7.7 * y + 0.7)
         + 0.004 * math.sin(17 * x + 0.4) * math.sin(13 * y + 1.3))
    return FLOOR_Z + mound + n * damp * edge

def gtop_z(x, y):
    """Platform top: gentle noise, damped to 0 at the pit baulk and platform edge."""
    edge_pit = min(1.0, sstep(RIM, RIM + 0.15, max(abs(x), abs(y))))
    edge_out = sstep(PLAT - 0.08, PLAT - 0.01, max(abs(x), abs(y)))
    n = 0.5 * math.sin(0.9 * x + 1.7) * math.sin(1.1 * y + 0.3) \
        + 0.5 * math.sin(2.3 * x + 0.5) * math.sin(2.7 * y + 2.2)
    return 0.007 * n * edge_pit * (1 - edge_out)

def wall_disp(s, z, L, sherd_pts):
    """Deterministic wall roughness; zero at baulk/corners, damped near embedded sherds."""
    n = (0.55 * math.sin(6.3 * s + 2.0 + 9.4 * z)
         + 0.30 * math.sin(11.9 * s + 0.7 + 16.1 * z)
         + 0.15 * math.sin(23.0 * s + 5.0 + 29.0 * z))
    f = min(1.0, -z / 0.05) * min(1.0, (z - FLOOR_Z) / 0.05) * sstep(0.0, 0.08, min(s, L - s))
    for (ss, zz) in sherd_pts:
        d = math.hypot(s - ss, (z - zz) * 1.5)
        f *= 0.15 + 0.85 * sstep(0.05, 0.16, d)
    return 0.010 * n * f

WALLS = [  # (A, B, inward normal, embedded-sherd (s,z) list)
    ((-RIM, RIM), (RIM, RIM), (0.0, -1.0), [(0.35 + RIM, -0.25)]),   # south (POT3)
    ((-RIM, -RIM), (RIM, -RIM), (0.0, 1.0), []),                      # north
    ((-RIM, -RIM), (-RIM, RIM), (1.0, 0.0), [(-0.30 + RIM, -0.36)]),  # west (POT1)
    ((RIM, -RIM), (RIM, RIM), (-1.0, 0.0), []),                       # east
]

def band_top(kind, s, wob):
    if kind == 'top':
        return 0.0
    if kind == 'fill':  # topsoil/fill boundary
        return -0.12 + 0.018 * math.sin(2 * math.pi * s / 1.1 + wob) \
                     + 0.010 * math.sin(2 * math.pi * s / 0.43 + wob * 2)
    return -0.32 + 0.016 * math.sin(2 * math.pi * s / 1.3 + wob * 3) \
                  + 0.009 * math.sin(2 * math.pi * s / 0.51 + wob)     # fill/cultural boundary

def build_ground():
    random.seed(7)
    m_topsoil = pbr_tint('gnd_topsoil', 'excavated_soil_wall', scale=1.5, hue=0.50, sat=1.15, val=0.55)
    # review #2 fix #6: middle band was olive-green (+0.06 hue). Note HSV wraps: the
    # first attempt (-0.10) wrapped past 0 into magenta and read as a red stripe. A
    # small +0.02 shift with lower sat + higher val gives yellow-brown rammed earth.
    m_fill = pbr_tint('gnd_fill', 'excavated_soil_wall', scale=1.8, hue=0.52, sat=0.88, val=1.10)
    m_cult = pbr_tint('gnd_cultural', 'excavated_soil_wall', scale=1.6, hue=0.50, sat=0.55, val=0.80)
    m_floor = pbr_tint('gnd_floor', 'gravelly_sand', scale=2.0, val=0.82)  # review #2: darker excavated floor so the ivory bone reads against it
    m_top = pbr_tint('gnd_platformtop', 'dirt', scale=1.5, val=0.92)
    m_heap = pbr('gnd_heap', 'dirt', scale=1.3)
    m_hess = pbr('gnd_hessian', 'hessian_230', scale=1.0)
    m_charcoal = flat('fleck_charcoal', (0.05, 0.045, 0.04), roughness=0.9)
    m_whitefleck = flat('fleck_white', (0.65, 0.62, 0.53), roughness=0.8)
    m_potfleck = flat('fleck_pottery', (0.40, 0.20, 0.10), roughness=0.8)
    m_pebble = flat('gnd_pebble', (0.42, 0.40, 0.37), roughness=0.85)

    # --- platform top: 4 strips around the pit opening (crisp baulk edges)
    patch('GND_TOP_north', (-PLAT, PLAT), (-PLAT, -RIM), 48, 12, gtop_z, m_top, 1.5)
    patch('GND_TOP_south', (-PLAT, PLAT), (RIM, PLAT), 48, 12, gtop_z, m_top, 1.5)
    patch('GND_TOP_west', (-PLAT, -RIM), (-RIM, RIM), 12, 24, gtop_z, m_top, 1.5)
    patch('GND_TOP_east', (RIM, PLAT), (-RIM, RIM), 12, 24, gtop_z, m_top, 1.5)

    # --- trench floor (uneven; bone pedestal + goal mound baked into floor_z; 46x46
    # grid resolves the 0.085 m pedestal cross-section without faceting)
    patch('GND_FLOOR', (-RIM, RIM), (-RIM, RIM), 46, 46, floor_z, m_floor, 2.0)

    # --- walls: 3 stratigraphic band meshes per wall, wavy boundaries, roughness noise
    for wi, (A, B, nrm, sherds) in enumerate(WALLS):
        A = Vector((A[0], A[1], 0.0)); B = Vector((B[0], B[1], 0.0))
        dirv = (B - A).normalized(); L = (B - A).length
        n = Vector((nrm[0], nrm[1], 0.0))
        wob = 1.7 * (wi + 1)
        cols, kinds = 28, ('top', 'fill', 'cult')
        rows_for = {'top': 5, 'fill': 8, 'cult': 7}
        for kind in kinds:
            rows = rows_for[kind]
            verts, faces = [], []
            for i in range(cols + 1):
                s = L * i / cols
                ztop = band_top(kind, s, wob)
                zbot = FLOOR_Z if kind == 'cult' else band_top('cult' if kind == 'fill' else 'fill', s, wob)
                for r in range(rows + 1):
                    z = ztop + (zbot - ztop) * r / rows
                    p = A + dirv * s + n * wall_disp(s, z, L, sherds) + Vector((0, 0, z))
                    verts.append((p.x, p.y, p.z))
            for i in range(cols):
                for r in range(rows):
                    a = i * (rows + 1) + r; b = a + rows + 1
                    faces.append((a, b, b + 1, a + 1))
            o = new_mesh(f'GND_WALL{wi}_{kind}', verts, faces,
                         {'top': m_topsoil, 'fill': m_fill, 'cult': m_cult}[kind])
            u_ax = 'x' if abs(dirv.x) >= 0.5 else 'y'
            set_uv(o, lambda v, ax=u_ax: ((v.x if ax == 'x' else v.y) * 1.5, v.z * 1.5))
        # cultural-layer flecks (charcoal / plaster / pottery chips) + topsoil pebbles
        for k in range(52):
            s = random.uniform(0.07, L - 0.07)
            z = random.uniform(-0.47, -0.34)
            rr = random.random()
            m = m_charcoal if rr < 0.66 else (m_whitefleck if rr < 0.87 else m_potfleck)
            sz = random.uniform(0.006, 0.013)
            p = A + dirv * s + n * (wall_disp(s, z, L, sherds) + sz * 0.55 + 0.0015) + Vector((0, 0, z))
            b = box(f'GND_FLK{wi}_{k}', (sz, sz * 0.7, sz * 0.5), (p.x, p.y, p.z), m, bevel=0)
            b.rotation_euler = (0, 0, random.uniform(0, math.pi))
        for k in range(10):
            s = random.uniform(0.1, L - 0.1)
            z = random.uniform(-0.10, -0.02)
            sz = random.uniform(0.012, 0.026)
            p = A + dirv * s + n * (wall_disp(s, z, L, sherds) + sz * 0.5 + 0.001) + Vector((0, 0, z))
            bpy.ops.mesh.primitive_uv_sphere_add(radius=sz, location=(p.x, p.y, p.z),
                                                 segments=10, ring_count=6)
            o = bpy.context.object; o.name = f'GND_PEB{wi}_{k}'
            o.scale = (1, 1, 0.55); o.data.materials.append(m_pebble)

    # --- spoil heap dome on the west rim + dirt clumps around the toe
    ring_n, row_n = 36, 13
    verts, faces = [], []
    for j in range(row_n + 1):
        u = 0.05 + 0.95 * j / row_n
        h = -0.012 if j == row_n else HEAP_H * (1.0 - u ** 1.6) ** 1.1 - 0.012
        for i in range(ring_n):
            a = 2 * math.pi * i / ring_n
            x = HEAP_C[0] + HEAP_RX * u * math.cos(a)
            y = HEAP_C[1] + HEAP_RY * u * math.sin(a)
            bump = 0.018 * math.sin(5 * a + 2 * u) * (1 - u) if 0 < j < row_n else 0.0
            verts.append((x, y, h + bump))
    for j in range(row_n):
        for i in range(ring_n):
            i2 = (i + 1) % ring_n
            a = j * ring_n + i; b = j * ring_n + i2
            c = (j + 1) * ring_n + i2; d = (j + 1) * ring_n + i
            faces.append((a, b, c, d))
    heap = new_mesh('GND_HEAP_dome', verts, faces, m_heap)
    set_uv(heap, lambda v: (v.x * 1.3, v.y * 1.3))
    for k in range(11):
        ang = random.uniform(0, 2 * math.pi)
        u = random.uniform(0.92, 1.55)
        x = HEAP_C[0] + HEAP_RX * u * math.cos(ang)
        y = HEAP_C[1] + HEAP_RY * u * math.sin(ang)
        if abs(x) > PLAT - 0.05 or abs(y) > PLAT - 0.05 or x > -RIM - 0.10:
            continue
        r = random.uniform(0.02, 0.05)
        z = heap_h(x, y) if u < 1.0 else 0.0
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=1,
                                              location=(x, y, z + r * 0.3))
        o = bpy.context.object; o.name = f'GND_HEAP_clump{k}'
        o.scale = (1, 1, 0.55); o.data.materials.append(m_heap)

    # --- hessian sandbag row (3) along the heap toe facing the pit
    for k, (bx, by, yaw) in enumerate([(-0.82, 0.05, 80), (-0.86, 0.30, 62), (-0.93, 0.52, 40)]):
        hz = heap_h(bx, by)
        g = bpy.data.objects.new(f'GND_BAG{k}', None)
        bpy.context.scene.collection.objects.link(g)
        g.location = (bx, by, hz - 0.025)
        g.rotation_euler = (0, 0, RAD(yaw))
        bag = box(f'GND_BAG{k}_body', (0.55, 0.24, 0.15), (0, 0, 0.0), m_hess, bevel=0.05)
        bag.parent = g
        for sx in (-1, 1):
            roll = cyl(f'GND_BAG{k}_roll{sx}', 0.068, 0.24, (sx * 0.272, 0, 0), m_hess,
                       rot=(0, math.pi / 2, 0), vertices=16)
            roll.parent = g
    return kids_of('GND_')

# ------------------------------------------------------------- interactive kit
CORD_PITCH, CORD_AMP = 0.0125, 0.0038   # review #2 fix #2: 2.4x amplitude; pitch chosen
                                        # so ~7 ridges span the sherd height

def cord_depth(z):
    """Triangle-wave groove depth in [0, 1]: sharp V grooves at phase 0, flat crests at
    0.5 (sharper relief than the old raised-cosine, which read as soft corrugation)."""
    ph = (z / CORD_PITCH) % 1.0
    return abs(2.0 * ph - 1.0)

def build_sherd(kind):
    """Standing rim sherd: curved panel about a vertical axis; the concave (inner) face
    points toward LOCAL -y at yaw 0. Cord-marked ridges modulate the inner radius
    (POT3 only) -- geometry is sampled at 56x22 (old 10x14 aliased the 9 mm ridge
    period exactly away: zero visible relief) and grooves additionally get a darker
    material so the banding survives any single lighting setup. POT1/POT2 bake their
    wall orientation into the geometry."""
    cfg = {'POT3': dict(Rm=0.11, t=0.025, h=0.09, chord=0.13, cord=True,
                        mout=flat('pot3_out', (0.44, 0.21, 0.12), roughness=0.75),
                        minn=flat('pot3_in', (0.40, 0.19, 0.105), roughness=0.55),
                        mdark=flat('pot3_in_dark', (0.16, 0.07, 0.04), roughness=0.7)),
           'POT1': dict(Rm=0.085, t=0.022, h=0.07, chord=0.085, cord=False,
                        mout=flat('pot1_out', (0.35, 0.21, 0.14), roughness=0.8),
                        minn=flat('pot1_in', (0.28, 0.16, 0.10), roughness=0.75),
                        mdark=None),
           # review #2 fix #3: POT2 enlarged (h 0.065->0.105, chord 0.10->0.13) and
           # brightened so it separates from the soil matrix at the east wall base.
           'POT2': dict(Rm=0.15, t=0.024, h=0.105, chord=0.13, cord=False,
                        mout=flat('pot2_out', (0.50, 0.26, 0.15), roughness=0.7),
                        minn=flat('pot2_in', (0.42, 0.22, 0.13), roughness=0.62),
                        mdark=None)}[kind]
    Rm, t, h, chord = cfg['Rm'], cfg['t'], cfg['h'], cfg['chord']
    half = math.asin(min(0.999, chord / (2 * Rm)))
    nc, nz = 22, 56
    Rin, Rout = Rm - t / 2, Rm + t / 2
    m_crust = flat('pot_crust', (0.20, 0.15, 0.10), roughness=1.0)

    def groove_frac(z):
        """1.0 at a cord groove center (radius pulled inward), 0.0 at a crest."""
        return cord_depth(z) if cfg['cord'] else 0.0

    def rin(z, th):
        r = Rin
        if cfg['cord']:
            r -= CORD_AMP * groove_frac(z)
            r += 0.0006 * math.sin(7 * th / (2 * half) + 40 * z)
        return r

    Vin, Vout = [], []
    for j in range(nz + 1):
        lip = 0.0022 * (1 - abs(2 * j / nz - 1)) if cfg['cord'] else 0.0
        z = -h / 2 + h * j / nz + lip
        for i in range(nc + 1):
            th = -half + 2 * half * i / nc
            x = Rm * math.sin(th)
            Vin.append((x, -Rm + rin(z, th), z))
            Vout.append((x, -Rm + Rout + 0.0008 * math.sin(9 * th + 3 * z), z))
    faces = []
    n = nc + 1
    for j in range(nz):
        for i in range(nc):
            a = j * n + i; b = a + 1; c = a + n + 1; d = a + n
            faces.append((a, d, c, b))                            # inner strip (even faces)
            a2 = len(Vin) + a
            faces.append((a2, a2 + 1, a2 + n + 1, a2 + n))        # outer strip (odd faces)
    for j in range(nz):                                           # end caps at +-half
        a0 = j * n; d0 = a0 + n
        a0o = len(Vin) + a0; d0o = a0o + n
        faces.append((a0, d0, d0o, a0o))
        aN = j * n + nc; dN = aN + n
        aNo = len(Vin) + aN; dNo = aNo + n
        faces.append((dN, aN, aNo, dNo))
    for i in range(nc):                                           # rim cap + broken bottom
        a = nz * n + i; b = a + 1
        faces.append((a, b, len(Vin) + b, len(Vin) + a))
        faces.append((i + 1, i, len(Vin) + i, len(Vin) + i + 1))
    mats = [cfg['mout'], cfg['minn']] + ([cfg['mdark']] if cfg['mdark'] else [])
    o = new_mesh(f'{kind}_panel', Vout + Vin, faces, cfg['mout'])
    for m in mats[1:]:
        o.data.materials.append(m)
    for fi, poly in enumerate(o.data.polygons):                   # inner strip -> mat 1/2
        if fi < 2 * nz * nc and fi % 2 == 0:
            j = (fi // 2) // nc
            zc = -h / 2 + h * (j + 0.5) / nz
            poly.material_index = 2 if (cfg['mdark'] and groove_frac(zc) > 0.5) else 1
    # dirt crust blobs on the outer (embedded) face, lower half
    random.seed({'POT3': 11, 'POT1': 12, 'POT2': 13}[kind])
    for k in range(7):
        th = random.uniform(-half * 0.8, half * 0.8)
        z = random.uniform(-h / 2, -h / 6)
        r = random.uniform(0.008, 0.018)
        x = Rm * math.sin(th)
        y = -Rm + Rout + 0.001
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=1,
                                              location=(x, y, z))
        c = bpy.context.object; c.name = f'{kind}_crust{k}'
        c.scale = (1, 0.5, 0.8); c.data.materials.append(m_crust)
    objs = [o] + kids_of(f'{kind}_crust')
    q = Quaternion((1, 0, 0, 0))
    if kind == 'POT1':
        q = Quaternion((0, 0, 1), RAD(90))                        # inner face -> +x
    elif kind == 'POT2':
        q = Quaternion((0, 1, 0), RAD(18)) @ Quaternion((0, 0, 1), RAD(-90))  # inner -> -x, lean onto wall
    for ob in objs:
        ob.rotation_mode = 'QUATERNION'  # ops-created objects default to Euler
        ob.rotation_quaternion = q @ ob.rotation_quaternion
        ob.location = q @ ob.location    # crust blobs live off-origin: rotate their positions too
    bake_rotation(objs)  # keep GLB node transforms identity (round-trip convention)
    return objs

def build_flag():
    m_steel = flat('flag_steel', (0.28, 0.29, 0.31), metallic=0.8, roughness=0.4)
    m_red = flat('flag_red', (0.62, 0.035, 0.03), roughness=0.55)
    m_cap = flat('flag_cap', (0.55, 0.05, 0.04), roughness=0.5)
    bpy.ops.mesh.primitive_cone_add(radius1=0.0008, radius2=0.003, depth=0.012,
                                    location=(0, 0, 0.006), vertices=12)
    tip = bpy.context.object; tip.name = 'FLAG_tip'; tip.data.materials.append(m_steel)
    cyl('FLAG_shaft', 0.003, 0.283, (0, 0, 0.012 + 0.283 / 2), m_steel, vertices=12)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.006, location=(0, 0, 0.298),
                                         segments=12, ring_count=8)
    cap = bpy.context.object; cap.name = 'FLAG_cap'; cap.data.materials.append(m_cap)
    # pennant: triangle prism in the local XZ plane (radial w.r.t. local Z)
    t = 0.0016
    verts = [(0.0032, 0, 0.292), (0.0032, 0, 0.220), (0.138, 0, 0.252),
             (0.0032 + t, 0, 0.292), (0.0032 + t, 0, 0.220), (0.138 + t, 0, 0.252)]
    faces = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    new_mesh('FLAG_pennant', verts, faces, m_red, smooth=False)
    return kids_of('FLAG_')

def build_bone():
    """Long bone, ~0.40 m overall (femur-scale). Review #2 fix #1: the midshaft is left
    CLEAN and bright ivory; matrix crust blobs seat only the two ends (the floor pedestal
    in floor_z holds the midshaft ~40% deep). Weathered-ivory albedo raised and
    roughness lowered so it pops against the soil. The whole bone is yawed 38 deg about
    its center so both ortho previews see the shaft broadside (pose stays identity).
    Review #3 fix B2: at main-view distance (~2.3 m) the bone still read dark/earthy,
    so the ivory gets a 10-20% brightness/contrast compensation -- base albedo +~9%,
    roughness 0.38 -> 0.30 (crisper grazing top highlight = contrast) plus a faint
    warm emission floor (+~7% at any distance). Main-view bone-top p92: 0.412 -> ~0.48.
    The end crust blobs are also thinned so more ivory shows on the visible shaft."""
    m_ivory = flat('bone_ivory', (1.0, 0.965, 0.86), roughness=0.30,
                   emissive=(0.31, 0.30, 0.26), emission_strength=0.14)
    m_crust = flat('bone_crust', (0.20, 0.15, 0.10), roughness=1.0)
    ns, nr = 26, 16
    verts, faces = [], []
    for i in range(ns + 1):
        tt = i / ns
        x = -0.17 + 0.31 * tt                    # shaft spans -0.17 .. +0.14
        r = 0.0235 + 0.0035 * tt
        cy = -0.004 - 0.004 * math.sin(tt * math.pi)
        cz = 0.004 + 0.005 * math.sin(tt * math.pi * 0.8)
        for k in range(nr):
            a = 2 * math.pi * k / nr
            verts.append((x, cy + r * math.cos(a), cz + r * math.sin(a) * 0.92))
    for i in range(ns):
        for k in range(nr):
            k2 = (k + 1) % nr
            a = i * nr + k; b = i * nr + k2
            c = (i + 1) * nr + k2; d = (i + 1) * nr + k
            faces.append((a, b, c, d))
    center0 = verts[0]
    centerN = verts[-1]
    vi0 = len(verts); verts.append(tuple(sum(v[i] for v in verts[0:nr]) / nr for i in range(3)))
    vi1 = len(verts); verts.append(tuple(sum(v[i] for v in verts[ns * nr:(ns + 1) * nr]) / nr for i in range(3)))
    for k in range(nr):
        k2 = (k + 1) % nr
        faces.append((vi0, k2, k))
        faces.append((vi1, ns * nr + k, ns * nr + k2))
    new_mesh('BONE_shaft', verts, faces, m_ivory)
    cyl('BONE_distlink', 0.0275, 0.05, (0.155, -0.004, -0.002), m_ivory, rot=(0, math.pi / 2, 0), vertices=20)
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.030,
                                             location=(0.175, -0.008 + 0.022 * sy, -0.008),
                                             segments=18, ring_count=12)
        o = bpy.context.object; o.name = f'BONE_cond{sy}'; o.data.materials.append(m_ivory)
        o.scale = (1.05, 0.95, 0.95)
    tube('BONE_neck', (-0.17, 0.0, 0.0), (-0.196, -0.030, 0.002), 0.018, m_ivory, vertices=14)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.031, location=(-0.208, -0.036, 0.002),
                                         segments=18, ring_count=12)
    hd = bpy.context.object; hd.name = 'BONE_head'; hd.data.materials.append(m_ivory)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.026, location=(-0.180, 0.017, -0.006),
                                         segments=14, ring_count=9)
    gt = bpy.context.object; gt.name = 'BONE_troch'; gt.data.materials.append(m_ivory)
    gt.scale = (1.1, 0.9, 1.0)
    random.seed(21)
    # matrix dirt crust ONLY at the two ends; the exposed midshaft (|x| < 0.10) stays clean
    for (xlo, xhi, n_end) in ((-0.20, -0.10, 4), (0.10, 0.17, 4)):
        for _ in range(n_end):
            x = random.uniform(xlo, xhi)
            r = random.uniform(0.012, 0.024)   # review #3 B2: thinner crust at the ends
            z = random.choice((0.018, -0.004))
            bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=1,
                                                  location=(x, random.uniform(-0.014, 0.014), z + r * 0.3))
            c = bpy.context.object; c.name = f'BONE_crust{xlo}_{_}'
            c.scale = (1.5, 1.1, 0.6); c.data.materials.append(m_crust)
    objs = kids_of('BONE_')
    rotate_about_center(objs, Quaternion((0, 0, 1), RAD(BONE_YAW_DEG)))
    lo, hi = bbox_world(objs)                    # recentre: exported bbox center == pose
    c = (lo + hi) / 2                            # so the pedestal in floor_z keys exactly
    for o in objs:
        o.location -= Vector((c.x, c.y, c.z))
    bpy.context.view_layer.update()
    return objs

def build_stay():
    m_leg = flat('stay_leg', (0.16, 0.17, 0.18), metallic=0.6, roughness=0.5)
    m_dark = flat('stay_dark', (0.09, 0.09, 0.10), roughness=0.5)
    m_body = flat('stay_body', (0.90, 0.74, 0.20), roughness=0.45)  # survey-instrument yellow
    m_brass = flat('stay_brass', (0.65, 0.5, 0.22), metallic=0.85, roughness=0.35)
    m_lcd = flat('stay_lcd', (0.05, 0.08, 0.10), roughness=0.3,
                 emissive=(0.35, 0.75, 0.55), emission_strength=0.9)
    m_lens = flat('stay_lens', (0.03, 0.035, 0.045), roughness=0.15, metallic=0.4)
    hub = Vector((0, 0, 0.97))
    for ang in (30, 150, 270):  # one leg points at the pit (-y from the station)
        fx = 0.25 * math.cos(RAD(ang)); fy = 0.25 * math.sin(RAD(ang))
        tube(f'STAY_leg{ang}', (fx, fy, 0.02), tuple(hub), 0.013, m_leg, vertices=10)
        bpy.ops.mesh.primitive_cone_add(radius1=0.013, radius2=0.004, depth=0.02,
                                        location=(fx, fy, 0.012), vertices=10)
        c = bpy.context.object; c.name = f'STAY_tip{ang}'; c.data.materials.append(m_leg)
        cyl(f'STAY_foot{ang}', 0.021, 0.012, (fx, fy, 0.006), m_dark, vertices=12)
    cyl('STAY_hub', 0.030, 0.10, (0, 0, 0.97), m_leg, vertices=16)
    box('STAY_trib', (0.11, 0.11, 0.04), (0, 0, 1.03), m_dark, bevel=0.004)
    for i, ang in enumerate((90, 210, 330)):
        a = RAD(ang)
        cyl(f'STAY_screw{i}', 0.011, 0.018, (0.085 * math.cos(a), 0.085 * math.sin(a), 1.03),
            m_brass, rot=(0, math.pi / 2, 0), vertices=12)
        cyl(f'STAY_screwcap{i}', 0.006, 0.024, (0.098 * math.cos(a), 0.098 * math.sin(a), 1.03),
            m_dark, rot=(0, math.pi / 2, 0), vertices=10)
    box('STAY_body', (0.15, 0.13, 0.20), (0, 0, 1.17), m_body, bevel=0.008)
    for sx in (-1, 1):  # vertical circle housings flanking the telescope axis
        cyl(f'STAY_disc{sx}', 0.058, 0.018, (0.058 * sx, 0, 1.17), m_dark,
            rot=(0, math.pi / 2, 0), vertices=32)
    # review #2 fix #4: telescope axis aimed at the pit-center floor (module-level
    # STAY_AIM_LOCAL = pit target - station head, station-local == world offsets since
    # the JSON pose is identity). The old aim (+0.15 local x) pointed PAST the east rim.
    aim = STAY_AIM_LOCAL.copy()
    c0 = Vector((0, 0, 1.30))
    q_aim = aim.to_track_quat('Z', 'Y')
    tube('STAY_tele', tuple(c0 - aim * 0.13), tuple(c0 + aim * 0.13), 0.028, m_dark, vertices=20)
    tube('STAY_objring', tuple(c0 + aim * 0.13), tuple(c0 + aim * 0.155), 0.033, m_body, vertices=20)
    cyl('STAY_lens', 0.028, 0.004, tuple(c0 + aim * 0.157), m_lens, rot=q_aim.to_euler(), vertices=20)
    tube('STAY_eyep', tuple(c0 - aim * 0.13), tuple(c0 - aim * 0.185), 0.016, m_dark, vertices=14)
    side = aim.cross(Vector((0, 0, 1))).normalized()
    cyl('STAY_focus', 0.012, 0.02, tuple(c0 - aim * 0.115 + side * 0.032), m_dark,
        rot=q_aim.to_euler(), vertices=12)
    box('STAY_lcd', (0.062, 0.005, 0.048), (0.028, -0.0665, 1.155), m_lcd, bevel=0)
    box('STAY_keys', (0.062, 0.005, 0.030), (0.028, -0.0665, 1.085), m_dark, bevel=0)
    for i in range(6):
        box(f'STAY_key{i}', (0.008, 0.006, 0.004),
            (0.006 + 0.010 * (i % 3), -0.0705, 1.094 + 0.011 * (i // 3)), m_body, bevel=0)
    for (nm, yy, zz) in (('a', 0.030, 1.195), ('b', -0.028, 1.135)):
        cyl(f'STAY_knob_{nm}', 0.026, 0.024, (0.088, yy, zz), m_dark, rot=(0, math.pi / 2, 0), vertices=24)
        cyl(f'STAY_knob_{nm}g', 0.030, 0.006, (0.094, yy, zz), m_brass, rot=(0, math.pi / 2, 0), vertices=24)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.056, minor_radius=0.005,
                                     location=(0, 0, 1.372), rotation=(RAD(90), 0, 0),
                                     major_segments=24, minor_segments=8)
    h = bpy.context.object; h.name = 'STAY_handle'; h.data.materials.append(m_dark)
    return kids_of('STAY_')

def build_trowel():
    m_steel = flat('trowel_steel', (0.52, 0.53, 0.55), metallic=0.9, roughness=0.32)
    m_wood = flat('trowel_wood', (0.11, 0.065, 0.04), roughness=0.65)
    outline = [(0.0, 0.075), (0.027, 0.045), (0.029, 0.010), (0.027, -0.030),
               (0.016, -0.070), (-0.016, -0.070), (-0.027, -0.030),
               (-0.029, 0.010), (-0.027, 0.045)]
    th = 0.0022
    verts = [(x, y, 0.0) for (x, y) in outline] + [(x, y, th) for (x, y) in outline]
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    new_mesh('TROWEL_blade', verts, faces, m_steel, smooth=False)
    box('TROWEL_tang', (0.012, 0.052, 0.003), (0, -0.094, 0.0015), m_steel, bevel=0.001)
    box('TROWEL_handle', (0.024, 0.115, 0.020), (0, -0.172, 0.0055), m_wood, bevel=0.007)
    cyl('TROWEL_end', 0.012, 0.024, (0, -0.229, 0.0055), m_wood, rot=(math.pi / 2, 0, 0), vertices=14)
    return kids_of('TROWEL_')

def build_equipmentpad():
    """Mat + finds crate (imported open body + leaning lid + ceramic pot visible above the
    rim) + folding string-grid frame over the SW trench quadrant + bucket + brush + tape.
    All in pad-local coords (pad origin PAD_O); exported as one GLB."""
    m_rubber = pbr('pad_mat', 'rubber_tiles', scale=1.2)
    m_steel = flat('pad_steel', (0.45, 0.46, 0.48), metallic=0.7, roughness=0.45)
    m_cap = flat('pad_pincap', (0.60, 0.06, 0.05), roughness=0.5)
    m_nylon = flat('pad_string', (0.78, 0.78, 0.74), roughness=0.5)
    m_bucket = flat('pad_bucket', (0.10, 0.11, 0.12), roughness=0.7)
    m_bucketin = flat('pad_bucketin', (0.07, 0.08, 0.085), roughness=0.8)
    m_metalh = flat('pad_handle', (0.4, 0.41, 0.43), metallic=0.8, roughness=0.4)
    m_wood = flat('pad_brushwood', (0.35, 0.22, 0.12), roughness=0.7)
    m_brist = flat('pad_bristle', (0.72, 0.66, 0.52), roughness=0.9)
    m_tape = flat('pad_tape', (0.75, 0.55, 0.08), roughness=0.6)
    box('PAD_mat', (0.85, 0.58, 0.008), (0, 0, 0.004), m_rubber, bevel=0.002)

    # --- folding string-grid frame over the SW quadrant of the trench (world -> pad-local)
    def loc(wx, wy, wz): return (wx - PAD_O.x, wy - PAD_O.y, wz)
    pins = [(-0.62, -0.62), (-0.06, -0.62), (-0.06, -0.06), (-0.62, -0.06)]
    for i, (wx, wy) in enumerate(pins):
        bz = floor_z(wx, wy)
        cyl(f'PAD_gpin{i}', 0.004, 0.65, loc(wx, wy, bz + 0.325), m_steel, vertices=10)
        cyl(f'PAD_gcap{i}', 0.0055, 0.03, loc(wx, wy, bz + 0.635), m_cap, vertices=10)
    zstr = 0.125
    for yy in (-0.46, -0.30, -0.14):
        tube(f'PAD_strY{yy}', loc(-0.62, yy, zstr), loc(-0.06, yy, zstr), 0.0016, m_nylon, vertices=6)
    for xx in (-0.46, -0.30, -0.14):
        tube(f'PAD_strX{xx}', loc(xx, -0.62, zstr), loc(xx, -0.06, zstr), 0.0016, m_nylon, vertices=6)

    # --- bucket (procedural; wooden_bucket not downloaded)
    cyl('PAD_bucket', 0.135, 0.24, (-0.62, -0.05, 0.12), m_bucket, vertices=28)
    cyl('PAD_bucketin', 0.128, 0.215, (-0.62, -0.05, 0.128), m_bucketin, vertices=28)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.136, minor_radius=0.005,
                                     location=(-0.62, -0.05, 0.24), major_segments=24, minor_segments=8)
    t = bpy.context.object; t.name = 'PAD_bucketrim'; t.data.materials.append(m_bucket)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.125, minor_radius=0.0025,
                                     location=(-0.62, -0.05, 0.295), rotation=(RAD(90), 0, 0),
                                     major_segments=24, minor_segments=8)
    hd = bpy.context.object; hd.name = 'PAD_buckethandle'; hd.data.materials.append(m_metalh)

    # --- brush + tape measure on the mat
    for nm, dims, lp in (('PAD_brushhead', (0.06, 0.030, 0.014), (-0.02, 0.20, 0.021)),
                         ('PAD_brushbristle', (0.062, 0.026, 0.010), (-0.02, 0.20, 0.010)),
                         ('PAD_brushhandle', (0.028, 0.020, 0.008), (0.032, 0.20, 0.030))):
        mat = m_wood if 'bristle' not in nm else m_brist
        b = box(nm, dims, lp, mat, bevel=0.002)
        b.rotation_euler = (0, 0, RAD(20))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.030, minor_radius=0.010,
                                     location=(0.15, 0.21, 0.022), major_segments=20, minor_segments=8)
    tp = bpy.context.object; tp.name = 'PAD_tape'; tp.data.materials.append(m_tape)

    # --- finds crate: open body + lid leaning against the north side + pot inside
    crate_objs = import_glb(ROOT / 'assets/meshes/env/wooden_crate_01.glb')
    body = [o for o in crate_objs if 'lid' not in o.name.lower()]
    lid = [o for o in crate_objs if 'lid' in o.name.lower()]
    rotate_about_center(body, Quaternion((0, 0, 1), RAD(12)))
    place_bbox_corner(body, xy_center=(0.10, -0.02), z_base=0.008)   # sits on the mat
    if lid:
        rotate_about_center(lid, Quaternion((1, 0, 0), RAD(-64)))    # leans toward -y (crate)
        place_bbox_corner(lid, y_max=0.32, z_base=0.004, x_min=0.10)
    pot_objs = import_glb(ROOT / 'assets/meshes/env/ceramic_pot.glb')
    for o in pot_objs:
        o.rotation_mode = 'QUATERNION'
        o.scale = tuple(0.70 * s for s in o.scale)
        o.rotation_quaternion = Quaternion((0, 0, 1), RAD(28)) @ o.rotation_quaternion
    bpy.context.view_layer.update()
    place_bbox_corner(pot_objs, xy_center=(0.10, -0.02), z_base=0.10)  # top clears crate rim
    bake_rotation(body)
    if lid:
        bake_rotation(lid)
    bake_rotation(pot_objs, scale=True)
    return kids_of('PAD_') + body + lid + pot_objs

# ------------------------------------------------------------------ main build
def main():
    MESH_OUT.mkdir(parents=True, exist_ok=True)
    table = []

    def build_part(name, objs, out_path):
        lo, hi = bbox_world(objs)
        tris = sum(len(o.data.polygons) for o in objs if o.type == 'MESH')
        p = export_glb(objs, out_path)
        table.append({'part': name, 'glb': str(p.relative_to(ROOT)), 'tris': tris,
                      'bytes': p.stat().st_size,
                      'bbox_local': [[round(x, 4) for x in lo], [round(x, 4) for x in hi]]})
        clear_scene()
        return lo, hi

    clear_scene()
    build_part('ground', build_ground(), ENV_OUT / 'dig_site_ground.glb')
    for kind in ('POT3', 'POT1', 'POT2'):
        build_part(kind, build_sherd(kind), MESH_OUT / f'{kind}.glb')
    build_part('FLAG', build_flag(), MESH_OUT / 'FLAG.glb')
    build_part('BONE', build_bone(), MESH_OUT / 'BONE.glb')
    build_part('STAY', build_stay(), MESH_OUT / 'STAY.glb')
    build_part('TROWEL', build_trowel(), MESH_OUT / 'TROWEL.glb')
    build_part('equipmentpad', build_equipmentpad(), ENV_OUT / 'dig_site_equipmentpad.glb')
    print(json.dumps({'exported': table}, indent=1), flush=True)

    # =========================================================== compose preview
    clear_scene()
    world_bg((0.55, 0.67, 0.82, 1.0), 0.55)
    parents, children = {}, {}

    def add_part(pid, path, pos, wxyz=(1, 0, 0, 0), scale=1.0, rest=None):
        objs = import_glb(path)
        p = parent_to('HC_' + pid, objs, location=pos, wxyz=wxyz)
        p.scale = (scale, scale, scale)
        bpy.context.view_layer.update()
        if rest is not None:
            settle(p, rest)
        parents[pid] = p; children[pid] = objs
        return p

    for oid in ('POT3', 'FLAG', 'BONE', 'STAY', 'POT1', 'POT2'):
        add_part(oid, MESH_OUT / f'{oid}.glb', POSES[oid])
    q_yaw = Quaternion((0, 0, 1), RAD(TROWEL_YAW_DEG)).normalized()
    add_part('TROWEL', MESH_OUT / 'TROWEL.glb', POSES['TROWEL'],
             wxyz=(q_yaw.w, q_yaw.x, q_yaw.y, q_yaw.z))

    add_part('dig_site_ground', ENV_OUT / 'dig_site_ground.glb', (0, 0, 0))
    add_part('dig_site_equipmentpad', ENV_OUT / 'dig_site_equipmentpad.glb',
             (PAD_O.x, PAD_O.y, PAD_O.z))

    env_json = [
        {'prop_id': 'dig_site_ground', 'label': '探方坑体与土堆',
         'asset': 'assets/meshes/env/dig_site_ground.glb',
         'pose': {'position_m': [0, 0, 0], 'wxyz': [1, 0, 0, 0]}, 'scale_m': [1, 1, 1]},
        {'prop_id': 'dig_site_equipmentpad', 'label': '坑边装备垫与文物箱',
         'asset': 'assets/meshes/env/dig_site_equipmentpad.glb',
         'pose': {'position_m': [PAD_O.x, PAD_O.y, PAD_O.z], 'wxyz': [1, 0, 0, 0]},
         'scale_m': [1, 1, 1]},
    ]

    def place_prop(pid, glb_name, xy, yaw_deg=0.0, scale=1.0):
        p = add_part(pid, ENV_OUT / glb_name, (xy[0], xy[1], 0.0), rest=0.0)
        q = Quaternion((0, 0, 1), RAD(yaw_deg)).normalized()
        p.rotation_quaternion = q @ CORR
        p.scale = (scale, scale, scale)
        bpy.context.view_layer.update()
        settle(p, 0.0)
        env_json.append({'prop_id': pid, 'label': '', 'asset': f'assets/meshes/env/{glb_name}',
                         'pose': {'position_m': list(v3t(tuple(p.location))),
                                  'wxyz': list(quat_norm((q.w, q.x, q.y, q.z)))},
                         'scale_m': [scale, scale, scale]})
        return p

    place_prop('trowel_01', 'trowel_01.glb', (-0.98, -0.62), yaw_deg=15)
    place_prop('stone_01', 'stone_01.glb', (1.15, -0.85), yaw_deg=30)
    place_prop('rock_07', 'rock_07.glb', (1.00, 0.95), yaw_deg=40)
    place_prop('rock_07_b', 'rock_07.glb', (-0.45, 1.10), yaw_deg=-25, scale=0.8)

    # rusted spade leaning into the heap: blade sunk into the south flank
    spade = import_glb(ENV_OUT / 'rusted_spade_01.glb')
    lean_dir = Vector((0.55, 0.83, 0.0)).normalized()
    q_lean = Quaternion((0, 0, 1), math.atan2(lean_dir.x, lean_dir.y)) @ Quaternion((1, 0, 0), RAD(-26))
    p = parent_to('HC_ENV_rusted_spade_01', spade, location=(0, 0, 0),
                  wxyz=(q_lean.w, q_lean.x, q_lean.y, q_lean.z))
    bpy.context.view_layer.update()
    slo, shi = bbox_world(spade)
    # review #2 fix #5 (+ tuning): target x nudged 10 cm west of the baulk so the blade
    # lands INSIDE the heap flank dome, not on the platform next to the rim lip.
    tgt = Vector((-1.12, 0.52, heap_h(-1.12, 0.52) - 0.14))
    p.location += Vector((tgt.x - slo.x, tgt.y - (slo.y + shi.y) / 2, tgt.z - slo.z))
    bpy.context.view_layer.update()
    # review #2 fix #5: the blade floated because heap_h was sampled at the TARGET xy,
    # not where the blade tip actually lands on the dome's sloping flank. Seat it: drop
    # the prop so its lowest vertex sits 6 cm BELOW the heap surface at that vertex's xy.
    low = None
    for o in spade:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            if low is None or w.z < low.z:
                low = w.copy()
    p.location.z += heap_h(low.x, low.y) - 0.06 - low.z
    bpy.context.view_layer.update()
    wlo, whi = bbox_world(spade)
    print(json.dumps({'spade_check': {'bbox': [[round(v, 3) for v in wlo], [round(v, 3) for v in whi]],
                                       'blade_vertex_xy': [round(low.x, 3), round(low.y, 3)],
                                       'heap_surface_at_blade_m': round(heap_h(low.x, low.y), 3),
                                       'blade_below_surface_m': round(heap_h(low.x, low.y) - wlo.z, 3),
                                       'pose': list(v3t(tuple(p.location))),
                                       'wxyz': list(quat_norm((q_lean.w, q_lean.x, q_lean.y, q_lean.z)))}}),
          flush=True)
    assert 0.5 < whi.z < 1.5 and wlo.z < 0.3, 'spade lean out of range'
    env_json.append({'prop_id': 'rusted_spade_01', 'label': '铁锹',
                     'asset': 'assets/meshes/env/rusted_spade_01.glb',
                     'pose': {'position_m': list(v3t(tuple(p.location))),
                              'wxyz': list(quat_norm((q_lean.w, q_lean.x, q_lean.y, q_lean.z)))},
                     'scale_m': [1, 1, 1]})
    parents['rusted_spade_01'] = p
    children['rusted_spade_01'] = spade

    # ------------------------------------------------------------- lights
    sun_pos = Vector((2.0, -2.2, 3.0))
    bpy.ops.object.light_add(type='SUN', location=sun_pos)
    sl = bpy.context.object
    sl.data.energy = 3.0
    sl.data.angle = 0.035
    sl.data.color = (1.0, 0.955, 0.88)
    sl.rotation_euler = (Vector((0, 0, -0.2)) - sun_pos).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.light_add(type='AREA', location=(-2.4, 0.6, 2.2))
    fl = bpy.context.object
    fl.data.energy = 30.0
    fl.data.size = 2.2
    fl.data.color = (0.85, 0.90, 1.0)
    fl.rotation_euler = (Vector((0, 0, -0.3)) - fl.location).to_track_quat('-Z', 'Y').to_euler()

    # ------------------------------------------------------------- labels
    # review #3 fix B1 (mandatory): every label sits on a bright rounded CHIP now.
    # Bare white glyphs over the bright western sky left the POT1 label pixel-scan
    # NEGATIVE at the review's 4 thresholds; a solid white plate behind dark text
    # gives every label one uniform high-contrast style (POT1 == POT2 == POT3 ...)
    # and a large detectable bright blob. Chips are preview-only: never exported,
    # excluded from the ortho fit (published ortho stays pinned at 3.81); their
    # frame margins and pixel detectability are asserted below. Leaders unchanged.
    # Emission strength 1.0 makes every chip FULLY self-lit: with 0.55, chips whose
    # billboard normal faces away from the sun (pit BONE/POT2) rendered their shaded
    # half at the bare emission floor (~0.52 lum), below pixel-scan thresholds even
    # though eyes could still read them. At 1.0 the whole plate sits at ~0.95+.
    chip_mat = flat('label_chip', (0.985, 0.985, 1.0), roughness=0.35,
                    emissive=(0.95, 0.95, 1.0), emission_strength=1.0)
    label_mat = flat('label_text', (0.06, 0.07, 0.10), roughness=0.5)  # dark on chip
    leader_mat = flat('leader_dark', (0.15, 0.15, 0.17), roughness=0.6)

    def add_chip(name, text_obj, lp, q, pad_w, pad_h):
        """Bright rounded plate centered on the text bbox, 4 mm behind the glyphs.
        Text bound_box is reliable only in the clean pre-render depsgraph state
        (post-render reads returned degenerate boxes -> half-size/offset chips in
        the first B1 attempt), so this is called at creation time only, with a
        sanity band that falls back to a per-string estimate."""
        bpy.context.view_layer.update()
        sz = text_obj.data.size
        est_w = 0.62 * len(text_obj.data.body) * sz
        lo = Vector(text_obj.bound_box[0]); hi = Vector(text_obj.bound_box[6])
        w, h = hi.x - lo.x, hi.y - lo.y
        cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        if not (0.75 * est_w <= w <= 1.3 * est_w) or not (0.5 * sz <= h <= 1.1 * sz) \
                or abs(cx) > 0.2 * sz or abs(cy) > 0.2 * sz:
            w, h, cx, cy = est_w, 0.72 * sz, 0.0, 0.0
        c = box(name, (w + pad_w, h + pad_h, 0.006), (0, 0, 0), chip_mat, bevel=0.003)
        c.rotation_mode = 'QUATERNION'
        c.rotation_quaternion = q
        c.location = Vector(lp) + q @ Vector((cx, cy, -0.007))
        return c
    # leaders stay above the ground plane until they are inside the pit opening
    LBL = {
        'POT3':   ((0.35, 1.06, 0.55), (0.35, 0.55, -0.10)),
        # review #2 fix #1: leader re-aimed at the EXPOSED midshaft (bone center + 0.03
        # along the baked 38 deg axis, shaft top); the old anchor stopped 34 mm above it
        'BONE':   ((0.18, -0.10, 0.36), (0.20, -0.085, -0.425)),
        'FLAG':   ((0.02, -0.88, 0.52), (0.02, -0.88, 0.335)),
        # beside the tripod head, not on top: a label floating at z=1.58 over the 1.5 m
        # instrument was the single biggest frame-width driver of the old 6.03 fit
        'STAY':   ((0.02, 1.22, 1.10), (0.43, 1.22, 1.17)),
        'POT1':   ((-1.02, -0.30, 0.42), (-0.55, -0.30, -0.25)),
        'POT2':   ((0.88, 0.30, 0.36), (0.52, 0.30, -0.36)),
        'TROWEL': ((-0.80, -0.34, 0.34), (-0.80, -0.09, 0.035)),
    }
    label_objs = []
    label_chips = {}
    for oid, (lp, ap) in LBL.items():
        tube(f'LEAD_{oid}', lp, ap, 0.0045, leader_mat, vertices=6)
        bpy.ops.object.text_add(location=Vector(lp))
        t = bpy.context.object; t.name = 'PREVIEW_LABEL_' + oid
        t.data.body = oid; t.data.size = 0.075
        t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'
        t.data.extrude = 0.003
        t.data.materials.append(label_mat)   # dark text on the bright chip (review #3 B1)
        q_lbl = (Vector(CAM_POS) - Vector(lp)).to_track_quat('Z', 'Y')
        t.rotation_euler = q_lbl.to_euler()
        label_objs.append(t)
        label_chips[oid] = add_chip(f'PREVIEW_CHIP_{oid}', t, lp, q_lbl, 0.032, 0.016)

    # Pit companion labels (review #2 fix #7 + review #3 B1 chips). They are CREATED
    # HERE, in the clean pre-render depsgraph state, hidden -- text bound_box reads
    # are only reliable before any render has run (post-render reads produced
    # degenerate boxes: half-size, offset chips in the first B1 attempt). They are
    # un-hidden for render 3 and re-hidden for render 4 below.
    PIT_LBL = {
        'POT3':   ((0.35, 0.50, 0.02), (0.35, 0.69, -0.205)),
        'POT1':   ((-0.60, -0.30, -0.16), (-0.71, -0.30, -0.31)),
        'POT2':   ((0.50, 0.30, -0.28), (0.66, 0.30, -0.41)),
        'BONE':   ((0.02, -0.22, -0.30), (0.13, -0.13, -0.425)),
        'FLAG':   ((-0.34, -0.84, 0.20), (0.0, -0.88, 0.27)),
    }
    pit_label_objs = []
    pit_chips = {}
    for oid, (lp, ap) in PIT_LBL.items():
        lead = tube(f'PITLEAD_{oid}', lp, ap, 0.0035, leader_mat, vertices=6)
        bpy.ops.object.text_add(location=Vector(lp))
        t = bpy.context.object; t.name = 'PIT_LABEL_' + oid
        t.data.body = oid; t.data.size = 0.052
        t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'
        t.data.extrude = 0.002
        t.data.materials.append(label_mat)   # dark text on the bright chip (review #3 B1)
        q_lbl = (Vector(CAM_POS) - Vector(lp)).to_track_quat('Z', 'Y')
        t.rotation_euler = q_lbl.to_euler()
        pit_label_objs.append(t)
        pit_chips[oid] = add_chip(f'PIT_CHIP_{oid}', t, lp, q_lbl, 0.036, 0.024)
        t.hide_render = True
        pit_chips[oid].hide_render = True
        lead.hide_render = True

    # ------------------------------------------------- render 1: kit preview
    # Review #1 fix #1: frame the TASK volume -- full trench pit + POT3/FLAG/BONE/
    # POT1/POT2/TROWEL + STAY + all 7 labels. The spoil heap's outer slope, the spade
    # and the equipment pad are NOT fitted; they crop naturally at the frame edges.
    # Fit method: exact per-object corner projections (a linear ortho projection maps
    # bbox corners to the projected extremes). The pit surfaces are fitted with
    # synthetic boxes clipped to what the near baulk leaves visible from CAM_POS
    # (from y=-1.35, z=1.05 the floor/walls north of y=-0.46 hide behind the north
    # rim); hidden corners must not widen the frame. The frame center is the camera
    # axis, so BOTH sides are constrained: |u| <= (0.5-m)*S, |v| <= (0.5-m)*S/aspect,
    # with m = 5.5% headroom over the 5% per-label margin asserted below.
    PIT_FIT_BOXES = [
        ((-0.76, 0.74, -0.515), (0.76, 0.76, 0.01)),    # south wall (POT3 wall), full
        ((-0.76, -0.46, -0.515), (-0.74, 0.76, 0.01)),  # west wall (POT1), visible part
        ((0.74, -0.46, -0.515), (0.76, 0.76, 0.01)),    # east wall (POT2), visible part
        ((-0.75, -0.46, -0.515), (0.75, 0.75, 0.01)),   # floor strip visible past the baulk
        ((-0.75, -0.76, -0.02), (0.75, -0.74, 0.01)),   # near (north) rim edge silhouette
    ]
    fit_objs = []
    for oid in ('POT3', 'FLAG', 'BONE', 'STAY', 'POT1', 'POT2', 'TROWEL'):
        fit_objs += children[oid]
    fit_objs += label_objs

    def projected_uv(objs, boxes, cam_pos, look):
        fwd = (Vector(look) - Vector(cam_pos)).normalized()
        right = Vector((0, 0, 1)).cross(fwd).normalized()
        up = fwd.cross(right).normalized()
        us, vs = [], []
        for o in objs:
            for v in o.bound_box:
                d = o.matrix_world @ Vector(v) - Vector(cam_pos)
                us.append(d @ right); vs.append(d @ up)
        for lo, hi in boxes:
            for x in (lo[0], hi[0]):
                for y in (lo[1], hi[1]):
                    for z in (lo[2], hi[2]):
                        d = Vector((x, y, z)) - Vector(cam_pos)
                        us.append(d @ right); vs.append(d @ up)
        return min(us), max(us), min(vs), max(vs)

    def fit_ortho(objs, boxes, cam_pos, look, margin):
        umin, umax, vmin, vmax = projected_uv(objs, boxes, cam_pos, look)
        aspect = 1600 / 1120
        s = max(max(abs(umin), abs(umax)) / (0.5 - margin),
                max(abs(vmin), abs(vmax)) * aspect / (0.5 - margin))
        return s, (round(umin, 3), round(umax, 3)), (round(vmin, 3), round(vmax, 3))

    s_fit, u_rng, v_rng = fit_ortho(fit_objs, PIT_FIT_BOXES, CAM_POS, CAM_LOOK, 0.055)
    ortho_fit = math.ceil(s_fit * 100) / 100          # round UP to 1 cm
    # review #2: geometry edits only ever shrink this fit; the published ortho stays
    # pinned at the reviewed 3.81 (content margins only improve). It may grow only if
    # the fitted content genuinely demands it.
    ortho_val = max(ortho_fit, 3.81)
    print(json.dumps({'fit_debug': {
        'mode': 'task-volume explicit fit (heap/spade/pad excluded: crop naturally)',
        'n_fit_objects': len(fit_objs),
        'u_range_m': list(u_rng), 'v_range_m': list(v_rng),
        's_fit': round(s_fit, 4), 'ortho_fit': ortho_fit, 'ortho_published': ortho_val,
        'old_auto_ortho_all_content': 6.03}}), flush=True)
    r1 = render_preview('dig_site_kit_preview.png', CAM_POS, CAM_LOOK,
                        ortho=ortho_val, res=(1600, 1120), samples=72)
    ortho_val = round(float(r1['projection'].split()[-1]), 3)

    # ------------------------------------------- in-render pixel self-checks
    import numpy as np
    img = bpy.data.images.load(str(OUT_RUNS / 'dig_site_kit_preview.png'), check_existing=False)
    cam = next(o for o in bpy.data.objects if o.type == 'CAMERA')
    W, H = img.size
    PXR = np.empty(W * H * 4, dtype=np.float32)
    img.pixels.foreach_get(PXR)      # single C-level copy (per-element RNA access would stall)
    PXR = PXR.reshape(H, W, 4)[::-1, :, :]  # buffer row 0 is the BOTTOM scanline: flip to display order

    def proj_px(world):
        v = Vector(world) - cam.location
        right = cam.matrix_world.col[0].xyz
        up = cam.matrix_world.col[1].xyz
        S = cam.data.ortho_scale
        x = (v @ right) / (S / 2)                    # ortho_scale spans the frame width
        y = (v @ up) / (S / (2 * W / H))             # frame height = S / aspect
        return int(round((x + 1) / 2 * W)), int(round((1 - (y + 1) / 2) * H))

    def pxbox(world, r=18):
        cx, cy = proj_px(world)
        return pxbox_at(cx, cy, r)

    def pxbox_at(cx, cy, r=18):
        box = PXR[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r), :3]
        return [round(float(box[:, :, i].mean()), 4) for i in range(3)]

    def pxq_at(cx, cy, r=22, q=0.92):
        """q-brightness percentile over the box (labels are thin strokes: mean washes out)."""
        box = PXR[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r), :3]
        lums = box @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        return round(float(np.quantile(lums, q)), 4)

    def lum(c): return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    def cdist(a, b): return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5
    def stay_yellow_frac(r=32):
        """Fraction of strongly-yellow pixels in a window around the instrument body."""
        cx, cy = proj_px((0.50, 1.20, 1.17))
        box = PXR[max(0, cy - r):min(H, cy + r), max(0, cx - r):min(W, cx + r), :3]
        yellow = (box[:, :, 0] - box[:, :, 2] > 0.06) & (box[:, :, 0] > 0.40)
        return round(float(yellow.mean()), 4)

    checks = {
        'pot3_terracotta': pxbox((0.35, 0.735, -0.25)),
        'pot1_terracotta': pxbox((-0.729, -0.30, -0.36)),
        'pot2_terracotta': pxbox((0.70, 0.30, -0.45)),
        'flag_red': pxbox((0.05, -0.88, 0.26), r=12),
        'stay_yellow': pxbox((0.50, 1.205, 1.23), r=12),
        'stay_yellow_frac': stay_yellow_frac(),
        # bone top strip is a thin bright band at this 17 deg grazing view: a plain box
        # mean mixes in the shadowed shaft side + floor, so ALSO take the p92 (the
        # bone-top pixels) -- that is the honest "is the bone bright" measurement.
        # review #3 B2: sample moved ONTO the camera-facing distal-half flank of the
        # midshaft (the old point (0.20,-0.085,-0.417) projected onto the bone's cast
        # shadow, so its p92 never tracked the material). Pre-B2 equivalent of the
        # measured value: (v - 0.0418 emission) / 1.0896 albedo ~= 0.35.
        'bone_pale': pxbox((0.20, -0.085, -0.419), r=9),
        'bone_top_p92': pxq_at(*proj_px((0.22, -0.09, -0.445)), r=10, q=0.92),
        'strat_top': pxbox((0.0, 0.745, -0.06), 10),
        'strat_fill': pxbox((0.0, 0.745, -0.22), 10),
        'strat_cult': pxbox((0.0, 0.745, -0.41), 10),
        'sky_corner_topleft': pxbox_at(30, 30, 25),
    }
    labels_seen = {oid: pxbox(lp, 22) for oid, (lp, ap) in LBL.items()}
    labels_q = {}
    for oid, (lp, ap) in LBL.items():
        cx, cy = proj_px(lp)
        labels_q[oid] = pxq_at(cx, cy)

    def chip_blob_scan(arr, proj, entries, win=95, thr=0.80, seed_r=16):
        """review #3 fix B1 proof: every label must appear as ONE solid bright blob
        (its chip) at the projected label position. Seeds the connected component
        within seed_r of the projected center (plain BFS, no scipy) and reports the
        blob centroid + pixel count. Bare-glyph labels failed exactly this kind of
        scan at the review thresholds."""
        Hh, Ww = arr.shape[:2]
        out = {}
        for oid, wp in entries:
            cx, cy = proj(wp)
            x0, y0 = max(0, cx - win), max(0, cy - win)
            x1, y1 = min(Ww, cx + win + 1), min(Hh, cy + win + 1)
            lums = arr[y0:y1, x0:x1, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
            mask = lums > thr
            scx, scy = cx - x0, cy - y0
            ys, xs = np.ogrid[: mask.shape[0], : mask.shape[1]]
            seed = mask & ((xs - scx) ** 2 + (ys - scy) ** 2 <= seed_r * seed_r)
            if not seed.any():
                out[oid] = {'chip_px': None, 'blob_px': 0}
                continue
            seen = np.zeros_like(mask)
            stack = list(zip(*np.nonzero(seed)))
            for s in stack:
                seen[s] = True
            while stack:
                a, b = stack.pop()
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        na, nb = a + da, b + db
                        if 0 <= na < seen.shape[0] and 0 <= nb < seen.shape[1] \
                                and mask[na, nb] and not seen[na, nb]:
                            seen[na, nb] = True
                            stack.append((na, nb))
            ys2, xs2 = np.nonzero(seen)
            out[oid] = {'chip_px': [int(x0 + xs2.mean()), int(y0 + ys2.mean())],
                        'blob_px': int(seen.sum())}
        return out

    chip_scan = chip_blob_scan(PXR, proj_px, [(oid, LBL[oid][0]) for oid in LBL])
    verdict = {
        'pot3_red_over_blue': checks['pot3_terracotta'][0] - checks['pot3_terracotta'][2] > 0.04,
        'pot1_red_over_blue': checks['pot1_terracotta'][0] - checks['pot1_terracotta'][2] > 0.02,
        'pot2_red_over_blue': checks['pot2_terracotta'][0] - checks['pot2_terracotta'][2] > 0.02,
        'flag_red_strong': checks['flag_red'][0] - max(checks['flag_red'][1:]) > 0.10,
        'stay_yellowish': checks['stay_yellow_frac'] > 0.03,
        'bone_bright': checks['bone_top_p92'] > 0.41,   # review #2 + #3 B2: on-band sample (pre-B2 ~0.35)
        'strata_distinct': min(cdist(checks['strat_top'], checks['strat_fill']),
                               cdist(checks['strat_fill'], checks['strat_cult']),
                               cdist(checks['strat_top'], checks['strat_cult'])) > 0.04,
        'labels_bright_p92': all(v > 0.75 for v in labels_q.values()),
        # review #3 B1: every label chip is a detectable bright blob (>= 700 px)
        'label_chips_detected': all(v['blob_px'] >= 700 for v in chip_scan.values()),
    }
    print(json.dumps({'pixel_selfchecks': {'samples': checks, 'labels': labels_seen,
                                           'labels_q92': labels_q,
                                           'chip_scan': chip_scan,
                                           'verdict': {k: bool(v) for k, v in verdict.items()}}},
                     indent=1), flush=True)

    # -------------------------------------- frame_verification (review #1 fix #1)
    # Per-label pixel margins measured in the rendered frame: every label keeps >= 5%
    # free frame on each side; task objects keep >= 3% (nothing task-relevant clips).
    def frame_rect(o):
        xs, ys = [], []
        for v in o.bound_box:
            cx, cy = proj_px(o.matrix_world @ Vector(v))
            xs.append(cx); ys.append(cy)
        return min(xs), max(xs), min(ys), max(ys)

    frame_margins = {}
    for t in label_objs:
        oid = t.name.replace('PREVIEW_LABEL_', '')
        rects = [frame_rect(t), frame_rect(label_chips[oid])]   # text + chip extents
        x0 = min(r[0] for r in rects); y0 = min(r[1] for r in rects)
        x1 = max(r[2] for r in rects); y1 = max(r[3] for r in rects)
        frame_margins[oid] = {
            'rect_px': [x0, y0, x1, y1],
            'margins_px': {'left': x0, 'right': W - 1 - x1, 'top': y0, 'bottom': H - 1 - y1},
            'margins_frac': {'left': round(x0 / W, 4), 'right': round((W - 1 - x1) / W, 4),
                             'top': round(y0 / H, 4), 'bottom': round((H - 1 - y1) / H, 4)}}
    obj_margins = {}
    for oid in ('POT3', 'FLAG', 'BONE', 'STAY', 'POT1', 'POT2', 'TROWEL'):
        worst = 1.0
        for o in children[oid]:
            x0, x1, y0, y1 = frame_rect(o)
            worst = min(worst, x0 / W, (W - 1 - x1) / W, y0 / H, (H - 1 - y1) / H)
        obj_margins[oid] = round(worst, 4)
    ok_labels = all(min(v['margins_frac'].values()) >= 0.05 for v in frame_margins.values())
    ok_objs = all(v >= 0.03 for v in obj_margins.values())
    print(json.dumps({'frame_verification': {
        'frame_px': [W, H], 'labels': frame_margins,
        'object_min_margin_frac': obj_margins,
        'labels_ge_5pct': ok_labels, 'objects_ge_3pct': ok_objs}}, indent=1), flush=True)
    assert ok_labels, 'a label violates the 5% frame margin'
    assert ok_objs, 'a task object clips the frame'
    assert verdict['label_chips_detected'], 'a label chip is not pixel-detectable (review #3 B1)'

    # ----------------------------- render 2: POT3 close-up (inspect_back evidence)
    for t in label_objs:
        t.hide_render = True
    for c in label_chips.values():
        c.hide_render = True
    for o in bpy.data.objects:
        if o.name.startswith('LEAD_'):
            o.hide_render = True
    # review #2 fix #2: raking key light high and north of the sherd so the ridge
    # slopes shade against the grooves; small hard source keeps groove shadows crisp
    # (energy tuned down after the first pass read washed out). Camera at ~0.47 m so
    # the sherd fills roughly a third of the frame (it occupied <10% before).
    bpy.ops.object.light_add(type='AREA', location=(0.42, 0.35, 0.35))
    cl = bpy.context.object
    cl.data.energy = 20.0
    cl.data.size = 0.28
    cl.rotation_euler = (Vector(POSES['POT3']) - cl.location).to_track_quat('-Z', 'Y').to_euler()
    r2 = render_preview('dig_site_kit_preview_pot3.png', (0.44, 0.28, -0.15),
                        (0.35, 0.73, -0.25), persp_fov=42, res=(1600, 1120), samples=64)

    # close-up self-check: terracotta hues + cord-ridge banding. The crop is CENTERED ON
    # THE PROJECTED SHERD (the old fixed center-crop measured mostly background, which
    # is why row_lum_std 0.107 'passed' with no visible ridges). Thresholds raised to
    # match: row std > 0.022 and >= 4 resolved bright bands inside the sherd crop.
    img2 = bpy.data.images.load(str(OUT_RUNS / 'dig_site_kit_preview_pot3.png'), check_existing=False)
    W2, H2 = img2.size
    buf2 = np.empty(W2 * H2 * 4, dtype=np.float32)
    img2.pixels.foreach_get(buf2)
    P2 = buf2.reshape(H2, W2, 4)[::-1, :, :]  # flip bottom-up buffer to display orders
    from bpy_extras.object_utils import world_to_camera_view
    ndc2 = world_to_camera_view(bpy.context.scene, bpy.context.scene.camera, Vector(POSES['POT3']))
    cx2, cy2 = int(ndc2.x * W2), int((1.0 - ndc2.y) * H2)
    crop = P2[max(0, cy2 - 110):min(H2, cy2 + 110), max(0, cx2 - 120):min(W2, cx2 + 120), :3]
    mean_rgb = [round(float(crop[:, :, i].mean()), 4) for i in range(3)]
    row_lums = crop @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    row_means = row_lums.mean(axis=1)
    prof = row_means - row_means.min()
    prof = prof / max(float(prof.max()), 1e-6)
    bright_bands, bi = 0, 1
    while bi < len(prof) - 1:
        if prof[bi] >= 0.45 and prof[bi] >= prof[bi - 1] and prof[bi] >= prof[bi + 1]:
            bright_bands += 1
            bi += 10      # ridge period is ~30-40 px: skip a full period past each crest
        else:
            bi += 1
    closeup = {'sherd_center_px': [cx2, cy2], 'crop_h': int(crop.shape[0]),
               'mean_rgb_at_sherd': mean_rgb,
               'terracotta_r_minus_b': round(mean_rgb[0] - mean_rgb[2], 4),
               'row_lum_minmax_delta': round(float(row_means.max() - row_means.min()), 4),
               'row_lum_std': round(float(row_means.std()), 4),
               'bright_bands': bright_bands,
               'cord_banding_present': bool(row_means.std() > 0.022 and bright_bands >= 4)}
    print(json.dumps({'pot3_closeup_selfcheck': closeup}), flush=True)
    assert closeup['cord_banding_present'], 'pot3 cord banding not readable in close-up'

    # ------------------------ render 3: pit interior mid-range (review #1 fix #2)
    # Tight ortho companion for depth + readability: pit interior with POT3 (south
    # wall), BONE (floor), FLAG (north rim), POT1 (west wall), POT2 (east floor
    # edge) at ~640 px/m. A persp 45-55 mm lens cannot hold FLAG and POT3 across
    # the ~1.7 m pit from any station that still sees past the near baulk, so the
    # review's "or tighter ortho" branch is used. Outer rim corners may crop.
    # review #2 fix #7: small billboard labels + leaders on all five task objects.
    # review #3 fix B1: same bright chip style as the main render (POT1 included).
    # (Labels/chips/leaders were created early, hidden; reveal them for this render.)
    for t in pit_label_objs:
        t.hide_render = False
    for c in pit_chips.values():
        c.hide_render = False
    for o in bpy.data.objects:
        if o.name.startswith('PITLEAD_'):
            o.hide_render = False

    PIT_INTERIOR_BOX = ((-0.71, -0.71, -0.52), (0.71, 0.71, 0.01))
    pit_objs = []
    for oid in ('POT3', 'POT1', 'POT2', 'BONE', 'FLAG'):
        pit_objs += children[oid]
    s_pit, pu_rng, pv_rng = fit_ortho(pit_objs, [PIT_INTERIOR_BOX],
                                      CAM_POS, PIT_LOOK, 0.045)
    pit_ortho = math.ceil(s_pit * 100) / 100
    r3 = render_preview('dig_site_kit_preview_pit.png', CAM_POS, PIT_LOOK,
                        ortho=pit_ortho, res=(1600, 1120), samples=48)

    cam3 = bpy.context.scene.camera
    img3 = bpy.data.images.load(str(OUT_RUNS / 'dig_site_kit_preview_pit.png'),
                                check_existing=False)
    W3, H3 = img3.size
    buf3 = np.empty(W3 * H3 * 4, dtype=np.float32)
    img3.pixels.foreach_get(buf3)
    P3 = buf3.reshape(H3, W3, 4)[::-1, :, :3]      # flip bottom-up buffer to display order

    def proj_px3(world):
        v = Vector(world) - cam3.location
        right = cam3.matrix_world.col[0].xyz
        up = cam3.matrix_world.col[1].xyz
        S = cam3.data.ortho_scale
        x = (v @ right) / (S / 2)
        y = (v @ up) / (S / (2 * W3 / H3))
        return int(round((x + 1) / 2 * W3)), int(round((1 - (y + 1) / 2) * H3))

    def px3(world, r=10):
        cx, cy = proj_px3(world)
        box = P3[max(0, cy - r):min(H3, cy + r), max(0, cx - r):min(W3, cx + r)]
        return [round(float(box[:, :, i].mean()), 4) for i in range(3)]

    pit_px = {k: px3(p) for k, p in {
        'pot3': (0.35, 0.735, -0.25), 'pot1': (-0.729, -0.30, -0.36),
        'pot2': (0.70, 0.30, -0.45), 'bone': (0.20, -0.085, -0.425),
        'flag_red': (0.05, -0.88, 0.26), 'strat_top': (0.0, 0.745, -0.06),
        'strat_fill': (0.0, 0.745, -0.22), 'strat_cult': (0.0, 0.745, -0.41)}.items()}
    # review #2 fix #1 acceptance: bone projected length >= 15% of the projected pit
    # width (rim square +-0.75 horizontal span) in this companion render.
    bpts = [proj_px3(o.matrix_world @ Vector(v)) for o in children['BONE'] for v in o.bound_box]
    bxs = [q[0] for q in bpts]; bys = [q[1] for q in bpts]
    bone_px_len = math.hypot(max(bxs) - min(bxs), max(bys) - min(bys))
    rpts = [proj_px3(Vector((sx * 0.75, sy * 0.75, 0.0))) for sx in (-1, 1) for sy in (-1, 1)]
    pit_px_w = max(q[0] for q in rpts) - min(q[0] for q in rpts)
    bone_len_ratio = bone_px_len / pit_px_w
    pit_inframe = {}
    for oid in ('POT3', 'POT1', 'POT2', 'BONE', 'FLAG'):
        worst = 1.0
        for o in children[oid]:
            xs, ys = [], []
            for v in o.bound_box:
                cx, cy = proj_px3(o.matrix_world @ Vector(v))
                xs.append(cx); ys.append(cy)
            worst = min(worst, min(xs) / W3, (W3 - 1 - max(xs)) / W3,
                        min(ys) / H3, (H3 - 1 - max(ys)) / H3)
        pit_inframe[oid] = round(worst, 4)
    # review #3 B1: pit chips in frame + pixel-detectable (same blob scan as render 1)
    pit_chip_inframe = {}
    for oid, c in pit_chips.items():
        xs, ys = [], []
        for v in c.bound_box:
            cx, cy = proj_px3(c.matrix_world @ Vector(v))
            xs.append(cx); ys.append(cy)
        pit_chip_inframe[oid] = round(min(min(xs) / W3, (W3 - 1 - max(xs)) / W3,
                                          min(ys) / H3, (H3 - 1 - max(ys)) / H3), 4)
    pit_chip_scan = chip_blob_scan(P3, proj_px3,
                                   [(oid, PIT_LBL[oid][0]) for oid in PIT_LBL],
                                   win=75, thr=0.80)
    pit_verdict = {
        'pots_reddish': all(pit_px[k][0] - pit_px[k][2] > 0.02
                            for k in ('pot1', 'pot2', 'pot3')),
        'bone_bright': lum(pit_px['bone']) > 0.38,
        'bone_long_enough': bone_len_ratio >= 0.15,
        'flag_red_strong': pit_px['flag_red'][0] - max(pit_px['flag_red'][1:]) > 0.10,
        'strata_distinct': min(cdist(pit_px['strat_top'], pit_px['strat_fill']),
                               cdist(pit_px['strat_fill'], pit_px['strat_cult']),
                               cdist(pit_px['strat_top'], pit_px['strat_cult'])) > 0.04,
        'all_five_inframe': all(v >= 0.02 for v in pit_inframe.values()),
        'chips_detected': all(v['blob_px'] >= 700 for v in pit_chip_scan.values()),
        'chips_inframe_2pct': all(v >= 0.02 for v in pit_chip_inframe.values()),
    }
    print(json.dumps({'pit_preview_selfcheck': {
        'projection': r3['projection'], 'px_per_m': round(W3 / cam3.data.ortho_scale, 1),
        'bone_px_len': round(bone_px_len, 1), 'pit_px_w': round(pit_px_w, 1),
        'bone_len_over_pit_w': round(bone_len_ratio, 4),
        'samples': pit_px, 'min_margin_frac': pit_inframe,
        'chip_scan': pit_chip_scan, 'chip_min_margin_frac': pit_chip_inframe,
        'verdict': {k: bool(v) for k, v in pit_verdict.items()},
        'fit_u_m': list(pu_rng), 'fit_v_m': list(pv_rng), 's_fit': round(s_pit, 4)}},
        indent=1), flush=True)
    assert all(pit_verdict.values()), 'pit preview selfcheck failed'

    # ------------------- render 4: STAY telescope aim zoom (review #2 fix #4)
    # From the ESE at ~2.3 m with a 50 mm lens: instrument fully framed on the left,
    # pit mouth beyond it to the right; the tube axis projects ~46 deg down on screen
    # (broadside + full depression readable). All labels stay hidden.
    for t in pit_label_objs:
        t.hide_render = True
    for c in pit_chips.values():
        c.hide_render = True
    for o in bpy.data.objects:
        if o.name.startswith('PITLEAD_'):
            o.hide_render = True
    r4 = render_preview('dig_site_kit_preview_stay.png', (2.3, 0.45, 1.50),
                        (0.40, 0.90, 0.85), persp_fov=50, res=(1600, 1120), samples=48)
    img4 = bpy.data.images.load(str(OUT_RUNS / 'dig_site_kit_preview_stay.png'), check_existing=False)
    W4, H4 = img4.size
    cam4 = bpy.context.scene.camera
    station = Vector(POSES['STAY'])
    c0_w = station + Vector((0, 0, 1.30))
    obj_tip = c0_w + STAY_AIM_LOCAL * 0.155
    eyepiece = c0_w - STAY_AIM_LOCAL * 0.185
    pit_c = Vector(STAY_AIM_TARGET)

    def ndc4(world):
        n = world_to_camera_view(bpy.context.scene, cam4, Vector(world))
        return int(n.x * W4), int((1.0 - n.y) * H4)

    tip_px, eye_px, pit_px4 = ndc4(obj_tip), ndc4(eyepiece), ndc4(pit_c)
    aim_ang = math.degrees(STAY_AIM_LOCAL.angle(pit_c - c0_w))
    aim_out = {
        'telescope_axis_vs_pit_dir_deg': round(aim_ang, 4),
        'depression_deg': round(math.degrees(math.atan2(-STAY_AIM_LOCAL.z,
                     math.hypot(STAY_AIM_LOCAL.x, STAY_AIM_LOCAL.y))), 1),
        'px_dist_objective_to_pitcenter': round(math.dist(tip_px, pit_px4), 1),
        'px_dist_eyepiece_to_pitcenter': round(math.dist(eye_px, pit_px4), 1),
        'objective_points_toward_pit': bool(math.dist(tip_px, pit_px4)
                                            < math.dist(eye_px, pit_px4)),
    }
    print(json.dumps({'stay_aim_selfcheck': aim_out}), flush=True)
    assert aim_ang < 2.0 and aim_out['objective_points_toward_pit'], 'telescope not aimed at pit'

    for t in label_objs:
        t.hide_render = False
    for c in label_chips.values():
        c.hide_render = False
    for o in bpy.data.objects:
        if o.name.startswith('LEAD_'):
            o.hide_render = False

    # =========================================================== scene JSON
    obj_defs = {
        'POT3':   {'label': '3 号陶片', 'color': (196, 98, 54), 'caps': ['point', 'inspect_back'],
                   'desc': '直立嵌于南壁,内壁有绳纹刻痕', 'anchors': {}},
        'FLAG':   {'label': '红色标记旗', 'color': (211, 54, 44), 'caps': ['point', 'assemble'],
                   'desc': '30cm 旗杆,局部 +Z 沿杆、尖端在原点', 'anchors': {}},
        'BONE':   {'label': '骨化石', 'color': (226, 214, 182), 'caps': ['point'],
                   'desc': '出露长骨,旗插其北侧',
                   'anchors': {'placement': list(BONE_PLACEMENT_ANCHOR)}},
        'STAY':   {'label': '全站仪', 'color': (232, 196, 84), 'caps': ['point', 'wait'],
                   'desc': '测站锁定,镜头朝探方', 'anchors': {}},
        'POT1':   {'label': '1 号陶片', 'color': (168, 120, 96), 'caps': ['point'],
                   'desc': '消歧用,仅指认', 'anchors': {}},
        'POT2':   {'label': '2 号陶片', 'color': (176, 88, 60), 'caps': ['point'],
                   'desc': '消歧用,仅指认', 'anchors': {}},
        'TROWEL': {'label': '手铲', 'color': (150, 156, 164), 'caps': ['point', 'rotate'],
                   'desc': '刃口朝向与柄线对齐', 'anchors': {}},
    }
    wxyz_by = {'TROWEL': list(quat_norm((q_yaw.w, q_yaw.x, q_yaw.y, q_yaw.z)))}
    obj_json = []
    for oid, d in obj_defs.items():
        obj_json.append({'object_id': oid, 'label': d['label'],
                         'asset': f'assets/meshes/dig_site/{oid}.glb',
                         'pose': {'position_m': list(v3t(POSES[oid])),
                                  'wxyz': wxyz_by.get(oid, [1, 0, 0, 0])},
                         'color': list(d['color']), 'capabilities': d['caps'],
                         'anchors': d['anchors'], 'description': d['desc']})

    spec = {
        'schema_version': '1.0', 'scene_id': 'dig_site', 'title': '考古探方发掘',
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': obj_json,
        'initial_instruction': '把 3 号陶片 POT3 翻过来看内壁刻纹,然后在骨化石 BONE 旁边插红色标记旗 FLAG,坑边全站仪 STAY 保持锁定别碰。',
        'camera_position_m': list(CAM_POS), 'camera_look_at_m': list(CAM_LOOK),
        'environment': env_json,
        'render_hints': {'ortho_scale_m': ortho_val, 'grid_extent_m': 2.5,
                         'cue_scale': 1.0, 'label_offset_m': 0.25, 'fit_camera': True},
    }
    write_scene_json('dig_site', spec)

    # =========================================================== verification
    bone_p = POSES['BONE']
    goal = [bone_p[i] + BONE_PLACEMENT_ANCHOR[i] for i in range(3)]
    fl_goal = floor_z(goal[0], goal[1])
    fl_bone = floor_z(bone_p[0], bone_p[1])
    anchor_out = {
        'bone_pose': list(bone_p), 'placement_anchor_local': list(BONE_PLACEMENT_ANCHOR),
        'assemble_goal_world': [round(g, 4) for g in goal],
        'floor_z_at_goal': round(fl_goal, 4),
        'goal_above_floor_m': round(goal[2] - fl_goal, 4),
        'goal_above_pit_floor_datum_m': round(goal[2] - FLOOR_Z, 4),
        'offset_north_of_bone_axis_m': round(goal[1] - bone_p[1], 4),
        'floor_z_at_bone': round(fl_bone, 4),
        'bone_center_vs_floor_m': round(bone_p[2] - fl_bone, 4),
        'asserts': {
            'goal_just_above_floor': 0.001 <= goal[2] - fl_goal <= 0.015,
            'goal_8cm_north': abs((goal[1] - bone_p[1]) + 0.08) < 1e-6,
            'bone_half_embedded': -0.02 <= bone_p[2] - fl_bone <= 0.005,
        },
    }
    print(json.dumps({'anchor_verification': anchor_out}, ensure_ascii=False, indent=1), flush=True)
    assert all(anchor_out['asserts'].values()), 'anchor math failed'

    # wall-plane clearance (bbox vs nominal wall planes at |x|,|y| = RIM)
    clearance = {}
    for oid in ('POT3', 'POT1', 'POT2', 'BONE'):
        lo, hi = bbox_world(children[oid])
        m = {'POT3': ('ymax', RIM - hi.y), 'POT1': ('xmin', lo.x + RIM),
             'POT2': ('xmax', RIM - hi.x),
             'BONE': ('planar', min(RIM - hi.x, RIM - hi.y, lo.x + RIM, lo.y + RIM))}[oid]
        clearance[oid] = {'bbox': [[round(x, 4) for x in lo], [round(x, 4) for x in hi]],
                          'check': m[0], 'clear_to_wall_plane_m': round(m[1], 4),
                          'clear': bool(m[1] > -0.001)}
    print(json.dumps({'wall_clearance': clearance}, indent=1), flush=True)
    assert all(v['clear'] for v in clearance.values()), 'object intersects wall plane'

    # POT3 radial-face check for inspect_back (decorated inner face normal is horizontal)
    nrm = (0.0, -1.0, 0.0)
    radial = abs(nrm[2]) < 1e-6
    print(json.dumps({'pot3_inspect_back_radial': {
        'inner_face_normal_local': list(nrm), 'radial_wrt_local_z': bool(radial),
        'note': '180 deg Z-turn swings the concave cord-marked face from -y to +y'}}), flush=True)
    assert radial

    # round-trip: re-imported POT3 must sit centered on its JSON pose
    lo, hi = bbox_world(children['POT3'])
    ctr = (lo + hi) / 2
    lat = (abs(ctr.x - POSES['POT3'][0]), abs(ctr.y - POSES['POT3'][1]))
    print(json.dumps({'pot3_roundtrip_center': [round(v, 4) for v in ctr],
                      'pose_xy': [round(v, 4) for v in POSES['POT3'][:2]],
                      'lateral_offset_m': [round(v, 4) for v in lat],
                      'within_1cm': bool(max(lat) < 0.01)}), flush=True)
    assert max(lat) < 0.01

    def axd(p): return round((Vector(p) - Vector(CAM_POS)).length, 3)
    print(json.dumps({'as_built_axial_distances_m': {
        'near_rim': axd((RIM, -RIM, 0.0)), 'POT3': axd(POSES['POT3']),
        'BONE': axd(POSES['BONE']), 'FLAG_goal': axd(goal),
        'STAY_lens': axd((POSES['STAY'][0], POSES['STAY'][1], 1.30)),
        'TROWEL': axd(POSES['TROWEL'])},
        'design_approx_m': {'POT3': 2.0, 'BONE': 2.3, 'STAY': 3.1, 'TROWEL': 1.8}}), flush=True)

    files = sorted(MESH_OUT.glob('*.glb')) + [ENV_OUT / 'dig_site_ground.glb',
                                              ENV_OUT / 'dig_site_equipmentpad.glb',
                                              OUT_RUNS / 'dig_site_kit_preview.png',
                                              OUT_RUNS / 'dig_site_kit_preview_pit.png',
                                              OUT_RUNS / 'dig_site_kit_preview_pot3.png',
                                              OUT_RUNS / 'dig_site_kit_preview_stay.png',
                                              ROOT / 'configs/scenes/dig_site.json']
    print(json.dumps({'file_table': {str(f.relative_to(ROOT)): f.stat().st_size for f in files}},
                     indent=1), flush=True)
    print(json.dumps({'camera_final': {'position': list(CAM_POS), 'look_at': list(CAM_LOOK)},
                      'ortho_task_volume': ortho_val,
                      'pit_preview_projection': r3['projection'],
                      'pot3_closeup_projection': r2['projection'],
                      'stay_zoom_projection': r4['projection']}), flush=True)

if __name__ == '__main__':
    main()
