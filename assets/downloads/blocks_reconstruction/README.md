# LDraw construction teaching parts

This scene uses the [LDraw Parts Library](https://www.ldraw.org/).
The retained source is mature, community-authored CAD, not a model measured by
HoloCue or supplied by the LEGO Group. LEGO does not sponsor or endorse this
scene. The changed dimensions below describe the HoloCue teaching adaptation.

## Sources and license

- [3001, Brick 2 x 4](https://library.ldraw.org/parts/3436), James Jessiman.
- [3867, Baseplate 16 x 16](https://library.ldraw.org/parts/7304), James Jessiman;
  the retained history also credits Deanna Earley for its corrected BFC geometry.
- The brick uses the original `s/3001s01.dat` shell, eight `stud.dat` instances,
  and three open `stud4.dat` tubes. The baseplate retains the source stud groups
  and rounded border geometry. Original author/history/license headers remain
  in every retained file.

All 25 retained geometry `.dat` files explicitly declare **CC BY 4.0**.
The original `CAreadme.txt` and `CAlicense4.txt` accompany them in `ldraw/`.
`CAreadme.txt` explains both old and new library licenses; its example of a
dual-license header is not the header of these 25 geometry files.
License: <https://creativecommons.org/licenses/by/4.0/>.

`source_receipt.json` records each original file URL, SHA256, author and license.
The files were obtained byte-for-byte from the public
[Pybricks LDraw mirror](https://github.com/pybricks/ldraw) at commit
`c43ed06a128a10ed65675166bf42eb6fd608b9b0`. Direct official ZIP requests returned
HTTP 403 from the remote host. This receipt does not claim a byte comparison
against the official server's ZIP. The main part identities and current
license headers were separately checked on the official catalog pages.

Additional dependency authors, as retained in their file headers, are
Niels Karsdorp, Tore Eriksson, Steffen, Paul Easter, Willy Tschager,
Mark Kennedy, Magnus Forsberg, and the LDraw Parts Tracker administrators.
The low and high resolution primitives retain their own history credits.
The scene uses the library's 48-segment cylinder, disc, ring and corner
primitives for smooth silhouettes. It omits zero-area type-2/type-5 display
edges rather than turning them into physical rods. BFC winding, mirrored
references and `INVERTNEXT` are respected during conversion.

The retained shell is watertight and winding-consistent. LDraw's studs and
tubes are open connecting surface primitives; their geometry is not a closed
Boolean union with the shell. The source and adapted whole assemblies are
therefore **not watertight solids**, although all retained primitive windings
are consistent. Collision checks must use their actual faces and the closed
shell, not signed-volume assumptions for the whole open surface assembly.
This topology is inherited from the mature source and is disclosed rather
than silently adding caps over the inspected holes.

## Teaching-scale adaptation

The original LDraw convention is -Y up, 20 LDU stud pitch, 24 LDU brick body
height, and 4 LDU stud height. See the
[LDraw file-format specification](https://www.ldraw.org/article/218.html).
The conversion rotates `(X, Y, Z)` to `(X, Z, -Y)` and uses **0.8 mm/LDU**,
twice the usual approximate physical scale, to preserve the scene's fixed
**16 mm stud pitch**. No `scene.json` field is changed.

| Geometry | Source after uniform conversion | Teaching adaptation |
|---|---|---|
| A/B footprint | 64 × 32 mm | Unchanged |
| A/B body height | 19.2 mm | Only straight side walls and tube ends extend 0.8 mm to 20 mm |
| A/B studs | Radius 4.8 mm, height 3.2 mm | Unchanged; eight studs at x = ±24/±8 mm, y = ±8 mm |
| A/B underside tubes | Inner radius 4.8 mm, outer radius 6.4 mm | Cross-section unchanged; three tube axes at x = -16/0/16 mm, y = 0 |
| A/B cavity roof | 3.2 mm below body top | Unchanged |
| BASE footprint | 256 × 256 mm, 16 × 16 studs | Outer rows removed to 14 × 10; mature border translated to 224 × 160 mm |
| BASE corner radius | 3.2 mm | Unchanged |
| BASE slab thickness | 3.2 mm | Flat slab depth becomes 6 mm; stud height remains 3.2 mm |

`size_m.z = 20 mm` describes the existing brick body, not the studs. The old
recipe's total height was 23.6 mm. The new full source-derived height is
23.2 mm: local body bottom -10 mm, body top +10 mm, stud top +13.2 mm.
The local inspection point beneath B remains -11 mm. Its three open tubes
and the continuous inner roof can be inspected from -Z.

The original A mating pose places its center at `(-0.032, 0.14, 0.046)` m.
Its bottom rim and tube ends are then at world Z = 0.036 m, the BASE slab top.
The eight corresponding BASE studs end at Z = 0.0392 m and enter the real
open cavity; the inner roof is at Z = 0.0528 m. Source nominal stud/side-wall
surfaces are tangent. The neighboring stud/tube nominal radial gap is about
0.1137 mm. These values describe scene geometry, not manufacturing tolerance,
friction, interference fit, or a dynamics simulation.

The printed target outline lies outside A's final 64 × 32 mm footprint.
It adds no hidden support or obstruction inside the receiving cavity.
The original object IDs, color fields, poses, action fields, anchors, prompt
planes, and task ordering are preserved. ABS is rendered as an opaque
nonmetallic material; roughness is a scene rendering choice, not a measured
source value.

Only B's three inspected tube groups use a same-hue darker base color,
RGB (28, 75, 121), obtained by rounding the original (40, 107, 173) times 0.70,
and roughness 0.40. This teaching visibility adaptation distinguishes the
annular rims from the same-normal blue cavity roof under Viser's existing
shadowless lighting. It is not a source texture or real/baked ambient
occlusion. A, the shell and studs keep their original material values.
Original faces, BFC winding, open holes, topology and single-sided opaque
rendering are unchanged. A disposable actual Viser client showed all three
complete thick annuli with these material values; no global light or viewer
setting was changed.

## Reused environment

The workbench is the existing mature Poly Haven
[`WoodenTable_03`](https://polyhaven.com/a/WoodenTable_03), placed with a single
uniform 1.10 scale. A removable 2 mm work mat provides the existing 30 mm
support datum for all three task objects. The environment also reuses
[`binder_notebook`](https://polyhaven.com/a/binder_notebook), uniformly scaled
0.40, and [`magnifying_glass_01`](https://polyhaven.com/a/magnifying_glass_01),
uniformly scaled 0.58 and laid flat. Both stay outside A's handling route.
The floor uses the existing
[`concrete_floor_worn_001`](https://polyhaven.com/a/concrete_floor_worn_001) maps.
Original embedded PBR maps are retained without duplicating the shared pool.
The shared magnifier GLB has `BLEND` on its lens but alpha 1 and no transmission
extension, which renders as an opaque white disc. Only this scene's placed
lens copy uses alpha 35/255 and roughness factor 0.08 so the mat is visible
through it. Its original geometry and maps remain; the shared GLB is unchanged.
This is display transparency for a background prop, not a refraction model.

These environment sources are **CC0**; the retained project receipts are
`assets/raw/engine_round/SOURCES.md`,
`assets/raw/engine_round/polyhaven_download_log.json`,
`assets/downloads/SOURCES.md`, and
`assets/downloads/polyhaven/polyhaven_download_log.json`.
The mat, labels and finite teaching adaptations are HoloCue additions.

## Validation boundary

The author check measures actual triangle-ray intersections in the open tubes,
cavity roof, and receiving studs, and exports only into the batch process
directory. Candidate PNGs are produced by actual Blender CPU rendering.
The integration review supplies the final Blender/Viser matched views and
bounded geometry/path tests. No task session or end-to-end experiment is part
of this asset reconstruction.
