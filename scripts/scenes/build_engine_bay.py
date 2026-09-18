"""Build the engine_bay (发动机舱维修) scene kit (Blender 3.1.2, CPU, via resource_guard).

Run:
  cd /home/hdd3/zhanghaonan/projects/holocue && .venv/bin/python scripts/guard/resource_guard.py \
      --rss-limit-gb 12 --execute -- /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/scenes/build_engine_bay.py 2>&1 | tee runs/scene_v2/build_engine_bay.log

Replicates the AR engine-repair reference photo: transverse inline-4 (EA888-style)
in an open-hood bay, garage workshop dressing, no human figure. docs/10 is the
design source; LAYOUT below is the single source of truth for world poses
(Z-up, m). Interactive GLBs are authored in world orientation (JSON quaternions
identity), so each GLB's local frame equals the world frame at its pose.

Outputs:
  assets/meshes/engine_bay/{CLAMP,PLUG,PLUGPORT,OILCAP,TENSIONER,CONN}.glb
  assets/meshes/env/engine_bay_{shell,engine,radiator}.glb  (+ engine_round props
    produced beforehand by scripts/assets/process_env_props.py)
  scenes/engine_bay/scene.json
  runs/scene_v2/engine_bay_kit_preview.png + 4 detail previews
  runs/scene_v2/build_engine_bay.log (assertion JSON evidence)

Sightline model: env parts prefixed BLK_ are potential occluders; the official
camera (-0.85, 1.55, 1.55) -> (0, 0.10, 0.90) must reach every interactive
object through them (verify_sightlines, slab-method ray evidence like
build_server_rack's back-view check). Preview labels additionally pass
verify_label_sightlines: ortho ray casting from the fitted kit camera against
triangle-exact BVH trees of every mesh, because AABB intersection cannot see
foreground/background depth separation (r2 P1-1 lesson).
"""
import bpy, sys, math, json
import bmesh
from pathlib import Path
from mathutils import Vector, Euler, Quaternion, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403

KIT = ROOT / 'assets/meshes/engine_bay'
RAD = math.radians

# ----------------------------------------------------------------------------
# LAYOUT (single source of truth; docs/10 object table verbatim)
# ----------------------------------------------------------------------------
LAYOUT = {
    'scene_id': 'engine_bay',
    'title': '发动机舱维修',
    'initial_instruction': '把 CLAMP 逆时针转 90 度，接着把 PLUG 插进 PLUGPORT，最后检查 CONN 的背面。',
    'camera_position_m': (-0.85, 1.55, 1.55),
    'camera_look_at_m': (0, 0.10, 0.90),
    'objects': {
        'CLAMP': {'pose': ([-0.18, 0.35, 1.02], (1, 0, 0, 0)), 'label': '进气软管卡箍',
                  'color': (216, 180, 60), 'capabilities': ['point', 'rotate'],
                  'anchors': {}, 'description': '蜗虫式进气软管卡箍，黄锌色，逆时针松开'},
        'PLUG': {'pose': ([0.12, 0.28, 1.02], (1, 0, 0, 0)), 'label': '新火花塞',
                 'color': (238, 234, 226), 'capabilities': ['point', 'insert'],
                 'anchors': {}, 'description': '陶瓷白新火花塞，倒放在气门室盖前托槽内'},
        'PLUGPORT': {'pose': ([0.12, 0.10, 0.98], (1, 0, 0, 0)), 'label': '三缸火花塞孔',
                     'color': (70, 74, 80), 'capabilities': ['point'],
                     'anchors': {'insertion': [0, 0, 0.03]},
                     'description': '取下点火线圈后的三缸火花塞孔口'},
        'OILCAP': {'pose': ([-0.28, 0.05, 1.00], (1, 0, 0, 0)), 'label': '机油加注口盖',
                   'color': (46, 48, 52), 'capabilities': ['point', 'rotate'],
                   'anchors': {}, 'description': '黑色塑料旋盖，顶部有开启方向箭头'},
        'TENSIONER': {'pose': ([0.48, 0.30, 0.85], (1, 0, 0, 0)), 'label': '皮带张紧轮',
                      'color': (168, 172, 178), 'capabilities': ['point', 'rotate'],
                      'anchors': {}, 'description': '发动机右端多楔带张紧轮，六角位释放张紧'},
        'CONN': {'pose': ([0.55, -0.15, 0.88], (1, 0, 0, 0)), 'label': '变速箱侧连接器',
                 'color': (224, 120, 40), 'capabilities': ['point', 'inspect_back'],
                 'anchors': {}, 'description': '针脚面朝发动机内侧，需翻转检查背面'},
    },
    'env': {
        'shell': {'asset': 'assets/meshes/env/engine_bay_shell.glb', 'label': '机舱与车库结构',
                  'position': (0, 0, 0)},
        'engine': {'asset': 'assets/meshes/env/engine_assembly.glb', 'label': '横置直列四缸发动机',
                   'position': (0, 0, 0)},
        'radiator': {'asset': 'assets/meshes/env/engine_bay_radiator.glb', 'label': '散热器总成',
                     'position': (0, 0, 0)},
    },
    # PolyHaven props (processed by scripts/assets/process_env_props.py).
    # rx/ry/rz orient the stored Z-up GLB; center_xy/base_z/center_z place it.
    'props': {
        'tool_cart': {'glb': 'tool_cart.glb', 'label': '工具车', 'scale': 0.8,
                      'center': (-1.55, 0.42), 'base_z': 0.0, 'rz': 18.0},
        'bench_vice_01': {'glb': 'bench_vice_01.glb', 'label': '台虎钳', 'scale': 1.0,
                          'on': 'tool_cart', 'center': (-1.20, 0.30), 'rz': 15.0},
        'ratchet_wrench': {'glb': 'ratchet_wrench.glb', 'label': '棘轮扳手', 'scale': 1.0,
                           'on': 'tool_cart', 'center': (-1.62, 0.44), 'rx': 90.0, 'rz': 25.0},
        'flathead_screwdriver': {'glb': 'flathead_screwdriver.glb', 'label': '一字螺丝刀',
                                 'scale': 1.0, 'center': (-0.10, 0.635), 'base_z': 0.942,
                                 'rx': 90.0, 'rz': 78.0},
        'WoodenTable_03': {'glb': 'WoodenTable_03.glb', 'label': '木工作桌', 'scale': 1.0,
                           'center': (1.62, 0.35), 'base_z': 0.0, 'rz': -12.0},
        'oil_tin': {'glb': 'oil_tin.glb', 'label': '机油铁罐', 'scale': 1.0,
                    'on': 'WoodenTable_03', 'center': (1.50, 0.42), 'rz': 20.0},
        'small_oil_can_01': {'glb': 'small_oil_can_01.glb', 'label': '长嘴油壶', 'scale': 1.0,
                             'on': 'WoodenTable_03', 'center': (1.70, 0.50), 'rz': -30.0},
        'lubricant_spray': {'glb': 'lubricant_spray.glb', 'label': '润滑喷剂', 'scale': 1.0,
                            'on': 'WoodenTable_03', 'center': (1.76, 0.26), 'rz': 0.0},
        'steel_frame_shelves_02': {'glb': 'steel_frame_shelves_02.glb', 'label': '钢架货架',
                                   'scale': 1.0, 'center': (-0.85, -2.16), 'base_z': 0.0, 'rz': 0.0},
        'old_tyre': {'glb': 'old_tyre.glb', 'label': '旧轮胎', 'scale': 1.0,
                     'center': (1.72, -1.52), 'base_z': 0.0, 'rz': 20.0},
        'old_tyre_b': {'glb': 'old_tyre.glb', 'label': '旧轮胎', 'scale': 1.0,
                       'center': (1.70, -1.51), 'stack': True, 'rz': -15.0},
        'rusted_wheel_rim_01': {'glb': 'rusted_wheel_rim_01.glb', 'label': '锈蚀轮毂', 'scale': 1.0,
                                'center': (1.70, -1.50), 'stack': True, 'rz': 10.0},
        'old_military_compressor': {'glb': 'old_military_compressor.glb', 'label': '老式空压机',
                                    'scale': 0.9, 'center': (-1.70, -1.62), 'base_z': 0.0, 'rz': 25.0},
        'caged_hanging_light': {'glb': 'caged_hanging_light.glb', 'label': '网罩吊工作灯',
                                'scale': 1.0, 'center': (-0.85, 0.05), 'center_z': 2.57, 'rz': 0.0},
        'caged_hanging_light_b': {'glb': 'caged_hanging_light.glb', 'label': '网罩吊工作灯',
                                  'scale': 1.0, 'center': (0.85, -0.15), 'center_z': 2.57, 'rz': 70.0},
        'mounted_fluorescent_lights': {'glb': 'mounted_fluorescent_lights.glb', 'label': '荧光灯排',
                                       'scale': 1.0, 'center': (-0.30, -2.425), 'center_z': 2.10,
                                       'rx': -90.0, 'rz': 0.0},
    },
}

# key design constants (world m, Z-up); engine crank along X, +Y = car front
WELL_X = [-0.16, -0.02, 0.12, 0.26]       # spark-plug well row (y = 0.10)
WELL_Y = 0.10
COVER_TOP = 0.97                           # valve cover top face
WELL_TOP = 1.010                           # well collar mouth (insertion anchor)
BELT_PULLEYS = [(0.00, 0.56, 0.075), (0.22, 0.80, 0.030),   # (y, z, r) at x = 0.48
                (0.325, 0.85, 0.034), (-0.13, 0.72, 0.050)]
HOOD_HINGE = Vector((0.0, -0.70, 1.285))
HOOD_OPEN_DEG = 70.0

# Contract fill lights (render_hints.fill_lights, r2 P1-2). The generic k-scaled
# light_rig for this ortho (k=3.81) puts all three area lights above the garage
# ceiling (z 3.50-4.64 vs ceiling top 3.01), leaving the bay near-black in the
# official chain (render mean luma 18.6-19.2, dead-black <8 = 16.7% reproduced
# 2026-09-17, cf. 15.7% measured on the pre-fill official render). With these
# three in-garage lights: mean luma 140.6 / dead-black <8 = 0.01% -- official
# evidence runs/engine_bay_blender.png (scripts/build_blender_scene.py consumes
# the same values from the contract). [x, y, z, power_W, disk_size_m]
FILL_LIGHTS = [[-1.45, 2.45, 2.25, 560.0, 1.4],
               [0.95, 2.55, 2.30, 400.0, 1.1],
               [0.05, -1.05, 2.55, 320.0, 0.9]]

# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
M = {}

def make_materials():
    M['alu'] = flat('eb_alu', (0.52, 0.535, 0.555, 1.0), roughness=0.42, metallic=0.88)
    M['alu_dark'] = flat('eb_alu_dark', (0.36, 0.37, 0.39, 1.0), roughness=0.5, metallic=0.8)
    M['alu_bright'] = flat('eb_alu_bright', (0.70, 0.72, 0.74, 1.0), roughness=0.3, metallic=0.9)
    M['steel'] = flat('eb_steel', (0.44, 0.46, 0.49, 1.0), roughness=0.35, metallic=0.9)
    M['cast_dark'] = flat('eb_cast_dark', (0.235, 0.24, 0.25, 1.0), roughness=0.62, metallic=0.7)
    M['vc_black'] = flat('eb_valvecover', (0.045, 0.047, 0.052, 1.0), roughness=0.58, metallic=0.1)
    M['intake_silver'] = flat('eb_intake_plastic', (0.60, 0.625, 0.65, 1.0), roughness=0.52, metallic=0.06)
    M['rubber_black'] = flat('eb_rubber', (0.028, 0.029, 0.032, 1.0), roughness=0.88)
    M['belt_rubber'] = flat('eb_belt_rubber', (0.055, 0.057, 0.062, 1.0), roughness=0.62)
    M['body_paint'] = flat('eb_body_paint', (0.115, 0.155, 0.185, 1.0), roughness=0.32, metallic=0.55)
    M['body_dark'] = flat('eb_body_dark', (0.075, 0.09, 0.105, 1.0), roughness=0.55, metallic=0.4)
    M['bay_dark'] = flat('eb_bay_dark', (0.082, 0.086, 0.092, 1.0), roughness=0.8, metallic=0.3)
    M['gold_zinc'] = flat('eb_gold_zinc', (0.80, 0.64, 0.25, 1.0), roughness=0.3, metallic=0.9)
    M['ceramic'] = flat('eb_ceramic', (0.90, 0.89, 0.86, 1.0), roughness=0.3)
    M['rust'] = flat('eb_rust', (0.30, 0.20, 0.14, 1.0), roughness=0.75, metallic=0.35)
    M['heat_shield'] = flat('eb_heat_shield', (0.72, 0.735, 0.75, 1.0), roughness=0.33, metallic=0.9)
    M['cable_black'] = flat('eb_cable_black', (0.03, 0.031, 0.034, 1.0), roughness=0.7)
    M['cable_red'] = flat('eb_cable_red', (0.42, 0.07, 0.05, 1.0), roughness=0.65)
    M['pin_gold'] = flat('eb_pin_gold', (0.85, 0.70, 0.25, 1.0), roughness=0.3, metallic=0.95)
    M['filter_white'] = flat('eb_filter_white', (0.82, 0.83, 0.85, 1.0), roughness=0.5)
    M['dip_yellow'] = flat('eb_dip_yellow', (0.85, 0.65, 0.10, 1.0), roughness=0.5)
    M['battery_dark'] = flat('eb_battery', (0.05, 0.052, 0.056, 1.0), roughness=0.6)
    M['coolant_tank'] = flat('eb_coolant_tank', (0.55, 0.72, 0.68, 1.0), roughness=0.25, metallic=0.05)
    M['coolant_tank'].blend_method = 'BLEND'
    M['coolant_tank'].node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.55
    M['label_prev'] = flat('eb_label_prev', (0.96, 0.97, 0.99, 1.0), roughness=0.5,
                           emissive=(1, 1, 1, 1.0), emission_strength=0.35)
    M['floor'] = pbr('eb_floor', 'concrete_floor_worn_001', scale=2.4)
    M['wall'] = pbr('eb_wall', 'factory_wall', scale=2.0)

# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def _wipe_meshes():
    for o in [x for x in bpy.data.objects if x.type == 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)

def _bbox_frame(objs):
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for v in o.bound_box:
            p = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, p.x); lo.y = min(lo.y, p.y); lo.z = min(lo.z, p.z)
            hi.x = max(hi.x, p.x); hi.y = max(hi.y, p.y); hi.z = max(hi.z, p.z)
    return lo, hi

def _tri(objs):
    return sum(len(o.data.polygons) for o in objs if o.type == 'MESH')

def tube(name, p0, p1, r, mat, vertices=20):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=tuple((p0 + p1) / 2),
                                        vertices=vertices)
    o = bpy.context.object; o.name = name
    o.rotation_euler = d.to_track_quat('Z', 'X').to_euler()
    if mat: o.data.materials.append(mat)
    return o

def ring(name, major, minor, location, mat, axis='Z', major_segments=32, minor_segments=8):
    bpy.ops.mesh.primitive_torus_add(location=location, major_radius=major, minor_radius=minor,
                                     major_segments=major_segments, minor_segments=minor_segments)
    o = bpy.context.object; o.name = name
    if axis == 'Y':
        o.rotation_euler = (RAD(90), 0, 0)
    elif axis == 'X':
        o.rotation_euler = (0, RAD(90), 0)
    if mat: o.data.materials.append(mat)
    return o

def _rot_world(objs, pivot, deg, axis='X'):
    q = Quaternion(Vector((1, 0, 0)) if axis == 'X' else Vector((0, 0, 1)), RAD(deg))
    t = Matrix.Translation(pivot)
    m = t @ q.to_matrix().to_4x4() @ t.inverted()
    # r2 fix: flush the depsgraph BEFORE composing. o.matrix_world read right
    # after box() set o.location can return the stale pre-location (identity)
    # matrix; m @ stale then overwrote the pose. This sent the last-created
    # hood box SH_hood_hinge1 rotating about the hinge from the ORIGIN and it
    # landed as a stray 0.05x0.08x0.17 m column at (0, 0.75, 1.50) in front of
    # the bay (mesh "Cube.072" -- the foreground that occluded the PLUGPORT
    # label's G/P in the r2 review). With the update, hinge1 lands at the
    # rear-right mirror of hinge-1: (0.45, -0.66, 1.34). Evidence:
    # runs/scene_v2/probe_label_sight_r2.log (hit) + rebuild bbox check.
    bpy.context.view_layer.update()
    for o in objs:
        o.matrix_world = m @ o.matrix_world.copy()
    bpy.context.view_layer.update()
    deselect_all()
    for o in objs:
        o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    deselect_all()

def _hull2d(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]

# ----------------------------------------------------------------------------
# interactive objects (local frame == world orientation; origin at JSON pose)
# ----------------------------------------------------------------------------
def build_clamp():
    """Worm-drive hose clamp, origin on the ring axis (hose axis runs +Y in world).
    The worm screw head sits on top so the visible slot faces +Z and the rotate
    demo about local Z turns the screw."""
    o = []
    o.append(ring('CLAMP_band', 0.0312, 0.0042, (0, 0, 0), M['gold_zinc'], axis='Y'))
    o.append(box('CLAMP_housing', (0.026, 0.014, 0.015), (0, 0, 0.032), M['gold_zinc'], bevel=0.001))
    o.append(cyl('CLAMP_hex', 0.0095, 0.008, (0, 0, 0.0435), M['gold_zinc'], vertices=6))
    o.append(box('CLAMP_slot', (0.0165, 0.0050, 0.003), (0, 0, 0.048), M['rubber_black'], bevel=0))
    o.append(box('CLAMP_tail', (0.013, 0.011, 0.004), (0.031, 0, 0.028), M['gold_zinc'], bevel=0.0006))
    return o

def build_plug():
    """Spark plug lying along local X on the valve-cover tray, origin at mid-ceramic."""
    o = []
    o.append(cyl('PLUG_ceramic', 0.0085, 0.055, (0.008, 0, 0), M['ceramic'],
                 rot=(0, RAD(90), 0), vertices=24))
    for i, x in enumerate((-0.006, 0.004, 0.014, 0.022)):
        o.append(ring(f'PLUG_rib{i}', 0.0095, 0.0015, (x, 0, 0), M['ceramic'], axis='X',
                      major_segments=24, minor_segments=6))
    o.append(cyl('PLUG_hex', 0.0105, 0.008, (-0.024, 0, 0), M['steel'],
                 rot=(0, RAD(90), 0), vertices=6))
    o.append(cyl('PLUG_shell', 0.0068, 0.014, (-0.035, 0, 0), M['steel'],
                 rot=(0, RAD(90), 0), vertices=20))
    o.append(cyl('PLUG_nose', 0.0052, 0.012, (-0.048, 0, 0), M['ceramic'],
                 rot=(0, RAD(90), 0), vertices=16))
    o.append(box('PLUG_terminal', (0.018, 0.004, 0.0045), (0.042, 0, 0.0065), M['steel'], bevel=0))
    return o

def build_plugport():
    """Open spark-plug well (coil removed), origin at (0.12,0.10,0.98).
    Bore extends DOWN into the head; mouth/collar top at local +0.031, which is
    the insertion anchor plane."""
    o = []
    o.append(cyl('PP_tube', 0.024, 0.088, (0, 0, -0.014), M['vc_black'], vertices=28))
    o.append(cyl('PP_collar', 0.0285, 0.010, (0, 0, 0.026), M['vc_black'], vertices=28))
    o.append(cyl('PP_bore', 0.0205, 0.075, (0, 0, -0.0125), M['rubber_black'], vertices=24))
    o.append(cyl('PP_bottom', 0.0205, 0.004, (0, 0, -0.053), M['rubber_black'], vertices=24))
    o.append(cyl('PP_seat', 0.0215, 0.008, (0, 0, -0.012), M['ceramic'], vertices=24))
    o.append(cyl('PP_mhex', 0.007, 0.006, (0, 0, -0.028), M['steel'], vertices=6))
    o.append(cyl('PP_terminal', 0.0042, 0.006, (0, 0, -0.005), M['steel'], vertices=10))
    for sx in (-1, 1):
        o.append(box(f'PP_tab{sx}', (0.008, 0.020, 0.007), (sx * 0.0305, 0, 0.007),
                     M['vc_black'], bevel=0.0006))
        o.append(cyl(f'PP_bolt{sx}', 0.004, 0.006, (sx * 0.0305, 0, 0.011), M['steel'], vertices=10))
    return o

