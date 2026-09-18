"""Kit builder for `cnc_toolchange` (立式加工中心手动装刀与拉钉点检, design v4).

Run (CPU, resource-guarded):
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
    /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
    --python scripts/scenes/build_cnc_toolchange.py

Outputs:
  scenes/cnc_toolchange/meshes/{MODESWITCH,T09,POCKET9,T03,MAG,PANEL}.glb
  scenes/cnc_toolchange/meshes/env/cnc_toolchange_{machine_shell,machine_interior,tool_tray,tool_cart,room}.glb
  scenes/cnc_toolchange/scene.json   (as-built; design values from scenes/cnc_toolchange/docs/design.md)
  runs/scene_v2/build_cnc_toolchange.log via shell redirect

Reviewed design (scenes/cnc_toolchange/docs/design.md v4): camera [1.05,-0.95,1.45]
-> look [0.00,0.45,1.15]; layers MODESWITCH/PANEL ~2.10m (far, same-layer dual
roles), T03 1.51m (mid), T09->POCKET9 1.06m (near). T03's pull-stud end face is
the inspect_back radial face (normal along the tool axis, local Z vertical).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
from common import _projected_size
from mathutils import Vector, Quaternion, Euler
import math

SCENE_ID = 'cnc_toolchange'
KIT = scene_kit(SCENE_ID)
KIT_MESH = KIT / 'meshes'
SCENE_ENV_DIR = scene_env(SCENE_ID)

CAM = (1.05, -0.95, 1.45)
LOOK = (0.00, 0.45, 1.15)

# Single source of truth for the scene JSON. Poses are the reviewed design
# world values (design.md 视点与深度表); geometry is modeled around each
# object's local origin per the project GLB contract.
LAYOUT = {
    'title': '立式加工中心手动装刀与拉钉点检',
    'initial_instruction': ('先把模式旋钮 MODESWITCH 顺时针拧 90 度切到手动档,'
                            '把镗刀 T09 插进刀库当前的 9 号刀套 POCKET9,'
                            '再拿起刀具车上的 T03,翻看柄尾的拉钉有没有松动,'
                            '控制面板 PANEL 全程盯着报警灯。'),
    'objects': {
        'MODESWITCH': {'pose': ([0.10, 1.00, 1.45], (1, 0, 0, 0)), 'label': '模式选择旋钮',
                       'color': (225, 225, 235), 'capabilities': ['point', 'rotate'],
                       'anchors': {}, 'description': '面板三档旋钮:自动/手动/编辑,白线指示当前档'},
        'T09': {'pose': ([0.30, 0.00, 1.03], (1, 0, 0, 0)), 'label': '9 号镗刀柄',
                'color': (205, 190, 150), 'capabilities': ['point', 'insert'],
                'anchors': {}, 'description': 'BT40 柄+拉钉,待入库,平放在刀臂托盘上'},
        'POCKET9': {'pose': ([0.72, 0.08, 1.12], (1, 0, 0, 0)), 'label': '9 号刀套',
                    'color': (95, 95, 105), 'capabilities': ['point'],
                    'anchors': {'insertion': [0, 0, 0]},
                    'description': '当前朝向开口的空刀套,套孔中轴即满插终点'},
        'T03': {'pose': ([0.35, 0.38, 1.20], (1, 0, 0, 0)), 'label': '3 号镗刀柄',
                'color': (210, 155, 120), 'capabilities': ['point', 'inspect_back'],
                'anchors': {},
                'description': '刀具车上平放(局部 Z 竖直);拉钉端面法线沿刀柄轴线(水平),垂直于局部 Z,为径向面'},
        'MAG': {'pose': ([0.72, 0.33, 1.37], (1, 0, 0, 0)), 'label': '刀库盘',
                'color': (135, 140, 150), 'capabilities': ['point'],
                'anchors': {}, 'description': '12 工位圆盘,电控转位,不可手动盘(能力负例用)'},
        'PANEL': {'pose': ([0.10, 1.02, 1.45], (1, 0, 0, 0)), 'label': '控制面板',
                  'color': (70, 80, 95), 'capabilities': ['point', 'wait'],
                  'anchors': {}, 'description': '程序状态屏+报警灯,与 MODESWITCH 同板,监控用(报警为脚本时间线事件)'},
    },
    # Design depth table (design.md): label -> (world point, expected depth m).
    'depth_rows': {
        'MODESWITCH(切档)': ([0.10, 1.00, 1.45], 2.10),
        'T09->POCKET9(插刀)': ([0.72, 0.08, 1.12], 1.06),
        'T03(拉钉点检)': ([0.35, 0.38, 1.20], 1.51),
        'PANEL(盯报警)': ([0.10, 1.02, 1.45], 2.10),
    },
}

# inspect_back radial-face evidence for T03 (local frame, pose wxyz identity):
# the pull-stud end face sits at local x=-0.24 with outward normal -x.
BACK_INFO = {'T03': {'center_local': (-0.24, 0.0, 0.0), 'normal_local': (-1.0, 0.0, 0.0)}}

# Seated pose of T09 at the POCKET9 anchor (flange face against the collar).
T09_SEATED = (0.62, 0.08, 1.12)

M_STEEL = flat('cnc painted steel', (0.16, 0.19, 0.22, 1.0), 0.72, 0.25)
M_STEEL2 = flat('cnc brushed steel', (0.38, 0.42, 0.45, 1.0), 0.82, 0.21)
M_DARK = flat('cnc rubber black', (0.025, 0.032, 0.038, 1.0), 0.05, 0.62)
M_YELLOW = flat('cnc safety yellow', (0.86, 0.46, 0.025, 1.0), 0.1, 0.3)
M_RED = flat('cnc alarm red', (0.72, 0.025, 0.018, 1.0), 0.15, 0.3, (0.8, 0.015, 0.01, 1.0))
M_BLUE = flat('cnc screen blue', (0.03, 0.22, 0.48, 1.0), 0.05, 0.28, (0.01, 0.08, 0.3, 1.0))
M_GREEN = flat('cnc status green', (0.03, 0.65, 0.18, 1.0), 0.05, 0.3, (0.02, 0.5, 0.1, 1.0))
M_WHITE = flat('cnc ivory', (0.86, 0.88, 0.86, 1.0), 0.0, 0.38)
M_GLASS = flat('cnc door glass', (0.35, 0.5, 0.55, 1.0), 0.05, 0.08)


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



def cylL(name, loc, radius, depth, mat, rot=(0, 0, 0), vertices=48):
    """Location-first cylinder wrapper over common.cyl (radius, depth, location)."""
    return cyl(name, radius, depth, loc, mat, rot=rot, vertices=vertices)

def pocket_stub(loc, mat=M_DARK, r=0.05, depth=0.10):
    """Magazine pocket barrel along local x (rim position given in disc yz)."""
    return cylL(f'stub', loc, r, depth, mat, rot=(0, math.pi / 2, 0), vertices=24)


def build_modeswitch():
    """3-position selector dial; dial axis local y (out of the panel)."""
    objs = [cylL('dial', (0, 0, 0), 0.062, 0.05, M_DARK, rot=(math.pi / 2, 0, 0)),
            cylL('dial_cap', (0, -0.02, 0), 0.05, 0.02, M_WHITE, rot=(math.pi / 2, 0, 0)),
            box('dial_grip', (0.012, 0.012, 0.012), (0, -0.012, 0.0), M_STEEL2, bevel=0.002),
            box('dial_pointer', (0.008, 0.008, 0.034), (0, -0.032, 0.017), M_RED, bevel=0),
            cylL('dial_stem', (0, 0.045, 0), 0.018, 0.05, M_DARK, rot=(math.pi / 2, 0, 0))]
    return objs


def boring_bar(name, stud_x):
    """BT40 boring-bar holder along local x; stud_x=+1 puts the pull stud on the
    +x (leading) end, -1 on the -x end. Returns (objects, stud_end_x)."""
    objs = []
    if stud_x > 0:
        stud_c, taper_c, flange_c, body_c, bar_c = 0.24, 0.155, 0.10, -0.02, -0.20
        objs += [cylL(f'{name}_stud', (stud_c, 0, 0), 0.018, 0.06, M_YELLOW, rot=(0, math.pi / 2, 0)),
                 cylL(f'{name}_taper', (taper_c, 0, 0), 0.045, 0.11, M_STEEL2, rot=(0, math.pi / 2, 0), vertices=24),
                 cylL(f'{name}_flange', (flange_c, 0, 0), 0.055, 0.02, M_STEEL2, rot=(0, math.pi / 2, 0)),
                 cylL(f'{name}_body', (body_c, 0, 0), 0.042, 0.17, M_STEEL2, rot=(0, math.pi / 2, 0)),
                 cylL(f'{name}_bar', (bar_c, 0, 0), 0.025, 0.34, M_DARK, rot=(0, math.pi / 2, 0))]
        # carbide insert near the cutting end
        objs.append(box(f'{name}_insert', (0.03, 0.008, 0.012), (-0.34, 0, 0.02), M_DARK, bevel=0.001))
        return objs, 0.27
    objs += [cylL(f'{name}_stud', (-0.21, 0, 0), 0.018, 0.06, M_YELLOW, rot=(0, math.pi / 2, 0)),
             cylL(f'{name}_taper', (-0.145, 0, 0), 0.045, 0.10, M_STEEL2, rot=(0, math.pi / 2, 0), vertices=24),
             cylL(f'{name}_flange', (-0.09, 0, 0), 0.055, 0.02, M_STEEL2, rot=(0, math.pi / 2, 0)),
             cylL(f'{name}_body', (0.02, 0, 0), 0.042, 0.14, M_STEEL2, rot=(0, math.pi / 2, 0)),
             cylL(f'{name}_bar', (0.15, 0, 0), 0.025, 0.18, M_DARK, rot=(0, math.pi / 2, 0))]
    objs.append(box(f'{name}_insert', (0.03, 0.008, 0.012), (0.22, 0, 0.02), M_DARK, bevel=0.001))
    return objs, -0.24


def build_pocket9():
    """Empty pocket at the magazine rim; local origin at the bore mouth (x=0),
    bore runs +x. Same convention as the drone_bench BAY (origin at mouth)."""
    objs = [cylL('bore', (0.08, 0, 0), 0.062, 0.16, M_DARK, rot=(0, math.pi / 2, 0)),
            cylL('collar', (0.012, 0, 0), 0.078, 0.024, M_STEEL2, rot=(0, math.pi / 2, 0)),
            box('detent', (0.02, 0.012, 0.012), (0.15, 0, 0), M_STEEL, bevel=0.002)]
    objs.append(txt('p9num', '9', (0.03, -0.085, 0.055), 0.05, M_WHITE, rot=(0, math.pi / 2, 0)))
    return objs


def build_mag():
    """12-station disc magazine; disc axis local x (mounted proud of the machine
    right wall). Pocket 9's station stays empty here (separate POCKET9 object at
    the rim position local (0, -0.25, -0.25))."""
    objs = [cylL('disc', (0, 0, 0), 0.35, 0.09, M_STEEL2, rot=(0, math.pi / 2, 0)),
            cylL('hub', (0, 0, 0), 0.09, 0.14, M_STEEL, rot=(0, math.pi / 2, 0))]
    p9_dir = Vector((0.0, -0.7071, -0.7071))
    for i in range(12):
        ang = 2 * math.pi * i / 12
        rim = Vector((0.0, math.cos(ang), math.sin(ang))) * 0.35
        if abs((rim / 0.35 - p9_dir).length) < 0.05:
            continue  # station 9 rendered by the POCKET9 kit object
        objs.append(pocket_stub((0.0, rim.y, rim.z)))
        objs.append(txt(f'num{i}', str(i + 1), (0.062, rim.y * 0.86, rim.z * 0.86), 0.032,
                        M_WHITE, rot=(0, math.pi / 2, 0)))
    return objs


def build_panel():
    """CNC control pendant board: program screen, pilot lights, mode strip; the
    MODESWITCH dial mounts at the board center (separate object)."""
    objs = [box('plate', (0.58, 0.06, 0.62), (0, 0.01, 0), M_STEEL, bevel=0.006),
            box('screen', (0.34, 0.024, 0.22), (0.10, -0.030, 0.17), M_BLUE, bevel=0.002),
            box('bezel', (0.38, 0.020, 0.26), (0.10, -0.026, 0.17), M_DARK, bevel=0.003)]
    for k, z in enumerate((0.22, 0.13, 0.04)):
        objs.append(cylL(f'pilot{k}', (-0.22, -0.035, z), 0.018, 0.014,
                        M_GREEN if k == 0 else M_RED, rot=(math.pi / 2, 0, 0)))
    objs.append(txt('modetext', 'AUTO  MAN  EDIT', (0.0, -0.040, -0.22), 0.036, M_WHITE,
                    rot=(math.pi / 2, 0, 0)))
    return objs


def build_env_machine_shell():
    """Column, side walls, slid-open safety door, pendant arm, magazine mount."""
    objs = [
        box('base', (1.55, 1.70, 0.50), (-0.125, 1.35, 0.25), M_STEEL, bevel=0.01),
        box('column', (1.55, 1.05, 2.20), (-0.125, 1.675, 1.60), M_STEEL, bevel=0.008),
        box('wall_l', (0.35, 0.65, 2.20), (-0.725, 0.825, 1.60), M_STEEL, bevel=0.006),
        box('wall_r', (0.20, 0.65, 2.20), (0.55, 0.825, 1.60), M_STEEL, bevel=0.006),
        box('topbeam', (1.55, 1.70, 0.15), (-0.125, 1.35, 2.775), M_STEEL, bevel=0.006),
        box('door_glass', (0.34, 0.04, 1.85), (-0.71, 0.53, 1.62), M_GLASS, bevel=0.002),
        box('rail_top', (0.95, 0.05, 0.05), (-0.125, 0.52, 2.60), M_STEEL2, bevel=0.004),
        box('rail_bot', (0.95, 0.05, 0.05), (-0.125, 0.52, 0.62), M_STEEL2, bevel=0.004),
        # pendant arm carrying the control board at the design pose
        box('pendant_arm', (0.10, 0.16, 0.10), (0.10, 1.10, 1.45), M_STEEL2, bevel=0.004),
        cylL('pendant_hinge', (0.10, 1.16, 1.45), 0.026, 0.12, M_DARK, rot=(0, 0, math.pi / 2)),
        # magazine mount reaching from the right wall to the disc hub
        box('mag_arm_a', (0.10, 0.46, 0.07), (0.685, 0.56, 1.31), M_STEEL, bevel=0.004),
        box('mag_arm_b', (0.10, 0.46, 0.07), (0.685, 0.56, 1.43), M_STEEL, bevel=0.004),
    ]
    return objs


def build_env_machine_interior():
    """Work table, fixture and spindle head shown through the open door."""
    return [
        box('table', (0.95, 0.42, 0.10), (-0.12, 0.86, 0.96), M_STEEL2, bevel=0.004),
        box('fixture', (0.42, 0.22, 0.10), (-0.12, 0.86, 1.06), M_DARK, bevel=0.004),
        box('spindle_head', (0.34, 0.30, 0.45), (-0.45, 0.86, 1.86), M_STEEL2, bevel=0.006),
        cylL('spindle_nose', (-0.45, 0.86, 1.58), 0.075, 0.16, M_DARK),
        box('chiphopper', (0.9, 0.16, 0.18), (-0.12, 0.70, 0.62), M_DARK, bevel=0.004),
    ]


def build_env_tool_tray():
    """Cantilevered tray at the machine mouth where T09 waits."""
    return [
        box('tray_arm_a', (0.07, 0.58, 0.07), (0.14, 0.24, 0.80), M_STEEL, bevel=0.003),
        box('tray_arm_b', (0.07, 0.58, 0.07), (0.46, 0.24, 0.80), M_STEEL, bevel=0.003),
        box('tray_top', (0.55, 0.26, 0.045), (0.30, 0.00, 0.955), M_STEEL2, bevel=0.003),
        box('vblock_a', (0.05, 0.10, 0.05), (0.42, 0.00, 0.985), M_DARK, bevel=0.002),
        box('vblock_b', (0.05, 0.10, 0.05), (0.16, 0.00, 0.985), M_DARK, bevel=0.002),
    ]


def build_env_tool_cart():
    """Mid-depth utility cart; T03 lies on its top (z=1.145+0.055)."""
    objs = [
        box('cart_body', (0.52, 0.28, 0.99), (0.35, 0.38, 0.615), M_STEEL2, bevel=0.005),
        box('cart_top', (0.60, 0.34, 0.05), (0.35, 0.38, 1.12), M_STEEL, bevel=0.003),
        box('cart_handle', (0.05, 0.05, 0.30), (0.09, 0.38, 0.95), M_DARK, bevel=0.003),
    ]
    for cx, cy in ((0.13, 0.25), (0.57, 0.25), (0.13, 0.51), (0.57, 0.51)):
        objs.append(cylL(f'caster_{cx}_{cy}', (cx, cy, 0.06), 0.06, 0.045, M_DARK,
                        rot=(math.pi / 2, 0, 0)))
    return objs


def build_env_room():
    """Workshop floor and walls (PBR from the PolyHaven pool)."""
    floor = pbr('cnc floor', 'hangar_concrete_floor', scale=1.4)
    wall = pbr('cnc wall', 'factory_wall', scale=1.2)
    return [
        box('floor', (6.4, 5.0, 0.06), (0.2, 0.85, -0.03), floor, bevel=0),
        box('backwall', (6.4, 0.10, 2.8), (0.2, 2.95, 1.40), wall, bevel=0),
        box('rightwall', (0.10, 5.0, 2.8), (2.95, 0.85, 1.40), wall, bevel=0),
        box('leftwall', (0.10, 5.0, 2.8), (-2.55, 0.85, 1.40), wall, bevel=0),
    ]


def delete_all(objs):
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.ops.object.delete(use_global=False)


def main():
    KIT.mkdir(parents=True, exist_ok=True)
    SCENE_ENV_DIR.mkdir(parents=True, exist_ok=True)
    # Fresh .blend file: drop the default Cube/Camera/Light but keep the
    # module-level materials (clear_scene would purge their zero-user datablocks).
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # ---- build & export interactive kits one at a time (local origins) ----
    builders = {
        'MODESWITCH': build_modeswitch,
        'T09': lambda: boring_bar('T09', +1)[0],
        'POCKET9': build_pocket9,
        'T03': lambda: boring_bar('T03', -1)[0],
        'MAG': build_mag,
        'PANEL': build_panel,
    }
    for oid, fn in builders.items():
        objs = fn()
        bpy.context.view_layer.update()
        export_glb(objs, KIT_MESH / f'{oid}.glb')
        delete_all(objs)

    env_builders = {
        'machine_shell': ('机床立柱与安全门', build_env_machine_shell),
        'machine_interior': ('工作台与主轴', build_env_machine_interior),
        'tool_tray': ('刀臂托盘', build_env_tool_tray),
        'tool_cart': ('中段刀具车', build_env_tool_cart),
        'room': ('车间地面与墙体', build_env_room),
    }
    for pid, (label, fn) in env_builders.items():
        objs = fn()
        bpy.context.view_layer.update()
        export_glb(objs, SCENE_ENV_DIR / f'{SCENE_ID}_{pid}.glb')
        delete_all(objs)

    # ---- assemble the world scene from the exported GLBs (official chain
    # semantics: import + parent empty at the JSON pose, CORR counter-rotate) ----
    for oid, spec in LAYOUT['objects'].items():
        objs = import_glb(KIT_MESH / f'{oid}.glb')
        pos, wxyz = spec['pose']
        parent_to('HC_' + oid, objs, location=pos, wxyz=wxyz)
    env_poses = {'machine_shell': ((0, 0, 0), (1, 0, 0, 0)), 'machine_interior': ((0, 0, 0), (1, 0, 0, 0)),
                 'tool_tray': ((0, 0, 0), (1, 0, 0, 0)), 'tool_cart': ((0, 0, 0), (1, 0, 0, 0)),
                 'room': ((0, 0, 0), (1, 0, 0, 0))}
    env_entries = []
    for pid, (label, _) in env_builders.items():
        objs = import_glb(SCENE_ENV_DIR / f'{SCENE_ID}_{pid}.glb')
        pos, wxyz = env_poses[pid]
        parent_to('HC_ENV_' + pid, objs, location=pos, wxyz=wxyz)
        env_entries.append({'prop_id': pid, 'label': label,
                            'asset': f'scenes/{SCENE_ID}/meshes/env/{SCENE_ID}_{pid}.glb',
                            'pose': {'position_m': list(pos), 'wxyz': list(wxyz)},
                            'scale_m': [1.0, 1.0, 1.0]})
    bpy.context.view_layer.update()

    obj_parents = {n.name[3:]: n for n in bpy.data.objects
                       if n.name.startswith('HC_') and not n.name.startswith('HC_ENV_')}
    env_parents = [n for n in bpy.data.objects if n.name.startswith('HC_ENV_')]

    # ---- as-built assertions (reviewed-design evidence) ----
    verify_depths(CAM, LOOK,
                  {k: v[0] for k, v in LAYOUT['depth_rows'].items()},
                  {k: v[1] for k, v in LAYOUT['depth_rows'].items()})

    def mesh_tree(parent):
        out, stack = [], list(parent.children)
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            if n.type == 'MESH':
                out.append(n)
        return out

    subject_items = {}
    for oid, p in obj_parents.items():
        own = mesh_tree(p)
        lo, hi = objs_bbox([p] + own)
        subject_items[oid] = (lo, hi, own)
    verify_back_radial('T03', LAYOUT['objects']['T03']['pose'],
                       BACK_INFO['T03']['center_local'], BACK_INFO['T03']['normal_local'], CAM)

    # framing: interactive objects + machine massing (room walls excluded)
    bboxes = {k: (v[0], v[1]) for k, v in subject_items.items()}
    frame_items = dict(bboxes)
    frame_items['machine'] = objs_bbox([env_parents[0]] + mesh_tree(env_parents[0]))
    all_lo, all_hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for lo, hi in frame_items.values():
        for i in range(3):
            all_lo[i] = min(all_lo[i], lo[i])
            all_hi[i] = max(all_hi[i], hi[i])
    # ortho fit must respect the content offset from the view axis, not just
    # its size: use absolute projected ranges (frame is centered on the axis).
    fwd, right, up = screen_basis(CAM, LOOK)
    cs = [Vector((x, y, z)) for x in (all_lo.x, all_hi.x) for y in (all_lo.y, all_hi.y)
          for z in (all_lo.z, all_hi.z)]
    u = [(c - Vector(CAM)) @ right for c in cs]
    v = [(c - Vector(CAM)) @ up for c in cs]
    ortho = round(max(max(abs(min(u)), abs(max(u))) * 2,
                      max(abs(min(v)), abs(max(v))) * 2 * 1280 / 900) * 1.06, 3)
    verify_frame(CAM, LOOK, ortho, bboxes)

    # MODESWITCH's bbox is mostly embedded in the PANEL board; visibility is
    # judged on the protruding dial cap + pointer (the operative surface).
    lo, hi, own = subject_items['MODESWITCH']
    subject_items['MODESWITCH'] = (Vector((lo.x, 0.970, lo.z)), Vector((hi.x, 0.998, hi.z)), own)

    blocker_meshes = [m for e in env_parents for m in mesh_tree(e)]
    blocker_meshes += [m for p in obj_parents.values() for m in mesh_tree(p)]
    verify_visibility(CAM, subject_items, blocker_meshes, min_frac=0.5)

    # insertion: T09 seated at the POCKET9 anchor must bury its stud/taper in the bore
    p9 = Vector(LAYOUT['objects']['POCKET9']['pose'][0])
    t09_objs = import_glb(KIT_MESH / 'T09.glb')
    seat = parent_to('T09_SEATED', t09_objs, location=T09_SEATED)
    bpy.context.view_layer.update()
    s_lo, s_hi = objs_bbox([seat] + mesh_tree(seat))
    b_lo, b_hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for v in [(p9[0] + 0.02, p9[1] - 0.05, p9[2] - 0.05), (p9[0] + 0.16, p9[1] + 0.05, p9[2] + 0.05)]:
        for i in range(3):
            b_lo[i] = min(b_lo[i], v[i]); b_hi[i] = max(b_hi[i], v[i])
    overlap = all(s_lo[i] < b_hi[i] and s_hi[i] > b_lo[i] for i in range(3))
    print(json.dumps({'insertion_verification': {
        'anchor_world_m': [round(v, 3) for v in p9],
        't09_seated_center_m': list(T09_SEATED),
        't09_seated_bbox_m': [[round(v, 3) for v in s_lo], [round(v, 3) for v in s_hi]],
        'bore_region_m': [[round(v, 3) for v in b_lo], [round(v, 3) for v in b_hi]],
        'axis': 'x (both)', 'leading_end_inside_bore': bool(overlap),
        'stud_tip_x_m': round(s_hi.x, 3)}}, ensure_ascii=False), flush=True)
    assert overlap, 'T09 seated pose does not reach into the POCKET9 bore'
    delete_all([seat] + mesh_tree(seat))

    # ---- lights, previews, scene JSON ----
    world_bg()
    aim = Vector(LOOK)
    light_rig(Vector((0.1, 0.7, 1.3)), 2.6)
    render_preview(f'{SCENE_ID}_kit_preview.png', CAM, LOOK,
                   objs=[o for n in obj_parents.values() for o in [n] + list(n.children)] +
                        [o for e in env_parents for o in [e] + list(e.children)],
                   ortho=ortho)
    render_preview(f'{SCENE_ID}_kit_preview_persp.png', CAM, LOOK,
                   objs=[o for n in obj_parents.values() for o in [n] + list(n.children)] +
                        [o for e in env_parents for o in [e] + list(e.children)],
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
