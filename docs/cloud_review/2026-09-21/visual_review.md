# HoloCue Cloud Update independent visual review

## Final closeout — resource stop, partial native coverage

Independent reviewer: /root/cloud_visual_review. Final supplied source SHA-256: 37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe. Application/assets are reported unchanged from b2c379ba; subsequent changes were to the audit harness only. Final image manifest contains **76 actually viewed originals**, each with SHA-256. This includes historical and failed pre-fix evidence; it is not 76 successful current-final acceptance images.

The main session reported an actual resource-guard stop: api_resources time 1789981747.5597982, host memory 50.0271949768 below reserve 50.3090789795; api_command/stderr says "host memory reserve reached". No more experiments, image waiting or polling will be performed by this reviewer. Run-stage counts below are supplied by the main session, not inferred from screenshots.

- Final label layout: all 12 scenes' wide/narrow originals were actually viewed (24 images); label text is present/readable with no evident wrong-object label or clipped text. Representative final detail/inspection originals plus 44 independently parsed real-node visibility samples support the intended label hiding. This is not every-object detail review or video frame-by-frame review.
- Native acceptance: blocks_final has 13 reported passed stages. Actual final-workspace pair and earlier scoped pairs were visually reviewed. CNC_final has **9 reported passed stages**, then step_02_inspection was interrupted with "Exporter stopped"; **the complete CNC scene is not passed**. Actual CNC start pair and step_01_endpoint_receiver pair were reviewed. Remaining six scheduled complete native runs and three changed_pairs groups were **not run** after the resource stop, rather than still awaiting output. CLAMP/BLUE/BASKET/empty-hole/FLAG targeted native acceptance therefore remains unfulfilled.
- Latest two originals: CNC step_01_endpoint_receiver Viser/Blender have matching visible receiver-cylinder/flange/base geometry and cyan cue placement. The view is low and mainly side-on: it does not reveal the receiver's inner hole, and the upper ghost extends beyond the image top in both. This pair supports renderer consistency at this saved view, not empty-hole verification or whole-step completion.
- **P3 retained, unfixed:** parts of some 3D leader lines are not visible (notably blocks B), while labels and corresponding objects remain identifiable. Depth occlusion is plausible but not established by this image review; no anchor-algorithm error is claimed.
- Historical c4463b3 optical_bench/server_rack final native panoramas (4 images) remain explicitly historical. Their geometry agrees between renderers; historical server-rack SPARE/SLOT4 label overlap is not a current-final regression claim.

The observations below are a chronological evidence record. Earlier "pending" text is superseded by this closeout: stopped or unrun work remains incomplete and will not be silently resumed. Original label-loss failures remain recorded alongside the successful final-label retest; they are not counted as current-final failures.

## Evidence record
Session: /root/cloud_visual_review (independent sub-agent), 2026-09-21.
Scope: current RUN runs/simulation/cloud_update_20260921_ce64aff5 only. Remote project read-only; no experiments started. Source SHA-256 supplied by main session: bd938aafb0b6e056bfecb53aa88ca189ae43d3724489194e34bfe53bffc3be24. Final digest pending main-session confirmation.

Method: each listed original PNG downloaded and actually displayed with tools.view_image. No test-pass proxy, no montage-only review. Exact viewed list and local SHA-256 are in visual_review_manifest.json. Local originals: visual_review_inputs/.

Current observations (23 originals viewed):
- Three new Blender panoramas: engine bay, shelf picking, drone bench are rendered with complete recognizable principal assemblies and useful structural detail. No obvious broken geometry in these views. These panoramas do not prove every action target or its hidden faces.
- Blocks inspection exposes the underside cavity and all three tubes clearly. Detail exposes eight studs. Initial wide and narrow screenshots have leader lines but no A/B/BASE text; restored wide has text, but B text is separated from leader endpoint. Initial/narrow label acceptance remains unproven.
- CNC detail and inspection expose the tool and pull-stud neck/end profile. Narrow and restored-wide labels readable and separated. Initial wide contains lines without label text.
- Connector inspection faces the P ALIGN KEY plaque. Direct read of scenes/connector/scene.json confirms P inspect_point=[0,-0.056,0], normal=[0,-1,0]: this matches the existing inspect_back contract and is NOT a demonstrated regression. P front pins and contract-required C rear inspection are not covered by this P-only screenshot group. Detail mostly shows the same rear face; only top key is partly visible. Connector wide/narrow/restored-wide all have leader lines without any object labels.
- Control panel inspection exposes rear yellow key and four contacts clearly. Narrow labels readable. Initial and restored wide have leader lines but no labels.

Visual findings notified immediately to main session: absent label text in multiple captures. Main session reports confirming a stale annotation-key bug and preparing a fix. Initial suspicion about connector P view direction was withdrawn after reading the actual inspect_back contract.

Pending: remaining labels_r2 scenes, current-session Viser/Blender pairs, changed_pairs CLAMP/BLUE/BASKET/empty-hole/FLAG. They are still being generated and are not counted as failures. All-operation-object coverage remains pending.

Supplement 1 (32 total originals viewed):
- Dig-site POT3 inspection exposes all three inner engraved bands. Restored-wide labels clear and separated; initial-wide/narrow contain lines but no label text.
- Blocks native Viser/Blender 01_start_paused and 02_middle_paused pairs: principal geometry, static objects, and cyan ghost placement agree visually between renderers. Material/light/background and UI-label differences are expected native differences. Mid-step cyan ghost appears above/back of base in both, not at incompatible positions. This check is visual, not a pixel identity claim. Temporary inspection/resume/end pairs still pending.

