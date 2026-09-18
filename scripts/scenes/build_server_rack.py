"""Build the server_rack scene kit (Blender 3.1.2, CPU-only, via resource_guard.py).

Outputs:
  scenes/server_rack/meshes/{SPARE,SLOT4,NODE3,ALARM,FAN}.glb      (interactive, origin-centered)
  scenes/server_rack/meshes/env/server_rack_{rackshell,floorpatch,wall,sidecart}.glb (procedural environment)
  scenes/server_rack/scene.json                                  (extended SceneSpec)
  runs/scene_v2/server_rack_kit_preview.png / ..._back.png         (self-review evidence)

LAYOUT below is the single source of truth for world poses (y=0 at rack front,
rack occupies y in [0,0.6], camera side is -y). GLB contents are built in their
own local frames; build_blender_scene.py parents them under HC_ empties at the
JSON poses, so all world placement lives here.

review#3 (round 3) fixes: back camera moved out of the wall graze zone with
deterministic rack-rear framing + ortho ray forensics in the log (verify_back_view);
FAN faceplate flush with the rack front plane; SLOT4 bay brightened to read
empty; brown-leaning 'metal_plate' PBR replaced by flat neutral gray steel.
"""
import bpy, sys, math, json, os
from pathlib import Path
from mathutils import Vector, Euler, Quaternion

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403  (pbr, flat, box, cyl, export_glb, ...)

KIT_DIR = ROOT / 'scenes/server_rack/meshes'
SCENE_ENV = scene_env('server_rack')

# ----------------------------------------------------------------------------
# LAYOUT (single source of truth)
# ----------------------------------------------------------------------------
LAYOUT = {
    'scene_id': 'server_rack',
    'title': '数据机柜排障',
    'initial_instruction': ('先把备用节点 SPARE 插进 4 号槽位 SLOT4,然后检查 3 号节点 NODE3 '
                            '背面的光纤接口,柜顶告警灯 ALARM 全程保持监控。'),
    'camera_position_m': (1.12, -1.02, 1.30),
    'camera_look_at_m': (-0.02, 0.30, 0.98),
    # review#3 fix: the old back camera (1.60, 1.50, 1.10) sat at the room wall
    # (wall spans y 1.575..1.625, x <= 1.5) and its ortho rays grazed the near
    # wall slab, occluding the rack rear for all x < +0.08 m. New position is
    # well in front of the wall (y=0.92), behind-right (azimuth ~44 deg) and
    # above the rack top (z=2.35) so the ALARM beacon clears the top cap; the
    # chosen point keeps >=1 cm of clearance on every subject sightline before
    # any wall geometry could enter the renderable depth range (probe evidence
    # in runs/scene_v2/probe_backcam_r3.py + back_view_verification in the log).
    'camera_back_position_m': (0.60, 0.92, 2.35),
    'camera_back_look_at_m': (0.0, 0.33, 1.02),
    'objects': {
        'SPARE': {'pose': ([-0.75, -0.35, 0.90], (1, 0, 0, 0)), 'label': '备用节点',
                  'color': (150, 180, 210), 'capabilities': ['point', 'insert'],
                  'anchors': {}, 'description': '1U 备用计算节点,沿导轨水平插入'},
        'SLOT4': {'pose': ([0, 0.28, 1.02], (1, 0, 0, 0)), 'label': '4 号槽位',
                  'color': (110, 200, 160), 'capabilities': ['point'],
                  'anchors': {'insertion': [0, 0, 0]}, 'description': '空槽位,带导轨与定位柱'},
        'NODE3': {'pose': ([0, 0.33, 0.55], (1, 0, 0, 0)), 'label': '3 号节点',
                  'color': (214, 160, 80), 'capabilities': ['point', 'inspect_back'],
                  'anchors': {}, 'description': '背面有四个光纤接口和提把手'},
        'ALARM': {'pose': ([0, 0.30, 1.93], (1, 0, 0, 0)), 'label': '柜顶告警灯',
                  'color': (235, 80, 80), 'capabilities': ['point', 'wait'],
                  'anchors': {}, 'description': '红色为故障,绿色为正常'},
        'FAN': {'pose': ([0, 0.28, 1.45], (1, 0, 0, 0)), 'label': '风扇模块',
                'color': (140, 140, 220), 'capabilities': ['point', 'rotate'],
                'anchors': {}, 'description': '滤网需旋转取出,顶部刻线对齐'},
    },
    'env': {  # procedural parts (origin conventions documented per builder)
        'rackshell': {'asset': 'scenes/server_rack/meshes/env/server_rack_rackshell.glb',
                      'label': '19寸机柜主体', 'position': (0, 0, 0)},
        'floorpatch': {'asset': 'scenes/server_rack/meshes/env/server_rack_floorpatch.glb',
                       'label': '防静电架空地板', 'position': (0, 0.3, 0)},
        'wall': {'asset': 'scenes/server_rack/meshes/env/server_rack_wall.glb',
                 'label': '机房墙体', 'position': (0, 1.6, 0)},
        'sidecart': {'asset': 'scenes/server_rack/meshes/env/server_rack_sidecart.glb',
                     'label': '防静电检修车', 'position': (-0.75, -0.35, 0)},
    },
    'props': {  # downloaded CC0 props: scale / target / z-mode fixed at build time
        # review#1 fixes: 'cart_board' removed (green PCB on the near-invisible mid
        # shelf read as a floating translucent teal ghost of SPARE); 'spare_rack'
        # removed (2.07 m dressing behind the rack appeared as a pure-black wedge
        # cut by the back-view right edge). 'wall_camera' moved to the -x wall
        # below the rack-top line: fully hidden behind the rack in the main view
        # and outside the back-view frame (was half-cut at its top edge).
        'cable_bundle': {'glb': 'modular_electric_cables.glb', 'label': '线缆束', 'scale': 0.40,
                         'center': (0.86, 0.24), 'base_z': 0.0, 'rot_z': 0.0},
        'wall_camera': {'glb': 'security_camera_01.glb', 'label': '墙面监控摄像头', 'scale': 1.0,
                        'center': (-1.28, 1.56), 'center_z': 1.60, 'rot_z': 180.0},
    },
}

# Dressing faceplates inside the rack shell: (z_center, height_m, style)
DRESSING = [
    (0.172, 0.0415, 'vent'), (0.262, 0.0860, 'drawer'), (0.352, 0.0860, 'server'),
    (0.442, 0.0415, 'switch'), (0.487, 0.0415, 'blank'),
    (0.617, 0.0415, 'blank'), (0.707, 0.0860, 'server'), (0.797, 0.0860, 'ups'),
    (0.887, 0.0415, 'switch'), (0.965, 0.0415, 'blank'), (1.075, 0.0415, 'vent'),
    (1.120, 0.0415, 'switch'), (1.210, 0.0860, 'server'), (1.300, 0.0860, 'drawer'),
    (1.380, 0.0415, 'blank'), (1.540, 0.0415, 'patch'), (1.630, 0.0860, 'server'),
    (1.720, 0.0860, 'blank2u'), (1.810, 0.0415, 'blank'),
]
RESERVED_BAYS = {'NODE3': (0.529, 0.571), 'SLOT4': (0.994, 1.046), 'FAN': (1.4085, 1.4915)}
CHASSIS_BACK_PLATE_Y = 0.220  # local y of the chassis back face (design constant)
NODE3_PORT_XS = [-0.096, -0.032, 0.032, 0.096]  # fiber port row on the back plate

