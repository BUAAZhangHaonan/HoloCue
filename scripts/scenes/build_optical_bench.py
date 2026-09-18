"""Build the optical_bench scene kit (interactive GLBs + env GLBs + scene JSON + previews).

Run via:
  cd /home/hdd3/zhanghaonan/projects/holocue && .venv/bin/python scripts/guard/resource_guard.py \
      --rss-limit-gb 12 --execute -- /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/scenes/build_optical_bench.py

Layout datum: breadboard TOP is z=0. Breadboard 1.25(y) x 0.65(x) m centered x=0,
world y in [-0.45,+0.80] (pose y=+0.175). Lab table top at z=-0.06 under everything.
Beam axis: world line x=0, z=0.120 running along +y:
  laser y=-0.30 (exit z=0.12) -> L1/POST2 y=+0.15 -> L2 y=+0.35 -> M y=+0.55
  -> slight fold ~10 deg toward -x -> TARGET (-0.106, +1.15) on the table (base z=-0.06).
M is a fine-steering mirror nearly perpendicular to the beam (mirror plane vertical,
reflective normal world ~(+0.996,+0.087,0) -> M yaw 95 deg); TARGET yaw 190 deg faces
the incoming beam back along the folded ray. POST2 post top local z=+0.070, insertion
anchor [0,0,0.100] = post top +0.03 (L1 mount drops on, its 40mm clamp sleeve engages
the top 14mm of the post; L1 origin = kinematic base plate center).
"""
import bpy, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import *  # noqa: F401,F403
from common import _framed_extents, _projected_size
from mathutils import Vector, Euler, Quaternion, Matrix

KIT = ROOT/'scenes/optical_bench/meshes'
SCENE_ENV = scene_env('optical_bench')
FONT_PATH = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')

BEAM_Z = 0.120                     # world beam height above breadboard top
POST_TOP = 0.070                   # POST2 post top, local z
ANCHOR_Z = 0.100                   # insertion anchor = post top + 0.03
Q_M = Quaternion((0, 0, 1), math.radians(95))      # M world yaw
Q_TGT = Quaternion((0, 0, 1), math.radians(190))   # TARGET world yaw

def rdeg(a): return math.radians(a)

def smooth(objs, angle=40):
    objs = objs if isinstance(objs, list) else [objs]
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        return objs
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.shade_smooth()
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        me = o.data
        me.use_auto_smooth = True
        me.auto_smooth_angle = rdeg(angle)
    return objs

def add_uv(objs):
    for o in objs:
        if o.type != 'MESH':
            continue
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=rdeg(66), island_margin=0.004)
        bpy.ops.object.mode_set(mode='OBJECT')
    return objs

def text_mesh(name, body, size, location, mat, align='CENTER', euler=(None, None, None)):
    """Font object converted to mesh so glTF export keeps it. Default orientation
    faces local +y (reading up along +z): euler (90,0,180) -> x=-x, y=+z, z=+y."""
    font = bpy.data.fonts.load(str(FONT_PATH)) if FONT_PATH.exists() else None
    rot = euler if euler[0] is not None else (rdeg(90), 0, rdeg(180))
    bpy.ops.object.text_add(location=location, rotation=rot)
    t = bpy.context.object
    t.name = name
    t.data.body = body
    t.data.size = size
    t.data.align_x = align
    t.data.align_y = 'CENTER'
    t.data.extrude = 0.0006
    if font:
        t.data.font = font
    t.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    return t

# ---------------------------------------------------------------- materials
MAT = {}
def M(name, rgba, metallic=0.0, roughness=0.55, emissive=None, es=1.0, alpha=1.0):
    if alpha < 1.0:
        mat = flat(name, rgba, metallic, roughness)
        mat.blend_method = 'BLEND'
        mat.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = alpha
        return mat
    if emissive is not None and len(emissive) == 3:
        emissive = tuple(emissive) + (1.0,)
    return flat(name, rgba, metallic, roughness, emissive, es)

def pbr_nodiffuse(name, tex_id, rgba, scale=1.0, metallic=None, roughness=None):
    """PBR with texture normal/roughness but a flat base color (for tinted metals)."""
    mat = flat(name, rgba, metallic, roughness)
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeTexCoord'); uv.location = (-1400, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-1200, 0)
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(uv.outputs['UV'], mp.inputs['Vector'])
    from common import _img as _ld
    for prefix, target in (('nor_gl', 'Normal'), ('Rough', 'Roughness')):
        img = _ld(tex_id, prefix)
        if img is None:
            continue
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
        tex.location = (-1000, -300*len(nt.nodes) % 1200 - 300)
        nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
        if target == 'Normal':
            nrm = nt.nodes.new('ShaderNodeNormalMap'); nrm.location = (-600, -700)
            nt.links.new(tex.outputs['Color'], nrm.inputs['Color'])
            nt.links.new(nrm.outputs['Normal'], bsdf.inputs['Normal'])
        else:
            nt.links.new(tex.outputs['Color'], bsdf.inputs[target])
    return mat

