"""Build the drone_bench scene kit (interactive GLBs + env GLBs + scene JSON + previews).

Run via:
  cd /home/hdd3/zhanghaonan/projects/holocue && .venv/bin/python scripts/guard/resource_guard.py \
      --rss-limit-gb 12 --execute -- /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/scenes/build_drone_bench.py

Layout datum: bench top z=0, footprint x in [-0.85,0.85], y in [-0.70,0.70]; camera
[0.55,-0.95,0.62] -> [0,0.05,0.12]. Drone sits inverted (belly up) on a cradle; nose -y.
Motor quadrants (world, nose toward -y): M1 front-left (-0.22,-0.22), M2 front-right
(+0.22,-0.22), M3 left-rear (-0.22,+0.22, orange damping ring on inboard radial face),
M4 right-rear (+0.22,+0.22).
"""
import bpy, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import *  # noqa: F401,F403
from common import _framed_extents, _projected_size
from mathutils import Vector, Euler, Quaternion, Matrix

KIT = ROOT/'assets/meshes/drone_bench'
FONT_PATH = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')

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

def orient(o, u, v, n):
    """Rotate object so local +x->u, +y->v, +z->n (right-handed basis)."""
    R = Matrix((u, v, n)).transposed().to_4x4()
    o.rotation_euler = R.to_euler()
    return o

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

def mats():
    MAT.clear()
    MAT['shell']   = M('DB_shell',   (0.74, 0.75, 0.79, 1), roughness=0.42)
    MAT['shell_dk']= M('DB_shell_dk',(0.42, 0.44, 0.48, 1), roughness=0.5)
    MAT['belly']   = M('DB_belly',   (0.55, 0.57, 0.60, 1), roughness=0.5)
    MAT['arm']     = M('DB_arm',     (0.16, 0.17, 0.19, 1), metallic=0.25, roughness=0.45)
    MAT['dark']    = M('DB_dark',    (0.06, 0.062, 0.068, 1), roughness=0.55)
    MAT['battery'] = M('DB_battery', (0.075, 0.078, 0.085, 1), roughness=0.48)
    MAT['orange']  = M('DB_orange',  (0.88, 0.33, 0.04, 1), roughness=0.55)
    MAT['silicone']= M('DB_silicone',(0.92, 0.38, 0.05, 1), roughness=0.68)
    MAT['gold']    = M('DB_gold',    (0.83, 0.65, 0.22, 1), metallic=1.0, roughness=0.3)
    MAT['steel']   = M('DB_steel',   (0.52, 0.54, 0.57, 1), metallic=0.9, roughness=0.35)
    MAT['steel_dk']= M('DB_steel_dk',(0.20, 0.21, 0.23, 1), metallic=0.8, roughness=0.45)
    MAT['rubber']  = M('DB_rubber',  (0.045, 0.048, 0.052, 1), roughness=0.92)
    MAT['white']   = M('DB_white',   (0.92, 0.92, 0.93, 1), roughness=0.4)
    MAT['smoke']   = M('DB_smoke',   (0.14, 0.145, 0.16, 1), metallic=0.1, roughness=0.14, alpha=0.5)
    # NOTE: emission_strength must stay 1.0 -- the glTF exporter folds strength>1 into
    # the emissive factor with clamping, which destroys the color saturation.
    MAT['led_g']   = M('DB_led_g',   (0.10, 0.85, 0.25, 1), emissive=(0.10, 0.95, 0.30), es=1.0)
    MAT['led_r']   = M('DB_led_r',   (0.55, 0.08, 0.05, 1), emissive=(0.90, 0.10, 0.06), es=1.0)
    MAT['amber']   = M('DB_amber',   (0.42, 0.20, 0.02, 1), emissive=(1.00, 0.58, 0.14), es=1.0)
    MAT['lens']    = M('DB_lens',    (0.02, 0.03, 0.06, 1), metallic=0.6, roughness=0.12)
    MAT['prop']    = M('DB_prop',    (0.25, 0.255, 0.265, 1), roughness=0.55)
    MAT['plastic'] = M('DB_plastic', (0.16, 0.165, 0.18, 1), roughness=0.6)
    MAT['win']     = M('DB_win',     (0.01, 0.01, 0.012, 1), roughness=0.2)

# ---------------------------------------------------------------- interactive builders
def build_bat():
    """Smart battery, bbox ~150x70x55, origin at bbox center.
    pack z rel [-0.0275,+0.0185] (46mm), top handle z rel [+0.0185,+0.0275] (9mm)."""
    objs = []
    objs.append(box('BAT_pack', (0.070, 0.150, 0.046), (0, 0, -0.0045), MAT['battery'], bevel=0.007))
    objs.append(box('BAT_band', (0.0725, 0.1525, 0.004), (0, 0, 0.006), MAT['dark'], bevel=0.001))
    for yy in (-0.055, 0.055):
        objs.append(box('BAT_stem', (0.009, 0.010, 0.009), (0, yy, 0.0230), MAT['dark'], bevel=0.0015))
    objs.append(box('BAT_bar', (0.011, 0.122, 0.0075), (0, 0, 0.0238), MAT['dark'], bevel=0.002))
    objs.append(box('BAT_contacts', (0.050, 0.014, 0.0016), (0, -0.050, -0.0281), MAT['gold'], bevel=0))
    # charge LEDs + button on the -y end face (faces the camera at rest and when seated)
    for i in range(4):
        objs.append(cyl('BAT_led', 0.0032, 0.0016, (-0.024 + i*0.016, -0.0762, 0.009), MAT['led_g'], rot=(rdeg(90), 0, 0), vertices=12))
    objs.append(cyl('BAT_btn', 0.0045, 0.0018, (0.030, -0.0762, 0.009), MAT['shell_dk'], rot=(rdeg(90), 0, 0), vertices=14))
    objs.append(box('BAT_label', (0.0015, 0.088, 0.020), (-0.0358, 0, -0.004), MAT['white'], bevel=0))
    smooth([o for o in objs if 'led' not in o.name and 'btn' not in o.name])
    return objs