# ---- review#3 back-view sightline model (world-space AABBs from build constants) ----
NEAR_CLIP = 0.1  # Blender ortho camera default clip_start: hits nearer than this do not render
# rack structure that could hide the ALARM beacon or NODE3's back plate
BACK_OCCLUDERS = {
    'topcap': ((-0.288, 0.012, 1.884), (0.288, 0.588, 1.900)),
    'topvent': ((-0.130, 0.220, 1.900), (0.130, 0.380, 1.924)),
    'beam_rear': ((-0.240, 0.544, 1.855), (0.240, 0.596, 1.900)),
    'post_rear_R': ((0.24, 0.54, 0.0), (0.30, 0.60, 1.90)),
    'post_rear_L': ((-0.30, 0.54, 0.0), (-0.24, 0.60, 1.90)),
    'cablemgmt': ((-0.260, 0.539, 0.14), (-0.212, 0.551, 1.86)),
    'cbundles': ((-0.247, 0.529, 0.145), (-0.165, 0.551, 1.695)),
}
# evidence sample points: ALARM above its base plate / NODE3 ports+handle+cables
ALARM_SAMPLES = [(0, 0.30, 1.936), (0, 0.30, 1.960), (0, 0.30, 1.990), (0, 0.345, 1.960),
                 (0.05, 0.30, 1.950), (-0.05, 0.30, 1.950)]
NODE3_BACK_SAMPLES = [(x, 0.556, 0.557) for x in NODE3_PORT_XS] + [
    (0.0, 0.556, 0.542), (-0.07, 0.556, 0.542), (0.07, 0.556, 0.542),
    (-0.10, 0.552, 0.532), (0.10, 0.552, 0.568), (-0.10, 0.58, 0.56), (0.10, 0.58, 0.56)]

_led_counter = [0]
def _next_led():
    _led_counter[0] += 1
    return _led_counter[0]

# ----------------------------------------------------------------------------
# shared materials
# ----------------------------------------------------------------------------
M = {}

def make_materials():
    # review#3 fix: the 'metal_plate' PBR diffuse is brown-leaning and read as
    # brown-wood on FAN/NODE3/dressing panels. Replaced with flat neutral gray
    # steel (cool tint, no texture -> no hue, no UV seam), as sanctioned by the
    # review ("flat neutral metallic"). Posts stay matte charcoal (review#1).
    M['chassis'] = flat('sr_chassis_steel', (0.225, 0.232, 0.245, 1.0), roughness=0.44, metallic=0.82)
    M['face'] = flat('sr_face_steel', (0.335, 0.345, 0.365, 1.0), roughness=0.34, metallic=0.78)
    # review#1 fix: posts/beams/topcap as matte charcoal 19-inch rack steel (the
    # worn 'metal_plate_02' diffuse read brown-wood and its 2.5x-tiled decal left
    # a hard cut-line seam down the front-left post). Flat color = no UV seam.
    M['rack'] = flat('sr_rack_frame', (0.045, 0.047, 0.053, 1.0), roughness=0.38, metallic=0.62)
    M['panel'] = flat('sr_side_panel_dark', (0.066, 0.069, 0.075, 1.0), roughness=0.50, metallic=0.35)
    M['floor'] = pbr('sr_floor', 'hangar_concrete_floor', scale=1.3)
    M['wall'] = pbr('sr_wall', 'factory_wall', scale=1.8)
    M['rubber'] = pbr('sr_rubber', 'rubber_tiles', scale=2.2)
    M['dark'] = flat('sr_dark_interior', (0.030, 0.034, 0.040, 1.0), roughness=0.92)
    M['void'] = flat('sr_slot_void', (0.014, 0.016, 0.019, 1.0), roughness=0.95)
    M['black'] = flat('sr_trim_black', (0.052, 0.055, 0.062, 1.0), roughness=0.45, metallic=0.35)
    M['rail'] = flat('sr_rail_steel', (0.56, 0.58, 0.61, 1.0), roughness=0.32, metallic=0.92)
    # review#3 fix: SLOT4 empty bay read as solid black at 4x zoom -- lighter
    # interior walls, brighter specular rails and light alignment posts so the
    # void reads as an EMPTY bay (rails/posts carry the read).
    M['bay_inner'] = flat('sr_bay_inner', (0.135, 0.145, 0.160, 1.0), roughness=0.48, metallic=0.60)
    M['rail_spec'] = flat('sr_rail_spec', (0.70, 0.72, 0.76, 1.0), roughness=0.18, metallic=0.95)
    M['post_guide'] = flat('sr_post_guide', (0.80, 0.82, 0.86, 1.0), roughness=0.30, metallic=0.12)
    M['white'] = flat('sr_index_white', (0.93, 0.93, 0.95, 1.0), roughness=0.40)
    # review#1 fix: slightly larger/brighter status LEDs so they read at preview scale
    M['led_green'] = flat('sr_led_green', (0.05, 0.30, 0.10, 1.0), emissive=(0.10, 1.00, 0.25, 1.0), emission_strength=3.2)
    M['led_green_dim'] = flat('sr_led_green_dim', (0.05, 0.30, 0.10, 1.0), emissive=(0.10, 1.00, 0.25, 1.0), emission_strength=1.9)
    M['led_amber'] = flat('sr_led_amber', (0.32, 0.18, 0.02, 1.0), emissive=(1.00, 0.55, 0.08, 1.0), emission_strength=2.7)
    M['led_teal'] = flat('sr_led_teal', (0.02, 0.30, 0.28, 1.0), emissive=(0.10, 0.95, 0.85, 1.0), emission_strength=2.2)
    M['fiber_teal'] = flat('sr_fiber_teal', (0.02, 0.35, 0.32, 1.0), emissive=(0.12, 1.00, 0.90, 1.0), emission_strength=3.0)
    M['lcd'] = flat('sr_lcd', (0.01, 0.02, 0.04, 1.0), emissive=(0.25, 0.60, 1.00, 1.0), emission_strength=0.55)
    M['screen'] = flat('sr_ups_screen', (0.02, 0.02, 0.02, 1.0), emissive=(0.55, 0.75, 0.45, 1.0), emission_strength=0.6)
    M['cable_blue'] = flat('sr_cable_blue', (0.05, 0.09, 0.22, 1.0), roughness=0.6)
    M['cable_teal'] = flat('sr_cable_teal', (0.03, 0.22, 0.20, 1.0), roughness=0.6)
    M['cable_black'] = flat('sr_cable_black', (0.03, 0.03, 0.033, 1.0), roughness=0.7)
    dome = flat('sr_dome_red', (0.55, 0.02, 0.02, 1.0), roughness=0.18, metallic=0.0,
                emissive=(1.00, 0.05, 0.05, 1.0), emission_strength=0.55)
    dome.blend_method = 'BLEND'
    dome.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.60
    M['dome_red'] = dome
    M['beacon'] = flat('sr_beacon_core', (0.35, 0.01, 0.01, 1.0), emissive=(1.00, 0.08, 0.05, 1.0), emission_strength=1.5)
    M['label_prev'] = flat('sr_label_prev', (0.96, 0.97, 0.99, 1.0), roughness=0.5,
                           emissive=(1, 1, 1, 1.0), emission_strength=0.35)

# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def _wipe_meshes():
    for o in [x for x in bpy.data.objects if x.type == 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)

def _bbox_frame(objs):
    """Combined bbox in current world space (== the GLB frame at build time).
    view_layer.update() first: matrix_world stays stale until a depsgraph pass."""
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for v in o.bound_box:
            p = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, p.x); lo.y = min(lo.y, p.y); lo.z = min(lo.z, p.z)
            hi.x = max(hi.x, p.x); hi.y = max(hi.y, p.y); hi.z = max(hi.z, p.z)
    return lo, hi

def _tri(objs):
    return sum(len(o.data.polygons) for o in objs)

# ----------------------------------------------------------------------------
# 1U chassis family (SPARE / NODE3) -- origin at chassis envelope center
# front faceplate at local -Y (toward camera side), back face at +Y (radial).
# ----------------------------------------------------------------------------
def build_chassis(kind):
    o = []
    o.append(box(f'{kind}_body', (0.430, 0.428, 0.041), (0, 0.006, 0), M['chassis'], bevel=0.0022))
    o.append(box(f'{kind}_faceplate', (0.470, 0.012, 0.044), (0, -0.214, 0), M['face'], bevel=0.0015))
    for sx in (-1, 1):  # rack ears with pull handles
        o.append(box(f'{kind}_ear{sx}', (0.024, 0.018, 0.038), (sx * 0.221, -0.216, 0), M['black'], bevel=0.0012))
        o.append(box(f'{kind}_pull{sx}', (0.006, 0.006, 0.034), (sx * 0.228, -0.219, 0), M['rail'], bevel=0))
    if kind == 'SPARE':
        o.append(cyl(f'{kind}_pwrbtn', 0.0075, 0.004, (-0.190, -0.2215, -0.004), M['black'],
                     rot=(math.pi / 2, 0, 0), vertices=24))
        o.append(cyl(f'{kind}_led1', 0.0038, 0.003, (-0.170, -0.2225, 0.007), M['led_green'],
                     rot=(math.pi / 2, 0, 0), vertices=16))
        o.append(cyl(f'{kind}_led2', 0.0038, 0.003, (-0.170, -0.2225, -0.005), M['led_green_dim'],
                     rot=(math.pi / 2, 0, 0), vertices=16))
        o.append(box(f'{kind}_idstrip', (0.046, 0.002, 0.011), (-0.122, -0.2210, -0.005), M['white'], bevel=0))
        for i in range(16):  # vent grille, right half of the faceplate
            o.append(box(f'{kind}_vent{i}', (0.0050, 0.0026, 0.0300), (0.030 + i * 0.0115, -0.2208, 0),
                         M['void'], bevel=0))
        o.append(box(f'{kind}_topline', (0.095, 0.006, 0.0025), (0.150, -0.195, 0.0218), M['white'], bevel=0))
    else:  # NODE3: populated front, fiber ports + handle + cable stubs on the back (+Y)
        for i, (x, c) in enumerate([(-0.196, 'led_green'), (-0.180, 'led_green_dim'),
                                    (-0.164, 'led_amber'), (-0.148, 'black')]):
            o.append(cyl(f'{kind}_fled{i}', 0.0036, 0.003, (x, -0.2225, 0.008),
                         M[c], rot=(math.pi / 2, 0, 0), vertices=16))
        o.append(box(f'{kind}_lcd', (0.052, 0.0035, 0.014), (-0.108, -0.2212, -0.004), M['lcd'], bevel=0))
        for i in range(14):
            o.append(box(f'{kind}_vent{i}', (0.0048, 0.0026, 0.0300), (0.030 + i * 0.0110, -0.2208, 0),
                         M['void'], bevel=0))
        # ---- back face (local y = +0.220, radial: +Y rotates to -Y under inspect_back) ----
        port_xs = [-0.096, -0.032, 0.032, 0.096]
        for i, x in enumerate(port_xs):
            o.append(cyl(f'{kind}_fport{i}', 0.0065, 0.014, (x, 0.226, 0.007), M['black'],
                         rot=(math.pi / 2, 0, 0), vertices=20))
            if i == 1:  # the teal fiber port (live link)
                # review#3 fix: the old 6.8 mm ring hid behind its own plug box
                # when viewed from the elevated back camera (0 teal px in frame);
                # enlarged to a 21 mm collar standing proud of the plug so the
                # live-link ring reads in the back-view evidence.
                o.append(cyl(f'{kind}_fring{i}', 0.0105, 0.005, (x, 0.2345, 0.007), M['fiber_teal'],
                             rot=(math.pi / 2, 0, 0), vertices=20))
            else:
                o.append(cyl(f'{kind}_fcap{i}', 0.0030, 0.004, (x, 0.2322, 0.007),
                             M['cable_blue' if i % 2 else 'cable_black'],
                             rot=(math.pi / 2, 0, 0), vertices=12))
        o.append(box(f'{kind}_bhandle', (0.150, 0.012, 0.016), (0, 0.226, -0.008), M['black'], bevel=0.001))
        for sx in (-1, 1):
            o.append(box(f'{kind}_bstand{sx}', (0.014, 0.008, 0.020), (sx * 0.062, 0.2225, -0.008),
                         M['rail'], bevel=0))
        for i, x in enumerate(port_xs[:1] + port_xs[2:]):  # 3 drooping cable stubs
            theta = math.radians(-55 - 8 * (i % 2))
            d = Vector((0, math.cos(theta), math.sin(theta)))
            base = Vector((x, 0.233, 0.007))
            c0 = base + d * 0.030
            o.append(cyl(f'{kind}_stub{i}', 0.0042, 0.060, tuple(c0),
                         M[['cable_teal', 'cable_blue', 'cable_black'][i]], rot=(theta, 0, 0), vertices=12))
            o.append(box(f'{kind}_plug{i}', (0.011, 0.014, 0.011), tuple(base + d * 0.004),
                         M['black'], bevel=0))
        o.append(box(f'{kind}_bvent', (0.150, 0.004, 0.024), (0, 0.2215, 0.0), M['void'], bevel=0))
    return o

# ----------------------------------------------------------------------------
# SLOT4 -- empty 1U bay, origin at bay volume center (x ±0.238, y ±0.235, z ±0.028)
# ----------------------------------------------------------------------------
def build_slot4():
    o = []
    # review#3 fix: interior no longer near-black (M['void']) -- lighter metal
    # walls + specular rails + light alignment posts read as an EMPTY bay.
    o.append(box('slot4_void', (0.400, 0.400, 0.044), (0, 0.020, 0), M['bay_inner'], bevel=0))
    for sz in (-1, 1):  # bezel lips
        o.append(box(f'slot4_lip{sz}', (0.476, 0.012, 0.004), (0, -0.229, sz * 0.026),
                     M['black'], bevel=0.0008))
    for sx in (-1, 1):  # bezel side posts
        o.append(box(f'slot4_post{sx}', (0.006, 0.012, 0.056), (sx * 0.235, -0.229, 0),
                     M['black'], bevel=0.0008))
    for sx in (-1, 1):  # alignment posts at the mouth (light tone, review#3)
        o.append(cyl(f'slot4_align{sx}', 0.004, 0.020, (sx * 0.190, -0.212, 0), M['post_guide'], vertices=14))
    for sx in (-1, 1):  # guide rails, inner faces at x = ±0.217 (chassis body is 0.430 wide)
        for sz in (-1, 1):
            o.append(box(f'slot4_rail{sx}{sz}', (0.008, 0.400, 0.006), (sx * 0.221, 0.0, sz * 0.0175),
                         M['rail_spec'], bevel=0.0006))
    o.append(box('slot4_backplate', (0.440, 0.004, 0.046), (0, 0.232, 0), M['bay_inner'], bevel=0))
    return o

