"""Live E2E acceptance for the engine_bay scene (engine round).

Five groups (E1-E5) against a live vLLM backend, following scripts/live_extended.py:
POST /sessions, POST /messages with request_id+expected_revision, poll the job to a
terminal status, then assert on queue/suspended/completed/assistant_message/display.

Honesty rules: model outputs (raw_response / raw_http_body / decision) are recorded
verbatim. Failures are recorded with their cause and are never retried to overwrite
the truth; no scripted answers are substituted for model output.
"""
import argparse, json, os, time, uuid
from pathlib import Path
import httpx

SCENE = 'engine_bay'
INIT = '把 CLAMP 逆时针转 90 度，接着把 PLUG 插进 PLUGPORT，最后检查 CONN 的背面。'

p = argparse.ArgumentParser()
p.add_argument('--api', default='http://127.0.0.1:8750')
p.add_argument('--out', default='runs/engine_round/live_engine_round.json')
a = p.parse_args()

headers = {'Authorization': 'Bearer ' + os.environ['HOLOCUE_API_KEY']} if os.getenv('HOLOCUE_API_KEY') else {}
client = httpx.Client(base_url=a.api, headers=headers, timeout=30)
report = {'backend_mode': 'live', 'scene': SCENE, 'cases': [], 'summary': {}}
path = Path(a.out)
path.parent.mkdir(parents=True, exist_ok=True)


def save():
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def req(method, url, **kw):
    r = client.request(method, url, **kw)
    r.raise_for_status()
    return r.json()


def state(sid):
    return req('GET', f'/api/v1/sessions/{sid}')


def display(sid):
    return req('GET', f'/api/v1/sessions/{sid}/display')


def control(sid, operation):
    s = state(sid)
    return req('POST', f'/api/v1/sessions/{sid}/control/{operation}',
               json={'expected_revision': s['revision']})


def say(sid, text, timeout=150.0):
    """One planner turn; returns (job, session_state, display_packet, elapsed)."""
    s = state(sid)
    t0 = time.perf_counter()
    j = req('POST', f'/api/v1/sessions/{sid}/messages',
            json={'text': text, 'request_id': uuid.uuid4().hex, 'expected_revision': s['revision']})
    while j['status'] == 'planning':
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError('planner timeout')
        time.sleep(0.3)
        j = req('GET', '/api/v1/jobs/' + j['id'])
    return j, state(sid), display(sid), time.perf_counter() - t0


def new_sid():
    return req('POST', '/api/v1/sessions', json={'scene_id': SCENE})['session_id']


def cues_of(s):
    return [t['semantic'] for t in s['queue']]


def snap(s, d):
    """Compact but complete snapshot of the final state + display for the report."""
    return {
        'revision': s['revision'], 'epoch': s['epoch'], 'execution': s['execution'],
        'assistant_message': s['assistant_message'], 'last_error': s.get('last_error'),
        'queue': [dict(t['semantic'], task_id=t['task_id']) for t in s['queue']],
        'suspended': [[dict(t['semantic'], task_id=t['task_id']) for t in q] for q in s['suspended']],
        'completed': [dict(t['semantic'], task_id=t['task_id']) for t in s['completed']],
        'display': {
            'revision': d['revision'], 'execution': d['execution'],
            'budget_total': d['budget_total'],
            'sum_n_gaussians': sum(c['n_gaussians'] for c in d['cues']),
            'cues': [{'target_id': c['target_id'], 'action': c['action'], 'task_role': c['task_role'],
                      'cue_type': c['cue_type'], 'angle_deg': c['angle_deg'], 'reference_id': c['reference_id'],
                      'depth_requirement': c['depth_requirement'], 'priority': c['priority'],
                      'n_gaussians': c['n_gaussians'], 'sigma_value': c['sigma_value'],
                      'sigma_profile': c['sigma_profile']} for c in d['cues']],
        },
    }


def record(name, sid, text, steps, verdict):
    """steps: list of step dicts (each with its own raw evidence)."""
    report['cases'].append({'name': name, 'session_id': sid, 'input': text, 'steps': steps,
                            'verdict': verdict[0], 'note': verdict[1]})


