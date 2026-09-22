"""Consume versioned live frames with native Blender geometry and Gaussian sprites."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[2]
NATIVE_LAYER_LIMIT = 768
sys.path.insert(0, str(ROOT / "src"))
from holocue.versioning import VersionGate


def pose_matrix(pose):
    return Matrix.Translation(Vector(pose["position_m"])) @ Quaternion(pose["wxyz"]).to_matrix().to_4x4()


def make_material():
    material = bpy.data.materials.new("HoloCueGaussianEnvelope")
    material.use_nodes = True
    material.blend_method = "BLEND"
    material.use_screen_refraction = False
    material.diffuse_color = (0.12, 0.80, 0.64, 1.0)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.12, 0.80, 0.64, 1.0)
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(str(ROOT / "assets/ui/gaussian_sprite.png"), check_existing=True)
    vertex = nodes.new("ShaderNodeAttribute")
    vertex.attribute_name = "Opacity"
    multiply = nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    links.new(image.outputs["Alpha"], multiply.inputs[0])
    links.new(vertex.outputs["Fac"], multiply.inputs[1])
    links.new(multiply.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    return material


def descendants(parent):
    yield parent
    for child in parent.children:
        yield from descendants(child)


class Consumer:
    def __init__(self, path):
        self.path = path
        self.material = make_material()
        self.cues = {}
        self.last_stamp = -1.0
        self.scene_id = bpy.context.scene["holocue_scene_id"]
        self.session_id = None
        self.gate = VersionGate()

    def update(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data["scene_id"] != self.scene_id:
            raise ValueError("Blender scene and live frame disagree")
        if data["rgb_encoding"] != "linear_0_1":
            raise ValueError("unsupported live-frame color encoding")
        if time.time() - data["generated_at"] > 3:
            raise TimeoutError("live frame expired")
        if self.session_id is not None and data["session_id"] != self.session_id:
            raise ValueError("live frame session changed")
        if data["generated_at"] < self.last_stamp or not self.gate.admit(data["revision"], data["epoch"]):
            raise ValueError("live frame version regressed")
        self.session_id = data["session_id"]
        if data["generated_at"] == self.last_stamp:
            return data
        scene = bpy.context.scene
        camera = scene.camera
        aspect = float(data["camera"]["aspect"])
        if not 0.1 <= aspect <= 10:
            raise ValueError("live camera aspect is outside the supported range")
        scene.render.resolution_x = 1280
        scene.render.resolution_y = round(1280 / aspect)
        scene.render.resolution_percentage = 100
        # Integer output dimensions must not change the live camera projection.
        # Blender constrains each pixel aspect component to at least one.
        pixel_ratio = aspect * scene.render.resolution_y / scene.render.resolution_x
        scene.render.pixel_aspect_x = max(1.0, pixel_ratio)
        scene.render.pixel_aspect_y = max(1.0, 1.0 / pixel_ratio)
        position = Vector(data["camera"]["position_m"])
        look = Vector(data["camera"]["look_at_m"])
        camera.location = position
        camera.rotation_mode = "QUATERNION"
        forward = np.asarray(look - position, dtype=float)
        forward /= np.linalg.norm(forward)
        up = np.asarray(data["camera"]["up_direction"], float)
        right = np.cross(forward, up)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        camera.rotation_quaternion = Matrix(np.column_stack([right, up, -forward]).tolist()).to_quaternion()
        camera.data.angle_y = data["camera"]["fov_rad"]
        inspection = data["view_mode"] == "inspection"
        for oid, pose in data["object_poses"].items():
            parent = bpy.data.objects["HC_OBJECT_" + oid]
            parent.matrix_world = pose_matrix(pose)
            for child in descendants(parent):
                child.hide_render = inspection and oid != data["selected_id"]
                child.hide_viewport = child.hide_render
        for parent in list(bpy.data.objects):
            if parent.name.startswith("HC_ENV_"):
                for child in descendants(parent):
                    child.hide_render = inspection
                    child.hide_viewport = inspection
        keep = {cue["task_id"] for cue in data["cues"]}
        for tid in list(self.cues):
            if tid not in keep:
                obj = self.cues.pop(tid)
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.meshes.remove(mesh)
        corner = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], float)
        directions = corner[:, 0, None] * right + corner[:, 1, None] * up
        for cue in data["cues"]:
            tid = cue["task_id"]
            count = cue["n_gaussians"]
            center = np.asarray(cue["centers_m"], float)
            radius = np.asarray(cue["radii_m"], float)
            vertices = (center[:, None, :] + radius[:, None, None] * directions).reshape(-1, 3)
            if tid not in self.cues or len(self.cues[tid].data.vertices) != 4 * count:
                if tid in self.cues:
                    obj = self.cues.pop(tid)
                    mesh = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    bpy.data.meshes.remove(mesh)
                mesh = bpy.data.meshes.new("Gaussian_" + tid)
                faces = np.arange(4 * count).reshape(count, 4)
                mesh.from_pydata(vertices.tolist(), [], faces.tolist())
                mesh.update()
                uv = mesh.uv_layers.new(name="EnvelopeUV")
                uv.data.foreach_set("uv", np.tile([0, 0, 1, 0, 1, 1, 0, 1], count))
                mesh.attributes.new(name="Opacity", type="FLOAT", domain="POINT")
                obj = bpy.data.objects.new("HC_CUE_" + tid, mesh)
                scene.collection.objects.link(obj)
                obj.data.materials.append(self.material.copy())
                self.cues[tid] = obj
            obj = self.cues[tid]
            obj.data.vertices.foreach_set("co", vertices.ravel())
            colors = np.repeat(np.asarray(cue["opacities"]), 4)
            obj.data.attributes["Opacity"].data.foreach_set("value", colors)
            cue_color = np.asarray(cue["rgb"], float)
            if (
                cue_color.shape != (3,)
                or not np.isfinite(cue_color).all()
                or np.any((cue_color < 0) | (cue_color > 1))
            ):
                raise ValueError("cue color must contain three normalized linear components")
            obj.data.materials[0].node_tree.nodes["Emission"].inputs["Color"].default_value = (
                *cue_color,
                1.0,
            )
            obj.data.update()
            obj.hide_render = not data["enabled"] or (inspection and cue["target_id"] != data["selected_id"])
            obj.hide_viewport = obj.hide_render
        self.last_stamp = data["generated_at"]
        bpy.context.view_layer.update()
        return data


def verify_consumed(consumer, data):
    scene = bpy.context.scene
    matrices = {
        oid: np.asarray(bpy.data.objects["HC_OBJECT_" + oid].matrix_world, dtype=float)
        for oid in data["object_poses"]
    }
    object_error = max(
        float(np.max(np.abs(matrices[oid] - np.asarray(pose_matrix(pose)))))
        for oid, pose in data["object_poses"].items()
    )
    errors = []
    for cue in data["cues"]:
        mesh = consumer.cues[cue["task_id"]].data
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", coordinates)
        vertices = coordinates.reshape(-1, 4, 3)
        centers = vertices.mean(axis=1)
        radii = np.linalg.norm(vertices[:, 1] - vertices[:, 0], axis=1) / 2
        alpha = np.empty(len(mesh.vertices), dtype=np.float32)
        mesh.attributes["Opacity"].data.foreach_get("value", alpha)
        color = np.asarray(mesh.materials[0].node_tree.nodes["Emission"].inputs["Color"].default_value[:3])
        result = {
            "task_id": cue["task_id"],
            "count": len(vertices),
            "center_error_m": float(np.max(np.abs(centers - np.asarray(cue["centers_m"])))),
            "radius_error_m": float(np.max(np.abs(radii - np.asarray(cue["radii_m"])))),
            "opacity_error": float(np.max(np.abs(alpha[::4] - cue["opacities"]))),
            "color_error": float(np.max(np.abs(color - cue["rgb"]))),
        }
        if (
            max(result[k] for k in ("center_error_m", "radius_error_m", "opacity_error", "color_error"))
            > 2e-5
        ):
            raise AssertionError("Blender Gaussian data differs from the consumed live frame: " + str(result))
        errors.append(result)
    camera_error = float(np.max(np.abs(np.asarray(scene.camera.location) - data["camera"]["position_m"])))
    if max(object_error, camera_error) > 2e-5:
        raise AssertionError("Blender object or camera position differs from the consumed frame")
    expected_forward = np.asarray(data["camera"]["look_at_m"]) - data["camera"]["position_m"]
    expected_forward /= np.linalg.norm(expected_forward)
    expected_right = np.cross(expected_forward, data["camera"]["up_direction"])
    expected_right /= np.linalg.norm(expected_right)
    expected_up = np.cross(expected_right, expected_forward)
    native_forward = np.asarray(scene.camera.rotation_quaternion @ Vector((0.0, 0.0, -1.0)))
    native_up = np.asarray(scene.camera.rotation_quaternion @ Vector((0.0, 1.0, 0.0)))
    forward_error = float(np.max(np.abs(native_forward - expected_forward)))
    up_error = float(np.max(np.abs(native_up - expected_up)))
    fov_error = abs(float(scene.camera.data.angle_y) - data["camera"]["fov_rad"])
    if max(forward_error, up_error, fov_error) > 2e-5:
        raise AssertionError("Native Blender camera forward, up or FOV differs from the consumed frame")
    native_projection = np.asarray(
        scene.camera.calc_matrix_camera(
            bpy.context.evaluated_depsgraph_get(),
            x=scene.render.resolution_x,
            y=scene.render.resolution_y,
            scale_x=scene.render.pixel_aspect_x,
            scale_y=scene.render.pixel_aspect_y,
        ),
        dtype=float,
    )
    expected_y = 1.0 / np.tan(data["camera"]["fov_rad"] / 2.0)
    expected_xy = np.array([expected_y / data["camera"]["aspect"], expected_y])
    native_xy = np.array([native_projection[0, 0], native_projection[1, 1]])
    projection_error = float(np.max(np.abs(native_xy - expected_xy)))
    if projection_error > 2e-5:
        raise AssertionError("Native Blender camera projection differs from the consumed frame")
    return {
        "blender_version": bpy.app.version_string,
        "session_id": data["session_id"],
        "revision": data["revision"],
        "epoch": data["epoch"],
        "camera_error_m": camera_error,
        "camera_forward_error": forward_error,
        "camera_up_error": up_error,
        "camera_fov_error_rad": fov_error,
        "camera_projection_xy_error": projection_error,
        "camera_projection_xy_expected": expected_xy.tolist(),
        "camera_projection_matrix": native_projection.tolist(),
        "camera_projection_aspect": float(native_xy[1] / native_xy[0]),
        "camera_projection_comparison": "XY coefficients; depth conventions are engine-specific",
        "render_resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "render_pixel_aspect": [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
        "camera_native_forward": native_forward.tolist(),
        "camera_native_up": native_up.tolist(),
        "camera_fov_rad": scene.camera.data.angle_y,
        "object_matrix_error": object_error,
        "object_matrices": {k: v.tolist() for k, v in matrices.items()},
        "cues": errors,
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_native_capture(directory):
    """Read actual native EXRs to diagnose color/alpha; never modify their pixels."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    report = {"manifest_sha256": digest(directory / "manifest.json"), "passes": []}
    for layer in manifest["passes"]:
        path = Path(layer["path"])
        image = bpy.data.images.load(str(path), check_existing=False)
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        pixels = pixels.reshape(-1, 4)
        alpha = pixels[:, 3]
        rgb = pixels[:, :3]
        colors = list(layer["material_colors"].values())
        record = {
            "path": str(path),
            "sha256": digest(path),
            "size": list(image.size),
            "alpha_mode": image.alpha_mode,
            "color_space": image.colorspace_settings.name,
            "alpha_min": float(alpha.min()),
            "alpha_max": float(alpha.max()),
            "nonzero_alpha_pixels": int((alpha > 1e-6).sum()),
            "positive_alpha_black_rgb_pixels": int(((alpha > 0.01) & (np.max(rgb, axis=1) < 1e-5)).sum()),
            "thresholds": [],
        }
        for threshold in (0.001, 0.01, 0.1, 0.5):
            mask = alpha > threshold
            if not mask.any():
                continue
            unpremult = rgb[mask] / alpha[mask, None]
            row = {
                "alpha_greater_than": threshold,
                "count": int(mask.sum()),
                "unpremult_rgb_quantiles": np.quantile(
                    unpremult, [0, 0.01, 0.1, 0.5, 0.9, 0.99, 1], axis=0
                ).tolist(),
            }
            if all(color == colors[0] for color in colors):
                expected = np.asarray(colors[0][:3])
                row["expected_emission_rgb"] = expected.tolist()
                row["mean_abs_error"] = np.abs(unpremult - expected).mean(axis=0).tolist()
                residual = rgb - alpha[:, None] * expected
                row["premult_residual_quantiles"] = np.quantile(
                    residual[mask], [0, 0.01, 0.5, 0.99, 1], axis=0
                ).tolist()
            record["thresholds"].append(row)
        report["passes"].append(record)
        bpy.data.images.remove(image)
    output = directory / "native_rgba_diagnostic.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Native EXR diagnostic written:", output, flush=True)
    return report


