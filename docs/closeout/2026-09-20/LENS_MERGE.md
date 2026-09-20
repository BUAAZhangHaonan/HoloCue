# Local lens merge, 2026-09-20

Only the authorized local current mirror was changed. No remote command, generation, test, service, GPU or native render was started during this merge. Parent owns deployment and commits.

Source before: `a05cfce56597ceae642621675019749c96e255ea423f040435ae842c9bb3695e`.
Source after: `0a7bdcb1e06ede04fb4fcd4689a25aa5cce9a4e347fe68420dffd0c9130837aa`.

Applied the exact r2 lens hunk through apply_patch, preserving the CLAMP changes. Local string comparisons proved the entire source prefix before the lens branch and suffix after its changed block equal the saved pre-merge source, and the changed block exactly equals r2. Applied the prepared mount test hunk and added the final 11-case lens test through apply_patch. Copied six immutable fixtures only after checking source hashes; all destination hashes match. Prior fixtures were not changed. Local verification command exited 0.

Exactly nine current files are in this merge:

| Relative path | SHA256 |
| --- | --- |
| src/holocue/modeling.py | 0a7bdcb1e06ede04fb4fcd4689a25aa5cce9a4e347fe68420dffd0c9130837aa |
| tests/test_panel_optical_mounts.py | eee77b484ad0001fe4a0a7b72c44b712755fb9229caf098df75d3ac698b1bce6 |
| tests/test_optical_lens_seat.py | c1b44d4dc071b9658aaafb058c58ca5cd3133884b082c7e1608835358ff761db |
| tests/fixtures/optical_lens_before_seat/L1.glb | dd4236403f6b3cf62516d168f858b544fe7d32fd93d17f08eac6dd09b977230b |
| tests/fixtures/optical_lens_before_seat/L2.glb | 34ff1c0a6f67d13ed34cdc7bb97e533902c8a0375489b304852c63b63aa8f108 |
| tests/fixtures/optical_lens_before_seat/scene.json | 1936c299bf9b2411772b50012882012c9845bcfdfcdf43d9387977039943c4b7 |
| tests/fixtures/optical_lens_before_seat/L1_view.json | 73652ad7e339a8f77952cbbc59fe21080f1b2ac441f114051a04c95cb35cda35 |
| tests/fixtures/optical_lens_before_seat/L2_view.json | 1f2664935285153004f470b64df6e8a26b667780cf77fa95df5ad0834c802c3b |
| tests/fixtures/optical_lens_before_seat/visible_rays.json | fe56fdb48cc685085a04579e5b0d5742111bc07e8a5cbb9d01fa8f98fde57df8 |

Geometry changes only L1/L2 optic_retainer 0000 blind seats and mounting_post 0002 tops. Mount tests whitelist precisely these two nodes on these two objects while preserving other node fingerprints and changed-node material checks; the added 11 tests constrain hole walls, contact, aperture clearance, original surfaces and visible rays.

Integration status: the prior 78-case run was terminated with exit 1 at 1789908500 by the host reserve guard (self RSS 0.497 GiB; available host 50.0318 GiB below 50.3091 GiB). It did not pass and was not retried. The combined 89-case run has not been started. Earlier independent r2 results remain archived and do not constitute integrated or native acceptance.

Saved before snapshots: modeling_before.py and mount_test_before.py in this directory. Exact input hunks remain optical_lens_candidate_r2/modeling.patch and optical_lens_deployment_prep/mount_tests.patch.
