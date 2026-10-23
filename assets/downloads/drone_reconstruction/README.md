# Drone bench source preparation and fit

The central airframe and all four 5010 motors come from the licensed PX4 X500
model. BAT uses complete LiPo body and lower converter-shell components. GUARD
uses the already attributed emaitee fluted cap, and VOLTMETER the existing
Poly Haven instrument. Read LICENSE.md for per-source attribution and changes.

The source frame's upper/lower perforated plates, tubular arms, motor plates,
and clamps are selected as complete connected components. Tall landing gear and
low camera/antenna rails are removed for a bench service arrangement. No arm or
motor cross-section is stretched. Original CF.png UVs are preserved.

BAT contains two 23.03 × 85.75 × 30.87 mm body modules, each at uniform source
scale 0.00049, within a uniformly scaled 62.25 × 109.32 × 18 mm converter lower
shell. This is an attributed teaching cassette, not a manufacturer battery
specification. The original long external leads/plug are removed as complete
components. The 78 × 126 mm interface base supplies two real rails at local
z=-0.0255. Initial rail pockets have floor z=0.028, and two separate
contact-pad recesses have floor z=0.029; BAY stop surfaces lie at local
-0.0255 / world 0.1295. Four thin foam seats derive their underside
vertices by ray intersection with the actual sloped source converter floor.

M3's new nonmetal isolator_ring has inner/outer radii 5.5/11 mm, roughness .92,
axis +X, centre [0.0345, 0, -0.005], and outer face x=0.036. Its centre stays
open, matching the original inspection contract. GUARD's mature cap and shaft
rotate; the journal, thrust bearing and pedestal remain fixed in environment.
All source meshes keep a single uniform scale, with only rigid repositioning.

Reproduce derived source GLBs in the existing project environment:

1. Run real Blender with `convert_px4.py -- --output-dir <project scratch>`.
2. Run `prepare_sources.py --converted-dir <same project scratch>` with project
   Python. It selects exact source components and writes standard Y-up GLBs.
3. `scripts/scenes/rebuild_drone_assets.py` loads these GLBs and the originals,
   creates finite teaching interfaces, and returns the unchanged task IDs.

No Gazebo/PX4 runtime, GPU, model inference or end-to-end task experiment is used.
Source original files and current API receipts remain here. Temporary exports,
previews and author checks stay in the project reconstruction scratch until the
parent task archives the required evidence.
