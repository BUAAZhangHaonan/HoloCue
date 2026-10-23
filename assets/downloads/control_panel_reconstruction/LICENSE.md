# Control-panel source assets and adaptations

## Adafruit enclosure and potentiometer: MIT

Original author: Adafruit Industries, copyright (c) 2016. Source repository: https://github.com/adafruit/Adafruit_CAD_Parts , pinned revision `c128bceb1f96b6ea8b68f250bda986ba85da24ea`. The repository's MIT license was read at that revision and is preserved verbatim in `Adafruit_MIT_LICENSE.txt`.

- `adafruit_2230.step`: unchanged original `2230 Extruded aluminum box 94mm/2230 Extruded aluminum box 94mm.step`.
- `adafruit_562.step`: unchanged original `562 10K Potentiometer/562 10K Potentiometer.step`.
- `adafruit_2230_zup.glb`: an uncut mesh conversion of the original enclosure. Units are metres; this reusable source is explicitly Z-up. Its three nodes are `extrusion`, `end_cap_positive_x` and `end_cap_negative_x`, corresponding to original solids 0, 1 and 2. Source millimetre coordinates are transformed rigidly by `(X,Y,Z) -> (-(Z-45.25), Y-14.4, X-41.4)/1000`. There is no per-axis scaling. The resulting bounds are +/- [0.04675, 0.0144, 0.0414] m. Tessellation uses 0.05 mm linear and 0.12 rad angular tolerance, with hard-edge normals and scalar PBR materials added for visualization.

The control-panel C derivative preserves the enclosure's original dimensions. Four finite bores, insulating bushings, four metallic teaching terminals and an asymmetric yellow indexing key are added on its +Y broad face. The key front passes through the original inspection point [0, .039, 0] m. These are HoloCue teaching interfaces, not a claim that Adafruit manufactures this connector assembly. End-cap screws and the stationary mounting plate are scene additions. The separate connector-scene builder may reuse the same original source with its own documented adaptation.

The potentiometer's source solid 2 is the rotating shaft. The other six solids remain fixed below the control panel. The source solids are converted from millimetres without shape distortion; a small shaft sleeve adapts the teaching cap.

## Knob by emaitee: CC BY 4.0

**Knob by emaitee**, originally published on Sketchfab on 2021-07-19: https://sketchfab.com/3d-models/knob-84d5f9911fdd4ada838a230d931926ee . The official model API's `license.url` is `http://creativecommons.org/licenses/by/4.0/`, and the current author/license receipt is preserved in `emaitee_knob_metadata.json`. The full license is in `CC-BY-4.0.txt`.

`emaitee_knob.glb` is the unchanged public archived GLB acquired through Objaverse/Ai2: https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-086/84d5f9911fdd4ada838a230d931926ee.glb . Objaverse's dataset documentation distinguishes the dataset's ODC-BY license from the individual objects' Creative Commons licenses: https://huggingface.co/datasets/allenai/objaverse . The individual model's CC BY 4.0 governs this reuse. No account, purchase, login bypass or private download endpoint was used.

The author describes a cap for a 100k potentiometer. Its authored flutes, shaft cavity and top geometry are retained. The numeric source coordinates are centered, rotated to the task's +Z rotary axis and uniformly scaled by .0032 (A) or .0034 (B) to fit the training envelope. This is a teaching-size adaptation, not certified vendor metrology. The original single material is replaced with scalar polymer PBR; a white pointer and a finite shaft sleeve are added. Derived knob geometry must retain the author, source link, CC BY 4.0 license and this modification notice. It is not relicensed as CC0.

## Existing shared environment pool

The bench, multimeter, circuit board, screwdriver and concrete floor maps reuse the existing Poly Haven CC0 pool. Their original source and download receipts remain in `assets/downloads/SOURCES.md`, `assets/downloads/polyhaven/polyhaven_download_log.json`, and the project's existing license record. Referenced asset IDs are `WoodenTable_03`, `retro_multimeter`, `circuit_board`, `flathead_screwdriver`, and `concrete_floor_worn_001`. No duplicated texture or model download is introduced here. The clean ESD mat, mounting panel, graduations and finite task interfaces are original scene additions.

The source records do not claim electrical functionality, certified assembly tolerances or real-device validation. Final geometry, contacts and interaction anchors are checked separately in the exported teaching scene. The selected models contain no source texture maps; their PBR colors are visualization materials rather than measured optical properties. Other project code and assets keep their existing licenses.
