"""Build the shelf_picking (仓储分拣站) scene kit.

Run (CPU only, via resource guard):
  cd /home/hdd3/zhanghaonan/projects/holocue && .venv/bin/python scripts/resource_guard.py \
      --rss-limit-gb 12 --execute -- /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/scenes_v2/build_shelf_picking.py

Produces:
  assets/meshes/shelf_picking/{RED,BLUE,BASKET,CONV,GREEN}.glb      (interactive, origin rules below)
  assets/meshes/env/shelf_picking_{shelfwall,conveyorbody,floor,wallpanel}.glb
  configs/scenes/shelf_picking.json
  runs/scene_v2/shelf_picking_kit_preview.png        (ortho framed tight on the task triangle)
  runs/scene_v2/shelf_picking_kit_preview_persp.png  (50mm perspective companion, depth evidence)
  runs/scene_v2/shelf_picking_kit_preview_blue.png   (close 3/4 of BLUE label face)

Origins: RED/BLUE/GREEN body center; BASKET base center (mouth tilted ~6.5 deg toward the main
camera, baked into the mesh; placement anchor remeasured from the rebuilt rim); CONV roller-top
center of end module; shelfwall front-bottom-center; conveyorbody front-end center at belt top;
floor/wallpanel center.
"""
import bpy, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
from mathutils import Vector, Euler

MESH_OUT = ROOT / 'assets/meshes/shelf_picking'
ENV_OUT = ROOT / 'assets/meshes/env'

RAD = math.radians

# ---------------------------------------------------------------- world layout
CAM_POS = (0.35, -1.15, 1.05)
CAM_LOOK = (0.0, 0.45, 0.60)
ROLLER_TOP_Z = 0.785          # world height of conveyor roller / belt top
SHELF_FACE_Y = 0.35           # shelf wall front face plane (toward -y)
BOARD_TOPS = [0.42, 0.92, 1.42]

POSES = {  # interactive objects (world); z finalised by settle() against resting surfaces
    'RED':    {'pos': (-0.35, 0.50, 1.01), 'rest': BOARD_TOPS[1]},
    'BLUE':   {'pos': (0.35, 0.47, 0.50), 'rest': BOARD_TOPS[0]},
    'BASKET': {'pos': (0.0, -0.35, 0.0), 'rest': 0.0},
    # Conveyor line sits at x=+1.45 (right of the shelf wall's right post at x=1.1) so the far
    # layer is in open view; design depth values (CONV y=1.35, GREEN y=1.30) are preserved.
    'CONV':   {'pos': (1.45, 1.35, ROLLER_TOP_Z), 'rest': None},
    'GREEN':  {'pos': (1.45, 1.30, 0.855), 'rest': ROLLER_TOP_Z},
}
# BASKET_PLACEMENT_ANCHOR is remeasured after the basket rebuild in section 3 (just above rim).

def v3(t): return tuple(round(x, 5) for x in t)
def quat_norm(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (round(w / n, 6), round(x / n, 6), round(y / n, 6), round(z / n, 6))

_flat4 = flat  # common.flat expects RGBA; all kit colors are RGB triples
def flat(name, rgb, metallic=0.0, roughness=0.55, emissive=None, emission_strength=1.0):
    return _flat4(name, (rgb[0], rgb[1], rgb[2], 1.0), metallic=metallic, roughness=roughness,
                  emissive=None if emissive is None else (emissive[0], emissive[1], emissive[2], 1.0),
                  emission_strength=emission_strength)

# ---------------------------------------------------------------- small helpers
def bbox_world(objs):
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            lo.x = min(lo.x, w.x); lo.y = min(lo.y, w.y); lo.z = min(lo.z, w.z)
            hi.x = max(hi.x, w.x); hi.y = max(hi.y, w.y); hi.z = max(hi.z, w.z)
    return lo, hi

def kids(parent):
    return [o for o in bpy.data.objects if o.parent == parent]

def settle(parent, target_z):
    """Shift an HC_ parent in z so its lowest world point sits at target_z."""
    bpy.context.view_layer.update()
    lo, _ = bbox_world([parent] + kids(parent))
    parent.location.z += target_z - lo.z
    bpy.context.view_layer.update()
    return round(target_z - lo.z, 4)

def tape_top(name, size, loc, mat, yaw=0.0):
    """Cardboard carton with a paper-tape strip on the top seam."""
    box(name, size, loc, flat(name + '_cb', (0.55, 0.40, 0.24), roughness=0.85), bevel=0.003)
    o = box(name + '_tape', (0.05, size[1] + 0.004, 0.005), (loc[0], loc[1], loc[2] + size[2] / 2 + 0.001),
            mat if mat else flat(name + '_tp', (0.80, 0.74, 0.62), roughness=0.9), bevel=0.0)
    if yaw:
        for ob in bpy.data.objects:
            if ob.name.startswith(name):
                ob.rotation_euler = (0, 0, yaw)

# ================================================================ 1. RED 红色包裹
clear_scene()
m_redcard = flat('red_cardboard', (0.55, 0.035, 0.03), roughness=0.88)  # low-luminance saturated red: must survive Filmic desaturation and read "red" at preview scale
m_tape = flat('paper_tape', (0.82, 0.76, 0.64), roughness=0.9)
m_labelw = flat('label_white', (0.93, 0.93, 0.90), roughness=0.5)
box('RED_body', (0.30, 0.22, 0.18), (0, 0, 0), m_redcard, bevel=0.006)
box('RED_tape', (0.05, 0.224, 0.006), (0, 0, 0.0905), m_tape, bevel=0.0)
box('RED_label', (0.10, 0.065, 0.004), (0.075, -0.045, 0.0905), m_labelw, bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('RED_')], MESH_OUT / 'RED.glb')

