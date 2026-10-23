"""Licensed cylinders, threaded valve parts and gauges on an unpressurized trainer.

The BSP source components are reused as visible hardware, not relabelled as a
manufacturer DIN coupling. Small adapters preserve the original task frames.
"""

from functools import lru_cache

import cadquery as cq
import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, STEEL
from scripts.scenes.asset_composition import textured_box

SOURCE = "assets/downloads/dive_reconstruction"
BOTTLE_SCALE = 0.735 / 1.3578672016721924
FITTING_SCALE = 0.88
STEM_SCALE = 0.35
STEM_AXIAL_SPACER = 0.0035
QRC_SHIFT_Y = -0.04392
QRC_SHOULDER_Y = 0.03204
QRC_FOOT_Z = -0.020 * FITTING_SCALE
QRC_PAD_DEPTH = 0.014
QRC_TABLE_TOP = 0.89 + QRC_FOOT_Z - QRC_PAD_DEPTH
QRC_FINAL = np.array([0.35, -0.009, 1.0])
VALVE_POSITION = np.array([0.35, 0.06, 1.0])
STEM_POSITION = np.array([0.34, 0.61, 1.25])
RACK_TOP = 0.18


def _mesh(shape):
    vertices, faces = shape.scale(1000).tessellate(0.05, 0.12)
    return trimesh.Trimesh(
        np.asarray([v.toTuple() for v in vertices]) / 1000, faces, process=True, validate=True
    )


