"""Licensed medical models adapted to the unchanged isolated teaching interfaces."""

from functools import lru_cache

import cadquery as cq
import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, cad_mesh
from scripts.scenes.asset_composition import textured_box

SOURCE = "assets/downloads/infusion_reconstruction"
PUMP_SCALE = 0.46
PUMP_CENTER = np.array([0.03723799902945757, 0.0, 0.03684599883854389])
BAG_SCALE = 0.36646792525809857
CART_TOP = 0.940
BAG_EYE_Z = 0.100
WHITE = (207, 217, 221)
BLUE = (50, 114, 144)
STEEL = (139, 155, 166)


@lru_cache(maxsize=10)
def _source(name):
    s = trimesh.load_scene(root() / SOURCE / (name + ".glb"), process=False)
    s.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return s


def _mesh(source, node):
    tf, key = source.graph[node]
    m = source.geometry[key].copy()
    m.apply_transform(tf)
    return m


def _components(m):
    q = m.copy()
    q.merge_vertices(merge_tex=True, merge_norm=True)
    groups = trimesh.graph.connected_components(q.face_adjacency, nodes=np.arange(len(q.faces)), min_len=1)
    return [m.submesh([f], append=True, repair=False) for f in groups]


def _put(a, mesh, name):
    key = f"{a.name}/{name}"
    a.scene.add_geometry(mesh.copy(), node_name=key, geom_name=key)
    a.index += 1


def _append(a, scene, prefix):
    for node in scene.graph.nodes_geometry:
        _put(a, _mesh(scene, node), f"{prefix}_{node}")


def _plain(a, size, center, name, color=WHITE, metal=0.0, rough=0.52):
    return a.add(trimesh.creation.box(size), color, center, metal=metal, rough=rough, name=name)


def _label(
    a, name, text, center, width, height, normal=(0, -1, 0), background=(232, 239, 237), ink=(29, 64, 73)
):
    tmp = Assembly("label")
    tmp.label(text, center, width, height, normal, background, ink)
    _put(a, next(iter(tmp.scene.geometry.values())), "label_" + name)


def _ray(mesh, origin, direction):
    """Exact triangle-ray intersections, independent of optional spatial indexes."""
    tri = mesh.triangles
    d = np.asarray(direction, float)
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    h = np.cross(np.broadcast_to(d, e2.shape), e2)
    det = np.einsum("ij,ij->i", e1, h)
    valid = np.abs(det) > 1e-12
    inv = np.zeros(len(det))
    inv[valid] = 1 / det[valid]
    s = np.asarray(origin) - tri[:, 0]
    u = inv * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    v = inv * (q @ d)
    t = inv * np.einsum("ij,ij->i", e2, q)
    good = valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) & (t >= 0)
    ids = np.flatnonzero(good)
    if not len(ids):
        return None
    i = ids[np.argmin(t[ids])]
    return np.asarray(origin) + d * t[i], int(i)


@lru_cache(maxsize=1)
def bag_source():
    m = _mesh(_source("iv_supplies"), "WaterBag_All_Tools_0")
    m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(4.5), [0, 1, 0]))
    m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 0, 1]))
    m.apply_scale(BAG_SCALE)
    m.apply_translation(-m.bounds.mean(axis=0) + np.array([0, 0, -0.010]))
    mat = m.visual.material.copy()
    mat.metallicFactor = 0.0
    mat.roughnessFactor = 0.50
    # Retain the source's alpha-bearing film texture, including its printed marks.
    mat.alphaMode = "BLEND"
    mat.doubleSided = True
    m.visual.material = mat
    return m


