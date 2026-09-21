"""Compact read-only status of the resumed batch."""
import json
import os
from pathlib import Path
run=Path(os.environ['RUN_DIR']);result={'native':{},'pairs':{}}
for file in sorted((run/'bridge_batches').glob('*/report.json')):
    result['native'][file.parent.name]=[{key:row.get(key) for key in ('scene_id','passed','failure')}|{'stages':len(row.get('stages',[]))} for row in json.loads(file.read_text())]
for file in sorted((run/'bridge_batches').glob('*/*/stages.json')):
    result['native'].setdefault(file.parent.parent.name,{'finished_stages':len(json.loads(file.read_text())),'running':True})
for file in sorted((run/'changed_pairs').glob('*/report.json')):
    result['pairs'][file.parent.name]=json.loads(file.read_text())['passed']
if not result['native'] and (run/'readiness.json').is_file():
    row=json.loads((run/'readiness.json').read_text())[-1]
    result['readiness']={name:value.get('status',value.get('error')) for name,value in row['responses'].items()}
print(json.dumps(result))
