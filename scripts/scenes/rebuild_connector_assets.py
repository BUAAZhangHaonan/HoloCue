"""Connector teaching station composed from a licensed, real extrusion.

Adafruit's 2230 CAD supplies the three main housings, including the original
extrusion channels and end plates. P/S are task-specific educational adapters,
not a claim that Adafruit supplies a four-contact connector. Only their contact
inserts, locating key, socket bores and mounting pads are newly dimensioned.
"""

from __future__ import annotations

from functools import lru_cache

import cadquery as cq
import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, BRASS, STEEL
from scripts.scenes.asset_composition import mature_asset, place_scene, textured_box

SOURCE = "assets/downloads/control_panel_reconstruction/adafruit_2230.step"
PIN_CENTERS = tuple((x, z) for x in (-0.014, 0.014) for z in (-0.006, 0.006))
PIN_RADIUS = 0.0025
SOCKET_RADIUS = 0.0032
BLUE = (32, 95, 151)
DARK = (39, 45, 50)
INSULATOR = (49, 56, 62)
YELLOW = (222, 173, 39)
LIGHT_INK = (238, 243, 244)
MAT_TOP = 0.03


@lru_cache(maxsize=3)
def _source(index):
    return cq.importers.importStep(str(root() / SOURCE)).solids().vals()[index]


def _mesh(shape):
    vertices, faces = shape.scale(1000).tessellate(0.04, 0.12)
    return trimesh.Trimesh(
        vertices=np.asarray([v.toTuple() for v in vertices]) / 1000,
        faces=faces,
        process=True,
        validate=True,
    )


def _box(size, center):
    return cq.Workplane("XY").box(*size).translate(center).val()


def _axial_cylinder(radius, begin, end, x=0, z=0):
    return cq.Solid.makeCylinder(radius, end - begin, cq.Vector(x, begin, z), cq.Vector(0, 1, 0))


def _long_case(index, scale):
    # Source units are mm. Its existing extrusion axis Z becomes local +Y.
    return (
        _source(index)
        .translate((-41.4, -14.4, -45.25))
        .rotate((0, 0, 0), (1, 0, 0), -90)
        .scale(0.001 * scale)
    )


def _add(a, shape, name, color, metal=0, rough=0.42):
    return a.add(_mesh(shape), color, metal=metal, rough=rough, name=name)


def _pad(a, x, y, width, depth, bottom, top, name="rubber_support"):
    _add(a, _box((width, depth, top - bottom), (x, y, (top + bottom) / 2)), name, DARK, rough=0.65)


def _screw(a, x, y, z, axis=(0, 1, 0), radius=0.0016, name="case_screw"):
    # Real recessed slot cut through the head, rather than a painted cross.
    head = cq.Workplane("XY").circle(radius).extrude(0.0014).val()
    slot = _box((radius * 1.4, 0.00045, 0.0008), (0, 0, 0.0013))
    mesh = _mesh(head.cut(slot))
    a.add(mesh, STEEL, (x, y, z), axis=axis, metal=0.85, rough=0.28, name=name)


def _end_plate_screws(a, plate, scale, axis):
    # Read the four 2.5 mm countersink mouths from the same transformed CAD
    # plate. Their source offsets are +/-37.9 mm by +/-10.9 mm, not guesses
    # from the outer box. The 1 mm deep, 45 degree head fits the source sink.
    mouths = []
    for edge in plate.Edges():
        if edge.geomType() == "CIRCLE":
            circle = edge._geomAdaptor().Circle()
            if np.isclose(circle.Radius(), 0.0025 * scale, atol=1e-9, rtol=0):
                p = circle.Location()
                mouths.append(np.array([p.X(), p.Y(), p.Z()]))
    if len(mouths) != 4:
        raise ValueError("Expected the four original Adafruit 2230 countersinks")
    depth = 0.001 * scale
    radius = 0.00245 * scale
    head = cq.Solid.makeCone(0.00145 * scale, radius, depth)
    slot = _box((radius * 1.4, 0.0005 * scale, 0.0005 * scale), (0, 0, depth - 0.0001 * scale))
    mesh = _mesh(head.cut(slot))
    for center in mouths:
        a.add(
            mesh.copy(),
            STEEL,
            center - np.asarray(axis) * depth,
            axis=axis,
            metal=0.85,
            rough=0.28,
            name="rear_plate_screw",
        )


