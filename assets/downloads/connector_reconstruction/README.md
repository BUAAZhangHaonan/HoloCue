# Connector reconstruction sources and adaptations

This scene is an enlarged, de-energized teaching adapter. Its primary housings
reuse an existing, openly licensed aluminum extrusion CAD model. The four-contact
insert, socket carrier, locating key and mounting pads are task-specific HoloCue
geometry. They are not an Adafruit connector product or a manufacturer-certified
mating pair.

## Shared original CAD

The original source is stored only once, beside the companion control-panel
builder:

- [Original Adafruit 2230 STEP](../control_panel_reconstruction/adafruit_2230.step)
- [Metric rigidly normalized mesh](../control_panel_reconstruction/adafruit_2230_zup.glb)
- [Original MIT notice](../control_panel_reconstruction/Adafruit_MIT_LICENSE.txt)
- [Source record and conversion](../control_panel_reconstruction/sources.json)
- [License and conversion notes](../control_panel_reconstruction/LICENSE.md)

Upstream: [Adafruit CAD Parts](https://github.com/adafruit/Adafruit_CAD_Parts),
commit `c128bceb1f96b6ea8b68f250bda986ba85da24ea`,
`2230 Extruded aluminum box 94mm/2230 Extruded aluminum box 94mm.step`.
Copyright 2016 Adafruit Industries. The original MIT notice is retained at the
link above. No duplicate original STEP is stored in this directory.

The three source solids are the extrusion and its two end plates. The source
unit is millimeters. P/S convert the source extrusion axis to scene-local +Y.
C uses the rigidly normalized, direct Z-up meter mesh. All source scaling is
uniform:

| Object | Source adaptation |
| --- | --- |
| P | 0.78 scale, all three original solids, blue powder-coat appearance; rear end at Y=-0.055 m. |
| S | 0.96 scale; extrusion is cut to the required axial length, front cap omitted, rear cap positioned at Y=0.035 m. Its original internal channels remain. A finite top keyway is cut into the opening. |
| C | 0.89 scale, all three original solids, rigid upright orientation; supported by 1 mm rubber pads. The rear key mount connects the source body to the unchanged inspection plane. |

Source geometry keeps its cross-sectional proportions; there is no independent
axis stretching. The STEP contains geometric CAD, not photographic PBR maps.
The builder assigns plausible scalar polymer, coating, aluminum and brass
materials. Rubber and insulating pieces have metallic factor zero.

## Task interface

IDs, scene JSON, poses, bounding envelopes, task order, mating frames and
inspection definitions remain unchanged. The contact layout is a task-specific
four-contact insert, not a claimed Mini-Fit or Picoflex component.

- P `contact_pin_1..4`: X=±0.014 m, Z=±0.006 m, axis +Y,
  radius 0.0025 m, Y=0.0325..0.055 m; finite chamfered tips.
- P `top_alignment_key`: X=±0.0045 m,
  Y=0.0165..0.0335 m, Z=0.011..0.018 m.
- S `contact_socket_bore_1..4`: matching X/Z centers,
  inner radius 0.0032 m, tube Y=-0.022..0.004 m, with a 0.6 mm mouth chamfer.
  These are open annular solids and the carrier is also drilled through.
- S `Adafruit_2230_open_extrusion_with_keyway`: the opening faces -Y;
  its actual roof is cut over X=±0.0053 m, Y=-0.036..-0.018 m.
- C `rear_yellow_locating_key`: an actual finite yellow solid,
  front surface Y=0.039 m at the original inspection point, with a top notch.
  `rear_key_mount` connects it to the source enclosure.
- C `rear_terminal_1..4`: X=±0.029 m, Z=±0.018 m,
  with independent insulating sleeves and slotted screw heads.

At the declared mating pose the P origin in S-local coordinates is
(0,-0.057,0) m. P tips therefore finish at S-local Y=-0.002 m.
The pin/bore nominal radial clearance is 0.7 mm. The neck remains in front of
the carrier; the broad source grip stays outside the socket opening.

P's final world origin is (-0.100, 0.103, 0.055) m, 4 mm above its initial
height. Two fixed environment rests, named `mating_foot_support`, support its
existing feet at this pose. Their centers are (-0.124, 0.082, 0.032) m and
(-0.076, 0.082, 0.032) m; each measures 0.006 by 0.046 by 0.004 m. Their bases
meet the work mat at Z=0.030 m and their tops meet the actual foot bottoms at
Z=0.034 m. Each rest is inset 0.5 mm from the sides and 4 mm from the ends of
its 0.007 by 0.054 m foot. This support is part of the teaching fixture; it does
not change the plug, socket, mating frame or contact clearances.

The tiny original P/S inspection-plane extensions beyond their nominal
half-lengths remain as real label faces, not changes to scene interaction
fields.

## Existing mature environment assets

The builder reuses the project's already attributed Poly Haven models
`WoodenTable_03`, `retro_multimeter`, `pliers` and
`flathead_screwdriver`, preserving their embedded textures and material maps.
Models are uniformly scaled and placed from their real bounds. The source hand
tools stand along their long axis; they are rigidly laid flat before fitting to
the bench. The protective mat uses matte, nonmetallic rubber rather than a
floor-tile texture. The workshop floor uses the existing
`concrete_floor_worn_001` material set. See the existing project asset license
record for their CC0 provenance. This directory does not duplicate that shared
pool.

## Candidate decision

The official KiCad current Molex 3D directory and official archived GitHub
mirror did not contain the checked Mini-Fit/Micro-Fit candidates. Two real
Picoflex four-pin STEP models were inspected in Blender, but their PCB-facing
geometry did not suit this axial teaching task. Neither those downloads nor
their licenses are dependencies of the delivered scene.