# ================================================================ 2. BLUE 蓝色周转箱
clear_scene()
m_blue = flat('blue_plastic', (0.12, 0.28, 0.52), roughness=0.32)
m_blued = flat('blue_plastic_dark', (0.08, 0.20, 0.38), roughness=0.4)
m_labelw = flat('label_white', (0.93, 0.93, 0.90), roughness=0.5)
m_bar = flat('barcode_dark', (0.07, 0.07, 0.08), roughness=0.6)
m_line = flat('label_line', (0.55, 0.55, 0.55), roughness=0.6)
box('BLUE_bottom', (0.376, 0.276, 0.014), (0, 0, -0.073), m_blued, bevel=0.003)
for nm, loc in [('f', (0, -0.144, -0.007)), ('b', (0, 0.144, -0.007))]:
    box(f'BLUE_wall_{nm}', (0.376, 0.012, 0.146), loc, m_blue, bevel=0.002)
for nm, loc in [('l', (-0.188, 0, -0.007)), ('r', (0.188, 0, -0.007))]:
    box(f'BLUE_wall_{nm}', (0.012, 0.276, 0.146), loc, m_blue, bevel=0.002)
box('BLUE_rim_f', (0.404, 0.018, 0.016), (0, -0.149, 0.072), m_blue, bevel=0.002)
box('BLUE_rim_b', (0.404, 0.018, 0.016), (0, 0.149, 0.072), m_blue, bevel=0.002)
box('BLUE_rim_l', (0.018, 0.28, 0.016), (-0.193, 0, 0.072), m_blue, bevel=0.002)
box('BLUE_rim_r', (0.018, 0.28, 0.016), (0.193, 0, 0.072), m_blue, bevel=0.002)
box('BLUE_grip_l', (0.016, 0.08, 0.03), (-0.188, 0, 0.02), m_blued, bevel=0.0)
box('BLUE_grip_r', (0.016, 0.08, 0.03), (0.188, 0, 0.02), m_blued, bevel=0.0)
# LARGE shipping label panel on the +Y radial face (world +y = toward wall; visible after inspect_back spin)
box('BLUE_labelpanel', (0.24, 0.004, 0.125), (0, 0.152, -0.002), m_labelw, bevel=0.0)
box('BLUE_labelstripe', (0.20, 0.002, 0.006), (0, 0.1545, 0.045), flat('stripe_red', (0.70, 0.18, 0.14), roughness=0.6), bevel=0.0)
for i, xl in enumerate([-0.082, -0.070, -0.060, -0.047, -0.038, -0.024, -0.014, -0.002, 0.010, 0.024, 0.036, 0.050, 0.064, 0.078]):
    w = [0.006, 0.003, 0.008, 0.004, 0.003, 0.007, 0.003][i % 7]
    box(f'BLUE_bar_{i}', (w, 0.002, 0.070), (xl, 0.155, -0.028), m_bar, bevel=0.0)
for j, zl in enumerate([0.032, 0.021, 0.010]):
    box(f'BLUE_line_{j}', (0.14 - j * 0.03, 0.002, 0.007), (-0.04, 0.1545, zl), m_line, bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('BLUE_')], MESH_OUT / 'BLUE.glb')

# ================================================================ 3. BASKET 拣选篮 (origin base center; mouth tilted ~6.5 deg toward the main camera)
clear_scene()
m_canvas = flat('basket_canvas', (0.42, 0.32, 0.22), roughness=0.92)   # tan canvas body (kept warm: must not match the gray floor)
m_strap  = flat('basket_strap',  (0.24, 0.185, 0.13), roughness=0.85)  # woven horizontal bands + rim band
m_rib    = flat('basket_rib',    (0.33, 0.26, 0.19), roughness=0.88)   # vertical strap ribs (contrast => woven read)
m_inner  = flat('basket_inner',  (0.05, 0.045, 0.04), roughness=0.95)  # dark cavity liner
m_handle = flat('basket_handle', (0.15, 0.14, 0.13), roughness=0.45)   # rigid rim handles
R_BOT, R_TOP, WALL_H = 0.150, 0.205, 0.185

