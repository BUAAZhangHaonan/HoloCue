"""Process downloaded PolyHaven gltf props into single-file GLBs under assets/meshes/env/.
Run inside Blender: blender -b --python scripts/assets_v2/process_props.py -- [--only id ...]
Outputs inventory (bbox m, triangles, size) to runs/scene_v2/prop_inventory.json.
"""
import bpy, sys, json, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--only', nargs='*', default=None)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

SRC = ROOT/'assets/downloads/polyhaven/models'
DST = ROOT/'assets/meshes/env'
DST.mkdir(parents=True, exist_ok=True)
inv_path = ROOT/'runs/scene_v2/prop_inventory.json'
inv = json.loads(inv_path.read_text()) if inv_path.exists() else {}

def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights, bpy.data.actions, bpy.data.curves):
        for x in list(block):
            if not x.users:
                block.remove(x)

ids = sorted(d.name for d in SRC.iterdir() if d.is_dir())
if a.only:
    ids = [i for i in ids if i in a.only]
for mid in ids:
    gltf = next(SRC.joinpath(mid).glob('*.gltf'), None)
    if gltf is None:
        print(f'WARN no gltf for {mid}', flush=True)
        continue
    out = DST/f'{mid}.glb'
    if out.exists():
        print(f'skip existing {out.name}', flush=True)
        continue
    clean()
    try:
        bpy.ops.import_scene.gltf(filepath=str(gltf))
    except Exception as e:
        print(f'ERROR importing {mid}: {e}', flush=True)
        continue
    # Drop non-mesh leftovers (cameras/lights/armature-unsupported extras).
    for o in list(bpy.data.objects):
        if o.type not in ('MESH', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    if not meshes:
        print(f'WARN {mid}: no meshes', flush=True)
        continue
    for o in meshes:
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    tris = 0
    lo = [1e9]*3; hi = [-1e9]*3
    for o in meshes:
        me = o.data
        tris += sum(len(p.vertices)-2 for p in me.polygons)
        for v in o.bound_box:
            w = o.matrix_world @ __import__('mathutils').Vector(v)
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    bpy.ops.export_scene.gltf(filepath=str(out), export_format='GLB', export_apply=True,
                              export_yup=False, use_selection=False)
    dims = [round(hi[i]-lo[i], 4) for i in range(3)]
    inv[mid] = {'glb': str(out.relative_to(ROOT)), 'bbox_m': dims, 'triangles': tris,
                'bytes': out.stat().st_size}
    print(json.dumps({'id': mid, 'bbox_m': dims, 'tris': tris, 'bytes': out.stat().st_size}), flush=True)

inv_path.parent.mkdir(parents=True, exist_ok=True)
inv_path.write_text(json.dumps(inv, indent=1, ensure_ascii=False))
print(f'inventory: {len(inv)} props -> {inv_path}')
