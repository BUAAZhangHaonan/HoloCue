"""Attributed engine and service parts on a fixed teaching service fixture.

The source assemblies keep uniform proportions. The well, bearings and mounts
adapt the existing HoloCue interfaces; they are not manufacturer fit claims.
"""

from functools import lru_cache

import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, STEEL
from scripts.scenes.asset_composition import mature_asset, textured_box

SOURCE = "assets/downloads/engine_reconstruction"
PLUG_AXIS = np.array([0.0017599985003471375, 0.0, -0.03329598903656006])
PLUG_SCALE = 0.0105 / (0.35948699712753296 - PLUG_AXIS[0])
ENGINE_SCALE = 0.58
ENGINE_OFFSET = np.array([-0.22, 0.29, 0.805 - 0.1345964780292324 * ENGINE_SCALE])
PORT_CENTER = np.array([0.16, 0.26, 1.055])
PLUG_GOAL = np.array([0.16, 0.26, 1.076])
INITIAL_PLUG = np.array([0.27, -0.27, 1.065])
CART_SCALE = 0.82
PALLET_TOP = 0.800


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


def _append(a, scene, prefix):
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        key = f"{a.name}/{a.index:04d}_{prefix}_{node}"
        a.scene.add_geometry(
            scene.geometry[geometry].copy(), node_name=key, geom_name=key, transform=transform
        )
        a.index += 1


def _plain(a, size, center, name, color=(27, 37, 44), metal=0.5, rough=0.50):
    return a.add(trimesh.creation.box(size), color, center, metal=metal, rough=rough, name=name)


def _ring(a, inner, outer, low, high, center, name, axis=(0, 0, 1), color=(75, 86, 96)):
    position = np.asarray(center) + np.asarray(axis) * (low + high) / 2
    return a.add(
        trimesh.creation.annulus(inner, outer, high - low, sections=96),
        color,
        position,
        axis=axis,
        metal=0.72,
        rough=0.42,
        name=name,
    )


@lru_cache(maxsize=1)
def plug_source():
    scene = _source("plug_barbados.glb").copy()
    scene.apply_translation(-PLUG_AXIS)
    scene.apply_scale(PLUG_SCALE)
    # The ceramic source has a metal/roughness map but no scalar metal field.
    # A zero metallic multiplier prevents treating the glazed insulator as metal.
    for node in scene.graph.nodes_geometry:
        _, key = scene.graph[node]
        material = scene.geometry[key].visual.material.copy()
        if node == "Object_2":
            material.metallicFactor = 0.0
            material.roughnessFactor = 0.48
        material.alphaMode = "OPAQUE"
        scene.geometry[key].visual.material = material
    return scene


def plug(obj):
    a = Assembly(obj.object_id)
    _append(a, plug_source(), "mr_barbados_spark_plug")
    return a


