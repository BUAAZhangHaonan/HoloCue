# Engine service fixture sources

The four original GLBs below were retrieved on 2026-10-23 from the public
Objaverse archive. Each model's own Sketchfab API record, retained beside the
GLB, explicitly identifies CC BY 4.0 and permits download. `sources.json` binds
the original files to their SHA256 values and exact archive URLs. The archive
dataset's general license is not used as a substitute for model licenses.
`CC-BY-4.0.txt` contains the license text. The original GLBs are retained unchanged.

| Original model | Author | Source | Use |
| --- | --- | --- | --- |
| Three Cylinder Motorcycle Engine | Jamie Hamel-Smith | https://sketchfab.com/3d-models/ad2416e341cb4beca3f86b0b00e84749 | Complete generic motorcycle engine, plus a separately adapted copy of its oil-cap part |
| Spark Plug | mr.barbados | https://sketchfab.com/3d-models/049df1e62c064b31ba6df5a0b8c6a562 | Complete five-part spark plug, including original thread and electrode geometry |
| Inbus Screw, bolt. imbus | YouniqueĪdeaStudio | https://sketchfab.com/3d-models/d4b2881cd9ef489f99df36fc88640397 | Complete screw reused at the CLAMP and TENSIONER interfaces |
| Threaded Connector 001 | Arrel | https://sketchfab.com/3d-models/758d28644a504285918302acb85323ca | Complete female half: Object_6 shell, Object_7 insulator, Object_8 conductive contacts |

## Changes and teaching adaptations

`scripts/scenes/rebuild_engine_assets.py` converts the archived standard glTF
Y-up coordinates to scene Z-up exactly once. Original shapes are uniformly
scaled. The existing shared Poly Haven pool is already Z-up and is not rotated
again during loading. No scene.json values or task interfaces are changed.

The engine's original archive bounds are approximately 0.4812 × 0.9061 × 0.7948
in the archive's nominal metre coordinates. Uniform scale 0.58 and a 90-degree
Z rotation give a 0.5256 × 0.2791 × 0.4610 m service assembly. This is a visual
training adaptation, not a measured motorcycle specification. Original named
parts and scalar materials are retained, including the radiator, hoses,
throttle bodies, airbox, cases and exhaust. The fixture has three small steel
saddles whose top faces match real downward oil-pan triangles.

The spark plug is centred on its actual longitudinal axis and uniformly scaled
to the existing 21 mm lateral envelope. Its resulting length is approximately
82.3 mm, within the fixed 90 mm envelope; the model is not stretched to fill it.
Original UVs, colour, normal and metal/roughness maps are retained. The ceramic
insulator's metallic multiplier is explicitly zero. No brand or engine-fit
claim is attached to this independently sourced plug.

Both initial and final plug rests bear on the distributed outer-edge vertices
of the genuine downward metal seat. Their measured plane determines the flat
annular seats; the source's shallow inner bevel remains free. The seats have
15.2 mm open centres, clearing the original thread peaks. The final sleeve has
a 15.2 mm lower bore, a 22.4 mm upper access bore,
and an unobstructed bottom at world Z=1.023 m. The electrode remains free above
that floor at the unchanged target centre (0.16, 0.26, 1.076). The source's own
thread geometry is retained; the sleeve is a teaching slip fit, not a verified
thread specification or torque assembly.

The source screw's actual planar head shoulder determines its axis. Complete
screws are uniformly scaled to 47 mm (CLAMP) and 35 mm (TENSIONER) length, with
their heads toward +X. Each fixed annular bearing meets the actual -X shoulder
face, while leaving the thread free. The clamp includes a separate fixed band
around its hose. Rotation is the original teaching interface; no deforming
worm-drive tightening or thread advancement is simulated.

The connector uses the complete female source half and omits the separate male
half, presentation cable and logo plinth. Uniform scale is 0.023 per archive
unit. Its original terminal face points +Y, with its front rim at local Y=0.034
m, behind the unchanged inspection point at Y=0.036 m. Scene-local scalar
finishes distinguish conductive contacts, non-metallic insulator and shell;
geometry is retained. This is a generic service connector, not claimed to fit
the motorcycle engine or a named automotive harness. The reused oil-cap mesh
has an open installed backside; a scene-local rotating spindle adapter joins
that original mesh to the flat bearing face of the fixed fill-neck adapter.

The trolley, ratchet wrench and hangar floor material reuse the project's
existing CC0 Poly Haven pool and its original receipts in
`assets/downloads/SOURCES.md`. The trolley is uniformly scaled by 0.82; the
wrench is placed horizontally. Added geometry is limited to the service
pallet, fixed sleeves, posts, saddles, clamp band/hollow hose and connector cradle
needed to preserve the existing task coordinates. The assembly represents an
exposed training service stand rather than a model-specific vehicle bay.

## Evidence

Source originals were inspected in real Blender CPU renders before selection.
The author candidate includes workspace, spark plug, well, clamp and connector
views. Exact generated bounds, bearing coordinates and source primitive
mapping are written by the reproducible author check in the current batch
scratch; parent integration retains the final checked evidence and images.
