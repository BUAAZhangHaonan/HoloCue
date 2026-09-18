"""Viser front end. One operator/session at a time, with versioned backend polling."""
from __future__ import annotations
import argparse,os,time,threading,uuid
import httpx,numpy as np,trimesh
from .config import root,load_scene,list_scenes
from .models import DisplayPacket
from .geometry import primitive_pool,display_pose
from .preview import response_panel

class Viewer:
    def __init__(self,base:str,host:str,port:int):
        import viser
        if host not in ('127.0.0.1','localhost','::1'):
            raise ValueError('Viser is loopback-only in phase 1. Use an SSH tunnel.')
        self.base=base.rstrip('/');self.headers={}
        if os.environ.get('HOLOCUE_API_KEY'):self.headers['Authorization']='Bearer '+os.environ['HOLOCUE_API_KEY']
        self.http=httpx.Client(timeout=5,headers=self.headers)
        self.server=viser.ViserServer(host=host,port=port)
        self.server.scene.set_up_direction('+z')
        self.server.gui.configure_theme(dark_mode=False,control_layout='collapsible')
        self.lock=threading.RLock();self.sid=None;self.active_scene=None
        self.world=[];self.cue_handles=[];self.motion=[];self.current_packet=None;self.scene_bounds={}
        self.packet_key=None;self.phase=0.;self.last_tick=time.perf_counter();self.last_poll=0.
        items=list_scenes();self.titles={x['title']:x['scene_id'] for x in items}
        # The control stack is tabbed so long queues/preview imagery never crowd the
        # task controls; the four operations share one button group row.
        # viser 1.1.1: tab-group handles are not context managers, tab handles are.
        tabs=self.server.gui.add_tab_group()
        # HOLOCUE_INITIAL_SCENE selects the kit the viewer opens with (evidence
        # captures per scene); default stays the first kit in the sorted list.
        init_id=os.environ.get('HOLOCUE_INITIAL_SCENE') or items[0]['scene_id']
        init_title=next((i['title'] for i in items if i['scene_id']==init_id),items[0]['title'])
        init_instruction=next((i['initial_instruction'] for i in items if i['title']==init_title),'')
        with tabs.add_tab('任务'):
            self.status=self.server.gui.add_markdown('正在连接后端')
            self.scene_choice=self.server.gui.add_dropdown('场景',options=list(self.titles),initial_value=init_title)
            self.command=self.server.gui.add_text('输入任务',initial_value=init_instruction)
            self.actions=self.server.gui.add_button_group('操作',['发送并更新任务','立即暂停','确认完成','继续'])
            self.detail=self.server.gui.add_markdown('任务尚未开始')
        with tabs.add_tab('显示'):
            self.focus=self.server.gui.add_slider('示意焦点',min=-1.5,max=1.5,step=.05,initial_value=0.)
            self.preview=self.server.gui.add_image(response_panel([],0),label='响应设计示意')
            self.warning=self.server.gui.add_markdown('几何提示与示意焦点预览;真实波场由后续光学后端接入。')
        @self.scene_choice.on_update
        def scene_changed(_):
            try:self.load(self.titles[self.scene_choice.value])
            except Exception as e:self.status.content=f'**场景加载错误**\n\n{e}'
        @self.actions.on_click
        def act(event):
            # viser 1.1.1 passes a GuiEvent; the clicked label is the group's value.
            val=event.target.value
            if val=='发送并更新任务':self.worker(self.submit,self.command.value)
            elif val=='立即暂停':self.worker(self.control,'pause')
            elif val=='确认完成':self.worker(self.control,'complete')
            elif val=='继续':self.worker(self.control,'resume')
        @self.focus.on_update
        def focus(_):
            with self.lock:
                if self.current_packet:self.preview.image=response_panel(self.current_packet.cues,self.focus.value)
        @self.server.on_client_connect
        def connect(client):
            with self.lock:
                if self.active_scene:
                    pos,look=self._camera(self.active_scene,self.scene_bounds.get(self.active_scene.scene_id,[]))
                    client.camera.position=pos;client.camera.look_at=look
        try:
            self.load(init_id)
        except Exception as e:  # noqa: BLE001 - fall back loudly, never crash the viewer
            print(f'[viewer] HOLOCUE_INITIAL_SCENE={init_id!r} failed ({e!r}); loading first kit instead')
            self.load(items[0]['scene_id'])
    def _camera(self,spec,bounds):
        """JSON camera by default; with fit_camera, back off along its axis until the
        scene bbox fills ~70% of a 50 deg perspective view (JSON positions were
        authored for orthographic framing and read as 'scene too small' in Viser)."""
        import math
        pos=np.asarray(spec.camera_position_m,float);look=np.asarray(spec.camera_look_at_m,float)
        if not spec.render_hints.fit_camera or not bounds:
            return pos,look
        lo=np.min([b[0] for b in bounds],axis=0);hi=np.max([b[1] for b in bounds],axis=0)
        radius=float(np.linalg.norm(hi-lo)/2)
        direction=pos-look;n=np.linalg.norm(direction)
        if n<1e-6:return pos,look
        dist=radius/math.tan(math.radians(25.))/0.7
        return look+direction/n*dist,look
    def request(self,method,path,**kwargs):
        r=self.http.request(method,self.base+path,**kwargs)
        r.raise_for_status();return r.json()
    def worker(self,fn,*args):
        def run():
            try:fn(*args)
            except Exception as e:self.status.content=f'**请求未完成**\n\n{e}'
        threading.Thread(target=run,daemon=True).start()
    def load(self,scene_id):
        s=self.request('POST','/api/v1/sessions',json={'scene_id':scene_id})
        spec=load_scene(scene_id)
        with self.lock:
            self.sid=s['session_id'];self.active_scene=spec;self.packet_key=None
            for h in self.world+self.cue_handles:h.remove()
            self.world=[];self.cue_handles=[];self.motion=[];self.current_packet=None
            rh=spec.render_hints
            bounds=[]
            self.world.append(self.server.scene.add_grid('/world/grid',width=rh.grid_extent_m,height=rh.grid_extent_m))
            if spec.environment:
                # Environment props are scenery only: no labels, never planner objects,
                # and never part of the fit_camera bbox: a scene shell that encloses the
                # subject (engine_bay garage, incl. far-away props) pushed the backup to
                # ~7x the authored distance, shrinking the subject and rendering the
                # fixed 2.4 mm cue points sub-pixel (invisible). Fit the task subject.
                for p in spec.environment:
                    mesh=trimesh.load(root()/p.asset,force='mesh');mesh.apply_scale(p.scale_m)
                    self.world.append(self.server.scene.add_mesh_trimesh('/world/env/'+p.prop_id,mesh,position=p.pose.position_m,wxyz=p.pose.wxyz))
            else:
                bench=trimesh.creation.box((.65,.58,.018));bench.apply_translation((0,.08,-.009))
                self.world.append(self.server.scene.add_mesh_simple('/world/bench',bench.vertices,bench.faces,color=(224,231,236)))
            for o in spec.objects:
                mesh=trimesh.load(root()/o.asset,force='mesh')
                self.world.append(self.server.scene.add_mesh_trimesh('/world/'+o.object_id,mesh,position=o.pose.position_m,wxyz=o.pose.wxyz))
                bounds.append(mesh.bounds+np.asarray(o.pose.position_m))
                p=np.asarray(o.pose.position_m)+[0,0,rh.label_offset_m]
                self.world.append(self.server.scene.add_label('/world_labels/'+o.object_id,o.label,position=p))
            self.command.value=spec.initial_instruction
            self.scene_bounds[scene_id]=bounds
            cam_pos,cam_look=self._camera(spec,bounds)
            for client in self.server.get_clients().values():
                client.camera.position=cam_pos;client.camera.look_at=cam_look
            self.status.content=f'**{spec.title}**\n\n会话 {self.sid[:8]}'
    def submit(self,text):
        with self.lock:sid=self.sid
        s=self.request('GET',f'/api/v1/sessions/{sid}')
        self.request('POST',f'/api/v1/sessions/{sid}/messages',json={'text':text,'request_id':uuid.uuid4().hex,'expected_revision':s['revision']})
    def control(self,operation):
        with self.lock:sid=self.sid
        s=self.request('GET',f'/api/v1/sessions/{sid}')
        self.request('POST',f'/api/v1/sessions/{sid}/control/{operation}',json={'expected_revision':s['revision']})
    def refresh(self,p:DisplayPacket,state:dict):
        with self.lock:
            if p.session_id!=self.sid:return
            key=(p.revision,p.epoch)
            old=self.current_packet
            self.current_packet=p
            if key!=self.packet_key:
                old_ids=[c.task_id for c in old.cues] if old else []
                new_ids=[c.task_id for c in p.cues]
                if old_ids!=new_ids:self.phase=0.
                for h in self.cue_handles:h.remove()
                self.cue_handles=[];self.motion=[]
                objects={o.object_id:o for o in self.active_scene.objects}
                rh=self.active_scene.render_hints
                for i,c in enumerate(p.cues):
                    if c.n_gaussians<=0:continue
                    name=f'/cues/{i}'
                    kind=c.cue_type if c.cue_type in ('ring_arrow','straight_arrow') else 'highlight'
                    pts=primitive_pool(kind)[:c.n_gaussians]*rh.cue_scale
                    rgb=(60,153,144) if c.task_role=='current' else (147,173,190)
                    h=self.server.scene.add_point_cloud(name+'/points',points=pts,colors=np.tile(np.asarray(rgb,dtype=np.uint8),(len(pts),1)),point_size=.0024,position=c.pose.position_m,wxyz=c.pose.wxyz)
                    self.cue_handles.append(h)
                    self.cue_handles.append(self.server.scene.add_label(name+'/text',c.instruction,position=np.asarray(c.pose.position_m)+[0,0,rh.label_offset_m+.05]))
                    if c.cue_type=='ghost_motion':
                        mesh=trimesh.load(root()/objects[c.target_id].asset,force='mesh')
                        ghost=self.server.scene.add_mesh_simple(name+'/ghost',mesh.vertices,mesh.faces,color=(78,181,171),opacity=.5,position=c.pose.position_m,wxyz=c.pose.wxyz)
                        self.cue_handles.append(ghost)
                        if c.task_role=='current':self.motion.append((ghost,c))
                    elif c.action=='rotate' and c.task_role=='current':self.motion.append((h,c))
                self.packet_key=key
                self.preview.image=response_panel(p.cues,self.focus.value)
            error=state.get('last_error')
            self.status.content=f"**{self.active_scene.title}**\n\n模式 {state['backend_mode']}  ·  状态 {p.execution}  ·  版本 {p.revision}"
            if error:self.status.content+='\n\n**错误** '+error
            queue='\n'.join(f"- {c.target_id}  {c.task_role}  N {c.n_gaussians}  σ {c.sigma_value:g}" for c in p.cues)
            self.detail.content=f"{state['assistant_message']}\n\n{queue}\n\n挂起计划 {len(state['suspended'])}  ·  完成步骤 {len(state['completed'])}"
    def run(self):
        while True:
            now=time.perf_counter();dt=min(now-self.last_tick,.2);self.last_tick=now
            with self.lock:
                if self.current_packet and self.current_packet.execution=='running':self.phase+=dt
                for handle,cue in self.motion:
                    pos,q=display_pose(cue,self.phase,True);handle.position=pos;handle.wxyz=q
                sid=self.sid
            if now-self.last_poll>.20:
                self.last_poll=now
                try:
                    p=DisplayPacket.model_validate(self.request('GET',f'/api/v1/sessions/{sid}/display'))
                    state=self.request('GET',f'/api/v1/sessions/{sid}')
                    self.refresh(p,state)
                except Exception as e:
                    # Freeze the visualization when a fresh authoritative state is unavailable.
                    with self.lock:
                        if self.current_packet:self.current_packet.execution='paused'
                    self.status.content=f'**后端连接中断，动作已停住**\n\n{e}'
            time.sleep(max(0.,1/30-(time.perf_counter()-now)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--api',default='http://127.0.0.1:8750');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8780)
    a=p.parse_args();Viewer(a.api,a.host,a.port).run()
if __name__=='__main__':main()