def plug(obj):
    a = Assembly(obj.object_id)
    scale = 0.78
    offset = -0.055 + 0.04675 * scale
    for i, name in enumerate(("extrusion", "rear_end_plate", "front_end_plate")):
        part = _long_case(i, scale).translate((0, offset, 0))
        _add(
            a,
            part,
            "Adafruit_2230_" + name,
            BLUE if i == 0 else (44, 106, 157),
            metal=0 if i == 0 else 0.8,
            rough=0.34,
        )
        if i == 1:
            _end_plate_screws(a, part, scale, (0, -1, 0))
    # These pads meet the unchanged initial work surface. They end before the
    # receiver opening at the final mating pose, so they do not enter its bore.
    for x in (-0.024, 0.024):
        _pad(a, x, -0.021, 0.007, 0.054, -0.021, -0.0144 * scale)

    neck = cq.Workplane("XY").box(0.048, 0.016, 0.022).edges("|Y").fillet(0.0012).val()
    _add(a, neck.translate((0, 0.0255, 0)), "four_contact_insulator", INSULATOR)
    key = _box((0.009, 0.017, 0.007), (0, 0.025, 0.0145))
    _add(a, key, "top_alignment_key", BLUE, rough=0.36)
    for i, (x, z) in enumerate(PIN_CENTERS, 1):
        # Short chamfered tip, a continuous cylindrical conductive body.
        shaft = _axial_cylinder(PIN_RADIUS, 0.0325, 0.0542, x, z)
        tip = cq.Solid.makeCone(PIN_RADIUS, 0.0018, 0.0008, cq.Vector(x, 0.0542, z), cq.Vector(0, 1, 0))
        _add(a, shaft.fuse(tip), f"contact_pin_{i}", BRASS, metal=0.85, rough=0.26)

    # The original inspect point is 1 mm behind the old half-length; retain it.
    a.label(
        "P  /  4 CONTACT", (0, -0.056, 0), 0.038, 0.009, (0, -1, 0), background=(28, 49, 68), ink=LIGHT_INK
    )
    a.label("P", (0, -0.019, 0.01135), 0.016, 0.008, (0, 0, 1), background=BLUE, ink=LIGHT_INK)
    return a


def socket(obj):
    a = Assembly(obj.object_id)
    scale = 0.96
    # Axial cropping is equivalent to cutting an extrusion to length. The
    # source cross-section is scaled uniformly; none of its axes is stretched.
    body = _long_case(0, scale).intersect(_box((0.2, 0.06856, 0.2), (0, -0.00072, 0)))
    slot = _box((0.0106, 0.018, 0.02), (0, -0.027, 0.016))
    body = body.cut(slot)
    _add(a, body, "Adafruit_2230_open_extrusion_with_keyway", (143, 153, 163), metal=0.82, rough=0.34)
    cap = _long_case(2, scale).translate((0, 0.035 - 0.04675 * scale, 0))
    _add(a, cap, "Adafruit_2230_rear_end_plate", (125, 136, 147), metal=0.8, rough=0.35)
    for x in (-0.029, 0.029):
        _pad(a, x, 0, 0.008, 0.060, -0.025, -0.0144 * scale)

    carrier = (
        cq.Workplane("XY").box(0.073, 0.029, 0.022).edges("|Y").fillet(0.001).translate((0, -0.006, 0)).val()
    )
    for x, z in PIN_CENTERS:
        carrier = carrier.cut(_axial_cylinder(0.00475, -0.022, 0.011, x, z))
    _add(a, carrier, "four_bore_insulating_carrier", INSULATOR)
    for i, (x, z) in enumerate(PIN_CENTERS, 1):
        tube = _axial_cylinder(0.0046, -0.022, 0.004, x, z).cut(
            _axial_cylinder(SOCKET_RADIUS, -0.023, 0.005, x, z)
        )
        # A genuine 0.6 mm lead-in chamfer enlarges only the mouth.
        lead = cq.Solid.makeCone(0.0038, SOCKET_RADIUS, 0.0006, cq.Vector(x, -0.022, z), cq.Vector(0, 1, 0))
        _add(a, tube.cut(lead), f"contact_socket_bore_{i}", BRASS, metal=0.85, rough=0.28)
    _end_plate_screws(a, cap, scale, (0, 1, 0))
    a.label("S  /  RECEIVER", (0, 0.036, 0), 0.04, 0.009, (0, 1, 0), background=(58, 66, 74), ink=LIGHT_INK)
    a.label("S", (-0.024, 0.007, 0.01395), 0.014, 0.008, (0, 0, 1), background=(107, 119, 130), ink=LIGHT_INK)
    return a


