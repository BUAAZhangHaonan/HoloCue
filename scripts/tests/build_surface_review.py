"""Build changed CAD regions and report the actual exported topology."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from holocue.assets import load_asset
from holocue.config import load_scene, root
from holocue.modeling import make_environment, make_object


def main():
    out = root() / 'runs/cloud_review'
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for sid, ids in [('shelf_picking', ('BLUE', 'BASKET')), ('drone_bench', ('BAY',)),
                     ('engine_bay', ('workstation',))]:
        spec = load_scene(sid)
        for oid in ids:
            start = time.perf_counter()
            obj = spec.environment[0] if oid == 'workstation' else next(o for o in spec.objects if o.object_id == oid)
            path = root() / obj.asset
            assembly = make_environment(spec) if oid == 'workstation' else make_object(obj)
            assembly.save(path)
            scene = load_asset(str(path), spec.asset_axes)
            parts = []
            for node in scene.graph.nodes_geometry:
                if oid == 'workstation' and not node.endswith(('0052_tube', '0053_tube', '0054_rounded_part', '0055_clamp_band')):
                    continue
                _, name = scene.graph[node]
                mesh = scene.geometry[name].copy()
                mesh.process(validate=True)
                parts.append({'node': node, 'faces': len(mesh.faces), 'watertight': bool(mesh.is_watertight),
                              'winding_consistent': bool(mesh.is_winding_consistent),
                              'components': len(mesh.split(only_watertight=False)), 'volume_m3': float(mesh.volume)})
            record = {'scene_id': sid, 'object_id': oid, 'asset': obj.asset,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'duration_s': time.perf_counter() - start, 'parts': parts}
            records.append(record)
            print(json.dumps(record), flush=True)
    (out / 'surface_build.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
