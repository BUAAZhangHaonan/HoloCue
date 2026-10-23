"""LDraw-derived teaching bricks with the existing 16 mm mating contract.

The original, attributed DAT files are retained beside the source receipt.
Straight wall heights and the baseplate outline are adapted, not its stud
cross-sections. See the asset README for the exact teaching-scale changes.
"""

from collections import defaultdict
from functools import lru_cache

import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly
from scripts.scenes.asset_composition import mature_asset, place_scene, textured_box

SOURCE_DIR = "assets/downloads/blocks_reconstruction/ldraw"
LDU_M = 0.0008
TABLE_TOP = 0.028
WORK_TOP = 0.030


@lru_cache(maxsize=2)
def _source_groups(part):
    """Expand the retained LDraw BFC geometry, using its 48-segment primitives.

    Type 2/5 display edges have no area and are not exported as fake rods.
    Mirrored references and INVERTNEXT both affect the triangle winding.
    Each actual stud/tube remains a named, independently inspectable group.
    """
    directory = root() / SOURCE_DIR
    groups = defaultdict(list)
    counts = defaultdict(int)

    def visit(relative, transform, inverted=False, group="shell"):
        ccw, invert_next = True, False
        for line in (directory / relative).read_text().splitlines():
            fields = line.split()
            if not fields:
                continue
            if fields[0] == "0":
                if fields[1:3] == ["BFC", "INVERTNEXT"]:
                    invert_next = True
                elif fields[1:2] == ["BFC"]:
                    if "CCW" in fields:
                        ccw = True
                    elif "CW" in fields:
                        ccw = False
                continue
            if fields[0] == "1":
                values = np.asarray(fields[2:14], dtype=float)
                local = np.eye(4)
                local[:3, 3] = values[:3]
                local[:3, :3] = values[3:].reshape(3, 3)
                filename = " ".join(fields[14:]).replace("\\", "/").lower()
                child = ("parts/" if filename.startswith("s/") else "p/") + filename
                high = directory / "p/48" / filename
                if child.startswith("p/") and high.is_file():
                    child = "p/48/" + filename
                subgroup = group
                if filename in ("stud.dat", "stud4.dat"):
                    kind = "stud" if filename == "stud.dat" else "underside_tube"
                    subgroup = f"{kind}_{counts[kind]:03d}"
                    counts[kind] += 1
                mirrored = np.linalg.det(local[:3, :3]) < 0
                visit(child, transform @ local, inverted ^ invert_next ^ mirrored, subgroup)
                invert_next = False
            elif fields[0] in ("3", "4"):
                points = np.asarray(fields[2:], dtype=float).reshape(-1, 3)
                points = trimesh.transform_points(points, transform)
                if inverted ^ (not ccw):
                    points = points[::-1]
                groups[group].append(points[[0, 1, 2]])
                if len(points) == 4:
                    groups[group].append(points[[0, 2, 3]])

    visit("parts/" + part + ".dat", np.eye(4))
    return {name: np.asarray(triangles) for name, triangles in groups.items()}


