# CNC teaching station asset reconstruction

This scene combines authored industrial assets with explicitly identified teaching interfaces. It is an isolated tool-change trainer, not a manufacturer-certified machine or a dimensional BT40 assembly. The original `cnc_toolchange/scene.json` is unchanged.

## Reused models and changes

| Source | Actual use | Changes |
|---|---|---|
| **CNC Tool Holder Assembly — vincent.leung** (the source page is also associated with UBC-3D-Resources), Sketchfab `a0475decb5f34656a51aa8140825f1a7`; original description **HSK Chuck with Tapered Collet & Locknut** | Complete ER locknut, slotted collet and carbide cutter in T09 and T03 | Bake the real source animation at frame 1, when assembled; exclude the entire HSK chuck body. Join source chunks belonging to each complete component, merge coincident vertices, make a documented Blender decimation LOD, and cap textures at 1024 pixels. Rigid orientation and **one uniform scale 0.030** are applied to all three parts together. Original UV maps remain. Metal/roughness scalars are assigned for the scene. |
| **Toolrack — Shinya.Araki**, Sketchfab `882a0f9e78d84853b02d48b1068ad086`; source description **BT30 tool rack** | One actual source V-groove flange in each tool; source 3030 uprights for the isolated display mounts | The original 46 mm flange is uniformly scaled by **63/46**; its V groove and opposed drive notches remain. The extracted 1.5 m upright is uniformly scaled **1.11**, retaining its cross section. The current builder repairs their source end surfaces while preserving functional bores and T slots; the complete cart was used in the initial reconstruction but has since been replaced by the existing Poly Haven tool_cart. |
| Adafruit aluminum enclosure 2230, already licensed under `../control_panel_reconstruction/LICENSE.md` | PANEL's actual extrusion and both end caps | Rigid reorientation, metre conversion and uniform **2.4** scale. An actual screen window is cut in the extrusion. A recessed display, keys and case fasteners are teaching additions. |
| EMAITEE knob, already licensed under `../control_panel_reconstruction/LICENSE.md` | MODESWITCH's complete ribbed knob | Rigid normalization, metre conversion and uniform **3.0** scale. The small rotation spindle and white pointer are teaching additions. |
| Existing Poly Haven pool, CC0 | WoodenTable_03, metal_toolbox, ratchet_wrench, lubricant_spray, tool_cart and concrete_floor_worn_001 | Rigid orientation followed by uniform fit; tool_cart retains metre-scale source dimensions. The ratchet is laid flat before fitting. No rusted diamond plate is used for the worktop. |

The source cart's whole-scene preview initially obscured the small tool: the later isolated real Blender preview verified a V groove and two drive notches. Only that complete flange region is used in T09/T03. The source's cylindrical upper stem is not presented as a true taper. The initial reconstruction separately reused the complete Araki cart as background equipment; the current scene uses Poly Haven tool_cart because the Araki cart's disconnected CAD surfaces did not meet closed-solid coverage.

Formal exported-mesh contact checks exposed inward winding in the extracted open CAD flange: all 128 underside triangles pointed +Z, and the broad outer wall also faced inward. The initial orientation correction preserved the open seams. The subsequent closed-solid repair retains the actual underside at local z = −0.015 m and preserves the source exterior walls, grooves and notches, while retessellating the source end surfaces. [Current repair details](../../../docs/CNC_TOPOLOGY_REPAIR.md) distinguish retained original corner normals on the mature background assets from normals on new repair surfaces and existing CAD hard-edge handling. They also document the two bounded cutter fragments removed from the rendered derivative and the corrected first-attempt shading defect. Original downloaded sources remain unchanged.

## Teaching interfaces and preserved geometry contracts

The 7/24 external shank, ER seat, wrench hex and retention stud are authored adapters. The basic shank proportions use the public [Falcon BT/DIN ISO 7388-2 dimension table](https://www.falcontoolings.com/bt-din-iso-7388-2-shank-detail.php): D 44.45 mm, flange D1 63 mm and taper length 65.4 mm for the BT40 reference. No manufacturer CAD or drawing is redistributed. The resulting assembly is described as mature ER components plus a teaching shank, not as the source HSK body renamed BT30 or a commercial matched toolholder.

- T09/T03 are 0.2048 m high with a 0.063 m flange. The original task dimensions remain 0.075 × 0.075 × 0.21 m.
- The **actual source flange underside remains local z = −0.015 m**, supported at world z = **1.085 m initially** and **1.240 m after insertion**. The cutter tip is local z = −0.100 m and never serves as the stop.
- Initial supports use an open base, three columns and an annular shoulder so the mature locknut and cutter are visible. POCKET9 has a true open 24.2 mm radius cavity, replaceable seat and four real counterbores. The counterbore floor is local z .075 m and its screw head is .077 m, below the .080 m upper face.
- The stud has an actual wrench hex, 5.6 mm radius neck through the original z .091 m inspection plane, an 8.8 mm radius head and a top at .1048 m. The original inspection point, normal and extent remain unchanged.
- MODESWITCH preserves the original local Z rotation axis and original Rx90 pose. Its stationary bearing is in the environment, separate from the complete moving cap, spindle and pointer.
- MAG and PANEL meet fixed rear mounting faces rather than floating. Their front openings and display are actual geometry. MAG is an authored isolated teaching disk, not falsely attributed to the source cart.

## Reproduction

Fixed download URLs, hashes, metadata and licenses are in `sources.json` and `LICENSE.md`. The original 235 MB UBC download is not duplicated in the formal asset tree; the actually used complete components and their source receipts are retained here. Obtain the original file at the exact URL and verify its SHA256 before rerunning preparation.

Use Blender 3.1.2 for the UBC extraction:

```text
blender -b -t 4 --python assets/downloads/cnc_reconstruction/prepare_ubc.py -- <downloaded-original.glb> <output-directory>
blender -b -t 4 --python assets/downloads/cnc_reconstruction/check_ubc_lod.py -- <downloaded-original.glb> <output-directory>/ubc_er_components.glb <output-directory>/ubc_lod_check.json
python assets/downloads/cnc_reconstruction/prepare_toolrack.py <this-directory>/toolrack.glb <output-directory>
```

The parent build calls `scripts/scenes/rebuild_cnc_assets.py:build(spec)`. All preparation or preview output and caches must remain in the task's authorized scratch directory when reproducing this work. The saved source-frame and component selection logic are in the preparation scripts, not in an undocumented manual edit.

## Detail and quality limits

The original retained ER components had 971,602 / 933,822 / 145,906 triangles. The prepared GLB imports as **18,000 / 24,000 / 13,998 triangles**. `ubc_preparation.json` records the pre-export modifier counts; two degenerate cutter triangles disappear in the actual exported GLB. `ubc_lod_check.json` measures 12,000 deterministic area samples in each direction per component at final scene scale: the largest sampled errors are **0.171 mm** for the nut, **0.303 mm** for the collet and **0.236 mm** for the cutter; the respective bidirectional 99th-percentile errors are at most **0.060 / 0.078 / 0.033 mm**. These are sampled nearest-surface distances, not a global Hausdorff guarantee or machining tolerance.

The authored adapters and educational disk remain simplified. Original source CAD includes open seams, and the scanned ER components include surface irregularities. The current rendered derivatives pass the documented closed-topology checks; this does not establish production machining accuracy or continuous contact dynamics. Candidate Blender inspection and limited author contact rays remain separate from exported-mesh trajectory tests and real Blender/Viser review.
