"""Execute from Blender's Scripting editor after loading a generated scene.
Set HOLOCUE_SESSION_ID and optionally HOLOCUE_API_URL / HOLOCUE_API_KEY before launching Blender.
Network thread never touches bpy. A bounded queue delivers packets to the main-thread timer.
"""
import bpy,os,time,json,threading,queue,urllib.request,math
from mathutils import Vector,Quaternion
SESSION=os.environ.get('HOLOCUE_SESSION_ID','')
BASE=os.environ.get('HOLOCUE_API_URL','http://127.0.0.1:8750').rstrip('/')
KEY=os.environ.get('HOLOCUE_API_KEY','')
if not SESSION:raise RuntimeError('Set HOLOCUE_SESSION_ID before starting the Blender bridge')
if bpy.app.driver_namespace.get('holocue_bridge_stop'):
    bpy.app.driver_namespace['holocue_bridge_stop'].set()
stop=threading.Event();bpy.app.driver_namespace['holocue_bridge_stop']=stop
packets=queue.Queue(maxsize=1)

def publish(x):
    try:packets.get_nowait()
    except queue.Empty:pass
    packets.put_nowait(x)

def poll():
    while not stop.wait(.2):
        try:
            headers={'Authorization':'Bearer '+KEY} if KEY else {}
            req=urllib.request.Request(BASE+'/api/v1/sessions/'+SESSION+'/display',headers=headers)
            with urllib.request.urlopen(req,timeout=2) as r:p=json.load(r)
            publish({'packet':p})
        except Exception as e:publish({'error':str(e)})
threading.Thread(target=poll,daemon=True).start()
state={'packet':None,'key':None,'phase':0.,'last':time.monotonic(),'handles':[],'last_received':0.}

def clear():
    for o in list(bpy.data.objects):
        if o.name.startswith('HC_CUE_'):bpy.data.objects.remove(o,do_unlink=True)
    state['handles']=[]

def create_cues(p):
    clear()
    for c in p['cues']:
        if c['n_gaussians']==0:continue
        parent=bpy.data.objects.get('HC_'+c['target_id'])
        if parent is None:raise RuntimeError('Scene missing target '+c['target_id'])
        pos=Vector(c['pose']['position_m'])
        if c['cue_type']=='ghost_motion':
            for child in parent.children_recursive:
                if child.type=='MESH':
                    cp=child.copy();cp.data=child.data.copy();cp.name='HC_CUE_'+c['task_id']+'_'+child.name
                    bpy.context.scene.collection.objects.link(cp);cp.parent=None;cp.matrix_world=child.matrix_world.copy()
                    cp.display_type='WIRE';cp.show_in_front=True
                    if c['task_role']=='current':state['handles'].append((cp,c,cp.matrix_world.copy(),Vector(c['pose']['position_m'])))
        else:
            bpy.ops.mesh.primitive_torus_add(major_radius=.052,minor_radius=.0018,location=pos+Vector((0,0,.084)),major_segments=48,minor_segments=8)
            ring=bpy.context.object;ring.name='HC_CUE_'+c['task_id'];ring.show_in_front=True
        bpy.ops.object.text_add(location=pos+Vector((-.042,0,.12)))
        text=bpy.context.object;text.name='HC_CUE_TEXT_'+c['task_id'];text.data.size=.014
        # ASCII identifiers avoid dependence on third-party font files inside Blender.
        text.data.body=f"{c['target_id']}  {c['task_role']}  N {c['n_gaussians']}  sigma {c['sigma_value']}"

def tick():
    if stop.is_set():return None
    now=time.monotonic();dt=min(now-state['last'],.1);state['last']=now
    try:
        item=packets.get_nowait()
        if 'error' in item:
            bpy.context.scene['holocue_bridge_error']=item['error']
            if state['packet']:state['packet']['execution']='paused'
        else:
            p=item['packet']
            if p['scene_id']!=bpy.context.scene.get('holocue_scene_id'):raise RuntimeError('session/Blender scene mismatch')
            state['last_received']=now
            key=(p['revision'],p['epoch'])
            if key!=state['key']:
                if state['packet'] is None or [c['task_id'] for c in p['cues']] != [c['task_id'] for c in state['packet']['cues']]:state['phase']=0.
                create_cues(p);state['key']=key
            state['packet']=p;bpy.context.scene['holocue_bridge_error']=''
    except queue.Empty:pass
    except Exception as e:
        bpy.context.scene['holocue_bridge_error']=str(e)
        if state['packet']:state['packet']['execution']='paused'
    if state['packet'] and now-state['last_received']>2:
        state['packet']['execution']='paused'
    if state['packet'] and state['packet']['execution']=='running':state['phase']+=dt
    f=(1-math.cos(2*math.pi*state['phase']/4))/2
    for obj,c,base,origin in state['handles']:
        obj.matrix_world=base.copy()
        if c['action'] in ('insert','assemble') and c.get('goal_pose'):
            delta=Vector(c['goal_pose']['position_m'])-origin;obj.location+=delta*f
        elif c['action'] in ('inspect_back','rotate'):
            angle=math.radians(c['angle_deg'] if c.get('angle_deg') is not None else 180)*f
            rotation=Quaternion((0,0,1),angle).to_matrix().to_4x4()
            from mathutils import Matrix
            obj.matrix_world=Matrix.Translation(origin)@rotation@Matrix.Translation(-origin)@base
    return 1/30
bpy.app.timers.register(tick,first_interval=.1)
print('HoloCue bridge connected to session',SESSION)