def build_bay():
    """Battery bay, origin at mouth center (+z up, mouth plane z=0).
    Opening 74x154, well floor z=-0.052, collar outer 90x170, guide chamfers,
    orange latch on -y rim, gold contact pins at -y end of floor."""
    objs = []
    t, h = 0.006, 0.008
    for yy in (-0.082, 0.082):                       # collar long walls (y ends)
        objs.append(box('BAY_collarY', (0.090, t, h), (0, yy, -0.004), MAT['shell_dk'], bevel=0.0012))
    for xx in (-0.042, 0.042):                       # collar side walls
        objs.append(box('BAY_collarX', (t, 0.158, h), (xx, 0, -0.004), MAT['shell_dk'], bevel=0.0012))
    wh = 0.044
    for yy in (-0.0815, 0.0815):                     # well walls, inner faces at +-0.079
        objs.append(box('BAY_wellY', (0.088, 0.005, wh), (0, yy, -0.030), MAT['dark'], bevel=0))
    for xx in (-0.0415, 0.0415):                     # inner faces at +-0.039
        objs.append(box('BAY_wellX', (0.005, 0.158, wh), (xx, 0, -0.030), MAT['dark'], bevel=0))
    objs.append(box('BAY_floor', (0.088, 0.168, 0.004), (0, 0, -0.052), MAT['dark'], bevel=0))
    for xx in (-0.0425, 0.0425):
        o = box('BAY_chamX', (0.007, 0.160, 0.007), (xx, 0, -0.0035), MAT['shell_dk'], bevel=0)
        o.rotation_euler = (0, rdeg(45), 0)
        objs.append(o)
    for yy in (-0.0825, 0.0825):
        o = box('BAY_chamY', (0.086, 0.007, 0.007), (0, yy, -0.0035), MAT['shell_dk'], bevel=0)
        o.rotation_euler = (rdeg(45), 0, 0)
        objs.append(o)
    objs.append(box('BAY_latch', (0.030, 0.008, 0.012), (0, -0.0865, 0.0005), MAT['orange'], bevel=0.002))
    objs.append(box('BAY_latchbtn', (0.012, 0.006, 0.005), (0, -0.0905, 0.004), MAT['orange'], bevel=0.001))
    for i in range(4):
        objs.append(cyl('BAY_pin', 0.0016, 0.006, (-0.0195 + i*0.013, -0.050, -0.049), MAT['gold'], vertices=10))
    for xx in (-0.042, 0.042):                       # screw bosses on collar corners
        for yy in (-0.081, 0.081):
            objs.append(cyl('BAY_boss', 0.0042, 0.006, (xx, yy, -0.002), MAT['shell_dk'], vertices=12))
    smooth([o for o in objs if 'pin' not in o.name and 'boss' not in o.name])
    return objs

def build_guard():
    """Guard cover over the bay. Hinge axis = local Z; closed cover extends local -X
    (over the bay); local frame at world: X->+Y, Y->+Z, Z->+X (hinge along world +X)."""
    objs = []
    for zz in (-0.042, 0.042):
        objs.append(box('GUARD_rail', (0.172, 0.020, 0.014), (-0.095, 0.008, zz), MAT['smoke'], bevel=0.002))
    objs.append(box('GUARD_top', (0.176, 0.006, 0.090), (-0.095, 0.021, 0), MAT['smoke'], bevel=0.0015))
    objs.append(cyl('GUARD_hinge', 0.0065, 0.098, (0, 0, 0), MAT['steel'], vertices=16))
    for xx in (-0.05, 0.05):
        objs.append(cyl('GUARD_hpost', 0.009, 0.008, (0, 0.004, xx), MAT['steel_dk'], vertices=12))
    kn = cyl('GUARD_thumbscrew', 0.0075, 0.009, (-0.168, 0.028, 0.036), MAT['steel'], vertices=12)
    kn.rotation_euler = (rdeg(90), 0, 0)
    objs.append(kn)
    objs.append(box('GUARD_screwslot', (0.003, 0.004, 0.020), (-0.168, 0.0235, 0.036), MAT['dark'], bevel=0))
    objs.append(box('GUARD_index', (0.005, 0.0015, 0.094), (-0.152, 0.0248, 0), MAT['white'], bevel=0))
    smooth([o for o in objs if 'thumbscrew' not in o.name and 'screwslot' not in o.name])
    return objs