def mats():
    MAT.clear()
    MAT['ano']     = M('OB_ano',     (0.055, 0.058, 0.066, 1), metallic=0.5, roughness=0.42)
    MAT['ano2']    = M('OB_ano2',    (0.105, 0.110, 0.125, 1), metallic=0.55, roughness=0.38)
    MAT['steel']   = M('OB_steel',   (0.55, 0.57, 0.60, 1), metallic=0.95, roughness=0.28)
    MAT['steel_dk']= M('OB_steel_dk',(0.20, 0.21, 0.23, 1), metallic=0.85, roughness=0.42)
    MAT['white']   = M('OB_white',   (0.93, 0.93, 0.94, 1), roughness=0.45)
    MAT['tick']    = M('OB_tick',    (0.62, 0.63, 0.65, 1), roughness=0.5)
    MAT['screen']  = M('OB_screen',  (0.945, 0.94, 0.925, 1), roughness=0.85)
    MAT['darkline']= M('OB_darkline',(0.05, 0.05, 0.055, 1), roughness=0.6)
    MAT['orange']  = M('OB_orange',  (0.90, 0.42, 0.08, 1), roughness=0.6)
    MAT['glass']   = M('OB_glass',   (0.72, 0.90, 0.86, 1), metallic=0.0, roughness=0.05, alpha=0.45)
    MAT['mirror']  = M('OB_mirror',  (0.91, 0.93, 0.96, 1), metallic=1.0, roughness=0.04)
    MAT['led']     = M('OB_led',     (0.45, 0.05, 0.04, 1), emissive=(0.9, 0.08, 0.05), es=1.6)
    MAT['beam']    = M('OB_beam',    (0.55, 0.04, 0.03, 1), emissive=(0.85, 0.06, 0.04), es=1.2, alpha=0.5)
    MAT['spot']    = M('OB_spot',    (0.62, 0.05, 0.03, 1), emissive=(0.95, 0.10, 0.06), es=2.4)
    MAT['plate']   = M('OB_plate',   (0.88, 0.87, 0.82, 1), roughness=0.5)
    MAT['board']   = pbr_nodiffuse('OB_board', 'metal_plate', (0.062, 0.066, 0.075, 1),
                                   metallic=0.55, roughness=0.42, scale=2.5)
    MAT['hole']    = M('OB_hole',    (0.018, 0.020, 0.024, 1), metallic=0.3, roughness=0.35)

# ---------------------------------------------------------------- shared builders
def base_plate(prefix, r=0.030, h=0.010, mat=None):
    """Post base with two mounting screws. Bottom at local z=0."""
    objs = [cyl(f'{prefix}_base', r, h, (0, 0, h/2), mat or MAT['ano'], vertices=32)]
    for sx in (-1, 1):
        objs.append(cyl(f'{prefix}_bscrew', 0.0045, 0.004, (sx*0.011, 0, h + 0.001), MAT['steel'],
                        vertices=10))
    return objs

def lens_mount(prefix, z0=0.0):
    """Kinematic ring mount family: 40mm clamp sleeve below the base plate (plate
    CENTER at z0), crown, torus ring (axis local +y) with Phi25 glass lens at
    z0+0.0205, three rear adjuster screws + thumb knobs."""
    objs = []
    objs.append(cyl(f'{prefix}_sleeve', 0.008, 0.040, (0, 0, z0 - 0.024), MAT['ano'], vertices=24))
    kn = cyl(f'{prefix}_lockknob', 0.0035, 0.006, (0.0095, 0, z0 - 0.034), MAT['steel_dk'],
             rot=(0, rdeg(90), 0), vertices=12)
    objs.append(kn)
    objs.append(cyl(f'{prefix}_plate', 0.022, 0.008, (0, 0, z0), MAT['ano2'], vertices=32))
    objs.append(box(f'{prefix}_crown', (0.020, 0.026, 0.012), (0, 0, z0 + 0.010), MAT['ano2'], bevel=0.002))
    zc = z0 + 0.0205
    bpy.ops.mesh.primitive_torus_add(major_radius=0.019, minor_radius=0.0065,
                                     location=(0, 0, zc), rotation=(rdeg(90), 0, 0),
                                     major_segments=40, minor_segments=14)
    ring = bpy.context.object; ring.name = f'{prefix}_ring'
    ring.data.materials.append(MAT['ano'])
    objs.append(ring)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0125, location=(0, 0, zc), segments=32, ring_count=16)
    lens = bpy.context.object; lens.name = f'{prefix}_lens'
    lens.scale = (1.0, 0.36, 1.0)
    lens.data.materials.append(MAT['glass'])
    objs.append(lens)
    for a in (90, 210, 330):
        x, z = 0.024*math.cos(rdeg(a)), zc + 0.024*math.sin(rdeg(a))
        objs.append(cyl(f'{prefix}_adj', 0.002, 0.012, (x, -0.008, z),
                        MAT['steel'], rot=(rdeg(90), 0, 0), vertices=12))
        objs.append(cyl(f'{prefix}_knob', 0.0042, 0.005, (x, -0.0165, z), MAT['ano2'],
                        rot=(rdeg(90), 0, 0), vertices=16))
    smooth([o for o in objs if 'lens' in o.name or 'ring' in o.name])
    return objs

# ---------------------------------------------------------------- interactive builders
def build_L1():
    """Phi25 biconvex lens in a kinematic ring mount on a short post clamp.
    Origin at mount base (plate) center; clamp sleeve spans local z -0.044..-0.004."""
    return lens_mount('L1', z0=0.0)

def build_POST2():
    """O12 post 60mm on M6 base plate + alignment pin + printed index marker ring.
    Origin at base center; post top local z=+0.070, pin to +0.077."""
    objs = base_plate('POST2')
    objs.append(cyl('POST2_post', 0.006, 0.060, (0, 0, 0.040), MAT['ano2'], vertices=24))
    objs.append(cyl('POST2_index', 0.0069, 0.004, (0, 0, 0.062), MAT['orange'], vertices=24))
    objs.append(cyl('POST2_pin', 0.00125, 0.007, (0, 0, POST_TOP + 0.0035), MAT['steel'], vertices=10))
    objs.append(text_mesh('POST2_num2', '2', 0.0068, (0.0143, 0, 0.006), MAT['white'],
                          euler=(rdeg(90), 0, rdeg(90))))
    smooth([o for o in objs if o.name == 'POST2_post'])
    return objs

def build_L2():
    """Same mount family as L1, already mounted on its own post at beam height
    (lens center local z=0.1205 = beam height). Origin at base center."""
    objs = base_plate('L2')
    objs.append(cyl('L2_post', 0.006, 0.046, (0, 0, 0.033), MAT['ano2'], vertices=24))
    objs.extend(lens_mount('L2m', z0=0.100))
    smooth([o for o in objs if o.name == 'L2_post'])
    return objs