def native_layer_plan(consumer, data):
    """Read the verified native meshes and order parallel sprites back to front."""
    scene = bpy.context.scene
    forward = np.asarray(scene.camera.rotation_quaternion @ Vector((0.0, 0.0, -1.0)), dtype=float)
    camera = np.asarray(scene.camera.location, dtype=float)
    sources = {}
    ordered = []
    hidden = []
    for cue in data["cues"]:
        tid = cue["task_id"]
        obj = consumer.cues[tid]
        mesh = obj.data
        count = len(mesh.polygons)
        vertices = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", vertices)
        vertices = vertices.reshape(count, 4, 3)
        opacity = np.empty(len(mesh.vertices), dtype=np.float32)
        mesh.attributes["Opacity"].data.foreach_get("value", opacity)
        sources[tid] = {
            "vertices": vertices,
            "opacity": opacity.reshape(count, 4),
            "material": mesh.materials[0],
        }
        if obj.hide_render:
            hidden.append({"task_id": tid, "count": count, "reason": "live visibility contract"})
            continue
        depth = (vertices - camera) @ forward
        if np.max(np.ptp(depth, axis=1), initial=0.0) > 2e-5:
            raise AssertionError("Sprites are not camera parallel; whole-quad depth ordering is invalid")
        ordered.extend(
            {"task_id": tid, "gaussian_index": index, "camera_depth_m": float(depth[index].mean())}
            for index in range(count)
        )
    ordered.sort(key=lambda row: (-row["camera_depth_m"], row["task_id"], row["gaussian_index"]))
    return sources, ordered, hidden