def r_wall(z):
    return R_BOT + (R_TOP - R_BOT) * (z / WALL_H)

def frustum(name, r1, r2, depth, z, mat, flip=False):
    """Open cone-frustum shell (band / wall). flip=True turns the normals inward so the
    cavity liner stays visible in backface-culling glTF viewers (Viser)."""
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth, location=(0, 0, z),
                                    end_fill_type='NOTHING', vertices=48)
    o = bpy.context.object; o.name = name; o.data.materials.append(mat)
    if flip:
        import bmesh
        bm = bmesh.new(); bm.from_mesh(o.data)
        for f in bm.faces:
            f.normal_flip()
        bm.normal_update(); bm.to_mesh(o.data); bm.free()
    return o

frustum('BASKET_wall_out', R_BOT + 0.004, R_TOP + 0.004, WALL_H, WALL_H / 2, m_canvas)
frustum('BASKET_wall_in', R_BOT - 0.008, R_TOP - 0.008, WALL_H - 0.010, (WALL_H - 0.010) / 2 - 0.005, m_inner, flip=True)
cyl('BASKET_sole', R_BOT + 0.004, 0.010, (0, 0, 0.005), m_canvas, vertices=48)
cyl('BASKET_floor', R_BOT - 0.006, 0.012, (0, 0, 0.012), m_inner, vertices=48)
# woven walls: horizontal strap bands crossed by vertical ribs
frustum('BASKET_band_lo', r_wall(0.060) + 0.004, r_wall(0.076) + 0.004, 0.016, 0.068, m_strap)
frustum('BASKET_band_hi', r_wall(0.126) + 0.004, r_wall(0.142) + 0.004, 0.016, 0.134, m_strap)
frustum('BASKET_rim', R_TOP + 0.005, R_TOP + 0.011, 0.020, WALL_H - 0.010, m_strap)
TAPER = math.atan2(R_TOP - R_BOT, WALL_H)
for k in range(10):
    a = k * math.pi / 5
    r_mid = (R_BOT + R_TOP) / 2 + 0.006
    rib = box(f'BASKET_rib_{k}', (0.008, 0.024, WALL_H - 0.008),
              (r_mid * math.cos(a), r_mid * math.sin(a), WALL_H / 2), m_rib, bevel=0.002)
    rib.rotation_euler = Euler((0, TAPER, a), 'ZYX')  # lean outward along the wall taper
for s in (-1, 1):  # two rigid rim handles on the +-x sides (mouth toward camera stays open)
    box(f'BASKET_hmount_{s}', (0.026, 0.062, 0.030), (s * (R_TOP + 0.008), 0, WALL_H - 0.014), m_handle, bevel=0.004)
    box(f'BASKET_hpost_f{s}', (0.014, 0.014, 0.066), (s * (R_TOP + 0.012), -0.045, WALL_H + 0.018), m_handle, bevel=0.003)
    box(f'BASKET_hpost_b{s}', (0.014, 0.014, 0.066), (s * (R_TOP + 0.012), 0.045, WALL_H + 0.018), m_handle, bevel=0.003)
    cyl(f'BASKET_hbar_{s}', 0.011, 0.104, (s * (R_TOP + 0.012), 0, WALL_H + 0.048), m_handle, rot=(math.pi / 2, 0, 0), vertices=20)
# tilt the whole basket ~6.5 deg so the open mouth faces the main camera, then reseat on z=0
BASKET_TILT = RAD(6.5)
bparts = [o for o in bpy.data.objects if o.name.startswith('BASKET_')]
R_tilt = Euler((BASKET_TILT, 0, 0), 'XYZ').to_matrix().to_4x4()
bpy.context.view_layer.update()
for o in bparts:
    o.matrix_world = R_tilt @ o.matrix_world
bpy.context.view_layer.update()
lo_bk, _ = bbox_world(bparts)
for o in bparts:
    o.location.z -= lo_bk.z
bpy.context.view_layer.update()
# remeasure the rebuilt rim: anchor sits just above the rim (mouth) center
rlo, rhi = bbox_world([bpy.data.objects['BASKET_rim']])
BASKET_PLACEMENT_ANCHOR = (round((rlo.x + rhi.x) / 2, 4), round((rlo.y + rhi.y) / 2, 4), round(rhi.z + 0.017, 4))
BASKET_RIM_TOP_LOCAL = round(rhi.z, 4)
# baked local contact shadow / AO (basket is point-only and stays on the floor)
cyl('BASKET_ao', 0.235, 0.0016, (0, 0, 0.0016), flat('basket_ao', (0.15, 0.14, 0.13), roughness=1.0), vertices=48)
cyl('BASKET_ao_core', 0.175, 0.0016, (0, 0, 0.0032), flat('basket_ao_core', (0.08, 0.075, 0.07), roughness=1.0), vertices=48)
export_glb([o for o in bpy.data.objects if o.name.startswith('BASKET_')], MESH_OUT / 'BASKET.glb')

