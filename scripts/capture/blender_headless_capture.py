"""Headless same-session evidence: run inside Blender alongside blender_live_bridge.py.
Blender 3.1 background mode exits instead of pumping timers, so this script drives the
bridge tick from a blocking loop and renders timestamped frames while the session evolves.

Usage (CPU, through scripts/guard/resource_guard.py):
  HOLOCUE_SESSION_ID=<sid> blender -b scenes/control_panel/blend/control_panel.blend \
    --python scripts/blender_live_bridge.py --python scripts/blender_headless_capture.py
"""
import bpy,os,time,json
from pathlib import Path
OUT=Path(os.environ.get('HOLOCUE_FRAME_DIR','runs/bridge_frames'))
SCENE=os.environ.get('HOLOCUE_SCENE_ID',bpy.context.scene.get('holocue_scene_id','scene'))
INTERVAL=float(os.environ.get('HOLOCUE_FRAME_INTERVAL','3'))
MAXFRAMES=int(os.environ.get('HOLOCUE_FRAME_MAX','14'))
OUT.mkdir(parents=True,exist_ok=True)
tick=bpy.app.driver_namespace['holocue_bridge_tick']
meta=[]
for i in range(1,MAXFRAMES+1):
    # Fresh pump window per frame: a Cycles render can outlast the interval, so deadlines
    # are measured from now — the bridge never starves and cue switches land in-window.
    deadline=time.monotonic()+INTERVAL
    while time.monotonic()<deadline:
        tick()
        time.sleep(.1)
    stamp=time.time()
    path=OUT/f'{SCENE}_f{i:03d}_t{stamp:.2f}.png'
    bpy.context.scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    tick()
    meta.append({'frame':i,'unix_time':stamp,'path':str(path),
                 'bridge_error':bpy.context.scene.get('holocue_bridge_error','')})
    (OUT/'sequence_meta.json').write_text(json.dumps(meta,indent=1))
bpy.app.driver_namespace['holocue_bridge_stop'].set()
print('frame capture ->',OUT)