@lru_cache(maxsize=8)
def _source(filename):
    scene = trimesh.load_scene(root() / SOURCE / filename, process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return scene


def _world_mesh(scene, node):
    transform, geometry = scene.graph[node]
    mesh = scene.geometry[geometry].copy()
    mesh.apply_transform(transform)
    return mesh


def _preserve(a, mesh, name):
    key = f"{a.name}/{a.index:04d}_{name}"
    a.scene.add_geometry(mesh.copy(), node_name=key, geom_name=key)
    a.index += 1


def _append(a, scene, prefix):
    for node in scene.graph.nodes_geometry:
        _preserve(a, _world_mesh(scene, node), prefix + "_" + node)


def _box(a, size, center, name, color=(60, 76, 85), metal=0.65, rough=0.38):
    return a.add(trimesh.creation.box(size), color, center, metal=metal, rough=rough, name=name)


def _ring(a, inner, outer, low, high, center, name, axis=(0, 0, 1), color=STEEL, metal=0.75, rough=0.36):
    position = np.asarray(center) + np.asarray(axis) * (low + high) / 2
    return a.add(
        trimesh.creation.annulus(inner, outer, high - low, sections=96),
        color,
        position,
        axis=axis,
        metal=metal,
        rough=rough,
        name=name,
    )


def _label(
    a, text, center, width, height, name, normal=(0, -1, 0), background=(231, 235, 228), ink=(22, 35, 43)
):
    temporary = Assembly("text")
    temporary.label(text, center, width, height, normal, background, ink)
    mesh = next(iter(temporary.scene.geometry.values()))
    mesh.visual.material.name = text.replace("\n", " ")
    key = f"{a.name}/label_{name}"
    a.scene.add_geometry(mesh, node_name=key, geom_name=key)
    a.index += 1


@lru_cache(maxsize=1)
def bottle_source():
    scene = _source("cylinder_body.glb").copy()
    scene.apply_scale(BOTTLE_SCALE)
    for mesh in scene.geometry.values():
        mesh.visual.material.alphaMode = "OPAQUE"
    return scene


def _front_sticker(a, identifier):
    # Clip the authored triangular surface itself, rather than interpolating a
    # grid across its facet boundaries (which would dip beneath the cylinder).
    # Stay below the actual neck grooves (Z=.220233/.226636), whose horizontal
    # ledges fold a projected text row back onto itself. The upper blank label
    # band sits behind the original clamp; both printed lines remain below it.
    low_z, high_z = 0.125, 0.219
    body = bottle_source().to_geometry()
    polygons = [list(triangle) for triangle in body.triangles]
    for normal, origin in [
        ([1, 0, 0], [-0.065, 0, 0]),
        ([-1, 0, 0], [0.065, 0, 0]),
        ([0, 0, 1], [0, 0, low_z]),
        ([0, 0, -1], [0, 0, high_z]),
        ([0, -1, 0], [0, 0, 0]),
    ]:
        clipped = []
        normal, origin = np.asarray(normal), np.asarray(origin)
        for polygon in polygons:
            output = []
            for one, two in zip(polygon, polygon[1:] + polygon[:1]):
                d1, d2 = (one - origin) @ normal, (two - origin) @ normal
                if d1 >= 0:
                    output.append(one)
                if (d1 >= 0) != (d2 >= 0):
                    output.append(one + (two - one) * d1 / (d1 - d2))
            if len(output) >= 3:
                clipped.append(output)
        polygons = clipped
    vertices, faces = [], []
    for polygon in polygons:
        offset = len(vertices)
        vertices.extend(polygon)
        faces.extend([[offset, offset + i, offset + i + 1] for i in range(1, len(polygon) - 1)])
    vertices = np.asarray(vertices)
    uv = np.column_stack([(vertices[:, 0] + 0.065) / 0.13, (vertices[:, 2] - low_z) / (high_z - low_z)])
    vertices[:, 1] -= 0.00012
    text = Assembly("front_text")
    text.label("\nTRAINING\n" + identifier, (0, 0, 0), 0.13, high_z - low_z, background=(231, 235, 228))
    material = next(iter(text.scene.geometry.values())).visual.material
    material.name = "TRAINING " + identifier
    mesh = trimesh.Trimesh(
        vertices, faces, process=False, visual=trimesh.visual.TextureVisuals(uv=uv, material=material)
    )
    key = f"{a.name}/label_front_training_{identifier}"
    a.scene.add_geometry(mesh, node_name=key, geom_name=key)
    a.index += 1


def bottle(obj):
    a = Assembly(obj.object_id)
    body = bottle_source()
    _append(a, body, "Alexander_Troianovskyi_source_body")
    radius = body.extents[0] / 2
    # A physical removable training plaque reaches the fixed inspection plane.
    # It is not a floating decal on the narrower, uniformly scaled source body.
    carrier = cq.Workplane("XY").box(0.150, 0.035, 0.090).translate((0, 0.0763, 0.1628))
    clearance = cq.Workplane("XY").circle(radius + 0.00012).extrude(0.092).translate((0, 0, 0.1168))
    a.add(
        _mesh(carrier.cut(clearance).val()),
        (43, 55, 61),
        metal=0,
        rough=0.82,
        name="training_serial_plaque_carrier",
    )
    for z in [0.1168, 0.2088]:
        _ring(
            a,
            radius,
            radius + 0.0024,
            z - 0.005,
            z + 0.005,
            (0, 0, 0),
            "training_plaque_clamp_band",
            color=(35, 42, 44),
            metal=0,
            rough=0.88,
        )
    _label(
        a,
        "TRAINING\n" + obj.object_id,
        (0, 0.09393, 0.1628),
        0.144,
        0.082,
        "training_serial_label_" + obj.object_id,
        normal=(0, 1, 0),
    )
    _front_sticker(a, obj.object_id)
    if obj.object_id != "BOTTLE3":
        cap = cq.Workplane("XY").circle(0.013).extrude(0.0025).translate((0, 0, 0.3675))
        socket = cq.Workplane("XY").polygon(6, 0.008).extrude(0.001).translate((0, 0, 0.3692))
        a.add(
            _mesh(cap.cut(socket).val()),
            (72, 82, 86),
            metal=0.62,
            rough=0.39,
            name="unpressurized_hex_socket_neck_blank",
        )
    return a


@lru_cache(maxsize=10)
def _valve_part(prefix):
    scene = _source("bsp_ball_valve_original.glb")
    node = next(node for node in scene.graph.nodes_geometry if node.startswith(prefix))
    return _world_mesh(scene, node)


def _fitting_part(prefix, qrc=False):
    mesh = _valve_part(prefix).copy()
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2 if qrc else np.pi / 2, [0, 0, 1]))
    mesh.apply_scale(FITTING_SCALE)
    if qrc:
        mesh.apply_translation([0, QRC_SHIFT_Y, 0])
    return mesh