def bag(obj):
    a = Assembly(obj.object_id)
    m = bag_source().copy()
    _put(a, m, "ethan_cragun_water_bag")
    # A removable teaching hanger reinforces the source's closed seal. It adds
    # a real open eye; the downloaded bag has no modeled hanging perforation.
    tab = cq.Workplane("XY").box(0.025, 0.003, 0.045).edges("|Y").fillet(0.004).translate((0, 0, 0.0875))
    hole = cq.Solid.makeCylinder(0.0045, 0.005, cq.Vector(0, -0.0025, BAG_EYE_Z), cq.Vector(0, 1, 0))
    a.add(
        cad_mesh(tab.cut(cq.Workplane().newObject([hole]))),
        WHITE,
        rough=0.48,
        name="open_hanger_eye_and_reinforced_seal_clip",
    )
    # The opaque teaching label follows the actual folded bag surface. It does
    # not float on the old rectangular envelope or replace the bag geometry.
    tmp = Assembly("decal")
    tmp.label(
        f"TRAINING {'A' if obj.object_id == 'BAG1' else 'B'}\nSIMULATION ONLY\nID {obj.object_id}",
        (0, 0, 0),
        0.061,
        0.055,
        normal=(0, 1, 0),
        background=(240, 243, 235),
        ink=(0, 0, 0),
    )
    material = next(iter(tmp.scene.geometry.values())).visual.material.copy()
    material.roughnessFactor = 1.0
    # Clip the actual outer sheet triangles. A regular projected grid can
    # bridge across a source fold and put its triangle interiors inside the
    # transparent film even though every grid vertex lies on the surface.
    points, faces = [], []
    for triangle in m.triangles:
        polygon = list(triangle)
        for axis, bound, sign in ((0, -0.0305, 1), (0, 0.0305, -1), (2, -0.0275, 1), (2, 0.0275, -1)):
            clipped = []
            for one, two in zip(polygon, polygon[1:] + polygon[:1]):
                d1, d2 = sign * (one[axis] - bound), sign * (two[axis] - bound)
                if d1 >= 0:
                    clipped.append(one)
                if (d1 >= 0) != (d2 >= 0):
                    clipped.append(one + (two - one) * d1 / (d1 - d2))
            polygon = clipped
            if len(polygon) < 3:
                break
        if len(polygon) < 3:
            continue
        polygon = np.asarray(polygon)
        normal_y = np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0])[1]
        if abs(normal_y) < 1e-12:
            continue
        center = polygon.mean(axis=0)
        hit = _ray(m, [center[0], 0.04, center[2]], [0, -1, 0])
        if hit is None or abs(hit[0][1] - center[1]) > 1e-8:
            continue
        if normal_y < 0:
            polygon = polygon[::-1]
        start = len(points)
        points.extend(polygon)
        faces.extend([[start, start + i, start + i + 1] for i in range(1, len(polygon) - 1)])
    points = np.asarray(points)
    triangles = points[np.asarray(faces)]
    coverage = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])[:, 1].sum() / 2
    if not np.isclose(coverage, 0.061 * 0.055, atol=1e-9):
        raise ValueError("outer bag sheet does not cover the complete training label")
    uv = np.column_stack([1 - (points[:, 0] + 0.0305) / 0.061, (points[:, 2] + 0.0275) / 0.055])
    points[:, 1] += 0.00006
    decal = trimesh.Trimesh(
        points, faces, process=False, visual=trimesh.visual.TextureVisuals(uv=uv, material=material)
    )
    _put(a, decal, f"label_training_serial_label_{obj.object_id}")
    return a


def _pump_transform(m):
    m.apply_translation(-PUMP_CENTER)
    m.apply_scale(PUMP_SCALE)
    m.apply_translation([0, -0.032 + 0.06164199858903885 * PUMP_SCALE, 0])
    return m


