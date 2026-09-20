"""Isolated operator sessions, asynchronous snapshots and a continuous display clock."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import threading
import time
import uuid

import httpx
import numpy as np
import viser

from .config import root,load_scene,list_scenes
from .models import DisplayPacket
from .response import profile
from .viewer_scene import SceneRenderer
from .bridge import atomic_json
from .versioning import VersionGate


class Operator:
    def __init__(self,client: viser.ClientHandle,base: str):
        self.client=client
        self.base=base.rstrip('/')
        self.http=httpx.Client(timeout=httpx.Timeout(5.,connect=3.),headers={
            'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {})
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix=f'operator-{client.client_id}')
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.renderer=None
        self.sid=None
        self.revision=-1
        self.epoch=-1
        self.pending=0
        self.gate=VersionGate()
        self.failed=False
        self.loaded=False
        self.last_snapshot=0.
        self.packet=None
        self.generation=0
        self.last_view_export=0.
        self.log_dir=root()/'runs/simulation/viewer'
        self.log_dir.mkdir(parents=True,exist_ok=True)
        self.log_file=self.log_dir/f'client_{client.client_id}.jsonl'
        choices=list_scenes()
        self.by_title={s['title']:s['scene_id'] for s in choices}
        initial_id=os.environ.get('HOLOCUE_INITIAL_SCENE',choices[0]['scene_id'])
        initial=next(s for s in choices if s['scene_id']==initial_id)
        gui=client.gui
        self.status=gui.add_markdown('连接场景服务')
        tabs=gui.add_tab_group()
        with tabs.add_tab('任务'):
            self.scene_choice=gui.add_dropdown('场景',options=list(self.by_title),initial_value=initial['title'],disabled=True)
            self.command=gui.add_text('任务指令',initial_value=initial['initial_instruction'])
            self.actions=gui.add_button_group('任务操作',['发送任务','暂停动作','确认完成','恢复任务'],visible=False)
            self.playback_speed=gui.add_number('动作播放速度',min=.1,max=2.,step=.05,initial_value=1.)
            self.message=gui.add_markdown('选择任务并提交指令')
            self.task_list=gui.add_markdown('任务队列为空')
            self.suspended_list=gui.add_markdown('')
            self.session_field=gui.add_text('会话标识',initial_value=os.environ.get('HOLOCUE_SESSION_ID',''))
            self.open_button=gui.add_button('打开已有会话')
        with tabs.add_tab('观察'):
            self.follow=gui.add_checkbox('跟随当前步骤',initial_value=True)
            self.target=gui.add_dropdown('观察对象',options=['等待场景'],initial_value='等待场景',disabled=True)
            self.view=gui.add_button_group('观察方式',['工作区域','目标特写','结构检查'],visible=False)
            self.inspect_text=gui.add_markdown('结构检查显示选中对象的真实网格与表面标签')
            self.focus_button=gui.add_button('聚焦选中对象',disabled=True)
        with tabs.add_tab('显示响应'):
            self.focus=gui.add_slider('焦点距离 米',min=.05,max=20.,step=.005,initial_value=1.)
            self.brightness=gui.add_slider('提示亮度',min=0.,max=4.,step=.05,initial_value=1.)
            self.focus_number=gui.add_number('焦点数值 米',min=.05,max=20.,step=.005,initial_value=1.)
            self.brightness_number=gui.add_number('亮度数值',min=0.,max=4.,step=.05,initial_value=1.)
            self.enabled=gui.add_checkbox('显示任务提示',initial_value=True)
            self.response_note=gui.add_markdown(
                '解析 Gaussian 包络仿真\n\n'+profile().profile_id+
                '\n\n参数来源：configs/preview_response.json；N 与 σ 分配来源：configs/display_policy.json。'+
                '\n\n焦点距离、Gaussian 宽度与亮度直接改变三维提示。显示放大倍率 '
                +str(profile().visual_magnification)+'。光学标定由物理后端提供。')
            self.response_values=gui.add_markdown('等待任务参数')

        @self.scene_choice.on_update
        def change_scene(event):
            if event.client_id is not None:
                self.launch(self.load,self.by_title[self.scene_choice.value],None)

        @self.actions.on_click
        def operation(event):
            label=event.target.value
            if label=='发送任务':
                self.launch(self.submit,self.command.value)
            else:
                self.launch(self.control,{'暂停动作':'pause','确认完成':'complete','恢复任务':'resume'}[label])

        @self.open_button.on_click
        def open_session(_):
            self.launch(self.load,None,self.session_field.value.strip())

        @self.view.on_click
        def select_view(event):
            mode={'工作区域':'workspace','目标特写':'detail','结构检查':'inspection'}[event.target.value]
            with self.lock:
                if self.renderer is None:
                    raise RuntimeError('scene is loading')
                self.renderer.select_view(mode,self.target.value)
                obj=self.renderer.objects[self.target.value]
                self.inspect_text.content=obj.label+'\n\n'+obj.description
                self.record('view',{'mode':mode,'target':obj.object_id})

        @self.focus_button.on_click
        def focus_selected(_):
            with self.lock:
                distance=self.renderer.focus_distance(self.target.value)
                if not .05<=distance<=20:
                    raise ValueError('focus distance outside the configured viewer range')
                self.focus.value=distance

        @self.focus.on_update
        def focus_value(_):
            self.focus_number.value=self.focus.value

        @self.focus_number.on_update
        def focus_number(_):
            self.focus.value=self.focus_number.value

        @self.brightness.on_update
        def brightness_value(_):
            self.brightness_number.value=self.brightness.value

        @self.brightness_number.on_update
        def brightness_number(_):
            self.brightness.value=self.brightness_number.value

        @client.camera.on_update
        def resized(_):
            with self.lock:
                if self.renderer and self.loaded and getattr(self,'camera_aspect',None)!=client.camera.aspect:
                    self.camera_aspect=client.camera.aspect
                    self.renderer.select_view(self.renderer.view_mode,self.target.value)

        self.launch(self.load,initial_id,os.environ.get('HOLOCUE_SESSION_ID'))
        threading.Thread(target=self.poll,daemon=True,name=f'poll-{client.client_id}').start()
        threading.Thread(target=self.animate,daemon=True,name=f'animate-{client.client_id}').start()

    def record(self,kind,data):
        with self.log_file.open('a',encoding='utf-8') as file:
            file.write(json.dumps({'time':time.time(),'kind':kind,'session_id':self.sid,**data},ensure_ascii=False)+'\n')

    def request(self,method,path,**kwargs):
        response=self.http.request(method,self.base+path,**kwargs)
        response.raise_for_status()
        return response.json()

    def launch(self,fn,*args):
        with self.lock:
            self.pending+=1
        future=self.executor.submit(fn,*args)
        def finish(result):
            with self.lock:
                self.pending-=1
            if result.cancelled():
                return
            error=result.exception()
            if error is not None:
                with self.lock:
                    self.failed=True
                    self.status.content='**执行错误**\n\n'+str(error)
                    self.record('error',{'type':type(error).__name__,'message':str(error)})
                result.result()
        future.add_done_callback(finish)
        return future

    def load(self,scene_id,sid):
        controls=(self.target,self.focus_button)
        self.scene_choice.disabled=True
        self.actions.visible=False
        self.view.visible=False
        for control in controls:
            control.disabled=True
        try:
            self.load_scene_session(scene_id,sid)
        finally:
            # A failed load still allows selecting a scene or opening a session.
            # Operations on scene nodes wait until the requested load succeeds.
            self.scene_choice.disabled=False
            self.actions.visible=self.loaded
            self.view.visible=self.loaded
            for control in controls:
                control.disabled=not self.loaded

    def load_scene_session(self,scene_id,sid):
        with self.lock:
            self.loaded=False;self.generation+=1;generation=self.generation
        if sid:
            state=self.request('GET',f'/api/v1/sessions/{sid}')
        else:
            state=self.request('POST','/api/v1/sessions',json={'scene_id':scene_id})
        spec=load_scene(state['scene_id'])
        with self.lock:
            if generation!=self.generation:
                return
            if self.renderer:
                self.renderer.close()
            self.renderer=SceneRenderer(self.client,spec)
            self.sid=state['session_id'];self.session_field.value=self.sid
            self.scene_choice.value=spec.title
            self.command.value=spec.initial_instruction
            self.target.options=[o.object_id for o in spec.objects]
            self.target.value=spec.objects[0].object_id
            self.packet=None;self.revision=-1;self.epoch=-1
            self.gate=VersionGate();self.failed=False;self.loaded=True
            self.renderer.select_view('workspace')
            self.focus.value=self.renderer.focus_distance(self.target.value)
            self.status.content=spec.title+'\n\n会话 '+self.sid
            self.inspect_text.content=spec.task_contract.setting
            self.record('scene_loaded',{'scene_id':spec.scene_id})

    def submit(self,text):
        if not text.strip():
            raise ValueError('任务指令不能为空')
        with self.lock:
            sid,generation=self.sid,self.generation
        state=self.request('GET',f'/api/v1/sessions/{sid}')
        receipt=self.request('POST',f'/api/v1/sessions/{sid}/messages',json={
            'text':text,'request_id':uuid.uuid4().hex,'expected_revision':state['revision']})
        with self.lock:
            if generation==self.generation:
                self.gate.require(state['revision']+1,receipt['epoch'])
                self.failed=False
                self.last_snapshot=0.

    def control(self,operation):
        with self.lock:
            sid,generation=self.sid,self.generation
        state=self.request('GET',f'/api/v1/sessions/{sid}')
        receipt=self.request('POST',f'/api/v1/sessions/{sid}/control/{operation}',json={'expected_revision':state['revision']})
        with self.lock:
            if generation==self.generation:
                self.gate.require(receipt['revision'],receipt['epoch'])
                self.failed=False
                self.last_snapshot=0.

    def accept(self,data,sid,generation):
        state=data['state'];packet=DisplayPacket.model_validate(data['display'])
        if packet.revision!=state['revision'] or packet.epoch!=state['epoch']:
            raise ValueError('snapshot state and display versions disagree')
        with self.lock:
            if sid!=self.sid or generation!=self.generation:
                return
            if not self.gate.admit(packet.revision,packet.epoch):
                return
            self.last_snapshot=time.perf_counter()
            if packet.revision==self.revision and packet.epoch==self.epoch:
                return
            old_current=next((c.task_id for c in self.packet.cues if c.task_role=='current'),None) if self.packet else None
            self.renderer.update_packet(packet)
            self.packet=packet;self.revision=packet.revision;self.epoch=packet.epoch
            self.status.content=f'**{self.renderer.spec.title}**\n\n{state["backend_mode"]} · {packet.execution} · {packet.revision}'
            self.message.content=state['assistant_message'] or ''
            if state['last_error']:
                self.message.content+='\n\n**执行错误** '+state['last_error']
            self.task_list.content='\n\n'.join(
                f'{i+1}. {task["semantic"]["target_id"]}　{task["semantic"]["instruction"]}'
                for i,task in enumerate(state['queue'])) or (
                    '临时任务已完成，原计划等待手动恢复。' if state['suspended'] else '当前没有待执行步骤。')
            if state['suspended']:
                saved='\n\n'.join(
                    f'{i+1}. {task["semantic"]["target_id"]}　{task["semantic"]["instruction"]}'
                    for i,task in enumerate(state['suspended'][-1]))
                self.suspended_list.content=(f'**已挂起 {len(state["suspended"])} 组计划，最近一组如下**\n\n'
                    +saved+'\n\n临时任务完成后，请点击“恢复任务”继续原计划。')
            else:
                self.suspended_list.content=''
            self.response_values.content='\n\n'.join(
                f'{c.target_id}　{c.task_role}　N {c.n_gaussians}　σ {c.sigma_value:g}' for c in packet.cues)
            current=next((c for c in packet.cues if c.task_role=='current'),None)
            if current:
                self.target.value=current.target_id
                if self.follow.value and old_current!=current.task_id:
                    mode='inspection' if current.action=='inspect_back' else 'detail' if current.action=='rotate' else 'workspace'
                    self.renderer.select_view(mode,current.target_id)
                    self.focus.value=self.renderer.focus_distance(current.target_id)
                    self.inspect_text.content=self.renderer.objects[current.target_id].description
            self.record('snapshot',{'revision':packet.revision,'epoch':packet.epoch,
                'scene_id':packet.scene_id,'backend_mode':state['backend_mode'],
                'execution':packet.execution,'tasks':[c.task_id for c in packet.cues]})

    def poll(self):
        while not self.stop.wait(.2):
            with self.lock:
                sid,generation=self.sid,self.generation
                ready=self.loaded and not self.failed
            if not ready:
                continue
            future=self.executor.submit(self.request,'GET',f'/api/v1/sessions/{sid}/snapshot')
            error=future.exception()
            if error is not None:
                with self.lock:
                    self.failed=True
                    self.status.content='**连接错误**\n\n'+str(error)
                    self.record('connection_error',{'message':str(error)})
                # Keep this polling thread available for an explicit operator retry.
                # failed stays set, and animation stays frozen, until load/control/submit succeeds.
                continue
            self.accept(future.result(),sid,generation)

    def animate(self):
        previous=time.perf_counter()
        while not self.stop.wait(1/30):
            now=time.perf_counter();dt=now-previous;previous=now
            with self.lock:
                if self.renderer is None or not self.loaded:
                    continue
                running=(not self.pending and not self.failed and now-self.last_snapshot<.8
                         and self.packet is not None and self.packet.execution=='running'
                         and self.gate.current(self.packet.revision,self.packet.epoch))
                self.renderer.tick(dt*self.playback_speed.value,now,self.focus.value,self.brightness.value,self.enabled.value,running)
                if now-self.last_view_export>=.2:
                    cam=self.client.camera
                    atomic_json(self.log_dir/f'client_{self.client.client_id}_view.json',{
                        'session_id':self.sid,'scene_id':self.renderer.spec.scene_id,
                        'revision':self.revision,'epoch':self.epoch,
                        'execution':self.packet.execution if self.packet else 'loading',
                        'clock_advancing':running,
                        'generated_at':time.time(),'position_m':list(cam.position),
                        'look_at_m':list(cam.look_at),'focus_m':self.focus.value,
                        'up_direction':list(cam.up_direction),'fov_rad':float(cam.fov),
                        'aspect':float(cam.aspect),
                        'brightness':self.brightness.value,'enabled':self.enabled.value,
                        'playback_speed':self.playback_speed.value,
                        'view_mode':self.renderer.view_mode,'selected_id':self.renderer.selected_id,
                        'elapsed_s':dict(self.renderer.clock.elapsed)})
                    self.last_view_export=now

    def close(self):
        self.stop.set()
        self.executor.shutdown(wait=True,cancel_futures=True)
        self.http.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://127.0.0.1:8750')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8780)
    args=parser.parse_args()
    if args.host not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Use a loopback address and an SSH tunnel for the viewer')
    server=viser.ViserServer(host=args.host,port=args.port)
    server.gui.configure_theme(dark_mode=False,control_layout='collapsible')
    operators={}
    @server.on_client_connect
    def connect(client):
        operators[client.client_id]=Operator(client,args.api)
    @server.on_client_disconnect
    def disconnect(client):
        operators.pop(client.client_id).close()
    threading.Event().wait()


if __name__=='__main__':
    main()
