"""Regenerate original assets AND baseline scene/fixture JSON. Review edits before running.
Do not run over edited manifests without backing them up. No external assets are downloaded.
"""
from pathlib import Path
import json, math,sys
import numpy as np,trimesh
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'src'))
from holocue.geometry import primitive_pool

def col(mesh,color):mesh.visual.face_colors=np.array([*color,255],dtype=np.uint8);return mesh

def box(extents,xyz,color):
 m=trimesh.creation.box(extents);m.apply_translation(xyz);return col(m,color)
def cyl(radius,height,xyz,color,sections=48):
 m=trimesh.creation.cylinder(radius=radius,height=height,sections=sections);m.apply_translation(xyz);return col(m,color)
def merge(meshes):return trimesh.util.concatenate(meshes)
C={'blue':(99,144,174),'green':(111,166,151),'yellow':(209,172,93),'gray':(180,188,194),'white':(228,234,237),'dark':(65,80,91)}
assets={}
assets['knob']=merge([cyl(.042,.029,(0,0,.027),C['dark']),cyl(.037,.035,(0,0,.056),C['blue']),box((.005,.029,.002),(0,.006,.075),C['white']),box((.014,.007,.016),(0,-.043,.033),C['yellow'])])
assets['module']=merge([box((.09,.08,.055),(0,0,.028),C['green']),box((.07,.004,.03),(0,-.042,.029),C['dark']),box((.025,.006,.012),(.019,.043,.023),C['yellow']),cyl(.012,.003,(0,0,.058),C['white'])])
assets['plug']=merge([box((.04,.043,.026),(0,0,.02),C['blue']),box((.026,.020,.013),(0,.03,.02),C['dark']),box((.016,.008,.005),(0,.044,.02),C['yellow']),cyl(.008,.025,(0,-.027,.02),C['dark'])])
assets['socket']=merge([box((.065,.022,.05),(0,.02,.025),C['gray']),box((.009,.022,.05),(-.028,0,.025),C['gray']),box((.009,.022,.05),(.028,0,.025),C['gray']),box((.054,.022,.009),(0,0,.047),C['gray']),box((.054,.022,.009),(0,0,.0045),C['gray']),box((.038,.002,.026),(0,.008,.025),C['dark'])])
assets['brick']=merge([box((.063,.063,.025),(0,0,.018),C['yellow'])]+[cyl(.009,.008,(x,y,.035),C['yellow'],24) for x in (-.016,.016) for y in (-.016,.016)])
assets['brick_blue']=merge([box((.063,.063,.025),(0,0,.018),C['blue'])]+[cyl(.009,.008,(x,y,.035),C['blue'],24) for x in (-.016,.016) for y in (-.016,.016)])
assets['baseplate']=merge([box((.12,.12,.01),(0,0,.005),C['green'])]+[cyl(.007,.006,(x,y,.013),C['green'],20) for x in (-.04,-.02,0,.02,.04) for y in (-.04,-.02,0,.02,.04)])
assets['ring_arrow']=merge([trimesh.creation.annulus(r_min=.047,r_max=.053,height=.002,sections=64),box((.012,.022,.003),(.037,-.036,.002),C['green'])]);col(assets['ring_arrow'],(82,164,145))
assets['straight_arrow']=merge([box((.009,.075,.004),(0,.0,.003),C['green']),trimesh.creation.cone(radius=.02,height=.032,sections=3)])
# Orient cone along +Y and put at the shaft end.
cone=trimesh.creation.cone(radius=.022,height=.034,sections=3);cone.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2,[1,0,0]));cone.apply_translation((0,.035,.005));col(cone,C['green'])
assets['straight_arrow']=merge([box((.009,.075,.004),(0,0,.005),C['green']),cone])
for name,m in assets.items():
 (R/'assets/meshes'/f'{name}.glb').write_bytes(trimesh.Scene(m).export(file_type='glb'))
 # OBJ provides an importer-independent geometry alternative; GLB retains materials.
 (R/'assets/meshes'/f'{name}.obj').write_text(trimesh.exchange.obj.export_obj(m,include_color=True),encoding='utf-8')

def obj(i,label,asset,p,color,cap,anchors=None,desc=''):
 return {'object_id':i,'label':label,'asset':f'assets/meshes/{asset}.glb','pose':{'position_m':p,'wxyz':[1,0,0,0]},'color':C[color],'capabilities':cap,'anchors':anchors or {},'description':desc}
