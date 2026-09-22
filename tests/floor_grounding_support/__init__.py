"""Triangle-level support and immutable authored-node checks; no rendering."""

import hashlib, json
import numpy as np

SCENES = (
    "control_panel",
    "optical_bench",
    "cnc_toolchange",
    "dive_fillstation",
    "server_rack",
    "shelf_picking",
    "engine_bay",
)
COUNTS = {
    "control_panel": 4,
    "optical_bench": 4,
    "cnc_toolchange": 4,
    "dive_fillstation": 4,
    "server_rack": 12,
    "shelf_picking": 12,
    "engine_bay": 12,
}


def mesh_map(scene):
    result = {}
    for node in scene.graph.nodes_geometry:
        tr, gn = scene.graph[node]
        m = scene.geometry[gn].copy()
        m.apply_transform(tr)
        result[str(node)] = m
    return result


def fingerprint(mesh):
    h = hashlib.sha256()
    for arr in (mesh.vertices, mesh.faces, mesh.vertex_normals, mesh.visual.uv):
        if arr is None:
            h.update(b"None")
            continue
        aa = np.asarray(arr)
        h.update(str(aa.shape).encode())
        h.update(aa.tobytes())
    mat = mesh.visual.material
    for key in ("name", "baseColorFactor", "metallicFactor", "roughnessFactor", "doubleSided", "alphaMode"):
        val = getattr(mat, key, None)
        if isinstance(val, np.ndarray):
            val = val.tolist()
        h.update(json.dumps(val, sort_keys=True).encode())
    image = getattr(mat, "baseColorTexture", None)
    if image is not None:
        h.update(np.asarray(image).tobytes())
    return h.hexdigest()


def surface_hit(xy, tris, highest):
    a = tris[:, 0, :2]
    u = tris[:, 1, :2] - a
    v = tris[:, 2, :2] - a
    w = xy - a
    det = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    good = np.abs(det) > 1e-15
    s = np.divide(w[:, 0] * v[:, 1] - w[:, 1] * v[:, 0], det, out=np.zeros_like(det), where=good)
    t = np.divide(u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0], det, out=np.zeros_like(det), where=good)
    hits = np.flatnonzero(good & (s >= -1e-8) & (t >= -1e-8) & (s + t <= 1 + 1e-8))
    if not len(hits):
        return None
    zs = tris[:, 0, 2] + s * (tris[:, 1, 2] - tris[:, 0, 2]) + t * (tris[:, 2, 2] - tris[:, 0, 2])
    i = int(hits[np.argmax(zs[hits]) if highest else np.argmin(zs[hits])])
    return {"z": float(zs[i]), "triangle_index": i, "triangle": tris[i].tolist()}


def horizontal_contact(lower, upper):
    tris = lower.triangles
    z = float(lower.vertices[:, 2].max())
    indices = np.flatnonzero(np.max(np.abs(tris[:, :, 2] - z), axis=1) < 1e-7)
    if not len(indices):
        return None
    i = int(indices[np.argmax(lower.area_faces[indices])])
    point = tris[i].mean(axis=0)
    hit = surface_hit(point[:2], upper.triangles, False)
    if hit is None:
        return None
    return {
        "gap_m": hit["z"] - float(point[2]),
        "lower_triangle_index": i,
        "lower_triangle": tris[i].tolist(),
        "witness": point.tolist(),
        "upper_hit": hit,
        "connected": abs(hit["z"] - float(point[2])) < 1e-6,
    }


def floor_contact(floor, part):
    tris = part.triangles
    z = float(part.vertices[:, 2].min())
    ii = np.flatnonzero(np.max(np.abs(tris[:, :, 2] - z), axis=1) < 1e-7)
    assert len(ii), "Support has no bottom plane"
    i = int(ii[np.argmax(part.area_faces[ii])])
    point = tris[i].mean(axis=0)
    hit = surface_hit(point[:2], floor.triangles, True)
    assert hit is not None, "Support bottom misses floor footprint"
    return {
        "gap_m": float(point[2]) - hit["z"],
        "part_triangle_index": i,
        "part_triangle": tris[i].tolist(),
        "witness": point.tolist(),
        "floor_hit": hit,
        "connected": abs(float(point[2]) - hit["z"]) < 1e-6,
    }