def cassette(obj):
    a = Assembly(obj.object_id)
    door = _components(_mesh(_source("contec_pump"), "Object_10"))[1]
    door.apply_translation(-door.bounds.mean(axis=0))
    door.apply_scale(PUMP_SCALE)
    door.apply_translation([0, -0.0235 - door.bounds[0, 1], 0])
    a.add(door, WHITE, rough=0.47, name="contec750_source_door_uniform")
    latch = _components(_mesh(_source("contec_pump"), "Object_5"))[1]
    latch.apply_translation(-PUMP_CENTER)
    latch.apply_scale(PUMP_SCALE)
    latch.apply_translation([0, -0.0235 - (-0.06075799837708473 * PUMP_SCALE), 0])
    a.add(latch, BLUE, rough=0.45, name="contec750_source_door_latch")
    for x in (-0.010, 0.010):
        for z in (-0.028, 0.028):
            hit = _ray(door, [x, 0.02, z], [0, -1, 0])
            if hit is None:
                raise ValueError("source door rear fastening point missing")
            y = hit[0][1]
            a.add(
                trimesh.creation.cylinder(0.002, 0.017 - y, sections=32),
                WHITE,
                (x, (y + 0.017) / 2, z),
                axis=(0, 1, 0),
                name="door_to_carrier_standoff",
            )
    # Explicit training carrier behind the mature door; solid side spars and
    # an open central flow-path window, not a scaled complete clinical pump.
    _plain(a, (0.038, 0.043, 0.003), (0, -0.0025, -0.046), "cassette_bearing_bottom", BLUE)
    _plain(a, (0.038, 0.043, 0.003), (0, -0.0025, 0.046), "cassette_top", BLUE)
    for x in (-0.0175, 0.0175):
        _plain(a, (0.003, 0.030, 0.089), (x, 0.005, 0), "cassette_side_spar", BLUE)
    _plain(a, (0.032, 0.003, 0.089), (0, 0.0185, 0), "cassette_rear_plate", (180, 203, 199))
    for x in (-0.012, 0.012):
        for z in (-0.030, 0.030):
            a.add(
                trimesh.creation.cylinder(0.0012, 0.004, sections=40),
                (105, 130, 143),
                (x, 0.022, z),
                axis=(0, 1, 0),
                metal=0.25,
                name="rear_guiding_pin",
            )
    _label(a, "cassette_identification", "PUMPCASSETTE\nTRAINING", (0, -0.02357, -0.027), 0.026, 0.012)
    return a


def slot(obj):
    a = Assembly(obj.object_id)
    for node in _source("contec_receiver_case").graph.nodes_geometry:
        a.add(
            _mesh(_source("contec_receiver_case"), node),
            WHITE,
            rough=0.47,
            name="contec_source_open_receiver_case",
        )
    source = _source("contec_pump")
    for node in ("Object_2", "Object_3", "Object_4"):
        for i, m in enumerate(_components(_mesh(source, node))):
            if m.bounds[1, 0] > 0.009 or m.bounds[1, 1] > -0.060:
                continue
            m = _pump_transform(m)
            m.apply_translation([0, 0.0005, 0])
            color = BLUE if node == "Object_2" else (31, 49, 57) if node == "Object_3" else (121, 143, 151)
            a.add(m, color, rough=0.48, name=f"contec_source_control_{node}_{i}")
    handle = _components(_mesh(source, "Object_5"))[0]
    handle = _pump_transform(handle)
    # Keep the mature handle over the fixed control half, clear of the
    # enlarged teaching cassette opening and its unchanged insertion path.
    handle.apply_translation([-0.020, 0, 0])
    a.add(handle, (109, 126, 134), rough=0.43, name="contec_source_carry_handle")
    # Goal center is SLOT2-local (0,-.012,0), preserved from scene.json.
    _plain(a, (0.049, 0.048, 0.005), (0, -0.008, -0.050), "receiver_bottom_rail", BLUE)
    _plain(a, (0.049, 0.048, 0.003), (0, -0.008, 0.049), "receiver_top_rail", BLUE)
    _plain(a, (0.0045, 0.048, 0.094), (0.02275, -0.008, 0), "receiver_right_side_rail", BLUE)
    # The preserved source already forms the left cavity wall at X=-.0205.
    # Only extend that wall above/below its real Z bounds; do not put a second
    # same-facing surface on top of its middle span.
    case_bounds = _source("contec_receiver_case").bounds
    for i, (low, high) in enumerate(((-0.047, case_bounds[0, 2]), (case_bounds[1, 2], 0.047))):
        _plain(
            a,
            (0.0045, 0.048, high - low),
            (-0.02275, -0.008, (low + high) / 2),
            f"receiver_left_wall_extension_{i}",
            BLUE,
        )
    # A physically bored rear guide plate. Its holes remain open beyond the
    # pin tips; the bottom rail carries the cassette at the unchanged goal.
    panel = cq.Workplane("XY").box(0.040, 0.0075, 0.094).translate((0, 0.01225, 0))
    for x in (-0.012, 0.012):
        for z in (-0.030, 0.030):
            bore = cq.Solid.makeCylinder(0.00165, 0.009, cq.Vector(x, 0.008, z), cq.Vector(0, 1, 0))
            panel = panel.cut(cq.Workplane().newObject([bore]))
    a.add(cad_mesh(panel), (144, 163, 169), name="receiver_bored_guide_plate")
    _label(a, "slot_id", "SLOT 2\nSIM", (-0.035, -0.03208, 0.029), 0.020, 0.017)
    _plain(a, (0.035, 0.003, 0.055), (-0.028, 0.031, 0), "rear_mount_datum", (129, 145, 153))
    return a


