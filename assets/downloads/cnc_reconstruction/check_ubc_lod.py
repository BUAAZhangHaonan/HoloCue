"""Measure deterministic bidirectional area samples; not a Hausdorff bound.
Blender argv after --: original GLB, prepared GLB, output JSON.
"""

import gc
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

raw, prepared, output = map(Path, sys.argv[sys.argv.index("--") + 1 :])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(raw))
bpy.context.scene.frame_set(1)
source_objects = list(bpy.context.scene.objects)
bpy.ops.import_scene.gltf(filepath=str(prepared))
prepared_objects = [o for o in bpy.context.scene.objects if o not in source_objects and o.type == "MESH"]
deps = bpy.context.evaluated_depsgraph_get()


def vertices_faces(objects):
    verts = []
    faces = []
    offset = 0
    for obj in objects:
        ev = obj.evaluated_get(deps)
        data = ev.to_mesh()
        data.calc_loop_triangles()
        coords = np.asarray([ev.matrix_world @ v.co for v in data.vertices], dtype=np.float64)
        tris = np.asarray([t.vertices[:] for t in data.loop_triangles], dtype=np.int32)
        verts.append(coords)
        faces.append(tris + offset)
        offset += len(coords)
        ev.to_mesh_clear()
    return np.concatenate(verts), np.concatenate(faces)


def sample(vertices, faces, seed):
    rng = np.random.default_rng(seed)
    triangles = vertices[faces]
    areas = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    tri = triangles[rng.choice(len(triangles), size=12000, p=areas / areas.sum())]
    uv = rng.random((len(tri), 2))
    flip = uv.sum(1) > 1
    uv[flip] = 1 - uv[flip]
    return tri[:, 0] + uv[:, 0, None] * (tri[:, 1] - tri[:, 0]) + uv[:, 1, None] * (tri[:, 2] - tri[:, 0])


report = {
    "source_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
    "prepared_sha256": hashlib.sha256(prepared.read_bytes()).hexdigest(),
    "blender": bpy.app.version_string,
    "source_frame": 1,
    "scene_scale_m_per_source_unit": 0.030,
    "method": "12000 deterministic area-weighted samples in each direction, nearest triangle distance; sample maxima are not a global Hausdorff guarantee",
    "parts": [],
}
for index, (name, prefix) in enumerate(
    {"ER_locknut": "rim_", "ER_collet": "vl002_innershell_", "carbide_endmill": "vl002b_"}.items()
):
    sv, sf = vertices_faces([o for o in source_objects if o.type == "MESH" and o.name.startswith(prefix)])
    pv, pf = vertices_faces([o for o in prepared_objects if o.name.startswith(name)])
    original_bvh = BVHTree.FromPolygons(sv.tolist(), sf.tolist(), all_triangles=True)
    prepared_bvh = BVHTree.FromPolygons(pv.tolist(), pf.tolist(), all_triangles=True)
    row = {"name": name, "source_triangles": len(sf), "prepared_triangles": len(pf)}
    for key, points, target in [
        ("source_to_lod", sample(sv, sf, 872 + index), prepared_bvh),
        ("lod_to_source", sample(pv, pf, 982 + index), original_bvh),
    ]:
        distances = np.asarray([target.find_nearest(Vector(p))[3] for p in points]) * 0.030 * 1000
        row[key + "_millimetres"] = {
            "p50": float(np.percentile(distances, 50)),
            "p95": float(np.percentile(distances, 95)),
            "p99": float(np.percentile(distances, 99)),
            "sample_max": float(distances.max()),
        }
    report["parts"].append(row)
    print(json.dumps(row), flush=True)
    del original_bvh, prepared_bvh, sv, sf, pv, pf
    gc.collect()
output.write_text(json.dumps(report, indent=2) + "\n")
