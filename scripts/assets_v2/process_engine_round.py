"""Process the engine_round PolyHaven downloads (assets/raw/engine_round/<cat>/<id>/)
into single-file Z-up GLBs under assets/meshes/env/.

Same recipe as scripts/assets_v2/process_props.py (import -> drop non-meshes ->
transform_apply -> export GLB with export_yup=False), but sourced from the
engine_round raw tree whose gltf payload is stored as an extension-less file
named `gltf` next to `<id>.bin` + `textures/`.

Idempotent: existing outputs are skipped, so reruns never clobber current or
other scenes' products. New inventory entries are MERGED into
runs/scene_v2/prop_inventory.json (existing keys untouched).

Run inside Blender via the resource guard:
  .venv/bin/python scripts/resource_guard.py --rss-limit-gb 12 --execute -- \
      /home/hdd3/zhanghaonan/opt/blender/blender -b -t 4 \
      --python scripts/assets_v2/process_engine_round.py
"""
import bpy, sys, json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'assets/raw/engine_round'
DST = ROOT / 'assets/meshes/env'
DST.mkdir(parents=True, exist_ok=True)
INV = ROOT / 'runs/scene_v2/prop_inventory.json'

# engine_round props this scene kit needs as single-file GLBs. bench_vice_01
# already exists in env/ from the earlier polyhaven batch (same CC0 asset) and
# is deliberately NOT rebuilt here.
WANT = [
    'flathead_screwdriver', 'ratchet_wrench', 'tool_cart',
    'WoodenTable_03', 'oil_tin', 'small_oil_can_01', 'lubricant_spray',
    'steel_frame_shelves_02', 'old_tyre', 'rusted_wheel_rim_01',
    'old_military_compressor', 'caged_hanging_light', 'mounted_fluorescent_lights',
]

def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                  bpy.data.cameras, bpy.data.lights, bpy.data.actions, bpy.data.curves):
        for x in list(block):
            if not x.users:
                block.remove(x)

def find_gltf(mid):
    for cat in ('tools', 'garage', 'engine'):
        d = SRC / cat / mid
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and (f.name == 'gltf' or f.name.endswith('.gltf')):
                return f
    return None

inv_old = json.loads(INV.read_text()) if INV.exists() else {}
inv = {}
for mid in WANT:
    out = DST / f'{mid}.glb'
    if out.exists():
        print(f'skip existing {out.name}', flush=True)
        if mid in inv_old:
            inv[mid] = inv_old[mid]
        continue
    gltf = find_gltf(mid)
    if gltf is None:
        print(f'ERROR no gltf payload for {mid}', flush=True)
        continue
    clean()
    try:
        bpy.ops.import_scene.gltf(filepath=str(gltf))
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
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
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
INV.write_text(json.dumps(merged, indent=1, ensure_ascii=False))
print(f'engine_round: {len(inv)} new/refreshed entries; inventory total {len(merged)} -> {INV}')