def _downward_contact(mesh, maximum_z, bottom):
    """Extrude the genuine bearing face into a thin, closed matching gasket."""
    face_ids = np.flatnonzero((mesh.face_normals[:, 2] < -0.92) & (mesh.triangles_center[:, 2] < maximum_z))
    upper = mesh.submesh([face_ids], append=True, repair=False)
    upper.merge_vertices()
    count = len(upper.vertices)
    vertices = np.vstack([upper.vertices, np.c_[upper.vertices[:, :2], np.full(count, bottom)]])
    top_faces = upper.faces[:, ::-1]
    faces = [*top_faces, *(upper.faces + count)]
    edges = np.sort(np.vstack([top_faces[:, [0, 1]], top_faces[:, [1, 2]], top_faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    for one, two in unique[counts == 1]:
        faces.extend([[one, two, two + count], [one, two + count, one + count]])
    result = trimesh.Trimesh(vertices, faces, process=True)
    result.fix_normals(multibody=True)
    return result


@lru_cache(maxsize=1)
def plug_seat():
    flange = _world_mesh(plug_source(), "Object_3")
    down = np.flatnonzero(flange.face_normals[:, 2] < -0.92)
    # The source's outward seat edge is the true bearing datum. A flat seat
    # touches those distributed edge vertices; the shallow inner bevel stays
    # free, and the 15.2 mm open centre clears the source's thread peaks.
    low = float(flange.triangles[down, :, 2].min())
    seat = trimesh.creation.annulus(0.0076, 0.0108, 0.003, sections=96)
    seat.apply_translation([0, 0, low - 0.0015])
    return seat


def port(obj):
    a = Assembly(obj.object_id)
    seat = plug_seat().copy()
    seat.apply_translation(PLUG_GOAL - PORT_CENTER)
    bottom = float(seat.bounds[0, 2])
    _ring(a, 0.0076, 0.026, -0.032, bottom, (0, 0, 0), "well_lower_open_bore")
    _ring(a, 0.0112, 0.026, bottom, 0.0313, (0, 0, 0), "well_upper_access_wall")
    a.add(seat, (136, 141, 145), metal=0.72, rough=0.40, name="well_measured_flange_seat")
    _ring(a, 0.0112, 0.026, 0.0313, 0.032, (0, 0, 0), "well_visible_top_rim", color=(105, 116, 122))
    return a


@lru_cache(maxsize=1)
def screw_source():
    mesh = _world_mesh(_source("socket_screw.glb"), "Object_2")
    # Area-weighted head underside normals identify the true axis, not the
    # slightly biased vertex PCA direction of the asymmetric helical thread.
    _, axes = np.linalg.eigh(np.cov(mesh.vertices.T))
    approximate = axes[:, -1]
    if approximate[2] > 0:
        approximate = -approximate
    candidates = (mesh.face_normals @ approximate > 0.999) & (mesh.area_faces > 0.3)
    true_axis = np.average(mesh.face_normals[candidates], axis=0, weights=mesh.area_faces[candidates])
    true_axis /= np.linalg.norm(true_axis)
    mesh.apply_transform(trimesh.geometry.align_vectors(true_axis, [-1, 0, 0]))
    # The head is now at +X, with its real underside facing -X.
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    return mesh


def screw_geometry(obj):
    mesh = screw_source().copy()
    mesh.apply_scale(float(obj.size_m[0]) / mesh.extents[0])
    return mesh


def screw(obj):
    a = Assembly(obj.object_id)
    a.add(
        screw_geometry(obj),
        (125, 132, 139),
        metal=0.85,
        rough=0.30,
        name="YouniqueIdeaStudio_complete_socket_screw",
    )
    return a


def screw_bearing(a, obj):
    mesh = screw_geometry(obj)
    centers = mesh.triangles_center
    mask = (mesh.face_normals[:, 0] < -0.999) & (centers[:, 0] > 0)
    # The head shoulder is the largest planar -X facet; its coplanar source
    # triangles make an annular bearing face with the thread left free.
    selected = np.flatnonzero(mask)
    if not len(selected):
        raise ValueError("Mature screw has no actual head underside")
    selected = selected[np.argmax(mesh.area_faces[selected])]
    shoulder = float(centers[selected, 0])
    head_radius = float(np.max(np.linalg.norm(mesh.vertices[:, 1:], axis=1)))
    bore = head_radius * 0.68
    base = shoulder - float(obj.size_m[0]) * 0.53
    position = np.asarray(obj.pose.position_m)
    _ring(
        a,
        bore,
        head_radius * 1.16,
        base,
        shoulder,
        position,
        f"{obj.object_id}_fixed_head_bearing",
        axis=(1, 0, 0),
    )
    return {
        "shoulder_local_x": shoulder,
        "bore_radius": bore,
        "head_radius": head_radius,
        "bearing_low_x": base,
    }


def connector_source():
    original = _source("threaded_connector.glb")
    scene = trimesh.Scene()
    colors = {
        "Object_6": ((35, 45, 53), 0.70, 0.44),
        "Object_7": ((207, 210, 199), 0.0, 0.48),
        "Object_8": ((180, 128, 51), 0.78, 0.30),
    }
    for node in ("Object_6", "Object_7", "Object_8"):
        mesh = _world_mesh(original, node)
        # Keep the entire original female part; the display plinth, male part
        # and loose presentation cable are not components of this object.
        mesh.apply_translation([-0.001985, -0.0034247, 0])
        mesh.apply_scale(0.023)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
        mesh.apply_translation([0, 0.034 - 2.155274271965027 * 0.023, 0])
        color, metal, rough = colors[node]
        mesh.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                name=f"Arrel_{node}_teaching_finish",
                baseColorFactor=[*color, 255],
                metallicFactor=metal,
                roughnessFactor=rough,
                alphaMode="OPAQUE",
                doubleSided=False,
            )
        )
        scene.add_geometry(mesh, node_name=node, geom_name=node)
    return scene


def connector(obj):
    a = Assembly(obj.object_id)
    _append(a, connector_source(), "Arrel_female_connector")
    return a


@lru_cache(maxsize=1)
def oilcap_source():
    mesh = _world_mesh(_source("triple_engine.glb"), "oil cap_Black Plastic_0")
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    mesh.apply_scale(0.032 / mesh.extents[2])
    return mesh


def oilcap(obj):
    a = Assembly(obj.object_id)
    a.add(oilcap_source(), (38, 42, 45), metal=0.0, rough=0.44, name="Jamie_Hamel_Smith_oil_cap")
    a.add(
        trimesh.creation.cylinder(0.011, 0.018, sections=64),
        (14, 18, 20),
        (0, 0, -0.007),
        metal=0,
        rough=0.55,
        name="oilcap_rotating_spindle_adapter",
    )
    return a


def _engine():
    scene = _source("triple_engine.glb").copy()
    scene.apply_scale(ENGINE_SCALE)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
    scene.apply_translation(ENGINE_OFFSET)
    return scene


def _column(a, xy, bottom, top, radius, name, color=(20, 27, 32)):
    a.add(
        trimesh.creation.cylinder(radius, top - bottom, sections=48),
        color,
        (*xy, (bottom + top) / 2),
        metal=0.4,
        rough=0.55,
        name=name,
    )


def _service_hose(a):
    straight = np.c_[np.full(24, -0.30), np.linspace(-0.31, 0.02, 24), np.full(24, 1.065)]
    p0, p1, p2, p3 = [
        np.array(p)
        for p in [(-0.30, 0.02, 1.065), (-0.30, 0.08, 1.065), (-0.36, 0.14, 1.025), (-0.36, 0.22, 1.025)]
    ]
    t = np.linspace(0, 1, 33)[1:, None]
    curve = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t**3 * p3
    points = np.vstack([straight, curve])
    tangents = np.gradient(points, axis=0)
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    radial = np.cross(tangents, [0, 0, 1])
    radial /= np.linalg.norm(radial, axis=1)[:, None]
    other = np.cross(tangents, radial)
    theta = np.arange(64) * 2 * np.pi / 64
    dirs = (
        np.cos(theta)[None, :, None] * radial[:, None, :] + np.sin(theta)[None, :, None] * other[:, None, :]
    )
    outer = (points[:, None, :] + 0.026 * dirs).reshape(-1, 3)
    inner = (points[:, None, :] + 0.021 * dirs).reshape(-1, 3)
    vertices = np.vstack([outer, inner])
    offset = len(outer)
    faces = []
    for row in range(len(points) - 1):
        for col in range(64):
            i = row * 64 + col
            j = row * 64 + (col + 1) % 64
            k = i + 64
            l = j + 64
            faces.extend(
                [
                    [i, j, l],
                    [i, l, k],
                    [i + offset, l + offset, j + offset],
                    [i + offset, k + offset, l + offset],
                ]
            )
    for row in (0, len(points) - 1):
        for col in range(64):
            i = row * 64 + col
            j = row * 64 + (col + 1) % 64
            faces.extend([[i, j, j + offset], [i, j + offset, i + offset]])
    mesh = trimesh.Trimesh(vertices, faces, process=True)
    mesh.fix_normals()
    a.add(mesh, (5, 7, 8), metal=0, rough=0.78, name="hollow_rubber_service_hose")


def environment(spec):
    a = Assembly("environment")
    objects = {o.object_id: o for o in spec.objects}
    textured_box(
        a, (2.8, 2.4, 0.045), (0, 0.22, -0.0225), "hangar_concrete_floor", tile_m=1.6, name="workshop_floor"
    )
    cart = mature_asset("tool_cart").copy()
    cart.apply_scale(CART_SCALE)
    cart.apply_translation(
        np.array([0.0, 0.14, 0.0]) - np.r_[cart.bounds.mean(axis=0)[:2], cart.bounds[0, 2]]
    )
    _append(a, cart, "PolyHaven_tool_cart")
    # A continuous steel service pallet sits above the mature trolley's rails.
    # Its front apron carries the fixed off-engine tasks at their original poses.
    _plain(a, (1.045, 0.865, 0.009), (0, 0.015, PALLET_TOP - 0.0045), "service_pallet", (20, 28, 34), 0.5)
    for x in (-0.38, 0.38):
        _plain(a, (0.025, 0.60, 0.018), (x, 0.03, 0.783), "pallet_crossmember", (29, 38, 43))
    engine = _engine()
    _append(a, engine, "Jamie_Hamel_Smith_generic_triple")
    # Three small machined saddles match actual downward oil-pan triangles.
    # They carry the engine, rather than using its global lowest exhaust point.
    pan = _world_mesh(engine, "oil pan_Engine Gray Rough_0")
    down = np.flatnonzero((pan.face_normals[:, 2] < -0.92) & (pan.area_faces > 0.00004))
    chosen = []
    for index in down[np.argsort(pan.area_faces[down])[::-1]]:
        point = pan.triangles_center[index]
        if all(np.linalg.norm(point[:2] - pan.triangles_center[j, :2]) > 0.045 for j in chosen):
            chosen.append(int(index))
        if len(chosen) == 3:
            break
    for index in chosen:
        patch = pan.submesh([[index]], append=True, repair=False)
        pad = _downward_contact(patch, float(patch.bounds[1, 2]) + 1e-5, PALLET_TOP)
        a.add(pad, (92, 106, 116), metal=0.7, rough=0.44, name="engine_oilpan_matched_saddle")
    # The well is a service sleeve supported below the existing target pose.
    _column(a, PORT_CENTER[:2], PALLET_TOP, PORT_CENTER[2] - 0.032, 0.024, "well_support_column")
    # Initial plug rest bears under the same genuine metal flange as the well.
    seat = plug_seat().copy()
    seat.apply_translation(INITIAL_PLUG)
    low = float(seat.bounds[0, 2])
    _ring(a, 0.0076, 0.016, 1.012, low, INITIAL_PLUG * [1, 1, 0], "initial_plug_open_rest")
    a.add(seat, (136, 141, 145), metal=0.72, rough=0.40, name="initial_plug_measured_flange_seat")
    _column(a, INITIAL_PLUG[:2], PALLET_TOP, 1.012, 0.015, "initial_plug_rest_pedestal")
    _plain(a, (0.115, 0.10, 0.006), (0.27, -0.27, PALLET_TOP + 0.003), "plug_pedestal_base")
    # One real sourced screw rotates inside each fixed, hollow bearing.
    screw_bearing(a, objects["CLAMP"])
    screw_bearing(a, objects["TENSIONER"])
    hose_center = np.array([-0.30, -0.10, 1.065])
    _ring(a, 0.026, 0.0285, -0.007, 0.007, hose_center, "fixed_clamp_band", axis=(0, 1, 0))
    _plain(a, (0.029, 0.013, 0.012), (-0.30, -0.10, 1.088), "clamp_band_screw_saddle", (122, 132, 139))
    _service_hose(a)
    for y in (-0.26, 0.0):
        _column(a, (-0.30, y), PALLET_TOP, 1.039, 0.012, "hose_fixture_standoff")
    _plain(a, (0.035, 0.036, 0.106), (0.38, 0.16, 0.853), "tensioner_fixture_post")
    _plain(a, (0.06, 0.13, 0.008), (0.38, 0.16, PALLET_TOP + 0.004), "tensioner_fixture_foot")
    # Oil-cap inspection/rotation remains on a separate fill-neck adapter.
    cap_bottom = 1.105 + float(oilcap_source().bounds[0, 2])
    _column(a, (-0.13, 0.16), 1.020, cap_bottom, 0.011, "oilcap_neck_adapter", (32, 38, 41))
    _ring(a, 0.0105, 0.020, 1.015, 1.023, (-0.13, 0.16, 0), "oilcap_neck_mount")
    # A shaped cradle supports the original female connector flange from below.
    conn = connector_source()
    flange = _world_mesh(conn, "Object_6")
    conn_bottom = float(flange.bounds[0, 2]) + 1.045
    _plain(a, (0.076, 0.058, 0.004), (0.44, -0.15, conn_bottom - 0.002), "connector_rest_platform")
    _column(a, (0.44, -0.15), PALLET_TOP, conn_bottom - 0.004, 0.022, "connector_rest_post")
    # The connection face remains at +Y; all readable labels stay behind it.
    a.label(
        "SERVICE ENGINE  /  GENERIC TRIPLE",
        (-0.10, -0.4176, 0.785),
        0.44,
        0.038,
        (0, -1, 0),
        (52, 66, 76),
        (229, 235, 232),
    )
    a.label("PLUG", (0.27, -0.286, 0.995), 0.025, 0.010, (0, -1, 0), (59, 72, 80), (231, 235, 227))
    # Useful existing CC0 bench tools, resting horizontally on the service apron.
    wrench = mature_asset("ratchet_wrench").copy()
    wrench.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    wrench.apply_scale(0.75)
    wrench.apply_translation(
        np.array([-0.02, -0.32, PALLET_TOP]) - np.r_[wrench.bounds.mean(axis=0)[:2], wrench.bounds[0, 2]]
    )
    _append(a, wrench, "PolyHaven_ratchet_wrench")
    return a


def build(spec):
    builders = {
        "PLUG": plug,
        "PLUGPORT": port,
        "CLAMP": screw,
        "TENSIONER": screw,
        "CONN": connector,
        "OILCAP": oilcap,
    }
    result = {obj.object_id: builders[obj.object_id](obj) for obj in spec.objects}
    result["environment"] = environment(spec)
    return result