# ----------------------------------------------------------------------------
# ALARM -- dome beacon, origin at base-plate center
# ----------------------------------------------------------------------------
def build_alarm():
    o = []
    o.append(cyl('alarm_base', 0.055, 0.012, (0, 0, 0.006), M['black'], vertices=32))
    o.append(cyl('alarm_ring', 0.047, 0.006, (0, 0, 0.014), M['rail'], vertices=32))
    o.append(cyl('alarm_beacon', 0.013, 0.028, (0, 0, 0.028), M['beacon'], vertices=20))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.041, location=(0, 0, 0.019), segments=32, ring_count=16)
    dome = bpy.context.object; dome.name = 'alarm_dome'
    dome.data.materials.append(M['dome_red']); o.append(dome)
    o.append(cyl('alarm_status', 0.004, 0.004, (0.046, 0, 0.013), M['led_green'], vertices=12))
    return o

# ----------------------------------------------------------------------------
# FAN -- 2U fan tray, origin at module center.
# review#3 fix: faceplate flush with the rack front plane -- front face at local
# y = -0.236 -> world y = 0.28 - 0.236 = 0.044 (SLOT4 mouth plane is 0.045); the
# module was previously recessed ~10 cm behind the front posts. JSON pose is
# unchanged; only the GLB-internal geometry moved forward.
# ----------------------------------------------------------------------------
def build_fan():
    o = []
    o.append(box('fan_body', (0.430, 0.422, 0.078), (0, -0.011, 0), M['chassis'], bevel=0.0022))
    o.append(box('fan_faceplate', (0.470, 0.014, 0.083), (0, -0.229, 0), M['face'], bevel=0.0015))
    for sx in (-1, 1):
        o.append(cyl(f'fan_thumb{sx}', 0.008, 0.007, (sx * 0.205, -0.2365, 0.0335), M['black'],
                     rot=(math.pi / 2, 0, 0), vertices=16))
    for cx in (-0.105, 0.105):  # two fan hubs behind ring grilles
        o.append(cyl(f'fan_recess{cx}', 0.0455, 0.003, (cx, -0.2340, 0), M['void'],
                     rot=(math.pi / 2, 0, 0), vertices=32))
        for k in range(5):  # blades
            a = math.radians(k * 72)
            o.append(box(f'fan_blade{cx}{k}', (0.004, 0.002, 0.024),
                         (cx + math.sin(a) * 0.020, -0.2325, math.cos(a) * 0.020), M['rail'], bevel=0))
        for r in (0.0375, 0.0255, 0.0135):  # concentric grille rings
            # review#3 fix: light steel rings over the dark recess raise contrast
            bpy.ops.mesh.primitive_torus_add(location=(cx, -0.2305, 0), rotation=(math.pi / 2, 0, 0),
                                             major_radius=r, minor_radius=0.0022,
                                             major_segments=32, minor_segments=6)
            t = bpy.context.object; t.name = f'fan_ring{cx}{r}'
            t.data.materials.append(M['rail']); o.append(t)
        o.append(cyl(f'fan_hub{cx}', 0.0100, 0.008, (cx, -0.2300, 0), M['rail'],
                     rot=(math.pi / 2, 0, 0), vertices=20))
    o.append(box('fan_topline', (0.055, 0.006, 0.003), (0.190, -0.2310, 0.0415), M['white'], bevel=0))
    return o

# ----------------------------------------------------------------------------
# rack shell -- local origin at rack front-bottom-center (x ±0.30, y 0..0.60, z 0..1.90)
# ----------------------------------------------------------------------------
def _dressing_unit(zc, h, style, idx):
    o = []
    nm = f'dress{idx:02d}'
    o.append(box(f'{nm}_plate', (0.465, 0.028, h), (0, 0.034, zc), M['face'], bevel=0.0012))
    o.append(box(f'{nm}_body', (0.430, 0.140, h - 0.004), (0, 0.115, zc), M['dark'], bevel=0))
    y = 0.0195
    if style in ('vent', 'server', 'drawer'):
        n = 16 if style != 'drawer' else 10
        for i in range(n):
            x = -0.205 + i * (0.41 / max(n - 1, 1))
            if style == 'drawer' and abs(x) < 0.09:
                continue
            o.append(box(f'{nm}_slot{i}', (0.006, 0.002, h - 0.012), (x, y, zc), M['void'], bevel=0))
    if style == 'switch':
        for i in range(10):
            o.append(box(f'{nm}_port{i}', (0.022, 0.003, 0.014), (-0.190 + i * 0.042, y, zc - 0.008),
                         M['void'], bevel=0))
    if style == 'patch':
        for i in range(12):
            x = -0.198 + (i % 6) * 0.0792
            zoff = zc + (0.009 if i < 6 else -0.009)
            o.append(box(f'{nm}_port{i}', (0.026, 0.003, 0.012), (x, y, zoff), M['void'], bevel=0))
    if style in ('drawer', 'server'):
        o.append(box(f'{nm}_handle', (0.150, 0.006, 0.014), (0.0, y - 0.002, zc), M['black'], bevel=0.0006))
        for sx in (-1, 1):
            o.append(box(f'{nm}_latch{sx}', (0.024, 0.005, 0.016), (sx * 0.178, y, zc), M['rail'], bevel=0))
    if style == 'ups':
        o.append(box(f'{nm}_screen', (0.084, 0.004, 0.026), (-0.15, y, zc), M['screen'], bevel=0))
        o.append(box(f'{nm}_vents', (0.170, 0.003, h - 0.014), (0.105, y, zc), M['void'], bevel=0))
    ledpat = ('led_green', 'led_green_dim', 'led_amber')
    if style in ('server', 'switch', 'ups', 'patch', 'vent'):
        for j in range(3):
            _next_led()
            k = (idx + j) % 3
            on = ((idx * 7 + j * 5) % 4) != 0
            mat = M[ledpat[k]] if on else M['black']
            o.append(cyl(f'{nm}_led{j}', 0.0034, 0.003, (0.196 + j * 0.013, y - 0.0005, zc + h / 2 - 0.009),
                         mat, rot=(math.pi / 2, 0, 0), vertices=12))
    for sx in (-1, 1):  # mounting thumbscrews
        o.append(cyl(f'{nm}_screw{sx}', 0.006, 0.004, (sx * 0.243, y + 0.001, zc), M['black'],
                     rot=(math.pi / 2, 0, 0), vertices=12))
    return o

