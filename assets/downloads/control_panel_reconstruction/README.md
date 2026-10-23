# Control-panel reconstruction sources

The builder is `scripts/scenes/rebuild_control_panel_assets.py`. It returns A, B, C and environment assemblies; all task IDs, poses, sizes and interaction fields remain in the unchanged scene contract.

| Part | Mature source | Adaptation |
|---|---|---|
| A/B rotating cap | `emaitee_knob.glb`, emaitee, CC BY 4.0 | Rigid reorientation, uniform factors .0032/.0034 from source coordinates, polymer material, attached white pointer |
| A/B rotary shaft and fixed stator | `adafruit_562.step`, Adafruit, MIT | Millimetres to metres; source solid 2 rotates, other solids stay in the drilled static panel |
| C housing | `adafruit_2230.step`, Adafruit, MIT | Original 93.5 x 28.8 x 82.8 mm upright geometry; finite four terminal bores and indexing key |
| Shared source for connector scene | `adafruit_2230_zup.glb` | Uncut three-part enclosure in **Z-up metres**; do not apply a glTF Y-up correction when loading this intermediate |

Source files, exact URLs, author/license receipts and file digests are in `sources.json`; complete attribution, changes and licensing boundaries are in `LICENSE.md`. No source texture maps accompany the CAD/cap models. Scene materials are scalar PBR, while the reused Poly Haven props retain their embedded PBR maps.

Stable task geometry names:

- `emaitee_fluted_knob`, `Adafruit_562_rotating_shaft`, `shaft_adapter_sleeve` and `white_rotation_indicator` are in A/B. The white pointer center is local [0, .0065, .02685] m; it rests on the source cap's intact top at z=.0266, clear of its authored radial notch.
- `A_stationary_bearing` / `B_stationary_bearing` are in the environment. Their top surfaces meet the respective cap bottoms at world z=.055 / .0524 m. Their fixed circular scale ticks stay outside the rotating cap.
- C's `rear_yellow_locating_key` has its front at local y=.039, through the original inspection point [0, .039, 0]. Four `rear_metal_terminal` parts are at x=+/- .016 and z=+/- .011, with tips at y=.0364. These added parts are teaching interfaces, not a vendor connector specification.
- `C_contact_foot` reaches the source housing's actual bottom at world z=.0436. The feet, plate, ESD mat, laminated bench top and original-proportion wooden table form a connected support stack.

The existing shared table and props are placed with uniform source scaling. The multimeter preserves its original upright body and floor-level lead coil, at 0.20 m height. The screwdriver is rigidly rotated by -94.4513246615 degrees about source X before sizing to 0.20 m length; this places its handle and blade tip on the same support plane instead of shrinking a vertical tool to the height budget. A plain 15 mm laminated worktop gives the control bench its required depth while retaining the mature table's original proportions. The footprint adaptation is explicit; no scanned texture is stretched onto the precision control panel.

Only local asset geometry, contacts and exports are checked during preparation. Electrical behavior, experimental performance and an end-to-end agent run are outside this reconstruction.