def native_chunk(sources, members, index):
    """Copy exact verified vertices/float opacity into one bounded native mesh."""
    vertices = np.stack([sources[row["task_id"]]["vertices"][row["gaussian_index"]] for row in members])
    opacity = np.stack([sources[row["task_id"]]["opacity"][row["gaussian_index"]] for row in members])
    count = len(members)
    if not 0 < count <= NATIVE_LAYER_LIMIT:
        raise AssertionError("Native Gaussian pass exceeds the transparent-ray safety bound")
    mesh = bpy.data.meshes.new(f"GaussianLayer_{index:04d}")
    mesh.from_pydata(vertices.reshape(-1, 3).tolist(), [], np.arange(count * 4).reshape(-1, 4).tolist())
    uv = mesh.uv_layers.new(name="EnvelopeUV")
    uv.data.foreach_set("uv", np.tile([0, 0, 1, 0, 1, 1, 0, 1], count))
    mesh.attributes.new(name="Opacity", type="FLOAT", domain="POINT")
    mesh.attributes["Opacity"].data.foreach_set("value", opacity.ravel())
    materials = {}
    for row, polygon in zip(members, mesh.polygons):
        tid = row["task_id"]
        if tid not in materials:
            materials[tid] = len(mesh.materials)
            mesh.materials.append(sources[tid]["material"])
        polygon.material_index = materials[tid]
    mesh.update()
    actual_vertices = np.empty(vertices.size, dtype=np.float32)
    actual_opacity = np.empty(opacity.size, dtype=np.float32)
    mesh.vertices.foreach_get("co", actual_vertices)
    mesh.attributes["Opacity"].data.foreach_get("value", actual_opacity)
    if not np.array_equal(actual_vertices, vertices.ravel()) or not np.array_equal(
        actual_opacity, opacity.ravel()
    ):
        raise AssertionError("Native capture chunk changed verified geometry or opacity")
    obj = bpy.data.objects.new(f"HC_CAPTURE_LAYER_{index:04d}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    evidence = {
        "count": count,
        "members": members,
        "vertices_float32_sha256": hashlib.sha256(actual_vertices.tobytes()).hexdigest(),
        "opacity_float32_sha256": hashlib.sha256(actual_opacity.tobytes()).hexdigest(),
        "material_colors": {
            tid: list(sources[tid]["material"].node_tree.nodes["Emission"].inputs["Color"].default_value)
            for tid in materials
        },
    }
    return obj, evidence