def _mesh(triangles):
    return trimesh.Trimesh(
        vertices=triangles.reshape(-1, 3),
        faces=np.arange(triangles.size // 3).reshape(-1, 3),
        process=True,
    )


def _z_up(points):
    # LDraw is -Y up; this proper rotation maps X,Z,-Y to X,Y,Z.
    return points[..., [0, 2, 1]] * np.asarray([LDU_M, LDU_M, -LDU_M])


def brick(obj):
    a = Assembly(obj.object_id)
    for name, original in _source_groups("3001").items():
        points = original.copy()
        # Top and the 4 LDU roof thickness stay fixed. Only the straight wall
        # and tube ends at y=24 extend to y=25: 19.2 -> 20.0 mm body height.
        points[..., 1] += np.clip((points[..., 1] - 4.0) / 20.0, 0.0, 1.0)
        points = _z_up(points)
        points[..., 2] += 0.010
        # The inspected blue tube rims otherwise blend into the same-normal
        # cavity roof in the shadowless viewer. This is a teaching material
        # contrast, not source texture/AO; all mature geometry stays intact.
        inspection_tube = obj.object_id == "B" and name.startswith("underside_tube_")
        color = tuple(round(c * 0.70) for c in obj.color) if inspection_tube else tuple(obj.color)
        a.add(
            _mesh(points),
            color,
            metal=0,
            rough=0.40 if inspection_tube else 0.26,
            name="ldraw_3001_" + name,
        )
    a.label(obj.object_id, (0, -0.01603, 0.001), 0.007, 0.006, background=(238, 235, 216))
    return a


def baseplate(obj):
    a = Assembly(obj.object_id)
    kept = 0
    for name, original in _source_groups("3867").items():
        points = original.copy()
        if name.startswith("stud_"):
            center = (points.min(axis=(0, 1)) + points.max(axis=(0, 1))) / 2
            if abs(center[0]) > 130.1 or abs(center[2]) > 90.1:
                continue
            kept += 1
        else:
            # Translate the four mature rounded border strips inward. This
            # preserves each 4 LDU corner radius while removing outer rows;
            # no stud pitch, stud radius, or corner cross-section is stretched.
            points[..., 0] -= np.sign(points[..., 0]) * 20
            points[..., 2] -= np.sign(points[..., 2]) * 60
            # Only the flat slab becomes 6 mm thick; the studs stay 3.2 mm.
            points[..., 1] *= 7.5 / 4
        points = _z_up(points)
        points[..., 2] += 0.003
        a.add(_mesh(points), tuple(obj.color), metal=0, rough=0.30, name="ldraw_3867_" + name)
    if kept != 140:
        raise ValueError(f"Expected 14 x 10 mature studs, got {kept}")
    # Printed alignment marks lie outside the final A footprint. They do not
    # replace the stud geometry, occupy the cavity, or act as physical support.
    for dx in (-0.034, 0.034):
        a.add(
            trimesh.creation.box((0.0007, 0.036, 0.00003)),
            (35, 63, 46),
            (-0.032 + dx, 0, 0.003025),
            rough=0.65,
            name="target_outline_print",
        )
    for dy in (-0.018, 0.018):
        a.add(
            trimesh.creation.box((0.068, 0.0007, 0.00003)),
            (35, 63, 46),
            (-0.032, dy, 0.003025),
            rough=0.65,
            name="target_outline_print",
        )
    a.label(
        "A  /  2 x 4", (-0.032, -0.032, 0.003045), 0.018, 0.004, (0, 0, 1), tuple(obj.color), (249, 237, 191)
    )
    return a


def _on_surface(a, asset_id, scale, xy, rz=0, rx=0):
    source = mature_asset(asset_id).copy()
    if asset_id == "magnifying_glass_01":
        # The existing GLB declares BLEND but exports its lens with alpha=1
        # and no transmission extension, producing an opaque white disc.
        # Use explicit display transparency only on this placed glass copy;
        # retain the frame maps and do not change the shared source GLB.
        for geometry in source.geometry.values():
            material = geometry.visual.material
            if material.name == "magnifying_glass_01_lense":
                material.baseColorFactor = [231, 242, 240, 35]
                material.alphaMode = "BLEND"
                material.roughnessFactor = 0.08
    if rx:
        source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rx), [1, 0, 0]))
    if rz:
        source.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rz), [0, 0, 1]))
    source.apply_scale(scale)
    source.apply_translation(
        np.asarray([*xy, WORK_TOP]) - np.r_[source.bounds.mean(axis=0)[:2], source.bounds[0, 2]]
    )
    place_scene(a, source, None, source.bounds.mean(axis=0), label=asset_id)


def environment(spec):
    a = Assembly("blocks_environment")
    table = mature_asset("WoodenTable_03").copy()
    table.apply_scale(1.10)
    table.apply_translation(
        np.asarray([0, 0.055, TABLE_TOP]) - np.r_[table.bounds.mean(axis=0)[:2], table.bounds[1, 2]]
    )
    floor_z = table.bounds[0, 2]
    place_scene(a, table, None, table.bounds.mean(axis=0), label="mature_wooden_teaching_table")
    # A thin removable mat supplies the original common 30 mm support datum.
    a.add(
        trimesh.creation.box((1.05, 0.56, 0.002)),
        (98, 110, 110),
        (0, 0.055, 0.029),
        metal=0,
        rough=0.83,
        name="teaching_work_mat",
    )
    textured_box(
        a, (2.5, 2.2, 0.035), (0, 0.055, floor_z - 0.0175), "concrete_floor_worn_001", name="visible_floor"
    )
    _on_surface(a, "binder_notebook", 0.40, (-0.27, 0.255), rz=-8)
    _on_surface(a, "magnifying_glass_01", 0.58, (0.27, 0.24), rz=-28, rx=90)
    a.label(
        "CONSTRUCTION LAB  /  16 mm GRID",
        (0, -0.18, 0.03004),
        0.25,
        0.014,
        (0, 0, 1),
        (98, 110, 110),
        (232, 231, 213),
    )
    return a


def build(spec):
    objects = {}
    for obj in spec.objects:
        if obj.object_id in ("A", "B"):
            objects[obj.object_id] = brick(obj)
        elif obj.object_id == "BASE":
            objects[obj.object_id] = baseplate(obj)
        else:
            raise ValueError(f"Unexpected blocks task object: {obj.object_id}")
    objects["environment"] = environment(spec)
    return objects