Supplement 2 (37 total originals viewed): dive-fillstation BOTTLE3 detail shows readable front ID; inspection shows TRAINING BOTTLE3 rear ID clearly. Initial/narrow/restored-wide label text absent, covered by same pending label fix. Connector task_contract is P insert S then C inspect_back, with C also the interrupt target; no expanded modeling requested.


Supplement 3 (39 total originals viewed): blocks 03_temporary_inspection native pair matches underside geometry and cyan-ring location/size. The large cyan ring overlaps parts of the outer two tubes in both renderers, while all three tube openings remain recognizable. This is a shared cue appearance, not a renderer mismatch. Awaiting final labels and remaining native pairs.


Final-source preliminary retest (41 total originals viewed):
- Final source SHA-256 supplied by main session: b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457. Prior images above belong to the pre-fix source and remain historical failure evidence.
- Actually viewed labels_final/blocks/wide.png and wide_repeat.png: A, B, BASE are visible in both. Repeated workspace selection no longer removes these labels.
- Remaining visual detail: B leader ends near x927 while its text starts near x1160 in both 1600px screenshots (roughly 233px gap); A and BASE attach to their leaders. Reported to main session for scope determination. This does not negate label visibility recovery.
- Awaiting completion notification for all 12 final-scene captures, then review the remaining originals in a batch. No missing-file failure inferred during generation.

## Final labels batch review — completed

Final HEAD supplied by main session: 7a7da494. Source SHA-256: b2c379ba354ce95e6e48d5a9e73f2ff5bcfecb22acf823b785101b6df5ea2457.
Actually viewed original wide + narrow captures for all 12 scenes (blocks from labels_final, other 11 from labels_final_r2), with blocks wide reused from the earlier final-source review. Also viewed engine_bay detail + inspection and blocks_final/blocks/06_final_workspace both native renders. Total manifest now 68 distinct originals, including historical pre-fix evidence.

- No missing object-label text, cropped label text, or evident wrong-object label in these 24 final work-area originals. All principal operation objects fit in the canvas. Narrow views have small scene geometry, especially CNC/infusion/drone, but labels remain separated and readable; these panoramas do not establish fine-detail visibility of every object.
- Engine-bay CONN detail and rear inspection are clear; four contacts and rear key are visible. Their annotations are hidden as intended. Independently read the last real-node sample for wide/narrow/detail/inspection in each of the 11 labels_final_r2 scenes: all passed, with both visibility booleans true for workspace views and false for detail/inspection. Summary: visual_review_node_summary.json. This supports the hidden-label behavior but does not replace original-image review.
- Final blocks native Viser/Blender pair: yellow A is on the base, blue B remains on its pad, old yellow pad is empty, and object geometry/placement agrees. Viser shows current plan complete, version 16, with task-confirmed B. No visible renderer placement mismatch.
- P3 remains: blocks B leader is only partly visible before its label; some other leaders also cross or disappear behind scene geometry. Objects and labels remain identifiable. Main-session source inspection reports that label/leader endpoint coordinates agree; 3D depth occlusion is a plausible cause, not independently proved here. This report does NOT establish an anchor-algorithm error. No rendering dependency, scene or camera changed to hide this limitation.

Other native scenes and changed_pairs are still pending generation/review. No claim of all-object detail acceptance or frame-by-frame video review is made.

## Historical panorama supplement — separate provenance

At the main session's explicit request, actually viewed four original PNGs from runs/simulation/repair_review_20260920_25bcc909/bridge/{optical_bench,server_rack}/06_final_workspace/{viser.png,frame_0000.png}. Historical source commit supplied by main session: c4463b3. These are NOT new cloud_update_20260921 runs. They add historical full-scene native-render visual material only; they do not prove current-source replay or final acceptance. Manifest total: 72 originals (68 previously recorded plus 4 historical).

- Optical bench historical pair: installed L1 sits in POST2, old front base pad is empty, L2/M/target and workbench geometry agree between native views. Different material/light response remains visible, especially lens shading. No obvious pose or missing-assembly mismatch.
- Server rack historical pair: SPARE occupies the rack slot, its left staging table is empty, NODE3 remains on the right table; rack/rails/nodes and lamp agree geometrically. Historical Viser labels SPARE/SLOT4 overlap locally at the installed slot. This is a historical-label observation, not evidence that the current revised label layout regressed.

Main session reports current final source has advanced to 37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe through harness-only synchronization fixes; application/assets remain as b2c379ba. This source relationship is supplied by the main session, not independently re-audited in this image-only task. Remaining new native pairs and changed target pairs are pending separate notification; no polling or experiments performed here.

## Current CNC start-stage supplement

Actually viewed bridge_batches/cnc_toolchange_final/cnc_toolchange/01_start_paused/{viser.png,frame_0000.png}, current source SHA-256 37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe (supplied by main session). Manifest total is now 74 originals. This is a start-paused stage only; the complete CNC run is still pending and is NOT declared passed here.

Principal CNC frame/panel/magazine/socket/tool geometry and the cyan cues agree in native pair placement. Viser shows all six object labels (PANEL, MODESWITCH, T09, MAG, POCKET9, T03), readable without text cropping or overlaps. The target mode switch and the two visible tools are distinguishable; support structures can hide portions of 3D leader lines, consistent with the recorded P3 limitation. Blender has softer/lighter shading and no UI annotations; no obvious missing assembly or target/cue displacement was seen. This panorama cannot establish internal tool-pocket detail or completion state.

Other pending native runs and changed target pairs remain pending. No polling, source modification, or experiments performed for this supplement.

