"""Acceptance against an actually running local model. Never substitutes replay for a failed model."""
import argparse,json,time,uuid,os
from pathlib import Path
import httpx
p=argparse.ArgumentParser();p.add_argument('--api',default='http://127.0.0.1:8750');p.add_argument('--out',default='runs/live_smoke.json');a=p.parse_args()
headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.getenv('HOLOCUE_API_KEY') else {}
client=httpx.Client(base_url=a.api,headers=headers,timeout=10)
def req(method,path,**kwargs):
 r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
assert req('GET','/health')['backend_mode']=='live','Acceptance requires a live local model'
report={'backend_mode':'live','cases':[]}
for scene,text in [('control_panel','把 B 逆时针转 30 度，接着检查 C 的背面。'),('connector','演示把 P 插进 S，插好后再检查 C。'),('blocks','先把 A 放到底板 BASE 上，然后检查 B 的背面。')]:
 s=req('POST','/api/v1/sessions',json={'scene_id':scene});sid=s['session_id']
 start=time.perf_counter()
 j=req('POST',f'/api/v1/sessions/{sid}/messages',json={'text':text,'request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
 while True:
  j=req('GET','/api/v1/jobs/'+j['id'])
  if j['status']!='planning':break
  if time.perf_counter()-start>100:raise TimeoutError('Model job exceeded 100 seconds')
  time.sleep(.25)
 assert j['status']=='done',j
 out=req('GET',f'/api/v1/sessions/{sid}/display')
 expected={'control_panel':'B','connector':'P','blocks':'A'}[scene]
 assert out['cues'][0]['target_id']==expected,out
 assert sum(c['n_gaussians'] for c in out['cues'])<=out['budget_total']
 report['cases'].append({'scene_id':scene,'session_id':sid,'latency_s':time.perf_counter()-start,'job':j,'packet':out})
path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(path)
