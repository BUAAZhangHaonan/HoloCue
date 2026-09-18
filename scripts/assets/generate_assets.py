"""Regenerate the original base geometry (nine GLB/OBJ pairs + gaussian pools) only.

Scene/fixture JSON (scenes/<id>/scene.json, examples/replay.json) and assets/ASSET_LICENSE.md
are hand-curated sources of truth with later field fixes and license sections; this
generator must never overwrite them. No external assets are downloaded.
"""
from pathlib import Path
import math,sys
import numpy as np,trimesh
R=Path(__file__).resolve().parents[2]
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
(R/'assets/gaussians').mkdir(exist_ok=True)
for k in ['ring_arrow','straight_arrow','highlight']:
 np.savez_compressed(R/'assets/gaussians'/f'{k}.npz',positions=primitive_pool(k),provenance=np.array('geometric_preview_pool_not_optically_fitted'))
print('assets',len(assets))
