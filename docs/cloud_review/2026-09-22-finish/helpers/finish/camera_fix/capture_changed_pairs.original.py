"""Scoped native pairs using unchanged production Audit capture and real UI."""
import argparse
import json
import os
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
from holocue.config import load_scene
from scripts.tests.audit_bridge_live import Audit,check_environment,save
from scripts.tests.audit_viewer_live import ui_input,CLIENT_READ

parser=argparse.ArgumentParser();parser.add_argument('--scene',required=True,choices=['engine_bay','shelf_picking','dig_site']);args=parser.parse_args()
args.api='http://127.0.0.1:8750';args.viewer='http://127.0.0.1:8780'
out=Path(os.environ['RUN_DIR'])/'changed_pairs'/args.scene;environment,blender=check_environment(out);out.mkdir(parents=True,exist_ok=False)
save(out/'environment.json',environment)
headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
with httpx.Client(base_url=args.api,headers=headers,timeout=30) as http,sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    context=browser.new_context(viewport={'width':1600,'height':1000},record_video_dir=str(out/'video'))
    page=context.new_page();audit=Audit(page,http,load_scene(args.scene),out,args,blender)
    try:
        audit.open();audit.start_exporter()
        audit.tab('显示响应');ui_input(page,'显示任务提示').uncheck()
        if args.scene=='engine_bay':
            audit.capture('empty_PLUGPORT_guidance_off','detail','PLUGPORT')
        elif args.scene=='shelf_picking':
            audit.capture('BASKET_empty_guidance_off','detail','BASKET')
            audit.capture('BLUE_inspection_guidance_off','inspection','BLUE')
        else:
            audit.select_view('detail','FLAG');before=audit.view();client=page.evaluate(CLIENT_READ);box=client['canvas']['box']
            x=box['x']+box['width']*.5;y=box['y']+box['height']*.5
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+180,y+100,steps=20);page.mouse.up();page.wait_for_timeout(2000)
            save(out/'side_view_control.json',{'method':'Visible canvas orbit drag from existing FLAG detail view','start':[x,y],'end':[x+180,y+100],'before':before,'after':audit.view()})
            audit.capture('FLAG_contact_side_guidance_off')
        if args.scene!='dig_site':
            audit.tab('显示响应');ui_input(page,'显示任务提示').check()
            data=audit.send(audit.spec.initial_instruction)
            while data['state']['queue']:
                task=data['state']['queue'][0];semantic=task['semantic']
                if args.scene=='shelf_picking' and semantic['target_id']=='RED' and semantic.get('reference_id')=='BASKET':
                    obj=next(o for o in audit.spec.objects if o.object_id=='RED')
                    audit.wait_elapsed(task['task_id'],obj.interaction.duration_s)
                    audit.control('暂停动作','paused');audit.capture('BASKET_endpoint_waiting_confirmation','detail','BASKET')
                data=audit.control('确认完成')
            audit.tab('显示响应');ui_input(page,'显示任务提示').uncheck()
            if args.scene=='engine_bay':audit.capture('CLAMP_completed_guidance_off','detail','CLAMP')
            else:audit.capture('BASKET_confirmed_guidance_off','detail','BASKET')
        save(out/'events.json',audit.read(f'/api/v1/sessions/{audit.sid}/events'))
        save(out/'report.json',{'scene_id':args.scene,'session_id':audit.sid,'passed':True,'stages':audit.stages,'browser_errors':audit.errors})
    except Exception as error:
        save(out/'failure.json',{'error':str(error),'type':type(error).__name__,'stages':audit.stages,'session_id':audit.sid})
        raise
    finally:
        if audit.exporter is not None:audit.exporter.close()
        context.close();browser.close()
