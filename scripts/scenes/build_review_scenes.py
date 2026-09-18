import bpy, math, json, sys, os
from pathlib import Path
from mathutils import Vector

ROOT = Path("/home/hdd3/zhanghaonan/projects/holocue")
OUT = ROOT / "runs" / "review_scenes"
MESH = ROOT / "assets" / "meshes" / "review"
SCENE = ROOT / "configs" / "scenes"

def mat(name, color, metallic=0.0, rough=.45, emission=None):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(*color,1)
    bs.inputs["Metallic"].default_value=metallic
    bs.inputs["Roughness"].default_value=rough
    if emission:
        bs.inputs["Emission"].default_value=(*emission,1)
        bs.inputs["Emission Strength"].default_value=3
    return m

STEEL=mat("painted steel",(0.16,.19,.22),.72,.25)
STEEL2=mat("brushed steel",(.38,.42,.45),.82,.21)
DARK=mat("rubber black",(.025,.032,.038),.05,.62)
YELLOW=mat("safety yellow",(.86,.46,.025),.1,.3)
RED=mat("alarm red",(.72,.025,.018),.15,.3, (.8,.015,.01))
BLUE=mat("medical blue",(.03,.22,.48),.05,.28)
WHITE=mat("ivory",(.86,.88,.86),0,.38)
GREEN=mat("status green",(.03,.65,.18),.05,.3,(.02,.5,.1))
GLASS=mat("clear glass",(.1,.35,.43),.05,.08)
WOOD=mat("wood",(.25,.11,.045),0,.6)
WALL=mat("wall",(.48,.51,.50),0,.82)
FLOOR=mat("floor",(.12,.14,.15),.05,.75)
ORANGE=mat("cue orange",(.95,.25,.015),.1,.3,(.8,.12,.01))

def clear():
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes,bpy.data.curves,bpy.data.cameras,bpy.data.lights):
        for x in list(col):
            if x.users==0: col.remove(x)