def build_M():
    """Phi25 first-surface mirror in a gimbal mount on a degree-tick rotation base.
    Mirror disc axis = local y (reflective face local -Y, coating label on local +Y
    radial back face). Mirror center local (0, 0, 0.120). White index line across
    the back frame. Origin at base center."""
    objs = []
    objs.append(cyl('M_base', 0.035, 0.008, (0, 0, 0.004), MAT['ano'], vertices=48))
    # raised scale bezel ring on the base, then the degree tick arc on it (5 deg steps)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.032, minor_radius=0.0035,
                                     location=(0, 0, 0.008), major_segments=56, minor_segments=8)
    bez = bpy.context.object; bez.name = 'M_scalebez'
    bez.scale = (1.0, 1.0, 0.30)
    bez.data.materials.append(MAT['ano2'])
    objs.append(bez)
    for i, adeg in enumerate(range(225, 316, 5)):
        a = rdeg(adeg)
        major = (i % 3) == 0
        rr = 0.0325
        o = box(f'M_tick{adeg}', (0.0085, 0.0024, 0.0024) if major else (0.0045, 0.0018, 0.0018),
                (rr*math.cos(a), rr*math.sin(a), 0.0094), MAT['white'] if major else MAT['tick'], bevel=0)
        o.rotation_euler = (0, 0, a)
        objs.append(o)
    objs.append(cyl('M_rotor', 0.028, 0.010, (0, 0, 0.013), MAT['ano2'], vertices=40))
    # pointer: orange index color (same language as POST2's marker ring) so the
    # pointer-to-tick alignment stays readable at preview scale; tip reaches the
    # rotor edge, visually meeting the white major tick on the bezel arc.
    objs.append(box('M_pointer', (0.005, 0.007, 0.003), (0, -0.0245, 0.0195), MAT['orange'], bevel=0))
    objs.append(cyl('M_post', 0.006, 0.068, (0, 0, 0.052), MAT['ano2'], vertices=24))
    objs.append(box('M_forkbase', (0.030, 0.024, 0.014), (0, 0, 0.093), MAT['ano'], bevel=0.003))
    for sx in (-1, 1):
        objs.append(box(f'M_tine{sx}', (0.006, 0.018, 0.048), (sx*0.0225, 0, 0.124), MAT['ano'], bevel=0.002))
        objs.append(cyl(f'M_pivot{sx}', 0.0015, 0.010, (sx*0.0190, 0, 0.120), MAT['steel'],
                        rot=(0, rdeg(90), 0), vertices=10))
    for sx in (-1, 1):  # gimbal adjusters facing the beam/camera quadrant
        objs.append(cyl(f'M_adj{sx}', 0.0035, 0.006, (sx*0.010, -0.016, 0.100), MAT['ano2'],
                        rot=(rdeg(90), 0, 0), vertices=14))
    # mirror disc: reflective -Y cap, back frame covers +Y cap
    objs.append(cyl('M_mirror', 0.0125, 0.005, (0, 0, 0.120), MAT['mirror'],
                    rot=(rdeg(90), 0, 0), vertices=40))
    objs.append(cyl('M_backframe', 0.018, 0.004, (0, 0.0035, 0.120), MAT['ano2'],
                    rot=(rdeg(90), 0, 0), vertices=40))
    # white index line across the back frame (top band) + coating label plate below it
    objs.append(box('M_wline', (0.020, 0.0012, 0.0032), (0, 0.0057, 0.1320), MAT['white'], bevel=0))
    objs.append(box('M_labelplate', (0.028, 0.0012, 0.016), (0, 0.0058, 0.1180), MAT['darkline'], bevel=0))
    objs.append(text_mesh('M_labelHR', 'HR-45°', 0.0075, (0, 0.0068, 0.1218), MAT['white']))
    objs.append(text_mesh('M_label1064', '1064', 0.0075, (0, 0.0068, 0.1145), MAT['white']))
    smooth([o for o in objs if o.name in ('M_mirror', 'M_post', 'M_base', 'M_rotor', 'M_backframe')])
    return objs

def build_TARGET():
    """150x120mm white matte screen on post + base. Face normal local +y with fine
    crosshair + concentric circles + corner screws; faint red laser spot slightly
    off-center. Origin at base center; screen center local z=0.180."""
    objs = base_plate('TGT', r=0.040)
    objs.append(cyl('TGT_post', 0.006, 0.114, (0, 0, 0.067), MAT['ano2'], vertices=24))
    objs.append(box('TGT_back', (0.158, 0.005, 0.128), (0, -0.0025, 0.180), MAT['ano2'], bevel=0.002))
    objs.append(box('TGT_screen', (0.150, 0.008, 0.120), (0, 0.004, 0.180), MAT['screen'], bevel=0.001))
    yf = 0.0086
    objs.append(box('TGT_crossH', (0.132, 0.0008, 0.0016), (0, yf, 0.180), MAT['darkline'], bevel=0))
    objs.append(box('TGT_crossV', (0.0016, 0.0008, 0.102), (0, yf, 0.180), MAT['darkline'], bevel=0))
    for rr in (0.012, 0.024, 0.042):
        bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=0.0008,
                                         location=(0, yf, 0.180), rotation=(rdeg(90), 0, 0),
                                         major_segments=48, minor_segments=6)
        t = bpy.context.object; t.name = f'TGT_ring{int(rr*1000)}'
        t.data.materials.append(MAT['darkline'])
        objs.append(t)
    for sx in (-1, 1):
        for sz in (-1, 1):
            objs.append(cyl('TGT_screw', 0.0022, 0.002, (sx*0.068, yf - 0.0004, 0.180 + sz*0.053),
                            MAT['steel_dk'], rot=(rdeg(90), 0, 0), vertices=10))
    objs.append(cyl('TGT_spot', 0.0035, 0.0006, (0.006, yf + 0.0003, 0.176), MAT['spot'],
                    rot=(rdeg(90), 0, 0), vertices=16))
    smooth([o for o in objs if o.name == 'TGT_post'])
    return objs

