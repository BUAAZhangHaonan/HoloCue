"""Asset-led CNC teaching station with explicit BT-style interface adapters.

UBC's complete ER collet, locknut and cutter are reused; its HSK body is not.
The source Araki flange and 3030 extrusions retain their cross sections. All
fixed task frames stay in scene.json; this module only supplies visual geometry.
"""

from functools import lru_cache
import cadquery as cq
import numpy as np
import trimesh
from holocue.config import root
from holocue.modeling import Assembly, STEEL
from scripts.scenes.asset_composition import mature_asset, textured_box

SOURCE = "assets/downloads/cnc_reconstruction"
CONTROL = "assets/downloads/control_panel_reconstruction"
TABLE_TOP = 0.995
FLANGE_SCALE = 0.063 / 0.046
FLANGE_TOP = -0.015 + 0.020 * FLANGE_SCALE
TAPER_BASE = FLANGE_TOP + 0.002
TAPER_TOP = TAPER_BASE + 0.0654
ER_SCALE = 0.030
ER_SHIFT = -0.100 + 1.9337472915649414 * ER_SCALE
POST_SCALE = 1.11
POST_Y = 0.6485
POST_FRONT = POST_Y - 0.015 * POST_SCALE


def _mesh(shape):
    vertices, faces = shape.scale(1000).tessellate(0.05, 0.12)
    return trimesh.Trimesh(
        vertices=np.asarray([v.toTuple() for v in vertices]) / 1000, faces=faces, process=True, validate=True
    )


@lru_cache(maxsize=8)
def _source(name):
    s = trimesh.load_scene(root() / SOURCE / name, process=False)
    s.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return s


def _append(a, s, name):
    for node in s.graph.nodes_geometry:
        transform, key = s.graph[node]
        key2 = f"{a.name}/{a.index:04d}_{name}_{node}"
        a.scene.add_geometry(s.geometry[key].copy(), node_name=key2, geom_name=key2, transform=transform)
        a.index += 1


def _box(a, size, center, color, name, metal=0.65, rough=0.34):
    return a.add(trimesh.creation.box(size), color, center, metal=metal, rough=rough, name=name)


def _turned(a, profile, color, name, metal=0.86, rough=0.25):
    m = trimesh.creation.revolve(np.asarray(profile), sections=128)
    m.fix_normals()
    return a.add(m, color, metal=metal, rough=rough, name=name)


def _screw(a, center, axis=(0, 0, 1), r=0.003, name="socket_cap_screw"):
    s = cq.Workplane("XY").circle(r).extrude(0.002)
    hole = cq.Workplane("XY").polygon(6, r * 1.02).extrude(0.0016).translate((0, 0, 0.0005))
    return a.add(_mesh(s.cut(hole).val()), STEEL, center, axis=axis, metal=0.85, rough=0.27, name=name)


