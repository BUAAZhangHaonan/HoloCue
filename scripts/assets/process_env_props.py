"""Process downloaded PolyHaven gltf props into single-file Z-up GLBs under assets/meshes/env/.

Unified pipeline for every download batch, replacing the former process_props.py
(polyhaven models tree) and process_engine_round.py (engine_round raw tree):
import -> drop non-meshes -> transform_apply(rotation, scale) -> export GLB
with export_yup=False. Handles both gltf payload layouts: <dir>/<id>/*.gltf
and <dir>/<cat>/<id>/gltf (extension-less payload next to <id>.bin + textures/).

Run inside Blender via the resource guard:
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
      /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/assets/process_env_props.py -- --source assets/downloads/polyhaven/models

Idempotent: existing GLBs are skipped and their entries carried over;
runs/scene_v2/prop_inventory.json is MERGED, never overwritten, so reruns never
clobber other scenes' products.
"""
import bpy, sys, json, argparse
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
DST = ROOT / 'assets/meshes/env'
DST.mkdir(parents=True, exist_ok=True)
INV = ROOT / 'runs/scene_v2/prop_inventory.json'

p = argparse.ArgumentParser()
p.add_argument('--source', default='assets/downloads/polyhaven/models',
               help='batch root relative to repo; ids live in <source>/<id>/ or <source>/<cat>/<id>/')
p.add_argument('--ids', nargs='*', default=None,
               help='restrict to these ids (default: every id found under --source)')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
SRC = ROOT / a.source

def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                  bpy.data.cameras, bpy.data.lights, bpy.data.actions, bpy.data.curves):
        for x in list(block):
            if not x.users:
                block.remove(x)

def gltf_payload(d: Path):
    """gltf entry file inside an id directory: *.gltf or an extension-less 'gltf'."""
    if not d.is_dir():
        return None
    for f in sorted(d.iterdir()):
        if f.is_file() and (f.name.endswith('.gltf') or f.name == 'gltf'):
            return f
    return None

def find_id_dir(mid: str):
    direct = SRC / mid
    if gltf_payload(direct):
        return direct
    for cat in sorted(SRC.iterdir()):
        cand = cat / mid
        if gltf_payload(cand):
            return cand
    return None

def discover_ids():
    ids = set()
    for child in sorted(SRC.iterdir()):
        if gltf_payload(child):
            ids.add(child.name)
        elif child.is_dir():
            for grand in sorted(child.iterdir()):
                if gltf_payload(grand):
                    ids.add(grand.name)
    return sorted(ids)

inv_old = json.loads(INV.read_text()) if INV.exists() else {}
inv = {}
ids = a.ids if a.ids else discover_ids()
for mid in ids:
    out = DST / f'{mid}.glb'
    if out.exists():
        print(f'skip existing {out.name}', flush=True)
        if mid in inv_old:
            inv[mid] = inv_old[mid]
        continue
    src_dir = find_id_dir(mid)
    if src_dir is None:
        print(f'ERROR no gltf payload for {mid}', flush=True)
        continue
    clean()
    try:
        bpy.ops.import_scene.gltf(filepath=str(gltf_payload(src_dir)))
    except Exception as e:
        print(f'ERROR importing {mid}: {e}', flush=True)
        continue
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
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for o in meshes:
        tris += sum(len(v.vertices) - 2 for v in o.data.polygons)
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    bpy.ops.export_scene.gltf(filepath=str(out), export_format='GLB', export_apply=True,
                              export_yup=False, use_selection=False)
    # dims in the STORED Z-up frame (the frame place_prop and the JSON pose use)
    dims = [round(hi[i] - lo[i], 4) for i in range(3)]
    inv[mid] = {'glb': str(out.relative_to(ROOT)), 'bbox_m': dims, 'triangles': tris,
                'bytes': out.stat().st_size}
    print(json.dumps({'id': mid, 'bbox_m_zup': dims, 'tris': tris,
                      'bytes': out.stat().st_size}), flush=True)

merged = dict(inv_old)
merged.update(inv)
INV.parent.mkdir(parents=True, exist_ok=True)
INV.write_text(json.dumps(merged, indent=1, ensure_ascii=False))
print(f'processed {len(inv)} new/refreshed of {len(ids)} ids; inventory total {len(merged)} -> {INV}')