def build_oilcap():
    o = []
    o.append(cyl('OC_skirt', 0.0295, 0.016, (0, 0, -0.007), M['vc_black'], vertices=28))
    o.append(cyl('OC_top', 0.031, 0.014, (0, 0, 0.004), M['vc_black'], vertices=28))
    for i in range(14):
        a = RAD(i * 360 / 14)
        b = box(f'OC_rib{i}', (0.0045, 0.010, 0.004),
                (math.cos(a) * 0.0245, math.sin(a) * 0.0245, 0.0105), M['bay_dark'], bevel=0)
        b.rotation_euler = (0, 0, a)
        o.append(b)
    o.append(box('OC_arrow_shaft', (0.018, 0.005, 0.0016), (-0.006, 0, 0.0122), M['intake_silver'], bevel=0))
    for s in (-1, 1):
        a = box(f'OC_arrow_head{s}', (0.009, 0.0046, 0.0016), (0.008, s * 0.0042, 0.0122),
                M['intake_silver'], bevel=0)
        a.rotation_euler = (0, 0, s * RAD(45))
        o.append(a)
    o.append(box('OC_retainer', (0.044, 0.006, 0.005), (0, 0, -0.0145), M['bay_dark'], bevel=0))
    return o

def build_tensioner():
    """Origin at the assembly visual center; arm reaches +Y (toward belt run top)."""
    o = []
    o.append(box('TN_base', (0.055, 0.060, 0.028), (0, -0.048, -0.012), M['alu'], bevel=0.0015))
    o.append(cyl('TN_pivot', 0.012, 0.044, (0, -0.048, -0.002), M['steel'],
                 rot=(0, RAD(90), 0), vertices=16))
    o.append(box('TN_arm', (0.040, 0.118, 0.024), (0, -0.012, -0.005), M['alu'], bevel=0.0012))
    o.append(cyl('TN_idler', 0.034, 0.030, (0, 0.025, 0.0), M['rubber_black'],
                 rot=(0, RAD(90), 0), vertices=32))
    for sx in (-1, 1):
        o.append(cyl(f'TN_washer{sx}', 0.036, 0.004, (sx * 0.0165, 0.025, 0.0), M['cast_dark'],
                     rot=(0, RAD(90), 0), vertices=32))
    for i, x in enumerate((-0.008, 0.0, 0.008)):
        o.append(ring(f'TN_groove{i}', 0.0345, 0.0012, (x, 0.025, 0.0), M['bay_dark'], axis='X',
                      major_segments=32, minor_segments=5))
    o.append(cyl('TN_hex', 0.0125, 0.009, (0.020, 0.025, 0.0), M['steel'],
                 rot=(0, RAD(90), 0), vertices=6))
    return o

def build_conn():
    """Connector shell, origin at shell center; pin face is local -X; corrugated
    tail + wire extend -Y (bbox convention registered in check_origins.py)."""
    o = []
    o.append(box('CONN_shell', (0.050, 0.036, 0.024), (0, 0, 0), M['vc_black'], bevel=0.0015))
    o.append(box('CONN_facerecess', (0.004, 0.028, 0.018), (-0.0255, 0, 0), M['rubber_black'], bevel=0))
    for i in range(8):
        yy = -0.009 + (i % 4) * 0.006
        zz = -0.005 if i < 4 else 0.005
        o.append(cyl(f'CONN_pin{i}', 0.0015, 0.007, (-0.0295, yy, zz), M['pin_gold'],
                     rot=(0, RAD(90), 0), vertices=8))
    o.append(box('CONN_latch', (0.020, 0.008, 0.006), (0.008, 0, 0.0145), M['bay_dark'], bevel=0.001))
    o.append(box('CONN_locktab', (0.030, 0.028, 0.005), (0.014, 0, -0.0135), M['cable_red'], bevel=0.001))
    o.append(cyl('CONN_sleeve', 0.0115, 0.030, (0, -0.033, 0), M['rubber_black'], vertices=20))
    for i, y in enumerate((-0.020, -0.027, -0.034, -0.041)):
        o.append(ring(f'CONN_corr{i}', 0.0122, 0.0018, (0, y, 0), M['rubber_black'], axis='Y',
                      major_segments=20, minor_segments=6))
    o.append(tube('CONN_wire', (0, -0.048, 0), (0, -0.082, -0.006), 0.0065, M['cable_black']))
    return o

# ----------------------------------------------------------------------------
# engine_bay_shell: bay structure + garage floor/wall + open hood (BLK_ = blocker)
# ----------------------------------------------------------------------------
def build_shell():
    o = []
    o.append(box('SH_garage_floor', (5.8, 5.8, 0.08), (0, 0, -0.04), M['floor'], bevel=0.004))
    o.append(box('BLK_SH_garage_wall', (5.8, 0.10, 2.70), (0, -2.50, 1.35), M['wall'], bevel=0.004))
    # review#4 fix: ceiling plane so the hanging-light cords terminate somewhere
    o.append(box('SH_garage_ceiling', (5.8, 5.8, 0.06), (0, 0, 2.98), M['bay_dark'], bevel=0.004))
    o.append(box('SH_garage_ceilingbeam1', (5.8, 0.12, 0.10), (0, -0.9, 2.93), M['cast_dark'], bevel=0.002))
    o.append(box('SH_garage_ceilingbeam2', (5.8, 0.12, 0.10), (0, 0.9, 2.93), M['cast_dark'], bevel=0.002))
    # bay floor pan + under cross members
    o.append(box('BLK_SH_pan', (1.58, 1.42, 0.022), (0, -0.06, 0.164), M['bay_dark'], bevel=0.002))
    o.append(box('SH_subframe_f', (1.44, 0.07, 0.09), (0, 0.34, 0.115), M['cast_dark'], bevel=0.002))
    o.append(box('SH_subframe_r', (1.44, 0.07, 0.09), (0, -0.42, 0.115), M['cast_dark'], bevel=0.002))
    # inner fenders (multi-segment arc, tops curl inward)
    for sx in (-1, 1):
        o.append(box(f'BLK_SH_fender{sx}_s1', (0.030, 1.44, 0.33), (sx * 0.775, -0.06, 0.315),
                     M['body_paint'], bevel=0.002))
        s2 = box(f'BLK_SH_fender{sx}_s2', (0.030, 1.44, 0.31), (sx * 0.762, -0.06, 0.615),
                 M['body_paint'], bevel=0.002)
        s2.rotation_euler = (0, -sx * RAD(8), 0); o.append(s2)
        s3 = box(f'BLK_SH_fender{sx}_s3', (0.030, 1.44, 0.27), (sx * 0.732, -0.06, 0.885),
                 M['body_paint'], bevel=0.002)
        s3.rotation_euler = (0, -sx * RAD(17), 0); o.append(s3)
        o.append(box(f'BLK_SH_fender{sx}_lip', (0.11, 1.44, 0.022), (sx * 0.715, -0.06, 1.024),
                     M['body_paint'], bevel=0.002))
    # firewall + cowl + harness punch
    o.append(box('BLK_SH_firewall', (1.56, 0.05, 1.22), (0, -0.775, 0.755), M['body_dark'], bevel=0.003))
    o.append(box('SH_firewall_pad', (1.42, 0.024, 0.64), (0, -0.742, 0.82), M['rubber_black'], bevel=0.002))
    o.append(box('BLK_SH_cowl', (1.56, 0.26, 0.035), (0, -0.90, 1.295), M['body_paint'], bevel=0.003))
    o.append(box('SH_hinge_deck', (1.56, 0.06, 0.09), (0, -0.715, 1.325), M['body_dark'], bevel=0.002))
    o.append(box('SH_punch_boss', (0.26, 0.09, 0.13), (0.20, -0.735, 1.09), M['body_dark'], bevel=0.002))
    o.append(box('SH_punch_grommet', (0.20, 0.035, 0.07), (0.20, -0.692, 1.09), M['rubber_black'], bevel=0.002))
    o.append(tube('SH_firewall_harness', (0.20, -0.70, 1.09), (0.02, -0.44, 1.015), 0.015, M['cable_black']))
    # brake booster + master cylinder
    o.append(box('BLK_SH_booster', (0.10, 0.14, 0.23), (-0.42, -0.655, 1.02), M['vc_black'], bevel=0.003))
    o.append(cyl('SH_booster_dome', 0.105, 0.09, (-0.42, -0.585, 1.02), M['vc_black'],
                 rot=(RAD(90), 0, 0), vertices=28))
    o.append(box('SH_master_cyl', (0.09, 0.15, 0.09), (-0.42, -0.505, 1.06), M['alu'], bevel=0.002))
    # front closure: upper + lower cross members, side brackets
    # review#1 fix: upper beam top lowered 0.98 -> 0.94 (grazed the low TENSIONER
    # sightline samples, evidence in round-1 log)
    o.append(box('BLK_SH_xmember_hi', (1.44, 0.075, 0.05), (0, 0.635, 0.915), M['cast_dark'], bevel=0.002))
    o.append(box('SH_latch', (0.09, 0.06, 0.05), (0, 0.635, 0.865), M['steel'], bevel=0.001))
    o.append(box('BLK_SH_xmember_lo', (1.44, 0.09, 0.10), (0, 0.635, 0.50), M['cast_dark'], bevel=0.002))
    for sx in (-1, 1):
        o.append(box(f'SH_closure_brk{sx}', (0.05, 0.11, 0.38), (sx * 0.70, 0.635, 0.72),
                     M['body_dark'], bevel=0.002))
    # strut towers (dome + top plate + 3 nuts + tie plate)
    for sx in (-1, 1):
        o.append(cyl(f'BLK_SH_tower{sx}', 0.13, 0.15, (sx * 0.56, -0.42, 0.945), M['body_paint'],
                     vertices=32))
        o.append(cyl(f'BLK_SH_tower{sx}_plate', 0.118, 0.018, (sx * 0.56, -0.42, 1.028),
                     M['body_paint'], vertices=32))
        for k in range(3):
            a = RAD(30 + k * 120)
            o.append(cyl(f'SH_tower{sx}_nut{k}', 0.011, 0.016,
                         (sx * 0.56 + math.cos(a) * 0.085, -0.42 + math.sin(a) * 0.085, 1.040),
                         M['steel'], vertices=6))
        o.append(box(f'SH_tower{sx}_tie', (0.19, 0.26, 0.018), (sx * 0.655, -0.42, 0.995),
                     M['body_paint'], bevel=0.002))
    # battery (left front corner)
    o.append(box('BLK_SH_battery', (0.26, 0.18, 0.20), (-0.58, 0.30, 0.90), M['battery_dark'], bevel=0.003))
    o.append(box('SH_battery_lid', (0.24, 0.16, 0.016), (-0.58, 0.30, 0.905), M['battery_dark'], bevel=0.002))
    o.append(cyl('SH_battery_term_p', 0.013, 0.020, (-0.50, 0.245, 0.905), M['pin_gold'], vertices=12))
    o.append(tube('SH_battery_cable', (-0.50, 0.245, 0.99), (-0.55, -0.20, 0.93), 0.007, M['cable_red']))
    # ---- open hood: build closed, then rotate 70 deg up about the hinge line ----
    hood = []
    hood.append(box('BLK_SH_hood_outer', (1.52, 1.30, 0.012), (0, -0.05, 1.302), M['body_paint'], bevel=0.004))
    hood.append(box('BLK_SH_hood_inner', (1.46, 1.24, 0.008), (0, -0.05, 1.293), M['body_dark'], bevel=0.002))
    for yy in (-0.55, -0.25, 0.05, 0.35):
        hood.append(box(f'BLK_SH_hood_rib{yy}', (1.34, 0.05, 0.020), (0, yy, 1.278), M['body_dark'], bevel=0.0015))
    for xx in (-0.52, 0.52):
        hood.append(box(f'BLK_SH_hood_ribx{xx}', (0.05, 1.16, 0.018), (xx, -0.05, 1.279), M['body_dark'], bevel=0.0015))
    for sx in (-1, 1):
        hood.append(box(f'SH_hood_hinge{sx}', (0.045, 0.17, 0.028), (sx * 0.45, -0.635, 1.268),
                        M['cast_dark'], bevel=0.002))
    _rot_world(hood, HOOD_HINGE, HOOD_OPEN_DEG, axis='X')
    o.extend(hood)
    # gas struts (computed in the open pose)
    # review#4 fix: strut base moved onto the tower tie plate (was embedded in
    # the right strut-tower dome, evidence: round-3 kit review)
    for sx in (-1, 1):
        hy = HOOD_HINGE.y + 0.38 * math.cos(RAD(HOOD_OPEN_DEG))
        hz = HOOD_HINGE.z + 0.38 * math.sin(RAD(HOOD_OPEN_DEG))
        o.append(tube(f'SH_strut{sx}_body', (sx * 0.67, -0.52, 1.02), (sx * 0.56, -0.535, 1.30),
                      0.0095, M['alu_dark']))
        o.append(tube(f'SH_strut{sx}_rod', (sx * 0.56, -0.535, 1.30), (sx * 0.50, hy, hz),
                      0.005, M['alu_bright']))
    return o

