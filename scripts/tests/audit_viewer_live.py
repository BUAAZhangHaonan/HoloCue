"""Capture real Viser interactions with a paused live-model task and raw evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import shutil

import httpx
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from scipy.spatial.transform import Rotation

from holocue.config import root,list_scenes,load_scene
from holocue.spatial import transform_points,rotation
from scripts.tests.live_twelve_scenes import LiveRun,signature


def ui_input(page,label):
    # Viser 1.1.1 renders the visible label separately from the input ID.
    # This selects the actual input in the observed control row.
    return page.get_by_text(label,exact=True).locator('xpath=ancestor::*[.//input][1]').locator('input')


VIEW_IDENTITY=('session_id','scene_id','revision','epoch','execution','selected_id','view_mode','enabled')
VIEW_NUMERIC=('position_m','look_at_m','up_direction','fov_rad','aspect','focus_m','brightness')
CLIENT_READ='''() => {
  const m=window.__viserMutable,c=m?.camera,canvas=m?.canvas;
  const root=window.__viserSceneTree?.getState()?.[""];
  const info=window.__viserTestpoints?.rendererInfo;
  if(!c||!canvas||!root?.wxyz||!m.cameraControl||!info) return {ready:false};
  // Read existing objects only. getTarget writes into a new scratch vector;
  // no camera/matrix/render/sort update or framebuffer mutation is requested.
  const target=c.position.clone(); m.cameraControl.getTarget(target);
  const gl=canvas.getContext('webgl2');
  if(!gl) return {ready:false};
  const box=canvas.getBoundingClientRect();
  return {ready:true,t:performance.now(),render_counter:info.render.frame,
    document_focus:document.hasFocus(),active_element:document.activeElement?.tagName,
    canvas:{width:canvas.width,height:canvas.height,
      box:{x:box.x,y:box.y,width:box.width,height:box.height},
      window_dpr:window.devicePixelRatio,viewport:{width:innerWidth,height:innerHeight},
      drawing_buffer:[gl.drawingBufferWidth,gl.drawingBufferHeight],
      gl_viewport:Array.from(gl.getParameter(gl.VIEWPORT)),
      default_framebuffer:gl.getParameter(gl.FRAMEBUFFER_BINDING)===null},
    root:{wxyz:root.wxyz,position:m.nodePoseData[""]?.position??root.position??[0,0,0]},
    camera:{position:c.position.toArray(),target:target.toArray(),up:c.up.toArray(),
      quaternion:c.quaternion.toArray(),matrix_world:c.matrixWorld.toArray(),
      matrix_world_inverse:c.matrixWorldInverse.toArray(),projection:c.projectionMatrix.toArray(),
      fov_rad:c.fov*Math.PI/180,aspect:c.aspect,near:c.near,far:c.far}};
}'''


def client_view_errors(client,view):
    """Compare actual Three camera readback in the Python-exposed world frame."""
    if not client.get('ready'):
        return {'passed':False,'reason':'Client readback is not ready'}
    camera=client['camera'];pose=client['root']
    inverse=Rotation.from_quat(pose['wxyz'],scalar_first=True).inv()
    position=inverse.apply(np.asarray(camera['position'])-pose['position'])
    target=inverse.apply(np.asarray(camera['target'])-pose['position'])
    up=inverse.apply(camera['up'])
    forward=inverse.apply(Rotation.from_quat(camera['quaternion']).apply([0,0,-1]))
    expected_forward=np.asarray(view['look_at_m'])-view['position_m']
    expected_forward/=np.linalg.norm(expected_forward)
    canvas=client['canvas'];box=canvas['box']
    pairs={'position_m':(position,view['position_m']),'look_at_m':(target,view['look_at_m']),
        'up_direction':(up,view['up_direction']),'forward':(forward,expected_forward),
        'fov_rad':(camera['fov_rad'],view['fov_rad']),'aspect':(camera['aspect'],view['aspect'])}
    errors={key:float(np.max(np.abs(np.asarray(a)-b))) for key,(a,b) in pairs.items()}
    expected_world=np.eye(4)
    expected_world[:3,:3]=Rotation.from_quat(camera['quaternion']).as_matrix()
    expected_world[:3,3]=camera['position']
    actual_world=np.asarray(camera['matrix_world']).reshape(4,4).T
    actual_inverse=np.asarray(camera['matrix_world_inverse']).reshape(4,4).T
    errors['matrix_world']=float(np.max(np.abs(actual_world-expected_world)))
    errors['matrix_world_inverse']=float(np.max(np.abs(actual_inverse-np.linalg.inv(expected_world))))
    errors['css_aspect']=abs(camera['aspect']-box['width']/max(box['height'],1))
    passed=(max(errors.values())<=1e-6 and box['width']>100 and box['height']>100
        and canvas['drawing_buffer']==[canvas['width'],canvas['height']]
        and canvas['default_framebuffer'])
    return {'passed':passed,'absolute_tolerance':1e-6,'errors':errors,
            'client_position_in_viser_world':position.tolist(),'client_target_in_viser_world':target.tolist()}


def same_view(left,right,*,camera=True):
    numeric=VIEW_NUMERIC if camera else ('focus_m','brightness')
    return (all(left[key]==right[key] for key in VIEW_IDENTITY)
        and not left['clock_advancing'] and not right['clock_advancing']
        and left['elapsed_s']==right['elapsed_s']
        and all(np.allclose(left[key],right[key],rtol=0,atol=1e-7) for key in numeric))


def same_client_frame(left,right):
    return (left.get('ready') and right.get('ready') and left['canvas']==right['canvas']
        and left['root']==right['root'] and all(np.allclose(left['camera'][key],right['camera'][key],
            rtol=0,atol=1e-7) for key in left['camera']))


def canvas_pixels(path,box,viewport,clip=None):
    """Hash the canvas part of the actual screenshot, accounting for CSS scale."""
    area=clip or {'x':0,'y':0,**viewport}
    with Image.open(path) as screenshot:
        scale=screenshot.width/area['width']
        if clip is not None and all(abs(box[key]-clip[key])<=1e-9 for key in ('x','y','width','height')):
            bounds=(0,0,screenshot.width,screenshot.height)
        else:
            # Only remove arithmetic noise at integer pixel boundaries. A real
            # fractional pixel still rounds outward and must fit in the image.
            edges=[(box['x']-area['x'])*scale,(box['y']-area['y'])*scale,
                   (box['x']+box['width']-area['x'])*scale,
                   (box['y']+box['height']-area['y'])*scale]
            edges=[round(value) if abs(value-round(value))<=1e-9 else value for value in edges]
            bounds=(int(np.floor(edges[0])),int(np.floor(edges[1])),
                    int(np.ceil(edges[2])),int(np.ceil(edges[3])))
        if bounds[0]<0 or bounds[1]<0 or bounds[2]>screenshot.width or bounds[3]>screenshot.height:
            raise AssertionError('Screenshot does not contain the entire observed canvas')
        pixels=np.asarray(screenshot.convert('RGBA').crop(bounds))
    return {'sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'shape':list(pixels.shape),'crop':list(bounds)}


def settled_canvas_pixels(path,before,after,clip=None):
    """Only associate screenshot pixels with bounds unchanged across the shot."""
    if not same_client_frame(before,after):
        return None
    canvas=before['canvas']
    return canvas_pixels(path,canvas['box'],canvas['viewport'],clip)


def assert_comparable_captures(left,right,*,changed_control=None,new_revision=False):
    """Reject response deltas that could instead come from camera/DPR changes."""
    if not same_client_frame(left['client_after'],right['client_after']):
        raise AssertionError('Response comparison changed client camera, viewport, backing size or DPR')
    for key in VIEW_IDENTITY:
        if new_revision and key in ('revision','epoch'):
            continue
        if left['view_after'][key]!=right['view_after'][key]:
            raise AssertionError('Response comparison changed view identity: '+key)
    for key in VIEW_NUMERIC:
        if key!=changed_control and not np.allclose(left['view_after'][key],right['view_after'][key],rtol=0,atol=1e-7):
            raise AssertionError('Response comparison changed another camera/response value: '+key)
    if not new_revision and left['view_after']['elapsed_s']!=right['view_after']['elapsed_s']:
        raise AssertionError('Response comparison changed the paused task clock')
    if left['pixels']['shape']!=right['pixels']['shape']:
        raise AssertionError('Response comparison changed screenshot pixel dimensions')


class BrowserRun:
    """All mutations use visible controls; HTTP is read-only evidence collection."""
    def __init__(self,page,http,out):
        self.page=page;self.read=LiveRun(http,out);self.out=out;self.actions=[]
        self.console=[]
        page.on('console',self.console_message)
        page.on('crash',lambda: self.record('browser_crash'))

    def console_message(self,message):
        if message.type in ('warning','error'):
            self.console.append({'time':time.time(),'type':message.type,'text':message.text})
            (self.out/'browser_console.json').write_text(json.dumps(self.console,ensure_ascii=False,indent=2))

    def record(self,operation,**data):
        self.actions.append({'time':time.time(),'operation':operation,**data})
        (self.out/'ui_actions.json').write_text(json.dumps(self.actions,ensure_ascii=False,indent=2))
        print(self.out.name,operation,flush=True)

    def state(self,sid):
        return self.read.state(sid)

    def view_button(self,label):
        started=time.time()
        self.record('view_click_started',button=label)
        try:
            self.page.get_by_role('button',name=label,exact=True).click()
        except Exception as error:
            self.record('view_click_failed',button=label,elapsed_s=time.time()-started,error=str(error))
            raise
        self.record('view_click_finished',button=label,elapsed_s=time.time()-started)
        return started

    def set_render_pixel_ratio(self,label):
        """Use Viser's visible setting for comparable response measurements."""
        if label not in ('1.0','Adaptive'):
            raise ValueError('Response measurements use 1.0; normal UI coverage uses Adaptive')
        page=self.page
        before=self.state(self.session_id)
        self.record('render_pixel_ratio_started',requested=label)
        page.locator('button').filter(has=page.locator('svg.tabler-icon-adjustments')).click()
        page.get_by_role('checkbox',name='Dev Settings',exact=True).check()
        field=page.get_by_role('combobox',name='Device Pixel Ratio',exact=True)
        previous=field.input_value()
        field.click()
        page.get_by_role('option',name=label,exact=True).click()
        value=field.input_value()
        if value!=label and not (label=='Adaptive' and value=='' and field.get_attribute('placeholder')=='Adaptive'):
            raise AssertionError('Visible render pixel ratio did not select '+label)
        (self.out/('pixel_ratio_'+label+'_dom.yaml')).write_text(page.locator('body').aria_snapshot())
        page.get_by_role('checkbox',name='Dev Settings',exact=True).uncheck()
        page.locator('button').filter(has=page.locator('svg.tabler-icon-arrow-back')).click()
        after=self.state(self.session_id)
        if before!=after:
            raise AssertionError('Render pixel ratio selection changed the task session')
        self.record('render_pixel_ratio_finished',requested=label,previous_visible_value=previous,
                    selected_visible_value=value,task_state_unchanged=True,
                    method='Existing Configuration & diagnostics / Dev Settings / Device Pixel Ratio UI')

    def capture(self,name,*,stable=False,expected_response=None,**kwargs):
        self.record('capture_started',file=name)
        started=time.monotonic()
        try:
            if stable:
                result=self.stable_capture(name,expected_response=expected_response,**kwargs)
            else:
                self.page.screenshot(path=str(self.out/name),timeout=60000,**kwargs)
                result=None
        except Exception as error:
            self.record('capture_failed',file=name,elapsed_s=time.monotonic()-started,error=str(error))
            views=[]
            for path in (root()/'runs/simulation/viewer').glob('client_*_view.json'):
                data=json.loads(path.read_text())
                if data.get('session_id')==getattr(self,'session_id',None):
                    views.append({'path':str(path),'view':data})
            (self.out/'capture_failure_views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2))
            raise
        self.record('capture_finished',file=name,elapsed_s=time.monotonic()-started)
        return result

    def stable_capture(self,name,*,expected_response=None,**kwargs):
        """Observe two settled real frames; retain the first frame and all retries."""
        sid=self.session_id
        deadline=time.monotonic()+420
        state=self.state(sid)
        if state['execution']!='paused':
            raise AssertionError('Stable evidence requires a real UI-paused task')
        def view():
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise TimeoutError('Paused canvas capture exceeded 420 seconds')
            return wait_view(sid,time.time()-.5,revision=state['revision'],timeout=min(25,remaining))
        reference=view()
        response=expected_response or {key:reference[key] for key in ('focus_m','brightness')}
        if not set(response).issubset({'focus_m','brightness'}):
            raise ValueError('Expected response may only assert focus_m and brightness')
        response={key:response.get(key,reference[key]) for key in ('focus_m','brightness')}
        stem=Path(name).stem
        report={'passed':False,'reference_view':reference,'expected_response':response,'samples':[],
            'scope':'Two consecutive matching actual canvas images, client camera/framebuffer and paused server identity; early images retained.',
            'timeout_s':420,'screenshot_timeout_s':60,'maximum_samples':6,
            'timeout_scope':'Evidence capture cost only; rendering and model parameters are unchanged.'}
        path=self.out/(stem+'_capture.json')
        def save():
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        save()
        previous=None
        try:
            for index in range(6):
                filename=stem+('_early.png' if index==0 else f'_sample_{index:02d}.png')
                sample={'file':filename,'started_at':time.time(),'view_before':view(),
                        'client_before':self.page.evaluate(CLIENT_READ)}
                report['samples'].append(sample);save()
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise TimeoutError('Paused canvas capture exceeded 420 seconds')
                self.page.screenshot(path=str(self.out/filename),timeout=min(60000,remaining*1000),**kwargs)
                sample.update(finished_at=time.time(),client_after=self.page.evaluate(CLIENT_READ),view_after=view())
                sample['png_sha256']=hashlib.sha256((self.out/filename).read_bytes()).hexdigest()
                before,after=sample['view_before'],sample['view_after']
                current=self.state(sid)
                sample['api_state_unchanged']=current==state
                # Camera may still settle after a resize. Identity/clock stay fixed;
                # each accepted sample and the accepted pair must freeze its camera.
                identity_fixed=(all(before[key]==after[key]==reference[key] for key in VIEW_IDENTITY)
                    and before['elapsed_s']==after['elapsed_s']==reference['elapsed_s']
                    and not before['clock_advancing'] and not after['clock_advancing'])
                response_fixed=all(np.isclose(candidate[key],value,rtol=0,atol=1e-7)
                    for candidate in (before,after) for key,value in response.items())
                sample['client_view_before']=client_view_errors(sample['client_before'],before)
                sample['client_view_after']=client_view_errors(sample['client_after'],after)
                sample['pixels']=settled_canvas_pixels(self.out/filename,
                    sample['client_before'],sample['client_after'],kwargs.get('clip'))
                if sample['pixels'] is None:
                    sample['pixel_comparison_skipped']='Client camera or canvas changed during screenshot; raw image retained.'
                sample['stable_within_shot']=(identity_fixed and response_fixed and sample['api_state_unchanged']
                    and sample['pixels'] is not None and same_view(before,after)
                    and sample['client_view_before']['passed'] and sample['client_view_after']['passed'])
                matched=(previous is not None and previous['stable_within_shot'] and sample['stable_within_shot']
                    and same_view(previous['view_after'],before)
                    and same_client_frame(previous['client_after'],sample['client_before'])
                    and previous['pixels']==sample['pixels']
                    and sample['client_after']['render_counter']>previous['client_before']['render_counter'])
                report['passed']=bool(matched);save()
                if not identity_fixed or not sample['api_state_unchanged']:
                    raise AssertionError('Task identity or clock changed during paused capture')
                if matched:
                    shutil.copyfile(self.out/filename,self.out/name)
                    report['accepted_file']=name;report['accepted_sample']=index;save()
                    return sample
                previous=sample
                self.page.wait_for_timeout(250)
            raise AssertionError('Canvas did not settle to two matching rendered paused frames')
        except Exception as error:
            report['error']={'type':type(error).__name__,'message':str(error)};save()
            raise

    def settled(self,sid,previous,planning=False):
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            state=self.state(sid)
            if self.page.get_by_text('执行错误',exact=True).count():
                text=self.page.locator('body').inner_text()
                self.record('visible_error',text=text)
                (self.out/'failure_dom.yaml').write_text(self.page.locator('body').aria_snapshot())
                self.capture('execution_error.png')
                raise AssertionError(text)
            if state['revision']>previous and state['execution']!='planning':
                events=self.read.request('GET',f'/api/v1/sessions/{sid}/events')
                if planning:
                    job_id=next(e['data']['job_id'] for e in reversed(events) if e['kind']=='turn_started')
                    job=self.read.request('GET',f'/api/v1/jobs/{job_id}')
                    if job['status']!='done' or not job['data'].get('raw_response'):
                        raise AssertionError(json.dumps(job,ensure_ascii=False))
                if state.get('last_error'):
                    raise AssertionError(state['last_error'])
                wait_view(sid,time.time()-1,revision=state['revision'])
                return state
            self.page.wait_for_timeout(200)
        raise TimeoutError(f'GUI action did not finish for session {sid}')

    def message(self,sid,text):
        self.session_id=sid
        previous=self.state(sid)['revision']
        self.page.get_by_role('tab',name='任务',exact=True).click()
        ui_input(self.page,'任务指令').fill(text)
        ui_input(self.page,'任务指令').press('Tab')
        self.record('message',text=text,previous_revision=previous)
        self.record('message_click_started',session_id=sid,previous_revision=previous)
        self.page.get_by_role('button',name='发送任务',exact=True).click()
        self.record('message_click_finished',session_id=sid,previous_revision=previous)
        return self.settled(sid,previous,planning=True)

    def control(self,sid,operation):
        previous=self.state(sid)['revision']
        self.page.get_by_role('tab',name='任务',exact=True).click()
        self.record(operation,previous_revision=previous)
        label={'pause':'暂停动作','resume':'恢复任务','complete':'确认完成'}[operation]
        self.page.get_by_role('button',name=label,exact=True).click()
        return self.settled(sid,previous)


def wait_view(session_id,after,mode=None,revision=None,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        candidates=[]
        for path in (root()/'runs/simulation/viewer').glob('client_*_view.json'):
            data=json.loads(path.read_text())
            if data['session_id']==session_id and data['generated_at']>after:
                if revision is not None and data['revision']<revision:
                    continue
                if mode is None or data['view_mode']==mode:
                    candidates.append(data)
        if candidates:
            return max(candidates,key=lambda item:item['generated_at'])
        time.sleep(.15)
    raise TimeoutError(f'Viser did not publish session {session_id} in view {mode}')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://127.0.0.1:8750')
    parser.add_argument('--viewer',default='http://127.0.0.1:8780')
    parser.add_argument('--browser',type=Path)
    parser.add_argument('--out',type=Path,default=root()/'runs/simulation/browser_live')
    parser.add_argument('--scenes',nargs='+',choices=[entry['scene_id'] for entry in list_scenes()],
                        help='Explicit scene subset for a targeted rerun; omitted means all twelve scenes.')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    entries=list_scenes()
    if args.scenes is not None:
        if len(set(args.scenes))!=len(args.scenes):
            parser.error('--scenes must not contain duplicate scene IDs')
        entries=[entry for entry in entries if entry['scene_id'] in args.scenes]
    temporary=Path(os.environ['TMPDIR']).resolve()
    if not temporary.is_relative_to(root()):
        raise ValueError('TMPDIR must be inside the project')
    headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    options={'headless':True,'args':['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    if args.browser is not None:
        options['executable_path']=str(args.browser)
    results=[]
    with httpx.Client(base_url=args.api,timeout=10,headers=headers) as http:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(**options)
            for entry in entries:
                spec=load_scene(entry['scene_id']);out=args.out/spec.scene_id;out.mkdir(exist_ok=True)
                context=browser.new_context(viewport={'width':1600,'height':1000},record_video_dir=str(out/'video'))
                run=None
                try:
                    page=context.new_page();errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(args.viewer,wait_until='networkidle')
                    software_notice=page.get_by_role('alert').filter(has_text='Software WebGL rendering detected')
                    if software_notice.count():
                        software_notice.get_by_role('button').click()
                    page.get_by_role('tab',name='任务',exact=True).click()
                    run=BrowserRun(page,http,out)
                    deadline=time.monotonic()+30
                    while not ui_input(page,'会话标识').input_value():
                        if page.get_by_text('执行错误',exact=True).count():
                            (out/'initial_failure_dom.yaml').write_text(page.locator('body').aria_snapshot())
                            run.capture('initial_error.png')
                            raise RuntimeError(page.locator('body').inner_text())
                        if time.monotonic()>deadline:
                            raise TimeoutError('initial viewer session did not load')
                        page.wait_for_timeout(200)
                    initial_sid=ui_input(page,'会话标识').input_value()
                    wait_view(initial_sid,time.time()-1,revision=0)
                    run.record('select_scene',scene_id=spec.scene_id,initial_session_id=initial_sid)
                    page.get_by_role('combobox',name='场景',exact=True).click()
                    page.get_by_role('option',name=spec.title,exact=True).click()
                    deadline=time.monotonic()+30
                    while True:
                        sid=ui_input(page,'会话标识').input_value()
                        if sid and run.state(sid)['scene_id']==spec.scene_id:
                            break
                        if time.monotonic()>deadline:
                            (out/'scene_switch_failure_dom.yaml').write_text(page.locator('body').aria_snapshot())
                            run.capture('scene_switch_failure.png')
                            raise TimeoutError('scene dropdown did not create the requested session')
                        page.wait_for_timeout(200)
                    (out/'initial_dom.yaml').write_text(page.locator('body').aria_snapshot())
                    state=run.message(sid,spec.initial_instruction)
                    expected=[(s.target_id,s.action,s.reference_id,s.angle_deg) for s in spec.task_contract.ordered_steps]
                    actual=[signature(t) for t in state['queue'] if t['semantic']['task_role']!='background']
                    if actual!=expected:
                        raise AssertionError(f'{spec.scene_id}: expected {expected}, received {actual}')
                    original_ids=[t['task_id'] for t in state['queue']]
                    paused=run.control(sid,'pause')
                    if paused['execution']!='paused':
                        raise AssertionError('GUI pause did not freeze the task')
                    page.get_by_role('tab',name='观察',exact=True).click()
                    ui_input(page,'跟随当前步骤').uncheck()
                    before=run.view_button('工作区域')
                    wait_view(sid,before,'workspace')
                    overview=run.capture('workspace.png',stable=True)['view_after']
                    before=run.view_button('目标特写')
                    wait_view(sid,before,'detail');run.capture('detail.png',stable=True)
                    # Inspection response must be measured from the contracted surface
                    # normal. Moving cues use the full workspace to include the endpoint.
                    inspection_response=state['queue'][0]['semantic']['action']=='inspect_back'
                    response_mode='inspection' if inspection_response else 'workspace'
                    response_button='结构检查' if inspection_response else '工作区域'
                    before=run.view_button(response_button)
                    response_view=wait_view(sid,before,response_mode)
                    current=next(o for o in spec.objects if o.object_id==state['queue'][0]['semantic']['target_id'])
                    check_point=transform_points(current.pose,np.asarray([current.interaction.inspect_point_local_m]))[0]
                    check_normal=rotation(current.pose).apply(current.interaction.inspect_normal_local)
                    normal_side=float((np.asarray(response_view['position_m'])-check_point)@check_normal)
                    if inspection_response and (normal_side<=0 or response_view['selected_id']!=current.object_id):
                        raise AssertionError('response camera is not on the contracted inspection side')
                    (out/'response_view_contract.json').write_text(json.dumps({
                        'view_mode':response_mode,'action':state['queue'][0]['semantic']['action'],
                        'target_id':current.object_id,'inspection_point_local_m':current.interaction.inspect_point_local_m,
                        'inspection_normal_local':current.interaction.inspect_normal_local,
                        'inspection_cue_clearance_m':current.interaction.inspect_cue_clearance_m,
                        'camera_normal_side_dot_m':normal_side,
                        'visibility_condition':'camera on contracted inspection-normal side; selected target isolated'
                            if inspection_response else 'workspace includes task trajectory and receiver',
                        'view':response_view},ensure_ascii=False,indent=2))
                    page.get_by_role('button',name='聚焦选中对象',exact=True).click()
                    # Adaptive resolution is exercised by the normal views above
                    # and below. Keep it out of paired response pixel measurements.
                    run.set_render_pixel_ratio('1.0')
                    page.get_by_role('tab',name='显示响应',exact=True).click()
                    ui_input(page,'亮度数值').fill('0')
                    ui_input(page,'亮度数值').press('Tab')
                    before=time.time();wait_view(sid,before);page.wait_for_timeout(400)
                    canvas=page.locator('canvas[data-engine]')
                    canvas_box=canvas.bounding_box()
                    if canvas_box is None or canvas_box['width']<100:
                        raise AssertionError('the native three.js canvas is not visible')
                    (out/'canvas_region.json').write_text(json.dumps({'canvas_box':canvas_box,
                        'viewport':page.viewport_size,'canvas_html':canvas.evaluate('(element) => element.outerHTML')},
                        ensure_ascii=False,indent=2))
                    zero_shot=run.capture('brightness_zero.png',stable=True,expected_response={'brightness':0.},clip=canvas_box)
                    ui_input(page,'亮度数值').fill('1')
                    ui_input(page,'亮度数值').press('Tab')
                    before=time.time();wait_view(sid,before);page.wait_for_timeout(400)
                    one_shot=run.capture('brightness_one.png',stable=True,expected_response={'brightness':1.},clip=canvas_box)
                    assert_comparable_captures(zero_shot,one_shot,changed_control='brightness')
                    zero=np.asarray(Image.open(out/'brightness_zero.png').convert('RGB')).astype(int)
                    one=np.asarray(Image.open(out/'brightness_one.png').convert('RGB')).astype(int)
                    changed=int((np.abs(one-zero).max(axis=2)>3).sum())
                    (out/'brightness_comparison.json').write_text(json.dumps({'changed_pixels':changed,
                        'metric_scope':'Whole-canvas changed pixels; not a locality or spatial-support measurement.',
                        'canvas_box':canvas_box,'view':one_shot['view_after'],
                        'zero_shot':zero_shot,'one_shot':one_shot},ensure_ascii=False,indent=2))
                    if changed<20:
                        raise AssertionError(f'{spec.scene_id}: brightness changed fewer than 20 canvas pixels')
                    focus=one_shot['view_after']['focus_m']
                    ui_input(page,'焦点数值 米').fill(str(round(focus+.35,4)))
                    ui_input(page,'焦点数值 米').press('Tab')
                    before=time.time();wait_view(sid,before);page.wait_for_timeout(400)
                    defocused_shot=run.capture('defocused.png',stable=True,expected_response={'brightness':1.},clip=canvas_box)
                    assert_comparable_captures(one_shot,defocused_shot,changed_control='focus_m')
                    unfocused=np.asarray(Image.open(out/'defocused.png').convert('RGB')).astype(int)
                    focus_changed=int((np.abs(one-unfocused).max(axis=2)>3).sum())
                    (out/'focus_comparison.json').write_text(json.dumps({'changed_pixels':focus_changed,
                        'metric_scope':'Whole-canvas changed pixels; not a locality or spatial-support measurement.',
                        'canvas_box':canvas_box,'view':defocused_shot['view_after'],
                        'focused_shot':one_shot,'defocused_shot':defocused_shot},ensure_ascii=False,indent=2))
                    if focus_changed<20:
                        raise AssertionError(f'{spec.scene_id}: focus changed fewer than 20 canvas pixels')
                    run.set_render_pixel_ratio('Adaptive')
                    page.get_by_role('tab',name='观察',exact=True).click()
                    ui_input(page,'跟随当前步骤').check()
                    before=time.time();interrupted=run.message(sid,spec.task_contract.interrupt_instruction)
                    if not interrupted['suspended'] or [t['task_id'] for t in interrupted['suspended'][-1]]!=original_ids:
                        raise AssertionError('GUI interruption did not retain original task identities')
                    temporary=[t for t in interrupted['queue'] if t['semantic']['task_role']!='background']
                    if len(temporary)!=1 or signature(temporary[0])!=(spec.task_contract.interrupt_target,'inspect_back',None,None):
                        (out/'invalid_interruption.json').write_text(json.dumps(interrupted,ensure_ascii=False,indent=2))
                        raise AssertionError('temporary inspection duplicated or changed the requested task')
                    inspection=wait_view(sid,before,'inspection');run.control(sid,'pause')
                    run.record('instruction_selected_inspection',revision=interrupted['revision'],
                               target_id=spec.task_contract.interrupt_target,view=inspection)
                    page.get_by_role('tab',name='观察',exact=True).click()
                    inspection=run.capture('inspection.png',stable=True)['view_after']
                    run.record('viewport_resize_started',previous=page.viewport_size,requested={'width':1100,'height':800})
                    page.set_viewport_size({'width':1100,'height':800})
                    run.record('viewport_resize_finished',actual=page.viewport_size)
                    before=time.time();wait_view(sid,before,'inspection');page.wait_for_timeout(400)
                    run.capture('inspection_narrow.png',stable=True)
                    run.control(sid,'complete')
                    resumed=run.control(sid,'resume')
                    if [t['task_id'] for t in resumed['queue']]!=original_ids:
                        raise AssertionError('GUI resume changed original task identities')
                    if [signature(t) for t in resumed['queue'] if t['semantic']['task_role']!='background']!=actual:
                        raise AssertionError('GUI resume changed original task parameters')
                    run.control(sid,'pause')
                    run.capture('resumed_narrow.png',stable=True)
                    final=run.state(sid)
                    for step in expected:
                        if signature(final['queue'][0])!=step:
                            raise AssertionError('GUI completion changed task order')
                        final=run.control(sid,'complete')
                    if final['queue'] or final['execution']!='idle':
                        raise AssertionError('GUI workflow did not finish')
                    (out/'final.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
                    if errors:
                        raise AssertionError(json.dumps(errors,ensure_ascii=False))
                    result={'status':'passed','scene_id':spec.scene_id,'session_id':sid,'backend_mode':'live',
                            'brightness_changed_pixels':changed,'focus_changed_pixels':focus_changed,
                            'overview':overview,'inspection':inspection,'browser_errors':errors}
                    (out/'visual.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
                except Exception as error:
                    result={'status':'failed','scene_id':spec.scene_id,
                            'error':str(error),'traceback':traceback.format_exc()}
                    (out/'failure.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
                    print(spec.scene_id,'FAILED',str(error),flush=True)
                    try:
                        (out/'failure_dom.yaml').write_text(page.locator('body').aria_snapshot(timeout=5000))
                        if run is not None:run.capture('failure.png')
                    except Exception as capture_error:
                        result['failure_capture_error']=str(capture_error)
                finally:
                    context.close()
                results.append(result)
                (args.out/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
            browser.close()
    if len(results)!=len(entries) or any(r['status']!='passed' for r in results):
        raise AssertionError(f"scene audit incomplete or failed: {sum(r['status']=='passed' for r in results)}/{len(entries)} passed")


if __name__=='__main__':
    main()
