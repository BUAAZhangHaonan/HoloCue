"""Convert original PX4 Collada sources with real Blender; no scene build.

blender -b -t 4 --python convert_px4.py -- --output-dir <project scratch>
"""

from pathlib import Path
import argparse, sys
import bpy

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
args.output_dir.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
for original, output in [
    ("NXP-HGD-CF.dae", "source_frame.glb"),
    ("5010Base.dae", "5010Base.glb"),
    ("5010Bell.dae", "5010Bell.glb"),
]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.collada_import(filepath=str(HERE / "px4/meshes" / original))
    bpy.ops.export_scene.gltf(filepath=str(args.output_dir / output), export_format="GLB", export_yup=True)
