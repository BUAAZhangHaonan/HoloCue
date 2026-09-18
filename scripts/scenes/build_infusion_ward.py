"""Kit builder for `infusion_ward` (病房输液泵装管与床头监护, design v2).

Run (CPU, resource-guarded):
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
    /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
    --python scripts/scenes/build_infusion_ward.py

Outputs:
  scenes/infusion_ward/meshes/{PUMPCASSETTE,SLOT2,STOPCOCK,BAG1,BAG2,MONITOR}.glb
  scenes/infusion_ward/meshes/env/infusion_ward_{bed,iv_station,trolley,room}.glb
  scenes/infusion_ward/scene.json  (as-built; design from scenes/infusion_ward/docs/design.md)

Reviewed design (v2): camera [0.40,-1.05,1.45] -> look [-0.15,0.55,1.35]; layers
SLOT2 cassette insertion ~1.26 m near (anchor at the slot mouth), STOPCOCK
~1.31 m (same near layer, its own step), BAG1 back label ~1.64 m mid (bag hangs
high on the stand), MONITOR ~2.50 m far head wall. BAG1's config label on the
bag back is the inspect_back radial face (normal horizontal, local Z vertical).
Depth tiers cover precise/persistent/neutral along one chain.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
from mathutils import Vector, Quaternion, Euler
import math

SCENE_ID = 'infusion_ward'
KIT = scene_kit(SCENE_ID)
KIT_MESH = KIT / 'meshes'
SCENE_ENV_DIR = scene_env(SCENE_ID)

CAM = (0.40, -1.05, 1.45)
LOOK = (-0.15, 0.55, 1.35)

LAYOUT = {
    'title': '病房输液泵装管与床头监护',
    'initial_instruction': ('把新泵盒 PUMPCASSETTE 插进输液泵的 2 号泵槽 SLOT2,'
                            '插好后核对 BAG1 背面的配置标签是不是 5% 糖,'
                            '确认无误再把三通 STOPCOCK 顺时针拧 90 度开始输液,'
                            '床头监护仪 MONITOR 全程盯着。'),
    'objects': {
        'PUMPCASSETTE': {'pose': ([-0.62, -0.32, 1.00], (1, 0, 0, 0)), 'label': '一次性泵盒',
                         'color': (150, 190, 170), 'capabilities': ['point', 'insert'],
                         'anchors': {}, 'description': '管路预装的输液泵盒,卡入泵槽;治疗车顶层待用'},
        'SLOT2': {'pose': ([0.05, 0.15, 1.18], (1, 0, 0, 0)), 'label': '2 号泵槽',
                  'color': (90, 90, 100), 'capabilities': ['point'],
                  'anchors': {'insertion': [0, 0, 0]},
                  'description': '泵正面导轨槽,槽口朝护士;槽体中心即满插终点'},
        'STOPCOCK': {'pose': ([0.10, 0.20, 0.95], (1, 0, 0, 0)), 'label': '三通旋塞',
                     'color': (90, 130, 180), 'capabilities': ['point', 'rotate'],
                     'anchors': {}, 'description': '串在泵下管路上,手柄横向为关,顺时针 90 度全开'},
        'BAG1': {'pose': ([-0.05, 0.55, 1.80], (1, 0, 0, 0)), 'label': '5% 糖袋',
                 'color': (230, 235, 240), 'capabilities': ['point', 'inspect_back'],
                 'anchors': {}, 'description': '背面贴配置标签(5% 葡萄糖);袋体贴面为径向面'},
        'BAG2': {'pose': ([-0.42, 0.55, 1.80], (1, 0, 0, 0)), 'label': '10% 糖袋',
                 'color': (230, 235, 240), 'capabilities': ['point'],
                 'anchors': {}, 'description': '消歧用,同型备用袋,背面标签为 10% 葡萄糖'},
        'MONITOR': {'pose': ([-0.35, 1.35, 1.60], (1, 0, 0, 0)), 'label': '床头监护仪',
                    'color': (60, 70, 80), 'capabilities': ['point', 'wait'],
                    'anchors': {}, 'description': '心率/血氧数值,报警时黄色闪烁(报警为脚本时间线事件)'},
    },
    'depth_rows': {
        'PUMPCASSETTE->SLOT2(插泵盒)': ([0.05, 0.15, 1.18], 1.26),
        'STOPCOCK(开三通)': ([0.10, 0.20, 0.95], 1.31),
        'BAG1(核对标签)': ([-0.05, 0.55, 1.80], 1.64),
        'MONITOR(监护)': ([-0.35, 1.35, 1.60], 2.50),
    },
}

# BAG1 inspect_back evidence (local frame, identity pose): the config label
# plate sits on the bag back at local (0, +0.028, +0.02), normal +y.
BACK_INFO = {'BAG1': {'center_local': (0.0, 0.028, 0.02), 'normal_local': (0.0, 1.0, 0.0)}}

# Cassette seated at the SLOT2 anchor: its front face (local origin) lands on
# the slot mouth, body recessing +y into the channel.
CASSETTE_SEATED = (0.05, 0.15, 1.18)

M_STEEL = flat('ward steel', (0.35, 0.39, 0.42, 1.0), 0.75, 0.25)
M_DARK = flat('ward plastic dark', (0.05, 0.06, 0.075, 1.0), 0.08, 0.5)
M_WHITE = flat('ward ivory', (0.92, 0.92, 0.90, 1.0), 0.03, 0.4)
M_GREEN = flat('ward wave green', (0.05, 0.85, 0.35, 1.0), 0.05, 0.3, (0.03, 0.6, 0.2, 1.0))
M_RED = flat('ward red', (0.78, 0.06, 0.05, 1.0), 0.12, 0.3)
M_BLUE = flat('ward screen blue', (0.05, 0.20, 0.38, 1.0), 0.06, 0.25, (0.01, 0.07, 0.25, 1.0))
M_FLUID = flat('ward fluid', (0.72, 0.85, 0.95, 1.0), 0.0, 0.08)
M_GLASS = flat('ward glass', (0.35, 0.5, 0.55, 1.0), 0.05, 0.1)
M_YELLOW = flat('ward alarm yellow', (0.95, 0.78, 0.10, 1.0), 0.1, 0.3, (0.8, 0.6, 0.05, 1.0))


def cylL(name, loc, radius, depth, mat, rot=(0, 0, 0), vertices=48):
    return cyl(name, radius, depth, loc, mat, rot=rot, vertices=vertices)


def txt(name, body, loc, size=0.04, mat=M_WHITE, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.align_x = 'CENTER'
    cu.size = size
    cu.extrude = 0.003
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


def build_cassette():
    """Disposable pump cassette; local origin at the center of the front face
    that enters the slot first, body extends +y."""
    return [box('shell', (0.15, 0.06, 0.20), (0, 0.03, 0), M_WHITE, bevel=0.006),
            box('window', (0.10, 0.008, 0.07), (0, -0.002, 0.045), M_FLUID, bevel=0.002),
            box('tube_pre', (0.012, 0.05, 0.012), (0.05, 0.005, -0.075), M_FLUID, bevel=0),
            box('latch_l', (0.014, 0.05, 0.03), (-0.078, 0.028, 0.06), M_DARK, bevel=0.002),
            box('latch_r', (0.014, 0.05, 0.03), (0.078, 0.028, 0.06), M_DARK, bevel=0.002)]


def build_slot2():
    """Pump face rail slot; local origin at the channel mouth (y=0), channel
    recesses +y. Guide rails + frame + number plate."""
    return [box('rail_l', (0.024, 0.13, 0.24), (-0.078, 0.062, 0), M_DARK, bevel=0.002),
            box('rail_r', (0.024, 0.13, 0.24), (0.078, 0.062, 0), M_DARK, bevel=0.002),
            box('guide_l', (0.006, 0.125, 0.24), (-0.065, 0.06, 0), M_RED, bevel=0),
            box('guide_r', (0.006, 0.125, 0.24), (0.065, 0.06, 0), M_RED, bevel=0),
            box('backplate', (0.13, 0.015, 0.20), (0, 0.125, 0), M_DARK, bevel=0.002),
            box('lip_t', (0.17, 0.02, 0.012), (0, 0.06, 0.10), M_DARK, bevel=0.002),
            box('lip_b', (0.17, 0.02, 0.012), (0, 0.06, -0.10), M_DARK, bevel=0.002),
            txt('slot2num', '2', (0.105, -0.004, 0.085), 0.045, M_WHITE, rot=(math.pi / 2, 0, 0))]


def build_stopcock():
    """In-line three-way stopcock on the tube; handle bar along x = closed."""
    return [cylL('body', (0, 0, 0), 0.034, 0.062, M_BLUE),
            cylL('port_u', (0, 0, 0.052), 0.014, 0.05, M_FLUID),
            cylL('port_d', (0, 0, -0.052), 0.014, 0.05, M_FLUID),
            cylL('port_l', (-0.048, 0, 0), 0.014, 0.05, M_FLUID, rot=(0, math.pi / 2, 0)),
            cylL('cap', (0, 0, 0.036), 0.020, 0.012, M_WHITE),
            box('handle', (0.150, 0.022, 0.022), (0, 0, 0.058), M_RED, bevel=0.004)]


def build_bag(fluid_rgba, label_text):
    """Hanging infusion bag, origin at bag center; label plate on the back."""
    objs = [box('bag', (0.13, 0.05, 0.21), (0, 0, 0), M_FLUID, bevel=0.012),
            box('fluid', (0.108, 0.034, 0.15), (0, 0, -0.018), M_FLUID, bevel=0.008),
            box('seal', (0.13, 0.052, 0.012), (0, 0, 0.108), M_WHITE, bevel=0.004),
            box('hanger', (0.05, 0.008, 0.03), (0, 0, 0.128), M_WHITE, bevel=0.002),
            cylL('port', (0, 0, -0.118), 0.016, 0.026, M_WHITE),
            box('label', (0.09, 0.004, 0.07), (0, 0.0275, 0.02), M_WHITE, bevel=0)]
    objs.append(txt('labeltxt', label_text, (0, 0.031, 0.02), 0.024, M_DARK,
                    rot=(math.pi / 2, 0, 0)))
    return objs


def build_monitor():
    """Bedside multi-parameter monitor with waveforms and alarm dome."""
    objs = [box('bezel', (0.42, 0.09, 0.34), (0, 0, 0), M_DARK, bevel=0.006),
            box('screen', (0.34, 0.02, 0.25), (0, -0.048, 0.02), M_BLUE, bevel=0.002)]
    for i in range(3):
        objs.append(box(f'wave{i}', (0.008, 0.004, 0.028), (-0.12 + i * 0.12, -0.059, 0.10),
                        M_GREEN, bevel=0))
    objs.append(box('valuebox', (0.09, 0.004, 0.05), (0.11, -0.059, -0.07), M_GREEN, bevel=0))
    objs.append(cylL('alarm', (0.13, -0.05, 0.185), 0.026, 0.02, M_YELLOW, rot=(math.pi / 2, 0, 0)))
    for k, x in enumerate((-0.14, -0.10, -0.06)):
        objs.append(cylL(f'btn{k}', (x, -0.048, -0.135), 0.012, 0.008, M_WHITE,
                         rot=(math.pi / 2, 0, 0)))
    objs.append(box('mount', (0.10, 0.06, 0.10), (0, 0.06, 0), M_STEEL, bevel=0.003))
    return objs


def build_env_bed():
    """Hospital bed with headboard at the monitor wall side."""
    objs = [box('frame', (1.55, 0.78, 0.12), (0.35, 1.02, 0.50), M_STEEL, bevel=0.006),
            box('mattress', (1.48, 0.72, 0.16), (0.35, 1.02, 0.64), M_WHITE, bevel=0.02),
            box('pillow', (0.34, 0.50, 0.08), (-0.22, 1.02, 0.76), M_WHITE, bevel=0.02),
            box('headboard', (0.10, 0.78, 0.62), (-0.42, 1.02, 1.05), M_STEEL, bevel=0.004),
            box('footboard', (0.08, 0.78, 0.55), (1.12, 1.02, 0.93), M_STEEL, bevel=0.004)]
    for cx, cy in ((-0.30, 0.70), (0.98, 0.70), (-0.30, 1.34), (0.98, 1.34)):
        objs.append(cylL(f'leg_{cx}_{cy}', (cx, cy, 0.20), 0.022, 0.44, M_STEEL))
        objs.append(cylL(f'caster_{cx}_{cy}', (cx, cy, 0.05), 0.05, 0.035, M_DARK,
                         rot=(math.pi / 2, 0, 0)))
    return objs


def build_env_iv_station():
    """IV stand with gantry hooks for the two bags and the pump on the pole;
    tube drops from the pump through the STOPCOCK line toward the bed."""
    objs = [cylL('pole', (0.02, 0.28, 1.02), 0.016, 2.04, M_STEEL),
            cylL('poletop', (0.02, 0.28, 2.06), 0.010, 0.06, M_STEEL)]
    for k in range(5):
        a = math.radians(90 + 72 * k)
        ex, ey = 0.02 + 0.26 * math.cos(a), 0.28 + 0.26 * math.sin(a)
        objs.append(pipe(f'baseleg{k}', (0.02, 0.28, 0.035), (ex, ey, 0.035), 0.010, M_STEEL))
        objs.append(cylL(f'basecaster{k}', (ex, ey, 0.028), 0.026, 0.02, M_DARK))
    # gantry arm reaching +y to the bag hooks
    objs.append(pipe('gantry', (0.02, 0.28, 2.03), (0.02, 0.55, 2.03), 0.012, M_STEEL))
    for hx in (-0.05, -0.42):
        objs.append(pipe(f'hook_{hx}', (hx, 0.55, 2.03), (hx, 0.55, 1.955), 0.006, M_STEEL))
    # pump housing on the pole (SLOT2's channel sits in its face)
    objs += [box('pump', (0.42, 0.20, 0.42), (0.05, 0.26, 1.20), M_WHITE, bevel=0.006),
             box('pump_screen', (0.24, 0.012, 0.09), (0.05, 0.155, 1.36), M_BLUE, bevel=0.002),
             cylL('pump_btn_a', (0.19, 0.152, 1.30), 0.016, 0.012, M_GREEN, rot=(math.pi / 2, 0, 0)),
             cylL('pump_btn_b', (0.19, 0.152, 1.24), 0.016, 0.012, M_RED, rot=(math.pi / 2, 0, 0)),
             box('clamp', (0.10, 0.06, 0.10), (0.02, 0.37, 1.20), M_DARK, bevel=0.002)]
    # tube line: pump bottom -> stopcock zone -> toward the bed arm
    objs += [pipe('tube_a', (0.10, 0.19, 1.10), (0.10, 0.20, 1.00), 0.008, M_FLUID),
             pipe('tube_b', (0.10, 0.20, 0.90), (0.18, 0.35, 0.80), 0.008, M_FLUID),
             pipe('tube_c', (0.18, 0.35, 0.80), (0.35, 0.75, 0.74), 0.008, M_FLUID)]
    # drip line from BAG1 down to the pump top
    objs.append(pipe('drip', (-0.05, 0.55, 1.68), (0.05, 0.30, 1.54), 0.007, M_FLUID))
    return objs


def build_env_trolley():
    """Treatment cart holding the fresh cassette."""
    objs = [box('body', (0.52, 0.36, 0.78), (-0.62, -0.32, 0.53), M_WHITE, bevel=0.005),
            box('top', (0.58, 0.42, 0.045), (-0.62, -0.32, 0.93), M_STEEL, bevel=0.003),
            box('handle', (0.05, 0.16, 0.03), (-0.36, -0.32, 0.80), M_STEEL, bevel=0.003)]
    for k in range(2):
        objs.append(box(f'drawer{k}', (0.46, 0.01, 0.22), (-0.62, -0.505, 0.42 + k * 0.28),
                        M_DARK, bevel=0.002))
    for cx, cy in ((-0.84, -0.48), (-0.40, -0.48), (-0.84, -0.16), (-0.40, -0.16)):
        objs.append(cylL(f'caster_{cx}_{cy}', (cx, cy, 0.05), 0.05, 0.035, M_DARK,
                         rot=(math.pi / 2, 0, 0)))
    return objs


def build_env_room():
    """Ward walls/floor, bedside cabinet and a half-drawn curtain."""
    floor = pbr('ward floor', 'rubber_tiles', scale=2.2)
    wall = pbr('ward wall', 'marble_01', scale=1.0)
    objs = [box('floor', (5.6, 4.8, 0.06), (0.0, 0.55, -0.03), floor, bevel=0),
            box('backwall', (5.6, 0.10, 2.8), (0.0, 1.51, 1.40), wall, bevel=0),
            box('leftwall', (0.10, 4.8, 2.8), (-2.4, 0.55, 1.40), wall, bevel=0),
            box('rightwall', (0.10, 4.8, 2.8), (2.45, 0.55, 1.40), wall, bevel=0),
            box('cabinet', (0.50, 0.44, 0.62), (0.95, 1.10, 0.31), M_WHITE, bevel=0.005),
            box('curtain', (0.02, 1.3, 2.0), (1.60, 0.80, 1.55), M_GLASS, bevel=0),
            cylL('curtain_track', (1.60, 0.80, 2.58), 0.012, 1.3, M_STEEL, rot=(0, 0, 0)),
            box('callbtn', (0.10, 0.03, 0.14), (-0.80, 1.445, 1.10), M_WHITE, bevel=0.002)]
    return objs


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
        'PUMPCASSETTE': build_cassette,
        'SLOT2': build_slot2,
        'STOPCOCK': build_stopcock,
        'BAG1': lambda: build_bag(M_FLUID, '5% GS 500ml'),
        'BAG2': lambda: build_bag(M_FLUID, '10% GS 500ml'),
        'MONITOR': build_monitor,
    }
    for oid, fn in builders.items():
        objs = fn()
        bpy.context.view_layer.update()
        export_glb(objs, KIT_MESH / f'{oid}.glb')
        delete_all(objs)

    env_builders = {
        'bed': ('病床与床头板', build_env_bed),
        'iv_station': ('输液架与泵体管路', build_env_iv_station),
        'trolley': ('床旁治疗车', build_env_trolley),
        'room': ('病房墙体地面与隔帘', build_env_room),
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
    verify_back_radial('BAG1', LAYOUT['objects']['BAG1']['pose'],
                       BACK_INFO['BAG1']['center_local'], BACK_INFO['BAG1']['normal_local'], CAM)

    bboxes = {k: (v[0], v[1]) for k, v in subject_items.items()}
    frame_items = dict(bboxes)
    frame_items['station'] = objs_bbox([env_parents[1]] + mesh_tree(env_parents[1]))
    frame_items['bed'] = objs_bbox([env_parents[0]] + mesh_tree(env_parents[0]))
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

    # SLOT2's channel recesses into the pump housing by design; visibility is
    # judged on the mouth zone (rails + number plate) in front of the face.
    lo, hi, own = subject_items['SLOT2']
    subject_items['SLOT2'] = (Vector((lo.x, 0.140, lo.z)), Vector((hi.x, 0.162, hi.z)), own)

    blocker_meshes = [m for e in env_parents for m in mesh_tree(e)]
    blocker_meshes += [m for p in obj_parents.values() for m in mesh_tree(p)]
    verify_visibility(CAM, subject_items, blocker_meshes, min_frac=0.5)

    # insertion: the cassette front face lands on the SLOT2 mouth, body
    # recessing +y into the channel region
    slot = Vector(LAYOUT['objects']['SLOT2']['pose'][0])
    cas_objs = import_glb(KIT_MESH / 'PUMPCASSETTE.glb')
    seat = parent_to('CAS_SEATED', cas_objs, location=CASSETTE_SEATED)
    bpy.context.view_layer.update()
    s_lo, s_hi = objs_bbox([seat] + mesh_tree(seat))
    chan = (Vector((0.05, 0.16, 1.07)), Vector((0.15, 0.26, 1.29)))
    overlap = all(s_lo[i] < chan[1][i] and s_hi[i] > chan[0][i] for i in range(3))
    print(json.dumps({'insertion_verification': {
        'anchor_world_m': [round(x, 3) for x in slot],
        'cassette_seated_center_m': list(CASSETTE_SEATED),
        'cassette_seated_bbox_m': [[round(x, 3) for x in s_lo], [round(x, 3) for x in s_hi]],
        'slot_channel_region_m': [[round(x, 3) for x in chan[0]], [round(x, 3) for x in chan[1]]],
        'axis': 'y (both)', 'cassette_recesses_into_channel': bool(overlap)}},
                     ensure_ascii=False), flush=True)
    assert overlap, 'Cassette seated pose does not recess into the SLOT2 channel'
    delete_all([seat] + mesh_tree(seat))

    world_bg()
    light_rig(Vector((0.0, 0.6, 1.2)), 2.2)
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
            'pose': {'position_m': [round(v, 4) for v in pos], 'wxyz': list(wxyz)},
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
