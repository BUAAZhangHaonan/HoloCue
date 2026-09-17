"""Extended live acceptance from docs/05 扩展测试输入. Records outcomes honestly,
including model failures; never substitutes scripted answers for model output.

Attempt 2 (this version): each group runs on a fresh session and inputs are bound to
their intended scene, so an early model failure cannot pollute later cases' history.
Attempt 1 results are kept at runs/live_extended_attempt1.json.
"""
import argparse,json,sys,time,uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_client import make_client, req as _req, state as _state, send as _send, new_session

p=argparse.ArgumentParser();p.add_argument('--api',default='http://127.0.0.1:8750');p.add_argument('--out',default='runs/live_extended.json');a=p.parse_args()
client=make_client(a.api)
report={'backend_mode':'live','cases':[]}
path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
def req(method,path,**kwargs):return _req(client,method,path,**kwargs)
def state(sid):return _state(client,sid)
def say(sid,text):return _send(client,sid,text,timeout=120)
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
def new_sid(scene='control_panel'):
    return new_session(client,scene)

def ok(cond,note):return ('passed' if cond else 'FAILED_MODEL_BEHAVIOR'),note

assert req('GET','/health')['backend_mode']=='live','live backend required'

# Group 1: natural-language pause / resume around a real task
g1=new_sid()
case('nl_task_start',g1,'把 B 逆时针转 30 度，接着检查 C 的背面。',
     lambda j,s: ok(j['status']=='done' and s['queue'] and s['queue'][0]['semantic']['target_id']=='B',
                    f'queue={[t["semantic"]["target_id"] for t in s["queue"]]}'))
case('nl_pause',g1,'暂停一下，先别继续',lambda j,s: ok(s['execution']=='paused',f'execution={s["execution"]}'))
case('nl_resume',g1,'继续刚才没做完的那步',
     lambda j,s: ok(s['execution']=='running' and s['queue'] and s['queue'][0]['semantic']['target_id']=='B',
                    f'execution={s["execution"]} queue={[t["semantic"]["target_id"] for t in s["queue"]]}'))

# Group 2: angle and order on a fresh session
g2=new_sid()
def c2(j,s):
    q=s['queue'];b=next((t for t in q if t['semantic']['target_id']=='B'),None)
    return ok(b is not None and b['semantic'].get('angle_deg')==15 and q[0]['semantic']['target_id']=='B',
              f'queue={[t["semantic"]["target_id"] for t in q]} angle={b and b["semantic"].get("angle_deg")}')
case('angle_order',g2,'B 先逆时针转 15 度，之后再看 A',c2)

# Group 3: nested interrupt and explicit completion of the temporary task
g3=new_sid()
case('nested_start',g3,'把 B 逆时针转 30 度，接着检查 C 的背面。',
     lambda j,s: ok(j['status']=='done' and s['queue'] and s['queue'][0]['semantic']['target_id']=='B','start ok'))
def c3(j,s):
    return ok(len(s['suspended'])>=1 and any(t['semantic']['target_id']=='B' for q2 in s['suspended'] for t in q2)
              and (not s['queue'] or s['queue'][0]['semantic']['target_id']=='C'),
              f'suspended={[[t["semantic"]["target_id"] for t in q2] for q2 in s["suspended"]]}')
case('nested_interrupt',g3,'别转了，先检查 C 的背面，回头还要接着做 B',c3)
case('complete_temp',g3,'把刚才临时检查的任务结束掉',
     lambda j,s: ok(any(t['semantic']['target_id']=='C' for t in s['completed']) and not s['queue'],
                    f'completed={[t["semantic"]["target_id"] for t in s["completed"]]}'))
case('resume_after_complete',g3,'继续刚才 B 的任务。',
     lambda j,s: ok(any(t['semantic']['target_id']=='B' for t in s['queue']),'B back in queue'))