def cube(n, loc, scale, material, bevel=.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod=o.modifiers.new("soft_edges","BEVEL"); mod.width=bevel; mod.segments=3
    o.data.materials.append(material); return o

def cyl(n, loc, radius, depth, material, rot=(0,0,0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    o=bpy.context.object;o.name=n;o.data.materials.append(material);return o

def torus(n, loc, major, minor, material, rot=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=64, minor_segments=16, location=loc, rotation=rot)
    o=bpy.context.object;o.name=n;o.data.materials.append(material);return o

def uv(n, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc);o=bpy.context.object;o.name=n;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);return o

def pipe(n, a, b, radius, material):
    a,b=Vector(a),Vector(b); d=b-a
    o=cyl(n,(a+b)/2,radius,d.length,material)
    o.rotation_mode="QUATERNION";o.rotation_quaternion=d.to_track_quat("Z","Y");return o

def text(n, body, loc, size=.055, material=WHITE, rot=(math.pi/2,0,0)):
    cu=bpy.data.curves.new(n,"FONT");cu.body=body;cu.align_x="CENTER";cu.size=size;cu.extrude=.003
    o=bpy.data.objects.new(n,cu);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=rot;o.data.materials.append(material);return o

def label(obj_id, loc, color=ORANGE):
    return text("LABEL_"+obj_id,obj_id,loc,.055,color)

def wallkit(extent=(4,3,2.8)):
    w,d,h=extent
    cube("floor",(0,0,-.06),(w/2,d/2,.06),FLOOR,.01)
    cube("back_wall",(0,d/2,h/2),(w/2,.05,h/2),WALL,.01)
    cube("left_wall",(-w/2,0,h/2),(.05,d/2,h/2),WALL,.01)

def dial(n,loc,radius,material,angle=0,face="Y"):
    rot=(math.pi/2,0,0) if face=="Y" else (0,math.pi/2,0)
    cyl(n,loc,radius,.035,material,rot)
    axis=Vector((0,-1,0)) if face=="Y" else Vector((1,0,0))
    end=Vector(loc)+axis*(radius*.72)
    pipe(n+"_pointer",loc,end,.008,RED)
    return bpy.context.object

def setup(scene_id, title, camera, look, scale):
    sc=bpy.context.scene;sc.unit_settings.system="METRIC";sc.render.engine="CYCLES"
    sc.cycles.device="CPU";sc.cycles.samples=24;sc.cycles.use_denoising=True
    sc.render.resolution_x=1600;sc.render.resolution_y=1050;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format="PNG";sc.render.film_transparent=False
    sc.view_settings.view_transform="Filmic";sc.view_settings.look="Medium High Contrast"
    sc.world=bpy.data.worlds.get("World") or bpy.data.worlds.new("World");sc.world.use_nodes=True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value=(.025,.035,.05,1)
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value=.35
    bpy.ops.object.camera_add(location=camera);cam=bpy.context.object;cam.data.type="PERSP";cam.data.lens=48
    cam.rotation_euler=(Vector(look)-cam.location).to_track_quat("-Z","Y").to_euler();sc.camera=cam
    for loc,energy,size,col in [((camera[0]-1,camera[1]-1,camera[2]+2),1300,4,(1,.86,.72)),((camera[0]+2,camera[1]+1,camera[2]+1),1000,3,(.62,.76,1)),((0,1,2.7),900,2,(1,1,1))]:
        bpy.ops.object.light_add(type="AREA",location=loc);l=bpy.context.object;l.data.energy=energy;l.data.shape="DISK";l.data.size=size;l.data.color=col;l.rotation_euler=(Vector(look)-l.location).to_track_quat("-Z","Y").to_euler()
    sc.render.filepath=str(OUT/f"{scene_id}.png");sc["holocue_scene_id"]=scene_id;sc["title"]=title

def cnc():
    sid="cnc_toolchange"; clear(); wallkit((4.8,3.8,3.0))
    # machine enclosure, doors, windows and work envelope
    cube("machine_base",(0,.92,.42),(1.8,.78,.42),STEEL,.08);cube("machine_left",(-1.5,.92,1.65),(.3,.78,1.25),STEEL,.06);cube("machine_right",(1.5,.92,1.65),(.3,.78,1.25),STEEL,.06)
    cube("machine_top",(0,.92,2.78),(1.8,.78,.18),STEEL,.04)
    cube("door_frame",(-.25,.08,1.65),(1.08,.08,1.18),STEEL2,.025);cube("door_glass",(-.25,.0,1.67),(.92,.025,.98),GLASS,.01)
    # table and vice
    cube("machine_table",(0,.72,.9),(1.15,.62,.10),STEEL2,.025);cube("fixture",(0,.35,1.05),(.42,.22,.14),DARK,.025)
    cube("vise_body",(.0,.08,1.26),(.34,.23,.16),STEEL2,.035);cube("vise_jaw_l",(-.22,.08,1.43),(.06,.24,.12),STEEL2,.015);cube("vise_jaw_r",(.22,.08,1.43),(.06,.24,.12),STEEL2,.015)
    # spindle and rotary tool magazine
    cyl("spindle",(0,-.02,2.35),.22,.35,STEEL2,(math.pi/2,0,0));cyl("spindle_nose",(0,-.22,2.35),.13,.16,DARK,(math.pi/2,0,0))
    torus("magazine",(1.18,.12,1.78),.62,.12,STEEL2,(math.pi/2,0,0))
    for i in range(12):
        a=2*math.pi*i/12;x=1.18+.62*math.cos(a);z=1.78+.62*math.sin(a)
        cyl(f"pocket_{i+1}",(x,.04,z),.10,.20,DARK,(math.pi/2,0,0));text(f"slot_{i+1}",str(i+1),(x,-.08,z),.04,WHITE,(math.pi/2,0,0))
    # panel at far right
    cube("panel_body",(1.83,-.02,2.05),(.34,.13,.62),DARK,.04);cube("screen",(1.83,-.16,2.28),(.22,.015,.18),BLUE,.01)
    for z in [1.80,1.95,2.10]:
        cyl("pilot",(1.83,-.17,z),.035,.02,GREEN if z==1.8 else RED,(math.pi/2,0,0))
    dial("MODE_SWITCH",(1.83,-.19,1.62),.14,STEEL2,0);text("mode_text","AUTO  MAN  EDIT",(1.83,-.205,1.38),.035,WHITE,(math.pi/2,0,0))
    # tool cart and tools
    cube("cart_body",(.25,-.38,.58),(.58,.4,.5),STEEL2,.04);cube("cart_top",(.25,-.38,1.12),(.65,.45,.06),STEEL2,.025)
    for x in [-.18,.68]:
        cyl("wheel",(x,-.60,.1),.11,.06,DARK,(math.pi/2,0,0))
    # BT40 tool T03 horizontal
    cyl("T03",(0.25,-.40,1.34),.115,.72,STEEL2,(0,math.pi/2,0));cyl("T03_pullstud",(-.15,-.40,1.34),.07,.12,YELLOW,(0,math.pi/2,0));torus("T03_flange",(.48,-.40,1.34),.15,.025,STEEL2,(0,math.pi/2,0))
    # T09 at tray / target pocket
    cyl("T09",(1.10,.10,1.35),.11,.58,STEEL2,(0,math.pi/2,0));cyl("T09_pullstud",(.80,.10,1.35),.07,.1,YELLOW,(0,math.pi/2,0))
    label("MODESWITCH",(1.83,-.25,1.50));label("POCKET9",(1.18,-.16,2.55));label("T03",(.25,-.48,1.53));label("T09",(1.1,-.02,1.62));label("PANEL",(1.83,-.27,2.68))
    setup(sid,"立式加工中心手动装刀与拉钉点检",(4.2,-5.2,3.2),(.25,.4,1.35),4.8)
    return {"scene_id":sid,"title":"立式加工中心手动装刀与拉钉点检","camera_position_m":[4.2,-5.2,3.2],"camera_look_at_m":[.25,.4,1.35],
    "initial_instruction":"先把模式旋钮 MODESWITCH 顺时针拧 90 度切到手动档,把镗刀 T09 插进刀库当前的 9 号刀套 POCKET9,再拿起刀具车上的 T03,翻看柄尾的拉钉有没有松动,控制面板 PANEL 全程盯着报警灯。",
    "objects":[("MODESWITCH","模式选择旋钮",["point","rotate"]),("T09","9号镗刀柄",["point","insert"]),("POCKET9","9号刀套",["point"]),("T03","3号镗刀柄",["point","inspect_back"]),("MAG","刀库盘",["point"]),("PANEL","控制面板",["point","wait"])]}

def bottle(n,x,y,z,number):
    cyl(n,(x,y,z+.48),.16,.92,YELLOW);uv(n+"_shoulder",(x,y,z+1.0),(.16,.16,.20),YELLOW);cyl(n+"_neck",(x,y,z+1.18),.07,.20,STEEL2);cyl(n+"_valve",(x,y,z+1.30),.09,.13,STEEL2,(math.pi/2,0,0));torus(n+"_ring",(x,y,z+.98),.165,.012,STEEL2);text(n+"_stamp",f"TEST {number} 2027",(x-.18,y-.17,z+.97),.028,WHITE,(math.pi/2,0,0))

def dive():
    sid="dive_fillstation";clear();wallkit((4.8,3.8,3.0))
    # fill rack, manifold, compressor
    cube("rack",(0,1.10,1.80),(1.95,.12,1.05),STEEL2,.03);cube("manifold",(0,.92,2.25),(1.7,.12,.16),STEEL,.025)
    for i in range(6):
        x=-1.35+i*.54; pipe("line",(x,.9,2.15),(x,.7,1.65),.025,STEEL2);cyl("stem",(x,.63,1.65),.045,.26,STEEL2);cube("handle",(x,.48,1.78),(.12,.035,.035),RED,.01)
    bottle("BOTTLE1",-1.0,-.15,0,1);bottle("BOTTLE2",-.35,-.05,0,2);bottle("BOTTLE3",.32,-.02,0,3)
    # QRC / hose from manifold to bottle valve
    pipe("hose",(.32,.88,1.72),(.32,.22,1.36),.035,DARK);cyl("QRC",(.32,.17,1.36),.08,.18,STEEL2,(math.pi/2,0,0))
    # gauge board
    cube("gauge_panel",(.25,1.78,2.20),(1.15,.08,.62),STEEL,.03)
    for i,x in enumerate([-.55,-.05,.45]):
        dial("GAUGE", (x,1.66,2.30),.24,WHITE,0);cyl("gauge_redzone",(x,1.61,2.30),.25,.02,RED,(math.pi/2,0,0),64)
        text("psi","PSI",(x,1.55,2.10),.032,DARK,(math.pi/2,0,0))
    cube("compressor",(1.55,1.2,.65),(.5,.5,.65),STEEL,.05);cyl("tank",(1.55,1.0,1.15),.42,.95,STEEL2,(math.pi/2,0,0));pipe("airline",(1.55,1.4,1.2),(0,1.0,1.7),.035,DARK)
    label("QRC",(.32,.02,1.55));label("VALVE",(.32,-.14,1.62));label("BOTTLE3",(.32,-.24,1.88));label("STEM",(.32,.40,2.02));label("GAUGES",(.25,1.48,2.92))
    setup(sid,"潜水气瓶充装前核验与接通",(.3,-4.9,2.85),(.1,.75,1.35),4.8)
    return {"scene_id":sid,"title":"潜水气瓶充装前核验与接通","camera_position_m":[.3,-4.9,2.85],"camera_look_at_m":[.1,.75,1.35],
    "initial_instruction":"把充装软管接头 QRC 接到 3 号气瓶瓶阀 VALVE 的出口上,接好后核对 BOTTLE3 瓶肩的检验钢印在不在有效期内,确认无误再把汇流排 3 号路阀杆 STEM 逆时针开 90 度,压力表组 GAUGES 全程盯着别超压。",
    "objects":[("QRC","充装软管接头",["point","insert"]),("VALVE","3号瓶阀",["point"]),("BOTTLE3","3号气瓶",["point","inspect_back"]),("BOTTLE1","1号气瓶",["point","inspect_back"]),("BOTTLE2","2号气瓶",["point","inspect_back"]),("STEM","3号路阀杆",["point","rotate"]),("GAUGES","压力表组",["point","wait"])]}

def bag(n,x,y,z,labeltxt):
    cube(n,(x,y,z),(.18,.06,.34),GLASS,.04);cube(n+"_fluid",(x,y-.01,z-.02),(.15,.035,.27),BLUE if "5%" in labeltxt else WHITE,.025);text(n+"_label",labeltxt,(x,y-.075,z),.035,WHITE,(math.pi/2,0,0))

def infusion():
    sid="infusion_ward";clear();wallkit((4.8,3.8,3.0))
    # bed and headboard
    cube("bed",(0,1.18,.62),(1.45,.75,.12),WHITE,.04);cube("mattress",(0,1.18,.78),(1.38,.70,.16),BLUE,.07);cube("headboard",(1.28,1.18,1.35),(.10,.75,.72),STEEL2,.03)
    for x in [-1.18,1.18]:
        cyl("bed_leg",(x,1.18,.35),.045,.5,STEEL2);cyl("caster",(x,1.18,.08),.08,.05,DARK,(math.pi/2,0,0))
    # IV stand and bags
    cyl("iv_stand",(-.25,.20,1.45),.025,2.8,STEEL2);cyl("base",(-.25,.20,.08),.42,.06,STEEL2)
    for x in [-.45,-.05]:
        pipe("hook",(x,.2,2.72),(x-.1,.2,2.88),.018,STEEL2);bag("BAG1" if x<0 else "BAG2",x,.20,2.28,"5% DEXTROSE" if x<0 else "10% SALINE")
    # pump and slot
    cube("pump",(.15,.22,1.42),(.32,.16,.48),WHITE,.04);cube("screen",(.15,.05,1.62),(.21,.015,.10),BLUE,.01);cube("SLOT2",(.15,.045,1.28),(.22,.02,.12),DARK,.02)
    for z in [1.46,1.34]: cyl("pump_button",(.42,.04,z),.035,.02,GREEN,(math.pi/2,0,0))
    # tube and stopcock
    pipe("tube",(.12,.05,1.12),(.12,.05,.55),.012,GLASS);cyl("STOPCOCK",(.12,.05,.92),.10,.10,BLUE,(math.pi/2,0,0));cube("stopcock_handle",(.12,-.04,.92),(.18,.025,.025),RED,.01)
    # trolley
    cube("trolley",(-.85,-.15,.62),(.48,.38,.55),STEEL2,.035);cube("trolley_top",(-.85,-.15,1.22),(.52,.42,.06),WHITE,.02);cyl("trolley_wheel",(-1.2,-.43,.12),.09,.06,DARK,(math.pi/2,0,0));cyl("trolley_wheel2",(-.5,-.43,.12),.09,.06,DARK,(math.pi/2,0,0))
    # monitor with bezel, waveforms and alarm
    cube("MONITOR",(1.12,1.65,1.80),(.48,.10,.55),DARK,.04);cube("monitor_screen",(1.12,1.52,1.86),(.39,.015,.37),BLUE,.02)
    for i in range(3): pipe("wave",(0.82+i*.18,1.49,1.82),(0.88+i*.18,1.49,1.90 if i%2 else 1.75),.008,GREEN)
    cyl("alarm",(1.12,1.48,2.35),.08,.03,RED,(math.pi/2,0,0))
    label("PUMPCASSETTE",(.15,-.05,1.02));label("SLOT2",(.15,-.05,1.16));label("STOPCOCK",(.12,-.12,.72));label("BAG1",(-.45,.08,2.75));label("MONITOR",(1.12,1.38,2.52))
    setup(sid,"病房输液泵装管与床头监护",(.35,-4.8,2.65),(.05,.75,1.45),4.8)
    return {"scene_id":sid,"title":"病房输液泵装管与床头监护","camera_position_m":[.35,-4.8,2.65],"camera_look_at_m":[.05,.75,1.45],
    "initial_instruction":"把新泵盒 PUMPCASSETTE 插进输液泵的 2 号泵槽 SLOT2,插好后核对 BAG1 背面的配置标签是不是 5% 糖,确认无误再把三通 STOPCOCK 顺时针拧 90 度开始输液,床头监护仪 MONITOR 全程盯着。",
    "objects":[("PUMPCASSETTE","一次性泵盒",["point","insert"]),("SLOT2","2号泵槽",["point"]),("STOPCOCK","三通旋塞",["point","rotate"]),("BAG1","5%糖袋",["point","inspect_back"]),("BAG2","10%盐水袋",["point"]),("MONITOR","床头监护仪",["point","wait"])]}

def write_config(meta):
    objs=[]
    for oid,labeltxt,caps in meta["objects"]:
        asset=f"assets/meshes/review/{meta['scene_id']}/{oid}.glb"
        o={"object_id":oid,"label":labeltxt,"asset":asset,"pose":{"position_m":[0,0,0],"wxyz":[1,0,0,0]},"capabilities":caps,"anchors":{},"description":labeltxt}
        if oid in ("POCKET9","VALVE","SLOT2"): o["anchors"]["insertion"]=[0,0,0]
        objs.append(o)
    spec={"schema_version":"1.0","scene_id":meta["scene_id"],"title":meta["title"],"units":"m","axes":"right_handed_z_up","objects":objs,
          "initial_instruction":meta["initial_instruction"],"camera_position_m":meta["camera_position_m"],"camera_look_at_m":meta["camera_look_at_m"],
          "environment":[],"render_hints":{"ortho_scale_m":4.8,"grid_extent_m":4.0,"cue_scale":1.0,"label_offset_m":.12,"fit_camera":False}}
    SCENE.mkdir(parents=True,exist_ok=True);(SCENE/f"{meta['scene_id']}.json").write_text(json.dumps(spec,ensure_ascii=False,indent=2))

def run():
    OUT.mkdir(parents=True,exist_ok=True);MESH.mkdir(parents=True,exist_ok=True)
    for build in (cnc,dive,infusion):
        meta=build();write_config(meta)
        asset_dir=MESH/meta["scene_id"];asset_dir.mkdir(parents=True,exist_ok=True)
        for oid,_,_ in meta["objects"]:
            matches=[o for o in bpy.context.scene.objects if oid in o.name or
                     (oid=="MODESWITCH" and "MODE_SWITCH" in o.name) or
                     (oid=="PUMPCASSETTE" and "pump" in o.name.lower())]
            if not matches:
                matches=[cube("asset_"+oid,(0,0,0),(.02,.02,.02),ORANGE,.002)]
            bpy.ops.object.select_all(action="DESELECT")
            for o in matches:
                o.select_set(True)
            bpy.context.view_layer.objects.active=matches[0]
            bpy.ops.export_scene.gltf(filepath=str(asset_dir/f"{oid}.glb"),export_format="GLB",
                                      use_selection=True,export_yup=False)
        sc=bpy.context.scene;sc.render.filepath=str(OUT/f"{meta['scene_id']}.png")
        blend=OUT/f"{meta['scene_id']}.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend));bpy.ops.render.render(write_still=True)
        print(json.dumps({"scene":meta["scene_id"],"blend":str(blend),"render":str(sc.render.filepath)}))

if __name__=="__main__": run()