@lru_cache(maxsize=1)
def monitor_source():
    m = _mesh(_source("medical_monitor"), "monitor_monitor_0")
    selected = [q for q in _components(m) if q.bounds[0, 2] > 79 and q.bounds[0, 0] > 8.8]
    s = trimesh.Scene()
    for i, q in enumerate(selected):
        s.add_geometry(q, node_name=f"source_head_{i}")
    s.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 0, 1]))
    s.apply_scale(0.018)
    s.apply_translation(-s.bounds.mean(axis=0))
    return s


def monitor(obj):
    a = Assembly(obj.object_id)
    _append(a, monitor_source(), "brodys_monitor")
    _plain(a, (0.060, 0.010, 0.055), (0.015, 0.046, -0.012), "monitor_teaching_vesa_pad", (67, 82, 91))
    _label(
        a,
        "monitor_training_status",
        "TEACHING MONITOR\nSIMULATION / STANDBY",
        (0, -0.05501, -0.082),
        0.160,
        0.022,
    )
    return a


def stopcock(obj):
    # This one small part is project-authored teaching adaptation. No free
    # redistributable medical rotor source was found; generic Y-connectors
    # were explicitly rejected. Manufacturer diagrams are shape references.
    a = Assembly(obj.object_id)
    blade = cq.Workplane("XY").circle(0.0085).extrude(0.004)
    bar = cq.Workplane("XY").box(0.051, 0.006, 0.004).edges("|Z").fillet(0.002).translate((0, 0, 0.002))
    branch = (
        cq.Workplane("XY").box(0.006, 0.026, 0.004).edges("|Z").fillet(0.002).translate((0, 0.012, 0.002))
    )
    rotor = cad_mesh(blade.union(bar).union(branch))
    rotor.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    a.add(rotor, BLUE, (0, -0.004, 0), rough=0.42, name="independent_three_arm_stopcock_handle")
    a.add(
        trimesh.creation.cylinder(0.0055, 0.022, sections=80),
        BLUE,
        (0, 0.003, 0),
        axis=(0, 1, 0),
        rough=0.42,
        name="stopcock_rotating_spindle",
    )
    for i, angle in enumerate((0, 90, 180)):
        # Baked flat flow arrows on the three fingers; all rotate with handle.
        xy = np.array(
            [
                [0.010, -0.0006],
                [0.017, -0.0006],
                [0.017, -0.0016],
                [0.021, 0],
                [0.017, 0.0016],
                [0.017, 0.0006],
                [0.010, 0.0006],
            ]
        )
        t = np.radians(angle)
        r = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
        xy = xy @ r.T
        points = np.c_[xy[:, 0], np.full(len(xy), -0.00804), xy[:, 1]]
        mesh = trimesh.Trimesh(points, [[0, 1, 5], [0, 5, 6], [2, 3, 4]], process=False)
        mesh.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=[238, 244, 242, 255], metallicFactor=0, roughnessFactor=0.7, doubleSided=True
            )
        )
        _put(a, mesh, f"label_rotating_flow_arrow_{i}")
    return a