def module(obj):
    a = Assembly(obj.object_id)
    source = trimesh.load_scene(
        root() / "assets/downloads/control_panel_reconstruction/adafruit_2230_zup.glb", process=False
    )
    # The source normalization is a rigid transform. C uses the extrusion
    # vertically across its face instead of the long horizontal P/S orientation.
    scale = 0.89
    source.apply_scale(scale)
    source.apply_translation((0, 0, 0.000346))
    for node in source.graph.nodes_geometry:
        transform, geometry = source.graph[node]
        mesh = source.geometry[geometry].copy()
        mesh.apply_transform(transform)
        coated = "extrusion" in node
        a.add(
            mesh,
            (57, 114, 104) if coated else (110, 120, 126),
            metal=0 if coated else 0.8,
            rough=0.36,
            name="Adafruit_2230_" + node,
        )
    for x in (-0.026, 0.026):
        for y in (-0.008, 0.008):
            _pad(a, x, y, 0.012, 0.006, -0.0375, -0.0365)

    rear = 0.0144 * scale
    mount = _box((0.026, 0.0202, 0.046), (0, rear + 0.0101, 0))
    _add(a, mount, "rear_key_mount", DARK)
    locating = _box((0.018, 0.006, 0.042), (0, 0.036, 0))
    notch = _box((0.006, 0.009, 0.008), (0.006, 0.036, 0.021))
    label_recess = _box((0.013, 0.0003, 0.005), (0, 0.039, -0.010))
    _add(a, locating.cut(notch).cut(label_recess), "rear_yellow_locating_key", YELLOW, rough=0.45)
    for i, (x, z) in enumerate(((x, z) for x in (-0.029, 0.029) for z in (-0.018, 0.018)), 1):
        sleeve = _axial_cylinder(0.0058, rear, 0.0195, x, z)
        _add(a, sleeve, f"terminal_insulator_{i}", DARK, rough=0.55)
        terminal = _axial_cylinder(0.0037, 0.0185, 0.031, x, z)
        _add(a, terminal, f"rear_terminal_{i}", BRASS, metal=0.85, rough=0.28)
        _screw(a, x, 0.031, z, radius=0.0039, name=f"terminal_screw_{i}")
    a.label(
        "C", (0, -rear - 0.00015, 0.014), 0.025, 0.018, (0, -1, 0), background=(41, 78, 72), ink=LIGHT_INK
    )
    a.label("KEY", (0, 0.039, -0.010), 0.013, 0.005, (0, 1, 0), background=YELLOW, ink=(44, 43, 37))
    return a


def _rest_asset(a, asset_id, limits, xy, bottom, rz=0, label=None, lay_flat=False):
    """Uniformly fit an existing model, then place its actual lowest surface."""
    source = mature_asset(asset_id).copy()
    if lay_flat:
        # The source hand tools stand along Z. Put their real thin direction
        # normal to the bench before the uniform fit, without deforming them.
        thin = np.eye(3)[int(np.argmin(source.extents))]
        long = np.eye(3)[int(np.argmax(source.extents))]
        rotation = np.eye(4)
        rotation[:3, :3] = np.vstack([long, np.cross(thin, long), thin])
        source.apply_transform(rotation)
    source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    factor = float(np.min(np.asarray(limits) / source.extents))
    source.apply_scale(factor)
    center = np.array([xy[0], xy[1], bottom + source.extents[2] / 2])
    return place_scene(a, source, None, center, label=label or asset_id)


def environment(spec):
    a = Assembly("environment")
    table = mature_asset("WoodenTable_03").copy()
    table.apply_scale(max(1.08 / table.extents[0], 0.575 / table.extents[1]))
    table_bounds = place_scene(
        a, table, None, (0, 0.03, 0.024 - table.extents[2] / 2), label="real_wooden_workbench"
    )
    mat = cq.Workplane("XY").box(0.96, 0.52, 0.006).edges("|Z").fillet(0.012).val()
    _add(a, mat.translate((0, 0.03, 0.027)), "protective_work_mat", (38, 60, 54), rough=0.82)
    # At the unchanged mating pose P is 4 mm above its initial bench height.
    # These fixed rests lie within its two existing feet and carry the body;
    # the four contacts retain their clearance instead of carrying its weight.
    for x in (-0.124, -0.076):
        _pad(a, x, 0.082, 0.006, 0.046, MAT_TOP, 0.034, name="mating_foot_support")
    floor_top = float(table_bounds[0, 2])
    textured_box(
        a,
        (3.4, 3.2, 0.08),
        (0, 0.1, floor_top - 0.04),
        "concrete_floor_worn_001",
        tile_m=2.0,
        name="workshop_floor",
    )
    _rest_asset(
        a,
        "retro_multimeter",
        (0.14, 0.12, 0.07),
        (0.32, 0.19),
        MAT_TOP,
        rz=-12,
        label="real_bench_multimeter",
    )
    _rest_asset(
        a, "pliers", (0.15, 0.14, 0.028), (-0.32, 0.20), MAT_TOP, rz=-30, label="real_pliers", lay_flat=True
    )
    _rest_asset(
        a,
        "flathead_screwdriver",
        (0.17, 0.07, 0.025),
        (0.30, -0.13),
        MAT_TOP,
        rz=12,
        label="real_screwdriver",
        lay_flat=True,
    )
    # Flush work-zone tags leave the full incoming P trajectory unobstructed.
    a.label(
        "4 CONTACT TRAINING BENCH",
        (0.27, -0.04, MAT_TOP + 0.0001),
        0.24,
        0.020,
        (0, 0, 1),
        background=(43, 55, 56),
        ink=LIGHT_INK,
    )
    return a


def build(spec):
    builders = {"P": plug, "S": socket, "C": module}
    result = {obj.object_id: builders[obj.object_id](obj) for obj in spec.objects}
    result["environment"] = environment(spec)
    return result