# ================================================================ 4. CONV 传送带端部 (origin roller-top center of end module)
clear_scene()
m_steel = flat('conv_steel', (0.55, 0.57, 0.60), metallic=0.85, roughness=0.35)
m_frame = flat('conv_frame', (0.22, 0.26, 0.32), metallic=0.3, roughness=0.55)
m_dark = flat('conv_dark', (0.10, 0.11, 0.13), roughness=0.6)
m_yellow = flat('conv_yellow', (0.85, 0.62, 0.08), roughness=0.6)
for i in range(8):
    y = -0.161 + i * 0.046
    cyl(f'CONV_roller_{i}', 0.026, 0.40, (0, y, -0.026), m_steel, rot=(0, math.pi / 2, 0), vertices=24)
box('CONV_side_l', (0.012, 0.40, 0.14), (-0.225, 0, -0.055), m_frame, bevel=0.002)
box('CONV_side_r', (0.012, 0.40, 0.14), (0.225, 0, -0.055), m_frame, bevel=0.002)
box('CONV_cross_f', (0.45, 0.03, 0.03), (0, -0.155, -0.115), m_dark, bevel=0.0)
box('CONV_cross_b', (0.45, 0.03, 0.03), (0, 0.155, -0.115), m_dark, bevel=0.0)
box('CONV_stop', (0.44, 0.016, 0.11), (0, -0.172, 0.055), m_frame, bevel=0.002)
box('CONV_stopyellow', (0.44, 0.018, 0.022), (0, -0.172, 0.095), m_yellow, bevel=0.0)
for sx in (-1, 1):
    for sy in (-1, 1):
        box(f'CONV_leg_{sx}_{sy}', (0.05, 0.05, 0.66), (0.195 * sx, 0.15 * sy, -0.455), m_dark, bevel=0.0)
        box(f'CONV_foot_{sx}_{sy}', (0.08, 0.08, 0.01), (0.195 * sx, 0.15 * sy, -0.776), m_dark, bevel=0.0)
cyl('CONV_post', 0.012, 0.34, (0.205, 0.165, 0.17), m_dark, vertices=16)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.024, location=(0.205, 0.165, 0.358))
lamp = bpy.context.object; lamp.name = 'CONV_lamp'
lamp.data.materials.append(flat('conv_lamp', (0.15, 0.9, 0.35), roughness=0.3, emissive=(0.10, 0.85, 0.30), emission_strength=2.2))
export_glb([o for o in bpy.data.objects if o.name.startswith('CONV_')], MESH_OUT / 'CONV.glb')

# ================================================================ 5. GREEN 端部绿箱
clear_scene()
m_green = flat('green_crate', (0.16, 0.42, 0.20), roughness=0.4)
m_greend = flat('green_crate_dark', (0.11, 0.32, 0.15), roughness=0.45)
m_labelw = flat('label_white', (0.93, 0.93, 0.90), roughness=0.5)
box('GREEN_body', (0.26, 0.20, 0.14), (0, 0, 0), m_green, bevel=0.005)
box('GREEN_rim_f', (0.268, 0.014, 0.012), (0, -0.100, 0.064), m_greend, bevel=0.0)
box('GREEN_rim_b', (0.268, 0.014, 0.012), (0, 0.100, 0.064), m_greend, bevel=0.0)
box('GREEN_rim_l', (0.014, 0.19, 0.012), (-0.133, 0, 0.064), m_greend, bevel=0.0)
box('GREEN_rim_r', (0.014, 0.19, 0.012), (0.133, 0, 0.064), m_greend, bevel=0.0)
box('GREEN_rib_f', (0.268, 0.008, 0.02), (0, -0.102, -0.015), m_greend, bevel=0.0)
box('GREEN_rib_b', (0.268, 0.008, 0.02), (0, 0.102, -0.015), m_greend, bevel=0.0)
box('GREEN_tag', (0.10, 0.003, 0.05), (0, 0.1015, -0.005), m_labelw, bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('GREEN_')], MESH_OUT / 'GREEN.glb')

