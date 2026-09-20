"""Exercise all authored workflows against a real local-model API."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import uuid

import httpx
import numpy as np

from holocue.config import root,list_scenes,load_scene
from holocue.models import DisplayCue,Pose
from holocue.spatial import matrix,trajectory


class LiveRun:
    def __init__(self,client,output):
        self.client=client;self.output=output;self.steps=[]

    def request(self,method,path,**kwargs):
        response=self.client.request(method,path,**kwargs)
        self.steps.append({'method':method,'path':path,'request':kwargs.get('json'),
                           'status':response.status_code,'response':response.text,'time':time.time()})
        (self.output/'http.json').write_text(json.dumps(self.steps,ensure_ascii=False,indent=2),encoding='utf-8')
        response.raise_for_status()
        return response.json()

    def state(self,sid):
        state=self.request('GET',f'/api/v1/sessions/{sid}')
        if state['backend_mode']!='live':
            raise ValueError('live model execution is required')
        return state

    def message(self,sid,text):
        state=self.state(sid)
        job=self.request('POST',f'/api/v1/sessions/{sid}/messages',json={
            'text':text,'expected_revision':state['revision'],'request_id':uuid.uuid4().hex})
        started=time.monotonic()
        while True:
            result=self.request('GET',f'/api/v1/jobs/{job["id"]}')
            if result['status']=='done':
                if result['data']['backend_mode']!='live' or not result['data']['raw_response']:
                    raise ValueError('model evidence is incomplete')
                evidence=result['data']
                wire=json.loads(evidence['raw_http_body'])['choices'][0]['message']['content']
                if wire!=evidence['raw_response']:
                    raise AssertionError('recorded model content differs from the HTTP response')
                decision=json.loads(wire)
                if decision!=evidence['decision']:
                    raise AssertionError('committed decision differs from raw model output')
                if decision['operation']!='clarify' and decision['assistant_message'] is not None:
                    raise AssertionError('model generated an extra execution narrative')
                state=self.state(sid)
                if state['assistant_message']!=decision['assistant_message']:
                    raise AssertionError('state replaced the actual model question or null field')
                if json.loads(state['history'][-1]['content'])!=decision:
                    raise AssertionError('committed history differs from the real decision')
                return state
            if result['status']!='planning':
                raise RuntimeError(json.dumps(result,ensure_ascii=False))
            if time.monotonic()-started>120:
                raise TimeoutError('model planning exceeded 120 seconds')
            time.sleep(.2)

    def control(self,sid,operation):
        state=self.state(sid)
        return self.request('POST',f'/api/v1/sessions/{sid}/control/{operation}',
                            json={'expected_revision':state['revision']})


def signature(task):
    cue=task['semantic']
    return cue['target_id'],cue['action'],cue.get('reference_id'),cue.get('angle_deg')


def require_persistent_visible(snapshot,targets):
    displayed={cue['target_id']:cue for cue in snapshot['display']['cues']}
    for target in targets:
        cue=displayed.get(target)
        if cue is None or cue['task_role']!='background' or cue['n_gaussians']<=0:
            raise AssertionError(f'Persistent background {target} is not visibly allocated')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--api',default='http://127.0.0.1:8750')
    parser.add_argument('--out',type=Path,default=root()/'runs/simulation/live')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    rows=[]
    with httpx.Client(base_url=args.api,timeout=10,headers=headers) as client:
        health=client.get('/health');health.raise_for_status()
        if health.json()['backend_mode']!='live':
            raise ValueError('API must use the live model')
        for item in list_scenes():
            spec=load_scene(item['scene_id']);directory=args.out/spec.scene_id;directory.mkdir(exist_ok=True)
            run=LiveRun(client,directory)
            initial=run.request('POST','/api/v1/sessions',json={'scene_id':spec.scene_id})
            sid=initial['session_id'];state=run.message(sid,spec.initial_instruction)
            initial_tasks=[t for t in state['queue'] if t['semantic']['task_role']!='background']
            expected=[(s.target_id,s.action,s.reference_id,s.angle_deg) for s in spec.task_contract.ordered_steps]
            actual=[signature(t) for t in initial_tasks]
            if actual!=expected:
                raise AssertionError(f'{spec.scene_id}: expected {expected}, received {actual}')
            background={t['semantic']['target_id'] for t in state['queue'] if t['semantic']['task_role']=='background'}
            if background!=set(spec.task_contract.persistent_targets):
                raise AssertionError(f'{spec.scene_id}: persistent targets {background}')
            initial_snapshot=run.request('GET',f'/api/v1/sessions/{sid}/snapshot')
            (directory/'initial_snapshot.json').write_text(json.dumps(initial_snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
            require_persistent_visible(initial_snapshot,spec.task_contract.persistent_targets)
            initial_ids=[t['task_id'] for t in state['queue']]
            original_queue=state['queue']
            paused=run.control(sid,'pause')
            if paused['execution']!='paused':
                raise AssertionError('pause failed')
            run.control(sid,'resume')
            state=run.message(sid,spec.task_contract.interrupt_instruction)
            if not state['suspended'] or [t['task_id'] for t in state['suspended'][-1]]!=initial_ids:
                raise AssertionError('interruption did not preserve the original plan identity')
            if state['suspended'][-1]!=original_queue:
                raise AssertionError('interruption changed the saved task parameters')
            if len(state['queue'])!=1 or signature(state['queue'][0])!=(spec.task_contract.interrupt_target,'inspect_back',None,None):
                raise AssertionError('temporary inspection added or changed a requested step')
            completed_temporary=run.control(sid,'complete')
            if completed_temporary['queue'] or completed_temporary['execution']!='idle' or completed_temporary['suspended'][-1]!=original_queue:
                raise AssertionError('temporary completion did not leave the original plan suspended')
            (directory/'temporary_completed.json').write_text(json.dumps(completed_temporary,ensure_ascii=False,indent=2),encoding='utf-8')
            state=run.message(sid,'请恢复挂起的原计划，保留原来的任务参数。')
            # The temporary queue is already empty; restoring it must retain every task identity.
            if [t['task_id'] for t in state['queue']]!=initial_ids:
                raise AssertionError('restored task identities differ')
            if [signature(t) for t in state['queue'] if t['semantic']['task_role']!='background']!=actual:
                raise AssertionError('restored task parameters differ')
            frames=[];completed_frames=[]
            for expected_task in expected:
                if signature(state['queue'][0])!=expected_task:
                    raise AssertionError('task order changed during completion')
                snapshot=run.request('GET',f'/api/v1/sessions/{sid}/snapshot')
                if snapshot['state']['revision']!=snapshot['display']['revision']:
                    raise AssertionError('snapshot is not atomic')
                require_persistent_visible(snapshot,spec.task_contract.persistent_targets)
                frames.append(snapshot)
                cue=DisplayCue.model_validate(snapshot['display']['cues'][0])
                endpoint=trajectory(cue,cue.interaction.duration_s)
                state=run.control(sid,'complete')
                confirmed=run.request('GET',f'/api/v1/sessions/{sid}/snapshot')
                pose=Pose.model_validate(confirmed['display']['object_poses'][cue.target_id])
                if not np.allclose(matrix(pose),matrix(endpoint),atol=1e-7):
                    raise AssertionError(f'Explicit completion did not update {cue.target_id} to its endpoint')
                if state['queue']:
                    require_persistent_visible(confirmed,spec.task_contract.persistent_targets)
                completed_frames.append(confirmed)
            if state['queue'] or state['execution']!='idle':
                raise AssertionError('workflow did not reach idle')
            (directory/'snapshots.json').write_text(json.dumps(frames,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'completed_snapshots.json').write_text(json.dumps(completed_frames,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'final.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append({'scene_id':spec.scene_id,'session_id':sid,'passed':True,'steps':len(expected),'backend_mode':'live'})
            (args.out/'report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            print(spec.scene_id,'live workflow passed',flush=True)
    if len(rows)!=12:
        raise AssertionError('all twelve scenes must run')


if __name__=='__main__':
    main()