def tool(obj):
    a = Assembly(obj.object_id)
    flange = _source("araki_bt_flange.glb").to_geometry()
    # The open CAD source has inward winding: its 128 underside triangles
    # face +Z. Reverse the complete flange, preserving every source position.
    flange.invert()
    flange.apply_scale(FLANGE_SCALE)
    flange.apply_translation([0, 0, FLANGE_TOP])
    a.add(flange, (152, 161, 164), metal=0.88, rough=0.27, name="Araki_BT_source_V_groove_flange")
    # The precise 7/24 shank is an explicitly authored teaching adapter, not
    # UBC's HSK body. The source V-groove flange above is uniformly enlarged.
    profile = [
        (0.006, -0.0555),
        (0.0178, -0.0555),
        (0.0188, -0.052),
        (0.0188, -0.031),
        (0.0207, -0.024),
        (0.0207, FLANGE_TOP - 0.001),
        (0.0234, FLANGE_TOP - 0.001),
        (0.0234, FLANGE_TOP),
        (0.022225, TAPER_BASE),
        (0.0126875, TAPER_TOP),
        (0.0118, TAPER_TOP + 0.001),
        (0.006, TAPER_TOP + 0.001),
    ]
    _turned(a, profile, (178, 184, 184), "teaching_7_24_taper_and_ER_seat")
    # A separate retained knob has a wrench shoulder, relief, neck and head.
    hexmesh = trimesh.creation.cylinder(0.0102, 0.005, sections=6)
    a.add(
        hexmesh,
        (114, 122, 125),
        (0, 0, TAPER_TOP + 0.0025),
        metal=0.88,
        rough=0.28,
        name="pull_stud_wrench_hex",
    )
    neck_start = TAPER_TOP + 0.005
    stud = [
        (0, neck_start),
        (0.0068, neck_start),
        (0.0068, neck_start + 0.001),
        (0.0056, neck_start + 0.002),
        (0.0056, 0.096),
        (0.0088, 0.0995),
        (0.0088, 0.1035),
        (0.0072, 0.1048),
        (0, 0.1048),
    ]
    _turned(a, stud, (145, 152, 155), "pull_stud_neck_and_retention_head", rough=0.23)
    er = _source("ubc_er_components.glb").copy()
    er.apply_translation([-0.3065, 0.131, 0])
    er.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    er.apply_scale(ER_SCALE)
    er.apply_translation([0, 0, ER_SHIFT])
    for geometry in er.geometry.values():
        mat = geometry.visual.material
        mat.metallicFactor = 0.82
        mat.roughnessFactor = 0.34
    _append(a, er, "UBC_complete_ER_component")
    a.label(obj.object_id, (0, -0.01905, -0.039), 0.017, 0.007, background=(61, 72, 77), ink=(230, 235, 230))
    return a


def _receiver(a, bottom, top, name, outer=0.047, fasteners=False):
    # The large straight, open cavity clears the complete scanned locknut.
    # T09 is supported at its source flange, never by its cutting tip.
    section = [
        (0.0242, bottom),
        (outer, bottom),
        (outer, top - 0.009),
        (outer + 0.003, top - 0.009),
        (outer + 0.003, top),
        (0.032, top),
        (0.032, top - 0.0018),
        (0.0242, top - 0.0018),
    ]
    if fasteners:
        body = cq.Workplane("XZ").polyline(section).close().revolve(360, (0, 0), (0, 1))
        for angle in (45, 135, 225, 315):
            x, y = 0.040 * np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
            recess = (
                cq.Workplane("XY").center(x, y).circle(0.0032).extrude(0.006).translate((0, 0, top - 0.005))
            )
            body = body.cut(recess)
        a.add(_mesh(body.val()), (77, 88, 96), metal=0.62, rough=0.37, name=name)
    else:
        _turned(a, section, (77, 88, 96), name, metal=0.62, rough=0.37)
    _turned(
        a,
        [(0.0242, top - 0.0018), (0.032, top - 0.0018), (0.032, top), (0.0242, top)],
        (184, 182, 162),
        name + "_replaceable_seat",
        metal=0.78,
        rough=0.31,
    )


def pocket(obj):
    a = Assembly(obj.object_id)
    _receiver(a, -0.08, 0.08, "open_tool_receiver", fasteners=True)
    for angle in (45, 135, 225, 315):
        x, y = 0.040 * np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
        _screw(a, (x, y, 0.075), r=0.0025, name="receiver_recessed_fastener")
    a.label("09", (0, -0.0501, 0.031), 0.031, 0.021)
    return a


@lru_cache(maxsize=1)
def _knob():
    m = trimesh.load_scene(root() / CONTROL / "emaitee_knob.glb", process=False).to_geometry()
    m.apply_translation([0, -32.1573753356934, 118.75])
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    m.apply_scale(0.001)
    m.merge_vertices()
    m.fix_normals()
    return m


def mode_switch(obj):
    a = Assembly(obj.object_id)
    m = _knob().copy()
    m.apply_scale(3.0)
    m.apply_translation([0, 0, -0.0195 - m.bounds[0, 2]])
    a.add(m, (90, 102, 109), metal=0.10, rough=0.33, name="emaitee_source_mode_knob")
    # Original local +Z remains the entire object's rotation axis.
    a.add(
        trimesh.creation.cylinder(0.003, 0.010, sections=64),
        STEEL,
        (0, 0, -0.015),
        metal=0.85,
        rough=0.25,
        name="mode_rotating_spindle",
    )
    _box(
        a,
        (0.0025, 0.010, 0.0004),
        (0, 0.0065, 0.0197),
        (244, 242, 225),
        "mode_white_pointer",
        metal=0,
        rough=0.46,
    )
    return a


