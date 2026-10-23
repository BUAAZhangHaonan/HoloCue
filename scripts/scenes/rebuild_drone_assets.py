"""Licensed PX4 airframe, 5010 motors and authored battery service interfaces.

All sourced parts keep their proportions. This is a teaching fixture assembled
from attributed models, not a claim to reproduce a certified flight vehicle.
"""

from functools import lru_cache
import cadquery as cq
import numpy as np
import trimesh
from holocue.config import root
from holocue.modeling import Assembly, STEEL
from scripts.scenes.asset_composition import mature_asset, place_scene, textured_box

SOURCE = "assets/downloads/drone_reconstruction"
FRAME_SCALE = 0.22 / 0.174
FRAME_TOP = 0.0965 + 0.0001036169996950868 * FRAME_SCALE
FRAME_BOTTOM = FRAME_TOP - 0.026363959535956386 * FRAME_SCALE
MAT_TOP = 0.030
RAIL_X = 0.0315
RAIL_BOTTOM = -0.0255


def _mesh(shape):
    vertices, faces = shape.scale(1000).tessellate(0.05, 0.12)
    return trimesh.Trimesh(
        vertices=np.asarray([v.toTuple() for v in vertices]) / 1000, faces=faces, process=True, validate=True
    )


@lru_cache(maxsize=8)
def _source(filename):
    scene = trimesh.load_scene(root() / SOURCE / filename, process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return scene


def _append(a, source, label):
    for node in source.graph.nodes_geometry:
        transform, g = source.graph[node]
        name = f"{a.name}/{a.index:04d}_{label}_{node}"
        a.scene.add_geometry(source.geometry[g].copy(), node_name=name, geom_name=name, transform=transform)
        a.index += 1


def _box(a, size, center, color, name, metal=0, rough=0.5):
    return a.add(trimesh.creation.box(size), color, center, metal=metal, rough=rough, name=name)


def _socket_head(a, position, radius=0.0022, name="socket_fastener"):
    head = cq.Workplane("XY").circle(radius).extrude(0.0016)
    hole = cq.Workplane("XY").polygon(6, radius * 1.02).extrude(0.0012).translate((0, 0, 0.0006))
    a.add(_mesh(head.cut(hole).val()), STEEL, position, metal=0.82, rough=0.27, name=name)


def _world_mesh(scene, node):
    transform, g = scene.graph[node]
    m = scene.geometry[g].copy()
    m.apply_transform(transform)
    return m


def _vertical_hits(mesh, xy):
    triangles = mesh.triangles
    a = triangles[:, 0, :2]
    u = triangles[:, 1, :2] - a
    v = triangles[:, 2, :2] - a
    q = np.asarray(xy) - a
    determinant = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    valid = np.abs(determinant) > 1e-18
    b = np.zeros(len(a))
    c = np.zeros(len(a))
    b[valid] = (q[valid, 0] * v[valid, 1] - q[valid, 1] * v[valid, 0]) / determinant[valid]
    c[valid] = (u[valid, 0] * q[valid, 1] - u[valid, 1] * q[valid, 0]) / determinant[valid]
    valid &= (b >= -1e-9) & (c >= -1e-9) & (b + c <= 1 + 1e-9)
    return (
        triangles[:, 0, 2]
        + b * (triangles[:, 1, 2] - triangles[:, 0, 2])
        + c * (triangles[:, 2, 2] - triangles[:, 0, 2])
    )[valid]


def battery(obj):
    a = Assembly(obj.object_id)
    # Reuse the complete lower converter shell, without inventing an assembly
    # between its two exploded source versions. Only the lower source is used.
    shell = _source("jayden_lipo_converter.glb")
    mesh = _world_mesh(shell, "Object_2")
    mesh.apply_translation([-mesh.bounds.mean(axis=0)[0], -mesh.bounds.mean(axis=0)[1], 0])
    mesh.apply_scale(0.0015)
    mesh.apply_translation([0, 0, -0.0215])
    a.add(mesh, (61, 75, 84), metal=0, rough=0.49, name="Jayden_Downes_converter_lower_shell")
    # A flat adapter gives the two original shell ribs an explicit load path.
    # Its two bosses meet source back-wall bottoms at z=0 (source coordinates).
    _box(a, (0.078, 0.126, 0.002), (0, 0, -0.0225), (53, 61, 67), "battery_interface_base", 0.25, 0.42)
    for x in (-RAIL_X, RAIL_X):
        _box(a, (0.008, 0.111, 0.004), (x, 0, -0.0235), (77, 85, 92), "battery_bottom_rail", 0.65, 0.30)
    for x in (-0.010, 0.010):
        _box(a, (0.006, 0.010, 0.001), (x, 0.037, -0.0240), (189, 156, 75), "battery_contact_pad", 0.86, 0.27)
    # Two complete sourced LiPo bodies occupy the converter interior. The
    # original long external leads are omitted as whole connected components;
    # this is explicitly a teaching contact cassette, not a Tattu product.
    pack_bottom = -0.0104
    for index, x in enumerate((-0.0125, 0.0125)):
        source = _source("tattu_pack_body.glb").copy()
        source.apply_scale(0.00049)
        source.apply_translation(
            np.asarray([x, -0.002, pack_bottom]) - np.r_[source.bounds.mean(axis=0)[:2], source.bounds[0, 2]]
        )
        _append(a, source, f"bhaktaj_LiPo_module_{index + 1}")
        for y in (0.003, 0.026):
            vertices = []
            for xx, yy in [
                (x - 0.0105, y - 0.003),
                (x + 0.0105, y - 0.003),
                (x + 0.0105, y + 0.003),
                (x - 0.0105, y + 0.003),
            ]:
                hits = _vertical_hits(mesh, (xx, yy))
                levels = hits[hits < pack_bottom]
                if not len(levels):
                    raise ValueError("No converter floor beneath pack foam seat")
                vertices.append([xx, yy, float(np.max(levels))])
            vertices.extend([[v[0], v[1], pack_bottom] for v in vertices])
            faces = [
                [0, 2, 1],
                [0, 3, 2],
                [4, 5, 6],
                [4, 6, 7],
                [0, 1, 5],
                [0, 5, 4],
                [1, 2, 6],
                [1, 6, 5],
                [2, 3, 7],
                [2, 7, 6],
                [3, 0, 4],
                [3, 4, 7],
            ]
            a.add(
                trimesh.Trimesh(vertices, faces, process=True),
                (37, 42, 45),
                metal=0,
                rough=0.92,
                name="battery_pack_foam_seat",
            )
        top = float(source.bounds[1, 2])
        a.label(
            f"LiPo {index + 1}\nSERVICE MODULE",
            (x, 0.004, top + 0.00006),
            0.020,
            0.043,
            (0, 0, 1),
            (216, 220, 213),
            (42, 48, 50),
        )
    a.label(
        "BAT  /  KEYED CARRIER",
        (0, -0.06305, -0.018),
        0.059,
        0.007,
        (0, -1, 0),
        (66, 76, 83),
        (232, 235, 223),
    )
    return a


def bay(obj):
    a = Assembly(obj.object_id)
    _box(a, (0.1, 0.148, 0.003), (0, 0, -0.0285), (58, 65, 71), "bay_structural_floor", 0.55, 0.38)
    for x in (-0.048, 0.048):
        _box(a, (0.004, 0.148, 0.057), (x, 0, 0.0015), (61, 72, 81), "bay_open_side_wall", 0.52, 0.37)
    for y in (-0.072, 0.072):
        _box(a, (0.092, 0.004, 0.057), (0, y, 0.0015), (61, 72, 81), "bay_open_end_wall", 0.52, 0.37)
    for x in (-RAIL_X, RAIL_X):
        _box(a, (0.009, 0.114, 0.0015), (x, 0, -0.02625), (163, 169, 172), "bay_rail_stop", 0.75, 0.29)
    for x in (-0.010, 0.010):
        a.add(
            trimesh.creation.cylinder(0.002, 0.0025, sections=32),
            (191, 163, 90),
            (x, 0.037, -0.02575),
            metal=0.85,
            rough=0.27,
            name="bay_spring_contact",
        )
    for x in (-0.048, 0.048):
        for y in (-0.061, 0.061):
            _socket_head(a, (x, y, 0.0284), 0.0017, "bay_wall_fastener")
    a.label(
        "BAY  /  INSERT +Z", (0, -0.07405, 0.012), 0.075, 0.011, (0, -1, 0), (61, 72, 81), (229, 232, 216)
    )
    return a


@lru_cache(maxsize=1)
def _knob():
    source = trimesh.load_scene(
        root() / "assets/downloads/control_panel_reconstruction/emaitee_knob.glb", process=False
    )
    mesh = source.to_geometry()
    mesh.apply_translation([0, -32.1573753356934, 118.75])
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    mesh.apply_scale(0.001)
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh


def guard(obj):
    a = Assembly(obj.object_id)
    mesh = _knob().copy()
    mesh.apply_scale(1.5)
    mesh.apply_translation([0, 0, -0.00975])
    a.add(mesh, (187, 90, 31), metal=0, rough=0.40, name="emaitee_guard_knob")
    a.add(
        trimesh.creation.cylinder(0.0029, 0.014, sections=48),
        STEEL,
        (0, 0, -0.0035),
        metal=0.82,
        rough=0.28,
        name="guard_rotating_shaft",
    )
    _box(
        a,
        (0.0013, 0.0050, 0.0003),
        (0, 0.0030, 0.00990),
        (238, 238, 224),
        "guard_white_rotation_mark",
        0,
        0.45,
    )
    return a


def motor(obj):
    a = Assembly(obj.object_id)
    for filename, dz in [("px4_5010_stator.glb", -0.005), ("px4_5010_bell.glb", -0.009)]:
        s = _source(filename).copy()
        s.apply_translation([0, 0, dz])
        _append(a, s, "PX4_5010")
    a.add(
        trimesh.creation.annulus(0.004, 0.014, 0.0105, sections=64),
        STEEL,
        (0, 0, -0.01725),
        metal=0.8,
        rough=0.30,
        name="motor_mount_adapter",
    )
    a.add(
        trimesh.creation.cylinder(0.003, 0.0105, sections=48),
        STEEL,
        (0, 0, 0.01725),
        metal=0.84,
        rough=0.27,
        name="exposed_motor_spindle",
    )
    for angle in np.arange(0, 360, 90) + 45:
        t = np.radians(angle)
        _socket_head(a, (0.011 * np.cos(t), 0.011 * np.sin(t), -0.012), 0.0015, "motor_mount_screw")
    if obj.object_id == "M3":
        # Open-center elastomer adapter: the inspection point stays in its hole.
        a.add(
            trimesh.creation.annulus(0.0055, 0.011, 0.003, sections=96),
            (235, 82, 9),
            (0.0345, 0, -0.005),
            axis=(1, 0, 0),
            metal=0,
            rough=0.92,
            name="isolator_ring",
        )
        a.add(
            trimesh.creation.annulus(0.0055, 0.0114, 0.002, sections=96),
            (76, 87, 95),
            (0.032, 0, -0.005),
            axis=(1, 0, 0),
            metal=0.65,
            rough=0.35,
            name="isolator_backing_ring",
        )
        _box(
            a, (0.021, 0.010, 0.002), (0.0205, 0, -0.020), (76, 87, 95), "isolator_lower_bracket", 0.65, 0.35
        )
        _box(
            a, (0.002, 0.010, 0.010), (0.030, 0, -0.014), (76, 87, 95), "isolator_upright_bracket", 0.65, 0.35
        )
    return a


def voltmeter(obj):
    a = Assembly(obj.object_id)
    s = mature_asset("retro_multimeter").copy()
    s.apply_scale(min(np.asarray(obj.size_m) / s.extents))
    s.apply_translation(-s.bounds.mean(axis=0))
    _append(a, s, "PolyHaven_retro_multimeter")
    return a


def _prop(a, asset_id, maximum, xy, bottom, rz=0, rx=0):
    s = mature_asset(asset_id).copy()
    if rx:
        s.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rx), [1, 0, 0]))
    s.apply_scale(min(np.asarray(maximum) / s.extents))
    if rz:
        s.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    s.apply_translation(np.asarray([*xy, bottom]) - np.r_[s.bounds.mean(axis=0)[:2], s.bounds[0, 2]])
    _append(a, s, asset_id)