# ---------------------------------------------------------------- env builders
def build_breadboard():
    """1.25(y) x 0.65(x) x 0.06 black anodized breadboard, origin TOP-center
    (top local z=0): O5 hole discs at 25mm pitch, side handles, 4 leveling feet."""
    objs = []
    objs.append(box('OB_BOARD_slab', (0.65, 1.25, 0.052), (0, 0, -0.026), MAT['board'], bevel=0.003))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0025, depth=0.0008,
                                        location=(-0.3, -0.6, -0.0002), vertices=20)
    grid = bpy.context.object; grid.name = 'OB_BOARD_holes'
    grid.data.materials.append(MAT['hole'])
    mx = grid.modifiers.new('GX', 'ARRAY')
    mx.use_constant_offset = True; mx.use_relative_offset = False
    mx.constant_offset_displace = (0.025, 0, 0); mx.count = 25
    my = grid.modifiers.new('GY', 'ARRAY')
    my.use_constant_offset = True; my.use_relative_offset = False
    my.constant_offset_displace = (0, 0.025, 0); my.count = 49
    bpy.context.view_layer.objects.active = grid
    bpy.ops.object.modifier_apply(modifier='GX')
    bpy.ops.object.modifier_apply(modifier='GY')
    objs.append(grid)
    for sx in (-1, 1):
        objs.append(box(f'OB_BOARD_handle{sx}', (0.048, 0.150, 0.014), (sx*0.3495, 0, -0.030),
                        MAT['ano'], bevel=0.003))
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(cyl(f'OB_BOARD_foot{sx}{sy}', 0.009, 0.008, (sx*0.27, sy*0.55, -0.056),
                            MAT['steel_dk'], vertices=18))
    return objs

def build_laser():
    """Compact DPSS laser head on a post mount, beam exit toward +y at z=0.120
    (world). Origin at base center."""
    objs = base_plate('LAS', r=0.026)
    objs.append(cyl('LAS_post', 0.008, 0.080, (0, 0, 0.050), MAT['ano2'], vertices=24))
    objs.append(box('LAS_clamp', (0.030, 0.036, 0.030), (0, 0, 0.105), MAT['ano'], bevel=0.003))
    objs.append(cyl('LAS_head', 0.020, 0.060, (0, -0.005, 0.120), MAT['ano'],
                    rot=(rdeg(90), 0, 0), vertices=36))
    objs.append(cyl('LAS_fring', 0.021, 0.006, (0, 0.023, 0.120), MAT['ano2'],
                    rot=(rdeg(90), 0, 0), vertices=36))
    objs.append(cyl('LAS_bezel', 0.005, 0.002, (0, 0.0265, 0.120), MAT['steel_dk'],
                    rot=(rdeg(90), 0, 0), vertices=16))
    objs.append(cyl('LAS_exit', 0.003, 0.0008, (0, 0.0276, 0.120), MAT['beam'],
                    rot=(rdeg(90), 0, 0), vertices=14))
    objs.append(cyl('LAS_rear', 0.021, 0.006, (0, -0.033, 0.120), MAT['ano2'],
                    rot=(rdeg(90), 0, 0), vertices=36))
    objs.append(cyl('LAS_bnc', 0.004, 0.010, (0, -0.041, 0.120), MAT['steel_dk'],
                    rot=(rdeg(90), 0, 0), vertices=16))
    objs.append(cyl('LAS_bnchole', 0.0015, 0.011, (0, -0.0412, 0.120), MAT['darkline'],
                    rot=(rdeg(90), 0, 0), vertices=12))
    objs.append(cyl('LAS_led', 0.002, 0.002, (0.010, -0.018, 0.1412), MAT['led'], vertices=12))
    objs.append(box('LAS_label', (0.001, 0.030, 0.014), (0.0205, -0.005, 0.120), MAT['plate'], bevel=0))
    for i in range(3):  # printed lines on the label plate
        objs.append(box(f'LAS_labeltxt{i}', (0.0004, 0.020 - i*0.004, 0.0012),
                        (0.0211, -0.005, 0.126 - i*0.0035), MAT['darkline'], bevel=0))
    smooth([o for o in objs if o.name in ('LAS_head', 'LAS_post')])
    return objs

def build_table():
    """Sturdy lab table, origin TOP-center (top local z=0, world top z=-0.06):
    1.05x1.95 marble top, dark metal frame, leveling feet to the floor at -0.80."""
    objs = []
    top = box('OB_TABLE_top', (1.05, 1.95, 0.05), (0, 0, -0.025),
              pbr('OB_marble', 'marble_01', scale=1.4), bevel=0.004)
    objs.append(top)
    frame = pbr('OB_frame', 'metal_plate', scale=1.2, metallic=0.7, roughness=0.5)
    for sy in (-1, 1):
        objs.append(box(f'OB_TABLE_skirtY{sy}', (1.05, 0.06, 0.05), (0, sy*0.94, -0.075), frame, bevel=0.003))
    for sx in (-1, 1):
        objs.append(box(f'OB_TABLE_skirtX{sx}', (0.06, 1.83, 0.05), (sx*0.495, 0, -0.075), frame, bevel=0.003))
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(box(f'OB_TABLE_LEG_{sx}{sy}', (0.05, 0.05, 0.76), (sx*0.47, sy*0.89, -0.48),
                            frame, bevel=0.003))
    for sx in (-1, 1):
        objs.append(box(f'OB_TABLE_STRETCHER{sx}', (0.04, 1.78, 0.04), (sx*0.47, 0, -0.62), frame, bevel=0.002))
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(cyl(f'OB_TABLE_foot{sx}{sy}', 0.012, 0.02, (sx*0.47, sy*0.89, -0.855),
                            MAT['steel_dk'], vertices=14))
    add_uv([top])
    return objs