@lru_cache(maxsize=1)
def _case():
    return tuple(cq.importers.importStep(str(root() / CONTROL / "adafruit_2230.step")).solids().vals())


def _case_shape(index, scale=2.4):
    return (
        _case()[index]
        .translate((-41.4, -14.4, -45.25))
        .rotate((0, 0, 0), (0, 1, 0), -90)
        .scale(0.001 * scale)
    )


def panel(obj):
    a = Assembly(obj.object_id)
    body = _case_shape(0)
    cut = cq.Workplane("XY").box(0.154, 0.018, 0.104).translate((-0.014, -0.03456, 0.024))
    body = body.cut(cut.val())
    a.add(_mesh(body), (138, 151, 157), metal=0.76, rough=0.33, name="Adafruit_2230_controller_extrusion")
    for i in (1, 2):
        a.add(
            _mesh(_case_shape(i)),
            (62, 74, 81),
            metal=0.55,
            rough=0.35,
            name=f"Adafruit_controller_endcap_{i}",
        )
    # This recessed display is backed inside a real opening in the CAD case.
    _box(
        a,
        (0.152, 0.004, 0.102),
        (-0.014, -0.032, 0.024),
        (21, 32, 37),
        "recessed_display",
        metal=0,
        rough=0.30,
    )
    a.label(
        "TOOL CHANGE\nPOCKET 09 : READY\nSPINDLE : STOP",
        (-0.014, -0.0341, 0.024),
        0.142,
        0.089,
        background=(23, 43, 49),
        ink=(162, 219, 207),
    )
    for index in range(5):
        x = -0.078 + index * 0.036
        a.add(
            trimesh.creation.cylinder(0.006, 0.003, sections=48),
            (215, 181, 58) if index == 4 else (60, 74, 81),
            (x, -0.0358, -0.061),
            axis=(0, -1, 0),
            metal=0,
            rough=0.44,
            name="controller_key",
        )
    a.label("ATC  /  TEACHING", (0.004, -0.0348, 0.083), 0.164, 0.014)
    a.label("RESET    JOG    TOOL    READY", (0, -0.0348, -0.084), 0.18, 0.011)
    for x in (-0.103, 0.103):
        for z in (-0.083, 0.083):
            _screw(a, (x, -0.03456, z), (0, -1, 0), 0.0025, "controller_case_fastener")
    return a


def magazine(obj):
    a = Assembly(obj.object_id)
    plate = cq.Workplane("XY").circle(0.207).extrude(0.013)
    for i in range(12):
        angle = np.radians(i * 30)
        x, z = 0.162 * np.array([np.sin(angle), np.cos(angle)])
        plate = plate.cut(cq.Workplane("XY").center(x, z).circle(0.0245).extrude(0.014))
    mesh = _mesh(plate.val())
    mesh.apply_translation((0, 0, -0.0065))
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    a.add(mesh, (109, 126, 136), (0, 0.006, 0), metal=0.74, rough=0.32, name="magazine_drilled_carrier")
    for i in range(12):
        angle = np.radians(i * 30)
        x, z = 0.162 * np.array([np.sin(angle), np.cos(angle)])
        ring = trimesh.creation.annulus(0.0245, 0.030, 0.025, sections=64)
        a.add(
            ring,
            (54, 66, 74),
            (x, -0.013, z),
            axis=(0, 1, 0),
            metal=0,
            rough=0.5,
            name="magazine_open_pocket",
        )
        a.label(f"{i + 1:02d}", (x, -0.026, z + 0.034), 0.022, 0.013)
    a.add(
        trimesh.creation.cylinder(0.040, 0.034, sections=96),
        (146, 155, 157),
        (0, 0.0295, 0),
        axis=(0, 1, 0),
        metal=0.8,
        rough=0.28,
        name="magazine_rear_hub",
    )
    a.add(
        trimesh.creation.cylinder(0.023, 0.012, sections=96),
        (79, 91, 97),
        (0, -0.0065, 0),
        axis=(0, 1, 0),
        metal=0.7,
        rough=0.32,
        name="magazine_front_hub",
    )
    for ang in (0, 90, 180, 270):
        x, z = 0.029 * np.array([np.sin(np.radians(ang)), np.cos(np.radians(ang))])
        _screw(a, (x, -0.0125, z), (0, -1, 0), 0.0022, "hub_fastener")
    return a


