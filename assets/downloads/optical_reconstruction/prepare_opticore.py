"""Offline Blender-only reproduction of the shipped OptiCore breadboard.

SPDX-License-Identifier: GPL-3.0-or-later
Uses the unmodified add_table / add_tableface functions in opticore_table.py.
Run with Blender --background --python this_file; no network access is used.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)


def object_data_add(context, mesh, operator=None):
    obj = bpy.data.objects.new("OptiCore_900x1400_25mm_true_bores", mesh)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


source = ast.parse((HERE / "opticore_table.py.txt").read_text())
source.body = [
    n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ("add_table", "add_tableface")
]
exec(compile(source, "opticore_table.py", "exec"), globals())
settings = SimpleNamespace(
    length=900,
    width=1400,
    thickness=25,
    hrad=3,
    brad=6,
    hspac=25,
    nph=16,
    nbev=6,
    smooth_type=True,
    shade_smooth=False,
)
add_table(settings, bpy.context)
obj = bpy.context.object
obj.scale = (0.001, 0.001, 0.001)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
obj.data.use_auto_smooth = True
obj.data.auto_smooth_angle = 0.52
bpy.ops.export_scene.gltf(
    filepath=str(HERE / "opticore_breadboard.glb"), export_format="GLB", use_selection=True, export_yup=True
)