def _foot_pad(mesh, plane, depth):
    """Closed pad copied from an actual downward planar source bearing face."""
    ids = np.flatnonzero(
        (mesh.face_normals[:, 2] < -0.9999) & (np.abs(mesh.triangles_center[:, 2] - plane) < 2e-7)
    )
    if len(ids) < 2:
        raise ValueError("Missing genuine downward bearing faces")
    upper = mesh.submesh([ids], append=True, repair=False)
    upper.merge_vertices()
    count = len(upper.vertices)
    vertices = np.vstack([upper.vertices, upper.vertices - [0, 0, depth]])
    top = upper.faces[:, ::-1]
    faces = [*top, *(upper.faces + count)]
    edges = np.sort(np.vstack([top[:, [0, 1]], top[:, [1, 2]], top[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    for one, two in unique[counts == 1]:
        faces.extend([[one, two, two + count], [one, two + count, one + count]])
    result = trimesh.Trimesh(vertices, faces, process=True)
    result.fix_normals(multibody=True)
    return result


@lru_cache(maxsize=1)
def qrc_seat():
    return _foot_pad(_fitting_part("Body4_", True), QRC_FOOT_Z, QRC_PAD_DEPTH)


def qrc(obj):
    a = Assembly(obj.object_id)
    for prefix in ["Body4_", "Body6_"]:
        a.add(
            _fitting_part(prefix, True),
            (150, 163, 170),
            metal=0.86,
            rough=0.29,
            name="Freek_complete_threaded_coupling_" + prefix,
        )
    # Open teaching spigot: the distal ring remains at original mating +Y=.045.
    # The inherited BSP coupling is the grip housing, not a DIN specification.
    profile = [
        (0.004, -0.044),
        (0.009, -0.044),
        (0.0105, -0.041),
        (0.0105, -0.034),
        (0.020, -0.034),
        (0.020, -0.030),
        (0.0125, -0.030),
        (0.0125, QRC_SHOULDER_Y - 0.003),
        (0.017, QRC_SHOULDER_Y - 0.003),
        (0.017, QRC_SHOULDER_Y),
        (0.0125, QRC_SHOULDER_Y),
        (0.0125, 0.043),
        (0.0118, 0.045),
        (0.004, 0.045),
        (0.004, -0.044),
    ]
    mesh = trimesh.creation.revolve(np.asarray(profile), sections=128)
    mesh.fix_normals()
    a.add(mesh, (171, 147, 88), axis=(0, 1, 0), metal=0.82, rough=0.31, name="teaching_open_mating_spigot")

    return a


def valve(obj):
    a = Assembly(obj.object_id)
    for prefix in ["Body3_", "Body4_", "Body6_", "Body7_"]:
        a.add(
            _fitting_part(prefix),
            (150, 163, 170),
            metal=0.86,
            rough=0.29,
            name="Freek_fixed_receiver_" + prefix,
        )
    # Retain the genuine source spindle boss but close this static teaching
    # receiver locally; the separate STEM task lives on the rear manifold.
    a.add(
        trimesh.creation.cylinder(0.008, 0.002, sections=48),
        (44, 52, 56),
        (0, 0, 0.03884),
        metal=0,
        rough=0.76,
        name="isolated_receiver_stem_cover",
    )
    return a


def _stem_transform(mesh):
    result = mesh.copy()
    result.apply_translation([0, 0, -0.043])
    result.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    result.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    result.apply_scale(STEM_SCALE)
    return result


def stem(obj):
    a = Assembly(obj.object_id)
    for prefix in ["Body1_Stainless", "Body1__", "Body2_", "Body5_"]:
        mesh = _stem_transform(_valve_part(prefix))
        mesh.apply_translation([0, -STEM_AXIAL_SPACER, 0])
        plastic = prefix == "Body1__"
        a.add(
            mesh,
            (182, 51, 39) if plastic else (157, 170, 177),
            metal=0 if plastic else 0.86,
            rough=0.78 if plastic else 0.28,
            name="Freek_rotating_handle_" + prefix,
        )
    a.add(
        trimesh.creation.cylinder(0.00165, 0.00635, sections=64),
        (145, 158, 164),
        (0, -0.003175, 0),
        axis=(0, -1, 0),
        metal=0.8,
        rough=0.3,
        name="teaching_extended_rotating_spindle",
    )
    return a


def gauges(obj):
    a = Assembly(obj.object_id)
    for index, x in enumerate([-0.125, 0, 0.125], 1):
        scene = _source("pressure_gauge_aligned.glb").copy()
        scene.apply_scale(0.0399)
        scene.apply_translation([x, 0, 0])
        for node in scene.graph.nodes_geometry:
            transform, key = scene.graph[node]
            mesh = scene.geometry[key].copy()
            mesh.apply_transform(transform)
            if "glass" in node:
                material = mesh.visual.material.copy()
                material.metallicFactor = 0
                material.roughnessFactor = 0.14
                mesh.visual.material = material
            _preserve(a, mesh, f"takeboncog_gauge_{index}_" + node)
    board = cq.Workplane("XZ").rect(0.4, 0.16).extrude(0.006).translate((0, 0.04, 0))
    for x in [-0.125, 0, 0.125]:
        bore = cq.Solid.makeCylinder(0.017, 0.012, cq.Vector(x, 0.031, 0), cq.Vector(0, 1, 0))
        board = board.cut(bore)
    a.add(
        _mesh(board.val()), (40, 56, 67), metal=0.35, rough=0.47, name="gauge_backplate_with_real_mount_holes"
    )
    for x, text in [(-0.125, "TRAINING 1"), (0, "TRAINING 2"), (0.125, "TRAINING 3")]:
        _label(a, text, (x, 0.0338, -0.061), 0.105, 0.014, text.replace(" ", "_"))
    return a


def _profile(a, length, start, direction, name):
    scene = trimesh.load_scene(
        root() / "assets/downloads/cnc_reconstruction/araki_3030_post.glb", process=False
    )
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    scene.apply_scale(length / 1.5)
    scene.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
    scene.apply_translation(start)
    for node in scene.graph.nodes_geometry:
        a.add(_world_mesh(scene, node), (125, 141, 149), metal=0.78, rough=0.35, name=name)


def _pipe(a, points, radius, name, color=(153, 132, 88), metal=0.76):
    for first, second in zip(points[:-1], points[1:]):
        a.add(
            trimesh.creation.cylinder(radius=radius, segment=[first, second], sections=48),
            color,
            metal=metal,
            rough=0.38,
            name=name,
        )
    for point in points[1:-1]:
        a.add(
            trimesh.creation.icosphere(subdivisions=2, radius=radius),
            color,
            point,
            metal=metal,
            rough=0.38,
            name=name + "_elbow",
        )


def environment(spec):
    a = Assembly("dive_fillstation_environment")
    textured_box(a, (2.6, 2.4, 0.06), (0, 0.26, -0.03), "hangar_concrete_floor", tile_m=1.5, name="floor")
    _box(a, (1.10, 0.44, 0.028), (0, 0.07, RACK_TOP - 0.014), "cylinder_rack_deck", metal=0.65)
    for x in [-0.46, 0.46]:
        for y in [-0.08, 0.22]:
            a.add(
                trimesh.creation.cylinder(0.041, 0.152, sections=64),
                (34, 42, 45),
                (x, y, 0.076),
                metal=0,
                rough=0.9,
                name="rack_floor_foot",
            )
    body = bottle_source().to_geometry()
    bottom_faces = np.flatnonzero((body.face_normals[:, 2] < -0.9999) & (body.triangles_center[:, 2] < -0.30))
    bottom_plane = float(np.min(body.triangles_center[bottom_faces, 2]))
    pad = _foot_pad(body, bottom_plane, bottom_plane + 0.56 - RACK_TOP)
    radius = body.extents[0] / 2
    for obj in spec.objects:
        if obj.object_id.startswith("BOTTLE"):
            position = np.asarray(obj.pose.position_m)
            a.add(pad, (42, 49, 50), position, metal=0, rough=0.9, name=obj.object_id + "_actual_bottom_seat")
            x, y, _ = position
            _ring(
                a,
                radius + 0.0002,
                radius + 0.004,
                0.425,
                0.449,
                (x, y, 0),
                obj.object_id + "_rack_restraint",
                color=(101, 119, 128),
                metal=0.72,
            )
            front = y + radius + 0.002
            _box(
                a,
                (0.035, 0.761 - front, 0.02),
                (x, (0.761 + front) / 2, 0.437),
                obj.object_id + "_restraint_rear_brace",
            )
    for x in [-0.53, 0.53]:
        a.add(
            trimesh.creation.cylinder(0.045, 0.03, sections=64),
            (32, 40, 45),
            (x, 0.77, 0.015),
            metal=0,
            rough=0.9,
            name="rear_frame_floor_foot",
        )
        _profile(a, 1.62, (x, 0.77, 0.03), (0, 0, 1), "Araki_source_rear_upright")
    for z in [0.45, 1.63]:
        _profile(a, 1.06, (-0.53, 0.77, z), (1, 0, 0), "Araki_source_rear_crossbeam")
    _box(
        a,
        (1.06, 0.018, 1.18),
        (0, 0.77, 1.04),
        "painted_instrument_backboard",
        (107, 135, 148),
        metal=0.25,
        rough=0.5,
    )
    _label(a, "DEPRESSURIZED\nTRAINING EQUIPMENT", (0, 0.7608, 0.98), 0.72, 0.16, "station_state")
    # QRC's initial seat is copied from its actual hexagonal bearing face.
    for x in [0.43, 0.67]:
        for y in [-0.40, -0.20]:
            a.add(
                trimesh.creation.cylinder(0.022, 0.03, sections=48),
                (32, 40, 45),
                (x, y, 0.015),
                metal=0,
                rough=0.9,
                name="QRC_rest_floor_foot",
            )
            _profile(a, QRC_TABLE_TOP - 0.038, (x, y, 0.03), (0, 0, 1), "Araki_source_QRC_stand_leg")
    _box(a, (0.30, 0.26, 0.008), (0.55, -0.30, QRC_TABLE_TOP - 0.004), "QRC_rest_top", (71, 86, 94))
    a.add(
        qrc_seat(), (45, 53, 58), (0.55, -0.30, 0.89), metal=0, rough=0.86, name="QRC_initial_true_hex_seat"
    )
    # The isolated receiver and final coupling are physically carried by this
    # neck-mounted training bridge, including a lower seat for the final QRC.
    a.add(
        trimesh.creation.cylinder(0.011, 0.0125, sections=64),
        (151, 165, 173),
        (0.35, 0.06, 0.93375),
        metal=0.8,
        rough=0.35,
        name="BOTTLE3_neck_fixture_adapter",
    )
    _box(a, (0.055, 0.155, 0.010), (0.35, 0.0245, 0.945), "receiver_and_QRC_training_bridge")
    seat = qrc_seat()
    a.add(seat, (45, 53, 58), QRC_FINAL, metal=0, rough=0.86, name="QRC_final_true_hex_seat")
    bounds = seat.bounds + QRC_FINAL
    _box(
        a,
        (bounds[1, 0] - bounds[0, 0], bounds[1, 1] - bounds[0, 1], bounds[0, 2] - 0.95),
        [*bounds.mean(axis=0)[:2], (0.95 + bounds[0, 2]) / 2],
        "QRC_final_seat_bridge_post",
    )
    for prefix in ["Body3_", "Body4_"]:
        part = _fitting_part(prefix)
        contact = _foot_pad(part, QRC_FOOT_Z, 0.014)
        a.add(
            contact,
            (56, 67, 75),
            VALVE_POSITION,
            metal=0.65,
            rough=0.42,
            name="VALVE_actual_hex_seat_" + prefix,
        )
        bounds = contact.bounds + VALVE_POSITION
        _box(
            a,
            (np.ptp(bounds[:, 0]), np.ptp(bounds[:, 1]), bounds[0, 2] - 0.95),
            [*bounds.mean(axis=0)[:2], (0.95 + bounds[0, 2]) / 2],
            "VALVE_seat_bridge_post_" + prefix,
        )
    # Complete original fixed valve body, separated from the moving STEM mesh.
    for prefix in ["Body3_", "Body4_", "Body6_", "Body7_"]:
        a.add(
            _stem_transform(_valve_part(prefix)),
            (148, 162, 171),
            STEM_POSITION,
            metal=0.86,
            rough=0.29,
            name="Freek_STEM_fixed_valve_" + prefix,
        )
    for prefix in ["Body3_", "Body4_"]:
        pad = _stem_transform(_foot_pad(_valve_part(prefix), -0.020, 0.015))
        a.add(
            pad,
            (53, 66, 73),
            STEM_POSITION,
            metal=0.65,
            rough=0.42,
            name="STEM_fixed_actual_hex_seat_" + prefix,
        )
    _ring(
        a,
        0.0019,
        0.0037,
        0,
        STEM_AXIAL_SPACER + 0.0001 * STEM_SCALE,
        STEM_POSITION,
        "STEM_fixed_axial_bearing_spacer",
        axis=(0, -1, 0),
        metal=0.72,
        rough=0.36,
    )
    block_front = 0.61 + (0.043 + 0.035) * STEM_SCALE
    # Open bent-plate bracket: the actual two source hex seats meet its front
    # plate, while two narrow webs carry load back to the instrument board.
    _box(a, (0.038, 0.004, 0.042), (0.34, block_front + 0.002, 1.25), "STEM_front_bearing_mount_plate")
    _box(a, (0.055, 0.004, 0.065), (0.34, 0.759, 1.25), "STEM_rear_mount_plate")
    for x in [0.323, 0.357]:
        _box(
            a,
            (0.004, 0.757 - block_front - 0.004, 0.035),
            (x, (0.757 + block_front + 0.004) / 2, 1.25),
            "STEM_open_mount_side_web",
        )
    for x in [0.321, 0.359]:
        for z in [1.226, 1.274]:
            bolt = _valve_part("Body2_").copy()
            bolt.apply_translation([0, 0, -0.052])
            bolt.apply_scale(0.3)
            bolt.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
            a.add(
                bolt,
                (141, 155, 163),
                (x, 0.7558, z),
                metal=0.82,
                rough=0.32,
                name="Freek_source_bracket_fastener",
            )
    for x in [-0.16, 0.16]:
        _box(a, (0.045, 0.061, 0.045), (x, 0.7305, 1.55), "GAUGES_rear_mount_standoff")
    _pipe(a, [(-0.43, 0.695, 1.34), (0.43, 0.695, 1.34)], 0.012, "isolated_manifold_tube")
    for x in [-0.125, 0, 0.125]:
        _pipe(
            a,
            [(x, 0.70, 1.55), (x, 0.725, 1.55), (x, 0.725, 1.34), (x, 0.695, 1.34)],
            0.005,
            "gauge_rear_training_tube",
        )
    _pipe(
        a,
        [(0.34, 0.625, 1.2647), (0.34, 0.625, 1.34), (0.34, 0.695, 1.34)],
        0.0055,
        "STEM_upper_training_tube",
    )
    _pipe(
        a,
        [
            (0.34, 0.625, 1.2353),
            (0.34, 0.625, 1.13),
            (0.51, 0.625, 1.13),
            (0.61, 0.50, 1.03),
            (0.64, 0.30, 0.77),
            (0.63, 0.15, 0.72),
        ],
        0.007,
        "parked_unpressurized_hose",
        color=(31, 40, 44),
        metal=0,
    )
    _box(a, (0.04, 0.04, 0.04), (0.63, 0.15, 0.70), "parked_hose_end_holder", metal=0)
    _pipe(
        a,
        [(0.63, 0.15, 0.68), (0.63, 0.77, 0.68), (0.53, 0.77, 0.68)],
        0.009,
        "hose_storage_support",
        color=STEEL,
        metal=0.75,
    )
    return a


def build(spec):
    builders = {
        "QRC": qrc,
        "VALVE": valve,
        "BOTTLE1": bottle,
        "BOTTLE2": bottle,
        "BOTTLE3": bottle,
        "STEM": stem,
        "GAUGES": gauges,
    }
    result = {obj.object_id: builders[obj.object_id](obj) for obj in spec.objects}
    result["environment"] = environment(spec)
    return result
