"""Extract actual full source flange and extrusion; preserve their cross sections."""

from pathlib import Path
import sys, json, hashlib
import numpy as np
import trimesh

source = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
m = trimesh.load_scene(source, process=False).to_geometry()
m.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=5)
parts = m.split(only_watertight=False)
record = {
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "source_raw_axes": "Z points down for the cart; wheel extrema +93 mm, cart top -1530 mm",
    "parts": [],
}
selected = []
for p in parts:
    lo, hi = p.bounds
    if np.all(lo >= [608, -466, -250]) and np.all(hi <= [657, -416, -160]):
        selected.append(p)
whole = trimesh.util.concatenate(selected)
whole.apply_translation([-632.5, 441, 204.928436279297])
mask = (whole.triangles[:, :, 2].min(1) >= -20.0001) & (whole.triangles[:, :, 2].max(1) <= 0.0001)
flange = whole.submesh([np.flatnonzero(mask)], append=True)
flange.apply_scale(0.001)
flange.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=7)
flange.fix_normals()
post = next(
    p.copy() for p in parts if np.allclose(p.extents, [30, 30, 1500], atol=0.001) and p.bounds[0, 0] < 1
)
post.apply_translation([-15, 485, 1530])
post.apply_scale(0.001)
post.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=7)
post.fix_normals()
for name, obj in [("araki_bt_flange", flange), ("araki_3030_post", post)]:
    sc = trimesh.Scene()
    sc.add_geometry(obj, node_name=name, geom_name=name)
    sc.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    sc.export(out / (name + ".glb"))
    record["parts"].append(
        {
            "name": name,
            "faces": len(obj.faces),
            "bounds_m": obj.bounds.tolist(),
            "watertight": obj.is_watertight,
            "adaptation": "complete original component selection; no cross-section deformation",
        }
    )
(out / "toolrack_preparation.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