def build_beam():
    """Static red beam polyline authored around the M bend at local origin:
    seg1 local y -0.8235..0 (laser exit to M), seg2 to the off-center spot on
    TARGET. Pose at world (0, 0.55, 0.120), identity."""
    objs = [cyl('OB_BEAM_seg1', 0.0008, 0.8235, (0, -0.4118, 0), MAT['beam'],
                rot=(rdeg(90), 0, 0), vertices=8)]
    end = Vector((-0.112, 0.599, -0.004))
    d = end.normalized()
    seg2 = cyl('OB_BEAM_seg2', 0.0008, end.length, (end/2).copy(), MAT['beam'], vertices=8)
    seg2.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    objs.append(seg2)
    return objs

def build_toolmat():
    o = box('OB_MAT', (0.34, 0.22, 0.004), (0, 0, 0.002), pbr('OB_linen', 'rough_linen', scale=3.0),
            bevel=0.0005)
    add_uv([o])
    return [o]

# ---------------------------------------------------------------- kit export
def wipe():
    clear_scene()
    common._img_cache.clear()
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for x in list(blk):
            if not x.users:
                blk.remove(x)

def build_all_kits():
    KIT.mkdir(parents=True, exist_ok=True)
    out = {}
    wipe(); mats()
    out['L1'] = export_glb(build_L1(), KIT/'L1.glb')
    wipe(); mats()
    out['POST2'] = export_glb(build_POST2(), KIT/'POST2.glb')
    wipe(); mats()
    out['L2'] = export_glb(build_L2(), KIT/'L2.glb')
    wipe(); mats()
    out['M'] = export_glb(build_M(), KIT/'M.glb')
    wipe(); mats()
    out['TARGET'] = export_glb(build_TARGET(), KIT/'TARGET.glb')
    env = {}
    wipe(); mats()
    env['breadboard'] = export_glb(build_breadboard(), SCENE_ENV/'optical_bench_breadboard.glb')
    wipe(); mats()
    env['laser'] = export_glb(build_laser(), SCENE_ENV/'optical_bench_laser.glb')
    wipe(); mats()
    env['table'] = export_glb(build_table(), SCENE_ENV/'optical_bench_table.glb')
    wipe(); mats()
    env['beam'] = export_glb(build_beam(), SCENE_ENV/'optical_bench_beam.glb')
    wipe(); mats()
    env['mat'] = export_glb(build_toolmat(), SCENE_ENV/'optical_bench_mat.glb')
    wipe()
    return out, env

# ---------------------------------------------------------------- poses
def qz(deg): return Quaternion((0, 0, 1), rdeg(deg))

POST2_POS = Vector((0, 0.15, 0))
L1_POS = Vector((0.15, -0.05, 0.044))       # resting loose in a board hole right of the line
OBJ_POSES = {
    'L1':     (L1_POS, qz(20)),
    'POST2':  (POST2_POS, Quaternion((1, 0, 0, 0))),
    'L2':     (Vector((0, 0.35, 0)), Quaternion((1, 0, 0, 0))),
    'M':      (Vector((0, 0.55, 0)), Q_M),
    'TARGET': (Vector((-0.106, 1.15, -0.06)), Q_TGT),
}
ENV_POSES = {
    'optical_bench_breadboard': (Vector((0, 0.175, 0)), Quaternion((1, 0, 0, 0))),
    'optical_bench_laser':      (Vector((0, -0.30, 0)), Quaternion((1, 0, 0, 0))),
    'optical_bench_table':      (Vector((0, 0.50, -0.06)), Quaternion((1, 0, 0, 0))),
    'optical_bench_beam':       (Vector((0, 0.55, BEAM_Z)), Quaternion((1, 0, 0, 0))),
    'optical_bench_mat':        (Vector((0.43, 0.08, -0.06)), Quaternion((1, 0, 0, 0))),
}
# downloaded props: (asset key, target center xy, base_z, rot_z_deg, extra euler, scale)
PROPS = {
    'desk_lamp_arm_01':   ('desk_lamp_arm_01', (-0.42, -0.22), -0.06, 105, (0, 0, 0), (1, 1, 1)),
    'screwdrivers_02':    ('screwdrivers_02', (0.42, 0.03), -0.056, 8, (0, 0, 0), (1, 1, 1)),
    'magnifying_glass_01':('magnifying_glass_01', (0.45, 0.24), -0.06, 25, (rdeg(-80), 0, 0), (1, 1, 1)),
    'binder_notebook':    ('binder_notebook', (-0.42, 0.52), -0.06, 14, (0, 0, 0), (1, 1, 1)),
    'circuit_board':      ('circuit_board', (0.30, 1.26), -0.06, 25, (0, 0, 0), (1, 1, 1)),
}

# ---------------------------------------------------------------- helpers
def roots_of(objs):
    out = []
    for o in objs:
        r = o
        while r.parent is not None:
            r = r.parent
        if r not in out:
            out.append(r)
    return out

def descendants(parent):
    out = []
    for o in bpy.data.objects:
        r = o
        while r is not None:
            if r == parent:
                out.append(o)
                break
            r = r.parent
    return out

def snap(parent, base_z, center_xy):
    bpy.context.view_layer.update()
    lo, hi = _framed_extents(descendants(parent))
    parent.location += Vector((center_xy[0] - (lo.x + hi.x)/2, center_xy[1] - (lo.y + hi.y)/2, base_z - lo.z))
    bpy.context.view_layer.update()
    return [round(c, 4) for c in parent.location]

