"""Real UI-driven twelve-scene, same-client native Blender bridge evidence.

Run with the project's .work/task_env.sh environment already sourced.
No model response or application state is supplied by this audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx
import numpy as np
import psutil
from PIL import Image
from playwright.sync_api import sync_playwright

from holocue.config import root, load_scene, list_scenes
from holocue.models import DisplayCue, Pose
from holocue.spatial import matrix, trajectory, transform_points
from scripts.tests.audit_viewer_live import ui_input,CLIENT_READ,client_view_errors
from scripts.tests.live_twelve_scenes import signature


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def check_environment(output):
    project=root().resolve()
    if not (project/'.work/task_env.sh').is_file():
        raise FileNotFoundError('Source the project .work/task_env.sh before this audit')
    settings={}
    for name in ('TMPDIR','TMP','TEMP','XDG_CACHE_HOME','PIP_CACHE_DIR','PLAYWRIGHT_BROWSERS_PATH'):
        value=Path(os.environ[name]).resolve()
        if not value.is_relative_to(project/'.work') and not value.is_relative_to(project/'runs/simulation'):
            raise ValueError(f'{name} must resolve inside project .work or runs/simulation')
        settings[name]=str(value)
    if not output.is_relative_to(project/'runs/simulation') and not output.is_relative_to(project/'.work'):
        raise ValueError('--out must be inside the project .work or runs/simulation')
    blender=Path(os.environ['BLENDER_BIN']).resolve()
    if not blender.is_file():
        raise FileNotFoundError(blender)
    return settings, blender


class OwnedProcess:
    """Only descendants of this recorded Popen invocation may be stopped."""
    def __init__(self, command, directory, name):
        self.directory=directory
        self.name=name
        self.log=(directory/f'{name}.log').open('w',encoding='utf-8')
        environment=os.environ.copy()
        environment['CUDA_VISIBLE_DEVICES']=''
        self.process=subprocess.Popen(command,cwd=root(),env=environment,stdout=self.log,
            stderr=subprocess.STDOUT,start_new_session=True)
        self.identity=psutil.Process(self.process.pid)
        self.record={'command':command,'cwd':str(root()),'pid':self.process.pid,
            'create_time':self.identity.create_time(),'started_at':time.time(),'cuda_visible_devices':''}
        save(directory/f'{name}_process.json',self.record)

    def close(self):
        if self.process.poll() is None:
            # The guard starts its Blender child in a different process group.
            # Track the actual descendants rather than targeting a process name/group.
            try:
                descendants=self.identity.children(recursive=True)
            except psutil.NoSuchProcess:
                descendants=[]
            owned=list(reversed(descendants))+[self.identity]
            self.record['stopped_owned_pids']=[p.pid for p in owned]
            for process in owned:
                try:
                    if process.is_running():
                        process.terminate()
                except psutil.NoSuchProcess:
                    pass
            _,alive=psutil.wait_procs(owned,timeout=10)
            for process in alive:
                try:
                    if process.is_running():
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(alive,timeout=5)
            self.process.wait(timeout=5)
        self.record.update(returncode=self.process.returncode,finished_at=time.time())
        save(self.directory/f'{self.name}_process.json',self.record)
        self.log.close()


class Audit:
    def __init__(self, page, client, spec, directory, args, blender):
        self.page=page;self.http=client;self.spec=spec;self.out=directory
        self.args=args;self.blender=blender;self.sid=None;self.view_path=None
        self.exporter=None;self.stages=[];self.inspected=[];self.errors=[];self.focus_actions=[]
        self.page.set_default_timeout(60000)
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))

    def read(self,path):
        response=self.http.get(path)
        with (self.out/'api_reads.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'time':time.time(),'method':'GET','path':path,
                'status':response.status_code,'body':response.text},ensure_ascii=False)+'\n')
        response.raise_for_status()
        return response.json()

    def snapshot(self):
        data=self.read(f'/api/v1/sessions/{self.sid}/snapshot')
        state=data['state'];display=data['display']
        if state['backend_mode']!='live' or state['scene_id']!=self.spec.scene_id:
            raise AssertionError('Unexpected live session/scene')
        if (state['revision'],state['epoch'])!=(display['revision'],display['epoch']):
            raise AssertionError('Non-atomic snapshot')
        if state['execution']=='error' or state.get('last_error'):
            raise RuntimeError(json.dumps(state,ensure_ascii=False))
        return data

    def wait_state(self,predicate,timeout=130):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            data=self.snapshot()
            if predicate(data['state']):
                return data
            self.page.wait_for_timeout(150)
        raise TimeoutError('UI operation did not reach its expected state')

    def view(self, revision=None, mode=None, after=0., selected=None):
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            paths=[self.view_path] if self.view_path else list((root()/'runs/simulation/viewer').glob('client_*_view.json'))
            for path in paths:
                if not path.is_file():
                    continue
                data=json.loads(path.read_text(encoding='utf-8'))
                if data['session_id']!=self.sid or data['scene_id']!=self.spec.scene_id:
                    continue
                if data['generated_at']<=after or time.time()-data['generated_at']>2:
                    continue
                if revision is not None and data['revision']!=revision:
                    continue
                if mode is not None and data['view_mode']!=mode:
                    continue
                if selected is not None and data['selected_id']!=selected:
                    continue
                self.view_path=path
                return data
            self.page.wait_for_timeout(100)
        raise TimeoutError('Current client did not export a matching view')

    def tab(self,name):
        tab=self.page.get_by_role('tab',name=name,exact=True)
        if tab.get_attribute('aria-selected')!='true':
            tab.click()

    def dropdown(self,label,value):
        self.page.get_by_role('combobox',name=label,exact=True).click()
        self.page.get_by_role('option',name=value,exact=True).click()

    def control(self,name,execution=None):
        before=self.snapshot()['state']
        self.tab('任务')
        self.page.get_by_role('button',name=name,exact=True).click()
        data=self.wait_state(lambda s:s['revision']>before['revision'] and
            (execution is None or s['execution']==execution))
        self.view(revision=data['state']['revision'])
        return data

    def send(self,text):
        before=self.snapshot()['state']['revision']
        self.tab('任务')
        ui_input(self.page,'任务指令').fill(text)
        ui_input(self.page,'任务指令').press('Tab')
        self.page.get_by_role('button',name='发送任务',exact=True).click()
        data=self.wait_state(lambda s:s['revision']>=before+2 and s['execution']=='running')
        save(self.out/'events.json',self.read(f'/api/v1/sessions/{self.sid}/events'))
        return data

    def select_view(self,mode,target=None):
        self.tab('观察')
        ui_input(self.page,'跟随当前步骤').uncheck()
        if target is not None:
            self.dropdown('观察对象',target)
        before=time.time()
        self.page.get_by_role('button',name={'workspace':'工作区域','detail':'目标特写','inspection':'结构检查'}[mode],exact=True).click()
        view=self.view(mode=mode,after=before,selected=target)
        # A viewport resize can publish its view-mode before the browser has
        # sent the new aspect and the server has refitted the camera. Use the
        # actual rendered camera before computing the expected focus depth.
        deadline=time.monotonic()+25
        camera_checks=[]
        stable_since=None
        previous_camera=None
        camera_exports=set()
        while True:
            view=self.view(mode=mode,after=before,selected=target)
            check=client_view_errors(self.page.evaluate(CLIENT_READ),view)
            camera=np.concatenate([view['position_m'],view['look_at_m'],
                view['up_direction'],[view['fov_rad'],view['aspect']]])
            now=time.monotonic()
            if not check['passed']:
                stable_since=None
                camera_exports.clear()
            elif previous_camera is None or not np.allclose(camera,previous_camera,rtol=0,atol=1e-7):
                stable_since=now
                camera_exports={view['generated_at']}
            elif stable_since is None:
                stable_since=now
                camera_exports={view['generated_at']}
            else:
                camera_exports.add(view['generated_at'])
            check['stable_camera_seconds']=0. if stable_since is None else now-stable_since
            check['view_generated_at']=view['generated_at']
            check['distinct_camera_exports']=len(camera_exports)
            camera_checks.append(check)
            previous_camera=camera
            if (check['passed'] and check['stable_camera_seconds']>=.75 and len(camera_exports)>=3) or now>deadline:
                break
            self.page.wait_for_timeout(100)
        with (self.out/'view_camera_checks.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'requested_at':before,'mode':mode,'target':target,
                'finished_at':time.time(),'checks':camera_checks})+'\n')
        if not check['passed'] or check['stable_camera_seconds']<.75 or len(camera_exports)<3:
            raise AssertionError('Visible camera did not settle before focusing: '+json.dumps(check))
        if target is not None and view['selected_id']!=target:
            raise AssertionError('Observation dropdown selected another object')
        # Manual camera changes deliberately preserve the user's focal setting.
        # For a readable native inspection, use the actual focus control after
        # moving the camera, then verify its depth against the scene contract.
        snapshot=self.snapshot()
        obj=next(obj for obj in self.spec.objects if obj.object_id==view['selected_id'])
        inspection_focus=mode=='inspection' or any(
            cue['target_id']==obj.object_id and cue['action']=='inspect_back'
            for cue in snapshot['display']['cues'])
        local=np.asarray(obj.interaction.inspect_point_local_m if inspection_focus
                         else obj.interaction.cue_offset_local_m,dtype=float)
        if inspection_focus:
            local=local+np.asarray(obj.interaction.inspect_normal_local)*obj.interaction.inspect_cue_clearance_m
        point=transform_points(Pose.model_validate(snapshot['display']['object_poses'][obj.object_id]),local[None,:])[0]
        forward=np.asarray(view['look_at_m'])-view['position_m']
        forward/=np.linalg.norm(forward)
        expected_focus=float((point-np.asarray(view['position_m']))@forward)
        before_focus=view['focus_m'];before=time.time()
        self.page.get_by_role('button',name='聚焦选中对象',exact=True).click()
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            view=self.view(mode=mode,after=before,selected=target)
            if abs(view['focus_m']-expected_focus)<1e-6:
                break
            self.page.wait_for_timeout(100)
        else:
            save(self.out/'focus_failure.json',{'expected_depth_m':expected_focus,
                'before_focus_m':before_focus,'observed_view':view,
                'focus_point_m':point.tolist(),'camera_before_focus':camera.tolist(),
                'snapshot':snapshot})
            raise AssertionError('Visible focus control did not focus the contracted target plane')
        self.focus_actions.append({'time':time.time(),'mode':mode,'target':obj.object_id,
            'previous_focus_m':before_focus,'expected_depth_m':expected_focus,
            'observed_focus_m':view['focus_m'],'control':'聚焦选中对象',
            'revision':view['revision'],'epoch':view['epoch']})
        save(self.out/'focus_actions.json',self.focus_actions)
        self.page.wait_for_timeout(250)
        return view

    def open(self):
        self.page.goto(self.args.viewer,wait_until='networkidle')
        software_notice=self.page.get_by_role('alert').filter(has_text='Software WebGL rendering detected')
        if software_notice.count():
            software_notice.get_by_role('button').click()
        self.tab('任务')
        deadline=time.monotonic()+30
        while not ui_input(self.page,'会话标识').input_value():
            if time.monotonic()>deadline:
                raise TimeoutError('Initial Viser session did not finish loading')
            self.page.wait_for_timeout(100)
        # Force an explicit new-session scene transition, even when the server's
        # initial scene matches the requested scene or carries an existing ID.
        other=next(row for row in list_scenes() if row['scene_id']!=self.spec.scene_id)
        self.dropdown('场景',other['title'])
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            sid=ui_input(self.page,'会话标识').input_value()
            if sid and self.read(f'/api/v1/sessions/{sid}')['scene_id']==other['scene_id']:
                break
            self.page.wait_for_timeout(100)
        else:
            raise TimeoutError('Scene switch did not create a session')
        previous=sid
        self.dropdown('场景',self.spec.title)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            sid=ui_input(self.page,'会话标识').input_value()
            if sid and sid!=previous:
                state=self.read(f'/api/v1/sessions/{sid}')
                if state['scene_id']==self.spec.scene_id:
                    self.sid=sid
                    break
            self.page.wait_for_timeout(100)
        if self.sid is None:
            raise TimeoutError('Requested scene did not create a fresh UI session')
        self.view()
        save(self.out/'session.json',{'session_id':self.sid,'scene_id':self.spec.scene_id,
            'client_view_path':str(self.view_path),'created_through':'Viser scene dropdown'})

    def start_exporter(self):
        command=[sys.executable,'scripts/scenes/export_live_frames.py','--session',self.sid,
            '--api',self.args.api,'--view-state',str(self.view_path),'--seconds','21600','--hz','10']
        self.exporter=OwnedProcess(command,self.out,'exporter')

    def wait_frame(self,snapshot,view):
        path=root()/'runs/simulation/bridge'/f'{self.sid}.json'
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            if self.exporter.process.poll() is not None:
                raise RuntimeError(f'Exporter exited: {self.exporter.process.returncode}')
            if path.is_file():
                data=json.loads(path.read_text(encoding='utf-8'))
                state=snapshot['state']
                if (data['session_id'],data['revision'],data['epoch'])==(self.sid,state['revision'],state['epoch']) and \
                    data['generated_at']>=view['generated_at'] and data['view_mode']==view['view_mode'] and \
                    data['selected_id']==view['selected_id']:
                    return path,data
            self.page.wait_for_timeout(100)
        raise TimeoutError('Exporter did not produce this client/version/view')

    def browser_sample(self,directory,index,reference):
        def same_view(actual):
            for key in ('session_id','scene_id','revision','epoch','execution','selected_id','view_mode','enabled'):
                if actual[key]!=reference[key]:
                    raise AssertionError(f'View changed during frozen capture: {key}')
            for key in ('position_m','look_at_m','up_direction','fov_rad','aspect','focus_m','brightness'):
                if not np.allclose(actual[key],reference[key],rtol=0,atol=1e-7):
                    raise AssertionError(f'Camera or response changed during frozen capture: {key}')
            if actual['elapsed_s']!=reference['elapsed_s']:
                raise AssertionError('Task clock changed during frozen capture')
        canvas=self.page.locator('canvas[data-engine]')
        def dimensions():
            return {'box':canvas.bounding_box(),**canvas.evaluate(
                '(element) => ({width:element.width,height:element.height,devicePixelRatio:window.devicePixelRatio})')}
        same_view(self.view(revision=reference['revision']))
        before=dimensions()
        if before['box'] is None:
            raise AssertionError('The real Three.js canvas is missing')
        filename=f'viser_sample_{index:02d}.png';started=time.time()
        self.page.screenshot(path=str(directory/filename),full_page=True,timeout=60000)
        finished=time.time();after=dimensions()
        same_view(self.view(revision=reference['revision']))
        box=before['box']
        bounds=(int(np.floor(box['x'])),int(np.floor(box['y'])),
                int(np.ceil(box['x']+box['width'])),int(np.ceil(box['y']+box['height'])))
        with Image.open(directory/filename) as captured:
            pixels=np.asarray(captured.convert('RGBA').crop(bounds))
        record={'file':filename,'started_at':started,'finished_at':finished,
            'dimensions_before':before,'dimensions_after':after,
            'dimensions_stable':before==after,
            'canvas_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),
            'png_sha256':hashlib.sha256((directory/filename).read_bytes()).hexdigest()}
        return record

    def settle_browser_capture(self,directory,reference,first):
        records=[first]
        for index in range(1,6):
            current=self.browser_sample(directory,index,reference)
            previous=records[-1];records.append(current)
            stable=(previous['dimensions_stable'] and current['dimensions_stable'] and
                    previous['dimensions_after']==current['dimensions_before'] and
                    previous['canvas_sha256']==current['canvas_sha256'])
            save(directory/'browser_capture.json',{'passed':stable,'samples':records,
                'scope':'Consecutive identical real canvas pixels and rendering dimensions with frozen view and task clock; early images retained'})
            if stable:
                shutil.copyfile(directory/current['file'],directory/'viser.png')
                return
            self.page.wait_for_timeout(250)
        raise AssertionError('The real canvas did not settle to two identical captures')

    def capture(self,name,mode=None,target=None):
        directory=self.out/name;directory.mkdir()
        print(self.spec.scene_id,name,'capture started',flush=True)
        if mode is not None:
            self.select_view(mode,target)
        snapshot=self.snapshot()
        view=self.view(revision=snapshot['state']['revision'],after=time.time())
        frame_path,data=self.wait_frame(snapshot,view)
        save(directory/'snapshot.json',snapshot)
        save(directory/'view_state.json',view)
        save(directory/'exported_frame_before.json',data)
        if snapshot['state']['execution'] not in ('paused','idle'):
            raise AssertionError('Native evidence must freeze the real task before capture')
        first_browser_sample=self.browser_sample(directory,0,view)
        save(directory/'browser_capture.json',{'passed':False,'samples':[first_browser_sample],
            'scope':'Awaiting native render and a subsequent matching real canvas capture'})
        command=[sys.executable,'scripts/guard/resource_guard.py','--gpus','2','--rss-limit-gb','12',
            '--log',str(directory/'resource_guard.jsonl'),'--execute','--',str(self.blender),
            '-b',str(root()/'scenes'/self.spec.scene_id/'scene.blend'),'-t','4',
            '--python-exit-code','1','--python','scripts/capture/blender_simulation_bridge.py',
            '--','--frame-file',str(frame_path),'--capture',str(directory),'--frames','1','--device','CUDA']
        owned=OwnedProcess(command,directory,'blender')
        wait_started=time.monotonic()
        last_activity=wait_started
        log_signature=None
        wait_policy={'total_timeout_s':5400,'no_log_progress_timeout_s':300,
            'scope':'Offline native evidence capture; rendering quality and resource guards are unchanged'}
        save(directory/'native_wait_policy.json',wait_policy)
        try:
            deadline=wait_started+wait_policy['total_timeout_s']
            while owned.process.poll() is None:
                if self.exporter.process.poll() is not None:
                    raise RuntimeError('Exporter stopped during native Blender capture')
                log_stat=(directory/'blender.log').stat()
                signature=(log_stat.st_size,log_stat.st_mtime_ns)
                if signature!=log_signature:
                    log_signature=signature
                    last_activity=time.monotonic()
                if time.monotonic()>deadline:
                    raise TimeoutError('Offline native Blender capture exceeded ninety minutes')
                if time.monotonic()-last_activity>wait_policy['no_log_progress_timeout_s']:
                    raise TimeoutError('Native Blender produced no log progress for five minutes')
                self.page.wait_for_timeout(200)
            if owned.process.returncode:
                raise RuntimeError(f'Native Blender failed with code {owned.process.returncode}')
        finally:
            wait_policy.update(elapsed_s=time.monotonic()-wait_started,
                seconds_since_last_log_progress=time.monotonic()-last_activity,
                final_log_signature=log_signature)
            save(directory/'native_wait_policy.json',wait_policy)
            owned.close()
        consumed_path=directory/'consumed_frame_0000.json'
        if not consumed_path.is_file():
            raise FileNotFoundError('Bridge must save its full consumed_frame_0000.json payload')
        consumed=json.loads(consumed_path.read_text(encoding='utf-8'))
        if (consumed['session_id'],consumed['revision'],consumed['epoch'])!=(self.sid,data['revision'],data['epoch']):
            raise AssertionError('Blender consumed another session or task version')
        if consumed['view_mode']!=view['view_mode'] or consumed['selected_id']!=view['selected_id']:
            raise AssertionError('Blender consumed another operator view')
        for key in ('position_m','look_at_m','up_direction','fov_rad','aspect','focus_m','brightness'):
            if not np.allclose(consumed['camera'][key],data['camera'][key]):
                raise AssertionError(f'Camera/response mismatch: {key}')
        if consumed['response_profile']!=data['response_profile']:
            raise AssertionError('Response provenance changed during bridge capture')
        for object_id,pose in data['object_poses'].items():
            if not np.allclose(matrix(Pose.model_validate(pose)),
                    matrix(Pose.model_validate(consumed['object_poses'][object_id])),atol=1e-7):
                raise AssertionError(f'Bridge entity pose mismatch: {object_id}')
        if snapshot['state']['execution'] in ('paused','idle'):
            expected_cues={cue['task_id']:cue for cue in data['cues']}
            if {cue['task_id'] for cue in consumed['cues']}!=set(expected_cues):
                raise AssertionError('Bridge cue task identities differ')
            for cue in consumed['cues']:
                expected_cue=expected_cues[cue['task_id']]
                for key in ('centers_m','radii_m','opacities','rgb','elapsed_s','n_gaussians'):
                    if not np.allclose(cue[key],expected_cue[key],atol=1e-7):
                        raise AssertionError(f'Paused bridge response differs: {cue["task_id"]}/{key}')
        if not (directory/'frame_0000.png').is_file():
            raise FileNotFoundError('Native Blender did not write its image')
        if self.errors:
            raise AssertionError(json.dumps(self.errors,ensure_ascii=False))
        self.settle_browser_capture(directory,view,first_browser_sample)
        result={'stage':name,'revision':data['revision'],'epoch':data['epoch'],
            'target':view['selected_id'],'view':view['view_mode'],'directory':str(directory),
            'frame_sha256':hashlib.sha256(consumed_path.read_bytes()).hexdigest()}
        self.stages.append(result);save(self.out/'stages.json',self.stages)
        print(self.spec.scene_id,name,'native capture verified',flush=True)
        return snapshot,view

    def wait_elapsed(self,task_id,minimum):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            view=self.view()
            if view['elapsed_s'].get(task_id,0.)>=minimum:
                return view
            self.page.wait_for_timeout(70)
        raise TimeoutError('Action did not advance to the required recorded progress')

    def object_views(self):
        directory=self.out/'objects';directory.mkdir()
        self.tab('显示响应')
        ui_input(self.page,'显示任务提示').uncheck()
        for obj in self.spec.objects:
            modes=['detail','inspection'] if 'inspect_back' in obj.capabilities else ['detail']
            for mode in modes:
                name=f'{obj.object_id}_{mode}'
                _,view=self.capture('object_'+name,mode,obj.object_id)
                self.page.screenshot(path=str(directory/f'{name}.png'),full_page=True)
                save(directory/f'{name}.json',view)
                self.inspected.append({'object_id':obj.object_id,'view':mode,'image':str(directory/f'{name}.png'),
                    'blender':str(self.out/('object_'+name)/'frame_0000.png'),'guidance_enabled':False})
        self.tab('显示响应')
        ui_input(self.page,'显示任务提示').check()
        save(self.out/'viewed_objects.json',self.inspected)

    def workflow(self):
        self.open()
        # The visible playback control allows a human or the audit to pause at
        # distinct action times without changing a task's angle/path/duration.
        self.tab('任务')
        ui_input(self.page,'动作播放速度').fill('0.1')
        ui_input(self.page,'动作播放速度').press('Tab')
        initial=self.send(self.spec.initial_instruction)
        initial_tasks=initial['state']['queue']
        actionable=[task for task in initial_tasks if task['semantic']['task_role']!='background']
        expected=[(step.target_id,step.action,step.reference_id,step.angle_deg) for step in self.spec.task_contract.ordered_steps]
        if [signature(task) for task in actionable]!=expected:
            raise AssertionError('Real model ordered steps differ from scene contract')
        if {task['semantic']['target_id'] for task in initial_tasks if task['semantic']['task_role']=='background'}!=set(self.spec.task_contract.persistent_targets):
            raise AssertionError('Real model persistent targets differ from scene contract')
        self.control('暂停动作','paused')
        first=actionable[0];duration=next(obj for obj in self.spec.objects if obj.object_id==first['semantic']['target_id']).interaction.duration_s
        start_view=self.view()
        elapsed=start_view['elapsed_s'].get(first['task_id'],0.)
        save(self.out/'start_timing.json',{'observed_elapsed_s':elapsed,'duration_s':duration,
            'playback_speed':start_view['playback_speed'],
            'meaning':'first UI-confirmed paused state after real model response; no clock reset'})
        if elapsed>=duration*.75:
            raise AssertionError('Initial UI pause was too late to capture a distinct action middle')
        self.start_exporter()
        self.capture('01_start_paused','workspace')
        self.control('恢复任务','running')
        self.wait_elapsed(first['task_id'],(elapsed+duration)/2)
        self.control('暂停动作','paused')
        _,middle=self.capture('02_middle_paused')
        mid_elapsed=middle['elapsed_s'][first['task_id']]
        if not elapsed<mid_elapsed<duration:
            raise AssertionError('Recorded middle is not between action start and endpoint')
        saved=self.snapshot()['state']['queue']
        saved_clock=self.view()['elapsed_s'][first['task_id']]
        interrupted=self.send(self.spec.task_contract.interrupt_instruction)
        if interrupted['state']['suspended'][-1]!=saved:
            raise AssertionError('Interruption changed task identities or parameters')
        if len(interrupted['state']['queue'])!=1:
            raise AssertionError('Temporary inspection copied an original task or added an unrequested step')
        temporary=interrupted['state']['queue'][0]
        if temporary['semantic']['target_id']!=self.spec.task_contract.interrupt_target or temporary['semantic']['action']!='inspect_back':
            raise AssertionError('Temporary inspection has the wrong target or action')
        self.control('暂停动作','paused')
        self.capture('03_temporary_inspection','inspection',temporary['semantic']['target_id'])
        self.page.set_viewport_size({'width':1100,'height':800})
        narrow=self.select_view('inspection',temporary['semantic']['target_id'])
        self.page.screenshot(path=str(self.out/'temporary_narrow.png'),full_page=True)
        save(self.out/'temporary_narrow.json',narrow)
        self.page.set_viewport_size({'width':1600,'height':1000})
        done=self.control('确认完成','idle')
        if done['state']['completed'][-1]['task_id']!=temporary['task_id']:
            raise AssertionError('Confirmation completed another temporary task')
        save(self.out/'temporary_confirmed.json',done)
        resumed=self.control('恢复任务','running')
        if resumed['state']['queue']!=saved:
            raise AssertionError('UI resume did not restore the original tasks and parameters')
        self.control('暂停动作','paused')
        first_semantic=first['semantic']
        first_reference=first_semantic.get('reference_id')
        restored_mode=('inspection' if first_semantic['action']=='inspect_back' else
                       'workspace' if first_reference else 'detail')
        _,restored=self.capture('04_original_restored',restored_mode,first_semantic['target_id'])
        if not saved_clock<=restored['elapsed_s'].get(first['task_id'],0.)<duration:
            raise AssertionError('Resume reset the interrupted clock or skipped its remaining motion')
        self.control('恢复任务','running')
        self.wait_elapsed(first['task_id'],duration+.2)
        self.control('暂停动作','paused')
        end,_=self.capture('05_endpoint_waiting')
        if end['state']['queue']!=initial_tasks or any(t['task_id']==first['task_id'] for t in end['state']['completed']):
            raise AssertionError('Animation endpoint improperly completed or changed a task')
        if first_reference:
            receiver,_=self.capture('05_endpoint_receiver','detail',first_reference)
            if receiver['state']!=end['state']:
                raise AssertionError('Receiver observation changed the paused task state')
        for index,expected_signature in enumerate(expected):
            snapshot=self.snapshot();current=snapshot['state']['queue'][0]
            if signature(current)!=expected_signature or current['task_id']!=actionable[index]['task_id']:
                raise AssertionError('Completion order or task identity changed')
            cue=DisplayCue.model_validate(snapshot['display']['cues'][0])
            mode='inspection' if cue.action=='inspect_back' else 'detail'
            if index and cue.action in ('rotate','insert','assemble'):
                # A source-only detail crops distant receivers and transit paths.
                # Retain the full operation and then inspect its receiving opening.
                motion_mode='workspace' if cue.reference_id else mode
                _,start=self.capture(f'step_{index:02d}_start',motion_mode,cue.target_id)
                started=start['elapsed_s'].get(cue.task_id,0.)
                if started>=cue.interaction.duration_s*.75:
                    raise AssertionError('Next action was not paused early enough for a distinct middle')
                self.control('恢复任务','running')
                self.wait_elapsed(cue.task_id,(started+cue.interaction.duration_s)/2)
                self.control('暂停动作','paused')
                _,mid=self.capture(f'step_{index:02d}_middle',motion_mode,cue.target_id)
                if not started<mid['elapsed_s'][cue.task_id]<cue.interaction.duration_s:
                    raise AssertionError('Next action middle is outside its time interval')
                self.control('恢复任务','running')
                self.wait_elapsed(cue.task_id,cue.interaction.duration_s+.2)
                self.control('暂停动作','paused')
                end,_=self.capture(f'step_{index:02d}_endpoint',motion_mode,cue.target_id)
                if cue.reference_id:
                    receiver,_=self.capture(f'step_{index:02d}_endpoint_receiver','detail',cue.reference_id)
                    if receiver['state']!=end['state']:
                        raise AssertionError('Receiver observation changed the paused task state')
            elif index:
                self.capture(f'step_{index:02d}_inspection',mode,cue.target_id)
            goal=trajectory(cue,cue.interaction.duration_s)
            after=self.control('确认完成')
            actual=Pose.model_validate(after['display']['object_poses'][cue.target_id])
            if not np.allclose(matrix(actual),matrix(goal),atol=1e-7):
                raise AssertionError(f'Completed object pose differs from endpoint: {cue.target_id}')
            if after['state']['queue']:
                self.control('暂停动作','paused')
            save(self.out/f'step_{index:02d}_confirmed.json',after)
        final=self.snapshot()
        if final['state']['queue'] or final['state']['suspended'] or final['state']['execution']!='idle':
            raise AssertionError('Workflow did not explicitly complete')
        self.capture('06_final_workspace','workspace')
        self.object_views()
        events=self.read(f'/api/v1/sessions/{self.sid}/events')
        save(self.out/'events.json',events)
        rows=events.get('events',[]) if isinstance(events,dict) else events
        commits=[row['data'] for row in rows if row['kind']=='plan_committed']
        if len(commits)<2 or any(not row.get('raw_response') or row.get('backend_mode')!='live' for row in commits):
            raise AssertionError('Missing raw live-model request/response evidence')
        save(self.out/'final.json',final)
        return {'scene_id':self.spec.scene_id,'session_id':self.sid,'client_view_path':str(self.view_path),
            'stages':self.stages,'viewed_objects':self.inspected,'browser_errors':self.errors,'passed':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://127.0.0.1:8750')
    parser.add_argument('--viewer',default='http://127.0.0.1:8780')
    parser.add_argument('--browser',type=Path)
    parser.add_argument('--out',type=Path,default=root()/'runs/simulation/bridge_live')
    parser.add_argument('--scenes',nargs='+')
    args=parser.parse_args();args.out=args.out.resolve()
    environment,blender=check_environment(args.out)
    args.out.mkdir(parents=True,exist_ok=False)
    save(args.out/'environment.json',environment)
    selected=args.scenes or [row['scene_id'] for row in list_scenes()]
    if len(selected)!=len(set(selected)):
        raise ValueError('Duplicate selected scenes')
    headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    launch={'headless':True,'args':['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    if args.browser:
        launch['executable_path']=str(args.browser)
    results=[]
    with httpx.Client(base_url=args.api,headers=headers,timeout=10) as http, sync_playwright() as playwright:
        browser=playwright.chromium.launch(**launch)
        try:
            for scene_id in selected:
                spec=load_scene(scene_id);directory=args.out/scene_id;directory.mkdir()
                context=browser.new_context(viewport={'width':1600,'height':1000},record_video_dir=str(directory/'video'))
                page=context.new_page();audit=Audit(page,http,spec,directory,args,blender)
                try:
                    results.append(audit.workflow())
                    print(scene_id,'native same-client bridge passed',flush=True)
                except Exception as error:
                    save(directory/'failure.json',{'type':type(error).__name__,'message':str(error),
                        'session_id':audit.sid,'stages':audit.stages,'browser_errors':audit.errors})
                    if audit.sid:
                        try:
                            save(directory/'events_on_failure.json',audit.read(f'/api/v1/sessions/{audit.sid}/events'))
                        except Exception as evidence_error:
                            save(directory/'event_capture_error.json',{'error':str(evidence_error)})
                    try:
                        page.screenshot(path=str(directory/'failure.png'),full_page=True)
                    except Exception as screenshot_error:
                        save(directory/'screenshot_error.json',{'error':str(screenshot_error)})
                    results.append({'scene_id':scene_id,'session_id':audit.sid,'passed':False,
                        'failure_type':type(error).__name__,'failure':str(error),
                        'stages':audit.stages,'browser_errors':audit.errors})
                    print(scene_id,'native same-client bridge failed:',str(error),flush=True)
                finally:
                    if audit.exporter is not None:
                        audit.exporter.close()
                    context.close()
                    save(args.out/'report.json',results)
        finally:
            browser.close()
    if len(results)!=len(selected) or any(not row['passed'] for row in results):
        raise AssertionError('Not all selected scenes completed')


if __name__=='__main__':
    main()