# ================================================================ 6. shelfwall (origin front-bottom-center; local y+ runs away from viewer)
clear_scene()
m_orange = flat('rack_orange', (0.82, 0.30, 0.06), metallic=0.15, roughness=0.55)
m_rackdark = flat('rack_dark', (0.25, 0.26, 0.28), metallic=0.4, roughness=0.6)
m_wood = pbr('shelf_wood', 'wood_table_001', scale=1.6, roughness=0.8)
for sx in (-1, 1):
    for sy in (0.045, 0.505):
        box(f'SHELF_post_{sx}_{sy}', (0.09, 0.09, 1.9), (1.05 * sx, sy, 0.95), m_orange, bevel=0.002)
        box(f'SHELF_foot_{sx}_{sy}', (0.13, 0.13, 0.015), (1.05 * sx, sy, 0.0075), m_rackdark, bevel=0.0)
    for z in (0.06, 0.68, 1.30, 1.80):
        box(f'SHELF_brace_h_{sx}_{z}', (0.04, 0.42, 0.04), (1.05 * sx, 0.275, z), m_rackdark, bevel=0.0)
    for (z0, z1, flip) in [(0.06, 0.68, False), (0.68, 1.30, True), (1.30, 1.80, False)]:
        dz = z1 - z0
        ln = math.hypot(dz, 0.42) * 1.02
        ang = math.atan2(dz, 0.42) * (-1 if flip else 1)
        o = box(f'SHELF_brace_d_{sx}_{z0}', (0.035, ln, 0.035), (1.05 * sx, 0.275, (z0 + z1) / 2), m_rackdark, bevel=0.0)
        o.rotation_euler = (ang, 0, 0)
for lvl, zb in enumerate([0.40, 0.90, 1.40]):
    box(f'SHELF_beam_f_{lvl}', (2.14, 0.055, 0.10), (0, 0.05, zb - 0.05), m_orange, bevel=0.002)
    box(f'SHELF_beam_b_{lvl}', (2.14, 0.055, 0.10), (0, 0.50, zb - 0.05), m_orange, bevel=0.002)
    box(f'SHELF_board_{lvl}', (2.16, 0.52, 0.04), (0, 0.28, zb), m_wood, bevel=0.002)
# filler cartons (world coords -> local by shifting y by -SHELF_FACE_Y)
m_tape_f = flat('filler_tape', (0.80, 0.74, 0.62), roughness=0.9)
def filler(name, size, wx, wy, wz, yaw):
    tape_top(f'SHELF_{name}', size, (wx, wy - SHELF_FACE_Y, wz), m_tape_f, yaw=RAD(yaw))
filler('cA', (0.30, 0.20, 0.20), -0.85, 0.60, 0.52, 8)
filler('cB', (0.22, 0.16, 0.15), -0.83, 0.61, 0.695, 33)
filler('cC', (0.24, 0.18, 0.16), 0.82, 0.62, 0.50, -12)
filler('cD', (0.24, 0.18, 0.15), 0.05, 0.66, 0.995, 20)
filler('cE', (0.26, 0.20, 0.14), 0.48, 0.58, 1.49, -8)
filler('cF', (0.18, 0.14, 0.12), -0.55, 0.60, 1.822, 15)
export_glb([o for o in bpy.data.objects if o.name.startswith('SHELF_')], ENV_OUT / 'shelf_picking_shelfwall.glb')

# ================================================================ 7. conveyorbody (origin front-end center at belt top; local y+ toward wall)
clear_scene()
m_belt = flat('belt_dark', (0.075, 0.075, 0.085), roughness=0.75)
m_tread = flat('belt_tread', (0.10, 0.10, 0.11), roughness=0.7)
m_gmetal = flat('guide_metal', (0.45, 0.47, 0.50), metallic=0.7, roughness=0.45)
m_cdark = flat('convleg_dark', (0.12, 0.13, 0.15), roughness=0.6)
box('BED_main', (0.45, 1.60, 0.05), (0, 0.80, -0.025), m_belt, bevel=0.0)
for i in range(15):
    box(f'BED_tread_{i}', (0.452, 0.014, 0.008), (0, 0.05 + i * 0.107, 0.002), m_tread, bevel=0.0)
box('BED_guide_l', (0.03, 1.60, 0.09), (-0.24, 0.80, 0.02), m_gmetal, bevel=0.002)
box('BED_guide_r', (0.03, 1.60, 0.09), (0.24, 0.80, 0.02), m_gmetal, bevel=0.002)
box('BED_frame', (0.42, 1.60, 0.03), (0, 0.80, -0.065), m_cdark, bevel=0.0)
for ly in (0.25, 1.35):
    for sx in (-1, 1):
        box(f'BED_leg_{sx}_{ly}', (0.05, 0.05, 0.70), (0.18 * sx, ly, -0.43), m_cdark, bevel=0.0)
        box(f'BED_foot_{sx}_{ly}', (0.09, 0.09, 0.012), (0.18 * sx, ly, -0.774), m_cdark, bevel=0.0)
    box(f'BED_brace_{ly}', (0.36, 0.04, 0.04), (0, ly, -0.55), m_cdark, bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('BED_')], ENV_OUT / 'shelf_picking_conveyorbody.glb')

