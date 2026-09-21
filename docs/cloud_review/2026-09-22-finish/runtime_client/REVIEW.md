# Viser HDR canvas opacity: isolated correction and build

Author: independent agent `/root/cloud_code_review`. Remote project:
`/home/hdd3/zhanghaonan/projects/holocue`. Evidence RUN:
`runs/simulation/cloud_finish90_20260921_e67b574`.

The installed Viser 1.1.1 component has a controlled, reproduced defect. In
`client/src/HDRJPGEnvironment.tsx`, its second texture load sets fade progress
to 1 while leaving the canvas CSS opacity unchanged. The frame handler then
returns immediately. A first load followed by exactly one animation frame
sets opacity to .05 + .95 * .2 = .24; a second load at that point leaves .24
permanently. On a white background this produces approximately .24 * RGB + 194.

The correction adds exactly `gl.domElement.style.opacity = "1";` to the
second-load branch. First-load fade, textures, HDR lighting, camera and model
parameters are unchanged. The isolated copied client and required `_assets`
live below `.work/viser_hdr_opacity_fix/viser`; the installed package and all
services remain unchanged by this preparation.

Evidence boundaries matter: the root's earlier passive live diagnosis observed
.05 -> .24 -> .62 -> 1 and did **not** reproduce a permanent .24 state. The older
bleached connector images and their pixel relationship support this causal
hypothesis; the controlled component test establishes that the code defect is
real. These facts do not establish that every old recording had the same cause.
No new native workflow acceptance is claimed by this correction.

## Recorded validation

Every command below used the existing record.py, RSS 8 GiB, and unchanged
`HOLOCUE_HOST_MAX_USED_FRACTION=.90`. All completed execution records retain
application source c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a
before and after.

| Record label | Result |
| --- | --- |
| hdr_opacity_prepare | rc0; copied client/assets and saved original identities |
| hdr_opacity_node | rc0; official Node 24.12.0 archive verified against official SHA256 list; npm 11.6.2 |
| hdr_opacity_dependencies | rc0; npm ci with original lockfile, project-local cache |
| hdr_opacity_regression_old | rc1; zero tests ran due unrelated ViewerContext style imports; preserved, not behavioral evidence |
| hdr_opacity_regression_old_behavior | rc1; first-load fade passed, second-load test failed exactly `expected 0.24 to be 1` |
| hdr_opacity_regression_fixed_behavior | rc0; both actual-component tests passed |
| hdr_opacity_build | rc0; tsc and Vite production build, original installed files and isolated lock rechecked |

The regression imports the real component, React and Three.js and controls
texture loader completion and frame scheduling. It mocks the graphics hooks
and requestRender context; it does not render WebGL or establish browser visual
acceptance. The context mock avoids unrelated styles, without replacing the
component under test. First-load .05 -> .24 -> 1 and second-load restoration
to 1 are separately asserted.

The existing lockfile's jsdom 30.0.1 emits an engine warning for Node 24.12.0
(its declared Node 24 minimum is 24.15.0). No dependency or Node version was
changed to hide this warning. Both tests and the TypeScript/Vite build actually
completed. Vite also retained its existing tsconfig-paths and Wasm externalized
module warnings in stderr.

## Reproducible artifacts

`build_fix.py` provides prepare/node/dependencies/test-old/test-fixed/build
actions. It installs Node and npm dependencies only inside this work directory;
its build action requires the exact old failing assertion and new passing
tests, verifies the lock, and checks that the installed package has not changed.
`HDRJPGEnvironment.opacity.patch` is the one-line source patch. The actual edit
was made with apply_patch and copied only into the isolated client. Apply this
patch between old and fixed regression actions when reproducing in a fresh
directory. Existing outputs must be retained and use fresh command labels.

| Artifact | SHA256 |
| --- | --- |
| Original TSX | ea854f80e057ccfbba238c645b051b1f0507c89d140e9e1902f0f6a31bf830e1 |
| Patched TSX | 5ae7030a60649863d135806cbe9a3a4750121d819d8d762e3bc97ee11028e637 |
| Original and current lockfile | 2df518d57396831ac0bb1bbd736db6905bdbeb1c98f688b93503b856f6cb420e |
| Original served build | d7a86b58a884879e1e6f09382d405bb69e761afe9fc8c1fdbe5eea6a787230e7 |
| Isolated new build (818780 bytes) | db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f |
| Component regression test | 706c0a326df5cd2907ed04123f94454a0d8aabf5f299633aa79798440016e7b9 |
| Patch | cdd4d6a62f26d49377ab7c04aa4548f4f779f300ca870453c2fbab718f5e1d95 |
| Official Node archive | bdebee276e58d0ef5448f3d5ac12c67daa963dd5e0a9bb621a53d1cefbc852fd |

Full identities are in `original_identity.json`, `node_identity.json`,
`dependency_identity.json` and `build_identity.json`; original TSX, lock and
build are retained in `original/`. The deployable candidate is
`viser/client/build/index.html`. No deployment was performed. Viser caches its
served HTML in process memory, so subsequent runtime validation must identify
the new viewer process and actual served document hash, not just the disk file.

## Capture helper cross-check

The root's capture helper at SHA
76e53bfe4d64649b393c8bd5cace95fe0bf70fdbf6081bde96bc7f524a7cfa0e
records the actual main-document response body, compares its SHA to the installed
build, and waits for actual canvas and ancestor opacity 1 before and after
frozen screenshots. These are read-only observations; no CSS is forced.

`capture_intro_probe.py` runs only that real helper's open/introduction method
in one fresh connector session, with no task workflow or model request. It is
recorded as `hdr_capture_intro_probe`. The actual response callback completed
without a deadlock: `served_client.json` recorded one HTTP 200 document matching
the original d7a86b58 build; `canvas_initial.json` passed with the real canvas
and every ancestor at opacity 1. The probe completed with rc0 in 185.443 seconds:
four real introduction views, empty task queue/completed lists, no browser
errors, and all nine initial/before/after canvas checks passed. Session identity
is `13e0d40f870549fc90f51425e377bcb0`; its final snapshot and result are retained.
This probe still uses the original runtime, not the isolated build. It proves
the response-body callback completes under this live protocol; it does not
prove a patched runtime or full task workflow passed.