def environment(spec):
    a = Assembly("drone_bench_environment")
    table = mature_asset("WoodenTable_03").copy()
    table.apply_scale(0.7525 / table.extents[2])
    table.apply_translation(
        np.asarray([0, 0.12, -0.7375]) - np.r_[table.bounds.mean(axis=0)[:2], table.bounds[0, 2]]
    )
    _append(a, table, "airframe_service_table")
    _box(a, (1.25, 1.06, 0.012), (0, 0.12, 0.021), (161, 164, 157), "laminated_bench_top", 0, 0.6)
    textured_box(a, (2.6, 2.5, 0.035), (0, 0.12, -0.755), "concrete_floor_worn_001", name="visible_floor")
    # True 2 mm pockets let the original BAT rails rest at world .028; the
    # rest of the ESD mat stays at .030. This is not a black visual decal.
    mat = cq.Workplane("XY").box(1.06, 0.97, 0.003).translate((0, 0.115, 0.0285))
    for x in (-RAIL_X, RAIL_X):
        slot = cq.Workplane("XY").box(0.0088, 0.112, 0.003).translate((x, 0, 0.0295))
        slot = slot.rotate((0, 0, 0), (0, 0, 1), 20).translate((0.34, -0.25, 0))
        mat = mat.cut(slot)
    # The two contact pads extend 1 mm below the main body, so their staging
    # recesses have a real .029 m floor beside the deeper rail pockets.
    for x in (-0.010, 0.010):
        slot = cq.Workplane("XY").box(0.0068, 0.0108, 0.002).translate((x, 0.037, 0.030))
        slot = slot.rotate((0, 0, 0), (0, 0, 1), 20).translate((0.34, -0.25, 0))
        mat = mat.cut(slot)
    a.add(_mesh(mat.val()), (51, 69, 72), metal=0, rough=0.82, name="esd_mat_with_battery_rail_pockets")
    frame = _source("px4_frame.glb").copy()
    frame.apply_scale(FRAME_SCALE)
    frame.apply_translation([0, 0, FRAME_TOP])
    _append(a, frame, "PX4_X500_frame")
    for x in (-0.079, 0.079):
        _box(
            a,
            (0.018, 0.135, FRAME_BOTTOM - MAT_TOP - 0.001),
            (x, 0, (MAT_TOP + FRAME_BOTTOM - 0.001) / 2),
            (74, 83, 88),
            "frame_service_cradle",
            0.5,
            0.42,
        )
        _box(
            a,
            (0.018, 0.135, 0.001),
            (x, 0, FRAME_BOTTOM - 0.0005),
            (32, 38, 41),
            "frame_cradle_contact_pad",
            0,
            0.90,
        )
    # End-plate tops vary by 0.081 mm in the original CAD. Read the real plate
    # surface at each motor seat instead of replacing that detail by an AABB.
    fmesh = frame.to_geometry()
    for obj in spec.objects:
        if not obj.object_id.startswith("M") or obj.object_id == "VOLTMETER":
            continue
        x, y, _ = obj.pose.position_m
        angles = np.arange(32) * 2 * np.pi / 32
        origins = np.c_[x + 0.012 * np.cos(angles), y + 0.012 * np.sin(angles), np.full(32, 0.10)]
        hit = np.concatenate([_vertical_hits(fmesh, origin[:2]) for origin in origins])
        levels = hit[(hit > 0.094) & (hit < 0.0975)]
        if not len(levels):
            raise ValueError("No real PX4 motor plate below " + obj.object_id)
        bottom = float(np.max(levels))
        top = 0.0975
        a.add(
            trimesh.creation.annulus(0.004, 0.014, top - bottom, sections=64),
            STEEL,
            (x, y, (top + bottom) / 2),
            metal=0.80,
            rough=0.30,
            name=obj.object_id + "_stationary_motor_seat",
        )
    # Two bridges rest on the real top carbon plate and carry the bay floor.
    for x in (-0.040, 0.040):
        _box(
            a,
            (0.012, 0.100, 0.125 - FRAME_TOP),
            (x, 0.020, (0.125 + FRAME_TOP) / 2),
            (71, 81, 89),
            "bay_to_frame_bridge",
            0.65,
            0.38,
        )
    # Fixed bearing components are outside GUARD, whose entire body rotates.
    _box(a, (0.034, 0.026, 0.007), (0.066, 0.025, 0.1535), (73, 84, 92), "guard_fixed_bay_ear", 0.65, 0.34)
    a.add(
        trimesh.creation.cylinder(0.008, 0.0105, sections=64),
        STEEL,
        (0.072, 0.025, 0.16225),
        metal=0.75,
        rough=0.33,
        name="guard_fixed_pedestal",
    )
    a.add(
        trimesh.creation.annulus(0.0031, 0.008, 0.0005, sections=64),
        STEEL,
        (0.072, 0.025, 0.16775),
        metal=0.80,
        rough=0.30,
        name="guard_journal_bearing",
    )
    a.add(
        trimesh.creation.annulus(0.00455, 0.008, 0.00025, sections=64),
        (92, 102, 108),
        (0.072, 0.025, 0.168125),
        metal=0.65,
        rough=0.35,
        name="guard_thrust_bearing",
    )
    _prop(a, "flathead_screwdriver", (0.028, 0.21, 0.028), (0.41, 0.19), MAT_TOP, rz=-12, rx=-94.4513246615)
    _prop(a, "screwdrivers_02", (0.13, 0.25, 0.026), (0.25, 0.44), MAT_TOP, rz=90)
    a.label("AIRFRAME SERVICE  /  PROPELLERS REMOVED", (0, -0.391, 0.018), 0.46, 0.017)
    a.label(
        "BATTERY STAGING  /  ISOLATED",
        (0.335, -0.337, 0.03008),
        0.22,
        0.013,
        (0, 0, 1),
        (51, 69, 72),
        (216, 225, 218),
    )
    return a


def build(spec):
    functions = {
        "BAT": battery,
        "BAY": bay,
        "GUARD": guard,
        "M1": motor,
        "M2": motor,
        "M3": motor,
        "M4": motor,
        "VOLTMETER": voltmeter,
    }
    result = {obj.object_id: functions[obj.object_id](obj) for obj in spec.objects}
    result["environment"] = environment(spec)
    return result