# ---------------------------------------------------------------- verification
def verify_anchor():
    """L1 seated on POST2: goal = POST2 pose + local insertion anchor; check the
    re-imported L1 bbox engages the post top, lands xy on the post axis, and its
    lens center rides the beam line. Plus JSON-pose round trip for L1."""
    wipe()
    objs = import_glb(KIT/'POST2.glb')
    parent_to('V_POST2', roots_of(objs), location=POST2_POS)
    bpy.context.view_layer.update()
    plo, phi = _framed_extents(objs)
    objs2 = import_glb(KIT/'L1.glb')
    goal = POST2_POS + Vector((0, 0, ANCHOR_Z))
    parent_to('V_L1', roots_of(objs2), location=goal)
    bpy.context.view_layer.update()
    lo, hi = _framed_extents(objs2)
    cx, cy = (lo.x + hi.x)/2, (lo.y + hi.y)/2
    rep = {
        'anchor_local': [0, 0, ANCHOR_Z],
        'post2_pose': [round(c, 4) for c in POST2_POS],
        'goal_world': [round(c, 4) for c in goal],
        'post2_bbox_max_z': round(phi.z, 4),
        'post_top_z_design': POST_TOP,
        'l1_bbox_min': [round(c, 4) for c in lo],
        'l1_bbox_max': [round(c, 4) for c in hi],
        'sleeve_bottom_z': round(lo.z, 4),
        'grip_depth_m': round(POST_TOP - lo.z, 4),
        'base_plate_bottom_z': round(lo.z + 0.044, 4),
        'lens_center_z': round(goal.z + 0.0205, 4),
        'beam_z': BEAM_Z,
        'xy_center_err_m': [round(cx - POST2_POS.x, 4), round(cy - POST2_POS.y, 4)],
    }
    rep['seated_ok'] = bool(0.008 <= rep['grip_depth_m'] <= 0.025
                            and rep['base_plate_bottom_z'] > POST_TOP
                            and max(abs(rep['xy_center_err_m'][0]), abs(rep['xy_center_err_m'][1])) < 0.002
                            and abs(rep['lens_center_z'] - BEAM_Z) < 0.002)
    # round trip: L1 at its JSON pose, bbox center must sit on the pose (<1 cm)
    p = bpy.data.objects['V_L1']
    p.location = L1_POS
    p.rotation_quaternion = qz(20) @ common.CORR
    bpy.context.view_layer.update()
    lo2, hi2 = _framed_extents(objs2)
    off = [round((lo2.x + hi2.x)/2 - L1_POS.x, 4), round((lo2.y + hi2.y)/2 - L1_POS.y, 4),
           round((lo2.z + hi2.z)/2 - L1_POS.z, 4)]
    rep['roundtrip_pose'] = [round(c, 4) for c in L1_POS]
    rep['roundtrip_bbox_center'] = [round((lo2.x + hi2.x)/2, 4), round((lo2.y + hi2.y)/2, 4), round((lo2.z + hi2.z)/2, 4)]
    rep['roundtrip_offset_m'] = off
    rep['roundtrip_ok'] = bool(max(abs(c) for c in off) < 0.01)
    # inspect_back: M local +Y (label face) must turn to the camera under 180 deg Z
    cam = Vector((0.5, -0.85, 0.55))
    m_pos = OBJ_POSES['M'][0]
    back0 = Q_M @ Vector((0, 1, 0))
    back1 = (Q_M @ qz(180)) @ Vector((0, 1, 0))
    tocam = (cam - Vector((0, 0.55, 0.12))).normalized()
    rep['inspect_back_face0'] = [round(c, 4) for c in back0]
    rep['inspect_back_face180'] = [round(c, 4) for c in back1]
    rep['inspect_back_dot_after_180'] = round(back1 @ tocam, 4)
    rep['inspect_back_dot_before'] = round(back0 @ tocam, 4)
    # radial +Y face: hidden from camera initially, turned into the camera hemisphere
    # (dot > 0.2) by the 180 deg local-Z turn (turntable inspect_back contract)
    rep['inspect_back_ok'] = bool((back1 @ tocam) > 0.2 and (back0 @ tocam) < 0)
    wipe()
    print(json.dumps({'insertion_verification': rep}, ensure_ascii=False), flush=True)
    return rep

# ---------------------------------------------------------------- compose & preview
def compose():
    wipe(); mats()
    for oid, (pos, quat) in OBJ_POSES.items():
        objs = import_glb(KIT/f'{oid}.glb')
        parent_to('HC_' + oid, roots_of(objs), location=pos, wxyz=quat.normalized())
    for pid, (pos, quat) in ENV_POSES.items():
        objs = import_glb(ENV/f'{pid}.glb')
        parent_to('HC_ENV_' + pid, roots_of(objs), location=pos, wxyz=quat.normalized())
    placed = {}
    for pid, (key, cxy, bz, rz, ex, sc) in PROPS.items():
        objs = import_glb(ENV/f'{key}.glb')
        p = parent_to('HC_ENV_' + pid, roots_of(objs))
        q_prop = Euler(ex, 'XYZ').to_quaternion() @ qz(rz)
        p.rotation_quaternion = q_prop @ common.CORR
        p.scale = sc
        placed[pid] = snap(p, bz, cxy)
    ground = bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0.4, -0.86))
    g = bpy.context.object; g.name = 'GROUND'
    g.data.materials.append(pbr('OB_floor', 'concrete_floor_worn_001', scale=2.5))
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 1.9, 0.45), rotation=(rdeg(90), 0, 0))
    w = bpy.context.object; w.name = 'WALL'
    w.scale = (1.0, 0.55, 1.0)
    w.data.materials.append(pbr('OB_wall', 'factory_wall', scale=2.0))
    add_uv([g, w])
    bpy.context.view_layer.update()
    return placed

