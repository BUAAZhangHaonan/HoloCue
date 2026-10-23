"""Asset-based controls with static instrument bearings and a keyed teaching module.

The source knob, potentiometer solids and extrusion preserve their proportions.
Only the finite training interfaces, mounting panel and pointer are authored here.
"""

from functools import lru_cache

import cadquery as cq
import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, STEEL
from scripts.scenes.asset_composition import mature_asset, place_scene, textured_box

SOURCE_DIR = "assets/downloads/control_panel_reconstruction"
CAP_TOP = 0.0266
POT_ORIGIN_Z = 0.0407
PANEL_TOP = 0.051
TABLE_TOP = 0.030
MAT_TOP = 0.033
SCALES = {"A": 3.2, "B": 3.4}


@lru_cache(maxsize=2)
def _cad_source(name):
    return tuple(cq.importers.importStep(str(root() / SOURCE_DIR / name)).solids().vals())


def _mesh(shape):
    """Tessellate metre shapes at a physically fixed 0.05 mm tolerance."""
    vertices, faces = shape.scale(1000).tessellate(0.05, 0.12)
    return trimesh.Trimesh(
        vertices=np.asarray([v.toTuple() for v in vertices]) / 1000,
        faces=faces,
        process=True,
        validate=True,
    )


@lru_cache(maxsize=1)
def _knob_mesh():
    # The published GLB has an X-axis cap in mm, with an offset CAD origin.
    scene = trimesh.load_scene(root() / SOURCE_DIR / "emaitee_knob.glb", process=False)
    mesh = scene.to_geometry()
    mesh.apply_translation([0, -32.1573753356934, 118.75])
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    mesh.apply_scale(0.001)
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh


def _cap_bottom(obj):
    return CAP_TOP - 0.013 * SCALES[obj.object_id]


def knob(obj):
    a = Assembly(obj.object_id)
    scale = SCALES[obj.object_id]
    mesh = _knob_mesh().copy()
    mesh.apply_scale(scale)
    mesh.apply_translation((0, 0, _cap_bottom(obj)))
    a.add(mesh, tuple(obj.color), rough=0.34, name="emaitee_fluted_knob")
    # The actual source shaft is the rotating solid; all its stator parts stay
    # in the environment. The small sleeve adapts the enlarged teaching cap.
    shaft = _cad_source("adafruit_562.step")[2].scale(0.001)
    a.add(
        _mesh(shaft),
        STEEL,
        (0, 0, POT_ORIGIN_Z - obj.pose.position_m[2]),
        metal=0.82,
        rough=0.27,
        name="Adafruit_562_rotating_shaft",
    )
    sleeve = trimesh.creation.annulus(0.00305, 0.00296675 * scale - 0.000015, 0.0073, sections=64)
    a.add(
        sleeve,
        (110, 116, 122),
        (0, 0, 0.05465 - obj.pose.position_m[2]),
        metal=0.7,
        rough=0.3,
        name="shaft_adapter_sleeve",
    )
    a.add(
        trimesh.creation.box(extents=(0.0028, 0.0090, 0.0005)),
        (245, 244, 232),
        (0, 0.0065, CAP_TOP + 0.00025),
        metal=0,
        rough=0.42,
        name="white_rotation_indicator",
    )
    return a


def _housing_shape(index):
    return (
        _cad_source("adafruit_2230.step")[index]
        .translate((-41.4, -14.4, -45.25))
        .rotate((0, 0, 0), (0, 1, 0), -90)
        .scale(0.001)
    )


def _socket_head(a, position, axis=(0, 0, 1), radius=0.0025, name="socket_head"):
    head = cq.Workplane("XY").circle(radius).extrude(0.0015)
    socket = cq.Workplane("XY").polygon(6, radius * 1.05).extrude(0.001).translate((0, 0, 0.0006))
    a.add(_mesh(head.cut(socket).val()), STEEL, position, axis=axis, metal=0.83, rough=0.25, name=name)