scenes=[{
 'schema_version':'1.0','scene_id':'control_panel','title':'旋钮与背面检查','units':'m','axes':'right_handed_z_up',
 'objects':[obj('A','旋钮 A','knob',[-.18,-.04,0],'blue',['point','rotate','inspect_back']),
            obj('B','旋钮 B','knob',[0,.075,.025],'blue',['point','rotate','inspect_back'],desc='当前操作对象，顶部白线是角度指示线'),
            obj('C','模块 C','module',[.18,.2,.05],'green',['point','inspect_back'],desc='背面有凸出的黄色定位结构')],
 'initial_instruction':'把 B 逆时针转 30 度，接着检查 C 的背面。',
 'camera_position_m':[.75,-.83,.68],'camera_look_at_m':[0,.10,.06]},
 {'schema_version':'1.0','scene_id':'connector','title':'插头的空间对准','units':'m','axes':'right_handed_z_up',
 'objects':[obj('P','蓝色插头','plug',[-.04,-.14,0],'blue',['point','insert','inspect_back']),
            obj('S','目标插座','socket',[-.04,.13,0],'gray',['point','inspect_back'],{'insertion':[0,-.027,0]}),
            obj('C','备用模块','module',[.16,.23,.025],'green',['point','inspect_back'])],
 'initial_instruction':'演示把 P 插进 S，插好后再检查 C。',
 'camera_position_m':[.60,-.78,.60],'camera_look_at_m':[.03,.03,.04]},
 {'schema_version':'1.0','scene_id':'blocks','title':'积木的分步搭建','units':'m','axes':'right_handed_z_up',
 'objects':[obj('A','黄色积木','brick',[-.15,-.09,0],'yellow',['point','assemble','inspect_back']),
            obj('B','蓝色积木','brick_blue',[.15,-.03,0],'blue',['point','assemble','inspect_back'],{'placement':[0,0,.034]}),
            obj('BASE','绿色底板','baseplate',[0,.20,0],'green',['point'],{'placement':[0,0,.011]})],
 'initial_instruction':'先把 A 放到底板 BASE 上，然后检查 B 的背面。',
 'camera_position_m':[.68,-.85,.72],'camera_look_at_m':[0,.10,.04]}
]
for s in scenes:(R/'configs/scenes'/f"{s['scene_id']}.json").write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'assets/gaussians').mkdir(exist_ok=True)
for k in ['ring_arrow','straight_arrow','highlight']:
 np.savez_compressed(R/'assets/gaussians'/f'{k}.npz',positions=primitive_pool(k),provenance=np.array('geometric_preview_pool_not_optically_fitted'))
(R/'assets/ASSET_LICENSE.md').write_text('''# 固定资产来源与许可\n\n本包的九组 GLB 和 OBJ 几何、Gaussian 预览采样池由本次交付的生成脚本创建，使用原创基础几何组合。可在该项目中使用、修改和重新发布；固定资产按 CC0 1.0 提供。\n\n这些是通用旋钮、模块、插接件和积木造型，不对应真实商业器件或品牌 CAD。GLB 包含顶点颜色，OBJ 提供简便的几何导入。几何单位是米，坐标为右手系、Z 轴向上。\n\nGaussian NPZ 是可重复的几何采样池，用于测试数量变化与接口。光学拟合与标定由全息后端提供。外部论文代码和模型权重均未打入本包，使用时遵循对应项目许可。\n''',encoding='utf-8')
# Exact replay fixtures are deliberately separate from the live planning path.
def cue(target,action,ctype,role,prio,depth,instruction,angle=None,ref=None):
 return dict(target_id=target,action=action,cue_type=ctype,task_role=role,priority=prio,depth_requirement=depth,instruction=instruction,angle_deg=angle,reference_id=ref)
fixtures=[
 {'id':'panel_start','scene_id':'control_panel','input':scenes[0]['initial_instruction'],'decision':{'operation':'replace','assistant_message':'先转动 B，再检查 C 的背面。','cues':[cue('B','rotate','ring_arrow','current',5,'precise','B 逆时针转 30 度',30),cue('C','inspect_back','ghost_motion','next',2,'persistent','接着检查 C 的背面')]}},
 {'id':'panel_interrupt','scene_id':'control_panel','input':'先别管 B，看看 C 的背面，保留 B 的角度。','decision':{'operation':'interrupt','assistant_message':'先检查 C，B 的 30 度参数已保留。','cues':[cue('C','inspect_back','ghost_motion','current',5,'precise','查看 C 的背面')]}},
 {'id':'panel_resume','scene_id':'control_panel','input':'继续刚才 B 的任务。','decision':{'operation':'resume','assistant_message':'继续把 B 逆时针转 30 度。','cues':[]}},
 {'id':'connector_start','scene_id':'connector','input':scenes[1]['initial_instruction'],'decision':{'operation':'replace','assistant_message':'先演示 P 插入 S，再检查 C。','cues':[cue('P','insert','ghost_motion','current',5,'precise','将 P 对准 S 插入',ref='S'),cue('C','inspect_back','ghost_motion','next',2,'persistent','检查 C 的背面')]}},
 {'id':'blocks_start','scene_id':'blocks','input':scenes[2]['initial_instruction'],'decision':{'operation':'replace','assistant_message':'先把黄色积木放在底板上，再看蓝色积木。','cues':[cue('A','assemble','ghost_motion','current',5,'precise','把 A 放在 BASE 上',ref='BASE'),cue('B','inspect_back','ghost_motion','next',2,'persistent','检查 B 的背面')]}}
]
(R/'examples/replay.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2),encoding='utf-8')
print('assets',len(assets),'scenes',len(scenes))