# ----------------------------------------------------------------------------
# engine_assembly: EA888-style transverse inline-4 (BLK_ = sightline blocker)
# ----------------------------------------------------------------------------
def build_engine():
    o = []
    # core castings
    o.append(box('ENG_block', (0.64, 0.30, 0.24), (0.02, -0.01, 0.70), M['alu'], bevel=0.004))
    o.append(box('ENG_oilpan', (0.52, 0.24, 0.16), (0.02, -0.03, 0.50), M['alu_dark'], bevel=0.004))
    o.append(cyl('ENG_drain', 0.009, 0.012, (0.10, -0.08, 0.415), M['steel'], vertices=12))
    o.append(box('ENG_head', (0.62, 0.28, 0.10), (0.02, -0.01, 0.87), M['alu_bright'], bevel=0.003))
    # valve cover (black plastic, ribs + facets + filler neck + tray + wells)
    o.append(box('ENG_valvecover', (0.62, 0.26, 0.05), (0.02, -0.005, 0.945), M['vc_black'], bevel=0.003))
    for yy in (-0.10, -0.062, -0.024):
        o.append(box(f'ENG_cover_rib{yy}', (0.58, 0.013, 0.019), (0.02, yy, 0.973), M['vc_black'], bevel=0.002))
    o.append(box('ENG_cover_ribe', (0.014, 0.22, 0.019), (0.30, -0.005, 0.973), M['vc_black'], bevel=0.002))
    facet = box('ENG_cover_facet', (0.58, 0.10, 0.014), (0.02, -0.095, 0.966), M['vc_black'], bevel=0.0015)
    facet.rotation_euler = (RAD(14), 0, 0); o.append(facet)
    o.append(cyl('ENG_oilneck', 0.033, 0.030, (-0.28, 0.05, 0.985), M['vc_black'], vertices=28))
    # spark-plug wells + coils (well #3 = PLUGPORT stays open, no coil)
    for x in WELL_X:
        if abs(x - 0.12) < 1e-6:
            continue
        o.append(cyl(f'ENG_well{x}', 0.024, 0.075, (x, WELL_Y, 0.9725), M['vc_black'], vertices=24))
        o.append(cyl(f'ENG_coil{x}', 0.0215, 0.050, (x, WELL_Y, 1.035), M['vc_black'], vertices=20))
        o.append(box(f'ENG_coilconn{x}', (0.026, 0.030, 0.018), (x, WELL_Y, 1.064), M['bay_dark'], bevel=0.001))
        o.append(ring(f'ENG_coilboot{x}', 0.0235, 0.0025, (x, WELL_Y, 1.013), M['vc_black'], axis='Z',
                      major_segments=20, minor_segments=6))
    # spark-plug service tray above the plenum (PLUG rests here)
    o.append(box('ENG_tray', (0.17, 0.11, 0.011), (0.12, 0.285, 1.006), M['steel'], bevel=0.0015))
    for yy in (0.233, 0.337):
        o.append(box(f'ENG_tray_lip{yy}', (0.17, 0.008, 0.007), (0.12, yy, 1.0125), M['steel'], bevel=0.0008))
    o.append(tube('ENG_tray_leg1', (0.06, 0.26, 1.001), (0.06, 0.26, 0.928), 0.005, M['steel'], vertices=10))
    o.append(tube('ENG_tray_leg2', (0.19, 0.31, 1.001), (0.19, 0.31, 0.946), 0.005, M['steel'], vertices=10))
    # intake: 4 runners -> plenum + resonator dome
    for x in WELL_X:
        r1 = box(f'ENG_runner{x}', (0.048, 0.105, 0.052), (x, 0.185, 0.885), M['intake_silver'], bevel=0.002)
        r1.rotation_euler = (RAD(-28), 0, 0); o.append(r1)
        o.append(box(f'ENG_runner2_{x}', (0.048, 0.060, 0.048), (x, 0.272, 0.902), M['intake_silver'], bevel=0.002))
    o.append(cyl('BLK_ENG_plenum', 0.062, 0.52, (0.05, 0.30, 0.885), M['intake_silver'],
                 rot=(0, RAD(90), 0), vertices=28))
    for x in (-0.15, -0.05, 0.05, 0.15, 0.25):
        o.append(ring(f'ENG_plenum_rib{x}', 0.063, 0.004, (x, 0.30, 0.885), M['intake_silver'], axis='X'))
    # throttle elbow + body
    o.append(tube('ENG_throttle_elbow', (-0.18, 0.27, 0.905), (-0.18, 0.245, 0.965), 0.034, M['intake_silver'], vertices=24))
    o.append(cyl('ENG_throttle', 0.037, 0.065, (-0.18, 0.2725, 1.00), M['alu'],
                 rot=(RAD(90), 0, 0), vertices=28))
    o.append(cyl('ENG_throttle_plate', 0.033, 0.004, (-0.18, 0.2725, 1.00), M['alu_dark'],
                 rot=(RAD(90), 0, RAD(15)), vertices=24))
    # corrugated intake hose (CLAMP rides it at y=0.35 on a SMOOTH stretch;
    # review#2 fix: rings previously intersected the clamp band)
    o.append(tube('ENG_hose_stub', (-0.18, 0.300, 1.002), (-0.18, 0.335, 1.015), 0.027, M['rubber_black'], vertices=24))
    o.append(tube('ENG_hose', (-0.18, 0.335, 1.02), (-0.18, 0.545, 1.02), 0.026, M['rubber_black'], vertices=24))
    for i in range(8):
        y = 0.379 + i * 0.021
        if abs(y - 0.35) < 0.020:
            continue
        o.append(ring(f'ENG_hose_corr{i}', 0.0282, 0.0045, (-0.18, y, 1.02),
                      M['rubber_black'], axis='Y', major_segments=24, minor_segments=8))
    o.append(ring('ENG_hose_clamp_far', 0.0300, 0.0035, (-0.18, 0.552, 1.02), M['gold_zinc'], axis='Y'))
    o.append(tube('ENG_airduct', (-0.18, 0.550, 1.018), (-0.315, 0.487, 0.995), 0.028, M['rubber_black'], vertices=20))
    o.append(box('BLK_ENG_airbox', (0.26, 0.20, 0.16), (-0.32, 0.585, 0.955), M['vc_black'], bevel=0.003))
    o.append(box('ENG_airbox_lid', (0.24, 0.17, 0.018), (-0.32, 0.585, 0.968), M['bay_dark'], bevel=0.002))
    o.append(box('ENG_airbox_strap', (0.27, 0.03, 0.165), (-0.32, 0.585, 0.955), M['steel'], bevel=0.001))
    # right-end accessory drive (belt plane x ~ 0.48)
    o.append(box('ENG_endplate', (0.045, 0.34, 0.42), (0.375, 0.0, 0.68), M['alu_dark'], bevel=0.003))
    o.append(cyl('ENG_crankpulley', 0.075, 0.050, (0.48, 0.0, 0.56), M['steel'],
                 rot=(0, RAD(90), 0), vertices=36))
    for i, r in enumerate((0.072, 0.067, 0.062)):
        o.append(ring(f'ENG_crank_groove{i}', r, 0.0022, (0.48, 0.0, 0.56), M['bay_dark'], axis='X'))
    o.append(cyl('ENG_crankhub', 0.022, 0.062, (0.48, 0.0, 0.56), M['steel'],
                 rot=(0, RAD(90), 0), vertices=20))
    o.append(cyl('ENG_alternator', 0.052, 0.10, (0.525, 0.22, 0.80), M['alu'],
                 rot=(0, RAD(90), 0), vertices=28))
    for i in range(5):
        o.append(box(f'ENG_alt_rib{i}', (0.085, 0.006, 0.012), (0.525, 0.22 + math.cos(i * 1.2566) * 0.05,
                     0.80 + math.sin(i * 1.2566) * 0.05), M['alu_dark'], bevel=0))
    o.append(cyl('ENG_altpulley', 0.030, 0.036, (0.48, 0.22, 0.80), M['steel'],
                 rot=(0, RAD(90), 0), vertices=24))
    o.append(cyl('ENG_waterpump', 0.055, 0.05, (0.515, -0.13, 0.72), M['alu'],
                 rot=(0, RAD(90), 0), vertices=24))
    o.append(cyl('ENG_wppulley', 0.050, 0.034, (0.48, -0.13, 0.72), M['steel'],
                 rot=(0, RAD(90), 0), vertices=28))
    # serpentine belt: convex-hull band with real thickness (outer + inner ring,
    # walls + end caps) around the pulley set; review#2 fix: the open tube read
    # as a flat black shield over the pulleys.
    pts = []
    for (yy, zz, r) in BELT_PULLEYS:
        for k in range(48):
            a = 2 * math.pi * k / 48
            pts.append((yy + (r + 0.007) * math.cos(a), zz + (r + 0.007) * math.sin(a)))
    hull = _hull2d([(round(p[0], 5), round(p[1], 5)) for p in pts])
    cen = (sum(p[0] for p in hull) / len(hull), sum(p[1] for p in hull) / len(hull))
    inner = []
    for i, (yy, zz) in enumerate(hull):
        px, pz = hull[(i - 1) % len(hull)], hull[(i + 1) % len(hull)]
        ex, ez = px[0] - yy, px[1] - zz
        fx, fz = hull[(i + 1) % len(hull)][0] - yy, hull[(i + 1) % len(hull)][1] - zz
        nx, nz = -ez, ex
        nl = math.hypot(nx, nz) or 1.0
        nx, nz = nx / nl, nz / nl
        if (cen[0] - yy) * nx + (cen[1] - zz) * nz < 0:
            nx, nz = -nx, -nz
        inner.append((yy + nx * 0.005, zz + nz * 0.005))
    X0, X1 = 0.459, 0.473
    verts = ([(X0, y, z) for (y, z) in hull] + [(X1, y, z) for (y, z) in hull]
             + [(X0, y, z) for (y, z) in inner] + [(X1, y, z) for (y, z) in inner])
    n = len(hull)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))            # outer wall
        faces.append((2 * n + i, 2 * n + j, 3 * n + j, 3 * n + i))  # inner wall
        faces.append((i, j, 2 * n + j, 2 * n + i))    # x0 cap ring
        faces.append((n + j, 3 * n + j, 2 * n + j, n + j))  # x1 cap ring
    me = bpy.data.meshes.new('ENG_belt')
    me.from_pydata(verts, [], faces)
    me.update()
    belt = bpy.data.objects.new('ENG_belt', me)
    bpy.context.scene.collection.objects.link(belt)
    belt.data.materials.append(M['belt_rubber'])
    o.append(belt)
    # exhaust: 4 branches -> collector + heat shields + downpipe
    for x in WELL_X:
        o.append(tube(f'ENG_exh_branch{x}', (x, -0.145, 0.80), (x, -0.255, 0.665), 0.019, M['rust'], vertices=14))
    o.append(tube('ENG_exh_mid1', (-0.16, -0.255, 0.665), (0.0, -0.29, 0.585), 0.019, M['rust'], vertices=14))
    o.append(tube('ENG_exh_mid2', (-0.02, -0.255, 0.665), (0.02, -0.29, 0.585), 0.019, M['rust'], vertices=14))
    o.append(tube('ENG_exh_mid3', (0.12, -0.255, 0.665), (0.08, -0.295, 0.575), 0.019, M['rust'], vertices=14))
    o.append(tube('ENG_exh_mid4', (0.26, -0.255, 0.665), (0.10, -0.295, 0.575), 0.019, M['rust'], vertices=14))
    o.append(cyl('ENG_collector', 0.035, 0.11, (0.05, -0.30, 0.565), M['rust'],
                 rot=(0, RAD(90), 0), vertices=20))
    o.append(cyl('ENG_o2sensor', 0.011, 0.030, (0.05, -0.335, 0.585), M['steel'], vertices=12))
    shield = box('ENG_heatshield_hi', (0.46, 0.16, 0.014), (0.05, -0.245, 0.72), M['heat_shield'], bevel=0.002)
    shield.rotation_euler = (RAD(18), 0, 0); o.append(shield)
    shield2 = box('ENG_heatshield_lo', (0.30, 0.13, 0.012), (0.05, -0.335, 0.615), M['heat_shield'], bevel=0.002)
    shield2.rotation_euler = (RAD(28), 0, 0); o.append(shield2)
    for (xx, yy, zz) in ((-0.10, -0.22, 0.755), (0.18, -0.22, 0.755), (-0.08, -0.31, 0.66), (0.16, -0.31, 0.66)):
        o.append(tube(f'ENG_shieldpost_{xx}_{yy}', (xx, yy, zz), (xx, yy - 0.02, zz - 0.045), 0.004,
                      M['steel'], vertices=8))
    o.append(tube('ENG_downpipe', (0.05, -0.345, 0.555), (0.02, -0.52, 0.30), 0.028, M['rust'], vertices=18))
    o.append(ring('ENG_downpipe_flex', 0.029, 0.004, (0.04, -0.42, 0.455), M['steel'],
                  axis='X', major_segments=20, minor_segments=6))
    # transmission (bell + gearbox) + CONN bracket
    o.append(cyl('ENG_bell', 0.155, 0.10, (0.61, -0.02, 0.70), M['alu_dark'],
                 rot=(0, RAD(90), 0), vertices=32))
    o.append(cyl('ENG_bellring', 0.118, 0.03, (0.565, -0.02, 0.70), M['cast_dark'],
                 rot=(0, RAD(90), 0), vertices=28))
    o.append(box('ENG_gearbox', (0.10, 0.28, 0.24), (0.71, -0.02, 0.66), M['alu_dark'], bevel=0.004))
    o.append(box('ENG_shiftlink', (0.05, 0.16, 0.03), (0.70, 0.10, 0.805), M['steel'], bevel=0.001))
    o.append(box('ENG_conn_bracket', (0.030, 0.05, 0.012), (0.555, -0.15, 0.860), M['steel'], bevel=0.001))
    o.append(cyl('ENG_conn_socket', 0.014, 0.012, (0.555, -0.15, 0.854), M['bay_dark'], vertices=14))
    # wiring: cover-front harness + coil drops + injector rail + ground strap
    o.append(tube('ENG_harness', (-0.28, 0.135, 0.962), (0.30, 0.135, 0.962), 0.009, M['cable_black'], vertices=12))
    for x in WELL_X:
        if abs(x - 0.12) < 1e-6:
            continue
        o.append(tube(f'ENG_coildrop{x}', (x, 0.135, 0.962), (x, 0.112, 1.058), 0.0055, M['cable_black'], vertices=8))
    o.append(cyl('ENG_injrail', 0.012, 0.46, (0.03, 0.155, 0.90), M['alu'],
                 rot=(0, RAD(90), 0), vertices=14))
    for x in WELL_X:
        o.append(tube(f'ENG_injstub{x}', (x, 0.148, 0.90), (x, 0.138, 0.885), 0.007, M['alu_dark'], vertices=8))
    o.append(tube('ENG_groundstrap', (0.30, 0.13, 0.945), (0.37, 0.10, 0.905), 0.006, M['cable_black'], vertices=8))
    # oil filter + dipstick
    o.append(cyl('ENG_oilfilter', 0.036, 0.09, (0.10, 0.11, 0.60), M['filter_white'], vertices=24))
    o.append(tube('ENG_dipstick', (-0.24, -0.14, 0.84), (-0.24, -0.105, 0.945), 0.0045, M['steel'], vertices=8))
    o.append(cyl('ENG_dipcap', 0.010, 0.022, (-0.24, -0.100, 0.955), M['dip_yellow'], vertices=14))
    # engine mounts / torque rod to the right strut tower
    o.append(box('ENG_mount_l', (0.05, 0.18, 0.11), (-0.325, -0.02, 0.81), M['cast_dark'], bevel=0.003))
    o.append(tube('ENG_torquerod', (0.36, 0.10, 0.88), (0.50, -0.22, 0.98), 0.013, M['alu_dark'], vertices=12))
    o.append(box('ENG_torquerod_brk', (0.06, 0.08, 0.05), (0.37, 0.10, 0.885), M['cast_dark'], bevel=0.002))
    return o