def build_rackshell():
    o = []
    for sx in (-1, 1):  # four corner posts
        for fy, py in ((0, 0.03), (1, 0.57)):
            o.append(box(f'post{sx}{fy}', (0.060, 0.060, 1.900), (sx * 0.27, py, 0.95),
                         M['rack'], bevel=0.002))
            yface = 0.0015 if fy == 0 else 0.5985
            z = 0.170
            while z < 1.845:  # 10 mm square hole pairs every 1U
                for hoff in (-0.0145, 0.0145):
                    o.append(box(f'hole{sx}{fy}{z:.3f}{hoff}', (0.0104, 0.006, 0.0104),
                                 (sx * 0.27 + hoff, yface, z), M['void'], bevel=0))
                z += 0.0445
    o.append(box('plinth', (0.576, 0.576, 0.100), (0, 0.30, 0.05), M['dark'], bevel=0.002))
    o.append(box('plinth_trim', (0.560, 0.004, 0.088), (0, 0.012, 0.056), M['black'], bevel=0))
    o.append(box('beam_front', (0.480, 0.052, 0.045), (0, 0.030, 1.8775), M['rack'], bevel=0.002))
    o.append(box('beam_rear', (0.480, 0.052, 0.045), (0, 0.570, 1.8775), M['rack'], bevel=0.002))
    # top cap + raised vent housing (housing top at z = 1.924; ALARM base sits on it)
    o.append(box('topcap', (0.576, 0.576, 0.016), (0, 0.30, 1.892), M['rack'], bevel=0.002))
    o.append(box('topvent', (0.260, 0.160, 0.024), (0, 0.30, 1.912), M['dark'], bevel=0.0015))
    for i in range(9):
        o.append(box(f'topvent_slot{i}', (0.012, 0.002, 0.010), (-0.090 + i * 0.0225, 0.218, 1.9195),
                     M['void'], bevel=0))
    # left side perforated panel; right side intentionally open (airflow + sight-line)
    o.append(box('sidepanel_l', (0.008, 0.576, 1.730), (-0.296, 0.30, 0.985), M['panel'], bevel=0.0015))
    # interior rear cable-management ladder + vertical cable bundles
    o.append(box('cablemgr_bar', (0.010, 0.012, 1.700), (-0.252, 0.545, 1.00), M['black'], bevel=0))
    for i in range(12):
        o.append(box(f'cablemgr_ring{i}', (0.048, 0.010, 0.009), (-0.236, 0.545, 0.18 + i * 0.140),
                     M['black'], bevel=0))
    for i in range(3):
        o.append(cyl(f'cbundle{i}', 0.011, 1.55, (-0.236 + i * 0.030, 0.540, 0.92),
                     M[('cable_black', 'cable_blue', 'cable_teal')[i]], vertices=10))
    for idx, (zc, h, style) in enumerate(DRESSING):
        o.extend(_dressing_unit(zc, h, style, idx))
    return o

# ----------------------------------------------------------------------------
# floor patch / wall / side cart
# ----------------------------------------------------------------------------
def build_floorpatch():
    o = [box('floor_tile', (3.0, 3.0, 0.030), (0, 0, -0.015), M['floor'], bevel=0.003)]
    for i in (-1, 1):  # raised-floor seam strips
        o.append(box(f'seam_ns{i}', (0.006, 3.0, 0.0025), (i * 0.5, 0, 0.0012), M['black'], bevel=0))
        o.append(box(f'seam_ew{i}', (3.0, 0.006, 0.0025), (0, i * 0.5, 0.0012), M['black'], bevel=0))
    return o

def build_wall():
    o = [box('wall_panel', (3.0, 0.05, 2.5), (0, 0, 1.25), M['wall'], bevel=0.004)]
    o.append(box('wall_cabletray', (2.4, 0.085, 0.05), (0, -0.065, 2.16), M['black'], bevel=0.002))
    for i in range(5):
        o.append(box(f'wall_conduit{i}', (0.030, 0.012, 1.55), (-0.98 + i * 0.49, -0.032, 1.325),
                     M['rail'], bevel=0))
    return o

def build_sidecart():
    o = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(cyl(f'cart_caster{sx}{sy}', 0.028, 0.050, (sx * 0.190, sy * 0.140, 0.025),
                         M['black'], vertices=16))
            o.append(box(f'cart_post{sx}{sy}', (0.020, 0.020, 0.800), (sx * 0.222, sy * 0.172, 0.450),
                         M['black'], bevel=0.0015))
    o.append(box('cart_bottom', (0.470, 0.370, 0.012), (0, 0, 0.106), M['chassis'], bevel=0.0015))
    o.append(box('cart_mid', (0.480, 0.380, 0.012), (0, 0, 0.450), M['chassis'], bevel=0.0015))
    o.append(box('cart_top', (0.500, 0.400, 0.012), (0, 0, 0.866), M['chassis'], bevel=0.0015))
    o.append(box('cart_mat', (0.460, 0.360, 0.006), (0, 0, 0.875), M['rubber'], bevel=0.0008))
    o.append(box('cart_handle', (0.440, 0.016, 0.016), (0, -0.196, 0.830), M['black'], bevel=0.0012))
    for sx in (-1, 1):
        o.append(box(f'cart_grip{sx}', (0.016, 0.020, 0.070), (sx * 0.205, -0.196, 0.790), M['rail'], bevel=0.001))
    o.append(box('cart_label', (0.060, 0.002, 0.020), (0.170, 0.201, 0.450), M['white'], bevel=0))
    return o

# ----------------------------------------------------------------------------
# geometry self-checks
# ----------------------------------------------------------------------------
def verify_bay_map():
    spans = sorted([(zc - h / 2, zc + h / 2) for zc, h, _ in DRESSING])
    for a, b in zip(spans, spans[1:]):
        assert b[0] - a[1] > 0.0025, f'dressing overlap: {a} {b}'
    for rid, (z0, z1) in RESERVED_BAYS.items():
        for a, b in spans:
            assert not (a < z1 and z0 < b), f'{rid} bay overlaps dressing {a, b}'
        assert 0.15 < z0 and z1 < 1.856, f'{rid} outside rack interior'
    print(json.dumps({'bay_map': 'ok', 'dressing_units': len(DRESSING), 'reserved_bays': RESERVED_BAYS}),
          flush=True)

def verify_insertion(spare_bbox, slot_bbox):
    """Anchor check with real mesh bboxes (SLOT4 pose rotation is identity)."""
    slo = LAYOUT['objects']['SLOT4']
    anchor = Vector(slo['anchors']['insertion'])
    slo_pos = Vector(slo['pose'][0])
    goal = slo_pos + anchor                       # where the SPARE origin lands
    g_lo = goal + spare_bbox[0]; g_hi = goal + spare_bbox[1]
    w_lo = slot_bbox[0] + slo_pos; w_hi = slot_bbox[1] + slo_pos
    inside = all(g_lo[i] >= w_lo[i] - 1e-6 and g_hi[i] <= w_hi[i] + 1e-6 for i in range(3))
    margins = {ax: [round(g_lo[i] - w_lo[i], 4), round(w_hi[i] - g_hi[i], 4)]
               for i, ax in enumerate('xyz')}
    out = {'anchor_local': list(slo['anchors']['insertion']),
           'goal_position_m': [round(x, 4) for x in goal],
           'spare_seated_bbox_m': [[round(x, 4) for x in g_lo], [round(x, 4) for x in g_hi]],
           'slot4_world_bbox_m': [[round(x, 4) for x in w_lo], [round(x, 4) for x in w_hi]],
           'clearance_m_per_axis': margins, 'fully_seated_inside': bool(inside)}
    print(json.dumps({'insertion_verification': out}, ensure_ascii=False), flush=True)
    assert inside, 'SPARE ghost would not seat fully inside SLOT4 volume'

