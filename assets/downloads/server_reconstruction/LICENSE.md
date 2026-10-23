# Server reconstruction source licenses

Retrieved and inspected on 2026-10-22. These licenses apply to the corresponding assets, not to the HoloCue code.

## Lenovo Rack SR-250

- Author: **impresistem** — https://sketchfab.com/impresistem
- Original model: https://sketchfab.com/3d-models/lenovo-rack-sr-250-8b8d37883eca405890ccf50869fa4c2c
- Published: 2021-07-06.
- Current first-party API verified on 2026-10-22: https://api.sketchfab.com/v3/models/8b8d37883eca405890ccf50869fa4c2c returned `isDownloadable=true` and license URL `http://creativecommons.org/licenses/by/4.0/`, with author-credit requirement and commercial use allowed.
- Asset license: **Creative Commons Attribution 4.0 (CC BY 4.0)** — https://creativecommons.org/licenses/by/4.0/
- Public redistribution source (Objaverse/Ai2): https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-105/8b8d37883eca405890ccf50869fa4c2c.glb
- Per-object provenance: https://huggingface.co/datasets/allenai/objaverse/resolve/main/metadata/000-105.json.gz ; UID `8b8d37883eca405890ccf50869fa4c2c`, license `by`, author `impresistem`, `isDownloadable=true`. The exact selected metadata entry is retained as `lenovo_sr250_metadata.json`.
- Objaverse's dataset-level ODC-By license is separate from the per-object CC-BY license: https://huggingface.co/datasets/allenai/objaverse . Credit the Objaverse dataset when using this redistribution source.
- Local source: `lenovo_sr250_impresistem.glb`, 3,983,408 bytes; 46,873 triangles, 10 meshes, 4 embedded image maps. Downloaded anonymously from the above public URL, without account credentials.
- Changes: coordinate conversion, fit to HoloCue's frozen 0.432 x 0.460 x 0.044 m training envelope, object identifiers and a generic optical inspection adapter; material maps retained. This is a visual training adaptation, not an exact manufacturer-dimensional SR250 replica. The original Lenovo markings are source content and imply no endorsement.
- Suggested attribution: “Lenovo Rack SR-250 by impresistem, CC BY 4.0, via Objaverse/Ai2; adapted for HoloCue.” Keep this attribution and source/license links with redistributed derivatives.

## Innerscene 42U cabinet layout model

- Creator/source: **Innerscene — original model**, published 2026-10-07.
- Original page: https://www.innerscene.com/tools/library/3d-parts/server-rack-42u-original-mep-cad-x3d-29d73308
- Anonymous download: https://www.innerscene.com/api/library/server-rack-42u-original-mep-cad-x3d-29d73308/download
- License: **CC0 1.0 Universal** — https://creativecommons.org/publicdomain/zero/1.0/
- Source library terms: https://www.innerscene.com/tools/library/terms
- Local source: `innerscene_server_rack.x3d`, 976,446 bytes; 45 separate source Shapes.
- Changes: front door removed, structural frame and four perforated rails retained; two units trimmed from the rails without shrinking their hole pitch; plain panels shortened to the fixed 1.90 m roof and depth adapted. Source external texture references were unavailable and are explicitly replaced by complete opaque PBR materials. No missing texture reference is exported.
- Limit: original unbranded layout/visualization model, not a manufacturer CAD part or certified dimension/load model. It supplies cabinet structure; detailed server chassis come from the independently authored Lenovo asset above.

## Existing shared accessories

Poly Haven `tool_cart`, `modular_electric_cables`, `rubber_tiles` and `hangar_concrete_floor` are existing project downloads under CC0. Their original source records remain in `assets/downloads/SOURCES.md` and `assets/ASSET_LICENSE.md`.
