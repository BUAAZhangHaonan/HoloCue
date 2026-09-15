"""Headless same-session evidence: run inside Blender alongside blender_live_bridge.py.
Loads nothing itself; renders timestamped frames while the bridge follows the live API.

Usage (Blender 3.1.2, CPU):
  HOLOCUE_SESSION_ID=<sid> blender -b assets/blender/control_panel.blend \
    --python scripts/blender_live_bridge.py --python scripts/blender_headless_capture.py
"""
import bpy,os,time,json
from pathlib import Path
OUT=Path(os.environ.get('HOLOCUE_FRAME_DIR','runs/bridge_frames'))
SCENE=os.environ.get('HOLOCUE_SCENE_ID',bpy.context.scene.get('holocue_scene_id','scene'))
INTERVAL=float(os.environ.get('HOLOCUE_FRAME_INTERVAL','2'))
MAXFRAMES=int(os.environ.get('HOLOCUE_FRAME_MAX','12'))
OUT.mkdir(parents=True,exist_ok=True)
state={'n':0,'t0':time.monotonic(),'meta':[]}

def frame():
    if state['n']>=MAXFRAMES:return None
    if time.monotonic()-state['t0']<INTERVAL*(state['n']+1):return .5
    state['n']+=1
    stamp=time.time()
    path=OUT/f'{SCENE}_f{state["n"]:03d}_t{stamp:.2f}.png'
    bpy.context.scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    err=bpy.context.scene.get('holocue_bridge_error','')
    state['meta'].append({'frame':state['n'],'unix_time':stamp,'path':str(path),'bridge_error':err})
    (OUT/'sequence_meta.json').write_text(json.dumps(state['meta'],indent=1))
    return .5
bpy.app.timers.register(frame,first_interval=INTERVAL)
print('frame capture ->',OUT)