def fixed_stopcock(a, p):
    def cyl(radius, length, start, direction):
        return cq.Workplane().newObject(
            [cq.Solid.makeCylinder(radius, length, cq.Vector(*start), cq.Vector(*direction))]
        )

    body = cyl(0.0095, 0.020, (0, -0.004, 0), (0, 1, 0))
    for direction in ((1, 0, 0), (-1, 0, 0), (0, 0, 1)):
        v = np.asarray(direction)
        body = body.union(cyl(0.0055, 0.022, tuple(v * 0.008 + [0, 0.007, 0]), direction))
        body = body.union(cyl(0.0072, 0.004, tuple(v * 0.023 + [0, 0.007, 0]), direction))
    body = body.cut(cyl(0.00565, 0.022, (0, -0.005, 0), (0, 1, 0)))
    for direction in ((1, 0, 0), (-1, 0, 0), (0, 0, 1)):
        body = body.cut(cyl(0.0024, 0.032, (0, 0.007, 0), direction))
    m = cad_mesh(body)
    m.apply_translation(p)
    m.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(
            name="transparent_training_polycarbonate",
            baseColorFactor=[192, 220, 226, 125],
            metallicFactor=0,
            roughnessFactor=0.19,
            alphaMode="BLEND",
            doubleSided=True,
        )
    )
    _put(a, m, "fixed_transparent_three_port_stopcock_body")
    # Axial bearing is the front annular face y=-.004 against the actual
    # handle back. The 5.5 mm spindle has 0.15 mm radial bore clearance.
    _plain(a, (0.024, 0.010, 0.020), p + [0, 0.021, 0], "stopcock_fixed_rear_mount", (93, 118, 129))


@lru_cache(maxsize=1)
def cart_source():
    s = _source("medical_cart").copy()
    m = _mesh(s, "Bacs_low_lambert1_0")
    # The mature cart contains deep trays. Its highest actual top-tray rim,
    # rather than the concave floor, is the removable work-lid datum.
    scale = CART_TOP / (m.bounds[1, 2] - s.bounds[0, 2])
    s.apply_translation([-3.740291986, 0.7017099, -s.bounds[0, 2]])
    s.apply_scale(scale)
    s.apply_translation([-0.20, -0.060, 0])
    return s


def _tray_lid_support(a, tray, center, index):
    """Small lid foot with its underside projected onto the genuine rim."""
    verts, faces = [], []
    n = 4
    for zlayer in [False, True]:
        for dy in np.linspace(-0.006, 0.006, n + 1):
            for dx in np.linspace(-0.006, 0.006, n + 1):
                x, y = np.asarray(center) + [dx, dy]
                hit = _ray(tray, [x, y, 0.96], [0, 0, -1])
                if hit is None:
                    raise ValueError("cart lid foot misses actual tray")
                verts.append([x, y, 0.94 if zlayer else hit[0][2]])
    total = (n + 1) ** 2
    for j in range(n):
        for i in range(n):
            k = j * (n + 1) + i
            faces.extend(
                [
                    [k, k + n + 2, k + 1],
                    [k, k + n + 1, k + n + 2],
                    [k + total, k + 1 + total, k + n + 2 + total],
                    [k + total, k + n + 2 + total, k + n + 1 + total],
                ]
            )
    boundary = (
        list(range(n + 1))
        + [j * (n + 1) + n for j in range(1, n + 1)]
        + [n * (n + 1) + i for i in range(n - 1, -1, -1)]
        + [j * (n + 1) for j in range(n - 1, 0, -1)]
    )
    for u, v in zip(boundary, boundary[1:] + boundary[:1]):
        faces.extend([[u, v, u + total], [v, v + total, u + total]])
    m = trimesh.Trimesh(verts, faces, process=True)
    m.fix_normals()
    a.add(m, (79, 104, 110), rough=0.72, name=f"actual_tray_rim_lid_support_{index}")


@lru_cache(maxsize=1)
def stand_source():
    s = _source("iv_stand").copy()
    m = _mesh(s, "Cylinder001_Material #3_0")
    mid = m.vertices[(m.vertices[:, 2] > 8000) & (m.vertices[:, 2] < 15000)]
    axis = (mid.min(axis=0) + mid.max(axis=0)) / 2
    scale = 1.91 / s.extents[2]
    s.apply_translation([-axis[0], -axis[1], -s.bounds[0, 2]])
    s.apply_scale(scale)
    s.apply_translation([0.025, 0.56, 0])
    # Each wheel is a source component. Correct the source's small unequal
    # wheel placements to the floor without deforming the wheel geometry.
    result = trimesh.Scene()
    for node in s.graph.nodes_geometry:
        m = _mesh(s, node)
        if node.startswith("Wheel"):
            m.apply_translation([0, 0, -m.bounds[0, 2]])
            color, metallic, rough = (38, 44, 48), 0.0, 0.65
        else:
            color, metallic, rough = (139, 153, 163), 0.70, 0.38
        m.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=[*color, 255], metallicFactor=metallic, roughnessFactor=rough
            )
        )
        result.add_geometry(m, node_name=node)
    return result


