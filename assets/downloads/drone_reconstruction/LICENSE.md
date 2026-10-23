# Drone service asset attribution

The licenses below apply to their respective assets, not to the whole repository.
The scene is a teaching fixture adapted from these sources; no author or
manufacturer endorsement, electrical certification or flight-equivalence is claimed.

## PX4 X500 frame and 5010 motor parts

- Model: NXP HoverGames / X500 base, `PX4/PX4-gazebo-models`.
- Model author in `model.config`: Benjamin Perseghetti.
- Copyright (c) 2022, Rudis Laboratories. BSD 3-Clause.
- Frozen commit: `e5997f455e33ec071c7c677fc59a65781de496a4`.
- [Model directory](https://github.com/PX4/PX4-gazebo-models/tree/e5997f455e33ec071c7c677fc59a65781de496a4/models/x500_base)
- [Model-specific license](https://raw.githubusercontent.com/PX4/PX4-gazebo-models/e5997f455e33ec071c7c677fc59a65781de496a4/models/x500_base/LICENSE)
- Complete notice and disclaimer: `px4/LICENSE`. Original config, SDF, 3 Collada
  models and the supplied CF.png are retained in `px4/`.
- Changes: selected complete structural components; removed tall landing gear,
  camera/antenna rails and controller assembly; original UVs retained; dark PBR
  carbon/aluminium materials. Frame scaled uniformly by 0.22/0.174. Motors keep
  their original metre scale and the published base/bell offset.

## Tattu Battery Pack

- Author: [bhaktaj](https://sketchfab.com/bhaktaj).
- [Original model](https://sketchfab.com/3d-models/tattu-battery-pack-517d88706c494d2a9e67dd3e2c2c4baf).
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Original public API license receipt: `tattu_metadata.json`.
- [Public Objaverse GLB](https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-047/517d88706c494d2a9e67dd3e2c2c4baf.glb).
- Changes: retain complete wrapped-body connected components (1,573 triangles);
  omit complete external lead/plug components; PBR remap; two copies uniformly
  scaled by 0.00049 source units into a teaching contact cassette. The result is
  not a product claim for Tattu capacity, topology, dimensions or wiring.

## Battery Replacement - LIPO

- Author: [Jayden Downes](https://sketchfab.com/jaydendownes).
- Description from the author: SYMA x25Pro LIPO Battery converter.
- [Original model](https://sketchfab.com/3d-models/battery-replacement-lipo-b53f8463a15148ceb81779b8059d881f).
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Original public API license receipt: `jayden_converter_metadata.json`.
- [Public Objaverse GLB](https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-032/b53f8463a15148ceb81779b8059d881f.glb).
- Changes: select the complete lower `Object_2` shell; uniform source-unit scale
  0.0015; rigid translation and polymer PBR. The other exploded source part is
  preserved in the original file but is not duplicated or overlapped in scene.

Complete CC BY 4.0 legal text is retained in `CC-BY-4.0.txt`. Attribution and the
change notices above must accompany redistributed derived model assets.

## Previously acquired sources reused without duplicate originals

- emaitee, "knob", CC BY 4.0: source and original license metadata are in
  `../control_panel_reconstruction/emaitee_knob.glb`, `LICENSE.md` and
  `emaitee_knob_metadata.json`. Only a rigid normalization and uniform 1.5 scale
  are used for GUARD. The fixed shaft support is independently authored.
- Poly Haven CC0: `WoodenTable_03`, `retro_multimeter`, `flathead_screwdriver`,
  `screwdrivers_02` and `concrete_floor_worn_001`, from the existing project pool.
  Original assets and receipts remain in `../polyhaven/`; no source is relabeled.
- New fixture plates, bearings, stops, inspection ring, labels and supports are
  HoloCue teaching geometry. They are not claimed as parts of the source products.