def coplanar_conflict_groups(vertices, depths, right, up):
    """Partition exact native quads without changing any vertex or attribute.

    Camera-parallel quads are rectangles in camera-plane coordinates. Positive
    rectangle overlap at indistinguishable float32 depth is a native-ray
    conflict. The tolerance covers four float32 ULPs at this geometry's scale;
    it changes only grouping, never the geometry or rendered parameters.
    """
    xy = np.stack((vertices @ right, vertices @ up), axis=-1)
    lo = xy.min(axis=1)
    hi = xy.max(axis=1)
    scale = max(float(np.abs(vertices).max()), float(np.abs(depths).max()), float(np.finfo(np.float32).tiny))
    tolerance = float(4 * np.spacing(np.float32(scale)))
    count = len(vertices)
    conflict = np.empty((count, count), dtype=bool)
    for index in range(count):
        conflict[index] = (
            (np.abs(depths - depths[index]) <= tolerance)
            & (lo[index, 0] < hi[:, 0])
            & (hi[index, 0] > lo[:, 0])
            & (lo[index, 1] < hi[:, 1])
            & (hi[index, 1] > lo[:, 1])
        )
    np.fill_diagonal(conflict, False)
    degree = conflict.sum(axis=1)
    if degree.any():
        colors = np.full(count, -1, dtype=int)
        sizes = []
        for index in np.argsort(-degree, kind="stable"):
            blocked = set(colors[conflict[index]].tolist())
            color = next(
                (k for k, size in enumerate(sizes) if k not in blocked and size < NATIVE_LAYER_LIMIT),
                len(sizes),
            )
            if color == len(sizes):
                sizes.append(0)
            colors[index] = color
            sizes[color] += 1
        groups = [np.flatnonzero(colors == color) for color in range(len(sizes))]
        method = "largest-degree-first coloring of coplanar screen-rectangle conflicts"
    else:
        stride = (count + NATIVE_LAYER_LIMIT - 1) // NATIVE_LAYER_LIMIT
        groups = [np.arange(phase, count, stride) for phase in range(stride)]
        method = "depth interleaving; no coplanar screen-rectangle conflicts"
    for indices in groups:
        if len(indices) > NATIVE_LAYER_LIMIT or conflict[np.ix_(indices, indices)].any():
            raise AssertionError("Native pass contains overlapping coplanar quads or exceeds its limit")
    if sorted(index for indices in groups for index in indices) != list(range(count)):
        raise AssertionError("Coplanar grouping omitted or duplicated native quads")
    return groups, {
        "grouping_method": method,
        "coplanar_depth_tolerance_m": tolerance,
        "coplanar_conflict_edges": int(degree.sum() // 2),
        "coplanar_conflict_max_degree": int(degree.max()),
        "color_run_quad_count": count,
        "color_run_pass_count": len(groups),
        "coplanar_overlap_free_verified": True,
        "screen_rectangle_bounds_sha256": hashlib.sha256(np.stack((lo, hi)).tobytes()).hexdigest(),
    }


def native_pass_groups(sources, ordered):
    """Separate adjacent planes without reordering distinct emission colors.

    Premultiplied layers of identical RGB commute exactly under AlphaOver.
    Coplanar overlapping quads occupy distinct native passes. Runs without
    conflicts retain depth interleaving. Distinct color runs keep depth order.
    """

    def color(row):
        return tuple(
            sources[row["task_id"]]["material"].node_tree.nodes["Emission"].inputs["Color"].default_value[:3]
        )

    camera = bpy.context.scene.camera
    right = np.asarray(camera.rotation_quaternion @ Vector((1.0, 0.0, 0.0)), dtype=float)
    up = np.asarray(camera.rotation_quaternion @ Vector((0.0, 1.0, 0.0)), dtype=float)
    groups = []
    start = 0
    run_index = 0
    while start < len(ordered):
        end = start + 1
        rgb = color(ordered[start])
        while end < len(ordered) and color(ordered[end]) == rgb:
            end += 1
        run = ordered[start:end]
        vertices = np.stack([sources[row["task_id"]]["vertices"][row["gaussian_index"]] for row in run])
        depths = np.asarray([row["camera_depth_m"] for row in run])
        indices, evidence = coplanar_conflict_groups(vertices, depths, right, up)
        for phase, selected in enumerate(indices):
            groups.append(
                (
                    [run[index] for index in selected],
                    {
                        "color_run": run_index,
                        "emission_rgb": list(rgb),
                        "color_run_pass_index": phase,
                        **evidence,
                    },
                )
            )
        start = end
        run_index += 1
    flattened = [(row["task_id"], row["gaussian_index"]) for members, _ in groups for row in members]
    expected = [(row["task_id"], row["gaussian_index"]) for row in ordered]
    if len(flattened) != len(expected) or set(flattened) != set(expected):
        raise AssertionError("Native depth grouping changed the visible Gaussian membership")
    return groups


def render_linear(path):
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not path.is_file():
        raise RuntimeError("Native Blender render did not write " + str(path))
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def save_native_png(path):
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    bpy.data.images["Render Result"].save_render(str(path), scene=scene)
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def capture_layered(consumer, data, destination, index):
    """Native Cycles holdout passes and native AlphaOver, without raster synthesis.

    Every sprite is a plane parallel to the camera. Distinct color runs retain
    their global far-to-near order; equal-color layers commute and use coplanar
    conflict groups, or depth interleaving where no coplanar overlap exists.
    The compositor receives premultiplied scene-linear 32-bit EXR renders. The
    compositor loads at most 16 cue layers plus one linear accumulator at once.
    The view transform is applied once when its final result is saved to PNG.
    """
    scene = bpy.context.scene
    if scene.render.engine != "CYCLES" or scene.cycles.samples != 48:
        raise ValueError("Layered bridge requires the native Cycles 48-sample scene")
    if scene.cycles.transparent_max_bounces <= NATIVE_LAYER_LIMIT:
        raise ValueError("Native transparency depth must exceed the bounded sprite count")
    directory = destination / f"frame_{index:04d}_passes"
    directory.mkdir(parents=True, exist_ok=False)
    sources, ordered, hidden = native_layer_plan(consumer, data)
    groups = native_pass_groups(sources, ordered)
    all_cues = list(consumer.cues.values())
    cue_names = {obj.name for obj in all_cues}
    geometry = [
        obj
        for obj in scene.objects
        if obj.name not in cue_names and obj.type in ("MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME")
    ]
    visibility = {obj.name: obj.hide_render for obj in all_cues}
    holdouts = {obj.name: obj.is_holdout for obj in geometry}
    old_transparent = scene.render.film_transparent
    old_compositing = scene.render.use_compositing
    old_min_transparent = scene.cycles.min_transparent_bounces
    old_denoising = scene.cycles.use_denoising
    loaded_images = []
    current_chunk = None
    manifest = {
        "method": "native Cycles bounded Gaussian passes with native compositor AlphaOver",
        "chunk_limit": NATIVE_LAYER_LIMIT,
        "samples": scene.cycles.samples,
        "transparent_max_bounces": scene.cycles.transparent_max_bounces,
        "base_min_transparent_bounces": old_min_transparent,
        "cue_min_transparent_bounces": NATIVE_LAYER_LIMIT,
        "base_denoising": old_denoising,
        "cue_denoising": False,
        "render_engine": scene.render.engine,
        "render_device": scene.cycles.device,
        "color_encoding": "scene-linear float32 RGBA, premultiplied alpha",
        "ordering": "far-to-near color runs; coplanar conflict coloring within equal-RGB runs, otherwise depth interleaving",
        "planned_pass_count": len(groups),
        "all_passes_coplanar_overlap_free_verified": all(
            group[1]["coplanar_overlap_free_verified"] for group in groups
        ),
        "compositor_batch_layer_limit": 16,
        "compositor_max_loaded_input_images": 17,
        "compositor_max_input_rgba_float32_bytes": 17
        * scene.render.resolution_x
        * scene.render.resolution_y
        * 16,
        "compositor_batches": [],
        "same_color_order_proof": "For identical RGB c, over gives c*(a+b-a*b) and a+b-a*b in either order.",
        "total_native_gaussians": sum(cue["n_gaussians"] for cue in data["cues"]),
        "visible_gaussians": len(ordered),
        "hidden_cues": hidden,
        "ordered_members_sha256": hashlib.sha256(json.dumps(ordered, sort_keys=True).encode()).hexdigest(),
        "holdout_geometry": [obj.name for obj in geometry if not obj.hide_render],
        "camera_matrix": np.asarray(scene.camera.matrix_world).tolist(),
        "camera_fov_rad": scene.camera.data.angle_y,
        "view_transform": scene.view_settings.view_transform,
        "view_look": scene.view_settings.look,
        "passes": [],
        "complete": False,
    }
    manifest_path = directory / "manifest.json"

    def record():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    record()
    try:
        scene.render.use_compositing = False
        for obj in all_cues:
            obj.hide_render = True
        bpy.context.view_layer.update()
        manifest["base"] = render_linear(directory / "base.exr")
        manifest["base_png"] = save_native_png(directory / "base.png")
        record()
        scene.render.film_transparent = True
        # With zero minimum bounces Cycles may terminate low-throughput
        # transparent paths before evaluating their emitted color. The native
        # alpha can then attenuate the background without corresponding RGB.
        # Every pass has at most this many planes, so disable that early path
        # termination for the complete bounded path, without changing its alpha.
        scene.cycles.min_transparent_bounces = NATIVE_LAYER_LIMIT
        if scene.cycles.min_transparent_bounces != NATIVE_LAYER_LIMIT:
            raise RuntimeError("Blender clamped the required minimum transparent path length")
        # Keep native color and alpha from the same samples. Denoising just RGB
        # against unfiltered transparency can create dark compositing fringes.
        scene.cycles.use_denoising = False
        for obj in geometry:
            obj.is_holdout = True
        for chunk_index, (members, group_evidence) in enumerate(groups):
            current_chunk, evidence = native_chunk(sources, members, chunk_index)
            evidence.update(group_evidence)
            bpy.context.view_layer.update()
            evidence.update(render_linear(directory / f"gaussians_{chunk_index:04d}.exr"))
            manifest["passes"].append(evidence)
            record()
            mesh = current_chunk.data
            bpy.data.objects.remove(current_chunk, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            current_chunk = None
        if sum(row["count"] for row in manifest["passes"]) != len(ordered):
            raise AssertionError("Native render passes omitted visible Gaussians")
        for obj in geometry:
            obj.is_holdout = holdouts[obj.name]
        scene.render.film_transparent = old_transparent
        scene.cycles.min_transparent_bounces = old_min_transparent
        scene.cycles.use_denoising = old_denoising
        bpy.context.view_layer.update()
        scene.use_nodes = True
        nodes = scene.node_tree.nodes
        links = scene.node_tree.links
        nodes.clear()

        def image_node(path):
            image = bpy.data.images.load(str(path), check_existing=False)
            image.colorspace_settings.name = "Linear"
            image.alpha_mode = "PREMUL"
            loaded_images.append(image)
            node = nodes.new("CompositorNodeImage")
            node.image = image
            return node.outputs["Image"]

        scene.render.use_compositing = True
        accumulator = directory / "base.exr"
        layers = manifest["passes"]
        batch_starts = range(0, len(layers), 16) if layers else [0]
        for batch_index, start in enumerate(batch_starts):
            batch = layers[start : start + 16]
            result = image_node(accumulator)
            for layer in batch:
                over = nodes.new("CompositorNodeAlphaOver")
                over.inputs[0].default_value = 1.0
                over.use_premultiply = False
                over.premul = 0.0
                links.new(result, over.inputs[1])
                links.new(image_node(Path(layer["path"])), over.inputs[2])
                result = over.outputs["Image"]
            composite = nodes.new("CompositorNodeComposite")
            links.new(result, composite.inputs["Image"])
            final = start + len(batch) >= len(layers)
            output = (
                destination / f"frame_{index:04d}.exr"
                if final
                else directory / f"composite_batch_{batch_index:04d}.exr"
            )
            if len(loaded_images) > 17:
                raise AssertionError("Native compositor exceeded its bounded image batch")
            result_file = render_linear(output)
            manifest["compositor_batches"].append(
                {
                    "index": batch_index,
                    "input_accumulator": str(accumulator),
                    "input_accumulator_sha256": digest(accumulator),
                    "layer_paths": [row["path"] for row in batch],
                    "loaded_input_images": len(loaded_images),
                    "output": result_file,
                }
            )
            # Keep every native intermediate EXR as evidence, but release the
            # source images and compositor buffers before loading the next batch.
            nodes.clear()
            for image in loaded_images:
                bpy.data.images.remove(image)
            loaded_images.clear()
            accumulator = output
            record()
        manifest["composite_exr"] = result_file
        manifest["composite_png"] = save_native_png(destination / f"frame_{index:04d}.png")
        manifest["complete"] = True
        record()
    finally:
        if current_chunk is not None:
            mesh = current_chunk.data
            bpy.data.objects.remove(current_chunk, do_unlink=True)
            bpy.data.meshes.remove(mesh)
        for obj in all_cues:
            obj.hide_render = visibility[obj.name]
        for obj in geometry:
            obj.is_holdout = holdouts[obj.name]
        scene.render.film_transparent = old_transparent
        scene.render.use_compositing = old_compositing
        scene.cycles.min_transparent_bounces = old_min_transparent
        scene.cycles.use_denoising = old_denoising
        if scene.use_nodes:
            scene.node_tree.nodes.clear()
        for image in loaded_images:
            bpy.data.images.remove(image)
        bpy.context.view_layer.update()
    # The original whole consumer meshes were never split, scaled or resampled.
    verify_consumed(consumer, data)
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": digest(manifest_path),
        "visible_gaussians": len(ordered),
        "native_pass_count": len(manifest["passes"]),
        "full_native_geometry_unchanged": True,
        "composite_exr": manifest["composite_exr"],
        "composite_png": manifest["composite_png"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame-file", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--device", choices=["CPU", "CUDA"], default="CPU")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    temp = Path(os.environ["TMPDIR"]).resolve()
    if not temp.is_relative_to(ROOT):
        raise ValueError("TMPDIR must be inside the project")
    bpy.context.preferences.filepaths.temporary_directory = str(temp)
    scene = bpy.context.scene
    # Native pass geometry is bounded to 768 camera-parallel quads. Configure
    # the supported depth once; verification only reads the consumed scene.
    scene.cycles.transparent_max_bounces = 1024
    device_record = {
        "device": args.device,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
    }
    if args.device == "CUDA":
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if not visible.startswith("GPU-") or "," in visible:
            raise ValueError("CUDA bridge requires one guard-selected GPU UUID")
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "CUDA"
        preferences.get_devices()
        selected = [item for item in preferences.devices if item.type == "CUDA"]
        if len(selected) != 1:
            raise RuntimeError("Expected exactly one authorized CUDA render device")
        for item in preferences.devices:
            item.use = item.type == "CUDA"
        scene.cycles.device = "GPU"
        device_record["devices"] = [
            {"id": item.id, "name": item.name, "type": item.type, "use": item.use}
            for item in preferences.devices
        ]
    else:
        scene.cycles.device = "CPU"
    consumer = Consumer(args.frame_file)
    if args.capture:
        args.capture.mkdir(parents=True, exist_ok=True)
        for index in range(args.frames):
            data = consumer.update()
            verification = verify_consumed(consumer, data)
            verification["render_device"] = device_record
            (args.capture / f"consumed_frame_{index:04d}.json").write_text(
                json.dumps(data, ensure_ascii=False)
            )
            verification["layered_capture"] = capture_layered(consumer, data, args.capture, index)
            verification["generated_at"] = data["generated_at"]
            (args.capture / f"frame_{index:04d}.json").write_text(json.dumps(verification, indent=2))
        return

    def tick():
        consumer.update()
        return 0.1

    bpy.app.timers.register(tick, first_interval=0.1, persistent=True)


if __name__ == "__main__":
    main()
