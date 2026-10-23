# Optical bench source assets

## Winters / Shepler open optomechanics

Brandon J. Winters and David Shepler, *3D printable optomechanical cage system with enclosure*, HardwareX 3 (2018), 62–81, DOI: https://doi.org/10.1016/j.ohx.2017.12.001.

- Author repository: https://osf.io/9kt52/
- Institutional publication: https://spark.bethel.edu/chemistry-faculty/2/
- Author-uploaded article copy, including the specifications and design-file license tables: https://www.researchgate.net/publication/322078822_3D_printable_optomechanical_cage_system_with_enclosure
- Public OSF node and license API evidence are retained in `osf_project.json`, `osf_license.json`, and `osf_contributors.json`. The contributor is Brandon J Winters. Downloads were public, without an account or paid transaction, on 2026-10-22.
- Exact original names, source pages, download URLs, and verified download SHA256 values are in `sources.json`. The hashes match the public OSF file metadata.

The OSF node currently specifies **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/). The article's hardware specifications and individual design-file table specify **CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/). We conservatively distribute these CAD files and their HoloCue geometry adaptations under **CC BY-SA 4.0**, retaining attribution and modification notices. The article's separate CC BY-NC-ND publication license is not used as the hardware license. No claim of endorsement is made.

These are real open-hardware printable parts used in the authors' interferometer / spectroscopy apparatus. They are not manufacturer-certified machined optical hardware. The STEP sources are untextured solids in millimetres; scene materials, optics, mounting hardware, labels, and task adapters were added by HoloCue.

| Retained source | Scene use / modification |
|---|---|
| `C02_fixed_lens.step` | L1/L2 optic mount at original scale; only a finite vertical blind post seat is cut. Also used at original scale behind the passive target card. |
| `B01_base.step` | POST2 and L2 receiver body, uniformly scaled 1.5 with a replaceable precision bushing; M stationary base uniformly scaled 0.85. |
| `C13_mirror_base.step` | Two solids: the kinematic base and ball-joint cap. Base retains original proportions and receives a finite vertical post seat; cap is positioned at the carrier joint. |
| `C15_mirror_mount.step` | Separate mirror carrier at original scale, with a 25.4 mm coated optic. |
| `M02_thumb_knob.step` | Original knob profile, uniformly scaled for locking and adjustment hardware. |
| `C04_adjustable_lens.step`, `P01_adjustable_post.step` | Loose spare optical components on the work tray, at original scale. |

**Source issue found:** the downloadable C13 and C14 STEP files have different file hashes but the same two CAD solids. Only the C13 source is retained. Its two solids are separated and instantiated once each; a duplicate full assembly is not overlaid. The original C14 download remains only a scratch inspection input until task cleanup.

The spherical optical lenses, reflective coating, blind insertion bushings, finite post seats, yaw bearing, rear serial tag, passive target card, hold-down adapters, and storage tray are HoloCue additions. L1 remains a vertical shaft insertion into POST2; M's task rotation remains yaw about its original vertical pivot. The source kinematic adjusters do not introduce a new pitch/yaw task. Scene anchors, object poses, capability lists, and task ordering are unchanged.

## OptiCore breadboard

Johannes Hinrichs / CodeFHD, OptiCore commit `f9b0029009846abbf34a0947971dc4c6ba1a21f6`:
https://github.com/CodeFHD/OptiCore/blob/f9b0029009846abbf34a0947971dc4c6ba1a21f6/bl_optomech/table.py

- `opticore_table.py.txt` is the exact downloaded source, retained with its copyright and GPL notice; the text suffix prevents the project's formatter from rewriting this external source.
- `opticore_LICENSE.txt` retains GPL-3.0. The source permits GPL version 3 or any later version.
- `prepare_opticore.py` invokes only the original `add_table` and `add_tableface` functions in Blender, offline, then converts millimetres to metres and exports `opticore_breadboard.glb` as standard Y-up glTF.
- Parameters: 900 × 1400 × 25 mm; 25 mm pitch, 3 mm bore radius; 16 vertices per hole; 6 mm corner radius. Both face openings, chamfers, and cylindrical bores are geometry, not decals or positive cylinders. Threads are not modelled.
- The preparation wrapper and generated board are conservatively distributed under **GPL-3.0-or-later** with the corresponding source and reproduction parameters. This does not claim that arbitrary output from a GPL program automatically inherits the program's license, and does not change the license of other HoloCue code or assets.

The scene builder only loads the generated board. It does not import or copy the GPL generator into shared helpers, modeling, or runtime code. Board UVs are computed from baked Z-up vertices. Its clean satin-aluminum appearance is a HoloCue-authored scalar PBR material (neutral gray, metallic 0.9, roughness 0.34), with no external color, normal, or displacement texture. The earlier weathered floor-plate material was removed after real Blender and Viser inspection showed an inappropriate raised diamond pattern; board geometry and hole openings are unchanged.

## Reused CC0 materials and surroundings

The existing project copies of Poly Haven `WoodenTable_03`, `flathead_screwdriver`, and `concrete_floor_worn_001` are reused. Their meshes / embedded PBR maps remain governed by **CC0**, documented in the project's source records (`assets/raw/engine_round/SOURCES.md`, `assets/downloads/SOURCES.md`). Source pages:

- https://polyhaven.com/a/WoodenTable_03
- https://polyhaven.com/a/flathead_screwdriver
- https://polyhaven.com/a/concrete_floor_worn_001

The package is intentionally not labelled wholly CC0. CAD adaptations, the OptiCore board, and Poly Haven content retain the separate licenses above.

## Rendering limits

The final lens GLBs carry `KHR_materials_transmission` (0.92), `KHR_materials_ior` (1.5168), and low roughness (0.055). They use `alphaMode: OPAQUE` and alpha 1, so physical transmission is not attenuated again by alpha blending. No runtime alpha fallback or emissive overlay is added. The closed lens mesh has two spherical faces and a finite edge. This supplies transparent glass in supported renderers; HoloCue does not compute an optical path, focal spot, calibrated refractive image, or laser emission. TARGET remains a passive alignment reference with the source disabled.