def _prop(a, name, xy, bottom, size, rx=0, rz=0):
    s = mature_asset(name).copy()
    if rx:
        s.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rx), [1, 0, 0]))
    if rz:
        s.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    s.apply_scale(min(np.asarray(size) / s.extents))
    s.apply_translation(np.r_[xy, bottom] - np.r_[s.bounds.mean(0)[:2], s.bounds[0, 2]])
    _append(a, s, name)


def _cart(a):
    # Preserve every authored face. The source has a single white CAD material;
    # separate its existing tyre surfaces by connected CAD component bounds.
    raw = trimesh.load_scene(root() / SOURCE / "toolrack.glb", process=False).to_geometry()
    raw.merge_vertices(digits_vertex=5)
    components = trimesh.graph.connected_components(
        raw.face_adjacency, nodes=np.arange(len(raw.faces)), min_len=1
    )
    tyre_faces = []
    frame_faces = []
    for indices in components:
        points = raw.vertices[raw.faces[indices]].reshape(-1, 3)
        low, high = points.min(0), points.max(0)
        tyre = low[2] > 17.9 and high[2] > 91 and high[2] - low[2] > 70 and max(high[:2] - low[:2]) < 60
        (tyre_faces if tyre else frame_faces).extend(indices)
    assert tyre_faces and len(tyre_faces) + len(frame_faces) == len(raw.faces)
    raw.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    raw.apply_scale(0.001)
    raw.apply_translation(np.array([0.03, 0.98, 0]) - np.r_[raw.bounds.mean(0)[:2], raw.bounds[0, 2]])
    for name, indices, color, metal, rough in [
        ("frame", frame_faces, (88, 107, 117), 0.58, 0.43),
        ("tyres", tyre_faces, (30, 34, 37), 0, 0.85),
    ]:
        mesh = raw.submesh([indices], append=True, repair=False)
        a.add(mesh, color, metal=metal, rough=rough, name="Araki_complete_tool_service_cart_" + name)


