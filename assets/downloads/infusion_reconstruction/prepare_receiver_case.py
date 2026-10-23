"""Reproduce the teaching receiver from the attributed Contec source mesh.

Run ``extract --work PATH`` with the project simulation Python, then run
``cut --work PATH`` with Blender. All intermediate data stays in PATH.
The original GLB is never modified. See the adjacent README for attribution.
"""

import argparse
import hashlib
import sys
from pathlib import Path


SOURCE_SHA256 = "5d9651a405c00168c12b820e3eb7fe52e4153e55d10a60dabfb0e7a25eaf524a"


def extract(source, work):
    import numpy as np
    import trimesh

    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Contec source differs from the attributed original receipt")
    scene = trimesh.load_scene(source, process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    transform, geometry = scene.graph["Object_10"]
    mesh = scene.geometry[geometry].copy()
    mesh.apply_transform(transform)
    connected = mesh.copy()
    connected.merge_vertices(merge_tex=True, merge_norm=True)
    groups = trimesh.graph.connected_components(
        connected.face_adjacency, nodes=np.arange(len(connected.faces)), min_len=1
    )
    mesh = mesh.submesh([groups[0]], append=True, repair=False)
    mesh.apply_translation([-0.03723799902945757, 0, -0.03684599883854389])
    mesh.apply_scale(0.46)
    mesh.apply_translation([0, -0.032 + 0.06164199858903885 * 0.46, 0])
    result = trimesh.Scene(mesh)
    result.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    result.export(work / "receiver_case_input.glb")


def cut(work, output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(work / "receiver_case_input.glb"))
    obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    # Local-Z-up opening bounds: [-.0205,-.042,-.050] to [.0205,.016,.050].
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.013, 0))
    cutter = bpy.context.object
    cutter.dimensions = (0.041, 0.058, 0.100)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("teaching_receiver_open_channel", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    obj.name = "contec_source_case_open_teaching_channel"
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_yup=True, export_apply=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["extract", "cut"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("contec_pump.glb"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("contec_receiver_case.glb"))
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.stage == "extract":
        extract(args.source, args.work)
    else:
        cut(args.work, args.output)


if __name__ == "__main__":
    main()
