# Dive fill station — attributed source components

This is a **depressurized, disconnected teaching assembly**. It is not a manufacturer's SCUBA filling system, a pressure-rated design, or a specified DIN/BSP adapter. The original HoloCue object identities, poses, envelopes, mating frame, inspection frame and ordered task are preserved in `scenes/dive_fillstation/scene.json`.

## Original assets and permissions

All three original model pages and Sketchfab model API receipts were checked on 2026-10-23. Each receipt identifies the model as downloadable under **Creative Commons Attribution 4.0**. `sources.json` records the exact public archive download, original page, original author, byte count and SHA-256. Original GLBs and metadata remain beside this file. `CC-BY-4.0.txt` contains the license. The archive/dataset's software license is not used as the model license.

| Original work | Author | Primary page | Retained original |
|---|---|---|---|
| Oxygen Cylinder | Alexander Troianovskyi (AlexOlTroi) | https://sketchfab.com/3d-models/oxygen-cylinder-e7419671f8124cab870d7a1a4d68b180 | `oxygen_cylinder_original.glb` |
| 2Piece-ball-valve-BSP-female | Freek de With | https://sketchfab.com/3d-models/2piece-ball-valve-bsp-female-b0773be701fc4c6ba7fc0c3389bd5c79 | `bsp_ball_valve_original.glb` |
| Pressure gauge | takeboncog | https://sketchfab.com/3d-models/pressure-gauge-95cf5b63b15549a2a173bb480577b6a9 | `pressure_gauge_original.glb` |

Original downloads are public Objaverse GLB archives hosted by `allenai/objaverse` on Hugging Face; the individual authors' current model metadata supplies the permission. No paid purchase, account-only download, or unlicensed manufacturer's CAD is included.

The support frame also reuses the complete 3030 extrusion mesh from **Toolrack, Shinya.Araki**, stored at `../cnc_reconstruction/araki_3030_post.glb`. Its original source and CC BY 4.0 attribution are in `../cnc_reconstruction/README.md`, `sources.json`, and the accompanying license. The concrete floor uses the existing **Poly Haven hangar_concrete_floor (CC0)** material pool; it does not change that source or its license.

## Extraction and modifications

`prepare_sources.py` runs against the retained originals in this directory. It verifies their recorded hashes and licenses, and writes `cylinder_body.glb`, `pressure_gauge_aligned.glb`, and `preparation.json`. Run it with the project's simulation Python and the approved project-local temporary/cache environment. No download or scratch-only script is needed to reproduce the extraction.

- **Cylinders:** select the complete 840-triangle connected cylinder body from Alexander Troianovskyi's model, preserving original faces, UVs and PBR textures. Omit the trolley, regulator and other disconnected source components. Rigidly center the body, then uniformly scale its 1.3578672017 m source height to 0.735 m. The resulting diameter is about 0.1494 m; it is not stretched to the 0.19 m allowed envelope. This original is a generic medical oxygen cylinder, not a SCUBA manufacturer's bottle. A conforming front teaching sticker covers the original medical marking. It clips actual source triangles only on the plain cylindrical region Z=0.125..0.219 m, below the source neck grooves at Z=0.220233/0.226636 m; its upper blank band passes behind the existing clamp while both text lines sit below it. No stacked coplanar decal layer is added; a removable, curved-backed training plaque and clamp bands carry the required rear label. The original rear inspection plane remains Y=0.094 m. The actual decal is at Y=0.09393 m. Each rear decal says exactly `TRAINING` and its own `BOTTLE1`, `BOTTLE2` or `BOTTLE3`. The BOTTLE1/2 necks receive short, unpressurized hex-socket blanks within the unchanged height allowance.
- **VALVE:** reuse the complete fixed source body, end cap and both helical thread components (`Body3_`, `Body4_`, `Body6_`, `Body7_`) at uniform scale 0.88. Rotate the original X flow axis rigidly onto local +Y. Add only a small static spindle cover and a neck-mounted teaching bridge. Preserve visible real thread geometry and the open receiving mouth.
- **QRC:** reuse the complete source end cap and thread (`Body4_`, `Body6_`) at the same uniform scale. Face this component in the opposite rigid direction, with translation Y=-0.04392 m, so the real hexagonal bearing face enters its final seat before the wider round collar. The finite brass-colored teaching spigot has an 8 mm open through bore; its nose radius is 12.5 mm, tapering to 11.8 mm at the unchanged local Y=0.045 m mating plane. Its shoulder is local Y=0.03204 m. At the original goal [0.35,-0.009,1.0], the shoulder meets the actual receiver mouth at world Y=0.02304 m. This is explicitly an unpressurized teaching adapter, not a claim that the source BSP female fitting is a ready-made DIN product.
- **STEM:** separate the complete original steel lever, grip, nut and spindle from the complete fixed valve body. Apply one rigid orientation and uniform scale 0.35. The original spindle maps to the unchanged local -Y task axis. A 3.5 mm axial stand-off, fixed annular bearing and short spindle extension clear the original mechanical stop throughout the required +90 degree teaching rotation. The source meshes themselves are not cropped to fake clearance. The fixed hardware uses an open plate bracket with narrow side webs, not a solid placeholder block. Its visible nuts reuse the source fastener uniformly.
- **GAUGES:** keep both complete source meshes and their embedded textures. Remove the archive's presentation rotation, align the original dial normal +Z to the station front -Y, and uniformly scale by 0.0399. Repeat this complete gauge three times. Correct the source glass material's metallic factor to zero and set roughness to 0.14; retain its authored texture transparency. These are static, visibly near-zero teaching dials, not a pressure simulation. Real mounting holes are cut into the backplate.
- **Frame and task fixtures:** the source 3030 extrusion is uniformly scaled for each length. Finite plates, clamps, seat pads, isolated tubing and storage supports are teaching fixtures. They preserve the existing task layout and are not represented as manufacturer-supplied parts.

## Actual support and interfaces

The bottle source has multiple downward-facing horizontal regions. The seat uses the **lowest actual planar bottom**, about local Z=-0.3657912 m, rather than the higher shoulder or the AABB's lower rim. Its lower face rests on the rack's Z=0.18 m deck. The outer low rim is left unobstructed.

QRC and VALVE seats are copied from genuine downward source hex faces at local Z=-0.0176 m. QRC's initial bearing plane is world Z=0.8724 m and its final bearing plane is world Z=0.9824 m. The final seat is carried by the bridge connected to BOTTLE3's actual neck top. The broad, lower round collar remains outside these seats. This provides vertical support rather than merely axial end-face coincidence.

The source CAD contains material-split open lever surfaces; they remain present, and no open surface is discarded from obstacle checks. Original source files are unmodified. Source body geometry and scale are distinguished from the locally authored teaching interfaces above.

## Validation boundary

Author checks use exported candidate GLBs, actual opposing triangle faces and the unchanged finite insertion/rotation poses. Real Blender CPU previews cover the workspace, coupling, receiver threads, rear BOTTLE3 label and separate lever bracket. Final formal GLB/native Blender export and independent Blender/Viser inspection are performed by the coordinating build. Geometry checks do not establish pressure integrity, load capacity, continuous dynamic clearance or operational diving safety. No end-to-end task experiment or model execution is part of this reconstruction.