def environment(spec):
    a = Assembly("cnc_environment")
    table = mature_asset("WoodenTable_03").copy()
    table.apply_scale(0.980 / table.extents[2])
    table.apply_translation(-np.r_[table.bounds.mean(0)[:2], table.bounds[0, 2]])
    table.apply_translation((0.03, 0.02, 0))
    _append(a, table, "mature_workbench")
    _box(a, (1.55, 0.90, 0.015), (0.03, 0.02, 0.9875), (137, 146, 148), "clean_machining_worktop", 0.72, 0.38)
    textured_box(a, (3.4, 2.8, 0.04), (0, 0.25, -0.020), "concrete_floor_worn_001", name="visible_floor")
    # Araki's source uses millimetres with wheels toward raw +Z. Rigidly turn
    # that entire authored cart upright; do not infer orientation from AABB.
    _cart(a)
    # Source 3030 uprights are complete 1.5 m CAD components, uniformly 1.11x.
    for x in (-0.62, 0.55):
        post = _source("araki_3030_post.glb").copy()
        post.apply_scale(POST_SCALE)
        post.apply_translation((x, POST_Y, 0.03))
        for geo in post.geometry.values():
            geo.visual.material = trimesh.visual.material.PBRMaterial(
                name="clean_anodized_extrusion",
                baseColorFactor=(143, 153, 158, 255),
                metallicFactor=0.78,
                roughnessFactor=0.34,
            )
        _append(a, post, "Araki_3030_upright")
        _box(a, (0.18, 0.22, 0.03), (x, POST_Y, 0.015), (69, 80, 86), "upright_ground_plate")
        for dx in (-0.065, 0.065):
            for dy in (-0.080, 0.080):
                _screw(a, (x + dx, POST_Y + dy, 0.03), r=0.004, name="stand_base_fastener")
    objects = {o.object_id: o for o in spec.objects}
    # The source flange underside at local z=-.015 transfers load here.
    for key in ("T09", "T03"):
        x, y, z = objects[key].pose.position_m
        rest = Assembly(key + "_stationary_flange_rest")
        bottom = TABLE_TOP - z
        top = -0.015
        _receiver(rest, top - 0.010, top, "open_initial_flange_seat", outer=0.043)
        _turned(
            rest,
            [(0.030, bottom), (0.046, bottom), (0.046, bottom + 0.008), (0.030, bottom + 0.008)],
            (78, 91, 99),
            "initial_rest_open_base",
            metal=0.62,
            rough=0.37,
        )
        for angle in (30, 150, 270):
            xpost, ypost = 0.037 * np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
            low, high = bottom + 0.008, top - 0.010
            rest.add(
                trimesh.creation.cylinder(0.004, high - low, sections=48),
                (115, 129, 137),
                (xpost, ypost, (low + high) / 2),
                metal=0.72,
                rough=0.32,
                name="initial_rest_support_column",
            )
        rest.transform(trimesh.transformations.translation_matrix((x, y, z)))
        _append(a, rest.scene, key + "_rest")
    _box(a, (0.115, 0.115, 0.085), (0.20, 0.25, 1.0375), (92, 106, 113), "POCKET9_support_riser")
    # Horizontal joints meet the actual rear faces of MAG and PANEL.
    _box(
        a,
        (0.080, POST_FRONT - 0.625, 0.110),
        (0.55, (POST_FRONT + 0.625) / 2, 1.47),
        (73, 85, 93),
        "MAG_rear_contact_plate",
    )
    for z in (1.422, 1.518):
        _screw(a, (0.55, 0.625, z), (0, -1, 0), 0.003, "MAG_mount_fastener")
    rear = 0.368 + 0.0144 * 2.4
    _box(a, (0.085, 0.006, 0.130), (-0.62, rear + 0.003, 1.65), (73, 85, 93), "PANEL_rear_contact_plate")
    _box(
        a,
        (0.042, POST_FRONT - (rear + 0.006), 0.034),
        (-0.62, (POST_FRONT + rear + 0.006) / 2, 1.65),
        (73, 85, 93),
        "PANEL_mount_arm",
    )
    # A finite stationary bearing supports the cap rim while leaving its shaft
    # in an open journal. All these parts remain outside the rotating object.
    bearing = trimesh.creation.annulus(0.0091, 0.020, 0.020, sections=96)
    a.add(
        bearing,
        (158, 165, 167),
        (-0.56, 0.4269, 1.34),
        axis=(0, 1, 0),
        metal=0.82,
        rough=0.30,
        name="MODESWITCH_fixed_thrust_bearing",
    )
    _box(a, (0.145, 0.010, 0.135), (-0.56, 0.4419, 1.34), (83, 99, 109), "MODESWITCH_mount_panel")
    _box(
        a,
        (0.045, POST_FRONT - 0.4469, 0.045),
        (-0.59, (POST_FRONT + 0.4469) / 2, 1.34),
        (73, 85, 93),
        "MODESWITCH_mount_arm",
    )
    a.label("MANUAL", (-0.56, 0.4367, 1.391), 0.070, 0.012)
    a.label("ATC", (-0.503, 0.4367, 1.34), 0.028, 0.013)
    _prop(a, "metal_toolbox", (-0.28, 0.29), TABLE_TOP, (0.31, 0.16, 0.14), rz=0)
    _prop(a, "ratchet_wrench", (0.15, -0.31), TABLE_TOP, (0.22, 0.06, 0.03), rx=90, rz=70)
    _prop(a, "lubricant_spray", (-0.53, 0.09), TABLE_TOP, (0.065, 0.065, 0.19))
    a.label("TOOL CHANGE TRAINER  /  ISOLATED", (0.03, -0.4301, 0.977), 0.60, 0.025)
    return a


def build(spec):
    fn = {
        "T09": tool,
        "T03": tool,
        "POCKET9": pocket,
        "MODESWITCH": mode_switch,
        "MAG": magazine,
        "PANEL": panel,
    }
    result = {obj.object_id: fn[obj.object_id](obj) for obj in spec.objects}
    result["environment"] = environment(spec)
    return result
