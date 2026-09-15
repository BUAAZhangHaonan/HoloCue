"""A real-LLM interruption/restoration acceptance; writes partial evidence even on failure."""
import argparse,json,time,uuid,os,sys
from pathlib import Path
import httpx
p=argparse.ArgumentParser();p.add_argument('--api',default='http://127.0.0.1:8750');p.add_argument('--out',default='runs/live_interrupt.json');a=p.parse_args()
headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.getenv('HOLOCUE_API_KEY') else {}
client=httpx.Client(base_url=a.api,headers=headers,timeout=10)
report={'backend_mode':'live','status':'running','events':[]}
path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
def req(method,path,**kwargs):
 r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
def state():return req('GET',f'/api/v1/sessions/{sid}')
def say(text):
 s=state();t=time.perf_counter()
 j=req('POST',f'/api/v1/sessions/{sid}/messages',json={'text':text,'request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
 while j['status']=='planning':
  if time.perf_counter()-t>100:raise TimeoutError('Live planner timed out')
  time.sleep(.25);j=req('GET','/api/v1/jobs/'+j['id'])
 report['events'].append({'input':text,'job':j,'elapsed_s':time.perf_counter()-t,'state':state()});save()
 assert j['status']=='done',j
 return state()
try:
 assert req('GET','/health')['backend_mode']=='live','Live endpoint required'
 s=req('POST','/api/v1/sessions',json={'scene_id':'control_panel'});sid=s['session_id'];report['session_id']=sid
 s=say('把 B 逆时针转 30 度，接着检查 C 的背面。')
 original=s['queue'][0];assert original['semantic']['target_id']=='B' and original['semantic']['angle_deg']==30
 s=say('先别管 B，看看 C 的背面，保留 B 的角度。')
 assert s['queue'][0]['semantic']['target_id']=='C' and s['suspended'][-1][0]==original
 s=req('POST',f'/api/v1/sessions/{sid}/control/complete',json={'expected_revision':s['revision']})
 s=say('继续刚才 B 的任务。');assert s['queue'][0]==original
 before=s['queue'];s=req('POST',f'/api/v1/sessions/{sid}/control/pause',json={'expected_revision':s['revision']})
 assert s['execution']=='paused' and s['queue']==before
 s=req('POST',f'/api/v1/sessions/{sid}/control/resume',json={'expected_revision':s['revision']})
 assert s['execution']=='running' and s['queue']==before
 report['status']='passed'
except Exception as e:
 report['status']='failed';report['error']=repr(e);save();raise
finally:
 save();client.close()
print(path)
