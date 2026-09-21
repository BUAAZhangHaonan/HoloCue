"""Read-only PID/create-time check with a distinct, immutable report per shutdown."""
import argparse
import json
import os
import time
from pathlib import Path
import psutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
run = Path(os.environ['RUN_DIR']).resolve()
output = args.output.resolve()
if not output.is_relative_to(run) or output.exists():
    raise ValueError('Output must be a new file inside this RUN')
rows = []
for path in sorted(run.rglob('*process.json')):
    record = json.loads(path.read_text())
    if not isinstance(record, dict) or not {'pid', 'create_time'} <= record.keys():
        continue
    row = {'record': str(path.relative_to(run)), 'pid': record['pid'], 'create_time': record['create_time']}
    try:
        process = psutil.Process(record['pid'])
        row['status'] = 'pid_reused' if process.create_time() != record['create_time'] else process.status()
    except psutil.NoSuchProcess:
        row['status'] = 'exited'
    rows.append(row)
live = [row for row in rows if row['status'] not in ('exited', 'pid_reused', psutil.STATUS_ZOMBIE)]
output.write_text(json.dumps({'checked_at': time.time(), 'passed': not live,
    'recorded_identities': rows, 'live_owned_identities': live,
    'scope': 'Read-only PID and creation-time verification; unrelated processes untouched.'}, indent=2)+'\n')
assert not live, live
print(json.dumps({'passed': True, 'recorded_identities_checked': len(rows)}))
