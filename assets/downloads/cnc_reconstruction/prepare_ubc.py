"""Bake UBC frame 1 and retain complete ER components, not its HSK body.
Run with Blender 3.1.2; argv after --: source GLB, output directory.
"""

import bpy
import json
import hashlib
import sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1 :]
source = Path(args[0])
out = Path(args[1])
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
bpy.context.scene.frame_set(1)
deps = bpy.context.evaluated_depsgraph_get()
report = {
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "frame": 1,
    "blender": bpy.app.version_string,
    "parts": [],
    "excluded": ["complete HSK chuck body"],
    "texture_max_edge": 1024,
    "uniform_scale_applied": 1,
}
groups = {"ER_locknut": "rim_", "ER_collet": "vl002_innershell_", "carbide_endmill": "vl002b_"}
keep = []
for name, prefix in groups.items():
    old = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith(prefix)]
    assert old, (name, prefix)
    pieces = []
    for obj in old:
        ev = obj.evaluated_get(deps)
        data = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=deps)
        mesh = bpy.data.objects.new("baked_" + obj.name, data)
        bpy.context.collection.objects.link(mesh)
        mesh.matrix_world = ev.matrix_world.copy()
        pieces.append(mesh)
    bpy.ops.object.select_all(action="DESELECT")
    for o in pieces:
        o.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    before = len(obj.data.polygons)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.000001)
    bpy.ops.object.mode_set(mode="OBJECT")
    target = {"ER_locknut": 18000, "ER_collet": 24000, "carbide_endmill": 14000}[name]
    dec = obj.modifiers.new("documented_LOD", "DECIMATE")
    dec.ratio = min(1, target / len(obj.data.polygons))
    dec.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=dec.name)
    points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    bounds = [[min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]]
    report["parts"].append(
        {
            "name": name,
            "source_prefix": prefix,
            "source_chunks": len(old),
            "faces_before": before,
            "faces_after": len(obj.data.polygons),
            "bounds_baked_frame1": bounds,
            "topology": "complete source component; no geometric crop",
        }
    )
    keep.append(obj)
for obj in list(bpy.context.scene.objects):
    if obj not in keep:
        bpy.data.objects.remove(obj, do_unlink=True)
for image in bpy.data.images:
    if image.type == "IMAGE" and max(image.size) > 1024:
        scale = 1024 / max(image.size)
        image.scale(round(image.size[0] * scale), round(image.size[1] * scale))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(
    filepath=str(out / "ubc_er_components.glb"),
    export_format="GLB",
    use_selection=True,
    export_yup=True,
    export_animations=False,
    export_extras=True,
)
(out / "ubc_preparation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2), flush=True)
