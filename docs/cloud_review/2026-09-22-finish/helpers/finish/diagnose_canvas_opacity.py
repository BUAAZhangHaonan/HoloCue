"""Observe actual browser canvas opacity without changing rendering state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
from playwright.sync_api import sync_playwright
from holocue.config import load_scene, root
from scripts.tests.audit_bridge_live import Audit, check_environment, save

READ = """() => [...document.querySelectorAll('canvas')].map(c=>({
 width:c.width,height:c.height,style:c.style.cssText,opacity:getComputedStyle(c).opacity,
 ancestors:[c.parentElement,c.parentElement?.parentElement].filter(Boolean).map(p=>({
 tag:p.tagName,opacity:getComputedStyle(p).opacity,background:getComputedStyle(p).backgroundColor}))}))"""
INIT = """window.__opacityObservations=[];let previous='';setInterval(()=>{
 const value=[...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,
 style:c.style.cssText,opacity:getComputedStyle(c).opacity}));const serialized=JSON.stringify(value);
 if(serialized!==previous){window.__opacityObservations.push({ms:performance.now(),canvases:value});previous=serialized;}
},50);"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--expected-opacity',type=float)
    args=parser.parse_args()
    output=args.out.resolve(); output.mkdir(parents=True,exist_ok=False)
    environment,blender=check_environment(output)
    save(output/'environment.json',environment)
    headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    with httpx.Client(base_url='http://127.0.0.1:8750',headers=headers,timeout=10) as client,sync_playwright() as pw:
        response=httpx.get('http://127.0.0.1:8780/',timeout=30)
        response.raise_for_status()
        (output/'served_index.html').write_bytes(response.content)
        browser=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        try:
            context=browser.new_context(viewport={'width':1600,'height':1000})
            context.add_init_script(INIT)
            page=context.new_page()
            audit=Audit(page,client,load_scene('connector'),output,SimpleNamespace(viewer='http://127.0.0.1:8780/',api='http://127.0.0.1:8750'),blender)
            audit.open(); audit.select_view('workspace')
            page.wait_for_timeout(5000)
            save(output/'snapshot.json',audit.snapshot())
            save(output/'view_state.json',audit.view())
            page.screenshot(path=str(output/'actual_page.png'),full_page=True)
            canvases=page.evaluate(READ)
            result={'canvases':canvases,'opacity_timeline':page.evaluate('window.__opacityObservations'),
                    'browser_errors':audit.errors,'served_index_sha256':hashlib.sha256(response.content).hexdigest(),
                    'scene_id':'connector','session_id':audit.sid,'passive_observation':True}
            save(output/'diagnostic.json',result)
            print(json.dumps(result),flush=True)
            if args.expected_opacity is not None:
                assert canvases and all(float(c['opacity'])==args.expected_opacity for c in canvases)
            assert not audit.errors
        finally:
            browser.close()

if __name__=='__main__':
    main()