# ----------------------------------------------------------------------------
# radiator_pack
# ----------------------------------------------------------------------------
def build_radiator():
    o = []
    o.append(box('BLK_RAD_core', (1.20, 0.035, 0.62), (0, 0.73, 0.73), M['bay_dark'], bevel=0.002))
    for i in range(16):
        o.append(box(f'RAD_fin{i}', (1.18, 0.008, 0.012), (0, 0.7125, 0.45 + i * 0.0375),
                     M['rubber_black'], bevel=0))
    for sx in (-1, 1):
        o.append(box(f'BLK_RAD_tank{sx}', (0.075, 0.06, 0.62), (sx * 0.6175, 0.73, 0.73),
                     M['vc_black'], bevel=0.003))
    o.append(cyl('RAD_fillneck', 0.025, 0.05, (0.6175, 0.73, 1.065), M['vc_black'], vertices=18))
    o.append(cyl('RAD_fillcap', 0.028, 0.014, (0.6175, 0.73, 1.096), M['alu_dark'], vertices=18))
    o.append(ring('BLK_RAD_shroud', 0.255, 0.022, (-0.22, 0.665, 0.72), M['vc_black'], axis='Y',
                  major_segments=36, minor_segments=10))
    o.append(cyl('RAD_fanhub', 0.06, 0.055, (-0.22, 0.668, 0.72), M['alu_dark'],
                 rot=(RAD(90), 0, 0), vertices=20))
    for k in range(6):
        a = RAD(k * 60)
        b = box(f'RAD_blade{k}', (0.055, 0.012, 0.155),
                (-0.22 + math.cos(a) * 0.14, 0.664, 0.72 + math.sin(a) * 0.14), M['vc_black'], bevel=0.001)
        b.rotation_euler = (0, 0, a + RAD(35))
        o.append(b)
    o.append(box('BLK_RAD_shroudplate', (0.56, 0.016, 0.54), (-0.22, 0.692, 0.72), M['vc_black'], bevel=0.002))
    # expansion tank (semi-transparent) + hose
    o.append(box('BLK_RAD_exptank', (0.13, 0.10, 0.21), (0.60, 0.68, 1.00), M['coolant_tank'], bevel=0.004))
    o.append(cyl('RAD_expcap', 0.026, 0.018, (0.60, 0.68, 1.112), M['vc_black'], vertices=18))
    o.append(box('RAD_explevel', (0.118, 0.004, 0.05), (0.60, 0.727, 1.02), M['ceramic'], bevel=0))
    o.append(tube('RAD_exphose', (0.60, 0.68, 0.897), (0.6175, 0.705, 0.80), 0.012, M['cable_black'], vertices=12))
    # upper support rod over the radiator
    # review#1 fix: rod moved (0.575,1.19) -> (0.665,1.115): the old position cut
    # the PLUGPORT/OILCAP/CONN sample sightlines (round-1 assertion evidence)
    for sx in (-1, 1):
        o.append(box(f'BLK_RAD_supbrk{sx}', (0.030, 0.05, 0.20), (sx * 0.63, 0.665, 1.0375), M['cast_dark'], bevel=0.002))
    o.append(cyl('BLK_RAD_surod', 0.011, 1.24, (0, 0.665, 1.115), M['cast_dark'],
                 rot=(0, RAD(90), 0), vertices=14))
    return o