def verify_node3(node_objs):
    """Chassis envelope must sit inside the rack with the back plate at y=0.55.
    Cable stubs intentionally droop out of the OPEN rack rear into the aisle."""
    pose = Vector(LAYOUT['objects']['NODE3']['pose'][0])
    chassis = [o for o in node_objs if 'stub' not in o.name and 'plug' not in o.name]
    c_lo, c_hi = _bbox_frame(chassis)
    w_lo = pose + c_lo; w_hi = pose + c_hi
    f_lo, f_hi = _bbox_frame(node_objs)
    rack = ((-0.30, 0.0, 0.0), (0.30, 0.60, 1.90))
    inside = all(w_lo[i] >= rack[0][i] and w_hi[i] <= rack[1][i] for i in range(3))
    back_face = pose.y + CHASSIS_BACK_PLATE_Y
    out = {'chassis_world_bbox_m': [[round(x, 4) for x in w_lo], [round(x, 4) for x in w_hi]],
           'full_bbox_with_cables_m': [[round(x, 4) for x in (pose + f_lo)], [round(x, 4) for x in (pose + f_hi)]],
           'back_plate_face_y': round(back_face, 4), 'chassis_inside_rack_volume': bool(inside),
           'cables_exit_open_rear': True,
           'back_face_radial': 'back normal is +Y (horizontal); inspect_back rotates 180 deg about local Z -> faces camera'}
    print(json.dumps({'node3_verification': out}, ensure_ascii=False), flush=True)
    assert inside, 'NODE3 chassis escapes the rack volume'
    assert abs(back_face - 0.55) < 0.005, 'NODE3 back face not at y=0.55'
    assert pose.y + f_hi.y < 0.66, 'cable stubs reach too far behind the rack'

# ----------------------------------------------------------------------------
# preview composition (mirrors build_blender_scene.py: HC_ / HC_ENV_ parents)
# ----------------------------------------------------------------------------
def _rotated_bbox(lo, hi, q):
    corners = [q @ Vector((x, y, z))
               for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    return (Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners))),
            Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners))))

def place_prop(pid, objs, spec):
    """Place a downloaded prop: imports arrive tipped by the glTF importer's X
    rotation; parent_to's CORR cancels it, so bbox math must measure the prop in
    its STORED Z-up frame -> apply CORR before the intended Z rotation."""
    s = spec['scale']
    q = Quaternion((0, 0, 1), math.radians(spec.get('rot_z', 0.0)))
    rlo, rhi = _rotated_bbox(*_bbox_frame(objs), q @ CORR)
    rc = (rlo + rhi) / 2
    loc = Vector((spec['center'][0] - s * rc.x, spec['center'][1] - s * rc.y, 0.0))
    if 'center_z' in spec:
        loc.z = spec['center_z'] - s * rc.z
    else:
        loc.z = spec['base_z'] - s * rlo.z
    p = parent_to('HC_ENV_' + pid, objs, location=loc, wxyz=q.normalized())
    p.scale = (s, s, s)
    return p, loc

def add_label(text, pos, cam_pos, look):
    bpy.ops.object.text_add(location=Vector(pos))
    t = bpy.context.object; t.name = 'LBL_' + text
    d = t.data
    d.body = text; d.size = 0.062; d.align_x = 'CENTER'; d.align_y = 'CENTER'; d.extrude = 0.0012
    # text glyphs face local +Z -> point it AT the camera, otherwise backface-culled
    t.rotation_euler = (Vector(cam_pos) - Vector(look)).to_track_quat('Z', 'Y').to_euler()
    d.materials.append(M['label_prev'])
    return t

def add_leader(a, b, name):
    """Thin white pointer from a label down into the rack interior (review#1 fix:
    NODE3's label hung over a static blank filler with no link to the real node)."""
    va, vb = Vector(a), Vector(b)
    axis = vb - va
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0035, depth=axis.length,
                                        location=(va + vb) / 2, vertices=10)
    o = bpy.context.object; o.name = 'LEAD_' + name
    o.rotation_euler = axis.to_track_quat('Z', 'X').to_euler()
    o.data.materials.append(M['label_prev'])
    return o

# ----------------------------------------------------------------------------
# deterministic preview framing (review#1 fix: cart + SPARE + ALARM must fit
# with ~8% margin on every side; final ortho reported in the log)
# ----------------------------------------------------------------------------
def _screen_basis(cam_pos, look):
    """Camera-local axes matching Blender's track-quat('-Z','Y'): x = screen right."""
    fwd = (Vector(look) - Vector(cam_pos)).normalized()
    zloc = -fwd
    yup = Vector((0, 0, 1))
    yloc = (yup - yup.dot(zloc) * zloc).normalized()  # screen up
    xloc = yloc.cross(zloc).normalized()              # screen right
    return fwd, xloc, yloc

def _proj_range(lo, hi, cam_pos, x, y):
    us, vs = [], []
    for cx in (lo.x, hi.x):
        for cy in (lo.y, hi.y):
            for cz in (lo.z, hi.z):
                d = Vector((cx, cy, cz)) - Vector(cam_pos)
                us.append(d.dot(x)); vs.append(d.dot(y))
    return min(us), max(us), min(vs), max(vs)

def fit_frame(cam_pos, look_seed, bbox_list, res, margin=0.08, iters=8):
    """Center the content on the camera axis, then size the ortho so every bbox
    keeps >= `margin` (fraction of frame) on all four sides. Returns (look, ortho)."""
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
    span_u = max(us) - min(us)
    span_v = max(vs) - min(vs)
    ortho = max(span_u / (1 - 2 * margin), span_v * aspect / (1 - 2 * margin))
    return look, ortho

def verify_frame(cam_pos, look, ortho, items, res, margin=0.08):
    """Print + assert per-item pixel bounds and frame margins (log evidence)."""
    _, x, y = _screen_basis(cam_pos, look)
    half_u, half_v = ortho / 2, ortho / 2 * res[1] / res[0]
    out = {}
    for name, (lo, hi) in items.items():
        u0, u1, v0, v1 = _proj_range(lo, hi, cam_pos, x, y)
        px0 = int(round((u0 + half_u) / ortho * res[0]))
        px1 = int(round((u1 + half_u) / ortho * res[0]))
        py0 = int(round((half_v - v1) / (2 * half_v) * res[1]))
        py1 = int(round((half_v - v0) / (2 * half_v) * res[1]))
        m = {'px': [px0, py0, px1, py1],
             'margin_pct': {'left': round(px0 / res[0] * 100, 1),
                            'right': round((res[0] - px1) / res[0] * 100, 1),
                            'top': round(py0 / res[1] * 100, 1),
                            'bottom': round((res[1] - py1) / res[1] * 100, 1)}}
        out[name] = m
    worst = min(min(v['margin_pct'].values()) for v in out.values())
    print(json.dumps({'frame_verification': {'res': list(res), 'ortho_scale_m': round(ortho, 3),
                                              'items': out, 'worst_margin_pct': worst}},
                     ensure_ascii=False), flush=True)
    assert worst >= margin * 100 - 0.5, f'framing margin below {margin*100:.0f}%: {out}'