def add_label(text, pos, euler, size=0.032):
    font = bpy.data.fonts.load(str(FONT_PATH)) if FONT_PATH.exists() else None
    mat_w = M('LAB_w', (0.97, 0.97, 0.95, 1), emissive=(0.4, 0.4, 0.38), es=1.0)
    mat_d = M('LAB_d', (0.02, 0.02, 0.03, 1))
    for off, mat in ((Vector((-0.0015, -0.0015, 0.0)), mat_d), (Vector((0, 0, 0.0008)), mat_w)):
        bpy.ops.object.text_add(location=Vector(pos) + off)
        t = bpy.context.object
        t.name = 'HC_LABEL_PREVIEW'
        t.data.body = text
        t.data.size = size
        t.data.align_x = 'CENTER'
        t.data.align_y = 'CENTER'
        t.data.extrude = 0.0015
        if font:
            t.data.font = font
        t.data.materials.append(mat)
        t.rotation_euler = euler.copy()

def add_stem(pos, target):
    """Leader line from just under a label down to a point ON its object: a dark
    outline cylinder around a white core (same dual style as the labels, readable
    over any background) plus an end dot whose sphere dips into the object so the
    stem visibly touches it. Drawn in world space, so it projects to a real line
    in the orthographic overview (the old camera-axis stem rendered end-on as a
    ~1mm dot and was invisible)."""
    mat_d = M('LAB_sd', (0.03, 0.03, 0.04, 1))
    mat_w = M('LAB_sw', (0.97, 0.97, 0.95, 1), emissive=(0.4, 0.4, 0.38), es=1.0)
    p0 = Vector(pos) + Vector((0, 0, -0.018))   # meets the glyph bottoms
    p1 = Vector(target)
    d = p1 - p0
    rot = d.to_track_quat('Z', 'Y').to_euler()
    mid = (p0 + p1)/2
    for name, r, mat in (('HC_LABEL_STEM_D', 0.0020, mat_d), ('HC_LABEL_STEM_W', 0.0012, mat_w)):
        s = cyl(name, r, d.length, mid, mat, rot=rot, vertices=8)
    for name, r, mat in (('HC_LABEL_STEM_DOT_D', 0.0052, mat_d), ('HC_LABEL_STEM_DOT_W', 0.0038, mat_w)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=p1, segments=16, ring_count=12)
        s = bpy.context.object; s.name = name
        s.data.materials.append(mat)

def clear_labels():
    for t in [o for o in bpy.data.objects if o.name.startswith('HC_LABEL')]:
        bpy.data.objects.remove(t, do_unlink=True)

def fit_ortho(cam_pos, look):
    """Auto-fit over the beam-line story (interactive kit + breadboard + laser +
    beam); the table/props/wall frame the shot but must not widen the story crop."""
    fit_objs = []
    for name in ('HC_L1', 'HC_POST2', 'HC_L2', 'HC_M', 'HC_TARGET',
                 'HC_ENV_optical_bench_breadboard', 'HC_ENV_optical_bench_laser',
                 'HC_ENV_optical_bench_beam'):
        p = bpy.data.objects.get(name)
        if p is None:
            continue
        for o in descendants(p):
            if o.type in ('MESH', 'CURVE', 'FONT'):
                fit_objs.append(o)
    lo, hi = _framed_extents(fit_objs)
    w, h = _projected_size(lo, hi, Vector(cam_pos), Vector(look))
    print(json.dumps({'fit_objs': len(fit_objs), 'bbox_min': [round(c, 3) for c in lo],
                      'bbox_max': [round(c, 3) for c in hi],
                      'projected_wh': [round(w, 3), round(h, 3)]}), flush=True)
    return max(w, h*(1600/1120))*1.06

def q2list(q):
    q = q.normalized()
    return [round(q.w, 6), round(q.x, 6), round(q.y, 6), round(q.z, 6)]

PREVIEW_LABELS = [
    # (object_id, text, label pos, leader target ON the object)
    ('L1', 'L1 一号透镜', (0.18, -0.11, 0.19), (0.15, -0.05, 0.072)),      # ring top
    ('POST2', 'POST2 二号柱位', (-0.06, 0.155, 0.13), (0, 0.15, 0.077)),   # post pin top
    ('L2', 'L2 二号透镜', (0.0, 0.35, 0.20), (0.0, 0.35, 0.128)),          # ring top
    ('M', 'M 折转反射镜', (0.0, 0.55, 0.24), (-0.002, 0.572, 0.149)),      # tine top
    ('TARGET', 'TARGET 靶屏', (-0.106, 1.15, 0.31), (-0.106, 1.15, 0.181)),  # screen top edge
]