# ================================================================ 8. floor (origin center) + painted lane
clear_scene()
m_conc = pbr('floor_conc', 'concrete_floor_worn_001', scale=2.0, roughness=0.95)
box('FLOOR_slab', (5.0, 4.0, 0.03), (0, 0, -0.015), m_conc, bevel=0.0)
box('FLOOR_lane', (0.07, 1.55, 0.006), (-0.55, -0.95, 0.004), flat('lane_yellow', (0.85, 0.62, 0.08), roughness=0.6), bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('FLOOR_')], ENV_OUT / 'shelf_picking_floor.glb')

# ================================================================ 9. wallpanel (origin center)
clear_scene()
m_wall = pbr('wall_factory', 'factory_wall', scale=2.5, roughness=0.95)
box('WALL_panel', (5.0, 0.06, 2.8), (0, 0, 0), m_wall, bevel=0.0)
box('WALL_base', (5.0, 0.065, 0.18), (0, 0, -1.31), flat('wall_base', (0.55, 0.56, 0.58), roughness=0.8), bevel=0.0)
export_glb([o for o in bpy.data.objects if o.name.startswith('WALL_')], ENV_OUT / 'shelf_picking_wallpanel.glb')

# ================================================================ 10. compose preview at JSON poses
clear_scene()
world_bg((0.60, 0.64, 0.70, 1.0), 0.9)

env_specs = [
    # procedural parts
    ('shelf_picking_shelfwall',   'assets/meshes/env/shelf_picking_shelfwall.glb',   (0.0, SHELF_FACE_Y, 0.0), (0, 0, 0), (1, 1, 1), None),
    ('shelf_picking_conveyorbody','assets/meshes/env/shelf_picking_conveyorbody.glb',(1.45, 1.53, ROLLER_TOP_Z), (0, 0, 0), (1, 1, 1), None),
    ('shelf_picking_floor',       'assets/meshes/env/shelf_picking_floor.glb',        (0.0, 1.20, 0.0), (0, 0, 0), (1, 1, 1), None),
    ('shelf_picking_wallpanel',   'assets/meshes/env/shelf_picking_wallpanel.glb',    (0.0, 3.21, 1.40), (0, 0, 0), (1, 1, 1), None),
    # downloaded props (probe-derived local bboxes; z finalised by settle)
    ('cardboard_box_01',  'assets/meshes/env/cardboard_box_01.glb',  (-0.55, 0.60, BOARD_TOPS[2]), (0, 0, -6), (1, 1, 1), BOARD_TOPS[2]),
    ('plastic_crate_01',  'assets/meshes/env/plastic_crate_01.glb',  (-0.45, 0.60, BOARD_TOPS[0]), (0, 0, 0), (1, 1, 1), BOARD_TOPS[0]),
    ('plastic_crate_02',  'assets/meshes/env/plastic_crate_02.glb',  (0.60, 0.62, BOARD_TOPS[1]), (0, 0, 3), (1, 1, 1), BOARD_TOPS[1]),
    ('wooden_crate_02',   'assets/meshes/env/wooden_crate_02.glb',   (1.30, 0.52, 0.0), (0, 0, 12), (1, 1, 1), 0.0),
    ('Barrel_02',         'assets/meshes/env/Barrel_02.glb',         (-1.62, 1.02, 0.0), (0, 0, 0), (1, 1, 1), 0.0),
    ('cement_bag',        'assets/meshes/env/cement_bag.glb',        (-1.60, 0.54, 0.34), (60, 0, 0), (1, 1, 1), 0.0),
    ('hand_truck',        'assets/meshes/env/hand_truck.glb',        (-1.40, 0.10, 0.0), (-10, 0, 0), (1, 1, 1), 0.0),
    ('steel_frame_shelves_02', 'assets/meshes/env/steel_frame_shelves_02.glb', (-1.75, 2.55, 0.0), (0, 0, 18), (0.8, 0.8, 0.8), 0.0),
]

env_json = []
env_parents = {}
for prop_id, asset, pos, euler, scale, rest in env_specs:
    objs = import_glb(ROOT / asset)
    p = parent_to('HC_ENV_' + prop_id, objs, location=pos)
    # parent_to already applied CORR (importer's -90 X cancel); compose desired pose on top of it.
    q_world = Euler(tuple(RAD(a) for a in euler)).to_quaternion()
    p.rotation_quaternion = q_world @ CORR
    p.scale = scale
    bpy.context.view_layer.update()
    if rest is not None:
        settle(p, rest)
    # Scene JSON stores the TRUE world pose; CORR is a Blender-internal importer compensation.
    env_json.append({'prop_id': prop_id, 'label': '', 'asset': asset,
                     'pose': {'position_m': v3(p.location), 'wxyz': quat_norm((q_world.w, q_world.x, q_world.y, q_world.z))},
                     'scale_m': v3(scale)})
    env_parents[prop_id] = p

