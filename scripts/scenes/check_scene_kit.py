"""Contract checker for per-scene kits under scenes/.

One folder per scene is the management contract (scenes/README of the template):
config, meshes, blend, docs and reviews live in the kit; builders live in
scripts/scenes/build_<id>.py; shared pools stay in assets/. This checker
verifies every kit against that contract and exits 1 listing failures.

Usage: .venv/bin/python scripts/scenes/check_scene_kit.py [scene_id ...]
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from holocue.config import root, list_scenes, load_scene  # noqa: E402

# Initial scenes predate per-scene builders: their geometry comes from
# scripts/assets/generate_assets.py (shared common/ pool) plus the generic
# official chain. Documented exception, not a loophole for new kits.
INITIAL_NO_BUILDER = {'blocks', 'connector', 'control_panel'}


def check(scene_id: str) -> list[str]:
    kit = root() / 'scenes' / scene_id
    failures = []
    if not (kit / 'scene.json').is_file():
        return [f'{scene_id}: scene.json missing']
    try:
        spec = load_scene(scene_id)
    except Exception as e:  # noqa: BLE001 - report, don't crash the sweep
        return [f'{scene_id}: scene.json fails to load: {e!r}']
    if spec.scene_id != scene_id:
        failures.append(f'{scene_id}: scene_id mismatch ({spec.scene_id})')

    for o in spec.objects:
        if not (root() / o.asset).is_file():
            failures.append(f'{scene_id}: object asset missing {o.asset}')
        if not o.capabilities:
            failures.append(f'{scene_id}: {o.object_id} has empty capabilities')
        if not o.description or o.description == o.label:
            failures.append(f'{scene_id}: {o.object_id} description is a label echo')
    for p in spec.environment:
        if not (root() / p.asset).is_file():
            failures.append(f'{scene_id}: env asset missing {p.asset}')
        if not p.label:
            failures.append(f'{scene_id}: env prop {p.prop_id} has empty label')
    rh = spec.render_hints
    if rh.ortho_scale_m == 4.8 and rh.grid_extent_m == 4.0 and not rh.fit_camera:
        failures.append(f'{scene_id}: render_hints look like untouched template values')

    if not (kit / 'blend' / f'{scene_id}.blend').is_file():
        failures.append(f'{scene_id}: blend/{scene_id}.blend missing (official chain not run)')
    if not (kit / 'docs' / 'design.md').is_file():
        failures.append(f'{scene_id}: docs/design.md missing')
    if not any((kit / 'reviews').glob('*')):
        failures.append(f'{scene_id}: reviews/ empty')
    if scene_id not in INITIAL_NO_BUILDER and \
            not (root() / 'scripts' / 'scenes' / f'build_{scene_id}.py').is_file():
        failures.append(f'{scene_id}: scripts/scenes/build_{scene_id}.py missing')

    license_text = (root() / 'assets' / 'ASSET_LICENSE.md').read_text(encoding='utf-8')
    if f'scenes/{scene_id}/meshes' not in license_text and scene_id not in INITIAL_NO_BUILDER:
        failures.append(f'{scene_id}: meshes not registered in assets/ASSET_LICENSE.md')
    return failures


def main() -> None:
    ids = sys.argv[1:] or [s['scene_id'] for s in list_scenes()]
    bad = [f for s in ids for f in check(s)]
    for s in ids:
        print(f'{s:16s} {"ok" if not check(s) else "FAIL"}')
    if bad:
        print('FAIL:')
        for f in bad:
            print(' -', f)
        raise SystemExit(1)
    print(f'all {len(ids)} scene kits conform')


if __name__ == '__main__':
    main()