def main():
    report = {}
    kits, envkits = build_all_kits()
    for k, v in {**kits, **envkits}.items():
        print(json.dumps({'kit': k, 'path': str(v), 'bytes': v.stat().st_size}), flush=True)
    report['insertion_verification'] = verify_anchor()

    placed = compose()
    light_rig(Vector((0, 0.35, 0.15)), extent=1.7, energy=1.4)
    bpy.ops.object.light_add(type='AREA', location=(-0.55, -0.15, 0.85))
    warm = bpy.context.object
    warm.data.energy = 30; warm.data.shape='DISK'; warm.data.size = 0.28
    warm.data.color = (1.0, 0.86, 0.68)
    warm.rotation_euler = (Vector((0, 0.3, 0.1)) - warm.location).to_track_quat('-Z', 'Y').to_euler()
    world_bg((0.66, 0.69, 0.74, 1.0), strength=0.8)

    cam_pos = Vector((0.5, -0.85, 0.55))
    look = Vector((0, 0.45, 0.15))
    euler_main = (look - cam_pos).to_track_quat('-Z', 'Y').to_euler()
    for oid, text, pos, tgt in PREVIEW_LABELS:
        add_stem(pos, tgt)
        add_label(text, pos, euler_main)

    ortho = fit_ortho(cam_pos, look)
    report['ortho_autofit'] = {'ortho_scale_m': round(ortho, 3)}
    r1 = render_preview('optical_bench_kit_preview.png', cam_pos, look, ortho=ortho)

    # ---- M close-up: a 180 deg Z-turned duplicate of M on the table is the hero,
    # back 3/4 from above: white index line + HR coating label plate + the base
    # degree tick arc all resolve (the inspect_back evidence). The front of the
    # real M (mirror + gimbal) is documented by the main preview.
    clear_labels()
    objs = import_glb(KIT/'M.glb')
    parent_to('HC_M_BACKDUP', roots_of(objs), location=(0.36, 0.66, -0.06),
              wxyz=(Q_M @ qz(180)).normalized())
    cam2 = Vector((0.63, 0.80, 0.23))
    look2 = Vector((0.36, 0.66, 0.07))
    euler2 = (look2 - cam2).to_track_quat('-Z', 'Y').to_euler()
    # captions anchored over the board, left of the hero mount and ~0.5 m from
    # the camera (the old title sat 0.17 m away: extreme perspective blew it
    # past the right edge); both lines lift 40-70 mm clear of the board top so
    # no glyph sinks into the surface. The tick caption takes a leader down to
    # the hero base rim, aimed below the tick plane so the dot covers no ticks.
    add_label('M 背面 180°: 白线基准', (0.20, 0.42, 0.072), euler2, size=0.014)
    add_label('镀膜编号 HR-45°-1064', (0.20, 0.42, 0.045), euler2, size=0.014)
    add_label('底座 0-90° 刻度弧', (0.26, 0.54, 0.030), euler2, size=0.016)
    add_stem((0.26, 0.54, 0.030), (0.340, 0.633, -0.0575))
    r2 = render_preview('optical_bench_kit_preview_m.png', cam2, look2, persp_fov=42,
                        res=(2200, 1540))
    clear_labels()
    bpy.data.objects.remove(bpy.data.objects['HC_M_BACKDUP'], do_unlink=True)
    report['renders'] = [r1, r2]

    # ---- scene JSON
    OBJ_META = {
        'L1':     ('一号透镜', [140, 220, 205], ['point', 'insert'], {},
                   'Φ25 双凸透镜,黑色 kinematic 镜架带三颗调节螺钉与锁紧旋钮,待插入柱位'),
        'POST2':  ('二号柱位', [255, 170, 40], ['point'],
                   {'insertion': [0, 0, ANCHOR_Z]},
                   '面包板定位柱位,Ø12 柱顶带定位销与橙色标记环,插入终点为柱顶+0.03'),
        'L2':     ('二号透镜', [90, 160, 235], ['point'], {},
                   '已装调好的另一枚同款透镜,已在光路中(与 L1 指代易混,消歧用)'),
        'M':      ('折转反射镜', [220, 225, 235], ['point', 'rotate', 'inspect_back'], {},
                   'Ø25 折转反射镜,镜面近垂直光路作约 10° 微折转;背面径向面有镀膜编号 '
                   'HR-45°-1064,白色刻线为入射基准,底座带 0-90° 刻度弧'),
        'TARGET': ('靶屏', [240, 240, 235], ['point', 'wait'], {},
                   '远端白色靶屏,十字线与同心圆刻度,屏上红色光斑位置即同轴判据'),
    }
    objects = []
    for oid, (pos, quat) in OBJ_POSES.items():
        label, color, caps, anchors, desc = OBJ_META[oid]
        objects.append({
            'object_id': oid, 'label': label, 'asset': f'scenes/optical_bench/meshes/{oid}.glb',
            'pose': {'position_m': [round(c, 4) for c in pos], 'wxyz': q2list(quat)},
            'color': color, 'capabilities': caps, 'anchors': anchors, 'description': desc,
        })
    environment = []
    for pid, (pos, quat) in ENV_POSES.items():
        environment.append({'prop_id': pid, 'label': '', 'asset': f'scenes/optical_bench/meshes/env/{pid}.glb',
                            'pose': {'position_m': [round(c, 4) for c in pos], 'wxyz': q2list(quat)},
                            'scale_m': [1.0, 1.0, 1.0]})
    for pid, (key, cxy, bz, rz, ex, sc) in PROPS.items():
        p = bpy.data.objects['HC_ENV_' + pid]
        environment.append({'prop_id': pid, 'label': '', 'asset': f'assets/meshes/env/{key}.glb',
                            'pose': {'position_m': [round(c, 4) for c in p.location], 'wxyz': q2list(p.rotation_quaternion)},
                            'scale_m': [round(s, 4) for s in sc]})
    spec = {
        'schema_version': '1.0', 'scene_id': 'optical_bench', 'title': '光具座同轴校准',
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': objects,
        'initial_instruction': '把透镜 L1 插进二号柱位 POST2,再把反射镜 M 顺时针转 15 度'
                               '把光斑引向靶屏,全程盯着 TARGET 上光斑的位置,最后看 M 背面的镀膜编号。',
        'camera_position_m': [round(c, 4) for c in cam_pos],
        'camera_look_at_m': [round(c, 4) for c in look],
        'environment': environment,
        'render_hints': {'ortho_scale_m': round(ortho, 3), 'grid_extent_m': 1.6,
                         'cue_scale': 0.5, 'label_offset_m': 0.06, 'fit_camera': True},
    }
    write_scene_json('optical_bench', spec)
    print(json.dumps({'camera_final': {'position': [round(c, 3) for c in cam_pos],
                                       'look_at': [round(c, 3) for c in look]},
                      'ortho_autofit': report['ortho_autofit'],
                      'props_placed': placed}, ensure_ascii=False), flush=True)
    print('BUILD_OK', flush=True)

main()
