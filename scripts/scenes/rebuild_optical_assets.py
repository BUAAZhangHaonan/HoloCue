"""Optical bench built around Winters/Shepler's licensed optomechanical CAD.

The original millimetre-scale STEP solids retain their proportions. A small
blind shaft seat, insertion bushings and the task's vertical rotary bearing
adapt real parts to the existing anchors. The offline OptiCore breadboard is
loaded as a mesh; GPL generator code is not imported by the scene builder.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cadquery as cq
import numpy as np
from PIL import Image, ImageDraw
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, LIGHT, STEEL, cad_mesh
from scripts.scenes.asset_composition import (
    place_asset,
    place_scene,
    textured_box,
)

SOURCE_DIR = "assets/downloads/optical_reconstruction"
OPTICAL_CENTER_MM = 35.920934
FRAME_DEPTH_MM = 15.875
SHAFT_RADIUS = 0.007
BORE_RADIUS = 0.00775
BOARD_TOP = 0.055
PRINTED_POLYMER = (43, 48, 54)


def _glass_extensions(tree):
    """Keep optical transmission in the final GLB, including Blender import.

    Transmission uses the standard opaque surface alpha mode. Alpha blending
    would attenuate the same physical glass a second time.
    """
    for material in tree.get("materials", []):
        if material.get("name") == "BK7_biconvex_optical_glass":
            material["extensions"] = {
                "KHR_materials_transmission": {"transmissionFactor": 0.92},
                "KHR_materials_ior": {"ior": 1.5168},
            }
            used = tree.setdefault("extensionsUsed", [])
            for key in material["extensions"]:
                if key not in used:
                    used.append(key)


class OpticalAssembly(Assembly):
    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        exported = self.scene.copy()
        exported.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
        exported.export(
            str(path), file_type="glb", include_normals=True, tree_postprocessor=_glass_extensions
        )


@lru_cache(maxsize=12)
def _source_solid(name, index=0):
    """CAD units are mm; preserve source origin and each independent solid."""
    imported = cq.importers.importStep(str(root() / SOURCE_DIR / (name + ".step")))
    return imported.solids().vals()[index]


def _mesh(shape):
    vertices, faces = shape.scale(1000).tessellate(0.05, 0.12)
    return trimesh.Trimesh(
        vertices=np.asarray([v.toTuple() for v in vertices]) / 1000, faces=faces, process=True, validate=True
    )


def _part(a, name, position=(0, 0, 0), scale=1.0, index=0, rotation=None, label=None, color=PRINTED_POLYMER):
    shape = _source_solid(name, index).scale(0.001 * scale)
    mesh = _mesh(shape)
    if rotation is not None:
        mesh.apply_transform(rotation)
    return a.add(mesh, color, position, metal=0, rough=0.42, name=label or name)


def _frame_shape(name, index, optic_z, depth_offset=FRAME_DEPTH_MM / 2000):
    # Source XY is the optical face, +Z its depth. Local +Y is the rear.
    return (
        _source_solid(name, index)
        .scale(0.001)
        .rotate((0, 0, 0), (1, 0, 0), 90)
        .translate((0, depth_offset, optic_z - OPTICAL_CENTER_MM / 1000))
    )


def _frame(
    a, name="C02_fixed_lens", index=0, optic_z=0.0208, depth_offset=FRAME_DEPTH_MM / 2000, shaft_top=-0.022
):
    shape = _frame_shape(name, index, optic_z, depth_offset)
    # Only the finite post interface is modified; no AABB deformation.
    bore = (
        cq.Workplane("XY")
        .circle(SHAFT_RADIUS + 0.0001)
        .extrude(0.12 + shaft_top)
        .translate((0, 0, -0.12))
        .val()
    )
    a.add(_mesh(shape.cut(bore)), PRINTED_POLYMER, metal=0, rough=0.42, name="Winters_" + name)
    return shape


def _shaft(a, top=-0.022, bottom=-0.065):
    a.add(
        trimesh.creation.cylinder(SHAFT_RADIUS, top - bottom, sections=64),
        STEEL,
        (0, 0, (top + bottom) / 2),
        metal=0.82,
        rough=0.24,
        name="mounting_post",
    )


def _biconvex_lens(radius=0.01268, edge_thickness=0.0018, curvature_radius=0.045):
    """Two spherical caps with a finite cylindrical edge, not a scaled sphere."""
    radial = np.linspace(0, radius, 25)
    angles = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    sag_edge = curvature_radius - np.sqrt(curvature_radius**2 - radius**2)
    vertices, faces = [], []
    rings = len(radial) - 1
    per_side = 1 + rings * len(angles)
    for side in (-1, 1):
        vertices.append([0, side * (edge_thickness / 2 + sag_edge), 0])
        for r in radial[1:]:
            sag = curvature_radius - np.sqrt(curvature_radius**2 - r**2)
            y = side * (edge_thickness / 2 + sag_edge - sag)
            vertices.extend([[r * np.cos(t), y, r * np.sin(t)] for t in angles])
    n = len(angles)
    for s in range(2):
        offset = s * per_side
        for j in range(n):
            faces.append([offset, offset + 1 + j, offset + 1 + (j + 1) % n])
        for ring in range(rings - 1):
            first = offset + 1 + ring * n
            second = first + n
            for j in range(n):
                k = (j + 1) % n
                faces.extend([[first + j, second + j, second + k], [first + j, second + k, first + k]])
    for j in range(n):
        k = (j + 1) % n
        a = 1 + (rings - 1) * n
        b = a + per_side
        faces.extend([[a + j, b + j, b + k], [a + j, b + k, a + k]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    mesh.fix_normals()
    mesh.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(
            name="BK7_biconvex_optical_glass",
            baseColorFactor=[235, 248, 255, 255],
            metallicFactor=0,
            roughnessFactor=0.055,
            alphaMode="OPAQUE",
            doubleSided=False,
        )
    )
    return mesh


def lens(obj):
    a = OpticalAssembly(obj.object_id)
    _frame(a)
    _shaft(a)
    glass = _biconvex_lens()
    glass.apply_translation((0, 0.0015, 0.0208))
    a.scene.add_geometry(glass, node_name=f"{a.name}/biconvex_glass", geom_name=f"{a.name}_biconvex_glass")
    a.label(
        obj.object_id + "  25.4 mm",
        (0, 0.00805, -0.008),
        0.025,
        0.006,
        (0, 1, 0),
        background=(54, 58, 62),
        ink=(228, 230, 225),
    )
    # Small metal clamp screws occupy the CAD's existing side screw bores.
    for sign in (-1, 1):
        a.cylinder(0.00145, 0.007, (sign * 0.041, 0.002045, 0.020742), STEEL, (1, 0, 0), "cage_lock_screw")
    return a


def _receiver(a, x=0, y=0, z_offset=0):
    """Source base + a replaceable precision bushing with the declared blind seat."""
    base_z = 0.060 + z_offset
    _part(a, "B01_base", (x, y, base_z), scale=1.5, label="Winters_B01_post_holder")
    a.box((0.072, 0.064, 0.005), (x, y, 0.0575 + z_offset), (64, 68, 73), name="hold_down_adapter")
    for dx in (-0.027, 0.027):
        a.cylinder(0.003, 0.003, (x + dx, y, 0.0615 + z_offset), STEEL, name="hold_down_screw")
    lock_z = base_z + 0.044447556788418694 * 1.5
    body = (
        cq.Workplane("XY")
        .circle(0.0115)
        .circle(BORE_RADIUS)
        .extrude(0.037)
        .translate((x, y, 0.103 + z_offset))
    )
    cross = cq.Workplane("YZ").circle(0.0026).extrude(0.03).translate((x - 0.03, y, lock_z))
    a.add(cad_mesh(body.cut(cross)), STEEL, metal=0.7, rough=0.28, name="sleeve_body")
    a.add(
        trimesh.creation.cylinder(0.0115, 0.005, sections=64),
        STEEL,
        (x, y, 0.1005 + z_offset),
        metal=0.7,
        rough=0.3,
        name="insertion_seat",
    )
    rot = trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0])
    _part(
        a,
        "M02_thumb_knob",
        (x - 0.030, y, lock_z),
        scale=0.45,
        rotation=rot,
        label="Winters_M02_locking_knob",
    )
    a.rod((x - 0.029, y, lock_z), (x - 0.0078, y, lock_z), 0.0025, STEEL, "locking_screw")


def post(obj):
    a = Assembly(obj.object_id)
    _receiver(a, z_offset=-obj.pose.position_m[2])
    a.label("POST 2", (0, -0.0326, -0.025), 0.038, 0.008, background=(64, 68, 73), ink=(230, 232, 229))
    return a


def _serial_label(a):
    index = a.index
    a.label(
        "M  /  HR-25\nSERIAL 1064-003", (0, 0.034, 0.015), 0.035, 0.013, (0, 1, 0), background=(220, 224, 222)
    )
    geometry = f"label_{index}"
    mesh = a.scene.geometry[geometry].copy()
    a.scene.delete_geometry(geometry)
    a.scene.add_geometry(
        mesh, node_name=f"{a.name}/rear_serial_label", geom_name=f"{a.name}_rear_serial_label"
    )


def mirror(obj):
    a = Assembly(obj.object_id)
    # C13 and C14 downloads contain the same two-solid export. Use the base
    # solid once; the separate cover is moved from its print layout to the joint.
    _frame(a, "C13_mirror_base", index=1, optic_z=0.015, depth_offset=0.016, shaft_top=-0.024)
    carrier = _frame_shape("C15_mirror_mount", 0, 0.015, 0.016)
    a.add(_mesh(carrier), (55, 60, 65), rough=0.42, name="Winters_C15_mirror_carrier")
    cover = _source_solid("C13_mirror_base", 0).translate((19.7358, -19.7358, 0)).scale(0.001)
    cover = cover.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 0.016, 0.015 - OPTICAL_CENTER_MM / 1000))
    a.add(_mesh(cover), PRINTED_POLYMER, rough=0.42, name="Winters_C14_joint_cap")
    # A coated 25.4 mm optic is seated inside the original C15 circular pocket.
    a.add(
        trimesh.creation.cylinder(0.0127, 0.0036, sections=96),
        (208, 220, 225),
        (0, 0.010, 0.015),
        axis=(0, 1, 0),
        metal=0.98,
        rough=0.045,
        name="coated_mirror_optic",
    )
    for x, z in [(-0.0099568, -0.0047358), (0.0197358, 0.0249568)]:
        a.cylinder(0.0018, 0.018, (x, 0.014, z), STEEL, (0, 1, 0), "kinematic_adjuster_screw")
        rot = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        _part(a, "M02_thumb_knob", (x, 0.026, z), scale=0.34, rotation=rot, label="Winters_M02_adjuster_knob")
    # The contract's rotation is yaw around the bearing at local z=-.065.
    a.add(
        trimesh.creation.cylinder(0.026, 0.008, sections=96),
        (58, 64, 70),
        (0, 0, -0.061),
        metal=0.7,
        rough=0.3,
        name="vertical_rotation_base",
    )
    _shaft(a, top=-0.024, bottom=-0.057)
    a.ring(0.022, 0.026, 0.001, (0, 0, -0.0565), STEEL, name="rotation_degree_bezel")
    for angle in range(0, 360, 15):
        t = np.radians(angle)
        a.rod(
            (0.023 * np.cos(t), 0.023 * np.sin(t), -0.0559),
            (0.0255 * np.cos(t), 0.0255 * np.sin(t), -0.0559),
            0.0003,
            LIGHT,
            "yaw_degree_tick",
        )
    # A real rear serial tag on short standoffs, below the fixed cue plane.
    a.box((0.040, 0.001, 0.018), (0, 0.0334, 0.015), (71, 78, 84), name="rear_serial_carrier")
    for x in (-0.019, 0.019):
        a.rod((x, 0.014, 0.015), (x, 0.0329, 0.015), 0.0018, STEEL, "serial_tag_standoff")
    _serial_label(a)
    return a


def target(obj):
    a = Assembly(obj.object_id)
    shape = _frame_shape("C02_fixed_lens", 0, 0, 0.0145)
    a.add(_mesh(shape), PRINTED_POLYMER, rough=0.42, name="Winters_target_mount")
    a.box((0.17, 0.003, 0.18), (0, -0.003, 0), (216, 222, 221), name="target_screen_card")
    a.box((0.040, 0.001, 0.020), (0, -0.001, 0), (60, 67, 72), name="target_card_mounting_pad")
    image = Image.new("RGB", (768, 768), (226, 230, 227))
    draw = ImageDraw.Draw(image)
    for i in range(64, 769, 64):
        draw.line((i, 0, i, 768), fill=(188, 198, 196), width=1)
        draw.line((0, i, 768, i), fill=(188, 198, 196), width=1)
    for radius in (80, 160, 240, 320):
        draw.ellipse((384 - radius, 384 - radius, 384 + radius, 384 + radius), outline=(35, 48, 53), width=3)
    draw.line((0, 384, 768, 384), fill=(35, 48, 53), width=3)
    draw.line((384, 0, 384, 768), fill=(35, 48, 53), width=3)
    verts = [
        [-0.08, -0.0046, -0.085],
        [0.08, -0.0046, -0.085],
        [0.08, -0.0046, 0.085],
        [-0.08, -0.0046, 0.085],
    ]
    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=[[0, 0], [1, 0], [1, 1], [0, 1]],
            material=trimesh.visual.material.PBRMaterial(
                name="printed_passive_alignment_target",
                baseColorTexture=image,
                metallicFactor=0,
                roughnessFactor=0.8,
            ),
        ),
    )
    a.scene.add_geometry(mesh, node_name="TARGET/printed_passive_target", geom_name="printed_passive_target")
    return a


@lru_cache(maxsize=1)
def _breadboard():
    scene = trimesh.load_scene(root() / SOURCE_DIR / "opticore_breadboard.glb", process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    # A clean satin metal finish matches an optical breadboard. Do not reuse
    # patterned or weathered floor-plate maps on precision optomechanics.
    material = trimesh.visual.material.PBRMaterial(
        name="OptiCore_breadboard_satin_aluminum",
        baseColorFactor=[176, 182, 188, 255],
        metallicFactor=0.9,
        roughnessFactor=0.34,
    )
    baked = trimesh.Scene()
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        mesh = scene.geometry[geometry].copy()
        mesh.apply_transform(transform)
        mesh.visual = trimesh.visual.TextureVisuals(uv=mesh.vertices[:, :2] / 0.45, material=material)
        baked.add_geometry(mesh, node_name=node, geom_name=node)
    return baked


def environment(spec):
    a = Assembly("optical_bench_environment")
    # Reuse a mature table, with its broad tabletop at the optical board bottom.
    place_asset(a, "WoodenTable_03", (1.05, 1.50, 0.7675), (0, 0.37, -0.35375), label="lab_support_table")
    textured_box(a, (2.5, 2.7, 0.035), (0, 0.37, -0.755), "concrete_floor_worn_001", name="visible_floor")
    board = _breadboard().copy()
    board.apply_translation((0, 0.36, BOARD_TOP))
    place_scene(a, board, None, board.bounds.mean(axis=0), label="OptiCore_true_hole_breadboard")
    # L1 rests in a storage sleeve whose floor is the original shaft bottom.
    a.box((0.09, 0.07, 0.010), (0.22, -0.12, 0.060), (49, 57, 63), name="L1_storage_pad")
    a.ring(
        0.0075, 0.012, 0.016, (0.22, -0.12, 0.073), PRINTED_POLYMER, name="L1_storage_sleeve"
    ).visual.material.metallicFactor = 0
    _receiver(a, 0, 0.34)
    # M's bearing is below its pivot; no fixed housing obstructs the yaw sweep.
    _part(a, "B01_base", (0, 0.61, BOARD_TOP), scale=0.85, label="Winters_M_stationary_base")
    top = BOARD_TOP + 0.05207 * 0.85
    a.add(
        trimesh.creation.cylinder(0.026, 0.103 - top, sections=96),
        STEEL,
        (0, 0.61, (top + 0.103) / 2),
        metal=0.7,
        rough=0.3,
        name="M_stationary_bearing",
    )
    a.label("YAW", (0, 0.582, 0.091), 0.026, 0.007)
    # Passive alignment screen support reaches its true lower card edge.
    a.box((0.11, 0.085, 0.010), (-0.31, 0.88, 0.060), PRINTED_POLYMER, name="TARGET_foot")
    a.cylinder(0.010, 0.015, (-0.31, 0.88, 0.0725), STEEL, name="TARGET_screen_support")
    # Real spare CAD parts and an existing CC0 screwdriver remain on the table.
    a.box((0.145, 0.15, 0.006), (0.32, 0.54, 0.058), (66, 74, 80), name="optomechanical_parts_tray")
    _part(a, "C04_adjustable_lens", (0.32, 0.51, 0.061), label="Winters_spare_adjustable_mount")
    _part(a, "P01_adjustable_post", (0.37, 0.59, 0.061), label="Winters_spare_adjustable_post")
    place_asset(
        a,
        "flathead_screwdriver",
        (0.022, 0.18, 0.015),
        (-0.36, 0.12, 0.0625),
        rz=12,
        label="maintenance_screwdriver",
    )
    a.label("OPTICAL BENCH  /  25 mm GRID", (0, -0.335, 0.026), 0.40, 0.018)
    return a


def build(spec):
    objects = {}
    for obj in spec.objects:
        if obj.object_id in ("L1", "L2"):
            objects[obj.object_id] = lens(obj)
        elif obj.object_id == "POST2":
            objects[obj.object_id] = post(obj)
        elif obj.object_id == "M":
            objects[obj.object_id] = mirror(obj)
        elif obj.object_id == "TARGET":
            objects[obj.object_id] = target(obj)
        else:
            raise ValueError(f"Unexpected optical task object: {obj.object_id}")
    objects["environment"] = environment(spec)
    return objects