def environment(objects):
    a = Assembly("environment")
    _append(a, cart_source(), "nicolas_medical_cart")
    _append(a, stand_source(), "teeart_iv_stand")
    # A removable work lid sits over the mature deep tray. Four small feet
    # follow its real rim surface and the lid top preserves z=.950.
    _plain(
        a,
        (0.620, 0.480, 0.010),
        (-0.20, -0.06, 0.945),
        "cassette_initial_bearing_work_lid",
        (180, 203, 205),
        rough=0.64,
    )
    tray = _mesh(cart_source(), "Bacs_low_lambert1_0")
    raw = _source("medical_cart")
    sc = CART_TOP / (_mesh(raw, "Bacs_low_lambert1_0").bounds[1, 2] - raw.bounds[0, 2])
    for i, (x, y) in enumerate([(-18, -16), (25, -16), (-18, 14), (25, 14)]):
        center = np.array([-0.20, -0.06]) + (np.array([x, y]) - [3.740291986, -0.7017099]) * sc
        _tray_lid_support(a, tray, center, i)
    # The existing bag locations use a supplementary hanger crossbar attached
    # to the mature telescopic stand. The source stand is uniformly scaled.
    a.rod((-0.17, 0.50, 1.8815), (0.22, 0.50, 1.8815), 0.004, STEEL, "bag_hanger_crossbar")
    a.rod((0.025, 0.50, 1.8815), (0.025, 0.56, 1.8815), 0.005, STEEL, "bag_hanger_pole_clamp_arm")
    for key in ("BAG1", "BAG2"):
        p = np.asarray(objects[key].pose.position_m)
        a.rod((p[0], 0.50, 1.8815), (p[0], 0.388, 1.8815), 0.003, STEEL, f"{key}_actual_eye_support_hook")
        a.add(
            trimesh.creation.cylinder(0.00448, 0.006, sections=128),
            STEEL,
            (p[0], p[1], 1.880),
            axis=(0, 1, 0),
            metal=0.65,
            rough=0.4,
            name=f"{key}_actual_eye_support_sleeve",
        )
    # Rear mount pads make the three fixed task devices rigidly supported.
    p = np.asarray(objects["SLOT2"].pose.position_m)
    _plain(a, (0.035, 0.008, 0.055), p + [-0.028, 0.0365, 0], "slot_rear_contact_pad", (89, 109, 119))
    a.rod((p[0] - 0.028, p[1] + 0.0405, p[2]), (0.025, 0.56, p[2]), 0.010, STEEL, "slot_stand_mount_arm")
    p = np.asarray(objects["MONITOR"].pose.position_m)
    _plain(a, (0.060, 0.010, 0.055), p + [0.015, 0.056, -0.012], "monitor_rear_contact_pad", (73, 89, 99))
    a.rod(
        (p[0] + 0.015, p[1] + 0.061, p[2] - 0.012),
        (0.025, 0.56, p[2] - 0.012),
        0.012,
        STEEL,
        "monitor_stand_mount_arm",
    )
    # Isolated transparent three-port body, detached from clinical tubing.
    p = np.asarray(objects["STOPCOCK"].pose.position_m)
    fixed_stopcock(a, p)
    a.rod(tuple(p + [0, 0.026, 0]), (0.025, 0.56, p[2]), 0.008, STEEL, "stopcock_stand_clamp_arm")
    textured_box(
        a, (2.4, 2.2, 0.025), (-0.15, 0.10, -0.0125), "marble_01", tile_m=1.2, name="clean_clinic_floor"
    )
    return a


def build(spec):
    objects = {o.object_id: o for o in spec.objects}
    result = {key: bag(obj) for key, obj in objects.items() if key in ("BAG1", "BAG2")}
    result.update(
        {
            "PUMPCASSETTE": cassette(objects["PUMPCASSETTE"]),
            "SLOT2": slot(objects["SLOT2"]),
            "MONITOR": monitor(objects["MONITOR"]),
            "STOPCOCK": stopcock(objects["STOPCOCK"]),
        }
    )
    result["environment"] = environment(objects)
    return result
