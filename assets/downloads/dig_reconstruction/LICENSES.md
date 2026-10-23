# Dig-site reconstruction source attribution

The models below are third-party scans used in an archaeology teaching scene.
Their different origins do not represent a documented archaeological assemblage.
The unmodified downloaded GLBs are retained next to this record. Current official
Sketchfab API responses and the archived Objaverse metadata are retained per model.
Individual model licenses, rather than the dataset license, authorize reuse.

## Incised Pottery Sherd

- Creator: **Florida Public Archaeology Network** ([profile](https://sketchfab.com/fpan)).
- Original: [Incised Pottery Sherd](https://sketchfab.com/3d-models/incised-pottery-sherd-d0f4ee864d9749da8cc095f7a794e6fc).
- License: **[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)**, verified in the individual official API response on 2026-10-22; downloadable status was true.
- Downloaded public archive: [Objaverse GLB](https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-020/d0f4ee864d9749da8cc095f7a794e6fc.glb).
- Original file: `fpan_incised.glb`, 139,424 triangles with embedded 1024 px color texture and geometric scan relief. No separate authored roughness/normal maps are claimed.
- The creator describes an early model assembled from two chunks. Both faces were inspected in native Blender; the visible body is continuous, while small disconnected scan fragments remain in the source. No historical dating, provenience, or physical specimen size is supplied by this record.
- Scene changes: rigid PCA orientation, centering, uniform scaling to the training envelope, and non-metallic rough opaque material settings. The original mesh, image and UVs are retained. The smoother inner face points toward local +Y for POT3. No artificial incisions are added.
- POT3 has a fitted AABB approximately 0.13669 x 0.02308 x 0.13000 m, from a uniform factor 0.06415446 applied to arbitrary source coordinates. This is a training size, not a measured archaeological dimension.
- POT1 and POT2 are teaching copies of this same scan at different uniform scales. Their object IDs do not imply different real excavated specimens.

## Cow Bone .::RAWscan::.

- Creator: **Andrea Spognetta (Spogna)** ([profile](https://sketchfab.com/spogna)).
- Original: [Cow Bone RAWscan](https://sketchfab.com/3d-models/cow-bone-rawscan-675694971dcb44e09f32353604a7a01d).
- License: **[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)**, verified in the individual official API response on 2026-10-22; downloadable status was true.
- Downloaded public archive: [Objaverse GLB](https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-101/675694971dcb44e09f32353604a7a01d.glb).
- Original file: `cow_bone.glb`, 439,222 triangles with embedded 1024 px color texture. No separate authored roughness/normal maps are claimed.
- Scene changes: rigid orientation, centering, uniform scaling and non-metallic rough opaque settings. No source shape is flattened or stretched independently by axis.
- Fitted training AABB approximately 0.12941 x 0.04001 x 0.04500 m, factor 0.01437255 applied to arbitrary source coordinates. True specimen measurements are unavailable. This is an animal bone scan used for teaching, not a claim of archaeological human remains.

## Existing CC0 resources reused

All of the following are existing repository resources from Poly Haven, licensed
[CC0](https://polyhaven.com/license). Source geometry and embedded PBR maps remain
in the existing asset pool; this directory does not duplicate that pool.

- [Trowel 01](https://polyhaven.com/a/trowel_01): intact mature tool model, rigidly oriented to its actual support facet and uniformly scaled to the fixed tool envelope. Albedo, OpenGL normal, and ARM maps are retained.
- [Wooden Crate 01](https://polyhaven.com/a/wooden_crate_01): field recording support fixture adapted to the fixed inspection height.
- [Excavated Soil Wall](https://polyhaven.com/a/excavated_soil_wall): actual displacement map drives subdivided excavation and cut-wall geometry; albedo, OpenGL normal and ARM are embedded.
- [Dirt](https://polyhaven.com/a/dirt): pit floor, outside rim and small soil contact beds; displacement is used on the main surfaces.
- [Hessian 230](https://polyhaven.com/a/hessian_230), [Wood Table 001](https://polyhaven.com/a/wood_table_001), [Rubber Tiles](https://polyhaven.com/a/rubber_tiles): recording cloth, tray/tool board and tool mat surfaces.

Small functional fixtures (survey stakes and strings, specimen cloth cradles,
local soil rests and the STAY mounting adapter) are scene-authored. Contact rests follow the
unmodified scan underside. They are supports, not added archaeological features.


## Fixed measuring station and tripod

### Total Station

- Creator: **makercommons** ([profile](https://sketchfab.com/makercommons)).
- Original: [Total Station](https://sketchfab.com/3d-models/total-station-080c4234efa941e4927606811387c9a9).
- License: **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**. The individual official API response retained in `total_station_api.json` confirms this license and downloadable status on 2026-10-22.
- Downloaded public archive: [Objaverse GLB](https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-078/080c4234efa941e4927606811387c9a9.glb). The unchanged file and per-model archive metadata are `total_station.glb` and `total_station_objaverse.json`.
- The scan contains 612,282 triangles in six primitives, an embedded 1024 px color image, an optical body, operating panels, handle and a three-point leveling base. No separate authored normal/roughness maps are claimed. Existing opaque, double-sided, nonmetallic scalar PBR settings and original image/UVs are retained.
- Scene adaptation: one rigid support-plane alignment, orientation toward the excavation, uniform scaling and translation. The source mesh is not stretched or flattened. Training bounds are approximately **0.12353 x 0.12532 x 0.21840 m**. The original source does not establish a measured physical device size; this is the fixed task-scale fit.
- The actual lowest three source vertices define a supporting plane at world **z = 0.6908 m**, preserving the former instrument base height. A small scene-authored tribrach adapter contacts that plane. `STAY` ID, pose, task capabilities and point hint are unchanged.

### Tripod

- Creator: **Artec 3D**. Original and official free download: [Tripod](https://www.artec3d.com/3d-models/tripod).
- The current official asset page links **CC BY 4.0**, while `license.txt` inside the downloaded OBJ archive explicitly grants **[CC BY 3.0 Unported](https://creativecommons.org/licenses/by/3.0/)**. Both original statements are recorded in `artec_tripod_source.json`; the unchanged ZIP and its exact license text are retained as `artec_tripod_obj.zip` and `artec_tripod_license.txt`. This derivative credits Artec 3D under the accompanying CC BY 3.0 notice, without relabeling that file as CC0 or claiming the two version statements are identical.
- Source: Artec Eva HD scan, 1,485,993 vertices and 2,972,238 triangles. The OBJ contains no UV/color/texture file. The scene therefore uses an explicitly authored black-coating scalar PBR material (linear base color 0.035/0.040/0.050, metallic 0.15, roughness 0.50); these are rendering choices, not measured material properties or a claimed source PBR set.
- The scanner-specific upper U bracket is detached at the existing mounting neck, at levelled-source z = 1045 source units. All three telescopic legs, lock collars, braces and feet remain the mature scan geometry. The remaining 2,250,866 triangles are reduced to 450,173 with Blender's 0.20 collapse ratio. The prepared standard Y-up glTF is `artec_tripod_adapted.glb`; the original archive is unchanged.
- After reduction, a new support plane is fitted to three actual foot vertices by rigid rotation. The three foot regions are separated into named nodes, without duplication or replacing them with cylinders. The complete tripod receives one uniform scale and an 82 degree yaw. No leg is independently stretched.
- The top neck reaches approximately **z = 0.6828 m**. The small mounting adapter bridges to the instrument's original **z = 0.6908 m** base. Its lower 0.5 mm engages the cut neck as a socket. The original scanner U bracket is not left hidden inside the instrument.
- Actual foot contacts in world metres: **(0.385193, 1.009664, 0)**, **(0.904745, 1.181425, 0)**, **(0.789599, 0.655246, 0)**. All three are non-collinear and on the outer soil rim; the complete foot meshes have at least **77.7 mm** clearance from the excavation or outside edge. Small soil patches are levelled under these actual feet.
- `stay_fit.json` records the complete source transforms, one scale per mature model, exact contact vertices, foot node names and adapter dimensions. These are training-scene placement data, not a manufacturer metrology certificate. The other six dig-site task objects and all `scene.json` fields are retained.
