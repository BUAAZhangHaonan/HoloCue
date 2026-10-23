"""Extract complete attributed source components without reshaping their geometry."""

from pathlib import Path
import hashlib
import json

import numpy as np
import trimesh

OUT = Path(__file__).resolve().parent
selected = {
    "alex_oxygen": "oxygen_cylinder_original.glb",
    "freek_ball": "bsp_ball_valve_original.glb",
    "takebon_pressure": "pressure_gauge_original.glb",
}
sources = json.loads((OUT / "sources.json").read_text())
for record in sources:
    source = OUT / record["file"]
    metadata = json.loads((OUT / record["metadata_file"]).read_text())
    assert metadata["isDownloadable"] and metadata["license"]["slug"] == "by"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
source = trimesh.load_scene(OUT / selected["alex_oxygen"], process=False)
source.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
node = "Oxygen_Cylinder_SM_M_Oxygen_Cylinder_0"
transform, name = source.graph[node]
whole = source.geometry[name].copy()
whole.apply_transform(transform)
welded = whole.copy()
welded.merge_vertices(merge_tex=True, merge_norm=True)
components = trimesh.graph.connected_components(welded.face_adjacency, nodes=np.arange(len(welded.faces)))
selection = []
for indices in components:
    points = welded.vertices[welded.faces[indices]].reshape(-1, 3)
    extents = np.ptp(points, axis=0)
    if len(indices) == 840 and np.allclose(extents, [0.2760122559, 0.2760122471, 1.3578672017], atol=1e-6):
        selection.append(indices)
assert len(selection) == 1
body = whole.submesh(selection, append=True, repair=False)
center = body.bounds.mean(axis=0)
body.apply_translation(-center)
bottle = trimesh.Scene()
bottle.add_geometry(
    body, node_name="Alexander_Troianovskyi_complete_cylinder_body", geom_name="complete_cylinder_body"
)
bottle.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
bottle.export(OUT / "cylinder_body.glb", include_normals=True)

# Both original gauge meshes are in the same author-local frame. The archive
# root contains a presentation rotation; remove that rigid presentation pose,
# then map the source face normal +Z to the station front -Y with Rx(+90).
gauge = trimesh.load_scene(OUT / selected["takebon_pressure"], process=False)
normalized = trimesh.Scene()
for name, mesh in gauge.geometry.items():
    part = mesh.copy()
    part.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    label = "takeboncog_glass" if len(part.faces) == 60 else "takeboncog_complete_gauge_body"
    normalized.add_geometry(part, node_name=label, geom_name=label)
normalized.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
normalized.export(OUT / "pressure_gauge_aligned.glb", include_normals=True)

record = {
    "cylinder_body": {
        "source_node": node,
        "source_connected_component_faces": 840,
        "source_center_translation_m": (-center).tolist(),
        "source_extents_m": body.extents.tolist(),
        "operation": "Select one complete connected cylinder body; preserve faces, UVs, embedded textures and source proportions. Omit original trolley, straps, regulator and gauge.",
    },
    "gauge": {
        "operation": "Preserve both full source meshes and embedded textures; remove only archive presentation rotation and rigidly align author +Z face normal to target -Y.",
        "faces": {name: len(mesh.faces) for name, mesh in gauge.geometry.items()},
    },
    "derived_files": {
        name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        for name in ["cylinder_body.glb", "pressure_gauge_aligned.glb"]
    },
}

(OUT / "preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