# Group 4: clarification and rejection behaviours (fresh sessions each)
g4=new_sid()
def c4(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    return ok(d.get('operation')=='clarify' or s['last_error'] is not None,
              f'operation={d.get("operation")} msg={s["assistant_message"][:40]}')
case('clarify_angle',g4,'这个旋钮转一点',c4)
g5=new_sid()
def c5(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    clarified=d.get('operation')=='clarify'
    rejected=j['status']=='error' and 'Z' in (s.get('last_error') or '')
    return ok(clarified or rejected,f'operation={d.get("operation")} error={(s.get("last_error") or "")[:60]}')
case('unknown_object',g5,'把不存在的 Z 转 30 度',c5)
g6=new_sid()
def c6(j,s):
    d=(j.get('data') or {}).get('decision') or {}
    rot_c=any(c.get('target_id')=='C' and c.get('action')=='rotate' for c in (d.get('cues') or []))
    return ok(j['status']=='error' or not rot_c,
              f'job={j["status"]} rotates_C={rot_c} error={(s.get("last_error") or "")[:60]}')
case('capability_violation',g6,'把 C 转 30 度',c6)

# Group 5: parameter-preserving interrupt
g7=new_sid()
case('keep_start',g7,'把 B 逆时针转 30 度，接着检查 C 的背面。',lambda j,s: ok(j['status']=='done','start ok'))
def c7(j,s):
    return ok((not s['queue'] or s['queue'][0]['semantic']['target_id']=='C') and len(s['suspended'])>=1,
              f'queue={[t["semantic"]["target_id"] for t in s["queue"]]} suspended={len(s["suspended"])}')
case('keep_params_show_c',g7,'显示 C，先保留 B 的操作参数',c7)

# Group 6: explicit replace scope (blocks scene, where A+BASE exist)
g8=new_sid('blocks')
def c8(j,s):
    return ok(any(t['semantic']['target_id']=='A' for t in s['queue']),
              f'queue={[t["semantic"]["target_id"] for t in s["queue"]]} suspended={len(s["suspended"])}')
case('replace_new_task',g8,'新建任务，把 A 放到底板 BASE 上',c8)

# Group 7: rapid double-send, only latest epoch may commit
g9=new_sid('control_panel')
s=state(g9)
j1=req('POST',f'/api/v1/sessions/{g9}/messages',json={'text':'把 B 逆时针转 30 度，接着检查 C 的背面。','request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
s2=state(g9)
j2=req('POST',f'/api/v1/sessions/{g9}/messages',json={'text':'先别管 B，看看 C 的背面，保留 B 的角度。','request_id':uuid.uuid4().hex,'expected_revision':s2['revision']})
t0=time.perf_counter()
while time.perf_counter()-t0<120:
    a1=req('GET','/api/v1/jobs/'+j1['id']);a2=req('GET','/api/v1/jobs/'+j2['id'])
    if a1['status']!='planning' and a2['status']!='planning':break
    time.sleep(.3)
superseded=a1['status']=='superseded';committed=a2['status']=='done'
report['cases'].append({'name':'rapid_double_send','job1':a1['status'],'job2':a2['status'],
    'verdict':'passed' if (superseded or a1['status']=='error') and committed else 'FAILED_EPOCH_RACE',
    'note':'first request must not commit after second epoch'});save()

# Group 8: model service down — checked while the model server is stopped externally
report['cases'].append({'name':'model_down','howto':'stop vLLM, send a message, expect job=error and session.last_error visible in UI/log','verdict':'MANUAL_STEP'});save()

report['summary']={'passed':sum(1 for c in report['cases'] if c['verdict']=='passed'),
 'model_failures':sum(1 for c in report['cases'] if c['verdict'] in ('FAILED_MODEL_BEHAVIOR','FAILED_EPOCH_RACE')),
 'harness_errors':sum(1 for c in report['cases'] if c['verdict']=='HARNESS_ERROR')}
save();client.close();print(path)
