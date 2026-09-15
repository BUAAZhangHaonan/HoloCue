"""Extended live acceptance from docs/05 扩展测试输入. Records outcomes honestly,
including model failures; never substitutes scripted answers for model output."""
import argparse,json,time,uuid,os
from pathlib import Path
import httpx

p=argparse.ArgumentParser();p.add_argument('--api',default='http://127.0.0.1:8750');p.add_argument('--out',default='runs/live_extended.json');a=p.parse_args()
headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.getenv('HOLOCUE_API_KEY') else {}
client=httpx.Client(base_url=a.api,headers=headers,timeout=10)
report={'backend_mode':'live','cases':[]}
path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
def req(method,path,**kwargs):
    r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
def state(sid):return req('GET',f'/api/v1/sessions/{sid}')
def say(sid,text):
    s=state(sid);t=time.perf_counter()
    j=req('POST',f'/api/v1/sessions/{sid}/messages',json={'text':text,'request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
    while j['status']=='planning':
        if time.perf_counter()-t>120:raise TimeoutError('planner timeout')
        time.sleep(.3);j=req('GET','/api/v1/jobs/'+j['id'])
    return j,state(sid),time.perf_counter()-t
def case(name,sid,text,check):
    try:
        job,s,elapsed=say(sid,text)
        verdict,note=check(job,s)
        report['cases'].append({'name':name,'input':text,'job_status':job['status'],
            'latency_s':round(elapsed,2),'verdict':verdict,'note':note,
            'assistant_message':s['assistant_message'],
            'queue':[t['semantic']['target_id']+':'+t['semantic']['action'] for t in s['queue']],
            'suspended':len(s['suspended']),'error':s.get('last_error'),
            'raw_decision':(job.get('data') or {}).get('decision')})
    except Exception as e:
        report['cases'].append({'name':name,'input':text,'verdict':'HARNESS_ERROR','note':repr(e)})
    save()

def ok(cond,note):return ('passed' if cond else 'FAILED_MODEL_BEHAVIOR'),note

assert req('GET','/health')['backend_mode']=='live','live backend required'
sid=req('POST','/api/v1/sessions',json={'scene_id':'control_panel'})['session_id']
report['session_id']=sid;save()

# 1 pause via natural language
case('nl_pause',sid,'暂停一下，先别继续',lambda j,s: ok(s['execution']=='paused',f'execution={s["execution"]}'))
# 2 resume via natural language
case('nl_resume',sid,'继续刚才没做完的那步',lambda j,s: ok(s['execution']!='paused',f'execution={s["execution"]}'))
# 3 angle and order
def c3(j,s):
    q=s['queue'];b=next((t for t in q if t['semantic']['target_id']=='B'),None)
    return ok(b is not None and b['semantic'].get('angle_deg')==15 and q[0]['semantic']['target_id']=='B',
              f'queue={[t["semantic"]["target_id"] for t in q]} angle={b and b["semantic"].get("angle_deg")}')
case('angle_order',sid,'B 先逆时针转 15 度，之后再看 A',c3)
# 4 nested interrupt preserving B parameters
def c4(j,s):
    return ok(len(s['suspended'])>=1 and any(t['semantic']['target_id']=='B' for q2 in s['suspended'] for t in q2)
              and (not s['queue'] or s['queue'][0]['semantic']['target_id']=='C'),
              f'suspended={[[t["semantic"]["target_id"] for t in q2] for q2 in s["suspended"]]}')
case('nested_interrupt',sid,'别转了，先检查 C 的背面，回头还要接着做 B',c4)
# 5 finish the temporary check explicitly
case('complete_temp',sid,'把刚才临时检查的任务结束掉',
     lambda j,s: ok(any(t['semantic']['target_id']=='C' for t in s['completed']) and not s['queue'],
                    f'completed={[t["semantic"]["target_id"] for t in s["completed"]]}'))
# 6 ambiguous angle must clarify, not guess
def c6(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    return ok(d.get('operation')=='clarify' or s['last_error'] is not None,
              f'operation={d.get("operation")} msg={s["assistant_message"][:40]}')
case('clarify_angle',sid,'这个旋钮转一点',c6)
# 7 unknown object
def c7(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    clarified=d.get('operation')=='clarify'
    rejected=j['status']=='error' and 'Z' in (s.get('last_error') or '')
    return ok(clarified or rejected,f'operation={d.get("operation")} error={(s.get("last_error") or "")[:60]}')
case('unknown_object',sid,'把不存在的 Z 转 30 度',c7)
# 8 capability violation (C has no rotate) must not silently pass
def c8(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    rot_c=any(c.get('target_id')=='C' and c.get('action')=='rotate' for c in (d.get('cues') or []))
    return ok(j['status']=='error' or not rot_c,
              f'job={j["status"]} rotates_C={rot_c} error={(s.get("last_error") or "")[:60]}')
case('capability_violation',sid,'把 C 转 30 度',c8)
# 9 display C while keeping B parameters
def c9(j,s):
    return ok((not s['queue'] or s['queue'][0]['semantic']['target_id']=='C') and len(s['suspended'])>=1,
              f'queue={[t["semantic"]["target_id"] for t in s["queue"]]} suspended={len(s["suspended"])}')
case('keep_params_show_c',sid,'显示 C，先保留 B 的操作参数',c9)
# 10 explicit new task replaces scope
def c10(j,s):
    return ok(any(t['semantic']['target_id']=='A' for t in s['queue']),
              f'queue={[t["semantic"]["target_id"] for t in s["queue"]]} suspended={len(s["suspended"])}')
case('replace_new_task',sid,'新建任务，把 A 放到底板 BASE 上',c10)

# 11 rapid double-send: only latest epoch may commit
s=state(sid)
j1=req('POST',f'/api/v1/sessions/{sid}/messages',json={'text':'把 B 逆时针转 30 度，接着检查 C 的背面。','request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
s2=state(sid)
j2=req('POST',f'/api/v1/sessions/{sid}/messages',json={'text':'先别管 B，看看 C 的背面，保留 B 的角度。','request_id':uuid.uuid4().hex,'expected_revision':s2['revision']})
t0=time.perf_counter()
while time.perf_counter()-t0<120:
    a1=req('GET','/api/v1/jobs/'+j1['id']);a2=req('GET','/api/v1/jobs/'+j2['id'])
    if a1['status']!='planning' and a2['status']!='planning':break
    time.sleep(.3)
superseded=a1['status']=='superseded';committed=a2['status']=='done'
report['cases'].append({'name':'rapid_double_send','job1':a1['status'],'job2':a2['status'],
    'verdict':'passed' if (superseded or a1['status']=='error') and committed else 'FAILED_EPOCH_RACE',
    'note':'first request must not commit after second epoch'});save()

# 12 model service down: visible error, frozen actions (checked while model server stopped externally)
report['cases'].append({'name':'model_down','howto':'stop vLLM, send a message, expect job=error and session.last_error visible in UI/log','verdict':'MANUAL_STEP'});save()

report['summary']={'passed':sum(1 for c in report['cases'] if c['verdict']=='passed'),
 'model_failures':sum(1 for c in report['cases'] if c['verdict']=='FAILED_MODEL_BEHAVIOR'),
 'harness_errors':sum(1 for c in report['cases'] if c['verdict']=='HARNESS_ERROR')}
save();client.close();print(path)