def module(obj):
    a = Assembly(obj.object_id)
    body = _housing_shape(0)
    ports = [(x, z) for x in (-0.016, 0.016) for z in (-0.011, 0.011)]
    for x, z in ports:
        bore = cq.Solid.makeCylinder(0.0042, 0.012, cq.Vector(x, 0.008, z), cq.Vector(0, 1, 0))
        body = body.cut(bore)
    a.add(_mesh(body), (148, 156, 161), metal=0.84, rough=0.31, name="Adafruit_2230_extrusion")
    for index, side in [(1, 1), (2, -1)]:
        a.add(
            _mesh(_housing_shape(index)),
            (61, 70, 76),
            metal=0.62,
            rough=0.33,
            name=f"Adafruit_2230_end_cap_{side}",
        )
        for y in (-0.0109, 0.0109):
            for z in (-0.0379, 0.0379):
                _socket_head(a, (side * 0.04675, y, z), (side, 0, 0), 0.0018, "end_cap_fastener")
    for x, z in ports:
        ring = trimesh.creation.annulus(0.0023, 0.0042, 0.008, sections=64)
        a.add(
            ring,
            (43, 48, 53),
            (x, 0.0164, z),
            axis=(0, 1, 0),
            metal=0,
            rough=0.43,
            name="rear_terminal_insulator",
        )
        pin = cq.Workplane("XY").circle(0.0023).extrude(0.026).edges(">Z").fillet(0.0006)
        a.add(
            _mesh(pin.val()),
            (201, 183, 133),
            (x, 0.0104, z),
            axis=(0, 1, 0),
            metal=0.92,
            rough=0.24,
            name="rear_metal_terminal",
        )
    # An asymmetric keyed prism has actual thickness and an attached base.
    key = (
        cq.Workplane("XY")
        .polyline([(-0.004, -0.012), (0.004, -0.012), (0.004, 0.009), (0.001, 0.014), (-0.004, 0.014)])
        .close()
        .extrude(0.0246)
    )
    # Local CAD Y becomes world Z, and its extrusion becomes rear-facing +Y.
    key_mesh = _mesh(key.val())
    key_mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    a.add(key_mesh, (239, 190, 48), (0, 0.0144, 0), metal=0, rough=0.36, name="rear_yellow_locating_key")
    a.label("C  /  SIGNAL MODULE\n24 V  -  ISOLATED", (0, -0.0146, 0.019), 0.063, 0.021)
    a.label("KEYED  /  4 CONTACTS", (0, 0.0146, 0.0315), 0.061, 0.008, (0, 1, 0))
    return a


def _panel(a, spec):
    outer = (
        cq.Workplane("XY").box(0.39, 0.20, 0.018).edges("|Z").fillet(0.004).translate((-0.085, -0.04, 0.042))
    )
    inner = cq.Workplane("XY").box(0.386, 0.196, 0.019).translate((-0.085, -0.04, 0.0385))
    panel = outer.cut(inner)
    knobs = [obj for obj in spec.objects if obj.object_id in SCALES]
    for obj in knobs:
        x, y, _ = obj.pose.position_m
        pocket = cq.Solid.makeCylinder(0.0095, 0.018, cq.Vector(x, y, 0.0315))
        bore = cq.Solid.makeCylinder(0.00315, 0.023, cq.Vector(x, y, 0.031))
        panel = panel.cut(pocket).cut(bore)
    for x in (-0.265, 0.095):
        for y in (-0.125, 0.045):
            panel = panel.cut(cq.Solid.makeCylinder(0.0015, 0.020, cq.Vector(x, y, 0.032)))
    a.add(_mesh(panel.val()), (75, 87, 94), metal=0.62, rough=0.37, name="control_panel_drilled_shell")
    for x in (-0.265, 0.095):
        for y in (-0.125, 0.045):
            _socket_head(a, (x, y, PANEL_TOP), radius=0.0023, name="panel_fastener")
    for obj in knobs:
        x, y, z = obj.pose.position_m
        bottom = z + _cap_bottom(obj)
        bearing = trimesh.creation.annulus(0.0105, 0.0184, bottom - PANEL_TOP, sections=96)
        a.add(
            bearing,
            STEEL,
            (x, y, (PANEL_TOP + bottom) / 2),
            metal=0.8,
            rough=0.3,
            name=f"{obj.object_id}_stationary_bearing",
        )
        for index, part in enumerate(_cad_source("adafruit_562.step")):
            if index == 2:
                continue
            color = (117, 96, 68) if index == 0 else (44, 48, 52) if index == 1 else STEEL
            a.add(
                _mesh(part.scale(0.001)),
                color,
                (x, y, POT_ORIGIN_Z),
                metal=0 if index in (0, 1) else 0.78,
                rough=0.38,
                name=f"Adafruit_562_{obj.object_id}_stator_{index}",
            )
        radius = 0.033 if obj.object_id == "A" else 0.037
        for degrees in range(0, 360, 15):
            theta = np.radians(degrees)
            length = 0.0045 if degrees % 30 == 0 else 0.0022
            item = trimesh.creation.box((0.0008, length, 0.00015))
            item.apply_transform(trimesh.transformations.rotation_matrix(theta, [0, 0, 1]))
            a.add(
                item,
                (217, 226, 223),
                (x - radius * np.sin(theta), y + radius * np.cos(theta), PANEL_TOP + 0.000075),
                metal=0,
                rough=0.6,
                name=f"{obj.object_id}_stationary_scale_tick",
            )
        a.label(
            obj.object_id + ("  RANGE" if obj.object_id == "A" else "  ADJUST"),
            (x, 0.030, PANEL_TOP + 0.0001),
            0.071,
            0.013,
            (0, 0, 1),
            (75, 87, 94),
            (236, 238, 229),
        )
        a.label(
            "0",
            (x, y + radius + 0.008, PANEL_TOP + 0.0001),
            0.008,
            0.008,
            (0, 0, 1),
            (75, 87, 94),
            (236, 238, 229),
        )
        a.label(
            "30",
            (x - (radius + 0.008) * 0.5, y + (radius + 0.008) * np.sqrt(3) / 2, PANEL_TOP + 0.0001),
            0.011,
            0.007,
            (0, 0, 1),
            (75, 87, 94),
            (236, 238, 229),
        )
    a.label(
        "ROTARY CONTROL  /  POWER ISOLATED",
        (-0.085, -0.121, PANEL_TOP + 0.0001),
        0.26,
        0.010,
        (0, 0, 1),
        (75, 87, 94),
        (221, 228, 226),
    )


