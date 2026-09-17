"""Download CC0 assets from PolyHaven into assets/downloads/polyhaven with md5 verification.
Only the ids listed in ASSET_LIST below are fetched; every file keeps its md5 from the API.
Run:  .venv/bin/python scripts/assets_v2/download_polyhaven.py [--models id ...] [--textures id ...] [--dry]
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'assets' / 'downloads' / 'polyhaven'
API = 'https://api.polyhaven.com'

MODELS = [
    # server_rack
    'worn_metal_rack', 'modular_electric_cables', 'circuit_board', 'security_camera_01',
    # drone_bench
    'metal_toolbox', 'screwdrivers_02', 'pliers', 'bench_vice_01', 'magnifying_glass_01',
    'retro_multimeter',
    # shelf_picking
    'cardboard_box_01', 'plastic_crate_01', 'plastic_crate_02', 'wooden_crate_02', 'Barrel_02',
    'cement_bag', 'hand_truck', 'steel_frame_shelves_02',
    # optical_bench
    'desk_lamp_arm_01', 'binder_notebook',
    # dig_site
    'trowel_01', 'rusted_spade_01', 'stone_01', 'rock_07', 'ceramic_pot', 'wooden_crate_01',
]
TEXTURES = [
    'metal_plate_02', 'factory_wall', 'hangar_concrete_floor',
    'rubber_tiles', 'wood_table_001',
    'concrete_floor_worn_001',
    'metal_plate', 'rough_linen', 'marble_01',
    'excavated_soil_wall', 'dirt', 'gravelly_sand', 'hessian_230',
]

def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def fetch(client: httpx.Client, url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with client.stream('GET', url) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + '.part')
                with tmp.open('wb') as f:
                    for chunk in r.iter_bytes(1 << 16):
                        f.write(chunk)
                tmp.replace(dest)
                return
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))

def download_model(client: httpx.Client, asset_id: str, log: list) -> None:
    base = OUT / 'models' / asset_id
    files = json.loads(client.get(f'{API}/files/{asset_id}').text)
    g = files['gltf']['1k']['gltf']
    entries = {'gltf': g} | {k: v for k, v in g.get('include', {}).items()}
    for rel, entry in entries.items():
        url, digest, size = entry['url'], entry['md5'], entry.get('size', 0)
        dest = base / rel
        fetch(client, url, dest)
        got = md5(dest)
        status = 'ok' if got == digest else 'MD5-MISMATCH'
        log.append({'id': asset_id, 'kind': 'model', 'file': rel, 'url': url,
                    'size': size, 'md5': digest, 'md5_ok': got == digest})
        print(f'{asset_id:28s} {rel:60s} {size:>9d}B {status}', flush=True)
        if got != digest:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f'md5 mismatch for {dest}')

def download_texture(client: httpx.Client, asset_id: str, log: list) -> None:
    base = OUT / 'textures' / asset_id
    files = json.loads(client.get(f'{API}/files/{asset_id}').text)
    count = 0
    for map_name, resos in files.items():
        if not isinstance(resos, dict) or '1k' not in resos:
            continue
        entry = resos['1k']
        if not isinstance(entry, dict) or 'jpg' not in entry:
            continue
        jpg = entry['jpg']
        url, digest = jpg['url'], jpg['md5']
        dest = base / f'{map_name}_1k.jpg'
        fetch(client, url, dest)
        got = md5(dest)
        log.append({'id': asset_id, 'kind': 'texture', 'file': dest.name, 'url': url,
                    'size': jpg.get('size', 0), 'md5': digest, 'md5_ok': got == digest})
        print(f'{asset_id:28s} {dest.name:60s} {jpg.get("size",0):>9d}B '
              f'{"ok" if got == digest else "MD5-MISMATCH"}', flush=True)
        if got != digest:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f'md5 mismatch for {dest}')
        count += 1
    if count == 0:
        raise RuntimeError(f'no 1k jpg maps found for texture {asset_id}')

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--models', nargs='*', default=MODELS)
    p.add_argument('--textures', nargs='*', default=TEXTURES)
    p.add_argument('--dry', action='store_true')
    a = p.parse_args()
    if a.dry:
        print(f'{len(a.models)} models, {len(a.textures)} textures planned')
        return
    log_path = OUT / 'polyhaven_download_log.json'
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    known = {(e['id'], e['kind'], e['file']) for e in log}
    with httpx.Client(timeout=httpx.Timeout(60, connect=10), follow_redirects=True) as client:
        for mid in a.models:
            download_model(client, mid, log)
        for tid in a.textures:
            download_texture(client, tid, log)
    log = [e for e in log if (e['id'], e['kind'], e['file']) in known] + \
          [e for e in log if (e['id'], e['kind'], e['file']) not in known]
    OUT.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False))
    print(f'log entries: {len(log)} -> {log_path}')

if __name__ == '__main__':
    main()
