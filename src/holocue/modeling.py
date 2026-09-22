"""Dimensioned, reusable CAD parts for the twelve teaching workstations.

Meshes are authored Z-up in metres and exported as standard Y-up glTF.
Labels are rasterized into embedded textures; font files are never exported.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from .models import SceneObject, SceneSpec
from .spatial import rotation

STEEL = (148, 163, 174)
DARK = (45, 59, 73)
RUBBER = (38, 44, 48)
LIGHT = (207, 215, 221)
BRASS = (178, 150, 82)
ORANGE = (219, 132, 47)
CAD_TESSELLATION_M = 0.0006


def cad_mesh(shape: cq.Workplane) -> trimesh.Trimesh:
    vertices, faces = shape.val().tessellate(CAD_TESSELLATION_M, 0.16)
    # CAD fillet poles can emit zero-area triangles with repeated vertices.
    # Remove those during validation so closed solids retain closed topology.
    return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces, process=True, validate=True)


@lru_cache(maxsize=512)
def rounded_box(size: tuple[float, float, float]) -> trimesh.Trimesh:
    if min(size) <= 0:
        raise ValueError("box dimensions must be positive")
    radius = min(min(size) * 0.16, 0.006)
    return cad_mesh(cq.Workplane("XY").box(*size).edges().fillet(radius))


class Assembly:
    def __init__(self, name: str) -> None:
        self.name = name
        self.scene = trimesh.Scene()
        self.index = 0

    def add(self, mesh, color=LIGHT, position=(0, 0, 0), axis=None, metal=0.0, rough=0.44, name="part"):
        item = mesh.copy()
        if axis is not None:
            item.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], axis))
        item.apply_translation(position)
        # Split hard edges while preserving the authored triangles. Set PBR
        # after smoothing because trimesh submesh does not retain no-UV visuals.
        item = trimesh.graph.smooth_shade(item, angle=np.radians(20.0), facet_minarea=None)
        material = trimesh.visual.material.PBRMaterial(
            name=f"{name}_material",
            baseColorFactor=[*color, 255],
            metallicFactor=metal,
            roughnessFactor=rough,
            doubleSided=False,
        )
        item.visual = trimesh.visual.TextureVisuals(material=material)
        self.scene.add_geometry(
            item, node_name=f"{self.name}/{self.index:04d}_{name}", geom_name=f"{self.name}_{self.index:04d}"
        )
        self.index += 1
        return item

    def box(self, size, position=(0, 0, 0), color=LIGHT, metal=0.0, name="panel"):
        return self.add(rounded_box(tuple(size)), color, position, metal=metal, name=name)

    def cylinder(self, radius, height, position=(0, 0, 0), color=STEEL, axis=(0, 0, 1), name="cylinder"):
        return self.add(
            trimesh.creation.cylinder(radius, height, sections=40),
            color,
            position,
            axis=axis,
            metal=0.65 if color == STEEL else 0.1,
            name=name,
        )

    def ring(self, inner, outer, height, position=(0, 0, 0), color=STEEL, axis=(0, 0, 1), name="ring"):
        return self.add(
            trimesh.creation.annulus(inner, outer, height, sections=48),
            color,
            position,
            axis=axis,
            metal=0.6,
            name=name,
        )

    def rod(self, a, b, radius, color=STEEL, name="tube"):
        return self.add(
            trimesh.creation.cylinder(radius=radius, segment=np.asarray([a, b]), sections=20),
            color,
            metal=0.45,
            name=name,
        )

    def sphere(self, radii, position, color=LIGHT, name="rounded_part"):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        mesh.apply_scale(radii)
        return self.add(mesh, color, position, name=name)

    def screws(self, x, y, z, axis=(0, 0, 1)):
        for xx in (-x, x):
            for yy in (-y, y):
                self.cylinder(0.0035, 0.002, (xx, yy, z), STEEL, axis, "fastener")

    def label(self, text, center, width, height, normal=(0, -1, 0), background=(226, 232, 230), ink=DARK):
        pixel_height = max(64, min(512, round(512 * height / width)))
        image = Image.new("RGB", (512, pixel_height), background)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 506, pixel_height - 6), radius=8, outline=ink, width=3)
        lines = text.split("\n")
        row_height = (pixel_height - 18) / len(lines)
        for i, line in enumerate(lines):
            font_size = max(8, int(row_height * 0.64))
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            while font.getlength(line) > 472 and font_size > 8:
                font_size -= 1
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            draw.text((256, 9 + (i + 0.5) * row_height), line, font=font, fill=ink, anchor="mm")
        up = np.array([0.0, 0.0, 1.0])
        n = np.asarray(normal, float)
        if abs(n @ up) > 0.95:
            up = np.array([0.0, 1.0, 0.0])
        right = np.cross(up, n)
        right /= np.linalg.norm(right)
        up = np.cross(n, right)
        vertices = np.asarray([(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)])
        world = np.asarray(center) + vertices[:, 0, None] * width * right + vertices[:, 1, None] * height * up
        material = trimesh.visual.material.PBRMaterial(
            baseColorTexture=image, roughnessFactor=0.75, metallicFactor=0
        )
        visual = trimesh.visual.TextureVisuals(
            uv=np.asarray([[0, 0], [1, 0], [1, 1], [0, 1]]), material=material
        )
        mesh = trimesh.Trimesh(vertices=world, faces=[[0, 1, 2], [0, 2, 3]], visual=visual, process=False)
        self.scene.add_geometry(
            mesh, node_name=f"{self.name}/label_{self.index}", geom_name=f"label_{self.index}"
        )
        self.index += 1

    def transform(self, transform):
        self.scene.apply_transform(transform)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        exported = self.scene.copy()
        exported.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
        exported.export(str(path), file_type="glb", include_normals=True)


def partition_cad_parts(shapes):
    """Partition a CSG union into material regions with disjoint interiors."""
    occupied = None
    for shape in shapes:
        region = shape if occupied is None else shape.cut(occupied)
        if not region.val().isValid() or region.val().Volume() <= 0:
            raise ValueError("CAD material partition must contain a valid positive-volume region")
        yield region
        occupied = shape if occupied is None else occupied.union(shape)


def box_frame(a: Assembly, size, thickness, color=LIGHT):
    x, y, z = size
    t = thickness
    panels = [
        ((x, y, t), (0, 0, -z / 2 + t / 2)),
        ((t, y, z), (-x / 2 + t / 2, 0, 0)),
        ((t, y, z), (x / 2 - t / 2, 0, 0)),
        ((x - 2 * t, t, z), (0, -y / 2 + t / 2, 0)),
        ((x - 2 * t, t, z), (0, y / 2 - t / 2, 0)),
    ]
    shapes = [
        cq.Workplane("XY").box(*extent).edges().fillet(min(min(extent) * 0.16, 0.006)).translate(position)
        for extent, position in panels
    ]
    for region in partition_cad_parts(shapes):
        a.add(cad_mesh(region), color, name="panel")


def hollow_front(a, size, wall, color, top_inlay: cq.Workplane | None = None):
    x, y, z = size
    t = wall
    a.box((t, y, z), (-x / 2 + t / 2, 0, 0), color)
    a.box((t, y, z), (x / 2 - t / 2, 0, 0), color)
    a.box((x - 2 * t, y, t), (0, 0, -z / 2 + t / 2), color)
    if top_inlay is None:
        a.box((x - 2 * t, y, t), (0, 0, z / 2 - t / 2), color)
    else:
        roof = cq.Workplane("XY").box(x - 2 * t, y, t).edges().fillet(min(min(x - 2 * t, y, t) * 0.16, 0.006))
        roof = roof.translate((0, 0, z / 2 - t / 2))
        a.add(cad_mesh(roof.cut(top_inlay)), color, name="panel")
    a.box((x - 2 * t, t, z - 2 * t), (0, y / 2 - t / 2, 0), DARK)


def make_object(obj: SceneObject) -> Assembly:
    a = Assembly(obj.object_id)
    x, y, z = obj.size_m
    c = obj.color
    k = obj.recipe
    if k == "knob":
        a.cylinder(min(x, y) * 0.44, z * 0.70, (0, 0, 0.05 * z), c, name="grip")
        a.cylinder(min(x, y) * 0.47, z * 0.12, (0, 0, -0.38 * z), DARK, name="flange")
        for theta in np.linspace(0, 2 * np.pi, 28, endpoint=False):
            a.cylinder(
                min(x, y) * 0.018,
                z * 0.62,
                (min(x, y) * 0.437 * np.cos(theta), min(x, y) * 0.437 * np.sin(theta), z * 0.05),
                DARK,
                name="knurl",
            )
        a.box((x * 0.065, y * 0.29, z * 0.025), (0, y * 0.23, z * 0.412), LIGHT, name="index_mark")
        if obj.object_id == "OILCAP":
            # Join the cap's original flange and grip without moving either.
            a.cylinder(min(x, y) / 3, z * 0.02, (0, 0, -z * 0.31), c, name="cap_grip_collar")
        elif obj.object_id in ("A", "B", "GUARD"):
            a.cylinder(min(x, y) / 3, z * 0.02, (0, 0, -z * 0.31), c, name="mount_neck")
        a.transform(trimesh.geometry.align_vectors([0, 0, 1], obj.interaction.rotation_axis_local))
    elif k == "module":
        a.box((x, y, z), (0, 0, 0), c, name="housing")
        a.box((x * 0.70, 0.003, z * 0.56), (0, -y / 2 - 0.001, 0), DARK, name="front_panel")
        a.label(obj.object_id, (0, -y / 2 - 0.003, 0), x * 0.58, z * 0.36)
        a.box((x * 0.25, 0.010, z * 0.25), (0, y / 2 + 0.003, z * 0.20), ORANGE, name="polarizing_key")
        for xx in np.linspace(-x * 0.30, x * 0.30, 4):
            a.cylinder(0.004, 0.008, (xx, y / 2 + 0.003, -z * 0.17), BRASS, (0, 1, 0), "terminal")
        a.label("REAR\nKEY + CONTACTS", (0, y / 2 + 0.001, -z * 0.34), x * 0.8, z * 0.18, (0, 1, 0))
        a.screws(x * 0.4, y * 0.39, z / 2 + 0.001)
    elif k == "plug":
        a.box((x, y * 0.68, z), (0, -y * 0.15, 0), c, name="grip")
        for yy in np.linspace(-y * 0.4, y * 0.10, 6):
            a.box((x * 1.02, 0.003, z * 0.80), (0, yy, 0), DARK, name="grip_rib")
        a.box((x * 0.72, y * 0.22, z * 0.70), (0, y * 0.29, 0), DARK, name="keyed_nose")
        a.box((x * 0.18, y * 0.25, 0.004), (0, y * 0.28, z * 0.39), ORANGE, name="top_key")
        for xx in (-x * 0.22, x * 0.22):
            for zz in (-z * 0.17, z * 0.17):
                a.cylinder(0.003, 0.018, (xx, y * 0.418, zz), BRASS, (0, 1, 0), "contact_pin")
        a.label("P\nALIGN KEY", (0, -y * 0.491, 0), x * 0.70, z * 0.65)
    elif k == "socket":
        # Cut the actual rounded marker volume out of its supporting roof.
        inlay = cq.Workplane("XY").box(0.012, y, 0.003).edges().fillet(0.003 * 0.16)
        inlay = inlay.translate((0, 0, z * 0.47))
        hollow_front(a, (x, y, z), 0.005, c, top_inlay=inlay)
        for xx in (-0.072 * 0.22, 0.072 * 0.22):
            for zz in (-0.042 * 0.17, 0.042 * 0.17):
                a.ring(0.0034, 0.0054, 0.018, (xx, -0.002, zz), BRASS, (0, 1, 0), "contact_socket")
        a.add(cad_mesh(inlay), ORANGE, name="key_channel_mark")
        a.label("S\nRECEIVER", (0, y / 2 + 0.001, 0), x * 0.8, z * 0.55, (0, 1, 0))
    elif k == "brick":
        thickness = 0.0016
        # A single molded shell avoids coplanar faces where five panels met.
        # Preserve the former panels' outer radius and the real open underside.
        outside = cq.Workplane("XY").box(x, y, z).edges().fillet(thickness * 0.16)
        cavity = cq.Workplane("XY").box(x - 2 * thickness, y - 2 * thickness, z).translate((0, 0, -thickness))
        a.add(cad_mesh(outside.cut(cavity)), c, name="open_bottom_shell")
        for xx in (-0.024, -0.008, 0.008, 0.024):
            for yy in (-0.008, 0.008):
                a.cylinder(0.0048, 0.0036, (xx, yy, z / 2 + 0.0018), c, name="stud")
        for xx in (-0.016, 0, 0.016):
            a.ring(0.0047, 0.0064, z - thickness, (xx, 0, -thickness / 2), c, name="underside_tube")
    elif k == "baseplate":
        a.box((x, y, z), (0, 0, 0), c)
        for xx in np.arange(-x / 2 + 0.008, x / 2, 0.016):
            for yy in np.arange(-y / 2 + 0.008, y / 2, 0.016):
                a.cylinder(0.0048, 0.0036, (xx, yy, z / 2 + 0.0018), c, name="stud")
    elif k == "server":
        a.box((x, y, z), (0, 0, 0), c, metal=0.65, name="chassis")
        for xx in np.linspace(-x * 0.38, x * 0.2, 20):
            a.box((0.005, 0.0015, z * 0.57), (xx, -y / 2 - 0.0008, 0), DARK, name="vent_slot")
        for xx in (-x * 0.46, x * 0.46):
            a.rod((xx, -y * 0.50, -z * 0.25), (xx, -y * 0.56, -z * 0.25), 0.004)
            a.rod((xx, -y * 0.56, -z * 0.25), (xx, -y * 0.56, z * 0.25), 0.004)
            a.rod((xx, -y * 0.56, z * 0.25), (xx, -y * 0.50, z * 0.25), 0.004)
        if obj.object_id == "NODE3":
            # Preserve the inspected fiber sockets in the current +Y rear frame.
            # The short cable tails stay above the chassis underside/support plane.
            for index, xx in enumerate(np.linspace(-x * 0.25, x * 0.25, 4)):
                center = (xx, y / 2 + 0.006, z * 0.12)
                a.ring(z * 0.115, z * 0.18, 0.011, center, DARK, (0, 1, 0), "fiber_socket")
                collar_color = (40, 175, 166) if index == 1 else STEEL
                a.ring(
                    z * 0.12,
                    z * 0.235,
                    0.004,
                    (xx, y / 2 + 0.013, z * 0.12),
                    collar_color,
                    (0, 1, 0),
                    "fiber_live_collar" if index == 1 else "fiber_collar",
                )
                if index != 1:
                    cable_color = [(45, 126, 153), RUBBER, (52, 144, 143), RUBBER][index]
                    a.cylinder(
                        z * 0.095, 0.009, (xx, y / 2 + 0.016, z * 0.12), cable_color, (0, 1, 0), "fiber_plug"
                    )
                    a.rod(
                        (xx, y / 2 + 0.020, z * 0.12),
                        (xx, y / 2 + 0.030, -z * 0.13),
                        z * 0.075,
                        cable_color,
                        "fiber_cable_tail",
                    )
                    a.rod(
                        (xx, y / 2 + 0.030, -z * 0.13),
                        (xx, y / 2 + 0.034, -z * 0.34),
                        z * 0.075,
                        cable_color,
                        "fiber_cable_tail",
                    )
            a.box((x * 0.38, 0.007, z * 0.12), (0, y / 2 + 0.004, -z * 0.33), DARK, name="rear_pull_handle")
        else:
            for xx in np.linspace(-x * 0.35, x * 0.25, 6):
                a.box((0.031, 0.008, 0.014), (xx, y / 2 + 0.003, 0), DARK, name="port")
                a.box((0.020, 0.001, 0.009), (xx, y / 2 + 0.0076, 0), BRASS, name="port_contact")
        a.label(obj.object_id, (x * 0.33, -y / 2 - 0.002, 0), x * 0.22, z * 0.75)
        a.label("PORTS", (x * 0.39, y / 2 + 0.009, 0), x * 0.18, z * 0.60, (0, 1, 0))
        a.screws(x * 0.45, y * 0.44, z / 2 + 0.001)
    elif k == "rack_slot":
        for xx in (-x / 2 + 0.006, x / 2 - 0.006):
            a.box((0.012, y, z), (xx, 0, 0), c, metal=0.7, name="rail")
            a.box((0.026, y, 0.005), (xx - np.sign(xx) * 0.007, 0, -z / 2 + 0.004), STEEL, name="support_lip")
        a.box((x, 0.012, z), (0, y / 2 - 0.006, 0), DARK, name="back_stop")
    elif k == "beacon":
        a.cylinder(x * 0.48, z * 0.18, (0, 0, -z * 0.40), DARK)
        for i, color in enumerate([(56, 152, 111), (229, 173, 43), (201, 72, 58)]):
            a.cylinder(x * 0.43, z * 0.24, (0, 0, z * (-0.2 + i * 0.25)), color, name="status_lens")
            a.ring(x * 0.41, x * 0.47, 0.004, (0, 0, z * (-0.32 + i * 0.25)), DARK)
    elif k in ("tray", "crate"):
        box_frame(a, (x, y, z), min(x, y, z) * 0.075, c)
        if k == "crate":
            for xx in np.linspace(-x * 0.42, x * 0.42, 9):
                a.box((0.004, 0.004, z * 0.7), (xx, y / 2 + 0.002, 0), LIGHT, name="reinforcing_rib")
            a.label("BLUE\nSHIPMENT 027", (0, y / 2 + 0.005, 0), x * 0.73, z * 0.55, (0, 1, 0))
    elif k == "battery":
        a.box((x, y, z), (0, 0, 0), c, name="battery_shell")
        for xx in (-x * 0.36, x * 0.36):
            a.box((0.008, y * 0.85, 0.004), (xx, 0, -z / 2), DARK, name="guide_rail")
        for xx in np.linspace(-x * 0.28, x * 0.28, 4):
            a.box((0.009, 0.015, 0.001), (xx, y * 0.30, -z / 2 - 0.0007), BRASS, name="contact")
        a.label("BAT\nTRAINING", (0, 0, z / 2 + 0.001), x * 0.85, y * 0.40, (0, 0, 1))
    elif k == "motor":
        a.cylinder(x * 0.42, z * 0.67, (0, 0, 0), DARK, name="stator")
        a.cylinder(x * 0.48, z * 0.12, (0, 0, -z * 0.40), STEEL, name="mount")
        a.cylinder(x * 0.39, z * 0.16, (0, 0, z * 0.33), c, name="rotor")
        a.cylinder(0.006, 0.010, (0, 0, z * 0.49), STEEL, name="shaft")
        for theta in np.linspace(0, 2 * np.pi, 20, endpoint=False):
            a.cylinder(
                0.0015,
                z * 0.56,
                (x * 0.415 * np.cos(theta), x * 0.415 * np.sin(theta), 0),
                BRASS,
                name="stator_detail",
            )
        if obj.object_id == "M3":
            # Local +X is the declared inspection face, without the old pose flip.
            point = np.asarray(obj.interaction.inspect_point_local_m)
            a.cylinder(z * 0.22, x * 0.10, tuple(point - [x * 0.09, 0, 0]), DARK, (1, 0, 0), "isolator_seat")
            a.add(
                trimesh.creation.annulus(z * 0.095, z * 0.245, x * 0.055, sections=64),
                ORANGE,
                tuple(point - [x * 0.0275, 0, 0]),
                axis=(1, 0, 0),
                metal=0.0,
                rough=0.88,
                name="isolator_ring",
            )
            a.cylinder(
                z * 0.063, x * 0.02, tuple(point - [x * 0.05, 0, 0]), STEEL, (1, 0, 0), "isolator_bolt"
            )
    elif k == "instrument":
        a.box((x, y, z), (0, 0, 0), c, name="instrument_case")
        a.box((x * 0.84, 0.002, z * 0.78), (0, -y / 2 - 0.001, 0), DARK, name="bezel")
        a.label(
            obj.object_id + "\nTRAINING READY",
            (0, -y / 2 - 0.0025, z * 0.08),
            x * 0.70,
            z * 0.46,
            background=(35, 58, 66),
            ink=(134, 223, 196),
        )
        for xx in np.linspace(-x * 0.25, x * 0.25, 4):
            a.cylinder(z * 0.04, 0.005, (xx, -y / 2 - 0.004, -z * 0.28), LIGHT, (0, -1, 0), "button")
        for xx in np.linspace(-x * 0.35, x * 0.35, 12):
            a.box((0.003, 0.002, z * 0.52), (xx, y / 2 + 0.001, 0), DARK, name="rear_vent")
    elif k == "parcel":
        a.box((x, y, z), (0, 0, 0), c, name="carton")
        a.box((x * 0.15, y + 0.001, 0.001), (0, 0, z / 2 + 0.0006), (190, 163, 115), name="tape")
        a.box((x * 0.15, 0.001, z), (0, -y / 2 - 0.0006, 0), (190, 163, 115), name="tape")
        a.label(obj.object_id + "\nBATCH 027", (0, y / 2 + 0.001, 0), x * 0.70, z * 0.50, (0, 1, 0))
    elif k in ("lens", "mirror"):
        center = (0, 0, z * 0.16)
        lens_seat = k == "lens" and obj.object_id in ("L1", "L2")
        if lens_seat:
            # Preserve the original 48-sided ring surfaces around a real blind
            # seat. Its bottom face receives the post below the optical opening.
            plane = cq.Plane(origin=(0, -y * 0.27, z * 0.16), xDir=(1, 0, 0), normal=(0, 1, 0))
            ring = cq.Workplane(plane).polygon(48, x * 0.96).polygon(48, x * 0.68).extrude(y * 0.54)
            seat = (
                cq.Workplane("XY").workplane(offset=-z * 0.5 - 0.005).circle(0.0071).extrude(z * 0.5 - 0.015)
            )
            a.add(cad_mesh(ring.cut(seat)), DARK, metal=0.6, name="optic_retainer")
        else:
            a.ring(x * 0.34, x * 0.48, y * 0.54, center, DARK, (0, 1, 0), "optic_retainer")
        if k == "lens":
            a.sphere((x * 0.35, y * 0.15, x * 0.35), center, (145, 192, 202), "convex_lens")
        else:
            a.add(
                trimesh.creation.cylinder(x * 0.35, 0.004, sections=64),
                (192, 209, 218),
                (0, -y * 0.20, z * 0.16),
                axis=(0, 1, 0),
                metal=0.95,
                rough=0.08,
                name="mirror_face",
            )
        if lens_seat:
            a.cylinder(0.007, z * 0.5 - 0.020, (0, 0, (-z * 0.5 - 0.020) / 2), STEEL, name="mounting_post")
        else:
            a.cylinder(0.007, z * 0.5, (0, 0, -z * 0.25), STEEL, name="mounting_post")
        for xx in (-x * 0.37, x * 0.37):
            a.cylinder(0.005, 0.018, (xx, y * 0.36, z * 0.18), BRASS, (0, 1, 0), "adjuster")
        if k == "mirror":
            base_radius = min(x * 0.40, y * 0.48)
            base_z = -z * 0.45
            a.cylinder(base_radius, z * 0.08, (0, 0, base_z), DARK, name="rotation_base")
            a.ring(
                base_radius * 0.78, base_radius, 0.0015, (0, 0, base_z + z * 0.05), STEEL, name="degree_bezel"
            )
            for index, degrees in enumerate(range(225, 316, 5)):
                angle = np.deg2rad(degrees)
                inner = base_radius * (0.78 if index % 3 == 0 else 0.86)
                outer = base_radius * 0.97
                a.rod(
                    (inner * np.cos(angle), inner * np.sin(angle), base_z + z * 0.06),
                    (outer * np.cos(angle), outer * np.sin(angle), base_z + z * 0.06),
                    0.00055,
                    LIGHT,
                    "degree_tick",
                )
            a.rod(
                (0, -base_radius * 0.47, base_z + z * 0.075),
                (0, -base_radius * 0.88, base_z + z * 0.075),
                0.0012,
                ORANGE,
                "degree_pointer",
            )
            a.box((x * 0.96, y * 0.36, z * 0.06), (0, 0, -z * 0.32), DARK, name="gimbal_crossbar")
            for sign in (-1, 1):
                a.box(
                    (x * 0.035, y * 0.40, z * 0.72), (sign * x * 0.479, 0, z * 0.04), DARK, name="gimbal_fork"
                )
                a.cylinder(
                    0.0025, x * 0.055, (sign * x * 0.463, 0, z * 0.16), STEEL, (1, 0, 0), "gimbal_pivot"
                )
            a.cylinder(x * 0.335, y * 0.30, (0, y * 0.34, z * 0.16), DARK, (0, 1, 0), "rear_coating_plate")
            a.label(obj.object_id + "\nHR-45° 1064", (0, y * 0.495, z * 0.16), x * 0.55, x * 0.29, (0, 1, 0))
            a.box((x * 0.24, 0.001, 0.002), (0, y * 0.50, z * 0.39), LIGHT, name="rear_index_line")
        else:
            a.label(obj.object_id + "\nCOATING 01", (0, y * 0.285, z * 0.16), x * 0.62, x * 0.24, (0, 1, 0))
    elif k == "post":
        a.box((x, y, 0.015), (0, 0, -z / 2 + 0.0075), DARK)
        a.ring(0.0075, 0.017, z * 0.88, (0, 0, z * 0.01), STEEL, name="post_holder")
        a.cylinder(0.009, 0.025, (0.021, 0, z * 0.20), DARK, (1, 0, 0), "locking_knob")
        a.screws(x * 0.35, y * 0.32, -z / 2 + 0.016)
    elif k == "target_screen":
        a.box((x, y, z), (0, 0, 0), DARK)
        a.box((x * 0.88, 0.002, z * 0.87), (0, -y / 2 - 0.001, 0), LIGHT)
        a.box((x * 0.78, 0.001, 0.001), (0, -y / 2 - 0.002, 0), DARK)
        a.box((0.001, 0.001, z * 0.78), (0, -y / 2 - 0.002, 0), DARK)
        for rr in (0.02, 0.04, 0.06):
            a.ring(rr, rr + 0.001, 0.001, (0, -y / 2 - 0.003, 0), DARK, (0, 1, 0), "target_ring")
    elif k == "potsherd":
        rows = 97 if obj.object_id == "POT3" else 25
        cols = 49
        vertices = []
        for side in (-1, 1):
            for j in range(rows):
                height = z * (j / (rows - 1) - 0.5)
                for i in range(cols):
                    lateral = 2 * i / (cols - 1) - 1
                    # A finite wall with concave +Y interior. The previous radial
                    # offset collapsed both surfaces onto y=0 at the centerline.
                    surface = y * (0.40 * lateral * lateral + side * 0.25)
                    if obj.object_id == "POT3" and side == 1:
                        for band in (-0.22, 0.0, 0.22):
                            center = z * (band + 0.012 * np.sin(5 * lateral))
                            surface -= y * 0.075 * np.exp(-0.5 * ((height - center) / (z * 0.014)) ** 2)
                    vertices.append(
                        [x * 0.5 * lateral, surface, height * (0.96 + 0.04 * np.cos(3 * lateral))]
                    )
        faces = []
        layer = rows * cols
        for offset, flip in ((0, False), (layer, True)):
            for j in range(rows - 1):
                for i in range(cols - 1):
                    v = offset + j * cols + i
                    for f in ([v, v + 1, v + cols + 1], [v, v + cols + 1, v + cols]):
                        faces.append(f[::-1] if flip else f)
        boundary = (
            list(range(cols))
            + [j * cols + cols - 1 for j in range(1, rows)]
            + list(range((rows - 1) * cols + cols - 2, (rows - 1) * cols - 1, -1))
            + [j * cols for j in range(rows - 2, 0, -1)]
        )
        for u, v in zip(boundary, boundary[1:] + boundary[:1]):
            faces.extend([[u, v, v + layer], [u, v + layer, u + layer]])
        shard = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
        shard.fix_normals()
        a.add(shard, c, rough=0.86, name="incised_inner_wall" if obj.object_id == "POT3" else "curved_shard")
    elif k == "bone":
        a.sphere((x * 0.42, y * 0.27, z * 0.30), (0, 0, 0), c, "shaft")
        for xx in (-x * 0.39, x * 0.39):
            for yy in (-y * 0.16, y * 0.16):
                a.sphere((x * 0.12, y * 0.32, z * 0.49), (xx, yy, 0), c, "bone_end")
    elif k == "flag":
        a.cylinder(0.004, z, (0, 0, 0), STEEL, name="flagpole")
        a.box((x * 0.82, 0.002, z * 0.32), (x * 0.41, 0, z * 0.27), c, name="flag")
        a.label("MARK", (x * 0.40, -0.0013, z * 0.27), x * 0.62, z * 0.20, background=c)
    elif k == "total_station":
        a.box((x, y, z * 0.63), (0, 0, z * 0.12), c)
        a.cylinder(x * 0.23, y * 0.80, (0, -y * 0.22, z * 0.17), DARK, (0, -1, 0), "telescope")
        a.cylinder(x * 0.17, 0.003, (0, -y * 0.63, z * 0.17), (98, 160, 177), (0, -1, 0), "objective")
        a.cylinder(x * 0.40, z * 0.17, (0, 0, -z * 0.37), DARK, name="tribrach")
        a.label("STAY\nLOCKED", (0, y / 2 + 0.001, 0), x * 0.73, z * 0.37, (0, 1, 0))
    elif k == "trowel":
        blade = cq.Workplane("XY").polyline([(-x / 2, 0), (0, -y * 0.48), (x / 2, 0)]).close().extrude(0.003)
        a.add(cad_mesh(blade), STEEL, position=(0, 0, -0.002), metal=0.7, name="blade")
        a.cylinder(z * 0.47, y * 0.48, (0, y * 0.20, 0), (144, 98, 56), (0, 1, 0), "handle")
        a.cylinder(0.005, y * 0.20, (0, -y * 0.02, 0), STEEL, (0, 1, 0), "tang")
    elif k == "screw":
        extension = 0.019 if obj.object_id == "CLAMP" else 0.0
        # Extend only the front of this clamp's shaft; its rear and ring teeth
        # stay fixed while the original head clears the molded hose shoulder.
        a.cylinder(
            y * 0.28,
            x * 0.74 + extension,
            (-x * 0.06 + extension / 2, 0, 0),
            STEEL,
            (1, 0, 0),
            "threaded_shank",
        )
        for xx in np.linspace(-x * 0.40, x * 0.18, 9):
            a.ring(y * 0.26, y * 0.36, 0.001, (xx, 0, 0), STEEL, (1, 0, 0), "thread")
        head = trimesh.creation.cylinder(y * 0.53, x * 0.23, sections=6)
        a.add(head, c, (x * 0.30 + extension, 0, 0), axis=(1, 0, 0), metal=0.7, name="hex_head")
        a.box((0.001, y * 0.65, 0.0018), (x * 0.423 + extension, 0, 0), DARK, name="driver_slot")
    elif k == "sparkplug":
        a.cylinder(0.007, z * 0.39, (0, 0, z * 0.20), LIGHT, name="ceramic")
        for zz in np.linspace(0, z * 0.33, 6):
            a.cylinder(0.008, 0.003, (0, 0, zz), LIGHT, name="ceramic_rib")
        a.add(
            trimesh.creation.cylinder(0.0105, 0.009, sections=6),
            STEEL,
            (0, 0, -z * 0.05),
            metal=0.8,
            name="hex_nut",
        )
        a.cylinder(0.006, z * 0.38, (0, 0, -z * 0.28), STEEL, name="threaded_shell")
        for zz in np.linspace(-z * 0.45, -z * 0.13, 10):
            a.ring(0.0058, 0.0065, 0.001, (0, 0, zz), STEEL, name="thread")
        # Keep the existing terminal tip, joining its base to the ceramic cap.
        ceramic_top = z * (0.20 + 0.39 / 2)
        terminal_top = z * 0.47 + 0.009 / 2
        a.cylinder(
            0.002,
            terminal_top - ceramic_top,
            (0, 0, (terminal_top + ceramic_top) / 2),
            STEEL,
            name="terminal",
        )
    elif k in ("bore", "tool_socket"):
        inner = 0.012 if k == "bore" else 0.020
        # The upper 6 mm belongs to the seating collar, not a second exposed cap.
        a.ring(inner, x / 2, z - 0.006, (0, 0, -0.003), c, name="receiver_bore")
        a.ring(inner, x * 0.55, 0.006, (0, 0, z / 2 - 0.003), STEEL, name="seating_face")
    elif k == "toolholder":
        a.cylinder(0.010, z * 0.42, (0, 0, -z * 0.285), STEEL, name="tool_shank")
        a.cylinder(x * 0.49, 0.012, (0, 0, -0.009), STEEL, name="flange")
        taper = cq.Workplane("XY").add(cq.Solid.makeCone(x * 0.34, x * 0.15, z * 0.38))
        a.add(cad_mesh(taper), c, (0, 0, 0), metal=0.8, name="taper")
        a.cylinder(0.006, z * 0.13, (0, 0, z * 0.43), STEEL, name="pull_stud")
        a.cylinder(0.009, z * 0.035, (0, 0, z * 0.49), STEEL, name="stud_head")
        # Cutting insert remains inside the .020 m shank diameter and therefore
        # does not reduce the declared tool-socket clearance.
        a.box((0.012, 0.003, 0.009), (0, -0.008, z * -0.45), BRASS, name="carbide_insert")
        a.cylinder(0.0015, 0.0015, (0, -0.010, z * -0.45), DARK, (0, -1, 0), "insert_fastener")
    elif k == "magazine":
        a.ring(x * 0.20, x * 0.48, y * 0.32, (0, 0, 0), c, (0, 1, 0), "magazine_disc")
        a.cylinder(x * 0.15, y * 0.50, (0, 0, 0), DARK, (0, 1, 0), "hub")
        for t in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            a.ring(
                0.020,
                0.027,
                y * 0.55,
                (x * 0.36 * np.cos(t), -y * 0.1, z * 0.36 * np.sin(t)),
                STEEL,
                (0, 1, 0),
                "pocket",
            )
    elif k == "din_connector":
        a.cylinder(x * 0.48, y * 0.55, (0, -y * 0.10, 0), DARK, (0, 1, 0), "handwheel")
        a.cylinder(x * 0.27, y * 0.35, (0, y * 0.32, 0), BRASS, (0, 1, 0), "nose")
        for yy in np.linspace(y * 0.22, y * 0.46, 7):
            a.ring(x * 0.25, x * 0.29, 0.001, (0, yy, 0), BRASS, (0, 1, 0), "thread")
        # Keep the current DIN mating nose; restore grip and retaining detail on
        # the non-mating handwheel, without adding an incompatible quick latch.
        for angle in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            a.cylinder(
                x * 0.014,
                y * 0.45,
                (x * 0.478 * np.cos(angle), -y * 0.10, z * 0.478 * np.sin(angle)),
                STEEL,
                (0, 1, 0),
                "handwheel_knurl",
            )
        a.ring(x * 0.29, x * 0.45, 0.002, (0, y * 0.175, 0), STEEL, (0, 1, 0), "retaining_collar")
        a.label("DRY", (0, -y * 0.38, 0), x * 0.70, z * 0.4)
    elif k == "valve":
        size = (x * 0.7, y * 0.7, z * 0.70)
        body = cq.Workplane("XY").box(*size).edges().fillet(min(min(size) * 0.16, 0.006))
        # Continue the receiver's actual 17 mm bore into the valve body. The
        # mating nose enters this cavity instead of intersecting a solid box.
        bore = cq.Workplane("XY").add(
            cq.Solid.makeCylinder(0.017, 0.032, cq.Vector(0, -y * 0.32 - 0.016, 0), cq.Vector(0, 1, 0))
        )
        a.add(cad_mesh(body.cut(bore)), c, metal=0.7, name="panel")
        a.ring(0.017, 0.025, 0.032, (0, -y * 0.32, 0), BRASS, (0, 1, 0), "DIN_receiver")
        a.cylinder(0.013, z * 0.45, (0, 0, -z * 0.37), BRASS, name="neck")
        a.cylinder(0.020, 0.022, (x * 0.35, 0, z * 0.13), DARK, (1, 0, 0), "handwheel")
    elif k == "cylinder":
        a.cylinder(x * 0.49, z * 0.77, (0, 0, -z * 0.025), c, name="bottle_body")
        a.sphere((x * 0.49, y * 0.49, z * 0.13), (0, 0, z * 0.345), c, "shoulder")
        a.sphere((x * 0.49, y * 0.49, z * 0.08), (0, 0, -z * 0.41), c, "base")
        a.cylinder(x * 0.13, z * 0.08, (0, 0, z * 0.49), STEEL, name="neck")
        a.ring(x * 0.46, x * 0.52, 0.025, (0, 0, -z * 0.43), DARK, name="boot")
        a.label("TRAINING\n" + obj.object_id, (0, y * 0.491, z * 0.22), x * 0.75, z * 0.13, (0, 1, 0))
        a.label(obj.object_id, (0, -y * 0.493, 0), x * 0.75, z * 0.15)
    elif k == "lever":
        handle_y = -y * 2
        a.cylinder(0.016, 0.016 - handle_y, (0, (0.016 + handle_y) / 2, 0), BRASS, (0, -1, 0), "spindle")
        a.box((x * 0.26, y * 0.55, z * 0.80), (0, handle_y, z * 0.23), c, name="handle")
        a.cylinder(0.010, 0.006, (0, handle_y - y * 0.2, 0), STEEL, (0, -1, 0), "retaining_bolt")
    elif k == "gauges":
        a.box((x, y, z), (0, 0, 0), DARK)
        for xx in (-x * 0.31, 0, x * 0.31):
            a.ring(z * 0.30, z * 0.36, 0.018, (xx, -y * 0.52, 0), STEEL, (0, -1, 0), "bezel")
            a.cylinder(z * 0.30, 0.003, (xx, -y * 0.58, 0), LIGHT, (0, -1, 0), "dial")
            for t in np.linspace(-0.75 * np.pi, 0.75 * np.pi, 13):
                p = np.array([xx + z * 0.25 * np.sin(t), -y * 0.61, z * 0.25 * np.cos(t)])
                q = np.array([xx + z * 0.29 * np.sin(t), -y * 0.61, z * 0.29 * np.cos(t)])
                a.rod(p, q, 0.0009, DARK, "tick")
            a.rod((xx, -y * 0.63, 0), (xx - z * 0.16, -y * 0.63, -z * 0.14), 0.0014, ORANGE, "needle")
    elif k == "cassette":
        a.box((x, y, z), (0, 0, 0), c, name="cassette")
        # Shallow side locks keep the source width below the receiver's .091 m
        # clear opening. The +Y alignment pins and mating frame are unchanged.
        for sign in (-1, 1):
            a.box(
                (0.002, y * 0.45, z * 0.17),
                (sign * (x / 2 + 0.0005), -y * 0.17, z * 0.23),
                DARK,
                name="cassette_side_lock",
            )
        a.box((x * 0.70, 0.003, z * 0.65), (0, -y * 0.52, 0), LIGHT, name="inspection_window")
        for xx in (-x * 0.27, x * 0.27):
            a.cylinder(0.005, 0.005, (xx, y / 2 + 0.001, 0), STEEL, (0, 1, 0), "alignment_pin")
        a.label("TRAINING", (0, -y * 0.56, 0), x * 0.76, z * 0.31)
    elif k == "cassette_slot":
        hollow_front(a, (x, y, z), 0.006, c)
        for xx in (-x * 0.30, x * 0.30):
            a.box((0.004, y * 0.7, 0.004), (xx, 0, -z * 0.35), STEEL, name="guide")
    elif k == "stopcock":
        # Extend the shaft towards the unchanged handle, keeping the rear cap
        # at +.0125 and the authored rotation axis at the object origin.
        a.cylinder(0.009, 0.02925, (0, -0.002125, 0), STEEL, (0, -1, 0), "rotor")
        # Preserve both rounded shapes, but make their overlapping material one
        # solid so the visible front/back planes are represented only once.
        handle = (
            cq.Workplane("XY").box(x, 0.009, 0.014).edges().fillet(min(min(x, 0.009, 0.014) * 0.16, 0.006))
        )
        pointer = (
            cq.Workplane("XY")
            .box(0.014, 0.009, z * 0.52)
            .edges()
            .fillet(min(min(0.014, 0.009, z * 0.52) * 0.16, 0.006))
        )
        handle = handle.translate((0, -y * 0.45, 0))
        pointer = pointer.translate((0, -y * 0.45, z * 0.18))
        a.add(cad_mesh(handle.union(pointer)), c, name="handle_pointer")
    elif k == "training_bag":
        a.box((x, y, z * 0.89), (0, 0, -z * 0.025), c, name="bag_body")
        a.box((x, 0.009, 0.016), (0, 0, z * 0.45), LIGHT, name="welded_seal")
        a.ring(0.006, 0.012, 0.005, (0, 0, z * 0.51), LIGHT, (0, 1, 0), "hanger_eye")
        for xx in (-x * 0.23, x * 0.23):
            a.cylinder(0.006, 0.025, (xx, 0, -z * 0.49), LIGHT, name="sealed_port")
        text = "TRAINING A" if obj.object_id == "BAG1" else "TRAINING B"
        a.label(text + "\nSIMULATION ONLY", (0, y / 2 + 0.001, 0), x * 0.86, z * 0.45, (0, 1, 0))
        a.label(obj.object_id, (0, -y / 2 - 0.001, 0), x * 0.73, z * 0.23)
    else:
        raise ValueError(f"unknown geometry recipe {k}")
    return a


def table(a, center, size=(0.90, 0.75), top=0.03, height=0.73, color=LIGHT):
    cx, cy = center
    x, y = size
    a.box((x, y, 0.035), (cx, cy, top - 0.0175), color, name="worktop")
    for xx in (-x * 0.42, x * 0.42):
        for yy in (-y * 0.40, y * 0.40):
            a.box(
                (0.035, 0.035, height),
                (cx + xx, cy + yy, top - 0.035 - height / 2),
                DARK,
                metal=0.55,
                name="table_leg",
            )
    a.box((x * 0.90, 0.028, 0.025), (cx, cy + y * 0.40, top - height * 0.67), STEEL, name="cross_member")


def tube_path(a, points, radius, color=RUBBER):
    for start, end in zip(points, points[1:]):
        a.rod(start, end, radius, color)
    for point in points[1:-1]:
        a.sphere((radius,) * 3, point, color)


def engine_hose_solids():
    """Dimensioned inlet, outlet and elbow walls with one continuous lumen."""
    points = np.asarray([(-0.46, -0.25, 1.04), (-0.32, -0.12, 1.06), (-0.27, 0.06, 1.03)])

    def faceted_solid(mesh):
        # Preserve the authored twenty-sided tubes and faceted elbow exterior;
        # rebuilding them as circular CAD primitives would change other walls.
        faces = [
            cq.Face.makeFromWires(cq.Wire.makePolygon([cq.Vector(*v) for v in triangle], close=True))
            for triangle in mesh.triangles
        ]
        return cq.Workplane(obj=cq.Solid.makeSolid(cq.Shell.makeShell(faces)))

    def roof_cutter(setback=0.0):
        high, low = 1.122 - setback, 1.087 - setback
        return (
            cq.Workplane("YZ")
            .moveTo(-0.3, high)
            .lineTo(-0.166, high)
            .bezier([(-0.166 + 0.05 / 3, high), (-0.116 - 0.05 / 3, low), (-0.116, low)], includeCurrent=True)
            .lineTo(-0.084, low)
            .bezier(
                [(-0.084 + 0.05 / 3, low), (-0.034 - 0.05 / 3, high), (-0.034, high)], includeCurrent=True
            )
            .lineTo(0.15, high)
            .lineTo(0.15, 1.3)
            .lineTo(-0.3, 1.3)
            .close()
            .extrude(1.0, both=True)
        )

    lumen = cq.Workplane(obj=cq.Solid.makeSphere(0.045, cq.Vector(*points[1]), angleDegrees1=-90))
    originals = []
    for start, end in zip(points, points[1:]):
        delta = end - start
        bore = cq.Solid.makeCylinder(
            0.045, float(np.linalg.norm(delta)), cq.Vector(*start), cq.Vector(*delta)
        )
        lumen = lumen.union(bore)
        originals.append(trimesh.creation.cylinder(radius=0.052, segment=[start, end], sections=20))
    elbow = trimesh.creation.icosphere(subdivisions=2, radius=0.052)
    elbow.apply_translation(points[1])
    originals.append(elbow)
    lumen = lumen.cut(roof_cutter(0.010))
    outer_cut = roof_cutter()
    return [faceted_solid(mesh).cut(outer_cut).cut(lumen) for mesh in originals]


def engine_clamp_hose(a):
    """Closed material regions and a band-mounted annular teaching screw seat."""
    for index, wall in enumerate(partition_cad_parts(engine_hose_solids())):
        a.add(
            cad_mesh(wall),
            DARK,
            metal=0.45 if index < 2 else 0.0,
            name="tube" if index < 2 else "rounded_part",
        )

    band = trimesh.creation.annulus(0.051, 0.055, 0.023, sections=48)
    band.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], [0, 1, 0]))
    band.apply_translation((-0.32, -0.12, 1.06))
    axis = cq.Vector(1, 0, 0)
    seat = cq.Workplane(obj=cq.Solid.makeCylinder(0.011, 0.051905, cq.Vector(-0.32421, -0.10, 1.10), axis))
    shoe = cq.Workplane("XY").box(0.032, 0.028, 0.0025).translate((-0.306, -0.10, 1.08825))
    seat = seat.union(shoe)
    bore = cq.Solid.makeCylinder(0.0052, 0.06, cq.Vector(-0.32021, -0.10, 1.10), axis)
    seat = seat.cut(bore)
    for xx in np.linspace(-0.3188, -0.29154, 9):
        groove = cq.Solid.makeCylinder(0.0066, 0.0012, cq.Vector(float(xx) - 0.0006, -0.10, 1.10), axis)
        seat = seat.cut(groove)
    faces = [
        cq.Face.makeFromWires(cq.Wire.makePolygon([cq.Vector(*v) for v in triangle], close=True))
        for triangle in band.triangles
    ]
    band_solid = cq.Workplane(obj=cq.Solid.makeSolid(cq.Shell.makeShell(faces)))
    a.add(cad_mesh(band_solid.union(seat)), STEEL, metal=0.6, name="clamp_band")


def inlaid_work_surface(a, spec):
    """A 30 mm support datum with separate, nonoverlapping pads and grid inlays."""
    top, depth, length, center_y = 0.030, 0.003, 0.94, 0.12
    table(a, (0, center_y), (1.05, length), top=top - depth)
    mat = cq.Workplane("XY").box(1.02, length * 0.96, depth).edges().fillet(depth * 0.16)
    mat = mat.translate((0, center_y, top - depth / 2))
    if spec.scene_id == "blocks":
        definitions = [
            ("left_parts_tray", (0.095, 0.055), (-0.13, -0.07), 0.012 * 0.16),
            ("right_parts_tray", (0.095, 0.055), (0.13, -0.07), 0.012 * 0.16),
        ]
    elif spec.scene_id == "connector":
        definitions = [("receiver_fixture", (0.19, 0.14), (-0.10, 0.16), 0.006 * 0.16)]
    elif spec.scene_id == "drone_bench":
        definitions = [("battery_pad", (0.12, 0.17), (0.34, -0.25), 0.007 * 0.16)]
    else:
        raise ValueError("No inlaid work surface contract for " + spec.scene_id)
    pads = []
    for name, size, xy, radius in definitions:
        envelope = cq.Workplane("XY").box(*size, depth).edges("|Z").fillet(radius)
        envelope = envelope.translate((*xy, top - depth / 2))
        pad = envelope
        if spec.scene_id == "drone_bench":
            bat = next(o for o in spec.objects if o.object_id == "BAT")
            x, y, z = bat.size_m
            orientation = rotation(bat.pose)
            if not np.allclose(orientation.as_matrix()[:, 2], [0, 0, 1], atol=1e-12):
                raise ValueError("Battery support requires its declared upright pose")
            yaw = float(orientation.as_euler("xyz", degrees=True)[2])
            # These open-top pockets follow the actual rails and contact faces
            # in the declared starting pose, leaving the housing on the mat.
            for xx in (-x * 0.36, x * 0.36):
                cutter = cq.Workplane("XY").box(0.008, y * 0.85, 0.004).translate((xx, 0, -z / 2))
                cutter = cutter.rotate((0, 0, 0), (0, 0, 1), yaw).translate(tuple(bat.pose.position_m))
                pad = pad.cut(cutter)
            for xx in np.linspace(-x * 0.28, x * 0.28, 4):
                cutter = cq.Workplane("XY").box(0.009, 0.015, 0.004)
                cutter = cutter.translate((float(xx), y * 0.30, -z / 2 - 0.0012 + 0.002))
                cutter = cutter.rotate((0, 0, 0), (0, 0, 1), yaw).translate(tuple(bat.pose.position_m))
                pad = pad.cut(cutter)
        mat = mat.cut(envelope)
        pads.append((name, envelope, pad))
    lines = []
    for index, xx in enumerate(np.linspace(-0.48, 0.48, 17)):
        line = cq.Workplane("XY").box(0.0006, length * 0.91, 0.0004)
        line = line.translate((float(xx), center_y, top - 0.0002))
        for _, envelope, _ in pads:
            line = line.cut(envelope)
        mat = mat.cut(line)
        lines.append((f"mat_line_{index:02d}", line))
    a.add(cad_mesh(mat), (56, 88, 96), name="work_mat")
    for name, _, pad in pads:
        a.add(cad_mesh(pad), DARK, name=name)
    for name, line in lines:
        a.add(cad_mesh(line), (76, 111, 116), name=name)


def make_environment(spec: SceneSpec) -> Assembly:
    a = Assembly(spec.scene_id + "_environment")
    sid = spec.scene_id
    objects = {o.object_id: o for o in spec.objects}
    if sid in ("control_panel", "connector", "blocks", "drone_bench", "optical_bench"):
        length = 1.5 if sid == "optical_bench" else 0.94
        center_y = 0.37 if sid == "optical_bench" else 0.12
        if sid in ("blocks", "connector", "drone_bench"):
            inlaid_work_surface(a, spec)
        else:
            table(a, (0, center_y), (1.05, length))
            a.box((1.02, length * 0.96, 0.003), (0, center_y, 0.0315), (56, 88, 96), name="work_mat")
            for xx in np.linspace(-0.48, 0.48, 17):
                a.box(
                    (0.0006, length * 0.91, 0.0004), (xx, center_y, 0.0333), (76, 111, 116), name="mat_line"
                )
        a.box((3, 3, 0.035), (0, 0, -0.755), (165, 176, 184), name="floor")
    if sid == "control_panel":
        panel = (
            cq.Workplane("XY").box(0.41, 0.18, 0.025).edges().fillet(0.004).translate((-0.08, -0.04, 0.0425))
        )
        for oid in ("A", "B"):
            o = objects[oid]
            px, py, pz = o.pose.position_m
            seat_z = pz - o.size_m[2] * 0.44
            recess = cq.Workplane("XY").center(px, py).circle(min(o.size_m[:2]) * 0.47 + 0.00025)
            panel = panel.cut(recess.extrude(0.056 - seat_z).translate((0, 0, seat_z)))
        a.add(cad_mesh(panel), (117, 137, 153), name="instrument_panel")
        a.box((0.145, 0.12, 0.015), (0.18, 0.17, 0.0375), DARK, name="module_support")
        for oid in ("A", "B"):
            p = np.asarray(objects[oid].pose.position_m)
            for t in np.linspace(0, 2 * np.pi, 24, endpoint=False):
                a.rod(
                    p + [0.05 * np.cos(t), 0.05 * np.sin(t), -0.015],
                    p + [0.056 * np.cos(t), 0.056 * np.sin(t), -0.015],
                    0.0007,
                    LIGHT,
                    "dial_tick",
                )
            a.label(oid, tuple(p + [0, -0.067, -0.013]), 0.027, 0.014, (0, 0, 1))
        a.label("HoloCue\nCONTROL WORKSTATION", (-0.08, -0.131, 0.044), 0.26, 0.045)
    elif sid == "connector":
        tube_path(
            a, [(0.18, 0.19, 0.063), (0.30, 0.26, 0.063), (0.36, 0.25, 0.035), (0.36, 0.42, 0.035)], 0.006
        )
        a.label("KEYED CONNECTOR", (0, -0.255, 0.031), 0.35, 0.08, (0, 0, 1))
    elif sid == "blocks":
        a.label("CONSTRUCTION LAB", (0, -0.27, 0.031), 0.40, 0.08, (0, 0, 1))
    elif sid == "drone_bench":
        body = cq.Workplane("XY").box(0.19, 0.24, 0.09).edges().fillet(0.008)
        opening = cq.Workplane("XY").box(0.105, 0.153, 0.08).translate((0, 0, 0.04))
        a.add(cad_mesh(body.cut(opening)), LIGHT, (0, 0.025, 0.090), name="airframe")
        support = (
            cq.Workplane("XY")
            .box(0.028, 0.040, 0.038)
            .edges()
            .fillet(0.00448)
            .translate((0.072, 0.025, 0.151))
        )
        latch = objects["GUARD"]
        px, py, pz = latch.pose.position_m
        seat_z = pz - latch.size_m[2] * 0.44
        # This shallow circular seat opens through the support's narrow sides.
        recess = cq.Workplane("XY").center(px, py).circle(min(latch.size_m[:2]) * 0.47 + 0.00025)
        a.add(
            cad_mesh(support.cut(recess.extrude(0.171 - seat_z).translate((0, 0, seat_z)))),
            DARK,
            name="latch_support",
        )
        for xx in (-0.22, 0.22):
            for yy in (-0.22, 0.22):
                a.rod((np.sign(xx) * 0.07, np.sign(yy) * 0.075, 0.096), (xx, yy, 0.099), 0.016, DARK, "arm")
                a.box((0.05, 0.06, 0.014), (xx, yy, 0.087), STEEL, name="motor_mount")
        a.box((0.24, 0.29, 0.016), (0, 0.025, 0.043), ORANGE, name="service_cradle")
        a.label("DRIVES DISCONNECTED", (0, -0.32, 0.031), 0.40, 0.07, (0, 0, 1))
    elif sid == "optical_bench":
        a.box((0.63, 1.22, 0.022), (0, 0.36, 0.044), STEEL, name="breadboard")
        for xx in np.arange(-0.28, 0.3, 0.035):
            for yy in np.arange(-0.19, 0.96, 0.035):
                a.cylinder(0.002, 0.001, (xx, yy, 0.0555), DARK, name="threaded_hole")
        for oid in ("L2", "M"):
            o = objects[oid]
            px, py, pz = o.pose.position_m
            # Retain the original forty-sided outside wall; only the axial
            # blind bore removes material above the existing shaft end.
            rim = [
                (0.014 * np.cos(t), 0.014 * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 40, endpoint=False)
            ]
            post = cq.Workplane("XY").polyline(rim).close().extrude(0.050).translate((px, py, 0.054))
            seat_z = pz - o.size_m[2] * 0.5
            bore = (
                cq.Workplane("XY")
                .center(px, py)
                .circle(0.00725)
                .extrude(0.105 - seat_z)
                .translate((0, 0, seat_z))
            )
            a.add(cad_mesh(post.cut(bore)), STEEL, metal=0.65, name="fixed_post")
            a.box((0.09, 0.08, 0.012), (px, py, 0.061), DARK, name="post_base")
        a.box((0.15, 0.13, 0.015), (0.22, -0.12, 0.058), DARK, name="optic_tray")
        a.cylinder(0.012, 0.045, (-0.31, 0.88, 0.058), STEEL, name="screen_post")
        a.label("OPTICAL ASSEMBLY\nSOURCE DISABLED", (0.33, 0.45, 0.06), 0.20, 0.10, (0, 0, 1))
    elif sid == "server_rack":
        a.box((3, 2.5, 0.06), (0, 0.2, -0.03), (149, 165, 176), name="raised_floor")
        for xx in (-0.28, 0.28):
            for yy in (-0.045, 0.61):
                a.box((0.035, 0.035, 1.90), (xx, yy, 0.99), DARK, name="rack_post")
        for zz in (0.05, 1.93):
            a.box((0.59, 0.70, 0.045), (0, 0.28, zz), DARK, name="rack_crossmember")
        a.box((0.55, 0.025, 1.8), (0, 0.64, 0.99), (81, 100, 116), name="rear_panel")
        for zz in (0.25, 0.50, 0.75, 1.42, 1.68):
            a.box((0.46, 0.52, 0.10), (0, 0.28, zz), (77, 91, 105), name="installed_module")
            for xx in np.linspace(-0.19, 0.19, 16):
                a.box((0.007, 0.004, 0.05), (xx, 0.016, zz), DARK, name="vent")
        table(a, (-0.72, -0.22), (0.55, 0.61), 0.88, 0.82)
        table(a, (0.72, -0.22), (0.55, 0.61), 0.88, 0.82)
        a.label("RACK 04", (0, -0.071, 1.82), 0.29, 0.075)
    elif sid == "shelf_picking":
        a.box((3.6, 3.3, 0.06), (0.30, 0.55, -0.03), (181, 186, 178), name="floor")
        for xx in (-0.69, 0.01):
            for yy in (0.01, 0.58):
                a.box((0.033, 0.033, 1.95), (xx, yy, 0.975), DARK, name="shelf_upright")
        for zz in (0.28, 0.64, 1.015, 1.70):
            a.box((0.74, 0.60, 0.03), (-0.34, 0.295, zz), (163, 171, 174), name="shelf_deck")
        a.box((0.70, 0.02, 1.72), (-0.34, 0.60, 0.95), (204, 207, 192), name="shelf_back")
        table(a, (-0.25, -0.62), (0.49, 0.41), 0.81, 0.75)
        table(a, (0.64, -0.14), (0.42, 0.40), 0.84, 0.78)
        table(a, (1.08, 0.70), (0.44, 1.05), 0.84, 0.78, DARK)
        for yy in np.linspace(0.20, 1.18, 23):
            a.cylinder(0.017, 0.40, (1.08, yy, 0.843), STEEL, (1, 0, 0), "roller")
        a.label("PICKING BAY 02", (-0.34, -0.011, 1.49), 0.45, 0.14)
    elif sid == "dig_site":
        a.box((1.4, 1.4, 0.06), (0, 0.20, -0.38), (114, 83, 57), name="pit_floor")
        for zz, color in [(-0.26, (133, 99, 67)), (-0.14, (160, 127, 87)), (-0.035, (174, 145, 103))]:
            height = 0.10
            for xx in (-0.79, 0.79):
                a.box((0.18, 1.76, height), (xx, 0.20, zz), color, name="soil_layer")
            for yy in (-0.59, 0.99):
                a.box((1.40, 0.18, height), (0, yy, zz), color, name="soil_layer")
        for xx in (-0.80, 0.80):
            for yy in (-0.6, 1.0):
                a.cylinder(0.015, 0.25, (xx, yy, 0.045), ORANGE, name="survey_stake")
        tube_path(
            a,
            [
                (-0.80, -0.60, 0.14),
                (0.80, -0.60, 0.14),
                (0.80, 1, 0.14),
                (-0.80, 1, 0.14),
                (-0.80, -0.60, 0.14),
            ],
            0.002,
            LIGHT,
        )
        a.box((0.35, 0.30, 0.03), (0.85, -0.46, 0.14), DARK, name="padded_recording_tray")
        a.box((0.36, 0.52, 0.06), (-0.85, -0.22, 0), (157, 168, 173), name="tool_tray")
        for t in (0, 2 * np.pi / 3, 4 * np.pi / 3):
            a.rod(
                (0.68, 0.98, 0.68),
                (0.68 + 0.26 * np.cos(t), 0.98 + 0.26 * np.sin(t), 0.01),
                0.018,
                ORANGE,
                "tripod_leg",
            )
        a.label("RECORDED MATERIAL", (0.85, -0.613, 0.14), 0.30, 0.065)
    elif sid == "engine_bay":
        a.box((3, 3, 0.06), (0, 0.25, -0.03), (150, 160, 165), name="garage_floor")
        a.box((1.18, 1.03, 0.25), (0, 0.20, 0.66), (51, 79, 106), name="engine_cradle")
        for xx in (-0.62, 0.62):
            a.box((0.14, 1.13, 0.17), (xx, 0.19, 0.94), (42, 98, 136), name="fender")
        a.box((1.16, 0.14, 0.18), (0, -0.40, 0.94), (42, 98, 136), name="front_crossmember")
        block = cq.Workplane("XY").box(0.68, 0.49, 0.26).edges().fillet(0.012)
        a.add(cad_mesh(block), STEEL, (0, 0.15, 0.84), metal=0.45, rough=0.62, name="engine_block")
        cover = cq.Workplane("XY").box(0.54, 0.41, 0.09).edges().fillet(0.015)
        cutter = cq.Workplane("XY").center(0.16, 0.11).circle(0.021).extrude(0.30, both=True)
        a.add(cad_mesh(cover.cut(cutter)), DARK, (0, 0.15, 1.04), rough=0.62, name="cam_cover")
        for xx in (-0.20, -0.08, 0.04):
            a.cylinder(0.022, 0.022, (xx, 0.26, 1.095), DARK, name="coil_base")
            a.box((0.058, 0.082, 0.029), (xx, 0.26, 1.120), (63, 71, 75), name="ignition_coil")
            a.box((0.028, 0.026, 0.017), (xx, 0.313, 1.120), (74, 84, 90), name="coil_connector")
        for yy in np.linspace(0.02, 0.32, 8):
            a.box((0.45, 0.008, 0.010), (-0.035, yy, 1.089), (70, 80, 89), name="cover_rib")
        for xx in (-0.244, 0.244):
            for yy in (-0.027, 0.07, 0.24, 0.326):
                a.cylinder(0.006, 0.004, (xx, yy, 1.088), STEEL, name="cover_fastener")
        for zz in np.linspace(0.745, 0.91, 6):
            a.box((0.60, 0.014, 0.015), (0, -0.098, zz), STEEL, name="casting_rib")
        for xx in (-0.26, 0.26):
            a.cylinder(0.018, 0.023, (xx, -0.112, 0.82), BRASS, (0, -1, 0), "core_plug")
        for yy in np.linspace(-0.01, 0.30, 4):
            tube_path(a, [(-0.16, yy, 1.00), (-0.31, yy, 1.04), (-0.40, yy, 0.93)], 0.033, STEEL)
        engine_clamp_hose(a)
        a.box((0.15, 0.13, 0.025), (0.27, -0.27, 1.0075), DARK, name="sparkplug_tray")
        a.box((0.12, 0.12, 0.05), (0.44, -0.15, 0.985), DARK, name="connector_rest")
        for yy in (0.04, 0.24):
            a.cylinder(0.073, 0.030, (0.38, yy, 0.90), DARK, (1, 0, 0), "belt_pulley")
        tube_path(
            a,
            [
                (0.401, 0.04, 0.975),
                (0.401, 0.24, 0.975),
                (0.401, 0.312, 0.90),
                (0.401, 0.24, 0.826),
                (0.401, 0.04, 0.826),
                (0.401, -0.033, 0.90),
                (0.401, 0.04, 0.975),
            ],
            0.006,
            RUBBER,
        )
        a.box((0.13, 0.24, 0.16), (-0.46, 0.41, 0.965), DARK, name="battery_case")
        a.box((0.14, 0.25, 0.02), (-0.46, 0.41, 1.055), (69, 83, 90), name="battery_lid")
        for xx, col in [(-0.502, (169, 58, 45)), (-0.418, (48, 52, 56))]:
            a.cylinder(0.012, 0.015, (xx, 0.35, 1.073), col, name="battery_terminal")
        a.label("12 V", (-0.46, 0.282, 0.99), 0.09, 0.06)
        for xx in np.linspace(-0.48, 0.48, 32):
            a.box((0.008, 0.034, 0.11), (xx, -0.36, 0.94), (96, 112, 120), name="radiator_fin")
        hood = rounded_box((1.21, 0.045, 0.91)).copy()
        hood.apply_transform(trimesh.transformations.rotation_matrix(-0.25, [1, 0, 0]))
        a.add(hood, (42, 98, 136), (0, 0.76, 1.49), metal=0.45, name="open_hood")
        for xx in (-0.46, 0, 0.46):
            rib = rounded_box((0.030, 0.035, 0.76)).copy()
            rib.apply_transform(trimesh.transformations.rotation_matrix(-0.25, [1, 0, 0]))
            a.add(rib, (49, 80, 101), (xx, 0.729, 1.49), name="hood_inner_rib")
        a.rod((-0.51, 0.45, 1), (-0.51, 0.81, 1.75), 0.010, STEEL, "hood_strut")
    elif sid == "cnc_toolchange":
        a.box((3, 2.6, 0.06), (0, 0.30, -0.03), (158, 169, 178), name="workshop_floor")
        table(a, (0.05, -0.05), (1.25, 0.74), 0.995, 0.92)
        a.box((0.80, 0.30, 0.72), (0.22, 0.79, 1.18), (190, 203, 212), name="machine_column")
        for xx in (-0.43, 0.88):
            a.box((0.12, 0.94, 1.18), (xx, 0.43, 1.23), (190, 203, 212), name="machine_side_column")
        a.box((1.43, 0.94, 0.11), (0.225, 0.43, 1.875), (180, 197, 208), name="machine_header")
        a.box((1.43, 0.76, 0.08), (0.225, 0.49, 0.60), (128, 151, 166), name="chip_tray")
        for zz in np.linspace(0.66, 1.65, 20):
            a.box((0.32, 0.018, 0.017), (0.28, 0.615, zz), (108, 130, 146), name="way_cover_fold")
        a.box((0.20, 0.25, 0.32), (0.23, 0.60, 1.62), (143, 163, 178), name="spindle_housing")
        a.cylinder(0.063, 0.12, (0.23, 0.55, 1.40), STEEL, name="spindle_nose")
        for yy in np.linspace(0.05, 0.43, 7):
            a.box((0.72, 0.012, 0.008), (0.12, yy, 1.008), DARK, name="table_t_slot")
        a.label("ISOLATED TRAINING CELL", (0.225, -0.045, 1.875), 0.79, 0.056)
        a.box((0.20, 0.18, 0.15), (0.20, 0.25, 1.005), DARK, name="tool_socket_support")
        a.box((0.37, 0.15, 0.65), (-0.55, 0.49, 1.45), DARK, name="control_console")
        a.label("TEACHING FIXTURE", (0, -0.425, 0.91), 0.52, 0.12)
        # Mount the magazine ahead of the way covers, with its hub connected
        # to the column front. Append to retain existing environment node IDs.
        a.cylinder(0.03, 0.034, (0.55, 0.623, 1.47), axis=(0, 1, 0), name="magazine_mount_standoff")
    elif sid == "dive_fillstation":
        a.box((2.6, 2.4, 0.06), (0, 0.26, -0.03), (158, 178, 180), name="floor")
        a.box((1.05, 0.42, 0.12), (0, 0.07, 0.13), DARK, name="bottle_rack")
        for xx in (-0.35, 0, 0.35):
            a.ring(0.093, 0.101, 0.024, (xx, 0.06, 0.44), STEEL, name="bottle_restraint")
            a.rod((xx, 0.16, 0.44), (xx, 0.37, 0.44), 0.012, STEEL, "restraint_bracket")
        a.box((1.10, 0.10, 1.05), (0, 0.77, 1.02), (124, 151, 166), name="manifold_panel")

        # Keep the original faceted manifold and hose cross sections outside
        # this local valve junction. A blind shaft seat replaces solid overlap.
        def valve_segment(start, end, radius):
            segment = trimesh.creation.cylinder(radius=radius, segment=np.asarray([start, end]), sections=20)
            direction = np.asarray(end) - start
            length = np.linalg.norm(direction)
            direction /= length
            ring = segment.vertices[np.abs((segment.vertices - start) @ direction) < 1e-8]
            ring = ring[np.linalg.norm(ring - start, axis=1) > radius / 2]
            u = ring[0] - start
            v = np.cross(direction, u)
            ring = ring[np.argsort(np.arctan2((ring - start) @ v, (ring - start) @ u))]
            wire = cq.Wire.makePolygon([cq.Vector(*p) for p in ring], close=True)
            return cq.Workplane(obj=cq.Solid.extrudeLinear(wire, [], cq.Vector(*(direction * length))))

        hose_points = [
            (0.34, 0.61, 1.25),
            (0.49, 0.53, 1.05),
            (0.62, 0.22, 0.58),
            (0.70, 0.10, 0.72),
            (0.67, 0.08, 0.90),
        ]
        hose_joint = tuple(np.asarray(hose_points[0]) + 0.16 * (np.asarray(hose_points[1]) - hose_points[0]))
        manifold = valve_segment((-0.42, 0.62, 1.25), (0.45, 0.62, 1.25), 0.024)
        boss = (
            cq.Workplane(cq.Plane(origin=(0.34, 0.584, 1.25), normal=(0, 1, 0))).circle(0.022).extrude(0.052)
        )
        branch = valve_segment(hose_points[0], hose_joint, 0.012)
        bore = (
            cq.Workplane(cq.Plane(origin=(0.34, 0.570, 1.25), normal=(0, 1, 0)))
            .circle(0.01625)
            .extrude(0.056)
        )
        a.add(cad_mesh(manifold.union(boss).union(branch).cut(bore)), BRASS, metal=0.45, name="manifold")
        table(a, (0.55, -0.30), (0.28, 0.25), 0.861, 0.80)
        tube_path(a, [hose_joint, *hose_points[1:]], 0.012, RUBBER)
        a.cylinder(0.017, 0.030, (0.67, 0.08, 0.91), DARK, name="parked_hose_cap")
        a.rod((0.67, 0.09, 0.88), (0.67, 0.73, 0.88), 0.006, STEEL, "hose_storage_hook")
        a.label("DEPRESSURIZED\nTRAINING EQUIPMENT", (0, 0.712, 0.94), 0.70, 0.23)
        # Keep the bottle poses and original detail meshes. These annular seats
        # bear against the flat boot undersides, leaving the lower domes clear.
        for obj in spec.objects:
            if obj.object_id in ("BOTTLE1", "BOTTLE2", "BOTTLE3"):
                xx, yy, zz = obj.pose.position_m
                boot_bottom = zz - obj.size_m[2] * 0.43 - 0.0125
                seat_height = boot_bottom - 0.19
                a.ring(
                    obj.size_m[0] * 0.46,
                    0.105,
                    seat_height,
                    (xx, yy, 0.19 + seat_height / 2),
                    RUBBER,
                    name="bottle_seat",
                )
        for xx in (-0.44, 0.44):
            for yy in (-0.065, 0.20):
                a.cylinder(0.045, 0.07, (xx, yy, 0.035), RUBBER, name="rack_foot")
        # A floor-supported rear frame carries the panel and connects to the
        # rack; the bottles themselves do not carry the panel.
        for xx in (-0.46, 0.46):
            a.cylinder(0.045, 0.04, (xx, 0.77, 0.02), RUBBER, name="panel_foot")
            a.cylinder(0.022, 0.49, (xx, 0.77, 0.285), STEEL, name="panel_post")
            a.rod((xx, 0.23, 0.13), (xx, 0.77, 0.13), 0.018, STEEL, "rack_rear_tie")
        for xx in (-0.35, 0, 0.35):
            a.rod((xx, 0.36, 0.44), (xx, 0.735, 0.54), 0.012, STEEL, "restraint_panel_brace")
        for xx in (-0.24, 0.24):
            a.rod((xx, 0.62, 1.25), (xx, 0.735, 1.25), 0.012, STEEL, "manifold_standoff")
        for xx in (-0.14, 0.14):
            a.box((0.035, 0.035, 0.035), (xx, 0.711, 1.515), DARK, name="gauge_panel_mount")
    elif sid == "infusion_ward":
        a.box((2.6, 2.6, 0.06), (0, 0.20, -0.03), (186, 199, 203), name="training_room_floor")
        table(a, (-0.45, -0.22), (0.50, 0.44), 0.95, 0.88)
        a.cylinder(0.014, 1.88, (0.03, 0.49, 0.99), STEEL, name="iv_pole")
        for theta in np.linspace(0, 2 * np.pi, 5, endpoint=False):
            end = (0.03 + 0.30 * np.cos(theta), 0.49 + 0.30 * np.sin(theta), 0.075)
            a.rod((0.03, 0.49, 0.13), end, 0.012, STEEL, "base_leg")
            a.cylinder(0.032, 0.025, (end[0], end[1], 0.045), DARK, (1, 0, 0), "caster")
        a.rod((-0.22, 0.49, 1.945), (0.25, 0.49, 1.945), 0.007, STEEL, "hanger")
        for xx in (-0.17, 0.22):
            tube_path(a, [(xx, 0.49, 1.945), (xx, 0.40, 1.945), (xx, 0.40, 1.90)], 0.004, STEEL)
        a.box((0.22, 0.11, 0.21), (0.05, 0.30, 1.30), LIGHT, name="pump_chassis")
        a.box((0.13, 0.12, 0.09), (-0.44, 0.62, 1.27), DARK, name="monitor_support")
        a.rod((-0.44, 0.62, 1.27), (-0.44, 0.62, 0.08), 0.015, STEEL, "monitor_stand")
        a.rod((0.065, 0.17, 1.01), (0.135, 0.17, 1.01), 0.007, LIGHT, "static_stopcock_body")
        a.label("TEACHING EQUIPMENT", (-0.45, -0.443, 0.88), 0.38, 0.10)
        # Add physical supports without moving the teaching objects or replacing
        # any authored detail. Each support meets the existing mating surfaces.
        a.cylinder(0.15, 0.026, (-0.44, 0.62, 0.013), DARK, name="monitor_floor_base")
        a.rod((-0.44, 0.62, 0.024), (-0.44, 0.62, 0.09), 0.015, STEEL, "monitor_stand_extension")
        a.ring(0.0135, 0.022, 0.04, (0.03, 0.49, 1.30), STEEL, name="pump_pole_clamp")
        a.rod((0.05, 0.35, 1.30), (0.03, 0.49, 1.30), 0.015, STEEL, "pump_pole_bracket")
        a.box((0.085, 0.005, 0.09), (0.05, 0.244, 1.30), LIGHT, name="slot_chassis_mount")
        a.ring(0.0135, 0.021, 0.03, (0.03, 0.49, 1.01), STEEL, name="stopcock_pole_clamp")
        a.rod((0.10, 0.173, 1.01), (0.03, 0.49, 1.01), 0.007, STEEL, "stopcock_pole_bracket")
        # The stationary journal starts exactly at the rotor rear cap, leaving
        # its -Y axis and complete 90-degree handle sweep unchanged.
        a.cylinder(0.007, 0.0115, (0.10, 0.16825, 1.01), LIGHT, (0, 1, 0), "stopcock_rotor_journal")
        a.cylinder(0.014, 0.022, (0.03, 0.49, 1.935), STEEL, name="pole_hanger_socket")
        for theta in np.linspace(0, 2 * np.pi, 5, endpoint=False):
            end = (0.03 + 0.30 * np.cos(theta), 0.49 + 0.30 * np.sin(theta), 0.045)
            a.ring(0.031, 0.045, 0.025, end, RUBBER, (1, 0, 0), "caster_floor_tread")
        for xx in (-0.66, -0.24):
            for yy in (-0.396, -0.044):
                a.box((0.035, 0.035, 0.04), (xx, yy, 0.02), DARK, name="table_floor_foot")
    else:
        raise ValueError(f"unknown workstation {sid}")
    # Append floor supports after the authored environment so original node IDs,
    # materials, task objects, and their reference frames remain unchanged.
    if sid in ("control_panel", "optical_bench"):
        cy = 0.37 if sid == "optical_bench" else 0.12
        depth = 1.5 if sid == "optical_bench" else 0.94
        for xx in (-1.05 * 0.42, 1.05 * 0.42):
            for yy in (cy - depth * 0.40, cy + depth * 0.40):
                a.box((0.035, 0.035, 0.0025), (xx, yy, -0.73625), DARK, name="table_ground_foot")
    elif sid == "cnc_toolchange":
        for xx in (0.05 - 1.25 * 0.42, 0.05 + 1.25 * 0.42):
            for yy in (-0.05 - 0.74 * 0.40, -0.05 + 0.74 * 0.40):
                a.box((0.035, 0.035, 0.04), (xx, yy, 0.02), DARK, name="table_ground_foot")
    elif sid == "dive_fillstation":
        for xx in (0.55 - 0.28 * 0.42, 0.55 + 0.28 * 0.42):
            for yy in (-0.30 - 0.25 * 0.40, -0.30 + 0.25 * 0.40):
                a.box((0.035, 0.035, 0.026), (xx, yy, 0.013), DARK, name="table_ground_foot")
    elif sid == "server_rack":
        for cx in (-0.72, 0.72):
            for xx in (cx - 0.55 * 0.42, cx + 0.55 * 0.42):
                for yy in (-0.22 - 0.61 * 0.40, -0.22 + 0.61 * 0.40):
                    a.box((0.035, 0.035, 0.025), (xx, yy, 0.0125), DARK, name="table_ground_foot")
        for xx in (-0.28, 0.28):
            for yy in (-0.045, 0.61):
                a.box((0.035, 0.035, 0.04), (xx, yy, 0.02), DARK, name="rack_ground_foot")
    elif sid == "shelf_picking":
        for cx, cy, width, depth in (
            (-0.25, -0.62, 0.49, 0.41),
            (0.64, -0.14, 0.42, 0.40),
            (1.08, 0.70, 0.44, 1.05),
        ):
            for xx in (cx - width * 0.42, cx + width * 0.42):
                for yy in (cy - depth * 0.40, cy + depth * 0.40):
                    a.box((0.035, 0.035, 0.025), (xx, yy, 0.0125), DARK, name="table_ground_foot")
    elif sid == "engine_bay":
        # A fixed teaching stand bears on the existing cradle underside z=.535.
        for xx in (-0.46, 0.46):
            a.box((0.12, 1.10, 0.04), (xx, 0.20, 0.02), DARK, name="engine_stand_base")
            for yy in (-0.17, 0.57):
                a.box((0.08, 0.08, 0.495), (xx, yy, 0.2875), STEEL, metal=0.55, name="engine_stand_post")
        # The fender/crossmember frame and connector rest have separate gaps
        # above the cradle. Join each to its existing bearing surfaces.
        for xx in (-0.57, 0.57):
            a.box((0.045, 0.12, 0.07), (xx, 0.20, 0.82), STEEL, metal=0.55, name="engine_fender_riser")
        a.box((0.055, 0.055, 0.175), (0.44, -0.15, 0.8725), STEEL, metal=0.55, name="engine_connector_post")
        for yy in (0.04, 0.24):
            a.cylinder(0.014, 0.025, (0.3525, yy, 0.90), STEEL, (1, 0, 0), "engine_pulley_axle")
        a.cylinder(0.005, 0.0027, (0.27, -0.27, 1.02135), DARK, name="sparkplug_rest_pad")
    return a
