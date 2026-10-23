"""Prepare licensed model components without changing their source proportions.

Run with the guarded project Python after convert_px4.py wrote its Blender
intermediates to --converted-dir. Derived GLBs use standard glTF Y-up.
"""

from pathlib import Path
import argparse, json, hashlib
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
R = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])


def load(path):
    s = trimesh.load_scene(path, process=False)
    s.apply_transform(R)
    return s


def parts(scene):
    for n in scene.graph.nodes_geometry:
        t, g = scene.graph[n]
        original = scene.geometry[g]
        m = original.copy()
        m.apply_transform(t)
        if hasattr(original.visual, "vertex_attributes") and "color" in original.visual.vertex_attributes:
            m.visual.vertex_attributes["color"] = np.asarray(
                original.visual.vertex_attributes["color"]
            ).copy()
        yield n, m


def material(mesh, name, color, metal=0, rough=0.5):
    mesh.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(
            name=name,
            baseColorFactor=[*color, 255],
            metallicFactor=metal,
            roughnessFactor=rough,
            doubleSided=False,
        )
    )
    return mesh


def save(scene, name):
    scene = scene.copy()
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    scene.export(HERE / name, include_normals=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--converted-dir", type=Path, required=True)
    a = p.parse_args()
    source = load(a.converted_dir / "source_frame.glb")
    frame = trimesh.Scene()
    receipt = []
    for n, m in parts(source):
        if n not in ("CarbonFiber", "Metal"):
            continue
        connectivity = m.copy()
        connectivity.merge_vertices(merge_tex=True, merge_norm=True)
        cc = trimesh.graph.connected_components(connectivity.face_adjacency, nodes=np.arange(len(m.faces)))
        wanted = set(range(1, 14)) | {22} if n == "CarbonFiber" else set(range(32))
        for i, ids in enumerate(cc):
            if i not in wanted:
                continue
            piece = m.submesh([ids], append=True, repair=False)
            # Keep original UVs and its supplied CF.png weave. Darkened PBR tint is
            # intentional; the original Collada material imports as nearly white.
            if n == "CarbonFiber":
                old = piece.visual.material
                piece.visual.material = trimesh.visual.material.PBRMaterial(
                    name="Rudis_carbon_weave",
                    baseColorTexture=old.baseColorTexture,
                    baseColorFactor=[65, 68, 71, 255],
                    metallicFactor=0.08,
                    roughnessFactor=0.48,
                    doubleSided=False,
                )
            else:
                material(piece, "Rudis_aluminium_clamp", (83, 91, 99), 0.78, 0.29)
            name = f"Rudis_{n}_{i:02d}"
            frame.add_geometry(piece, node_name=name, geom_name=name)
            receipt.append({"name": name, "faces": len(ids), "source_bounds_m": piece.bounds.tolist()})
    save(frame, "px4_frame.glb")
    for source_name, target in [("5010Base", "px4_5010_stator.glb"), ("5010Bell", "px4_5010_bell.glb")]:
        s = trimesh.Scene()
        for n, m in parts(load(a.converted_dir / f"{source_name}.glb")):
            material(m, "Rudis_" + n, (126, 132, 137) if n == "Stator" else (42, 46, 51), 0.83, 0.30)
            s.add_geometry(m, node_name="Rudis_" + n, geom_name="Rudis_" + n)
        save(s, target)
    # Source COLOR_0 is normalized float; partition uniform-color faces into
    # PBR regions so Trimesh's uint8 cast cannot silently erase the colors.
    battery = trimesh.Scene()
    palette = [
        ("cable_black", (24, 24, 24), 0),
        ("cable_red", (180, 47, 32), 0),
        ("XT_insulator", (223, 174, 35), 0),
        ("XT_contacts", (183, 158, 94), 0.85),
        ("wrapped_pack", (47, 52, 58), 0),
    ]
    for _, m in parts(load(HERE / "tattu_battery.glb")):
        colors = np.asarray(m.visual.vertex_attributes["color"])
        unique = np.unique(colors, axis=0)
        assert len(unique) == 5
        face_colors = colors[m.faces]
        assert np.max(np.ptp(face_colors, axis=1)) < 1e-7
        for value, (name, color, metal) in zip(unique, palette):
            ids = np.flatnonzero(np.all(face_colors[:, 0] == value, axis=1))
            part = m.submesh([ids], append=True, repair=False)
            material(part, "bhaktaj_" + name, color, metal, 0.52 if not metal else 0.29)
            battery.add_geometry(part, node_name="bhaktaj_" + name, geom_name="bhaktaj_" + name)
    save(battery, "tattu_battery_pbr.glb")
    pack = trimesh.Scene()
    for n, m in parts(battery):
        if n not in ("bhaktaj_wrapped_pack", "bhaktaj_cable_black"):
            continue
        c = m.copy()
        c.merge_vertices(merge_tex=True, merge_norm=True)
        cc = trimesh.graph.connected_components(c.face_adjacency, nodes=np.arange(len(m.faces)))
        for i, ids in enumerate(cc):
            piece = m.submesh([ids], append=True, repair=False)
            if piece.bounds[0, 1] > -100 and piece.bounds[1, 1] > 80 and len(ids) > 100:
                material(
                    piece,
                    "bhaktaj_pack_wrap_" + str(i),
                    (48, 53, 58) if n == "bhaktaj_wrapped_pack" else (28, 31, 34),
                    0,
                    0.50,
                )
                pack.add_geometry(piece, node_name=n + "_body", geom_name=n + "_body")
    assert sum(len(m.faces) for m in pack.geometry.values()) == 1573
    save(pack, "tattu_pack_body.glb")
    (HERE / "preparation.json").write_text(
        json.dumps(
            {
                "method": "Whole connected component selection; original UVs retained; material remap only; no per-axis scaling or mesh replacement.",
                "frame_components": receipt,
                "excluded": "Complete tall landing legs, camera/antenna rails, flight controller and rubber mounts. Propellers were not downloaded.",
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("*.glb")},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