# ----------------------------------------------------------------------------
# review#3 back-view evidence checks (orthographic ray forensics)
# ----------------------------------------------------------------------------
def _seg_box_hit(p, d, tmax, lo, hi, tmin=1e-4):
    """Segment p + t*d for t in [tmin, tmax] vs AABB [lo, hi] (slab method)."""
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

def _bbox_grid(lo, hi, nu=7, nv=5, nw=7):
    def fr(a, b, n):
        return [a] if n == 1 else [a + (b - a) * k / (n - 1) for k in range(n)]
    return [Vector((x, y, z)) for x in fr(lo.x, hi.x, nu)
            for y in fr(lo.y, hi.y, nv) for z in fr(lo.z, hi.z, nw)]

def _obj_world_bbox(obj):
    cs = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))

def verify_back_view(cam_pos, look, ortho, res, subjects, wall_objs, node3_children):
    """Print + assert the review#3 blocking evidence for the back view:

    1. WALL GRAZE: no wall-GLB geometry between the camera and any subject --
       for a 7x5x7 grid over every subject bbox, the ortho ray toward the camera
       plane (direction -fwd, length = subject depth) must not hit any wall
       object's bbox at depth >= clip_start. Wall parts beyond the subject or
       laterally outside the frame cannot occlude; hits nearer than clip_start
       are near-clipped by Blender and do not render.
    2. NODE3's fiber port row (fport/fring/fcap meshes) must project >= 60 px.
    3. ALARM beacon + NODE3 back plate unoccluded by rack structure (topcap /
       topvent / rear beam / rear posts / cable management), same ray test.
    """
    cam = Vector(cam_pos)
    fwd, xloc, yloc = _screen_basis(cam_pos, look)
    hu, hv = ortho / 2, ortho / 2 * res[1] / res[0]
    bpy.context.view_layer.update()
    wall_boxes = {o.name: _obj_world_bbox(o) for o in wall_objs if o.type == 'MESH'}
    # -- 1. wall sightlines ---------------------------------------------------
    hits, tested = [], 0
    for name, (lo, hi) in subjects.items():
        for p in _bbox_grid(lo, hi):
            depth = (p - cam).dot(fwd)
            if depth <= NEAR_CLIP:
                continue
            tested += 1
            for wname, (wlo, whi) in wall_boxes.items():
                if _seg_box_hit(p, -fwd, depth, wlo, whi, tmin=NEAR_CLIP):
                    hits.append([name, wname, [round(v, 3) for v in p]])
    # -- 2. fiber port row pixel width ---------------------------------------
    port_objs = [o for o in node3_children
                 if any(k in o.name for k in ('fport', 'fring', 'fcap'))]
    assert port_objs, 'fiber port meshes not found in imported NODE3'
    plo, phi = _bbox_frame(port_objs)
    pu0, pu1, _, _ = _proj_range(plo, phi, cam_pos, xloc, yloc)
    port_px = (pu1 - pu0) / ortho * res[0]
    # -- 3. ALARM / NODE3-back structural occlusion ---------------------------
    occ = []
    for label, pts in (('ALARM', ALARM_SAMPLES), ('NODE3_back', NODE3_BACK_SAMPLES)):
        for p in pts:
            depth = (Vector(p) - cam).dot(fwd)
            if depth <= NEAR_CLIP:
                continue
            for bname, (blo, bhi) in BACK_OCCLUDERS.items():
                if _seg_box_hit(Vector(p), -fwd, depth, Vector(blo), Vector(bhi), tmin=NEAR_CLIP):
                    occ.append([label, bname, p])
    out = {'camera_position_m': [round(v, 4) for v in cam],
           'ortho_scale_m': round(ortho, 4),
           'frame_half_extents_m': {'u': round(hu, 3), 'v': round(hv, 3)},
           'near_clip_m': NEAR_CLIP,
           'wall_parts_tested': sorted(wall_boxes),
           'subject_sightlines_tested': tested,
           'wall_hits_between_camera_and_subject': hits,
           'fiber_port_row_px': round(port_px, 1),
           'alarm_node3_occlusion_hits': occ}
    print(json.dumps({'back_view_verification': out}, ensure_ascii=False), flush=True)
    assert not hits, f'wall geometry occludes subject sightlines: {hits}'
    assert port_px >= 60, f'fiber port row only {port_px:.1f}px wide (<60px)'
    assert not occ, f'rack structure occludes ALARM/NODE3 evidence points: {occ}'

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    clear_scene()
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
    sc.cycles.use_denoising = True
    make_materials()
    verify_bay_map()

    def build_and_export(name, fn, out_path, verify=None):
        objs = fn()
        bbox = _bbox_frame(objs)
        if verify:
            verify(objs)
        tris = _tri(objs)
        path = export_glb(objs, out_path)
        rec = {'name': name, 'bbox': bbox, 'tris': tris, 'path': path, 'objs': objs}
        _wipe_meshes()
        return rec

    exported = {}
    exported['SPARE'] = build_and_export('SPARE', lambda: build_chassis('SPARE'), KIT_DIR / 'SPARE.glb')
    exported['SLOT4'] = build_and_export('SLOT4', build_slot4, KIT_DIR / 'SLOT4.glb')
    verify_insertion(exported['SPARE']['bbox'], exported['SLOT4']['bbox'])
    exported['NODE3'] = build_and_export('NODE3', lambda: build_chassis('NODE3'),
                                         KIT_DIR / 'NODE3.glb', verify=verify_node3)
    exported['ALARM'] = build_and_export('ALARM', build_alarm, KIT_DIR / 'ALARM.glb')
    exported['FAN'] = build_and_export('FAN', build_fan, KIT_DIR / 'FAN.glb')
    for part, fn in (('rackshell', build_rackshell), ('floorpatch', build_floorpatch),
                     ('wall', build_wall), ('sidecart', build_sidecart)):
        exported[part] = build_and_export(part, fn, SCENE_ENV / f'server_rack_{part}.glb')

    table = [{'part': k, 'glb': str(v['path'].relative_to(ROOT)), 'mesh_tris': v['tris'],
              'bytes': v['path'].stat().st_size} for k, v in exported.items()]
    print(json.dumps({'exported': table}, indent=1), flush=True)
    for k in ('SPARE', 'SLOT4', 'NODE3', 'ALARM', 'FAN'):
        assert exported[k]['tris'] < 150000, f'{k} over triangle budget'

    # ---------------- full-scene composition preview ----------------
    clear_scene()  # purges 0-user materials -> rebuild the preview-only ones
    M['label_prev'] = flat('sr_label_prev', (0.96, 0.97, 0.99, 1.0), roughness=0.5,
                           emissive=(1, 1, 1, 1.0), emission_strength=0.35)
    world_bg((0.44, 0.50, 0.58, 1.0), strength=0.52)
    parents, children = {}, {}
    for oid, spec in LAYOUT['objects'].items():
        objs = import_glb(exported[oid]['path'])
        pos, wxyz = spec['pose']
        parents[oid] = parent_to('HC_' + oid, objs, location=pos, wxyz=wxyz)
        parents[oid]['holocue_object_id'] = oid
        children[oid] = objs
    for pid, spec in LAYOUT['env'].items():
        objs = import_glb(ROOT / spec['asset'])
        parents[pid] = parent_to('HC_ENV_' + pid, objs, location=spec['position'])
        parents[pid]['holocue_prop_id'] = pid
        children[pid] = objs
    prop_pos = {}
    for pid, spec in LAYOUT['props'].items():
        objs = import_glb(ENV / spec['glb'])
        parents[pid], loc = place_prop(pid, objs, spec)
        prop_pos[pid] = loc
        children[pid] = objs

    # round-trip check: the re-imported SPARE must sit centered on its JSON pose
    lo, hi = _bbox_frame(children['SPARE'])
    center = (lo + hi) / 2
    pose = Vector(LAYOUT['objects']['SPARE']['pose'][0])
    lat = (abs(center.x - pose.x), abs(center.y - pose.y))
    print(json.dumps({'spare_roundtrip_center': [round(v, 4) for v in center],
                      'json_pose': list(pose), 'lateral_offset_m': [round(v, 4) for v in lat],
                      'within_1cm': bool(max(lat) < 0.01)}), flush=True)
    assert max(lat) < 0.01, 're-imported SPARE not centered on its JSON pose'

    light_rig(Vector((0.05, 0.25, 1.05)), extent=2.3, energy=1.7)

    # labels float in front of the rack face (y<0) so panels cannot occlude them
    labels = {'SPARE': (-0.75, -0.35, 0.968), 'SLOT4': (0, -0.05, 1.078),
              'NODE3': (0, -0.05, 0.625), 'ALARM': (0, 0.30, 2.030), 'FAN': (0, -0.05, 1.508)}
    lab_objs = [add_label(t, p, LAYOUT['camera_position_m'], LAYOUT['camera_look_at_m'])
                for t, p in labels.items()]
    # NODE3 label leader: from under the label down INTO the bay opening, ending at
    # the real NODE3 faceplate top edge (bay gap z 0.508..0.596 -> no panel clipping)
    lead_objs = [add_leader((0, -0.048, 0.607), (0, 0.10, 0.573), 'NODE3')]

    # review#1 fix: deterministic reframe -- whole cart + SPARE + rack + ALARM +
    # every label fit with >=8% margin on all sides (auto-fit only guaranteed 4%).
    RES = (1600, 1120)
    fit_items = {k: _bbox_frame(children[k]) for k in ('sidecart', 'SPARE', 'rackshell', 'ALARM')}
    fit_items['labels'] = _bbox_frame(lab_objs + lead_objs)
    look_fit, ortho_fit = fit_frame(Vector(LAYOUT['camera_position_m']),
                                    Vector(LAYOUT['camera_look_at_m']),
                                    list(fit_items.values()), RES)
    LAYOUT['camera_look_at_m'] = [round(v, 4) for v in look_fit]
    used = render_preview('server_rack_kit_preview.png', LAYOUT['camera_position_m'],
                          LAYOUT['camera_look_at_m'], ortho=ortho_fit, res=RES, samples=64)
    ortho = ortho_fit
    verify_frame(LAYOUT['camera_position_m'], LAYOUT['camera_look_at_m'], ortho_fit,
                 fit_items, RES)

    # review#3 fix: deterministic framing for the back view too -- subject is the
    # rack rear (rackshell + ALARM + NODE3 incl. drooping cables), centered with
    # >=8% margins (the old ortho='auto' fit the scale but never centered, so the
    # rack top + ALARM fell out of frame and a dead-black room void dominated).
    back_cam = Vector(LAYOUT['camera_back_position_m'])
    back_items = {k: _bbox_frame(children[k]) for k in ('rackshell', 'ALARM', 'NODE3')}
    look_back, ortho_back = fit_frame(back_cam, Vector(LAYOUT['camera_back_look_at_m']),
                                      list(back_items.values()), RES)
    LAYOUT['camera_back_look_at_m'] = [round(v, 4) for v in look_back]
    render_preview('server_rack_kit_preview_back.png', LAYOUT['camera_back_position_m'],
                   LAYOUT['camera_back_look_at_m'], ortho=ortho_back, res=RES, samples=64)
    verify_frame(LAYOUT['camera_back_position_m'], LAYOUT['camera_back_look_at_m'],
                 ortho_back, back_items, RES)
    verify_back_view(LAYOUT['camera_back_position_m'], LAYOUT['camera_back_look_at_m'],
                     ortho_back, RES, back_items, children['wall'], children['NODE3'])

    # ---------------- scene JSON ----------------
    def obj_entry(oid):
        s = LAYOUT['objects'][oid]
        pos, wxyz = s['pose']
        return {'object_id': oid, 'label': s['label'], 'asset': f'scenes/server_rack/meshes/{oid}.glb',
                'pose': {'position_m': [round(v, 4) for v in pos], 'wxyz': list(wxyz)},
                'color': list(s['color']), 'capabilities': s['capabilities'],
                'anchors': {k: list(v) for k, v in s['anchors'].items()},
                'description': s['description']}

    env_entries = []
    for pid, spec in LAYOUT['env'].items():
        env_entries.append({'prop_id': pid, 'label': spec['label'], 'asset': spec['asset'],
                            'pose': {'position_m': list(spec['position']), 'wxyz': [1, 0, 0, 0]},
                            'scale_m': [1.0, 1.0, 1.0]})
    for pid, spec in LAYOUT['props'].items():
        loc = prop_pos[pid]
        q = Quaternion((0, 0, 1), math.radians(spec.get('rot_z', 0.0))).normalized()
        env_entries.append({'prop_id': pid, 'label': spec['label'],
                            'asset': f"assets/meshes/env/{spec['glb']}",
                            'pose': {'position_m': [round(v, 4) for v in loc],
                                     'wxyz': [round(v, 6) for v in q]},
                            'scale_m': [spec['scale']] * 3})

    spec_out = {
        'schema_version': '1.0', 'scene_id': LAYOUT['scene_id'], 'title': LAYOUT['title'],
        'units': 'm', 'axes': 'right_handed_z_up',
        'objects': [obj_entry(o) for o in ('SPARE', 'SLOT4', 'NODE3', 'ALARM', 'FAN')],
        'initial_instruction': LAYOUT['initial_instruction'],
        'camera_position_m': list(LAYOUT['camera_position_m']),
        'camera_look_at_m': list(LAYOUT['camera_look_at_m']),
        'environment': env_entries,
        'render_hints': {'ortho_scale_m': round(ortho, 3), 'grid_extent_m': 2.5,
                         'cue_scale': 1.0, 'label_offset_m': 0.12},
    }
    write_scene_json(LAYOUT['scene_id'], spec_out)
    print(json.dumps({'final_camera': {'position_m': list(LAYOUT['camera_position_m']),
                                       'look_at_m': list(LAYOUT['camera_look_at_m']),
                                       'ortho_scale_m': round(ortho, 3)},
                      'final_back_camera': {'position_m': list(LAYOUT['camera_back_position_m']),
                                            'look_at_m': list(LAYOUT['camera_back_look_at_m']),
                                            'ortho_scale_m': round(ortho_back, 3)},
                      'previews': [str(OUT_RUNS / 'server_rack_kit_preview.png'),
                                   str(OUT_RUNS / 'server_rack_kit_preview_back.png')]}), flush=True)

if __name__ == '__main__':
    main()