def build_motor(pad=False):
    """Motor can ~D30, axis local Z, canonical orientation: 3 lugs at local -Z (mount
    side), ribbed barrel, top bell +Z with cooling slots. M3 adds orange silicone
    damping ring on the local +X radial face (inboard when yawed -45 deg)."""
    objs = []
    objs.append(cyl('M_barrel', 0.0140, 0.020, (0, 0, 0.004), MAT['dark'], vertices=40))
    for i in range(6):
        objs.append(cyl('M_rib', 0.0149, 0.0014, (0, 0, -0.0035 + i*0.0035), MAT['steel_dk'], vertices=40))
    objs.append(cyl('M_flange', 0.0155, 0.0035, (0, 0, -0.0078), MAT['steel_dk'], vertices=40))
    objs.append(cyl('M_bell', 0.0148, 0.007, (0, 0, 0.0175), MAT['dark'], vertices=40))
    objs.append(cyl('M_cap', 0.0052, 0.0022, (0, 0, 0.0220), MAT['steel_dk'], vertices=20))
    for i in range(8):
        a = i*rdeg(45)
        o = box('M_slot', (0.0045, 0.0016, 0.0045), (0.0105*math.cos(a), 0.0105*math.sin(a), 0.0185), MAT['rubber'], bevel=0)
        o.rotation_euler = (0, 0, a)
        objs.append(o)
    for a in (90, 210, 330):
        rad = rdeg(a)
        o = box('M_lug', (0.013, 0.0065, 0.005), (0.0165*math.cos(rad), 0.0165*math.sin(rad), -0.0090), MAT['steel_dk'], bevel=0.001)
        o.rotation_euler = (0, 0, rad)
        objs.append(o)
        objs.append(cyl('M_lugscrew', 0.0022, 0.003, (0.0165*math.cos(rad), 0.0165*math.sin(rad), -0.0065), MAT['steel'], vertices=10))
    if pad:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.0088, minor_radius=0.0030,
                                         location=(0.0165, 0, -0.002), major_segments=24, minor_segments=12)
        t = bpy.context.object
        t.name = 'M_dampring'
        t.rotation_euler = (0, rdeg(90), 0)   # torus axis -> local +X
        t.scale = (0.45, 1.0, 1.0)            # flatten along axis into a pad ring
        t.data.materials.append(MAT['silicone'])
        smooth(t)
        objs.append(t)
    smooth([o for o in objs if o.name in ('M_barrel', 'M_bell', 'M_flange', 'M_cap')])
    return objs

def build_voltmeter():
    """Bench voltmeter ~220x200x80 body + 25-deg tilted head, amber 7-seg '12.6'."""
    objs = []
    objs.append(box('VM_case', (0.220, 0.200, 0.052), (0, 0, 0.032), MAT['dark'], bevel=0.006))
    for xx in (-0.088, 0.088):
        for yy in (-0.078, 0.078):
            objs.append(cyl('VM_foot', 0.0085, 0.006, (xx, yy, 0.003), MAT['rubber'], vertices=14))
    n = Vector((0, -math.sin(rdeg(25)), math.cos(rdeg(25))))
    u = Vector((1, 0, 0))
    v = n.cross(u)
    C = Vector((0, -0.0484, 0.0801))
    panel = box('VM_panel', (0.204, 0.118, 0.010), (0, 0, 0), MAT['dark'], bevel=0.003)
    orient(panel, u, v, n); panel.location = C
    objs.append(panel)
    for xx in (-0.098, 0.098):
        o = box('VM_cheek', (0.006, 0.052, 0.075), (xx, -0.052, 0.062), MAT['dark'], bevel=0.002)
        o.rotation_euler = (rdeg(25), 0, 0)
        objs.append(o)
    win = box('VM_window', (0.118, 0.056, 0.006), (0, 0, 0), MAT['win'], bevel=0.001)
    orient(win, u, v, n); win.location = C + (-0.006)*u + (0.006)*v + 0.007*n
    objs.append(win)

    # ---- 7-segment "12.6" (proud of the window glass: panel face C+0.005n, window front C+0.010n)
    h, t2, d, dw, gap = 0.040, 0.0055, 0.003, 0.027, 0.009
    seg_l = h*0.55
    yT, yM, yB = h*0.5 - seg_l*0.28, 0.0, -(h*0.5 - seg_l*0.28)
    xL, xR = -dw/2 + t2*0.6, dw/2 - t2*0.6
    origin = C + (-0.006)*u + (0.006)*v + 0.013*n
    segs = []
    def place(cx, cy, sx, sy):
        o = box('VM_seg', (sx, sy, d), (0, 0, 0), MAT['amber'], bevel=0)
        orient(o, u, v, n)
        o.location = origin + cx*u + cy*v
        segs.append(o)
    maps = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd',
            '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg'}
    glyphs = [('dot', 0.008) if c == '.' else (c, dw) for c in '12.6']
    total = sum(g[1] for g in glyphs) + gap*(len(glyphs) - 1)
    cx = -total/2
    for c, w in glyphs:
        if c == 'dot':
            place(cx + w/2, yB - t2*1.2, t2*1.3, t2*1.3)
        else:
            on = set(maps[c])
            if 'a' in on: place(cx + dw/2, yT, seg_l, t2)
            if 'g' in on: place(cx + dw/2, yM, seg_l, t2)
            if 'd' in on: place(cx + dw/2, yB, seg_l, t2)
            if 'f' in on: place(cx + xL, yT/2 + 0.002, t2, seg_l)
            if 'b' in on: place(cx + xR, yT/2 + 0.002, t2, seg_l)
            if 'e' in on: place(cx + xL, yB/2 - 0.002, t2, seg_l)
            if 'c' in on: place(cx + xR, yB/2 - 0.002, t2, seg_l)
        cx += w + gap
    objs.extend(segs)

    knob = cyl('VM_knob', 0.0135, 0.011, (0, 0, 0), MAT['dark'], vertices=12)
    orient(knob, u, v, n); knob.location = C + (0.064)*u + (-0.006)*v + 0.008*n
    objs.append(knob)
    cap = cyl('VM_knobcap', 0.0045, 0.0025, (0, 0, 0), MAT['steel_dk'], vertices=14)
    orient(cap, u, v, n); cap.location = C + (0.064)*u + (-0.006)*v + 0.0145*n
    objs.append(cap)
    for i, mat in enumerate((M('DB_jack_r', (0.68, 0.09, 0.06, 1), roughness=0.4), MAT['rubber'])):
        j = cyl('VM_jack', 0.0072, 0.008, (0, 0, 0), mat, vertices=18)
        orient(j, u, v, n); j.location = C + (-0.075)*u + (-0.016 + i*0.032)*v + 0.005*n
        objs.append(j)
        h2 = cyl('VM_jackhole', 0.0035, 0.009, (0, 0, 0), MAT['dark'], vertices=12)
        orient(h2, u, v, n); h2.location = j.location + 0.0008*n
        objs.append(h2)
    led = cyl('VM_led', 0.0034, 0.004, (0, 0, 0), MAT['led_g'], vertices=12)
    orient(led, u, v, n); led.location = C + (0.064)*u + (-0.036)*v + 0.007*n
    objs.append(led)
    for i in range(5):
        objs.append(box('VM_vent', (0.004, 0.0015, 0.022), (-0.06 + i*0.03, 0.1008, 0.040), MAT['rubber'], bevel=0))
    objs.append(box('VM_brand', (0.084, 0.0015, 0.010), (0, -0.1008, 0.046), MAT['white'], bevel=0))
    smooth([o for o in objs if o.name in ('VM_case', 'VM_panel', 'VM_cheek', 'VM_knob')])
    return objs

