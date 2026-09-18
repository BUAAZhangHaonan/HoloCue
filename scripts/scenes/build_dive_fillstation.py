"""Kit builder for `dive_fillstation` (潜水气瓶充装前核验与接通, design v2).

Run (CPU, resource-guarded):
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
    /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
    --python scripts/scenes/build_dive_fillstation.py

Outputs:
  scenes/dive_fillstation/meshes/{QRC,VALVE,BOTTLE3,BOTTLE1,BOTTLE2,STEM,GAUGES}.glb
  scenes/dive_fillstation/meshes/env/dive_fillstation_{filling_station,manifold_bank,line3_hose,compressor,room}.glb
  scenes/dive_fillstation/scene.json  (as-built; design from scenes/dive_fillstation/docs/design.md)

Reviewed design (v2): camera [0.30,-1.05,1.30] -> look [0.05,0.60,1.00]; layers
QRC/VALVE ~1.11 m near-low (hose coupler onto the bottle-3 valve outlet, anchor
at the outlet mouth), BOTTLE3 shoulder stamp ~1.12 m (same near layer, its own
step), STEM 1.57 m mid (manifold valve spindle, closed = lever down), GAUGES
2.28 m far wall (continuous regulated watch). The stamp band on the shoulder's
back side is the inspect_back radial face (normal horizontal, local Z vertical
along the bottle axis).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
from common import _projected_size
from mathutils import Vector, Quaternion, Euler
import math

SCENE_ID = 'dive_fillstation'
KIT = scene_kit(SCENE_ID)
KIT_MESH = KIT / 'meshes'
SCENE_ENV_DIR = scene_env(SCENE_ID)

CAM = (0.30, -1.05, 1.30)
LOOK = (0.05, 0.60, 1.00)

LAYOUT = {
    'title': '潜水气瓶充装前核验与接通',
    'initial_instruction': ('把充装软管接头 QRC 接到 3 号气瓶瓶阀 VALVE 的出口上,'
                            '接好后核对 BOTTLE3 瓶肩的检验钢印在不在有效期内,'
                            '确认无误再把汇流排 3 号路阀杆 STEM 逆时针开 90 度,'
                            '压力表组 GAUGES 全程盯着别超压。'),
    'objects': {
        'QRC': {'pose': ([0.50, -0.10, 0.85], (1, 0, 0, 0)), 'label': '充装软管接头',
                'color': (185, 190, 195), 'capabilities': ['point', 'insert'],
                'anchors': {}, 'description': '3 号路固定软管末端的快插接头,套口即局部原点'},
        'VALVE': {'pose': ([0.25, -0.05, 0.63], (1, 0, 0, 0)), 'label': '3 号瓶阀',
                  'color': (120, 125, 135), 'capabilities': ['point'],
                  'anchors': {'insertion': [0, 0, 0]},
                  'description': '瓶阀出口朝充装员,带单向阀;出口局部原点即插接终点'},
        'BOTTLE3': {'pose': ([0.25, -0.05, 0.26], (1, 0, 0, 0)), 'label': '3 号气瓶',
                    'color': (230, 180, 40), 'capabilities': ['point', 'inspect_back'],
                    'anchors': {},
                    'description': '瓶肩环带打检验钢印与编号;站立位局部 Z 沿瓶轴(竖直),钢印面法线水平,垂直于局部 Z,为径向面'},
        'BOTTLE1': {'pose': ([-0.50, -0.12, 0.26], (1, 0, 0, 0)), 'label': '1 号气瓶',
                    'color': (230, 180, 40), 'capabilities': ['point', 'inspect_back'],
                    'anchors': {}, 'description': '消歧用,同型;瓶肩钢印可查'},
        'BOTTLE2': {'pose': ([-0.12, -0.10, 0.26], (1, 0, 0, 0)), 'label': '2 号气瓶',
                    'color': (230, 180, 40), 'capabilities': ['point', 'inspect_back'],
                    'anchors': {}, 'description': '消歧用,同型;瓶肩钢印可查'},
        'STEM': {'pose': ([0.30, 0.55, 1.20], (0.7071, 0.7071, 0.0, 0.0)), 'label': '3 号路阀杆',
                 'color': (200, 60, 50), 'capabilities': ['point', 'rotate'],
                 'anchors': {},
                 'description': '汇流排 3 号路阀杆,手柄垂直向下为关,逆时针 90 度全开'},
        'GAUGES': {'pose': ([0.10, 1.30, 1.50], (1, 0, 0, 0)), 'label': '压力表组',
                   'color': (240, 240, 240), 'capabilities': ['point', 'wait'],
                   'anchors': {}, 'description': '多路缸压指示,超压区红刻度(读数为脚本时间线)'},
    },
    'depth_rows': {
        'QRC/VALVE(接管)': ([0.25, -0.05, 0.63], 1.11),
        'BOTTLE3(钢印核对)': ([0.25, -0.05, 0.50], 1.12),
        'STEM(开阀)': ([0.30, 0.55, 1.20], 1.57),
        'GAUGES(盯压)': ([0.10, 1.30, 1.50], 2.28),
    },
}

# BOTTLE3 inspect_back evidence (local frame, identity pose): the test-stamp
# plate sits on the shoulder's back side at local (0, +0.088, 0.235), normal +y.
BACK_INFO = {'BOTTLE3': {'center_local': (0.0, 0.09, 0.235), 'normal_local': (0.0, 1.0, 0.0)}}

# QRC seated at the VALVE outlet anchor: its socket mouth (local origin) lands
# exactly on the valve mouth, sleeve extending back toward the operator (-y).
QRC_SEATED = (0.25, -0.05, 0.63)

M_STEEL = flat('dive painted steel', (0.17, 0.20, 0.23, 1.0), 0.72, 0.25)
M_STEEL2 = flat('dive brushed steel', (0.40, 0.44, 0.47, 1.0), 0.82, 0.21)
M_DARK = flat('dive rubber black', (0.028, 0.035, 0.042, 1.0), 0.05, 0.62)
M_YELLOW = flat('dive bottle yellow', (0.87, 0.71, 0.10, 1.0), 0.10, 0.35)
M_RED = flat('dive valve red', (0.72, 0.04, 0.03, 1.0), 0.15, 0.3, (0.5, 0.02, 0.01, 1.0))
M_WHITE = flat('dive gauge white', (0.90, 0.90, 0.88, 1.0), 0.05, 0.35)
M_BLUE = flat('dive panel blue', (0.05, 0.23, 0.45, 1.0), 0.10, 0.3)
M_GLASS = flat('dive glass', (0.25, 0.45, 0.5, 1.0), 0.05, 0.1)


def cylL(name, loc, radius, depth, mat, rot=(0, 0, 0), vertices=48):
    """Location-first cylinder wrapper over common.cyl (radius, depth, location)."""
    return cyl(name, radius, depth, loc, mat, rot=rot, vertices=vertices)


def torusL(name, loc, major, minor, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=48, minor_segments=12,
                                     location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    return o


def txt(name, body, loc, size=0.04, mat=M_WHITE, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.align_x = 'CENTER'
    cu.size = size
    cu.extrude = 0.004
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = Euler(rot, 'XYZ')
    o.data.materials.append(mat)
    return o


def pipe(n, a, b, radius, mat):
    a, b = Vector(a), Vector(b)
    d = b - a
    o = cylL(n, (a + b) / 2, radius, d.length, mat)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    return o


def build_bottle(number):
    """Standard scuba cylinder, origin at mid-height; stamp plate on the back
    (+y) shoulder side, white number plate on the front (-y)."""
    objs = [cylL('body', (0, 0, 0), 0.075, 0.52, M_YELLOW),
            torusL('boot', (0, 0, -0.255), 0.077, 0.012, M_DARK, rot=(math.pi / 2, 0, 0)),
            torusL('neckring', (0, 0, 0.265), 0.05, 0.008, M_STEEL2, rot=(math.pi / 2, 0, 0))]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(0, 0, 0.28))
    sh = bpy.context.object
    sh.name = 'shoulder'
    sh.scale = (0.075, 0.075, 0.095)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    sh.data.materials.append(M_YELLOW)
    objs.append(sh)
    objs.append(cylL('neck', (0, 0, 0.385), 0.030, 0.10, M_STEEL2))
    # back-side test stamp plate (the inspect_back radial face) + front number
    objs.append(box('stamp', (0.046, 0.006, 0.034), (0, 0.0755, 0.235), M_STEEL2, bevel=0.001))
    objs.append(box('numplate', (0.048, 0.005, 0.05), (0, -0.076, 0.19), M_WHITE, bevel=0))
    objs.append(txt(f'num{number}', str(number), (0, -0.0815, 0.19), 0.05, M_DARK,
                    rot=(math.pi / 2, 0, 0)))
    objs.append(txt(f'stamp{number}', f'T{number} 2027', (0, 0.081, 0.235), 0.020, M_WHITE,
                    rot=(math.pi / 2, 0, 0)))
    return objs


def build_qrc():
    """Quick-release coupler; local origin at the socket mouth (-y face), the
    sleeve extends +y toward the hose."""
    return [cylL('sleeve', (0, 0.06, 0), 0.038, 0.13, M_STEEL2, rot=(math.pi / 2, 0, 0)),
            cylL('collar', (0, 0.015, 0), 0.05, 0.03, M_BLUE, rot=(math.pi / 2, 0, 0)),
            torusL('capring', (0, -0.008, 0), 0.040, 0.006, M_RED, rot=(0, 0, math.pi / 2)),
            cylL('tail', (0, 0.145, 0), 0.024, 0.05, M_DARK, rot=(math.pi / 2, 0, 0)),
            box('latch', (0.016, 0.05, 0.022), (0.032, 0.02, 0.0), M_RED, bevel=0.002)]


def build_valve():
    """K-valve on the bottle top; local origin at the outlet mouth (-y), the
    body rises +z onto the bottle neck."""
    return [cylL('outlet', (0, -0.028, 0), 0.021, 0.055, M_STEEL2, rot=(math.pi / 2, 0, 0)),
            cylL('body', (0, 0.01, 0.055), 0.042, 0.11, M_STEEL2),
            cylL('seat', (0, 0.01, 0.115), 0.030, 0.03, M_DARK),
            torusL('handwheel', (0.052, 0.01, 0.055), 0.042, 0.008, M_RED, rot=(0, math.pi / 2, 0)),
            cylL('burst', (0, -0.01, 0.09), 0.012, 0.02, M_DARK, rot=(math.pi / 2, 0, 0))]


def build_stem():
    """Manifold line-3 valve: spindle along local +z (toward the operator after
    the pose rotation), handwheel at the end, lever pointing local -y (= world
    down) in the closed state."""
    return [cylL('stem', (0, 0, 0.10), 0.018, 0.20, M_STEEL2),
            cylL('wheel', (0, 0, 0.225), 0.062, 0.024, M_RED),
            cylL('hub', (0, 0, 0.225), 0.018, 0.05, M_STEEL2),
            box('lever', (0.02, 0.13, 0.02), (0, -0.062, 0.222), M_RED, bevel=0.002)]


def build_gauges():
    """Wall board with three dial gauges (needle + red overpressure zone)."""
    objs = [box('board', (1.00, 0.06, 0.55), (0, 0.01, 0), M_STEEL, bevel=0.004)]
    for i, x in enumerate((-0.30, 0.0, 0.30)):
        objs += [cylL(f'rim{i}', (x, -0.035, 0.03), 0.165, 0.035, M_STEEL2, rot=(math.pi / 2, 0, 0)),
                 cylL(f'face{i}', (x, -0.054, 0.03), 0.148, 0.008, M_WHITE, rot=(math.pi / 2, 0, 0), vertices=64)]
        objs.append(box(f'needle{i}', (0.006, 0.005, 0.115), (x + 0.02, -0.059, 0.03 - 0.045),
                        M_RED, bevel=0))
        objs.append(box(f'redzone{i}', (0.10, 0.004, 0.02), (x - 0.09, -0.060, 0.135), M_RED, bevel=0))
        objs.append(txt(f'psilabel{i}', 'PSI', (x, -0.056, -0.16), 0.03, M_DARK,
                        rot=(math.pi / 2, 0, 0)))
    return objs


def build_env_filling_station():
    """Floor pad, retaining posts and chains around the bottle row."""
    return [box('pad', (1.75, 0.55, 0.03), (-0.10, -0.10, 0.015), M_DARK, bevel=0.002),
            cylL('post_l', (-0.90, -0.10, 0.36), 0.024, 0.72, M_YELLOW),
            cylL('post_r', (0.50, -0.10, 0.36), 0.024, 0.72, M_YELLOW),
            box('chain_hi', (1.36, 0.016, 0.016), (-0.20, -0.10, 0.56), M_STEEL, bevel=0),
            box('chain_lo', (1.36, 0.016, 0.016), (-0.20, -0.10, 0.28), M_STEEL, bevel=0)]


def build_env_manifold_bank():
    """Six-line manifold rail on the wall bracket; line 3's spindle is the
    interactive STEM, other lines carry mini valves and coiled spare hoses."""
    # Low strip: the backing panel must stay below ~1.20 m so the wall-mounted
    # GAUGES board (z 1.23-1.78) keeps a clear line of sight from the camera.
    objs = [box('panel', (2.60, 0.08, 0.30), (0.57, 0.62, 1.05), M_BLUE, bevel=0.004),
            cylL('rail', (0.57, 0.55, 1.18), 0.045, 2.45, M_STEEL2, rot=(0, math.pi / 2, 0))]
    for k, x in enumerate((-0.78, -0.24, 0.30, 0.84, 1.38, 1.92)):
        objs.append(pipe(f'drop{k}', (x, 0.55, 1.18), (x, 0.47, 1.18), 0.028, M_STEEL2))
        if x == 0.30:
            continue  # line 3 rendered by the STEM kit object
        objs += [cylL(f'mini_stem{k}', (x, 0.42, 1.18), 0.014, 0.10, M_STEEL2),
                 cylL(f'mini_wheel{k}', (x, 0.36, 1.18), 0.04, 0.016, M_RED, rot=(math.pi / 2, 0, 0)),
                 torusL(f'coil{k}', (x, 0.30, 1.00), 0.09, 0.02, M_DARK, rot=(math.pi / 2, 0, 0))]
    objs += [box('bracket_a', (0.10, 0.20, 0.10), (-0.40, 0.70, 1.10), M_STEEL, bevel=0.003),
             box('bracket_b', (0.10, 0.20, 0.10), (1.55, 0.70, 1.10), M_STEEL, bevel=0.003)]
    return objs


def build_env_line3_hose():
    """Fixed fill hose from line 3 curving down to the QRC rest position."""
    return [pipe('hose_a', (0.30, 0.47, 1.16), (0.44, 0.20, 1.05), 0.026, M_DARK),
            pipe('hose_b', (0.44, 0.20, 1.05), (0.52, -0.10, 0.90), 0.026, M_DARK),
            pipe('hose_c', (0.52, -0.10, 0.90), (0.50, -0.10, 0.865), 0.024, M_DARK)]


def build_env_compressor():
    return [box('pump', (0.75, 0.55, 0.55), (1.75, 1.05, 0.28), M_STEEL, bevel=0.006),
            cylL('tank', (1.75, 1.05, 0.98), 0.30, 0.85, M_STEEL2, rot=(0, math.pi / 2, 0)),
            cylL('filter', (1.45, 0.78, 0.62), 0.07, 0.22, M_DARK),
            pipe('airline', (1.75, 1.20, 1.22), (0.60, 0.66, 1.38), 0.026, M_DARK)]


def build_env_room():
    floor = pbr('dive floor', 'concrete_floor_worn_001', scale=1.3)
    wall = pbr('dive wall', 'factory_wall', scale=1.2)
    return [box('floor', (6.0, 5.0, 0.06), (0.1, 0.55, -0.03), floor, bevel=0),
            box('backwall', (6.0, 0.10, 2.8), (0.1, 1.38, 1.40), wall, bevel=0),
            box('leftwall', (0.10, 5.0, 2.8), (-2.6, 0.55, 1.40), wall, bevel=0),
            box('rightwall', (0.10, 5.0, 2.8), (2.75, 0.55, 1.40), wall, bevel=0)]


def delete_all(objs):
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.ops.object.delete(use_global=False)


def mesh_tree(parent):
    out, stack = [], list(parent.children)
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        if n.type == 'MESH':
            out.append(n)
    return out


def main():
    KIT_MESH.mkdir(parents=True, exist_ok=True)
    SCENE_ENV_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    builders = {
        'QRC': build_qrc,
        'VALVE': build_valve,
        'BOTTLE3': lambda: build_bottle(3),
        'BOTTLE1': lambda: build_bottle(1),
        'BOTTLE2': lambda: build_bottle(2),
        'STEM': build_stem,
        'GAUGES': build_gauges,
    }
    for oid, fn in builders.items():
        objs = fn()
        bpy.context.view_layer.update()
        export_glb(objs, KIT_MESH / f'{oid}.glb')
        delete_all(objs)

    env_builders = {
        'filling_station': ('充装位地垫与固定链', build_env_filling_station),
        'manifold_bank': ('六路汇流排', build_env_manifold_bank),
        'line3_hose': ('3 号路充装软管', build_env_line3_hose),
        'compressor': ('空气压缩机', build_env_compressor),
        'room': ('充装间地面与墙体', build_env_room),
    }
    for pid, (label, fn) in env_builders.items():
        objs = fn()
        bpy.context.view_layer.update()
        export_glb(objs, SCENE_ENV_DIR / f'{SCENE_ID}_{pid}.glb')
        delete_all(objs)

    for oid, spec in LAYOUT['objects'].items():
        objs = import_glb(KIT_MESH / f'{oid}.glb')
        pos, wxyz = spec['pose']
        parent_to('HC_' + oid, objs, location=pos, wxyz=wxyz)
    env_entries = []
    for pid, (label, _) in env_builders.items():
        objs = import_glb(SCENE_ENV_DIR / f'{SCENE_ID}_{pid}.glb')
        parent_to('HC_ENV_' + pid, objs)
        env_entries.append({'prop_id': pid, 'label': label,
                            'asset': f'scenes/{SCENE_ID}/meshes/env/{SCENE_ID}_{pid}.glb',
                            'pose': {'position_m': [0, 0, 0], 'wxyz': [1, 0, 0, 0]},
                            'scale_m': [1.0, 1.0, 1.0]})
    bpy.context.view_layer.update()

    obj_parents = {n.name[3:]: n for n in bpy.data.objects
                   if n.name.startswith('HC_') and not n.name.startswith('HC_ENV_')}
    env_parents = [n for n in bpy.data.objects if n.name.startswith('HC_ENV_')]

    verify_depths(CAM, LOOK,
                  {k: v[0] for k, v in LAYOUT['depth_rows'].items()},
                  {k: v[1] for k, v in LAYOUT['depth_rows'].items()})

    subject_items = {}
    for oid, p in obj_parents.items():
        own = mesh_tree(p)
        lo, hi = objs_bbox([p] + own)
        subject_items[oid] = (lo, hi, own)
    verify_back_radial('BOTTLE3', LAYOUT['objects']['BOTTLE3']['pose'],
                       BACK_INFO['BOTTLE3']['center_local'], BACK_INFO['BOTTLE3']['normal_local'], CAM)

    bboxes = {k: (v[0], v[1]) for k, v in subject_items.items()}
    frame_items = dict(bboxes)
    frame_items['manifold'] = objs_bbox([env_parents[1]] + mesh_tree(env_parents[1]))
    frame_items['gaugewall'] = objs_bbox([env_parents[4]] + mesh_tree(env_parents[4]))
    all_lo, all_hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for lo, hi in frame_items.values():
        for i in range(3):
            all_lo[i] = min(all_lo[i], lo[i])
            all_hi[i] = max(all_hi[i], hi[i])
    fwd, right, up = screen_basis(CAM, LOOK)
    cs = [Vector((x, y, z)) for x in (all_lo.x, all_hi.x) for y in (all_lo.y, all_hi.y)
          for z in (all_lo.z, all_hi.z)]
    u = [(c - Vector(CAM)) @ right for c in cs]
    v = [(c - Vector(CAM)) @ up for c in cs]
    ortho = round(max(max(abs(min(u)), abs(max(u))) * 2,
                      max(abs(min(v)), abs(max(v))) * 2 * 1280 / 900) * 1.06, 3)
    verify_frame(CAM, LOOK, ortho, bboxes)

    blocker_meshes = [m for e in env_parents for m in mesh_tree(e)]
    blocker_meshes += [m for p in obj_parents.values() for m in mesh_tree(p)]
    verify_visibility(CAM, subject_items, blocker_meshes, min_frac=0.5)

    # insertion: QRC socket mouth lands on the VALVE outlet anchor; the sleeve
    # reaches back toward the operator and overlaps the outlet nose region
    valve = Vector(LAYOUT['objects']['VALVE']['pose'][0])
    qrc_objs = import_glb(KIT_MESH / 'QRC.glb')
    seat = parent_to('QRC_SEATED', qrc_objs, location=QRC_SEATED)
    bpy.context.view_layer.update()
    s_lo, s_hi = objs_bbox([seat] + mesh_tree(seat))
    nose = (Vector((0.25, -0.08, 0.60)), Vector((0.29, -0.02, 0.66)))
    overlap = all(s_lo[i] < nose[1][i] and s_hi[i] > nose[0][i] for i in range(3))
    print(json.dumps({'insertion_verification': {
        'anchor_world_m': [round(x, 3) for x in valve],
        'qrc_seated_center_m': list(QRC_SEATED),
        'qrc_seated_bbox_m': [[round(x, 3) for x in s_lo], [round(x, 3) for x in s_hi]],
        'valve_outlet_region_m': [[round(x, 3) for x in nose[0]], [round(x, 3) for x in nose[1]]],
        'axis': 'y (both)', 'sleeve_engages_outlet': bool(overlap)}}, ensure_ascii=False), flush=True)
    assert overlap, 'QRC seated pose does not engage the VALVE outlet'
    delete_all([seat] + mesh_tree(seat))

    world_bg()
    light_rig(Vector((0.2, 0.6, 1.1)), 2.4)
    all_scene_objs = [o for n in obj_parents.values() for o in [n] + mesh_tree(n)] + \
                     [o for e in env_parents for o in [e] + mesh_tree(e)]
    render_preview(f'{SCENE_ID}_kit_preview.png', CAM, LOOK, objs=all_scene_objs, ortho=ortho)
    render_preview(f'{SCENE_ID}_kit_preview_persp.png', CAM, LOOK, objs=all_scene_objs,
                   persp_fov=48)

    spec = {
        'schema_version': '1.0', 'scene_id': SCENE_ID, 'title': LAYOUT['title'],
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': [], 'initial_instruction': LAYOUT['initial_instruction'],
        'camera_position_m': list(CAM), 'camera_look_at_m': list(LOOK),
        'environment': env_entries,
        'render_hints': {'ortho_scale_m': ortho, 'grid_extent_m': 3.0,
                         'cue_scale': 1.0, 'label_offset_m': 0.12, 'fit_camera': True},
    }
    for oid, spec_o in LAYOUT['objects'].items():
        pos, wxyz = spec_o['pose']
        spec['objects'].append({
            'object_id': oid, 'label': spec_o['label'],
            'asset': f'scenes/{SCENE_ID}/meshes/{oid}.glb',
            'pose': {'position_m': [round(v, 4) for v in pos], 'wxyz': [round(v, 4) for v in wxyz]},
            'color': list(spec_o['color']), 'capabilities': spec_o['capabilities'],
            'anchors': {k: list(v) for k, v in spec_o['anchors'].items()},
            'description': spec_o['description'],
        })
    write_scene_json(SCENE_ID, spec)

    files = sorted(KIT_MESH.glob('*.glb')) + sorted(SCENE_ENV_DIR.glob('*.glb')) + \
            [ROOT / f'scenes/{SCENE_ID}/scene.json']
    print(json.dumps({'file_table': {str(f.relative_to(ROOT)): f.stat().st_size for f in files}},
                     indent=1), flush=True)


main()