obj_defs = {
    'RED':    {'label': '红色包裹',   'color': (176, 58, 42),  'caps': ['point', 'assemble'], 'desc': '二层标准件包裹', 'rest': BOARD_TOPS[1]},
    'BLUE':   {'label': '蓝色周转箱', 'color': (46, 94, 168),  'caps': ['point', 'rotate', 'inspect_back'], 'desc': '+Y 侧贴发货面单', 'rest': BOARD_TOPS[0]},
    'BASKET': {'label': '拣选篮',     'color': (74, 72, 70),   'caps': ['point'], 'desc': '软底拣选篮', 'rest': 0.0,
               'anchors': {'placement': list(BASKET_PLACEMENT_ANCHOR)}},
    'CONV':   {'label': '传送带端部', 'color': (128, 132, 136), 'caps': ['point', 'wait'], 'desc': '到位指示灯在端部', 'rest': None},
    'GREEN':  {'label': '端部绿箱',   'color': (56, 150, 72),  'caps': ['point', 'wait'], 'desc': '补货标记箱(静止)', 'rest': ROLLER_TOP_Z},
}
obj_json = []
inter_parents = {}
for oid, d in obj_defs.items():
    objs = import_glb(MESH_OUT / f'{oid}.glb')
    p = parent_to('HC_' + oid, objs, location=POSES[oid]['pos'])
    if d['rest'] is not None:
        settle(p, d['rest'])
    obj_json.append({'object_id': oid, 'label': d['label'], 'asset': f'assets/meshes/shelf_picking/{oid}.glb',
                     'pose': {'position_m': v3(p.location), 'wxyz': [1, 0, 0, 0]},
                     'color': list(d['color']), 'capabilities': d['caps'],
                     'anchors': d.get('anchors', {}), 'description': d['desc']})
    inter_parents[oid] = p

# preview-only labels above the 5 interactive objects (ASCII only; billboards toward the camera).
# Each text sits directly above its own object with a short vertical leader tick; the five ticks
# live in separate screen columns (RED left, BASKET mid-left, BLUE center, GREEN/CONV right), so
# no leader can cross another and none lands on a foreign object. GREEN's text is raised and
# offset left so no shelf beam can occlude it.
label_objs = []
label_mat = flat('label_text', (0.97, 0.97, 1.0), roughness=0.4, emissive=(0.9, 0.9, 1.0), emission_strength=0.45)
tick_mat = flat('label_tick', (0.92, 0.92, 0.96), roughness=0.4, emissive=(0.85, 0.85, 0.95), emission_strength=0.4)
LABEL_SPEC = {  # oid: (text_center_xyz, tick_bottom_z, tick_top_z)
    'RED':    ((-0.35, 0.50, 1.28), 1.135, 1.215),
    'BLUE':   ((0.35, 0.47, 0.76), 0.615, 0.695),
    'BASKET': ((0.0, -0.35, 0.42), 0.275, 0.355),
    'CONV':   ((1.62, 1.47, 1.28), 0.845, 1.215),   # over the roller module, right of GREEN's column
    'GREEN':  ((1.33, 1.25, 1.12), 0.950, 1.045),   # raised + offset left: clear of shelf beams
}
for oid, ((lx, ly, lz), ta, tb) in LABEL_SPEC.items():
    loc = Vector((lx, ly, lz))
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.object; t.name = 'PREVIEW_LABEL_' + oid
    t.data.body = oid; t.data.size = 0.07; t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'
    t.data.extrude = 0.003
    t.data.materials.append(label_mat)
    t.rotation_euler = (Vector(CAM_POS) - loc).to_track_quat('Z', 'Y').to_euler()
    label_objs.append(t)
    label_objs.append(box('PREVIEW_TICK_' + oid, (0.006, 0.006, tb - ta), (lx, ly, (ta + tb) / 2), tick_mat, bevel=0.0))

light_rig(Vector((0.0, 0.7, 0.9)), 3.0, energy=2.0)

# convention check: an origin-centered interactive object must land centered on its JSON pose
lo_b, hi_b = bbox_world([inter_parents['BLUE']] + kids(inter_parents['BLUE']))
blue_pose = obj_json[[o['object_id'] for o in obj_json].index('BLUE')]['pose']['position_m']
print(json.dumps({'blue_center_check': {
    'bbox_center_xy': [round((lo_b.x + hi_b.x) / 2, 4), round((lo_b.y + hi_b.y) / 2, 4)],
    'pose_xy': [round(blue_pose[0], 4), round(blue_pose[1], 4)],
    'delta_m': round(max(abs((lo_b.x + hi_b.x) / 2 - blue_pose[0]), abs((lo_b.y + hi_b.y) / 2 - blue_pose[1])), 4)}}), flush=True)