def build_prop(blade_z=0.0, hub_z=0.005, r=0.099, yaw=0):
    """Two-blade prop lying flat (blades in xy-plane)."""
    objs = []
    hub = cyl('P_hub', 0.0125, 0.009, (0, 0, hub_z), MAT['prop'], vertices=20)
    hub.rotation_euler = (0, 0, rdeg(yaw))
    objs.append(hub)
    for s in (-1, 1):
        b = box('P_blade', (r, 0.020, 0.0035), (s*r/2, 0, blade_z), MAT['prop'], bevel=0.001)
        b.rotation_euler = (rdeg(s*7), 0, rdeg(yaw))
        objs.append(b)
    smooth([hub])
    return objs

# ---------------------------------------------------------------- env builders
def build_table():
    objs = []
    top = box('DB_TABLE_top', (1.70, 1.40, 0.050), (0, 0, -0.025), pbr('DB_wood', 'wood_table_001', scale=1.5), bevel=0.004)
    objs.append(top)
    for xx, yy in ((-0.78, -0.63), (0.78, -0.63), (-0.78, 0.63), (0.78, 0.63)):
        objs.append(box(f'DB_TABLE_LEG_{xx:+.2f}{yy:+.2f}', (0.045, 0.045, 0.80), (xx, yy, -0.45), MAT['steel_dk'], bevel=0.003))
    for xx in (-0.765, 0.765):
        objs.append(box('DB_TABLE_STRETCHER', (0.04, 1.24, 0.04), (xx, 0, -0.60), MAT['steel_dk'], bevel=0.002))
    shelf = box('DB_TABLE_SHELF', (1.56, 1.18, 0.030), (0, 0, -0.435), pbr('DB_wood2', 'wood_table_001', scale=2.2), bevel=0.003)
    objs.append(shelf)
    add_uv([top, shelf])
    return objs

def build_mat():
    o = box('DB_MAT', (1.05, 0.72, 0.004), (0, 0, 0.002), pbr('DB_rubbertiles', 'rubber_tiles', scale=2.4), bevel=0.0005)
    add_uv([o])
    return [o]

def build_cradle():
    objs = []
    objs.append(box('DB_CRADLE_rail', (0.070, 0.40, 0.012), (0, 0, 0.006), MAT['steel_dk'], bevel=0.002))
    for yy in (-0.075, 0.075):
        objs.append(box('DB_CRADLE_block', (0.10, 0.085, 0.030), (0, yy, 0.027), MAT['dark'], bevel=0.006))
        for s in (-1, 1):
            o = box('DB_CRADLE_pad', (0.104, 0.032, 0.007), (0, yy + s*0.007, 0.0445), MAT['orange'], bevel=0.001)
            o.rotation_euler = (rdeg(s*18), 0, 0)
            objs.append(o)
    objs.append(cyl('DB_CRADLE_screw', 0.004, 0.010, (0, 0.20, 0.006), MAT['steel'], vertices=6))
    return objs