# ----------------------------------------------------------------------------
# verification
# ----------------------------------------------------------------------------
def _obj_world_bbox(obj):
    cs = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))

def _seg_box_hit(p, d, tmax, lo, hi, tmin=1e-4):
    t0, t1 = tmin, tmax
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if p[i] < lo[i] or p[i] > hi[i]:
                return False
        else:
            a = (lo[i] - p[i]) / d[i]; b = (hi[i] - p[i]) / d[i]
            t0 = max(t0, min(a, b)); t1 = min(t1, max(a, b))
            if t0 > t1:
                return False
    return True

def _pt_box_dist(p, lo, hi):
    dx = max(lo.x - p.x, 0, p.x - hi.x)
    dy = max(lo.y - p.y, 0, p.y - hi.y)
    dz = max(lo.z - p.z, 0, p.z - hi.z)
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def verify_sightlines(cam_pos, samples, blocker_objs):
    """Official camera -> every interactive-object sample must clear every BLK_
    env part (segment truncated 2 cm before the sample). Also reports the min
    clearance from each object's sightline bundle to any blocker."""
    cam = Vector(cam_pos)
    bpy.context.view_layer.update()
    blocks = {o.name: _obj_world_bbox(o) for o in blocker_objs if o.type == 'MESH'}
    hits, tested, clear = [], 0, {}
    for name, pts in samples.items():
        best = 1e9
        for p in pts:
            p = Vector(p)
            d = p - cam; L = d.length; d /= L
            tested += 1
            for bname, (blo, bhi) in blocks.items():
                if _seg_box_hit(cam, d, L - 0.02, blo, bhi, tmin=0.05):
                    hits.append([name, bname, [round(v, 3) for v in p]])
                for k in range(1, 21):
                    best = min(best, _pt_box_dist(cam + d * (L * k / 20), blo, bhi))
        clear[name] = round(best, 4)
    out = {'camera_position_m': list(cam), 'blocker_parts_tested': len(blocks),
           'sightlines_tested': tested, 'min_clearance_m': clear,
           'occlusion_hits': hits}
    print(json.dumps({'sightline_verification': out}, ensure_ascii=False), flush=True)
    assert not hits, f'env geometry occludes interactive objects: {hits}'

def _screen_basis(cam_pos, look):
    fwd = (Vector(look) - Vector(cam_pos)).normalized()
    zloc = -fwd
    yup = Vector((0, 0, 1))
    yloc = (yup - yup.dot(zloc) * zloc).normalized()
    xloc = yloc.cross(zloc).normalized()
    return fwd, xloc, yloc

def _proj_range(lo, hi, cam_pos, x, y):
    us, vs = [], []
    for cx in (lo.x, hi.x):
        for cy in (lo.y, hi.y):
            for cz in (lo.z, hi.z):
                d = Vector((cx, cy, cz)) - Vector(cam_pos)
                us.append(d.dot(x)); vs.append(d.dot(y))
    return min(us), max(us), min(vs), max(vs)

def fit_frame(cam_pos, look_seed, bbox_list, res, margin=0.07, iters=8):
    look = Vector(look_seed)
    aspect = res[0] / res[1]
    for _ in range(iters):
        _, x, y = _screen_basis(cam_pos, look)
        us, vs = [], []
        for lo, hi in bbox_list:
            u0, u1, v0, v1 = _proj_range(lo, hi, cam_pos, x, y)
            us += [u0, u1]; vs += [v0, v1]
        look = look + x * ((min(us) + max(us)) / 2) + y * ((min(vs) + max(vs)) / 2)
    _, x, y = _screen_basis(cam_pos, look)
    us, vs = [], []
    for lo, hi in bbox_list:
        u0, u1, v0, v1 = _proj_range(lo, hi, cam_pos, x, y)
        us += [u0, u1]; vs += [v0, v1]
    ortho = max((max(us) - min(us)) / (1 - 2 * margin), (max(vs) - min(vs)) * aspect / (1 - 2 * margin))
    return look, ortho

def verify_frame(cam_pos, look, ortho, items, res, margin=0.07):
    _, x, y = _screen_basis(cam_pos, look)
    half_u, half_v = ortho / 2, ortho / 2 * res[1] / res[0]
    out = {}
    for name, (lo, hi) in items.items():
        u0, u1, v0, v1 = _proj_range(lo, hi, cam_pos, x, y)
        px0 = int(round((u0 + half_u) / ortho * res[0]))
        px1 = int(round((u1 + half_u) / ortho * res[0]))
        py0 = int(round((half_v - v1) / (2 * half_v) * res[1]))
        py1 = int(round((half_v - v0) / (2 * half_v) * res[1]))
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

def add_label(text, pos, cam_pos, look):
    bpy.ops.object.text_add(location=Vector(pos))
    t = bpy.context.object; t.name = 'LBL_' + text
    d = t.data
    d.body = text; d.size = 0.062; d.align_x = 'CENTER'; d.align_y = 'CENTER'; d.extrude = 0.0012
    t.rotation_euler = (Vector(cam_pos) - Vector(look)).to_track_quat('Z', 'Y').to_euler()
    d.materials.append(M['label_prev'])
    return t

def _label_text_points(t, nu=7, nv=3):
    """21-point grid on a label's camera-facing text surface (world coords)."""
    bpy.context.view_layer.update()
    xs = [v[0] for v in t.bound_box]; ys = [v[1] for v in t.bound_box]
    z_face = max(v[2] for v in t.bound_box)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [t.matrix_world @ Vector((x0 + (x1 - x0) * i / (nu - 1),
                                     y0 + (y1 - y0) * j / (nv - 1), z_face))
            for i in range(nu) for j in range(nv)]

def verify_label_sightlines(cam_pos, look, label_objs):
    """Line-of-sight occlusion probe for preview labels (r2 P1-1 method).

    The r1 probe intersected the 21-point text grid against mesh AABBs, which
    only detects 3D intersection: the mis-baked hinge column stood IN FRONT of
    the PLUGPORT text plane at a different depth and passed unnoticed. Here we
    cast ortho rays parallel to the kit-camera view axis: for each text point,
    start on the camera plane and intersect triangle-exact BVH trees of every
    scene mesh (env + props + interactive objects); any hit nearer than the
    point itself is line-of-sight occlusion."""
    cam = Vector(cam_pos)
    fwd, xloc, yloc = _screen_basis(cam_pos, look)
    lab_names = {t.name for t in label_objs}
    bpy.context.view_layer.update()
    trees = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name in lab_names:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        trees.append((o.name, BVHTree.FromBMesh(bm)))
        bm.free()
    per, occluders = {}, []
    for t in label_objs:
        pts = _label_text_points(t)
        n_hit, meshes = 0, set()
        for p in pts:
            d = p - cam
            u, v, tp = d.dot(xloc), d.dot(yloc), d.dot(fwd)
            origin = cam + xloc * u + yloc * v
            for name, tree in trees:
                loc, _n, _idx, dist = tree.ray_cast(origin, fwd)
                if loc is not None and dist < tp - 0.002:
                    n_hit += 1; meshes.add(name)
        per[t.name] = {'rays': len(pts), 'occluded_rays': n_hit, 'hit_meshes': sorted(meshes)}
        occluders += [(t.name, m) for m in sorted(meshes)]
    print(json.dumps({'label_sightline_verification': {
        'method': 'ortho ray-cast (triangle-exact BVH), 21 pts per label text face',
        'camera_position_m': list(cam), 'look_at_m': [round(c, 4) for c in Vector(look)],
        'meshes_tested': len(trees), 'labels': per}}, ensure_ascii=False), flush=True)
    assert not occluders, f'preview label occluded along the camera sightline: {occluders}'