def check(steps, name, cond, detail):
    """Append a named assertion result to the current step; returns cond."""
    steps[-1]['checks'].append({'name': name, 'passed': bool(cond), 'detail': detail})
    return bool(cond)


def begin_step(steps, label, text, j, s, d, elapsed):
    steps.append({'label': label, 'input': text, 'job_status': j['status'],
                  'latency_s': round(elapsed, 2),
                  'operation': (j.get('data') or {}).get('decision', {}).get('operation'),
                  'job_error': (j.get('data') or {}).get('error'),
                  'raw_response': (j.get('data') or {}).get('raw_response'),
                  'raw_http_body': ((j.get('data') or {}).get('raw_http_body')
                                    if (j.get('data') or {}).get('error') or j['status'] == 'error' else None),
                  'raw_decision': (j.get('data') or {}).get('decision'),
                  'state': snap(s, d), 'checks': []})


assert req('GET', '/health')['backend_mode'] == 'live', 'live backend required'

# ---------------------------------------------------------------- E1 initial plan
e1_sid = new_sid()
steps = []
j, s, d, el = say(e1_sid, INIT)
begin_step(steps, 'E1', INIT, j, s, d, el)
dec = (j.get('data') or {}).get('decision') or {}
cs = dec.get('cues') or []
ok_all = True
ok_all &= check(steps, 'job_done', j['status'] == 'done', f'job={j["status"]}')
ok_all &= check(steps, 'operation_replace', dec.get('operation') == 'replace',
                f'operation={dec.get("operation")}')
ok_all &= check(steps, 'at_least_2_cues', len(cs) >= 2, f'n_cues={len(cs)}')
first = cs[0] if cs else {}
ok_all &= check(steps, 'first_cue_current_CLAMP_rotate_90',
                first.get('target_id') == 'CLAMP' and first.get('action') == 'rotate'
                and first.get('task_role') == 'current' and first.get('angle_deg') == 90,
                f'first={first}')
plug = next((c for c in cs if c.get('target_id') == 'PLUG'), None)
ok_all &= check(steps, 'PLUG_insert_ref_PLUGPORT',
                plug and plug.get('action') == 'insert' and plug.get('reference_id') == 'PLUGPORT',
                f'plug={plug}')
conn = next((c for c in cs if c.get('target_id') == 'CONN'), None)
ok_all &= check(steps, 'CONN_inspect_back', conn and conn.get('action') == 'inspect_back',
                f'conn={conn}')
dc = d['cues']
sum_n = sum(c['n_gaussians'] for c in dc)
ok_all &= check(steps, 'N_conservation_6000',
                d['budget_total'] == 6000 and len(dc) >= 2 and sum_n == d['budget_total'],
                f'budget={d["budget_total"]} sum_n={sum_n} per_cue={[(c["target_id"], c["n_gaussians"]) for c in dc]}')
ok_all &= check(steps, 'sigma_positive', all(c['sigma_value'] > 0 for c in dc),
                f'sigmas={[(c["target_id"], c["depth_requirement"], c["sigma_value"]) for c in dc]}')
sig = {(c['depth_requirement']): c['sigma_value'] for c in dc}
ok_all &= check(steps, 'sigma_precise_ne_persistent',
                'precise' in sig and 'persistent' in sig and sig['precise'] != sig['persistent'],
                f'sigma_by_depth={sig}')
record('E1_initial', e1_sid, INIT, steps, ('passed' if ok_all else 'FAILED', 'see checks'))
save()

# ---------------------------------------------------------------- E2 interrupt (same session)
steps = []
E2 = '先别管卡箍，直接看 CONN 的背面。'
j, s, d, el = say(e1_sid, E2)
begin_step(steps, 'E2', E2, j, s, d, el)
dec = (j.get('data') or {}).get('decision') or {}
ok_all = check(steps, 'job_done', j['status'] == 'done', f'job={j["status"]}')
ok_all &= check(steps, 'operation_interrupt', dec.get('operation') == 'interrupt',
                f'operation={dec.get("operation")}')
