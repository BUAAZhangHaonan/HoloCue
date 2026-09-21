"""Record the actual model guard stop and preserve the scene results."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

root=Path(os.environ['HOLOCUE_ROOT']);run=Path(os.environ['RUN_DIR'])
stdout=(run/'model_command/stdout.log').read_text()
stderr=(run/'model_command/stderr.log').read_text()
assert 'Stopped only owned process group: host memory reserve reached' in stderr
reserve=float(re.findall(r'"host_reserve_gib":\s*([0-9.]+)',stdout)[-1])
events=[json.loads(line) for line in (run/'model_resources.jsonl').read_text().splitlines()]
breaches=[row for row in events if row.get('host_available_gib',float('inf'))<reserve]
assert breaches
files=['model_command/execution.json','model_command/stderr.log','model_resources.jsonl',
       'bridge_cnc_toolchange_command/execution.json','bridge_batches/cnc_toolchange/report.json',
       'bridge_connector_command/execution.json','bridge_batches/connector/report.json']
result={
    'reason':'The actual host-memory guard stopped the model service. CNC completed using its existing plan; connector then failed its initial real model request with ConnectError. Experiments stopped under the package resource rule.',
    'host_reserve_gib':reserve,'observed_breaches':breaches,
    'first_breach_utc':datetime.fromtimestamp(breaches[0]['time'],timezone.utc).isoformat(),
    'restart_after_breach_performed':False,'threshold_changed':False,
    'native_full_passed_this_run':['cnc_toolchange'],'native_failed_before_capture':['connector'],
    'native_not_run':['control_panel','dig_site','dive_fillstation','drone_bench','infusion_ward'],
    'targeted_pairs_not_run':['engine_bay','shelf_picking','dig_site'],
    'evidence':[{'path':(run/name).relative_to(root).as_posix(),'sha256':hashlib.sha256((run/name).read_bytes()).hexdigest()} for name in files]}
(run/'RESOURCE_STOP.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
