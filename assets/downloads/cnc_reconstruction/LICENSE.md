# CNC model attribution and licenses

## CNC Tool Holder Assembly

- Author: **vincent.leung**; source display association **UBC-3D-Resources**.
- Title: **CNC Tool Holder Assembly**. Source description: **HSK Chuck with Tapered Collet & Locknut**.
- Original page: https://sketchfab.com/3d-models/cnc-tool-holder-assembly-a0475decb5f34656a51aa8140825f1a7
- Author profile: https://sketchfab.com/vincent.leung
- License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/ ; legal terms https://creativecommons.org/licenses/by/4.0/legalcode
- License evidence: `ubc_holder_metadata.json` is the public model API response identifying the author, UID, download availability and license.
- Redistribution here: `ubc_er_components.glb`, a modified extraction of the complete locknut, collet and cutter. Changes: assembled frame-1 baking, component selection excluding the HSK chuck, vertex merging, documented mesh decimation, 1024-pixel texture limit and the scene's rigid/uniform transform and material scalar assignment. The asset derivative remains CC BY 4.0. The source author does not endorse this adaptation.

## Toolrack

- Author: **Shinya.Araki**.
- Title: **Toolrack**. Source description: **BT30 tool rack**.
- Original page: https://sketchfab.com/3d-models/toolrack-882a0f9e78d84853b02d48b1068ad086
- Author profile: https://sketchfab.com/Shinya.Araki
- License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/ ; legal terms https://creativecommons.org/licenses/by/4.0/legalcode
- License evidence: `toolrack_metadata.json` is the public model API response identifying the author, UID, download availability and license.
- Redistribution here: the unchanged `toolrack.glb` and derived `araki_bt_flange.glb` / `araki_3030_post.glb`. Changes to derivatives: complete component selection, rigid recentering, mm-to-m conversion and normal/axis handling. Scene composition additionally rotates the full cart wheel-down, assigns grey metal and nonmetal tyre materials, uniformly enlarges the flange by 63/46 and the extracted upright by 1.11. All source geometry derivatives remain CC BY 4.0. The author does not endorse this adaptation.
- A later actual-face check found inward winding in the open extracted flange. The scene builder reverses the complete flange's winding/normals without changing source positions, scale, contact planes or the retained source files.

The public Objaverse/Hugging Face files are the delivery mirrors. The permissions above come from the **individual source model licenses**, not from Objaverse code or dataset packaging. Actual files were downloaded and opened in real Blender. Download URLs and source hashes are preserved in `sources.json`.

## Existing shared assets

- Adafruit aluminum enclosure **2230**: MIT, with original copyright and license text retained at `../control_panel_reconstruction/LICENSE.md` and its linked source records. This directory does not duplicate the original STEP.
- **EMAITEE** knob: CC BY 4.0, with source title, original URL and attribution in `../control_panel_reconstruction/LICENSE.md` and `../control_panel_reconstruction/sources.json`. It is reused read-only here with a rigid transformation and uniform scale.
- Poly Haven **WoodenTable_03, metal_toolbox, ratchet_wrench, lubricant_spray, concrete_floor_worn_001**: CC0, https://polyhaven.com/license ; existing project asset-pool provenance is retained. The source pool is referenced, not re-downloaded or relicensed.

## Authored adapters and scripts

The teaching shank, retention stud, receiving fixtures, support structure, display details and magazine disk are project-authored additions. Public manufacturer dimension tables are factual design references only; manufacturer CAD, drawings and logos are not redistributed here. These attributions apply to the listed asset files and their derivatives and do not change the license of the rest of HoloCue. Preparation and builder scripts retain the project's existing code-license treatment.