ok_all &= check(steps, 'suspended_depth_1_with_CLAMP',
                len(s['suspended']) == 1 and any(t['semantic']['target_id'] == 'CLAMP'
                                                 for t in s['suspended'][0]),
                f'suspended={[[t["semantic"]["target_id"] for t in q] for q in s["suspended"]]}')
q0 = cues_of(s)[0] if s['queue'] else {}
ok_all &= check(steps, 'new_cue_CONN_current',
                q0.get('target_id') == 'CONN' and q0.get('task_role') == 'current',
                f'queue0={q0}')
record('E2_interrupt', e1_sid, E2, steps, ('passed' if ok_all else 'FAILED', 'see checks'))
save()

# ---------------------------------------------------------------- E3 resume (same session)
E3 = '继续刚才 CLAMP 的任务。'
steps = []
j, s, d, el = say(e1_sid, E3)
begin_step(steps, 'E3_literal', E3, j, s, d, el)
dec = (j.get('data') or {}).get('decision') or {}
blocked = j['status'] == 'error' and 'Complete the temporary task' in (s.get('last_error') or '')
steps[-1]['note'] = ('model chose resume while the temporary CONN task was still in the queue; '
                     'the domain guard rejected it' if blocked else '')
literal_ok = (j['status'] == 'done' and dec.get('operation') == 'resume')
if literal_ok:
    clamp = next((t['semantic'] for t in s['queue'] if t['semantic']['target_id'] == 'CLAMP'), None)
    literal_ok &= check(steps, 'suspended_popped', len(s['suspended']) == 0,
                        f'suspended={len(s["suspended"])}')
    literal_ok &= check(steps, 'CLAMP_back_angle90',
                        clamp is not None and clamp.get('angle_deg') == 90,
                        f'clamp={clamp}')
    record('E3_resume', e1_sid, E3, steps, ('passed' if literal_ok else 'FAILED', 'literal single message'))
else:
    check(steps, 'resume_blocked_by_design',
          blocked or j['status'] == 'error',
          f'job={j["status"]} last_error={s.get("last_error")}')
    # Designed workflow (same as the demo timeline): confirm the temporary task
    # complete, then resume. Nothing is substituted; both turns are model turns.
    c = control(e1_sid, 'complete')
    j2, s2, d2, el2 = say(e1_sid, E3)
    steps.append({'label': 'E3_complete_then_resume',
                  'input': f'[control complete rev={c["revision"]}] {E3}',
                  'job_status': j2['status'], 'latency_s': round(el2, 2),
                  'operation': (j2.get('data') or {}).get('decision', {}).get('operation'),
                  'job_error': (j2.get('data') or {}).get('error'),
                  'raw_response': (j2.get('data') or {}).get('raw_response'),
                  'raw_decision': (j2.get('data') or {}).get('decision'),
                  'state': snap(s2, d2), 'checks': [],
                  'note': 'literal E3 message hit the temp-task guard; retried as '
                          'confirm-complete + resume (the documented flow), evidence above kept'})
    dec2 = (j2.get('data') or {}).get('decision') or {}
    clamp = next((t['semantic'] for t in s2['queue'] if t['semantic']['target_id'] == 'CLAMP'), None)
    ok2 = check(steps, 'operation_resume', dec2.get('operation') == 'resume',
                f'operation={dec2.get("operation")}')
    ok2 &= check(steps, 'suspended_popped', len(s2['suspended']) == 0,
                 f'suspended={len(s2["suspended"])}')
    ok2 &= check(steps, 'CLAMP_back_angle90',
                 clamp is not None and clamp.get('angle_deg') == 90,
                 f'clamp={clamp}')
    record('E3_resume', e1_sid, E3, steps,
           ('passed' if ok2 and blocked else 'FAILED',
            'resume reached via confirm-complete; literal attempt preserved in E3_literal'))
save()

# ---------------------------------------------------------------- E4 replace semantics (fresh session)
e4_sid = new_sid()
steps = []
j, s, d, el = say(e4_sid, INIT)
begin_step(steps, 'E4_init', INIT, j, s, d, el)
rev0 = s['revision']
E4 = 'CLAMP 改成顺时针转 45 度。'
j, s, d, el = say(e4_sid, E4)
begin_step(steps, 'E4_replace', E4, j, s, d, el)
dec = (j.get('data') or {}).get('decision') or {}
cs = dec.get('cues') or []
ok_all = check(steps, 'job_done', j['status'] == 'done', f'job={j["status"]}')
ok_all &= check(steps, 'operation_replace', dec.get('operation') == 'replace',
                f'operation={dec.get("operation")}')