# ---- render 1: ortho preview framed tight on the task triangle
#      (BASKET -> shelf wall with RED/BLUE -> CONV/GREEN end), ~10% margin. The camera axis is
#      iteratively aimed at the triangle's screen centroid so a small ortho fits without
#      clipping BASKET or the conveyor end module.
task_objs = []
for k in inter_parents:
    task_objs.append(inter_parents[k]); task_objs += kids(inter_parents[k])
task_objs += label_objs
camv, look = Vector(CAM_POS), Vector(CAM_LOOK)
for _ in range(8):
    fwd = (look - camv).normalized()
    right = Vector((0, 0, 1)).cross(fwd)
    if right.length < 1e-6:
        right = Vector((1, 0, 0)).cross(fwd)
    right.normalize(); up = fwd.cross(right).normalized()
    us, vs_ = [], []
    for o in task_objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            us.append((w - camv) @ right); vs_.append((w - camv) @ up)
    look = look + ((max(us) + min(us)) / 2) * right + ((max(vs_) + min(vs_)) / 2) * up
PREVIEW_LOOK = v3(look)
ortho_val = round(max(max(us) - min(us), (max(vs_) - min(vs_)) * 1600 / 1120) * 1.10, 2)
ortho_val = max(ortho_val, 2.6)  # review band 2.6-3.2; extra headroom only, never less
r1 = render_preview('shelf_picking_kit_preview.png', CAM_POS, PREVIEW_LOOK, ortho=ortho_val, samples=96)

# ---- render 3: 50mm perspective companion (depth evidence), on the main view ray pulled
#      back far enough that the whole task triangle fits a normal-photo lens
persp_pos = v3(camv - 3.6 * fwd)
r3 = render_preview('shelf_picking_kit_preview_persp.png', persp_pos, PREVIEW_LOOK, persp_fov=50, samples=64)

# ---- render 2: close 3/4 of BLUE label face (inspect_back evidence), no preview labels
for t in label_objs:
    t.hide_render = True
r2 = render_preview('shelf_picking_kit_preview_blue.png', (0.85, 1.35, 0.80), (0.35, 0.52, 0.53),
                    persp_fov=50, samples=64)
for t in label_objs:
    t.hide_render = False

# ================================================================ 11. scene JSON
spec = {
    'schema_version': '1.0',
    'scene_id': 'shelf_picking',
    'title': '仓储分拣站',
    'units': 'm',
    'axes': 'right_handed_z_up',
    'objects': obj_json,
    'initial_instruction': '把第二层的红色包裹 RED 放进拣选篮 BASKET,然后翻看蓝箱 BLUE 背面的面单,同时留意传送带 CONV 端部有没有绿箱 GREEN 到位。',
    'camera_position_m': list(CAM_POS),
    'camera_look_at_m': list(PREVIEW_LOOK),
    'environment': env_json,
    'render_hints': {'ortho_scale_m': ortho_val, 'grid_extent_m': 2.5, 'cue_scale': 1.0, 'label_offset_m': 0.12},
}
write_scene_json('shelf_picking', spec)

# ================================================================ 12. reports
files = sorted(MESH_OUT.glob('*.glb')) + sorted(ENV_OUT.glob('shelf_picking_*.glb')) + \
        [OUT_RUNS / 'shelf_picking_kit_preview.png', OUT_RUNS / 'shelf_picking_kit_preview_persp.png',
         OUT_RUNS / 'shelf_picking_kit_preview_blue.png', ROOT / 'configs/scenes/shelf_picking.json']
print(json.dumps({'file_table': {str(f.relative_to(ROOT)): f.stat().st_size for f in files}}, indent=1), flush=True)

bp = obj_json[[o['object_id'] for o in obj_json].index('BASKET')]['pose']['position_m']
goal = [bp[i] + BASKET_PLACEMENT_ANCHOR[i] for i in range(3)]
rim_z = bp[2] + BASKET_RIM_TOP_LOCAL
print(json.dumps({'anchor_math': {'basket_pose': bp, 'placement_anchor_local': list(BASKET_PLACEMENT_ANCHOR),
                                  'basket_tilt_deg': round(math.degrees(BASKET_TILT), 2),
                                  'assemble_goal_world': [round(g, 4) for g in goal],
                                  'basket_rim_top_world_z': round(rim_z, 4),
                                  'goal_above_rim_m': round(goal[2] - rim_z, 4),
                                  'red_bottom_at_goal_m': round(goal[2] - 0.0905, 4)}}, indent=1), flush=True)
print(json.dumps({'camera_final': {'position': list(CAM_POS), 'look_at': list(PREVIEW_LOOK),
                                   'persp_position': list(persp_pos)},
                  'ortho_used': ortho_val, 'blue_closeup': r2['projection'], 'persp': r3['projection']}), flush=True)
