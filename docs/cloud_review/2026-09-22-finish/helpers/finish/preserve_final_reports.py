"""Copy explicit final metadata to Git documentation; preserve evidence bytes."""
import shutil
from pathlib import Path

root = Path('/home/hdd3/zhanghaonan/projects/holocue')
run = root / 'runs/simulation/cloud_finish90_20260921_e67b574'
work = root / '.work/cloud_finish90_20260921'
destination = root / 'docs/cloud_review/2026-09-22-finish'
run_names = ['FINAL_SUMMARY.md', 'REVIEW_NOTES.md', 'NEXT_REVIEW_PROMPT.md',
    'COVERAGE.json', 'review_selection.json', 'source_final.json', 'assets_final.json',
    'SOURCE_PHASES.json', 'source_phase_c33.json', 'source_phase_camera_atomic.json',
    'VIDEO_ACCEPTANCE.json', 'local_video_inventory.json',
    'service_shutdown_resume03.json', 'shutdown_gpu_ports_resume03.json',
    'owned_process_verification_final.json', 'inherited_evidence_verification.json']
work_names = ['camera_phase_delivery_review.md', 'camera_sync_review.md',
    'delivery_helpers_cross_review.md', 'privacy_review_final.md', 'privacy_review_final.json',
    'review_video_tool_review.md', 'service_generation_review.md', 'video_provenance_review.md',
    'visual_review.md', 'visual_review_seal.json', 'final_review_inventory.json']
commands = ['selection_final', 'selection_final_attempt02', 'export_final', 'verify_bundle_final',
    'pytest_camera_final', 'camera_atomic_live', 'pairs_shelf_picking_attempt02',
    'pairs_shelf_picking_attempt03', 'shutdown_resume03', 'verify_cleanup_final']
copies = [(run / name, destination / name) for name in run_names]
copies += [(work / name, destination / 'reviews' / name) for name in work_names]
copies += [(run / 'upload' / name, destination / 'upload' / name)
           for name in ('UPLOAD_INDEX.json', 'SHA256SUMS')]
for command in commands:
    for name in ('execution.json', 'stdout.log', 'stderr.log'):
        copies.append((run / (command + '_command') / name,
                       destination / 'delivery_commands' / command / name))
for source, target in copies:
    assert source.is_file(), source
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
print(f'Preserved {len(copies)} files without modifying evidence sources.')