def fit_persp(cam_pos, look_seed, bbox_list, res, margin=0.06, iters=8):
    """Centre a PERSPECTIVE frame on the bboxes and solve the lens (36 mm sensor,
    AUTO fit -> horizontal). Returns (look, lens_mm, worst_margin_pct)."""
    look = Vector(look_seed)
    aspect = res[0] / res[1]
    for _ in range(iters):
        _, x, y = _screen_basis(cam_pos, look)
        us, vs = [], []
        for lo, hi in bbox_list:
            u0, u1, v0, v1 = _proj_range(lo, hi, cam_pos, x, y)
            us += [u0, u1]; vs += [v0, v1]
        look = look + x * ((min(us) + max(us)) / 2) + y * ((min(vs) + max(vs)) / 2)
    fwd, x, y = _screen_basis(cam_pos, look)
    max_tan = 0.0
    for lo, hi in bbox_list:
        for cx in (lo.x, hi.x):
            for cy in (lo.y, hi.y):
                for cz in (lo.z, hi.z):
                    d = Vector((cx, cy, cz)) - Vector(cam_pos)
                    t = d.dot(fwd)
                    max_tan = max(max_tan,
                                  abs(d.dot(x)) / t / (1 - 2 * margin),
                                  abs(d.dot(y)) / t * aspect / (1 - 2 * margin))
    lens = 18.0 / max_tan
    tan_hx = 18.0 / lens; tan_hy = tan_hx / aspect
    worst = 100.0
    for lo, hi in bbox_list:
        for cx in (lo.x, hi.x):
            for cy in (lo.y, hi.y):
                for cz in (lo.z, hi.z):
                    d = Vector((cx, cy, cz)) - Vector(cam_pos)
                    t = d.dot(fwd)
                    worst = min(worst,
                                (1 - abs(d.dot(x)) / t / tan_hx) * 100,
                                (1 - abs(d.dot(y)) / t / tan_hy) * 100)
    return look, round(lens, 1), round(worst, 1)

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    KIT.mkdir(parents=True, exist_ok=True)
    clear_scene()
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
    sc.cycles.use_denoising = True
    make_materials()

    built_bbox = {}

    def build_and_export(name, fn, out_path):
        objs = fn()
        bbox = _bbox_frame(objs)
        tris = _tri(objs)
        path = export_glb(objs, out_path)
        print(json.dumps({'exported': {'part': name, 'glb': str(path.relative_to(ROOT)),
                                       'mesh_tris': tris, 'bytes': path.stat().st_size,
                                       'local_bbox': [[round(v, 4) for v in bbox[0]],
                                                      [round(v, 4) for v in bbox[1]]]}}), flush=True)
        built_bbox[name] = bbox
        if name in LAYOUT['objects']:
            assert tris < 150000, f'{name} over triangle budget'
        _wipe_meshes()
        return path

    paths = {}
    for oid in LAYOUT['objects']:
        paths[oid] = build_and_export(oid, globals()[f'build_{oid.lower()}'], KIT / f'{oid}.glb')
    paths['shell'] = build_and_export('shell', build_shell, ENV / 'engine_bay_shell.glb')
    paths['engine'] = build_and_export('engine', build_engine, ENV / 'engine_assembly.glb')
    paths['radiator'] = build_and_export('radiator', build_radiator, ENV / 'engine_bay_radiator.glb')

    # ---------------- full-scene composition ----------------
    clear_scene()
    M['label_prev'] = flat('eb_label_prev', (0.96, 0.97, 0.99, 1.0), roughness=0.5,
                           emissive=(1, 1, 1, 1.0), emission_strength=0.35)
    world_bg((0.30, 0.33, 0.38, 1.0), strength=0.5)
    parents, children = {}, {}
    for oid, spec in LAYOUT['objects'].items():
        objs = import_glb(paths[oid])
        pos, wxyz = spec['pose']
        parents[oid] = parent_to('HC_' + oid, objs, location=pos, wxyz=wxyz)
        parents[oid]['holocue_object_id'] = oid
        children[oid] = objs
    for pid, spec in LAYOUT['env'].items():
        objs = import_glb(ROOT / spec['asset'])
        parents[pid] = parent_to('HC_ENV_' + pid, objs, location=spec['position'])
        parents[pid]['holocue_prop_id'] = pid
        children[pid] = objs

    # round-trip: re-imported world bbox must equal build-time local bbox + pose
    rt = {}
    for oid, spec in LAYOUT['objects'].items():
        lo, hi = _bbox_frame(children[oid])
        pose = Vector(spec['pose'][0])
        dlo = max(abs(lo[i] - (built_bbox[oid][0][i] + pose[i])) for i in range(3))
        dhi = max(abs(hi[i] - (built_bbox[oid][1][i] + pose[i])) for i in range(3))
        rt[oid] = round(max(dlo, dhi), 6)
    print(json.dumps({'pose_roundtrip_max_err_m': rt, 'within_1mm': all(v < 1e-3 for v in rt.values())}),
          flush=True)
    assert all(v < 1e-3 for v in rt.values()), 'interactive GLB round-trip drift >= 1mm'

    # insertion anchor + mouth coincidence
    pp = LAYOUT['objects']['PLUGPORT']
    anchor_w = Vector(pp['pose'][0]) + Vector(pp['anchors']['insertion'])
    pp_lo, pp_hi = _bbox_frame(children['PLUGPORT'])
    print(json.dumps({'plugport_insertion_anchor_world_m': [round(v, 4) for v in anchor_w],
                      'collar_top_world_z': round(pp_hi.z, 4),
                      'anchor_vs_mouth_err_m': round(abs(anchor_w.z - pp_hi.z), 4)}), flush=True)
    assert abs(anchor_w.z - pp_hi.z) < 0.004, 'insertion anchor not at the well mouth'

    # CONN pin face direction (pins must face -X)
    pins = [o for o in children['CONN'] if 'pin' in o.name.lower()]
    shellc = [o for o in children['CONN'] if 'shell' in o.name.lower()][0]
    plo, phi = _bbox_frame(pins)
    pc = (plo + phi) / 2
    sc_lo, sc_hi = _bbox_frame([shellc])
    scc = (sc_lo + sc_hi) / 2
    ndir = (pc - scc).normalized()
    print(json.dumps({'conn_pin_face_normal': [round(v, 4) for v in ndir],
                      'x_component': round(ndir.x, 4)}), flush=True)
    assert ndir.x < -0.9, 'CONN pin face does not point -X'

    # depth layering evidence (docs/10 criterion 1)
    cam = Vector(LAYOUT['camera_position_m'])
    depths = {oid: round((Vector(s['pose'][0]) - cam).length, 3) for oid, s in LAYOUT['objects'].items()}
    print(json.dumps({'camera_to_object_distance_m': depths,
                      'focus_span_m': round(max(depths.values()) - min(depths.values()), 3)}), flush=True)

    # sightline samples (grids shrunk toward each object's center)
    def grid(lo, hi, k=0.35, nu=5, nv=3, nw=5):
        c = (lo + hi) / 2
        pts = []
        for i in range(nu):
            for j in range(nv):
                for k2 in range(nw):
                    pts.append(c + Vector(((i / (nu - 1) - 0.5) * 2 * k * (hi.x - lo.x),
                                           (j / (nv - 1) - 0.5) * 2 * k * (hi.y - lo.y),
                                           (k2 / (nw - 1) - 0.5) * 2 * k * (hi.z - lo.z))))
        return pts
    samples = {oid: grid(*_bbox_frame(children[oid])) for oid in LAYOUT['objects']}
    pp_pos = Vector(pp['pose'][0])
    samples['PLUGPORT'] = [pp_pos + Vector((0.022 * math.cos(RAD(a)), 0.022 * math.sin(RAD(a)), 0.028))
                           for a in range(0, 360, 40)] + [pp_pos + Vector((0, 0, 0.028))]
    blockers = [o for part in ('shell', 'engine', 'radiator') for o in children[part]
                if o.type == 'MESH' and 'BLK' in o.name]
    verify_sightlines(LAYOUT['camera_position_m'], samples, blockers)

    # ---------------- props ----------------
    env_json = []
    for pid, spec in LAYOUT['env'].items():
        env_json.append({'prop_id': pid, 'label': spec['label'], 'asset': spec['asset'],
                         'pose': {'position_m': list(spec['position']), 'wxyz': [1, 0, 0, 0]},
                         'scale_m': [1.0, 1.0, 1.0]})
    prop_tops = {}

    def place_prop3(pid, spec, base_z=None):
        objs = import_glb(ENV / spec['glb'])
        q = (Quaternion((0, 0, 1), RAD(spec.get('rz', 0.0)))
             @ Quaternion((1, 0, 0), RAD(spec.get('rx', 0.0)))
             @ Quaternion((0, 1, 0), RAD(spec.get('ry', 0.0)))).normalized()
        p = parent_to('HC_ENV_' + pid, objs, location=(0, 0, 0), wxyz=q)
        s = spec['scale']
        p.scale = (s, s, s)
        bpy.context.view_layer.update()
        lo, hi = _bbox_frame(objs)
        loc = Vector((0, 0, 0))
        loc.x = spec['center'][0] - (lo.x + hi.x) / 2
        loc.y = spec['center'][1] - (lo.y + hi.y) / 2
        if 'center_z' in spec:
            loc.z = spec['center_z'] - (lo.z + hi.z) / 2
        else:
            bz = base_z if base_z is not None else spec.get('base_z', 0.0)
            loc.z = bz - lo.z
        p.location = loc
        bpy.context.view_layer.update()
        parents[pid] = p; children[pid] = objs
        env_json.append({'prop_id': pid, 'label': spec['label'],
                         'asset': f"assets/meshes/env/{spec['glb']}",
                         'pose': {'position_m': [round(v, 4) for v in loc],
                                  'wxyz': [round(v, 6) for v in (q.w, q.x, q.y, q.z)]},
                         'scale_m': [s, s, s]})
        return p

    for pid, spec in LAYOUT['props'].items():
        # two-stage props ('on') and stacked dressing ('stack') are placed below
        if 'on' in spec or spec.get('stack'):
            continue
        place_prop3(pid, spec)
        prop_tops[pid] = _bbox_frame(children[pid])[1].z
    for pid, spec in LAYOUT['props'].items():
        if 'on' not in spec:
            continue
        base = prop_tops[spec['on']] + 0.002
        place_prop3(pid, spec, base_z=base)

    # stacked tyres/rim: b and rim sit on the first tyre
    tyre_h = 0.165
    for pid, dz in (('old_tyre_b', tyre_h), ('rusted_wheel_rim_01', 2 * tyre_h)):
        spec = LAYOUT['props'][pid]
        place_prop3(pid, spec, base_z=dz)

    # ---------------- lights + labels ----------------
    light_rig(Vector((0.0, 0.10, 1.00)), extent=2.8, energy=1.55)
    # Label poses. r1 P1 fixes: TENSIONER (0.70,0.48,1.02)->(0.48,0.46,1.14)
    # (was occluded by expansion tank / support rod / right fender lip), CONN
    # (0.76,-0.30,0.99)->(0.64,-0.20,1.14) (sat behind the right fender inner
    # panel + strut tower). r2 P1-1: PLUGPORT (0.38,-0.04,1.12)->(0.13,-0.08,1.22).
    # The r1 acceptance probe ("21-point text grid vs every mesh AABB segment")
    # only detected 3D intersection: the mis-baked SH_hood_hinge1 column (build
    # bug fixed in _rot_world) stood IN FRONT of the PLUGPORT text plane at a
    # different depth, killing the G/P strokes (r2 review: 21 px of zero-bright
    # gap between them) while the AABB probe read zero blockers. Labels are now
    # verified every build by verify_label_sightlines(): ortho ray casting from
    # the kit camera through 21 points per text face vs triangle-exact BVH of
    # all scene meshes (JSON evidence printed to the log). The new PLUGPORT pose
    # comes from the r2 candidate scan (runs/scene_v2/probe_label_sight_r2.log):
    # 21/21 rays clear even with the stray column still present, 0.30 m offset
    # to the well, >=75 px / >=64 px screen gap to other labels / objects, and
    # outside all four detail-shot frustums.
    labels = {'CLAMP': (-0.24, 0.50, 1.12), 'PLUG': (-0.05, 0.47, 1.14),
              'PLUGPORT': (0.13, -0.08, 1.22), 'OILCAP': (-0.46, -0.04, 1.12),
              'TENSIONER': (0.48, 0.46, 1.14), 'CONN': (0.64, -0.20, 1.14)}
    lab_objs = [add_label(t, p, LAYOUT['camera_position_m'], LAYOUT['camera_look_at_m'])
                for t, p in labels.items()]

    # ---------------- kit preview (official camera, ortho, framed) ----------------
    # review#2/#3 fix: fit the WORK AREA (bay lower structure + engine + radiator
    # + labels). The open hood (top z 2.51) is excluded: including it blew the
    # ortho to 4.55 and recentered the axis nearly horizontal, so the standing
    # hood panel dominated the frame and the engine shrank; the hood now crops
    # naturally at the frame top like a real over-the-fender service photo.
    RES = (1600, 1120)
    bay_lower = [c for c in children['shell']
                 if not any(k in c.name for k in ('garage', 'hood', 'strut'))]
    fit_items = {'bay_lower': _bbox_frame(bay_lower),
                 'engine': _bbox_frame(children['engine']),
                 'radiator': _bbox_frame(children['radiator']),
                 'labels': _bbox_frame(lab_objs)}
    look_fit, ortho_fit = fit_frame(Vector(LAYOUT['camera_position_m']),
                                    Vector(LAYOUT['camera_look_at_m']),
                                    list(fit_items.values()), RES)
    # r2 P1-2: kit previews now carry the CONTRACT fill lights (same values as
    # render_hints below), aimed at the fitted look point exactly like the
    # official renderer (scripts/build_blender_scene.py). Previews are
    # noticeably brighter than the r1/r2-review evidence -- expected.
    for x, y, z, power, size in FILL_LIGHTS:
        bpy.ops.object.light_add(type='AREA', location=(x, y, z))
        fl = bpy.context.object
        fl.data.energy = power; fl.data.shape = 'DISK'; fl.data.size = size
        fl.rotation_euler = (Vector(look_fit) - Vector((x, y, z))).to_track_quat('-Z', 'Y').to_euler()
    print(json.dumps({'fill_lights': {'entries': FILL_LIGHTS,
                                      'aim_m': [round(v, 4) for v in look_fit]}}), flush=True)
    # r2 P1-1 acceptance probe: all six labels must be clear along the camera
    # sightline (runs after fit so it uses the final kit camera).
    verify_label_sightlines(LAYOUT['camera_position_m'], tuple(look_fit), lab_objs)
    render_preview('engine_bay_kit_preview.png', LAYOUT['camera_position_m'],
                   tuple(look_fit), ortho=ortho_fit, res=RES, samples=64)
    verify_frame(LAYOUT['camera_position_m'], tuple(look_fit), ortho_fit, fit_items, RES)

    # ---------------- detail previews (perspective) ----------------
    render_preview('engine_bay_clamp.png', (-0.50, 0.86, 1.30), (-0.18, 0.36, 1.01),
                   persp_fov=55, res=RES, samples=64)
    render_preview('engine_bay_plugport.png', (-0.12, 0.78, 1.44), (0.12, 0.12, 0.99),
                   persp_fov=50, res=RES, samples=64)
    render_preview('engine_bay_pulleys.png', (1.05, 0.74, 1.32), (0.47, 0.08, 0.74),
                   persp_fov=45, res=RES, samples=64)
    render_preview('engine_bay_conn.png', (0.16, -0.60, 1.28), (0.54, -0.15, 0.89),
                   persp_fov=45, res=RES, samples=64)

    # wide workshop context shot: every prop + garage, for dressing QA evidence
    wide_items = [_bbox_frame(children[k]) for k in ('shell', 'engine', 'radiator')]
    wide_items += [_bbox_frame(children[p]) for p in LAYOUT['props']]
    look_wide, ortho_wide = fit_frame(Vector(LAYOUT['camera_position_m']),
                                      Vector((0.0, -0.3, 0.9)), wide_items, RES, margin=0.03)
    render_preview('engine_bay_workshop_wide.png', LAYOUT['camera_position_m'],
                   tuple(look_wide), ortho=ortho_wide, res=RES, samples=48)

    # r2 P2 (r1/r2 P2-3): auxiliary view proving the opened hood is modelled in
    # full -- the kit preview intentionally crops the hood top (framing note
    # above). Front-high PERSPECTIVE from inside the garage (below the ceiling
    # beams, so no ceiling occludes the sightlines); lens auto-fitted so hood +
    # engine + radiator all stay in frame with margin (asserted like the kit).
    hood_parts = [c for c in children['shell'] if 'hood' in c.name]
    hood_items = {'hood': _bbox_frame(hood_parts),
                  'engine': _bbox_frame(children['engine']),
                  'radiator': _bbox_frame(children['radiator'])}
    HOOD_CAM = (-1.00, 2.35, 2.68)
    look_hood, lens_hood, hood_margin = fit_persp(Vector(HOOD_CAM), Vector((0.0, -0.20, 1.15)),
                                                  list(hood_items.values()), RES, margin=0.06)
    print(json.dumps({'hood_view_verification': {
        'camera_position_m': list(HOOD_CAM), 'look_at_m': [round(v, 4) for v in look_hood],
        'lens_mm': lens_hood, 'worst_margin_pct': hood_margin}}, ensure_ascii=False), flush=True)
    assert hood_margin >= 5.5, f'hood view framing margin too small: {hood_margin}'
    render_preview('engine_bay_hood_view.png', HOOD_CAM, tuple(look_hood),
                   persp_fov=lens_hood, res=RES, samples=48)

    # ---------------- scene JSON ----------------
    def obj_entry(oid):
        s = LAYOUT['objects'][oid]
        pos, wxyz = s['pose']
        return {'object_id': oid, 'label': s['label'], 'asset': f'assets/meshes/engine_bay/{oid}.glb',
                'pose': {'position_m': [round(v, 4) for v in pos], 'wxyz': list(wxyz)},
                'color': list(s['color']), 'capabilities': s['capabilities'],
                'anchors': {k: list(v) for k, v in s['anchors'].items()},
                'description': s['description']}

    spec_out = {
        'schema_version': '1.0', 'scene_id': LAYOUT['scene_id'], 'title': LAYOUT['title'],
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': [obj_entry(o) for o in ('CLAMP', 'PLUG', 'PLUGPORT', 'OILCAP', 'TENSIONER', 'CONN')],
        'initial_instruction': LAYOUT['initial_instruction'],
        'camera_position_m': list(LAYOUT['camera_position_m']),
        'camera_look_at_m': [round(v, 4) for v in look_fit],
        'environment': env_json,
        'render_hints': {'ortho_scale_m': round(ortho_fit, 3), 'grid_extent_m': 2.5,
                         'cue_scale': 1.0, 'label_offset_m': 0.12, 'fit_camera': True,
                         # see FILL_LIGHTS above (r2 P1-2): in-garage bay fill,
                         # because the k-scaled generic rig sits above the
                         # ceiling shell and starves the bay (official render
                         # mean luma 18.6-19.2 / dead-black<8 16.7% pre-fill vs
                         # 140.6 / 0.01% with them; evidence
                         # runs/engine_bay_blender.png).
                         # [x, y, z, power_W, disk_size_m]
                         'fill_lights': [list(l) for l in FILL_LIGHTS]},
    }
    write_scene_json(LAYOUT['scene_id'], spec_out)
    # post-write recheck (JSON is rewritten by this script; fit_camera must survive)
    reread = json.loads((ROOT / 'scenes/engine_bay/scene.json').read_text(encoding='utf-8'))
    assert reread['render_hints']['fit_camera'] is True
    assert reread['initial_instruction'] == LAYOUT['initial_instruction']
    print(json.dumps({'final_camera': {'position_m': list(LAYOUT['camera_position_m']),
                                       'look_at_m': [round(v, 4) for v in look_fit],
                                       'ortho_scale_m': round(ortho_fit, 3)},
                      'fit_camera_recheck': True,
                      'environment_entries': len(env_json)}), flush=True)

if __name__ == '__main__':
    main()