def _prop_on_surface(a, asset_id, maximum_size, xy, bottom, rz=0, rx=0):
    source = mature_asset(asset_id).copy()
    if rx:
        source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rx), [1, 0, 0]))
    source.apply_scale(min(np.asarray(maximum_size) / source.extents))
    if rz:
        source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    source.apply_translation(
        np.asarray([*xy, bottom]) - np.r_[source.bounds.mean(axis=0)[:2], source.bounds[0, 2]]
    )
    place_scene(a, source, None, source.bounds.mean(axis=0), label=asset_id)


def environment(spec):
    a = Assembly("control_panel_environment")
    table = mature_asset("WoodenTable_03").copy()
    table.apply_scale(0.7525 / table.extents[2])
    table.apply_translation(
        np.asarray([0, 0.12, -0.7375]) - np.r_[table.bounds.mean(axis=0)[:2], table.bounds[0, 2]]
    )
    place_scene(a, table, None, table.bounds.mean(axis=0), label="electrical_bench_table")
    a.add(
        trimesh.creation.box((1.25, 0.94, 0.015)),
        (161, 164, 157),
        (0, 0.12, 0.0225),
        metal=0,
        rough=0.6,
        name="laminated_bench_top",
    )
    textured_box(a, (2.6, 2.5, 0.035), (0, 0.12, -0.755), "concrete_floor_worn_001", name="visible_floor")
    a.add(
        trimesh.creation.box((1.01, 0.90, 0.003)),
        (54, 73, 75),
        (0, 0.12, 0.0315),
        metal=0,
        rough=0.76,
        name="clean_esd_work_mat",
    )
    _panel(a, spec)
    # C's real source bottom is at world z=.0436. Two short feet transfer load
    # through a mounting plate to the mat; the rear inspection approach is free.
    a.box(
        (0.12, 0.075, 0.004),
        (0.18, 0.17, MAT_TOP + 0.002),
        (56, 64, 70),
        metal=0.5,
        name="C_stationary_mount_plate",
    )
    for dx in (-0.026, 0.026):
        a.add(
            trimesh.creation.box((0.018, 0.023, 0.0066)),
            (64, 71, 76),
            (0.18 + dx, 0.17, 0.0403),
            metal=0.55,
            rough=0.38,
            name="C_contact_foot",
        )
    for dx in (-0.050, 0.050):
        for dy in (-0.026, 0.026):
            _socket_head(a, (0.18 + dx, 0.17 + dy, 0.037), radius=0.002, name="C_mount_fastener")
    _prop_on_surface(a, "retro_multimeter", (0.17, 0.24, 0.20), (-0.29, 0.29), MAT_TOP, rz=-12)
    _prop_on_surface(
        a, "flathead_screwdriver", (0.030, 0.20, 0.030), (0.39, -0.10), MAT_TOP, rz=18, rx=-94.4513246615
    )
    _prop_on_surface(a, "circuit_board", (0.14, 0.17, 0.03), (-0.04, 0.38), MAT_TOP, rz=8)
    a.label("ELECTRICAL TRAINING  /  ISOLATED SUPPLY", (0, -0.351, 0.015), 0.43, 0.018)
    return a


def build(spec):
    objects = {}
    for obj in spec.objects:
        if obj.object_id in SCALES:
            objects[obj.object_id] = knob(obj)
        elif obj.object_id == "C":
            objects[obj.object_id] = module(obj)
        else:
            raise ValueError(f"Unexpected control-panel task object: {obj.object_id}")
    objects["environment"] = environment(spec)
    return objects
