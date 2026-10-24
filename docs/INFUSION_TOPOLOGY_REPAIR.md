# Infusion ward surface repair

This adaptation retains the licensed medical models, their exterior detail,
textures and transforms. It changes only `infusion_ward` asset construction and
the resulting meshes. The complete scene contract, prompts, object poses,
inspection views, insertion endpoint, guide dimensions, rotation axis and
rotation angle remain unchanged.

The repaired exports contain 92 render nodes. Of these, 89 are oriented closed
solids after joining identical positions; the three existing flat textured
identification/status decals keep their original decal classification. All 29
genuine invalid nodes in the original topology diagnosis now have actual closed
render geometry. The other 13 originally flagged nodes were UV/normal seams or
the receiver-case degenerate-face issue. Audit classification was corrected
separately; no audit exception is introduced by this builder.

| Component | Actual geometry change |
| --- | --- |
| Two water bags | Retain every exterior triangle and UV. Add a 0.10 mm inward film and annular rims around the two existing outlets; neither outlet receives a cap. |
| Curved bag labels | Preserve the printed front and reviewed texture. Add a 0.03 mm back and edge wall. Sub-picometre clipping discrepancies are canonicalized before extrusion; float32 front positions are unchanged. |
| Three flow arrows | Preserve the seven-point outline. Triangulate the shaft/head connection without T junctions and add a 0.04 mm paint layer ending at the existing handle face. |
| Receiver case | Remove four collinear zero-area triangles and split their four adjacent real triangles at the existing intermediate vertices. The exterior surface and all source points are retained. |
| Blue control panel | Bridge three pairs of 18-edge aperture rims with real bore walls. Recover the final 52-edge material interface from 50 existing neighboring-button triangles. |
| Screen, frame and buttons | Add a 0.15 mm screen back, a 0.08 mm frame back with the screen opening retained, and the missing button backs. Orient the completed volumes outward. All remain left of the cassette channel. |
| Monitor | Restore the documented three/four-edge missing surface patches without replacing the head geometry or texture. |
| Cart frame and cross-ties | Add 0.8 mm inward tube walls while retaining their open bores. |
| Cart caster brackets, spring washers, tray-support rods and end plugs | Restore their missing component backs from the existing boundary vertices. These are not the functional bag or cassette openings. |
| Cart base | Retain the four original closed 260-face bodies. Trim four opposed-face, zero-thickness source burrs, eight faces total. They protruded about 0.15 mm from the body; this is an explicit local exterior change, not duplicate-body-face removal. |
| Four stand wheels | Loft the missing lower tread through each wheel's two original 11-point curved side profiles and eight-point axial borders. The curved patch retains the source floor-contact positions. Close the separate near-planar eight-edge mounting back. |

`scripts/scenes/infusion_topology.py` is confined to this builder. Each repair
checks its documented boundary pattern and refuses an unrecognized source.
Original downloaded assets remain untouched. The finite walls and patches are
part of the exported visual meshes, not bounding boxes, convex hulls or private
collision substitutes.

## Validation

The affected checks are:

```sh
HOLOCUE_SCENE_SET=reconstructed .venv-simulation/bin/python -m pytest -q \
  tests/test_infusion_topology.py tests/test_dive_infusion_assets.py \
  -k 'infusion_ward or test_cassette_four_real_guide_pins_enter_open_receiver_bores'
```

They cover the actual emitted assets, topology coverage, original bag exterior
and texture, both open outlets and finite film thickness, nondegenerate case
faces, physical labels/arrows, control volumes, the complete original contract,
support contact, the original insertion keyframes plus 61 sampled poses, 37
rotation poses, original inspection views, label visibility, and all four open
guide bores. These finite geometric checks do not establish continuous dynamics
or model/UI execution. Blender, Viser and live end-to-end evidence belong to the
separate affected-scene batch validation.