def build_dronebody():
    """Origin at fuselage center; belly is local +z (drone inverted in world)."""
    objs = []
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    pod = bpy.context.object
    pod.name = 'DB_BODY_pod'
    pod.scale = (0.11, 0.17, 0.046)
    me = pod.data
    for vt in me.vertices:      # taper nose (-y) and tail (+y)
        if vt.co.y < -0.35:
            vt.co.x *= 0.74; vt.co.z *= 0.80
        elif vt.co.y > 0.35:
            vt.co.x *= 0.86; vt.co.z *= 0.90
    me.update()
    bv = pod.modifiers.new('Bevel', 'BEVEL'); bv.width = 0.024; bv.segments = 3; bv.limit_method = 'ANGLE'
    pod.data.materials.append(MAT['shell'])
    smooth(pod)
    objs.append(pod)
    objs.append(box('DB_BODY_baycut', (0.096, 0.168, 0.0025), (0.02, 0, 0.0452), MAT['belly'], bevel=0.002))
    for xx in (-0.038, 0.038):
        for yy in (-0.074, 0.074):
            objs.append(cyl('DB_BODY_boss', 0.0042, 0.004, (0.02 + xx, yy, 0.0475), MAT['shell_dk'], vertices=12))
    for yy in (-0.055, 0.055):
        objs.append(box('DB_BODY_pline', (0.205, 0.0035, 0.0012), (0, yy, 0.0463), MAT['shell_dk'], bevel=0))
    for xx in (-0.076, 0.076):
        objs.append(box('DB_BODY_pline2', (0.0035, 0.30, 0.0012), (xx, 0, 0.0463), MAT['shell_dk'], bevel=0))
    objs.append(box('DB_BODY_led', (0.016, 0.0025, 0.008), (0, -0.171, 0.012), MAT['led_g'], bevel=0))
    for xx in (-1, 1):
        for i in range(3):
            objs.append(box('DB_BODY_vent', (0.0018, 0.045, 0.008), (xx*0.1095, -0.01 + i*0.055, 0.008), MAT['dark'], bevel=0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, y0 = sx*0.075, sy*0.125
            x1, y1 = sx*0.215, sy*0.215
            L = math.hypot(x1 - x0, y1 - y0)
            a = math.atan2(y1 - y0, x1 - x0)
            arm = cyl('DB_BODY_arm', 0.011, L, ((x0 + x1)/2, (y0 + y1)/2, 0), MAT['arm'], vertices=20)
            arm.rotation_euler = (0, 0, a - rdeg(90))
            objs.append(arm)
            objs.append(box('DB_BODY_plate', (0.058, 0.058, 0.006), (sx*0.22, sy*0.22, -0.011), MAT['arm'], bevel=0.002))
    for (px, py, yaw) in ((-0.22, -0.22, 15), (0.22, -0.22, -20)):   # props still on M1/M2
        for o in build_prop(blade_z=-0.0495, hub_z=-0.046, yaw=yaw):
            o.location += Vector((px, py, 0))
            objs.append(o)
    for sx in (-1, 1):   # landing gear folded flat against belly (up), flanking bay
        objs.append(box('DB_BODY_gear', (0.030, 0.130, 0.010), (sx*0.085, -0.010, 0.051), MAT['shell_dk'], bevel=0.003))
        objs.append(box('DB_BODY_gearpad', (0.024, 0.020, 0.013), (sx*0.085, -0.072, 0.0515), MAT['dark'], bevel=0.003))
    objs.append(box('DB_BODY_gimbalarm', (0.020, 0.030, 0.016), (0, -0.148, 0.038), MAT['dark'], bevel=0.002))
    ball = cyl('DB_BODY_gimbal', 0.0165, 0.024, (0, -0.158, 0.052), MAT['dark'], vertices=28)
    objs.append(ball)
    lens = cyl('DB_BODY_lens', 0.0085, 0.010, (0, -0.172, 0.052), MAT['lens'], rot=(rdeg(90), 0, 0), vertices=20)
    objs.append(lens)
    objs.append(cyl('DB_BODY_lensring', 0.0105, 0.006, (0, -0.169, 0.052), MAT['arm'], rot=(rdeg(90), 0, 0), vertices=20))
    gps = cyl('DB_BODY_gps', 0.016, 0.010, (0, 0.158, -0.051), MAT['shell_dk'], vertices=24)
    dome = cyl('DB_BODY_gpsdome', 0.012, 0.004, (0, 0.158, -0.057), MAT['dark'], vertices=24)
    smooth([ball, gps, dome])
    objs.extend([gps, dome])
    return objs

def build_tray():
    objs = []
    objs.append(box('DB_TRAY_base', (0.28, 0.20, 0.016), (0, 0, 0.008), MAT['plastic'], bevel=0.003))
    for yy in (-0.0975, 0.0975):
        objs.append(box('DB_TRAY_wallY', (0.284, 0.005, 0.024), (0, yy, 0.020), MAT['plastic'], bevel=0.002))
    for xx in (-0.1395, 0.1395):
        objs.append(box('DB_TRAY_wallX', (0.005, 0.195, 0.024), (xx, 0, 0.020), MAT['plastic'], bevel=0.002))
    for xx in (-0.047, 0.047):
        objs.append(box('DB_TRAY_div', (0.004, 0.19, 0.018), (xx, 0, 0.017), MAT['plastic'], bevel=0.001))
    def jitter(i, k): return 0.0026*math.sin(i*2.7 + k), 0.0026*math.cos(i*1.3 + k)
    for i in range(10):
        jx, jy = jitter(i, 0)
        objs.append(cyl('DB_TRAY_screw', 0.0022, 0.0075, (-0.098 + (i % 5)*0.014 + jx, -0.055 + (i//5)*0.030 + jy, 0.0195), MAT['steel'], vertices=8))
    for i in range(8):
        jx, jy = jitter(i, 2)
        objs.append(cyl('DB_TRAY_nut', 0.0032, 0.0025, (-0.016 + (i % 4)*0.016 + jx, -0.045 + (i//4)*0.034 + jy, 0.017), MAT['steel_dk'], vertices=6))
    for i in range(6):
        jx, jy = jitter(i, 4)
        objs.append(cyl('DB_TRAY_stand', 0.0035, 0.010, (0.082 + (i % 3)*0.024 + jx, -0.040 + (i//3)*0.036 + jy, 0.021), MAT['gold'], vertices=10))
    for (ox, oy, yaw) in ((-0.30, 0.01, 28), (0.23, 0.17, -18)):   # 2 removed props lying flat
        for o in build_prop(blade_z=0.0022, hub_z=0.006, yaw=yaw):
            o.location += Vector((ox, oy, 0))
            objs.append(o)
    return objs

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
    out['BAT'] = export_glb(build_bat(), KIT/'BAT.glb')
    wipe(); mats()
    out['BAY'] = export_glb(build_bay(), KIT/'BAY.glb')
    wipe(); mats()
    out['GUARD'] = export_glb(build_guard(), KIT/'GUARD.glb')
    wipe(); mats()
    out['M1'] = export_glb(build_motor(pad=False), KIT/'M1.glb')
    wipe(); mats()
    out['M2'] = export_glb(build_motor(pad=False), KIT/'M2.glb')
    wipe(); mats()
    out['M3'] = export_glb(build_motor(pad=True), KIT/'M3.glb')
    wipe(); mats()
    out['M4'] = export_glb(build_motor(pad=False), KIT/'M4.glb')
    wipe(); mats()
    out['VOLTMETER'] = export_glb(build_voltmeter(), KIT/'VOLTMETER.glb')
    env = {}
    wipe(); mats()
    env['table'] = export_glb(build_table(), ENV/'drone_bench_table.glb')
    wipe(); mats()
    env['mat'] = export_glb(build_mat(), ENV/'drone_bench_mat.glb')
    wipe(); mats()
    env['cradle'] = export_glb(build_cradle(), ENV/'drone_bench_cradle.glb')
    wipe(); mats()
    env['dronebody'] = export_glb(build_dronebody(), ENV/'drone_bench_dronebody.glb')
    wipe(); mats()
    env['partstray'] = export_glb(build_tray(), ENV/'drone_bench_partstray.glb')
    wipe()
    return out, env

# ---------------------------------------------------------------- poses
def qz(deg): return Quaternion((0, 0, 1), rdeg(deg))
def qx180(): return Quaternion((1, 0, 0), rdeg(180))

BAY_POS = Vector((0.02, 0.0, 0.148))          # bay mouth plane
BAY_ANCHOR = Vector((0.0, 0.0, -0.0185))      # insertion anchor (BAT origin when seated)
GUARD_HINGE = Vector((0.02, 0.103, 0.146))
Q_FRAME = Quaternion((0.5, 0.5, 0.5, 0.5))    # local x->+Y, y->+Z, z->+X
GUARD_OPEN = -115.0                           # deg about local Z (hinge), opens to rear

OBJ_POSES = {
    'BAT':       (Vector((0.38, -0.27, 0.0315)), qz(18)),
    'BAY':       (BAY_POS, Quaternion((1, 0, 0, 0))),
    'GUARD':     (GUARD_HINGE, Q_FRAME @ qz(GUARD_OPEN)),
    'M1':        (Vector((-0.22, -0.22, 0.074)), qx180()),
    'M2':        (Vector((0.22, -0.22, 0.074)), qx180()),
    'M3':        (Vector((-0.22, 0.22, 0.074)), qx180() @ qz(45)),   # +45 yaw: ring local +X lands inboard (0.707,-0.707) after the 180X flip
    'M4':        (Vector((0.22, 0.22, 0.074)), qx180()),
    'VOLTMETER': (Vector((-0.32, 0.50, 0.0)), qz(8)),
}
ENV_POSES = {
    'drone_bench_table':     (Vector((0, 0, 0)), Quaternion((1, 0, 0, 0))),
    'drone_bench_mat':       (Vector((0, 0, 0)), Quaternion((1, 0, 0, 0))),
    'drone_bench_cradle':    (Vector((0, 0, 0.004)), Quaternion((1, 0, 0, 0))),
    'drone_bench_dronebody': (Vector((0, 0, 0.094)), Quaternion((1, 0, 0, 0))),
    'drone_bench_partstray': (Vector((0.40, -0.56, 0.0)), Quaternion((1, 0, 0, 0))),
}
# downloaded props: (asset key, target center xy, base_z or None, rot_z_deg, extra euler, scale)
PROPS = {
    'metal_toolbox':           ('metal_toolbox', (0.52, 0.50), 0.0, 14, (0, 0, 0), (1, 1, 1)),
    'screwdrivers_02':         ('screwdrivers_02', (-0.44, -0.05), 0.004, 8, (0, 0, 0), (1, 1, 1)),
    'pliers':                  ('pliers', (-0.40, 0.18), 0.004, 90, (0, 0, 0), (1, 1, 1)),
    'bench_vice_01':           ('bench_vice_01', (-0.64, -0.56), 0.0, 90, (0, 0, 0), (1, 1, 1)),
    'magnifying_glass_01':     ('magnifying_glass_01', (0.60, -0.50), 0.0, 25, (rdeg(90), 0, 0), (1, 1, 1)),
    'circuit_board':           ('circuit_board', (0.52, 0.46), None, 12, (0, 0, 0), (1, 1, 1)),
    'retro_multimeter':        ('retro_multimeter', (-0.35, -0.10), -0.42, -15, (0, 0, 0), (1, 1, 1)),
    'modular_electric_cables': ('modular_electric_cables', (-0.35, 0.655), 0.0, 0, (0, 0, 0), (0.40, 0.40, 0.40)),
}

# ---------------------------------------------------------------- verification
def verify_seated():
    wipe()
    objs = import_glb(KIT/'BAT.glb')
    goal = BAY_POS + BAY_ANCHOR            # BAY rotation is identity
    parent_to('BATGOAL', roots_of(objs), location=goal)
    bpy.context.view_layer.update()
    lo, hi = _framed_extents(objs)
    rep = {
        'goal_position_m': [round(c, 4) for c in goal],
        'bat_bbox_world_min': [round(c, 4) for c in lo],
        'bat_bbox_world_max': [round(c, 4) for c in hi],
        'bay_mouth_z_m': 0.148, 'well_floor_z_m': 0.096,
        'pack_top_above_mouth_m': round(hi.z - 0.009 - 0.148, 4),
        'handle_top_above_mouth_m': round(hi.z - 0.148, 4),
        'pack_bottom_below_mouth_m': round(0.148 - lo.z, 4),
        'clearance_pack_bottom_to_floor_m': round(lo.z - 0.096, 4),
        'bat_xy_size_m': [round(hi.x - lo.x, 4), round(hi.y - lo.y, 4)],
        'well_opening_xy_m': [0.078, 0.158],
        'xy_clearance_per_side_m': [round((0.078 - (hi.x - lo.x))/2, 4), round((0.158 - (hi.y - lo.y))/2, 4)],
    }
    rep['flush_seat_ok'] = bool(abs(rep['pack_top_above_mouth_m']) < 0.002
                                and rep['clearance_pack_bottom_to_floor_m'] > 0.0
                                and min(rep['xy_clearance_per_side_m']) > 0.001)
    wipe()
    return rep

# ---------------------------------------------------------------- preview
PREVIEW_LABELS = [
    ('BAT', 'BAT 智能电池', (0.38, -0.27, 0.125)),
    ('BAY', 'BAY 电池仓', (0.02, 0.0, 0.245)),
    ('GUARD', 'GUARD 电池护罩', (0.02, 0.135, 0.335)),
    ('M1', 'M1 前左电机', (-0.22, -0.22, 0.165)),
    ('M2', 'M2 前右电机', (0.22, -0.22, 0.165)),
    ('M3', 'M3 左后电机', (-0.22, 0.22, 0.165)),
    ('M4', 'M4 右后电机', (0.22, 0.22, 0.165)),
    ('VOLTMETER', 'VOLTMETER 台式电压表', (-0.32, 0.50, 0.215)),
]

def snap(parent, base_z, center_xy):
    bpy.context.view_layer.update()
    lo, hi = _framed_extents(descendants(parent))
    parent.location += Vector((center_xy[0] - (lo.x + hi.x)/2, center_xy[1] - (lo.y + hi.y)/2, base_z - lo.z))
    bpy.context.view_layer.update()
    return [round(c, 4) for c in parent.location]

def roots_of(objs):
    """Top-level imported nodes (walk up past glTF-internal hierarchy)."""
    out = []
    for o in objs:
        r = o
        while r.parent is not None:
            r = r.parent
        if r not in out:
            out.append(r)
    return out

def descendants(parent):
    """All objects whose parent chain contains `parent`."""
    out = []
    for o in bpy.data.objects:
        r = o
        while r is not None:
            if r == parent:
                out.append(o)
                break
            r = r.parent
    return out

def compose():
    wipe(); mats()
    for oid, (pos, quat) in OBJ_POSES.items():
        objs = import_glb(KIT/f'{oid}.glb')
        parent_to('HC_' + oid, roots_of(objs), location=pos, wxyz=quat.normalized())
    for pid, (pos, quat) in ENV_POSES.items():
        objs = import_glb(ENV/f'{pid}.glb')
        parent_to('HC_ENV_' + pid, roots_of(objs), location=pos, wxyz=quat.normalized())
    toolbox_top = None
    placed = {}
    for pid, (key, cxy, bz, rz, ex, sc) in PROPS.items():
        objs = import_glb(ENV/f'{key}.glb')
        p = parent_to('HC_ENV_' + pid, roots_of(objs))
        q_prop = Euler(ex, 'XYZ').to_quaternion() @ qz(rz)   # extra euler, then local Z rot
        p.rotation_quaternion = q_prop @ common.CORR
        p.scale = sc
        use_bz = bz
        if pid == 'circuit_board':
            use_bz = toolbox_top + 0.001
        placed[pid] = snap(p, use_bz, cxy)
        if pid == 'metal_toolbox':
            bpy.context.view_layer.update()
            lo, hi = _framed_extents(descendants(p))
            toolbox_top = hi.z
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -0.852))
    ground = bpy.context.object
    ground.name = 'GROUND'
    ground.data.materials.append(pbr('DB_floor', 'hangar_concrete_floor', scale=3.0))
    add_uv([ground])
    return placed

def add_label(text, pos, euler, size=0.036):
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

def clear_labels():
    for t in [o for o in bpy.data.objects if o.name.startswith('HC_LABEL')]:
        bpy.data.objects.remove(t, do_unlink=True)

def fit_ortho(cam_pos, look):
    fit_objs = []
    for p in bpy.data.objects:
        if not p.name.startswith(('HC_', 'HC_ENV_')) or p.name.startswith('HC_LABEL'):
            continue
        for o in descendants(p):
            if o.type not in ('MESH', 'CURVE', 'FONT'):
                continue
            if any(tag in o.name for tag in ('LEG_', 'STRETCHER', 'SHELF')):
                continue
            fit_objs.append(o)
    lo, hi = _framed_extents(fit_objs)
    w, h = _projected_size(lo, hi, Vector(cam_pos), Vector(look))
    print(json.dumps({'fit_objs': len(fit_objs), 'bbox_min': [round(c, 3) for c in lo],
                      'bbox_max': [round(c, 3) for c in hi],
                      'projected_wh': [round(w, 3), round(h, 3)]}), flush=True)
    return max(w, h*(1600/1120))*1.06

def verify_bat_lateral():
    """Coordinator check: imported BAT mesh bbox center must sit on its JSON pose."""
    p = bpy.data.objects['HC_BAT']
    bpy.context.view_layer.update()
    lo, hi = _framed_extents(descendants(p))
    cx, cy = (lo.x + hi.x)/2, (lo.y + hi.y)/2
    pose = OBJ_POSES['BAT'][0]
    rep = {'bat_bbox_center_xy': [round(cx, 4), round(cy, 4)],
           'bat_pose_xy': [round(pose.x, 4), round(pose.y, 4)],
           'lateral_offset_m': [round(cx - pose.x, 4), round(cy - pose.y, 4)]}
    rep['ok'] = bool(abs(cx - pose.x) < 0.01 and abs(cy - pose.y) < 0.01)
    print(json.dumps({'bat_lateral_check': rep}, ensure_ascii=False), flush=True)
    return rep

def q2list(q):
    q = q.normalized()
    return [round(q.w, 6), round(q.x, 6), round(q.y, 6), round(q.z, 6)]

def main():
    report = {}
    kits, envkits = build_all_kits()
    report['seat_verification'] = verify_seated()
    print(json.dumps({'seat_verification': report['seat_verification']}, ensure_ascii=False), flush=True)

    placed = compose()
    light_rig(Vector((0, 0, 0.15)), extent=1.35, energy=1.5)
    world_bg((0.60, 0.63, 0.68, 1.0), strength=0.75)

    cam_pos = Vector((0.55, -0.95, 0.62))
    look = Vector((0, 0.05, 0.12))
    euler_main = (look - cam_pos).to_track_quat('-Z', 'Y').to_euler()
    for oid, text, pos in PREVIEW_LABELS:
        add_label(text, pos, euler_main)

    ortho = fit_ortho(cam_pos, look)
    report['ortho_autofit'] = {'ortho_scale_m': round(ortho, 3)}
    report['bat_lateral_check'] = verify_bat_lateral()
    r1 = render_preview('drone_bench_kit_preview.png', cam_pos, look, ortho=ortho)

    clear_labels()
    cam2 = Vector((0.0, -0.005, 0.18))
    look2 = Vector((-0.208, 0.208, 0.076))
    euler2 = (look2 - cam2).to_track_quat('-Z', 'Y').to_euler()
    add_label('M3 减震垫', (-0.265, 0.265, 0.128), euler2, size=0.012)
    r2 = render_preview('drone_bench_kit_preview_m3.png', cam2, look2, persp_fov=50)
    clear_labels()
    report['renders'] = [r1, r2]

    # ---- scene JSON
    OBJ_META = {
        'BAT':       ('智能电池', [96, 100, 108], ['point', 'insert'], {}, '黑色电池,沿把手方向插入,底部一端为触点'),
        'BAY':       ('电池仓', [255, 148, 36], ['point'], {'insertion': [0, 0, -0.0185]}, '机身腹部卡扣仓,仰放开口朝上,仓底有金色触点针'),
        'GUARD':     ('电池护罩', [176, 180, 190], ['point', 'rotate'], {}, '烟灰色半透明护罩,顶部白色刻线为角度指示'),
        'M1':        ('前左电机', [110, 168, 210], ['point'], {}, '消歧用,仅指认'),
        'M2':        ('前右电机', [214, 156, 102], ['point'], {}, '消歧用,仅指认'),
        'M3':        ('左后电机', [235, 140, 52], ['point', 'inspect_back'], {}, '朝机身一侧径向面上有橙色减震垫,被机臂遮挡'),
        'M4':        ('右后电机', [148, 198, 142], ['point'], {}, '消歧用,仅指认'),
        'VOLTMETER': ('台式电压表', [108, 196, 158], ['point', 'wait'], {}, '数码管读数 12.6,过压报红色'),
    }
    objects = []
    for oid, (pos, quat) in OBJ_POSES.items():
        label, color, caps, anchors, desc = OBJ_META[oid]
        objects.append({
            'object_id': oid, 'label': label, 'asset': f'assets/meshes/drone_bench/{oid}.glb',
            'pose': {'position_m': [round(c, 4) for c in pos], 'wxyz': q2list(quat)},
            'color': color, 'capabilities': caps, 'anchors': anchors, 'description': desc,
        })
    environment = []
    for pid, (pos, quat) in ENV_POSES.items():
        environment.append({'prop_id': pid, 'label': '', 'asset': f'assets/meshes/env/{pid}.glb',
                            'pose': {'position_m': [round(c, 4) for c in pos], 'wxyz': q2list(quat)},
                            'scale_m': [1.0, 1.0, 1.0]})
    for pid, (key, cxy, bz, rz, ex, sc) in PROPS.items():
        p = bpy.data.objects['HC_ENV_' + pid]
        environment.append({'prop_id': pid, 'label': '', 'asset': f'assets/meshes/env/{key}.glb',
                            'pose': {'position_m': [round(c, 4) for c in p.location], 'wxyz': q2list(p.rotation_quaternion)},
                            'scale_m': [round(s, 4) for s in sc]})
    spec = {
        'schema_version': '1.0', 'scene_id': 'drone_bench', 'title': '无人机检修台',
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': objects,
        'initial_instruction': '把电池 BAT 插进机身电池仓 BAY,顺时针拧紧固定护罩 GUARD 30 度,再检查左后电机 M3 朝机身一侧的减震垫,电压表 VOLTMETER 全程盯着。',
        'camera_position_m': [round(c, 4) for c in cam_pos],
        'camera_look_at_m': [round(c, 4) for c in look],
        'environment': environment,
        'render_hints': {'ortho_scale_m': round(ortho, 3), 'grid_extent_m': 1.8, 'cue_scale': 0.8, 'label_offset_m': 0.10},
    }
    write_scene_json('drone_bench', spec)
    print(json.dumps({'ortho': report['ortho_autofit'], 'props_placed': placed}, ensure_ascii=False), flush=True)
    print('BUILD_OK', flush=True)

if __name__ == '__main__':
    main()