def axial_contact(lower, upper, axis, point):
    order = [i for i in range(3) if i != axis] + [axis]
    p = np.asarray(point)[order]
    a = surface_hit(p[:2], lower.triangles[:, :, order], True)
    b = surface_hit(p[:2], upper.triangles[:, :, order], False)
    assert a is not None and b is not None
    for h in (a, b):
        tri = np.asarray(h["triangle"])
        world = np.zeros_like(tri)
        world[:, order] = tri
        h["world_triangle"] = world.tolist()
    return {
        "gap_m": b["z"] - a["z"],
        "axis": axis,
        "axis_point": list(point),
        "lower_hit": a,
        "upper_hit": b,
        "connected": abs(b["z"] - a["z"]) < 1e-6,
    }


def contacts(meshes):
    floor_names = [n for n in meshes if "floor" in n]
    assert len(floor_names) == 1
    fn = floor_names[0]
    floor = meshes[fn]
    rows = []
    for name, m in meshes.items():
        if name.endswith(("table_ground_foot", "rack_ground_foot", "engine_stand_base")):
            rows.append({"lower": fn, "upper": name, **floor_contact(floor, m)})
        if name.endswith(("table_ground_foot", "rack_ground_foot", "engine_stand_post")):
            target = (
                "table_leg"
                if name.endswith("table_ground_foot")
                else "rack_post"
                if name.endswith("rack_ground_foot")
                else "engine_cradle"
            )
            candidates = []
            for nn, mm in meshes.items():
                if nn.endswith(target):
                    edge = horizontal_contact(m, mm)
                    if edge is not None:
                        candidates.append((nn, edge))
            assert len(candidates) == 1, (name, candidates)
            nn, edge = candidates[0]
            rows.append({"lower": name, "upper": nn, **edge})
        if name.endswith("engine_stand_post"):
            candidates = []
            for nn, mm in meshes.items():
                if (
                    nn.endswith("engine_stand_base")
                    and np.all(m.bounds.mean(axis=0)[:2] >= mm.bounds[0, :2])
                    and np.all(m.bounds.mean(axis=0)[:2] <= mm.bounds[1, :2])
                ):
                    # Lower base's centre may not lie under this individual post.
                    edge = floor_contact(mm, m)
                    if edge is not None:
                        candidates.append((nn, edge))
            assert len(candidates) == 1, (name, candidates)
            nn, edge = candidates[0]
            rows.append({"lower": nn, "upper": name, **edge})
        if name.endswith(("engine_fender_riser", "engine_connector_post")):
            cradle = next(n for n in meshes if n.endswith("engine_cradle"))
            rows.append({"lower": cradle, "upper": name, **floor_contact(meshes[cradle], m)})
            target = "fender" if name.endswith("engine_fender_riser") else "connector_rest"
            candidates = []
            for nn, mm in meshes.items():
                if nn.endswith(target):
                    edge = horizontal_contact(m, mm)
                    if edge is not None:
                        candidates.append((nn, edge))
            assert len(candidates) == 1, (name, candidates)
            nn, edge = candidates[0]
            rows.append({"lower": name, "upper": nn, **edge})
        if name.endswith("table_leg"):
            candidates = []
            for nn, mm in meshes.items():
                if nn.endswith("worktop"):
                    edge = horizontal_contact(m, mm)
                    if edge is not None:
                        candidates.append((nn, edge))
            assert len(candidates) == 1, (name, candidates)
            nn, edge = candidates[0]
            rows.append({"lower": name, "upper": nn, **edge})
        if name.endswith("engine_pulley_axle"):
            centre = m.bounds.mean(axis=0)
            block = next(n for n in meshes if n.endswith("engine_block"))
            pulley = next(
                n
                for n in meshes
                if n.endswith("belt_pulley") and abs(meshes[n].bounds.mean(axis=0)[1] - centre[1]) < 1e-5
            )
            rows.append({"lower": block, "upper": name, **axial_contact(meshes[block], m, 0, centre)})
            rows.append({"lower": name, "upper": pulley, **axial_contact(m, meshes[pulley], 0, centre)})
        if name.endswith("sparkplug_rest_pad"):
            tray = next(n for n in meshes if n.endswith("sparkplug_tray"))
            shell = next(n for n in meshes if n.endswith("PLUG/0008_threaded_shell"))
            rows.append({"lower": tray, "upper": name, **floor_contact(meshes[tray], m)})
            rows.append({"lower": name, "upper": shell, **horizontal_contact(m, meshes[shell])})
    return rows