ok_all &= check(steps, 'revision_advanced', s['revision'] > rev0,
                f'rev {rev0}->{s["revision"]}')
clamp = next((c for c in cs if c.get('target_id') == 'CLAMP'), None)
ok_all &= check(steps, 'new_CLAMP_rotate_45',
                clamp and clamp.get('action') == 'rotate' and abs(clamp.get('angle_deg') or 0) == 45,
                f'clamp={clamp}')
ok_all &= check(steps, 'old_90_cue_gone_from_display',
                not any(c['target_id'] == 'CLAMP' and c['angle_deg'] == 90 for c in d['cues'])
                and not any(c['target_id'] == 'CLAMP' and c['angle_deg'] == 90
                            for t in s['queue'] for c in [t['semantic']]),
                f'display_clamp={[(c["target_id"], c["angle_deg"]) for c in d["cues"]]}')
ok_all &= check(steps, 'suspended_cleared_by_replace', len(s['suspended']) == 0,
                f'suspended={len(s["suspended"])}')
ok_all &= check(steps, 'new_plan_is_current_version', d['revision'] == s['revision'],
                f'display rev={d["revision"]} session rev={s["revision"]}')
record('E4_replace', e4_sid, E4, steps, ('passed' if ok_all else 'FAILED', 'see checks'))
save()

# ---------------------------------------------------------------- E5 capability violation (fresh session)
e5_sid = new_sid()
steps = []
E5 = '把 PLUG 旋转 720 度。'
j, s, d, el = say(e5_sid, E5)
begin_step(steps, 'E5', E5, j, s, d, el)
dec = (j.get('data') or {}).get('decision') or {}
cs = dec.get('cues') or []
violating = [c for c in cs if c.get('target_id') == 'PLUG' and c.get('action') == 'rotate']
disp_violating = [c for c in d['cues'] if c['target_id'] == 'PLUG' and c['action'] == 'rotate']
if j['status'] == 'error':
    # Rejection path A: the model emitted the violating cue and the domain validator
    # rejected it. The visible error and the raw output must both be preserved.
    ok_all = check(steps, 'visible_error_PLUG_rotate',
                   s.get('last_error') is not None and 'PLUG' in s['last_error']
                   and 'rotate' in s['last_error'],
                   f'last_error={s.get("last_error")}')
    ok_all &= check(steps, 'job_data_error_kept', (j.get('data') or {}).get('error') is not None
                    and (j.get('data') or {}).get('raw_response') is not None,
                    'job.data.error + job.data.raw_response preserved')
elif j['status'] == 'done':
    # Rejection path B: the model itself refused to emit a violating cue (clarify or a
    # non-rotate cue). Its raw decision is the evidence.
    ok_all = check(steps, 'model_refused_violating_cue', not violating,
                   f'cues={cs}')
else:
    ok_all = check(steps, 'terminal_status', False, f'job={j["status"]}')
ok_all &= check(steps, 'no_violating_cue_in_display', not disp_violating,
                f'display_plug={[c for c in d["cues"] if c["target_id"] == "PLUG"]}')
ok_all &= check(steps, 'session_readable_revision_intact',
                s['revision'] >= 2 and d['revision'] == s['revision'],
                f'rev={s["revision"]} display rev={d["revision"]} epoch={s["epoch"]}')
record('E5_capability_violation', e5_sid, E5, steps, ('passed' if ok_all else 'FAILED', 'see checks'))
save()

report['summary'] = {
    'groups': {c['name']: c['verdict'] for c in report['cases']},
    'passed': sum(1 for c in report['cases'] if c['verdict'] == 'passed'),
    'failed': sum(1 for c in report['cases'] if c['verdict'] != 'passed'),
}
save()
client.close()
print(path)
for name, verdict in report['summary']['groups'].items():
    print(f'{name}: {verdict}')
