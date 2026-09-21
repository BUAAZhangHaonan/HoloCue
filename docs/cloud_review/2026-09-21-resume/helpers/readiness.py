"""Wait for the recorded local services and save real readiness responses."""
import json
import os
import time
from pathlib import Path
import httpx
import psutil
run=Path(os.environ['RUN_DIR']);checks=[]
headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    for name in ('model','api','viewer'):
        record=json.loads((run/(name+'_repair_process.json')).read_text())
        process=psutil.Process(record['pid'])
        assert process.create_time()==record['create_time'] and process.is_running(),name
    row={'time':time.time(),'host_available_gib':psutil.virtual_memory().available/1024**3,'responses':{}}
    for name,url in [('model','http://127.0.0.1:8000/v1/models'),('api','http://127.0.0.1:8750/health'),('viewer','http://127.0.0.1:8780/')]:
        try:
            response=httpx.get(url,headers=headers if name=='api' else {},timeout=10)
            row['responses'][name]={'status':response.status_code}
            if name!='viewer':row['responses'][name]['body']=response.text
        except httpx.HTTPError as error:
            row['responses'][name]={'error':type(error).__name__}
    checks.append(row);(run/'readiness.json').write_text(json.dumps(checks,indent=2)+'\n')
    if all(value.get('status')==200 for value in row['responses'].values()):
        print('Recorded model/API/viewer ready; original service settings retained.');break
    time.sleep(5)
else:raise TimeoutError('Services did not become ready within ten minutes')
