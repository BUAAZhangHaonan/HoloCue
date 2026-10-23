"""Licensed photogrammetry and displaced soil for the archaeology teaching pit.

Task poses, envelopes and anchors remain defined by scene.json. Scan specimens
keep their proportions; no undocumented real-world specimen scale is inferred.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from itertools import pairwise
import json

import numpy as np
import trimesh
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import Delaunay

from holocue.config import root
from holocue.modeling import LIGHT, ORANGE, Assembly, make_object
from holocue.models import SceneSpec
from scripts.scenes.asset_composition import (
    mature_asset,
    place_asset,
    place_scene,
    surface_material,
    textured_box,
)

# These orthonormal frames were checked against both sides in native Blender.
# POT3 +Y is the smoother interior, not the densely incised exterior.
SHERD_FRAME = np.array(
    [
        [-0.8630832939904367, -0.3768989409486612, -0.33620591301521596],
        [0.4659703639894731, -0.33743286010214785, -0.8179307335018062],
        [0.19483030441421414, -0.8626043433898661, 0.4668564010986704],
    ]
)
BONE_FRAME = np.array(
    [
        [-0.16247031039121632, -0.9856889784858393, -0.044951484212697984],
        [0.9665488083196714, -0.14982181343429765, -0.20817498734257536],
        [0.198461077738696, -0.07727005830721952, 0.9770581040613675],
    ]
)


@lru_cache(maxsize=1)
def _stay_fit():
    path = root() / "assets/downloads/dig_reconstruction/stay_fit.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=2)
def _measurement_asset(part):
    """Apply a recorded rigid transform and one uniform scale to a real asset."""
    fit = _stay_fit()[part]
    source = trimesh.load_scene(root() / "assets/downloads/dig_reconstruction" / fit["file"], process=False)
    source.apply_transform(np.asarray(fit["transform"]))
    return source


def _insert_measurement_asset(assembly, part):
    source = _measurement_asset(part)
    for node in source.graph.nodes_geometry:
        transform, key = source.graph[node]
        mesh = source.geometry[key].copy()
        mesh.apply_transform(transform)
        _insert(assembly, mesh, f"{part}_{node}")


def _insert(assembly, mesh, name):
    key = f"{assembly.name}/{assembly.index:04d}_{name}"
    assembly.scene.add_geometry(mesh, node_name=key, geom_name=key)
    assembly.index += 1


def _fit(source, size, frame=None):
    source = source.copy()
    if frame is not None:
        transform = np.eye(4)
        transform[:3, :3] = frame
        source.apply_transform(transform)
    source.apply_translation(-source.bounds.mean(axis=0))
    factor = float(np.min(np.asarray(size) / source.extents))
    source.apply_scale(factor)
    source.metadata["uniform_fit_scale"] = factor
    source.metadata["declared_training_envelope_m"] = list(size)
    return source


@lru_cache(maxsize=2)
def _scan(asset):
    source = trimesh.load_scene(
        root() / "assets/downloads/dig_reconstruction" / f"{asset}.glb", process=False
    )
    for mesh in source.geometry.values():
        material = deepcopy(mesh.visual.material)
        # The archive assigned default metallicity to non-metallic scan albedo.
        material.metallicFactor = 0.0
        material.roughnessFactor = 0.88
        material.alphaMode = "OPAQUE"
        material.doubleSided = True
        mesh.visual.material = material
    return source


def _trowel(size):
    source = mature_asset("trowel_01").copy()
    mesh = source.to_mesh()
    _, axes = np.linalg.eigh(np.cov(mesh.vertices.T))
    transform = np.eye(4)
    transform[:3, :3] = axes[:, [1, 2, 0]].T
    if np.linalg.det(transform[:3, :3]) < 0:
        transform[1, :3] *= -1
    source.apply_transform(transform)
    # An actual convex-hull support facet establishes three physical contact
    # points. This rotates the intact mesh, without flattening blade or handle.
    hull = source.to_mesh().convex_hull
    candidates = np.flatnonzero((hull.face_normals[:, 2] < -0.85) & (hull.area_faces > 0.0001))
    vertices = source.to_mesh().vertices
    best_scale, best_rotation = -1.0, None
    for facet in candidates:
        rotation = trimesh.geometry.align_vectors(hull.face_normals[facet], [0, 0, -1])
        points = trimesh.transform_points(vertices, rotation)
        scale = float(np.min(np.asarray(size) / np.ptp(points, axis=0)))
        if scale > best_scale:
            best_scale, best_rotation = scale, rotation
    if best_rotation is None:
        raise ValueError("The mature trowel has no broad downward support facet")
    source.apply_transform(best_rotation)
    return _fit(source, size)


@lru_cache(maxsize=4)
def _heightmap(texture):
    path = root() / "assets/downloads/polyhaven/textures" / texture / "Displacement_1k.jpg"
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=float) / 255.0


def _height(texture, u, v, tile=2.0):
    values = _heightmap(texture)
    xx = np.floor((np.asarray(u) / tile % 1.0) * values.shape[1]).astype(int)
    yy = np.floor((1.0 - np.asarray(v) / tile % 1.0) * values.shape[0]).astype(int) % values.shape[0]
    return values[yy, xx]


def _grid(assembly, coordinates, uv, shape, texture, name, reverse=False):
    nx, ny = shape
    cells = np.arange(nx * ny).reshape(nx, ny)
    a = cells[:-1, :-1].ravel()
    b = cells[1:, :-1].ravel()
    c = cells[1:, 1:].ravel()
    d = cells[:-1, 1:].ravel()
    faces = np.vstack((np.column_stack((a, b, c)), np.column_stack((a, c, d))))
    if reverse:
        faces = faces[:, ::-1]
    mesh = trimesh.Trimesh(vertices=np.asarray(coordinates).reshape(-1, 3), faces=faces, process=False)
    material = deepcopy(surface_material(texture))
    material.doubleSided = True
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.asarray(uv).reshape(-1, 2), material=material)
    _insert(assembly, mesh, name)


def _ground_height(x, y):
    # Rim geometry has millimetre-scale relief. Deliberately level the actual
    # instrument feet and recording/tool-board footprints, not the whole soil.
    z = -0.006 * (1 - _height("dirt", x, y))
    inner_edge = np.minimum(np.abs(np.abs(x) - 0.70), np.minimum(np.abs(y + 0.50), np.abs(y - 0.90)))
    z *= np.clip(inner_edge / 0.025, 0, 1)
    board = (x < -0.665) & (x > -1.045) & (y > -0.565) & (y < 0.12)
    tray = (x > 0.69) & (x < 1.02) & (y > -0.61) & (y < -0.31)
    z = np.where(board | tray, 0.0, z)
    for fx, fy, _ in _stay_fit()["tripod"]["foot_contacts_world_m"]:
        z *= np.clip((np.hypot(x - fx, y - fy) - 0.040) / 0.018, 0, 1)
    return z


def _floor_height(x, y):
    edge = np.minimum(np.minimum(x + 0.70, 0.70 - x), np.minimum(y + 0.50, 0.90 - y))
    relief = 0.008 * (1 - _height("dirt", x, y)) * np.clip(edge / 0.025, 0, 1)
    mark_distance = np.hypot(x - 0.32, y - 0.02)
    relief *= np.clip((mark_distance - 0.045) / 0.035, 0, 1)
    return -0.35 - relief


def _soil_patch(artifact, pose):
    """Rasterize the real lower surface and feather its soil bed into the pit.

    The scan is unchanged. Dense submillimetre samples preserve real support
    while the surrounding soil falls smoothly over 35 mm, without extruded
    columns or vertical UVs. This patch joins the same floor triangulation.
    """
    mesh = artifact.scene.to_mesh()
    mesh.apply_translation(pose)
    minimum, maximum = mesh.bounds
    xs = np.linspace(
        minimum[0] - 0.04, maximum[0] + 0.04, int(np.ceil((maximum[0] - minimum[0] + 0.08) / 0.00075)) + 1
    )
    ys = np.linspace(
        minimum[1] - 0.04, maximum[1] + 0.04, int(np.ceil((maximum[1] - minimum[1] + 0.08) / 0.00075)) + 1
    )
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    xx, yy = np.meshgrid(xs, ys, indexing="ij")
    surface = np.full(xx.shape, np.inf)
    selected = (mesh.face_normals[:, 2] < -0.15) & (mesh.triangles_center[:, 2] < minimum[2] + 0.010)
    for triangle in mesh.triangles[selected]:
        low, high = triangle.min(axis=0), triangle.max(axis=0)
        i0 = max(0, int(np.ceil((low[0] - xs[0]) / dx)))
        i1 = min(len(xs) - 1, int(np.floor((high[0] - xs[0]) / dx)))
        j0 = max(0, int(np.ceil((low[1] - ys[0]) / dy)))
        j1 = min(len(ys) - 1, int(np.floor((high[1] - ys[0]) / dy)))
        if i0 > i1 or j0 > j1:
            continue
        a, b, c = triangle
        first, second = b - a, c - a
        determinant = first[0] * second[1] - first[1] * second[0]
        if abs(determinant) < 1e-16:
            continue
        qx, qy = xx[i0 : i1 + 1, j0 : j1 + 1] - a[0], yy[i0 : i1 + 1, j0 : j1 + 1] - a[1]
        u = (qx * second[1] - qy * second[0]) / determinant
        v = (first[0] * qy - first[1] * qx) / determinant
        zz = a[2] + u * first[2] + v * second[2]
        inside = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (zz < minimum[2] + 0.009)
        block = surface[i0 : i1 + 1, j0 : j1 + 1]
        np.minimum(block, np.where(inside, zz, np.inf), out=block)
    known = np.isfinite(surface)
    if known.sum() < 3:
        raise ValueError("Scanned artifact has insufficient true underside samples for a soil bed")
    distance, indices = distance_transform_edt(~known, sampling=(dx, dy), return_indices=True)
    nearest = surface[tuple(indices)]
    blend = np.clip(distance / 0.035, 0, 1)
    weight = 1 - blend * blend * (3 - 2 * blend)
    baseline = _floor_height(xx, yy)
    zz = baseline + np.maximum(nearest - baseline, 0) * weight
    return np.column_stack((xx.ravel(), yy.ravel(), zz.ravel()))


def _soil(assembly, objects, specs):
    # A continuous cut, with surface displacement sampled from the existing
    # CC0 soil scan. There are no repeated coloured horizontal wall bands.
    x, y = np.meshgrid(np.linspace(-0.70, 0.70, 121), np.linspace(-0.50, 0.90, 121), indexing="ij")
    floor = np.column_stack((x.ravel(), y.ravel(), _floor_height(x, y).ravel()))
    for object_id in ("POT1", "POT2", "BONE"):
        patch = _soil_patch(objects[object_id], specs[object_id].pose.position_m)
        low, high = patch.min(axis=0), patch.max(axis=0)
        outside = (
            (floor[:, 0] < low[0])
            | (floor[:, 0] > high[0])
            | (floor[:, 1] < low[1])
            | (floor[:, 1] > high[1])
        )
        floor = np.vstack((floor[outside], patch))
    triangles = Delaunay(floor[:, :2]).simplices
    mesh = trimesh.Trimesh(vertices=floor, faces=triangles, process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=floor[:, :2] / 2, material=surface_material("dirt"))
    _insert(assembly, mesh, "pit_floor")
    for side in ("west", "east", "south", "north"):
        u, v = np.meshgrid(np.linspace(0, 1.40, 121), np.linspace(0, 0.35, 43), indexing="ij")
        displacement = 0.017 * (_height("excavated_soil_wall", u, v) - 0.5)
        displacement *= np.sin(np.pi * v / 0.35) * np.sin(np.pi * u / 1.40)
        if side in ("west", "east"):
            xx = np.full_like(u, -0.70 if side == "west" else 0.70) + displacement
            yy = u - 0.50
        else:
            xx = u - 0.70
            yy = np.full_like(u, -0.50 if side == "south" else 0.90) + displacement
        _grid(
            assembly,
            np.stack((xx, yy, v - 0.35), -1),
            np.stack((u, v), -1) / 2,
            u.shape,
            "excavated_soil_wall",
            f"excavation_{side}_wall",
            reverse=side in ("east", "south"),
        )
    for name, xmin, xmax, ymin, ymax in [
        ("west_rim", -1.06, -0.70, -0.72, 1.27),
        ("east_rim", 0.70, 1.09, -0.72, 1.27),
        ("south_rim", -0.70, 0.70, -0.72, -0.50),
        ("north_rim", -0.70, 0.70, 0.90, 1.27),
    ]:
        xx, yy = np.meshgrid(np.linspace(xmin, xmax, 41), np.linspace(ymin, ymax, 91), indexing="ij")
        _grid(
            assembly,
            np.stack((xx, yy, _ground_height(xx, yy)), -1),
            np.stack((xx, yy), -1) / 2,
            xx.shape,
            "dirt",
            name,
        )
    # Outer cut faces close the block under the irregular ground surface.
    for name, x0, y0, x1, y1 in [
        ("west", -1.06, -0.72, -1.06, 1.27),
        ("east", 1.09, -0.72, 1.09, 1.27),
        ("south", -1.06, -0.72, 1.09, -0.72),
        ("north", -1.06, 1.27, 1.09, 1.27),
    ]:
        uu, vv = np.meshgrid(np.linspace(0, 1, 101), np.linspace(0, 1, 31), indexing="ij")
        xx, yy = x0 + uu * (x1 - x0), y0 + uu * (y1 - y0)
        zz = -0.42 + vv * (0.42 + _ground_height(xx, yy))
        _grid(
            assembly,
            np.stack((xx, yy, zz), -1),
            np.stack((uu, zz), -1),
            uu.shape,
            "excavated_soil_wall",
            f"outer_{name}_soil",
            reverse=name in ("east", "south"),
        )
    textured_box(assembly, (2.15, 1.99, 0.04), (0.015, 0.275, -0.40), "dirt", 2, "soil_base")


def _underface_rest(assembly, artifact, pose, base, band, texture, name):
    """A soft soil/cloth rest follows the unmodified lowest scanned underside.

    Each cap is the actual reversed scan triangle, extruded down into the
    supporting bed. No scan vertices, texture or claimed specimen features are
    changed to obtain contact. Only the lowest edge region is supported.
    """
    mesh = artifact.scene.to_mesh()
    mesh.apply_translation(pose)
    lower = mesh.bounds[0, 2]
    selected = (mesh.face_normals[:, 2] < -0.15) & (mesh.triangles_center[:, 2] < lower + band)
    triangles = mesh.triangles[selected][:, ::-1, :]
    # Independent triangular prisms avoid accidental material loss at seams.
    vertices, faces = [], []
    for triangle in triangles:
        if np.min(triangle[:, 2]) <= base:
            continue
        offset = len(vertices)
        bottom = triangle.copy()
        bottom[:, 2] = base
        vertices.extend(triangle)
        vertices.extend(bottom)
        faces.extend(
            np.asarray(
                [[0, 1, 2], [5, 4, 3], [0, 3, 4], [0, 4, 1], [1, 4, 5], [1, 5, 2], [2, 5, 3], [2, 3, 0]]
            )
            + offset
        )
    if not vertices:
        raise ValueError(f"No real underside available for {name}")
    vertices = np.asarray(vertices)
    rest = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    rest.visual = trimesh.visual.TextureVisuals(uv=vertices[:, :2] / 0.20, material=surface_material(texture))
    _insert(assembly, rest, name)


def _fixtures(assembly, objects, specs):
    # A low existing wooden field crate carries the registration pad. This
    # adapts a fixture to the original inspection height, not the specimen.
    place_asset(
        assembly, "wooden_crate_01", (0.31, 0.27, 0.13), (0.85, -0.46, 0.065), label="recording_crate"
    )
    textured_box(assembly, (0.32, 0.28, 0.012), (0.85, -0.46, 0.136), "wood_table_001", 0.5, "recording_tray")
    textured_box(assembly, (0.30, 0.26, 0.008), (0.85, -0.46, 0.146), "hessian_230", 0.20, "recording_pad")
    _underface_rest(
        assembly,
        objects["POT3"],
        specs["POT3"].pose.position_m,
        0.150,
        0.020,
        "hessian_230",
        "POT3_conformal_cradle",
    )
    assembly.label("POT3  /  REGISTERED", (0.85, -0.602, 0.136), 0.26, 0.024)
    textured_box(assembly, (0.36, 0.65, 0.018), (-0.85, -0.22, 0.009), "wood_table_001", 0.5, "tool_board")
    textured_box(
        assembly, (0.33, 0.62, 0.012), (-0.85, -0.22, 0.024), "rubber_tiles", 0.30, "TROWEL_support_mat"
    )
    # The real scan retains telescopic legs, locks, braces and three foot tips.
    # The removed scanner-specific U bracket is replaced by a small adapter.
    _insert_measurement_asset(assembly, "tripod")
    adapter = _stay_fit()["adapter"]
    assembly.cylinder(
        adapter["radius_m"],
        adapter["height_m"],
        adapter["center_world_m"],
        (10, 12, 15),
        name="STAY_tribrach_adapter",
    )
    for x in (-0.80, 0.80):
        for y in (-0.60, 1.0):
            assembly.cylinder(0.009, 0.22, (x, y, 0.03), ORANGE, name="survey_stake")
    corners = [
        (-0.80, -0.60, 0.14),
        (0.80, -0.60, 0.14),
        (0.80, 1.0, 0.14),
        (-0.80, 1.0, 0.14),
        (-0.80, -0.60, 0.14),
    ]
    for a, b in pairwise(corners):
        assembly.rod(a, b, 0.0012, LIGHT, "survey_string")


def build(spec: SceneSpec) -> dict[str, Assembly]:
    specs = {obj.object_id: obj for obj in spec.objects}
    objects = {}
    for obj in spec.objects:
        item = Assembly(obj.object_id)
        if obj.object_id.startswith("POT"):
            source = _fit(_scan("fpan_incised"), obj.size_m, SHERD_FRAME)
            place_scene(item, source, None, (0, 0, 0), label="fpan_photogrammetry_sherd")
            item.scene.metadata.update(source.metadata)
        elif obj.object_id == "BONE":
            source = _fit(_scan("cow_bone"), obj.size_m, BONE_FRAME)
            place_scene(item, source, None, (0, 0, 0), label="cow_bone_photogrammetry")
            item.scene.metadata.update(source.metadata)
        elif obj.object_id == "TROWEL":
            source = _trowel(obj.size_m)
            place_scene(item, source, None, (0, 0, 0), label="polyhaven_trowel_01")
            item.scene.metadata.update(source.metadata)
        elif obj.object_id == "STAY":
            _insert_measurement_asset(item, "station")
            item.scene.metadata.update(_stay_fit()["station"]["metadata"])
        else:
            item = make_object(obj)
        objects[obj.object_id] = item
    environment = Assembly("environment")
    _soil(environment, objects, specs)
    _fixtures(environment, objects, specs)
    objects["environment"] = environment
    return objects
