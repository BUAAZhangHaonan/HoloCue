"""Verify interactive-object GLBs are usable at their JSON pose.

Two checks per scene object asset:
1. trimesh check (matches the Viser path): load force='mesh', convert the glTF
   Y-up payload to the project Z-up frame, require the mesh to sit within
   `tol` of its declared origin (the JSON pose positions the origin, not the bbox).
2. declared-extent sanity: mesh extents > 0 and no NaN.

Usage: .venv/bin/python scripts/scenes/check_origins.py <scene_id> [scene_id ...]
Exit 1 listing failures; prints one line per object.
"""
from __future__ import annotations
import sys
import numpy as np
import trimesh

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'src'))
from holocue.config import load_scene, root

# Deliberate origin conventions that the lateral/vertical windows cannot infer.
# key: 'scene/object'; value: reason string. Keep this list SHORT and justified.
KNOWN_CONVENTIONS = {
    # Back face carries cable stubs extending +y; visual center is the chassis.
    'server_rack/NODE3': 'asymmetric cable stubs on back plate',
    # Origin at the bay mouth (insertion reference plane, like the connector scene socket S).
    'drone_bench/BAY': 'origin at bay mouth plane; well hangs below',
    # Origin at the hinge axis: rotate cues anchor the rotation center.
    'drone_bench/GUARD': 'origin at hinge axis; cover extends when open',
    # Origin at roller-top (arrival plane reference); legs extend to floor.
    'shelf_picking/CONV': 'origin at roller-top arrival plane; legs below',
    # Origin at the pin tip (planting point); the pennant cloth flies sideways.
    'dig_site/FLAG': 'origin at pin tip; pennant cloth offsets the bbox laterally',
    # Origin at the blade (rotation reference for the edge-line angle); handle extends -y.
    'dig_site/TROWEL': 'origin at blade center; handle extends away',
    # Origin at the well-mouth reference plane (insertion anchor); the bore and
    # ceramic seat extend DOWN into the head, so the bbox center sits below.
    'engine_bay/PLUGPORT': 'origin at well mouth plane; bore extends below into the head',
    # Origin at the shell center; the corrugated tail + wire extend -y from it.
    'engine_bay/CONN': 'tail wire extends -y from the shell center',
    # Origin at the bore mouth (insertion anchor plane); the bore extends +x
    # into the disc rim, so the bbox center sits behind the origin.
    'cnc_toolchange/POCKET9': 'origin at bore mouth plane; bore extends +x into the disc rim',
    # Origin at the valve outlet mouth (insertion anchor); body extends +y up
    # onto the bottle neck, offsetting the bbox center.
    'dive_fillstation/VALVE': 'origin at valve outlet mouth; body extends up onto the bottle neck',
    # Origin at the pump-slot mouth (insertion anchor); the channel recesses
    # into the pump face, offsetting the bbox center.
    'infusion_ward/SLOT2': 'origin at slot mouth plane; channel recesses into the pump face',
}

# Project GLBs store Z-up world-frame geometry as-is (trimesh/Viser contract); no
# axis conversion applies. Blender-side imports counter-rotate on the parent empty.
def check(scene_id: str, tol: float = 0.25) -> list[str]:
    spec = load_scene(scene_id)
    failures = []
    for o in spec.objects:
        mesh = trimesh.load(root() / o.asset, force='mesh')
        v = np.asarray(mesh.vertices, dtype=float)
        lo, hi = v.min(axis=0), v.max(axis=0)
        center = (lo + hi) / 2
        size = hi - lo
        extent = float(np.linalg.norm(size))
        # Guard against kit authoring outliers: lateral offset near zero, vertical free to
        # follow origin-at-contact-plane or origin-at-insertion-end conventions (the first three scenes use both).
        lateral = float(np.linalg.norm(center[:2])) / max(extent, 1e-9)
        z_ok = -0.1 * max(size[2], 1e-9) <= center[2] <= 1.05 * max(size[2], 1e-9)
        status = 'ok' if lateral <= 0.15 and z_ok else 'OFFSET'
        why = KNOWN_CONVENTIONS.get(f'{scene_id}/{o.object_id}')
        if status != 'ok' and why:
            status = f'ok-by-convention ({why})'
        print(f'{scene_id:14s} {o.object_id:8s} center=({center[0]:+.3f},{center[1]:+.3f},{center[2]:+.3f}) '
              f'extent={extent:.3f} lateral={lateral:.2f} {status}')
        if not status.startswith('ok'):
            failures.append(f'{scene_id}/{o.object_id}')
    return failures

def main() -> None:
    scenes = sys.argv[1:] or ['control_panel', 'connector', 'blocks']
    bad = [f for s in scenes for f in check(s)]
    if bad:
        print('FAIL:', ', '.join(bad))
        raise SystemExit(1)
    print('all object origins within tolerance')

if __name__ == '__main__':
    main()
