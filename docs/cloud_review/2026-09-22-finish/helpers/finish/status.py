"""Read-only compact status for the active native and video queues."""
import json
import os
from pathlib import Path

run = Path(os.environ['RUN_DIR'])
read = lambda path: json.loads(path.read_text())
status = {'native': {}, 'pairs': {}, 'video_complete': [], 'produced': [], 'video_active': {}, 'failures': {}, 'captured_attempts': {}, 'produced_attempts': {}}
for base, kind in [('bridge_batches', 'native'), ('changed_pairs', 'pairs')]:
    for directory in sorted((run/base).glob('*')):
        report = directory/'report.json'
        stage_files = list(directory.glob('*/stages.json')) if kind == 'native' else [directory/'stages.json']
        status[kind][directory.name] = read(report) if report.is_file() else {'stages': sum(len(read(p)) for p in stage_files if p.is_file())}
        if report.is_file():
            result = read(report)
            passed = all(row.get('passed', False) for row in result) if isinstance(result, list) else result.get('passed')
            status[kind][directory.name] = {'passed': passed, 'report_exists': True}
for attempt in sorted((run/'videos').glob('*_attempt*')):
    manifest = attempt/'manifest.json'
    if manifest.is_file():
        for item in read(manifest)['scenes']:
            if item['passed']:
                status['video_complete'].append(item['scene_id'])
                status['captured_attempts'][attempt.name] = item['scene_id']
            else:
                status['failures'][attempt.name] = item.get('error', 'failed')
    else:
        for timeline in attempt.glob('*/ui_timeline.json'):
            rows = read(timeline)
            if rows:
                row = rows[-1]
                status['video_active'][attempt.name] = row.get('stage', row['kind'])
    for product in attempt.glob('*/produced*/manifest.json'):
        status['produced'].append(read(product)['scene_id'])
        status['produced_attempts'][str(product.relative_to(run))] = read(product)['scene_id']
for execution in sorted(run.glob('*_command/execution.json')):
    record = read(execution)
    if record['returncode']:
        status['failures'][execution.parent.name] = record['returncode']
status['video_complete'] = sorted(set(status['video_complete']))
status['produced'] = sorted(set(status['produced']))
print(json.dumps(status, ensure_ascii=False))
