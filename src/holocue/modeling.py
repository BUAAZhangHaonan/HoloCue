"""Dimensioned, reusable CAD parts for the twelve teaching workstations.

Meshes are authored Z-up in metres and exported as standard Y-up glTF.
Labels are rasterized into embedded textures; font files are never exported.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from .models import SceneObject, SceneSpec
from .spatial import rotation

STEEL=(148,163,174)
DARK=(45,59,73)
RUBBER=(38,44,48)
LIGHT=(207,215,221)
BRASS=(178,150,82)
ORANGE=(219,132,47)


def cad_mesh(shape: cq.Workplane) -> trimesh.Trimesh:
    vertices, faces = shape.val().tessellate(.0006, .16)
    # CAD fillet poles can emit zero-area triangles with repeated vertices.
    # Remove those during validation so closed solids retain closed topology.
    return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces,
                           process=True, validate=True)


@lru_cache(maxsize=512)
def rounded_box(size: tuple[float,float,float]) -> trimesh.Trimesh:
    if min(size) <= 0:
        raise ValueError('box dimensions must be positive')
    radius = min(min(size)*.16, .006)
    return cad_mesh(cq.Workplane('XY').box(*size).edges().fillet(radius))


class Assembly:
    def __init__(self, name: str) -> None:
        self.name=name
        self.scene=trimesh.Scene()
        self.index=0

    def add(self, mesh, color=LIGHT, position=(0,0,0), axis=None, metal=.0, rough=.44, name='part'):
        item=mesh.copy()
        if axis is not None:
            item.apply_transform(trimesh.geometry.align_vectors([0,0,1],axis))
        item.apply_translation(position)
        # Split hard edges while preserving the authored triangles. Set PBR
        # after smoothing because trimesh submesh does not retain no-UV visuals.
        item=trimesh.graph.smooth_shade(item,angle=np.radians(20.),facet_minarea=None)
        material=trimesh.visual.material.PBRMaterial(name=f'{name}_material',
            baseColorFactor=[*color,255], metallicFactor=metal, roughnessFactor=rough,
            doubleSided=False)
        item.visual=trimesh.visual.TextureVisuals(material=material)
        self.scene.add_geometry(item,node_name=f'{self.name}/{self.index:04d}_{name}',
                                geom_name=f'{self.name}_{self.index:04d}')
        self.index+=1
        return item

    def box(self, size, position=(0,0,0), color=LIGHT, metal=0., name='panel'):
        return self.add(rounded_box(tuple(size)),color,position,metal=metal,name=name)

    def cylinder(self,radius,height,position=(0,0,0),color=STEEL,axis=(0,0,1),name='cylinder'):
        return self.add(trimesh.creation.cylinder(radius,height,sections=40),color,position,
                        axis=axis,metal=.65 if color==STEEL else .1,name=name)

    def ring(self,inner,outer,height,position=(0,0,0),color=STEEL,axis=(0,0,1),name='ring'):
        return self.add(trimesh.creation.annulus(inner,outer,height,sections=48),color,position,
                        axis=axis,metal=.6,name=name)

    def rod(self,a,b,radius,color=STEEL,name='tube'):
        return self.add(trimesh.creation.cylinder(radius=radius,segment=np.asarray([a,b]),sections=20),
                        color,metal=.45,name=name)

    def sphere(self,radii,position,color=LIGHT,name='rounded_part'):
        mesh=trimesh.creation.icosphere(subdivisions=2)
        mesh.apply_scale(radii)
        return self.add(mesh,color,position,name=name)

    def screws(self,x,y,z,axis=(0,0,1)):
        for xx in (-x,x):
            for yy in (-y,y):
                self.cylinder(.0035,.002,(xx,yy,z),STEEL,axis,'fastener')

    def label(self,text,center,width,height,normal=(0,-1,0),background=(226,232,230),ink=DARK):
        pixel_height=max(64,min(512,round(512*height/width)))
        image=Image.new('RGB',(512,pixel_height),background)
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((6,6,506,pixel_height-6),radius=8,outline=ink,width=3)
        lines=text.split('\n')
        row_height=(pixel_height-18)/len(lines)
        for i,line in enumerate(lines):
            font_size=max(8,int(row_height*.64))
            font=ImageFont.truetype('DejaVuSans.ttf',font_size)
            while font.getlength(line)>472 and font_size>8:
                font_size-=1
                font=ImageFont.truetype('DejaVuSans.ttf',font_size)
            draw.text((256,9+(i+.5)*row_height),line,font=font,fill=ink,anchor='mm')
        up=np.array([0.,0.,1.])
        n=np.asarray(normal,float)
        if abs(n@up)>.95:
            up=np.array([0.,1.,0.])
        right=np.cross(up,n);right/=np.linalg.norm(right)
        up=np.cross(n,right)
        vertices=np.asarray([(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)])
        world=np.asarray(center)+vertices[:,0,None]*width*right+vertices[:,1,None]*height*up
        material=trimesh.visual.material.PBRMaterial(baseColorTexture=image,roughnessFactor=.75,metallicFactor=0)
        visual=trimesh.visual.TextureVisuals(uv=np.asarray([[0,0],[1,0],[1,1],[0,1]]),material=material)
        mesh=trimesh.Trimesh(vertices=world,faces=[[0,1,2],[0,2,3]],visual=visual,process=False)
        self.scene.add_geometry(mesh,node_name=f'{self.name}/label_{self.index}',geom_name=f'label_{self.index}')
        self.index+=1

    def transform(self, transform):
        self.scene.apply_transform(transform)

    def save(self,path: Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        exported=self.scene.copy()
        exported.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
        exported.export(str(path),file_type='glb',include_normals=True)


def box_frame(a: Assembly,size,thickness,color=LIGHT):
    x,y,z=size;t=thickness
    a.box((x,y,t),(0,0,-z/2+t/2),color)
    a.box((t,y,z),(-x/2+t/2,0,0),color)
    a.box((t,y,z),(x/2-t/2,0,0),color)
    a.box((x-2*t,t,z),(0,-y/2+t/2,0),color)
    a.box((x-2*t,t,z),(0,y/2-t/2,0),color)


def hollow_front(a,size,wall,color,top_inlay: cq.Workplane | None=None):
    x,y,z=size;t=wall
    a.box((t,y,z),(-x/2+t/2,0,0),color)
    a.box((t,y,z),(x/2-t/2,0,0),color)
    a.box((x-2*t,y,t),(0,0,-z/2+t/2),color)
    if top_inlay is None:
        a.box((x-2*t,y,t),(0,0,z/2-t/2),color)
    else:
        roof=cq.Workplane('XY').box(x-2*t,y,t).edges().fillet(min(min(x-2*t,y,t)*.16,.006))
        roof=roof.translate((0,0,z/2-t/2))
        a.add(cad_mesh(roof.cut(top_inlay)),color,name='panel')
    a.box((x-2*t,t,z-2*t),(0,y/2-t/2,0),DARK)


def make_object(obj: SceneObject) -> Assembly:
    a=Assembly(obj.object_id)
    x,y,z=obj.size_m;c=obj.color;k=obj.recipe
    if k=='knob':
        a.cylinder(min(x,y)*.44,z*.70,(0,0,.05*z),c,name='grip')
        a.cylinder(min(x,y)*.47,z*.12,(0,0,-.38*z),DARK,name='flange')
        for theta in np.linspace(0,2*np.pi,28,endpoint=False):
            a.cylinder(min(x,y)*.018,z*.62,(min(x,y)*.437*np.cos(theta),min(x,y)*.437*np.sin(theta),z*.05),DARK,name='knurl')
        a.box((x*.065,y*.29,z*.025),(0,y*.23,z*.412),LIGHT,name='index_mark')
        a.transform(trimesh.geometry.align_vectors([0,0,1],obj.interaction.rotation_axis_local))
    elif k=='module':
        a.box((x,y,z),(0,0,0),c,name='housing')
        a.box((x*.70,.003,z*.56),(0,-y/2-.001,0),DARK,name='front_panel')
        a.label(obj.object_id,(0,-y/2-.003,0),x*.58,z*.36)
        a.box((x*.25,.010,z*.25),(0,y/2+.003,z*.20),ORANGE,name='polarizing_key')
        for xx in np.linspace(-x*.30,x*.30,4):
            a.cylinder(.004,.008,(xx,y/2+.003,-z*.17),BRASS,(0,1,0),'terminal')
        a.label('REAR\nKEY + CONTACTS',(0,y/2+.001,-z*.34),x*.8,z*.18,(0,1,0))
        a.screws(x*.4,y*.39,z/2+.001)
    elif k=='plug':
        a.box((x,y*.68,z),(0,-y*.15,0),c,name='grip')
        for yy in np.linspace(-y*.4,y*.10,6):
            a.box((x*1.02,.003,z*.80),(0,yy,0),DARK,name='grip_rib')
        a.box((x*.72,y*.22,z*.70),(0,y*.29,0),DARK,name='keyed_nose')
        a.box((x*.18,y*.25,.004),(0,y*.28,z*.39),ORANGE,name='top_key')
        for xx in (-x*.22,x*.22):
            for zz in (-z*.17,z*.17):
                a.cylinder(.003,.018,(xx,y*.418,zz),BRASS,(0,1,0),'contact_pin')
        a.label('P\nALIGN KEY',(0,-y*.491,0),x*.70,z*.65)
    elif k=='socket':
        # Cut the actual rounded marker volume out of its supporting roof.
        inlay=cq.Workplane('XY').box(.012,y,.003).edges().fillet(.003*.16)
        inlay=inlay.translate((0,0,z*.47))
        hollow_front(a,(x,y,z),.005,c,top_inlay=inlay)
        for xx in (-.072*.22,.072*.22):
            for zz in (-.042*.17,.042*.17):
                a.ring(.0034,.0054,.018,(xx,-.002,zz),BRASS,(0,1,0),'contact_socket')
        a.add(cad_mesh(inlay),ORANGE,name='key_channel_mark')
        a.label('S\nRECEIVER',(0,y/2+.001,0),x*.8,z*.55,(0,1,0))
    elif k=='brick':
        thickness=.0016
        # A single molded shell avoids coplanar faces where five panels met.
        # Preserve the former panels' outer radius and the real open underside.
        outside=cq.Workplane('XY').box(x,y,z).edges().fillet(thickness*.16)
        cavity=cq.Workplane('XY').box(x-2*thickness,y-2*thickness,z).translate((0,0,-thickness))
        a.add(cad_mesh(outside.cut(cavity)),c,name='open_bottom_shell')
        for xx in (-.024,-.008,.008,.024):
            for yy in (-.008,.008):a.cylinder(.0048,.0036,(xx,yy,z/2+.0018),c,name='stud')
        for xx in (-.016,0,.016):a.ring(.0047,.0064,z-thickness,(xx,0,-thickness/2),c,name='underside_tube')
    elif k=='baseplate':
        a.box((x,y,z),(0,0,0),c)
        for xx in np.arange(-x/2+.008,x/2,.016):
            for yy in np.arange(-y/2+.008,y/2,.016):a.cylinder(.0048,.0036,(xx,yy,z/2+.0018),c,name='stud')
    elif k=='server':
        a.box((x,y,z),(0,0,0),c,metal=.65,name='chassis')
        for xx in np.linspace(-x*.38,x*.2,20):
            a.box((.005,.0015,z*.57),(xx,-y/2-.0008,0),DARK,name='vent_slot')
        for xx in (-x*.46,x*.46):
            a.rod((xx,-y*.50,-z*.25),(xx,-y*.56,-z*.25),.004)
            a.rod((xx,-y*.56,-z*.25),(xx,-y*.56,z*.25),.004)
            a.rod((xx,-y*.56,z*.25),(xx,-y*.50,z*.25),.004)
        if obj.object_id=='NODE3':
            # Preserve the inspected fiber sockets in the current +Y rear frame.
            # The short cable tails stay above the chassis underside/support plane.
            for index,xx in enumerate(np.linspace(-x*.25,x*.25,4)):
                center=(xx,y/2+.006,z*.12)
                a.ring(z*.115,z*.18,.011,center,DARK,(0,1,0),'fiber_socket')
                collar_color=(40,175,166) if index==1 else STEEL
                a.ring(z*.12,z*.235,.004,(xx,y/2+.013,z*.12),collar_color,
                       (0,1,0),'fiber_live_collar' if index==1 else 'fiber_collar')
                if index!=1:
                    cable_color=[(45,126,153),RUBBER,(52,144,143),RUBBER][index]
                    a.cylinder(z*.095,.009,(xx,y/2+.016,z*.12),cable_color,(0,1,0),'fiber_plug')
                    a.rod((xx,y/2+.020,z*.12),(xx,y/2+.030,-z*.13),
                          z*.075,cable_color,'fiber_cable_tail')
                    a.rod((xx,y/2+.030,-z*.13),(xx,y/2+.034,-z*.34),
                          z*.075,cable_color,'fiber_cable_tail')
            a.box((x*.38,.007,z*.12),(0,y/2+.004,-z*.33),DARK,name='rear_pull_handle')
        else:
            for xx in np.linspace(-x*.35,x*.25,6):
                a.box((.031,.008,.014),(xx,y/2+.003,0),DARK,name='port')
                a.box((.020,.001,.009),(xx,y/2+.0076,0),BRASS,name='port_contact')
        a.label(obj.object_id,(x*.33,-y/2-.002,0),x*.22,z*.75)
        a.label('PORTS',(x*.39,y/2+.009,0),x*.18,z*.60,(0,1,0))
        a.screws(x*.45,y*.44,z/2+.001)
    elif k=='rack_slot':
        for xx in (-x/2+.006,x/2-.006):
            a.box((.012,y,z),(xx,0,0),c,metal=.7,name='rail')
            a.box((.026,y,.005),(xx-np.sign(xx)*.007,0,-z/2+.004),STEEL,name='support_lip')
        a.box((x,.012,z),(0,y/2-.006,0),DARK,name='back_stop')
    elif k=='beacon':
        a.cylinder(x*.48,z*.18,(0,0,-z*.40),DARK)
        for i,color in enumerate([(56,152,111),(229,173,43),(201,72,58)]):
            a.cylinder(x*.43,z*.24,(0,0,z*(-.2+i*.25)),color,name='status_lens')
            a.ring(x*.41,x*.47,.004,(0,0,z*(-.32+i*.25)),DARK)
    elif k in ('tray','crate'):
        box_frame(a,(x,y,z),min(x,y,z)*.075,c)
        if k=='crate':
            for xx in np.linspace(-x*.42,x*.42,9):a.box((.004,.004,z*.7),(xx,y/2+.002,0),LIGHT,name='reinforcing_rib')
            a.label('BLUE\nSHIPMENT 027',(0,y/2+.005,0),x*.73,z*.55,(0,1,0))
    elif k=='battery':
        a.box((x,y,z),(0,0,0),c,name='battery_shell')
        for xx in (-x*.36,x*.36):a.box((.008,y*.85,.004),(xx,0,-z/2),DARK,name='guide_rail')
        for xx in np.linspace(-x*.28,x*.28,4):a.box((.009,.015,.001),(xx,y*.30,-z/2-.0007),BRASS,name='contact')
        a.label('BAT\nTRAINING',(0,0,z/2+.001),x*.85,y*.40,(0,0,1))
    elif k=='motor':
        a.cylinder(x*.42,z*.67,(0,0,0),DARK,name='stator')
        a.cylinder(x*.48,z*.12,(0,0,-z*.40),STEEL,name='mount')
        a.cylinder(x*.39,z*.16,(0,0,z*.33),c,name='rotor')
        a.cylinder(.006,.010,(0,0,z*.49),STEEL,name='shaft')
        for theta in np.linspace(0,2*np.pi,20,endpoint=False):
            a.cylinder(.0015,z*.56,(x*.415*np.cos(theta),x*.415*np.sin(theta),0),BRASS,name='stator_detail')
        if obj.object_id=='M3':
            # Local +X is the declared inspection face, without the old pose flip.
            point=np.asarray(obj.interaction.inspect_point_local_m)
            a.cylinder(z*.22,x*.10,tuple(point-[x*.09,0,0]),DARK,(1,0,0),'isolator_seat')
            a.add(trimesh.creation.annulus(z*.095,z*.245,x*.055,sections=64),
                  ORANGE,tuple(point-[x*.0275,0,0]),axis=(1,0,0),
                  metal=0.,rough=.88,name='isolator_ring')
            a.cylinder(z*.063,x*.02,tuple(point-[x*.05,0,0]),STEEL,(1,0,0),'isolator_bolt')
    elif k=='instrument':
        a.box((x,y,z),(0,0,0),c,name='instrument_case')
        a.box((x*.84,.002,z*.78),(0,-y/2-.001,0),DARK,name='bezel')
        a.label(obj.object_id+'\nTRAINING READY',(0,-y/2-.0025,z*.08),x*.70,z*.46,
                background=(35,58,66),ink=(134,223,196))
        for xx in np.linspace(-x*.25,x*.25,4):a.cylinder(z*.04,.005,(xx,-y/2-.004,-z*.28),LIGHT,(0,-1,0),'button')
        for xx in np.linspace(-x*.35,x*.35,12):a.box((.003,.002,z*.52),(xx,y/2+.001,0),DARK,name='rear_vent')
    elif k=='parcel':
        a.box((x,y,z),(0,0,0),c,name='carton')
        a.box((x*.15,y+.001,.001),(0,0,z/2+.0006),(190,163,115),name='tape')
        a.box((x*.15,.001,z),(0,-y/2-.0006,0),(190,163,115),name='tape')
        a.label(obj.object_id+'\nBATCH 027',(0,y/2+.001,0),x*.70,z*.50,(0,1,0))
    elif k in ('lens','mirror'):
        center=(0,0,z*.16)
        a.ring(x*.34,x*.48,y*.54,center,DARK,(0,1,0),'optic_retainer')
        if k=='lens':
            a.sphere((x*.35,y*.15,x*.35),center,(145,192,202),'convex_lens')
        else:
            a.add(trimesh.creation.cylinder(x*.35,.004,sections=64),
                  (192,209,218),(0,-y*.20,z*.16),axis=(0,1,0),
                  metal=.95,rough=.08,name='mirror_face')
        a.cylinder(.007,z*.5,(0,0,-z*.25),STEEL,name='mounting_post')
        for xx in (-x*.37,x*.37):a.cylinder(.005,.018,(xx,y*.36,z*.18),BRASS,(0,1,0),'adjuster')
        if k=='mirror':
            base_radius=min(x*.40,y*.48)
            base_z=-z*.45
            a.cylinder(base_radius,z*.08,(0,0,base_z),DARK,name='rotation_base')
            a.ring(base_radius*.78,base_radius,.0015,(0,0,base_z+z*.05),STEEL,name='degree_bezel')
            for index,degrees in enumerate(range(225,316,5)):
                angle=np.deg2rad(degrees)
                inner=base_radius*(.78 if index%3==0 else .86)
                outer=base_radius*.97
                a.rod((inner*np.cos(angle),inner*np.sin(angle),base_z+z*.06),
                      (outer*np.cos(angle),outer*np.sin(angle),base_z+z*.06),
                      .00055,LIGHT,'degree_tick')
            a.rod((0,-base_radius*.47,base_z+z*.075),
                  (0,-base_radius*.88,base_z+z*.075),.0012,ORANGE,'degree_pointer')
            a.box((x*.96,y*.36,z*.06),(0,0,-z*.32),DARK,name='gimbal_crossbar')
            for sign in (-1,1):
                a.box((x*.035,y*.40,z*.72),(sign*x*.479,0,z*.04),DARK,name='gimbal_fork')
                a.cylinder(.0025,x*.055,(sign*x*.463,0,z*.16),STEEL,(1,0,0),'gimbal_pivot')
            a.cylinder(x*.335,y*.30,(0,y*.34,z*.16),DARK,(0,1,0),'rear_coating_plate')
            a.label(obj.object_id+'\nHR-45° 1064',(0,y*.495,z*.16),x*.55,x*.29,(0,1,0))
            a.box((x*.24,.001,.002),(0,y*.50,z*.39),LIGHT,name='rear_index_line')
        else:
            a.label(obj.object_id+'\nCOATING 01',(0,y*.285,z*.16),x*.62,x*.24,(0,1,0))
    elif k=='post':
        a.box((x,y,.015),(0,0,-z/2+.0075),DARK)
        a.ring(.0075,.017,z*.88,(0,0,z*.01),STEEL,name='post_holder')
        a.cylinder(.009,.025,(.021,0,z*.20),DARK,(1,0,0),'locking_knob')
        a.screws(x*.35,y*.32,-z/2+.016)
    elif k=='target_screen':
        a.box((x,y,z),(0,0,0),DARK)
        a.box((x*.88,.002,z*.87),(0,-y/2-.001,0),LIGHT)
        a.box((x*.78,.001,.001),(0,-y/2-.002,0),DARK)
        a.box((.001,.001,z*.78),(0,-y/2-.002,0),DARK)
        for rr in (.02,.04,.06):a.ring(rr,rr+.001,.001,(0,-y/2-.003,0),DARK,(0,1,0),'target_ring')
    elif k=='potsherd':
        rows=97 if obj.object_id=='POT3' else 25
        cols=49;vertices=[]
        for side in (-1,1):
            for j in range(rows):
                height=z*(j/(rows-1)-.5)
                for i in range(cols):
                    lateral=2*i/(cols-1)-1
                    # A finite wall with concave +Y interior. The previous radial
                    # offset collapsed both surfaces onto y=0 at the centerline.
                    surface=y*(.40*lateral*lateral+side*.25)
                    if obj.object_id=='POT3' and side==1:
                        for band in (-.22,0.,.22):
                            center=z*(band+.012*np.sin(5*lateral))
                            surface-=y*.075*np.exp(-.5*((height-center)/(z*.014))**2)
                    vertices.append([x*.5*lateral,surface,height*(.96+.04*np.cos(3*lateral))])
        faces=[];layer=rows*cols
        for offset,flip in ((0,False),(layer,True)):
            for j in range(rows-1):
                for i in range(cols-1):
                    v=offset+j*cols+i
                    for f in ([v,v+1,v+cols+1],[v,v+cols+1,v+cols]):faces.append(f[::-1] if flip else f)
        boundary=list(range(cols))+[j*cols+cols-1 for j in range(1,rows)]+list(range((rows-1)*cols+cols-2,(rows-1)*cols-1,-1))+[j*cols for j in range(rows-2,0,-1)]
        for u,v in zip(boundary,boundary[1:]+boundary[:1]):faces.extend([[u,v,v+layer],[u,v+layer,u+layer]])
        shard=trimesh.Trimesh(vertices=vertices,faces=faces,process=True)
        shard.fix_normals()
        a.add(shard,c,rough=.86,name='incised_inner_wall' if obj.object_id=='POT3' else 'curved_shard')
    elif k=='bone':
        a.sphere((x*.42,y*.27,z*.30),(0,0,0),c,'shaft')
        for xx in (-x*.39,x*.39):
            for yy in (-y*.16,y*.16):a.sphere((x*.12,y*.32,z*.49),(xx,yy,0),c,'bone_end')
    elif k=='flag':
        a.cylinder(.004,z,(0,0,0),STEEL,name='flagpole')
        a.box((x*.82,.002,z*.32),(x*.41,0,z*.27),c,name='flag')
        a.label('MARK',(x*.40,-.0013,z*.27),x*.62,z*.20,background=c)
    elif k=='total_station':
        a.box((x,y,z*.63),(0,0,z*.12),c)
        a.cylinder(x*.23,y*.80,(0,-y*.22,z*.17),DARK,(0,-1,0),'telescope')
        a.cylinder(x*.17,.003,(0,-y*.63,z*.17),(98,160,177),(0,-1,0),'objective')
        a.cylinder(x*.40,z*.17,(0,0,-z*.37),DARK,name='tribrach')
        a.label('STAY\nLOCKED',(0,y/2+.001,0),x*.73,z*.37,(0,1,0))
    elif k=='trowel':
        blade=cq.Workplane('XY').polyline([(-x/2,0),(0,-y*.48),(x/2,0)]).close().extrude(.003)
        a.add(cad_mesh(blade),STEEL,position=(0,0,-.002),metal=.7,name='blade')
        a.cylinder(z*.47,y*.48,(0,y*.20,0),(144,98,56),(0,1,0),'handle')
        a.cylinder(.005,y*.20,(0,-y*.02,0),STEEL,(0,1,0),'tang')
    elif k=='screw':
        a.cylinder(y*.28,x*.74,(-x*.06,0,0),STEEL,(1,0,0),'threaded_shank')
        for xx in np.linspace(-x*.40,x*.18,9):a.ring(y*.26,y*.36,.001,(xx,0,0),STEEL,(1,0,0),'thread')
        head=trimesh.creation.cylinder(y*.53,x*.23,sections=6)
        a.add(head,c,(x*.30,0,0),axis=(1,0,0),metal=.7,name='hex_head')
        a.box((.001,y*.65,.0018),(x*.423,0,0),DARK,name='driver_slot')
    elif k=='sparkplug':
        a.cylinder(.007,z*.39,(0,0,z*.20),LIGHT,name='ceramic')
        for zz in np.linspace(0,z*.33,6):a.cylinder(.008,.003,(0,0,zz),LIGHT,name='ceramic_rib')
        a.add(trimesh.creation.cylinder(.0105,.009,sections=6),STEEL,(0,0,-z*.05),metal=.8,name='hex_nut')
        a.cylinder(.006,z*.38,(0,0,-z*.28),STEEL,name='threaded_shell')
        for zz in np.linspace(-z*.45,-z*.13,10):a.ring(.0058,.0065,.001,(0,0,zz),STEEL,name='thread')
        # Keep the existing terminal tip, joining its base to the ceramic cap.
        ceramic_top=z*(.20+.39/2)
        terminal_top=z*.47+.009/2
        a.cylinder(.002,terminal_top-ceramic_top,
                   (0,0,(terminal_top+ceramic_top)/2),STEEL,name='terminal')
    elif k in ('bore','tool_socket'):
        inner=.012 if k=='bore' else .020
        # The upper 6 mm belongs to the seating collar, not a second exposed cap.
        a.ring(inner,x/2,z-.006,(0,0,-.003),c,name='receiver_bore')
        a.ring(inner,x*.55,.006,(0,0,z/2-.003),STEEL,name='seating_face')
    elif k=='toolholder':
        a.cylinder(.010,z*.42,(0,0,-z*.285),STEEL,name='tool_shank')
        a.cylinder(x*.49,.012,(0,0,-.009),STEEL,name='flange')
        taper=cq.Workplane('XY').add(cq.Solid.makeCone(x*.34,x*.15,z*.38))
        a.add(cad_mesh(taper),c,(0,0,0),metal=.8,name='taper')
        a.cylinder(.006,z*.13,(0,0,z*.43),STEEL,name='pull_stud')
        a.cylinder(.009,z*.035,(0,0,z*.49),STEEL,name='stud_head')
        # Cutting insert remains inside the .020 m shank diameter and therefore
        # does not reduce the declared tool-socket clearance.
        a.box((.012,.003,.009),(0,-.008,z*-.45),BRASS,name='carbide_insert')
        a.cylinder(.0015,.0015,(0,-.010,z*-.45),DARK,(0,-1,0),'insert_fastener')
    elif k=='magazine':
        a.ring(x*.20,x*.48,y*.32,(0,0,0),c,(0,1,0),'magazine_disc')
        a.cylinder(x*.15,y*.50,(0,0,0),DARK,(0,1,0),'hub')
        for t in np.linspace(0,2*np.pi,12,endpoint=False):
            a.ring(.020,.027,y*.55,(x*.36*np.cos(t),-y*.1,z*.36*np.sin(t)),STEEL,(0,1,0),'pocket')
    elif k=='din_connector':
        a.cylinder(x*.48,y*.55,(0,-y*.10,0),DARK,(0,1,0),'handwheel')
        a.cylinder(x*.27,y*.35,(0,y*.32,0),BRASS,(0,1,0),'nose')
        for yy in np.linspace(y*.22,y*.46,7):a.ring(x*.25,x*.29,.001,(0,yy,0),BRASS,(0,1,0),'thread')
        # Keep the current DIN mating nose; restore grip and retaining detail on
        # the non-mating handwheel, without adding an incompatible quick latch.
        for angle in np.linspace(0,2*np.pi,24,endpoint=False):
            a.cylinder(x*.014,y*.45,(x*.478*np.cos(angle),-y*.10,z*.478*np.sin(angle)),
                       STEEL,(0,1,0),'handwheel_knurl')
        a.ring(x*.29,x*.45,.002,(0,y*.175,0),STEEL,(0,1,0),'retaining_collar')
        a.label('DRY',(0,-y*.38,0),x*.70,z*.4)
    elif k=='valve':
        size=(x*.7,y*.7,z*.70)
        body=cq.Workplane('XY').box(*size).edges().fillet(min(min(size)*.16,.006))
        # Continue the receiver's actual 17 mm bore into the valve body. The
        # mating nose enters this cavity instead of intersecting a solid box.
        bore=cq.Workplane('XY').add(cq.Solid.makeCylinder(.017,.032,
            cq.Vector(0,-y*.32-.016,0),cq.Vector(0,1,0)))
        a.add(cad_mesh(body.cut(bore)),c,metal=.7,name='panel')
        a.ring(.017,.025,.032,(0,-y*.32,0),BRASS,(0,1,0),'DIN_receiver')
        a.cylinder(.013,z*.45,(0,0,-z*.37),BRASS,name='neck')
        a.cylinder(.020,.022,(x*.35,0,z*.13),DARK,(1,0,0),'handwheel')
    elif k=='cylinder':
        a.cylinder(x*.49,z*.77,(0,0,-z*.025),c,name='bottle_body')
        a.sphere((x*.49,y*.49,z*.13),(0,0,z*.345),c,'shoulder')
        a.sphere((x*.49,y*.49,z*.08),(0,0,-z*.41),c,'base')
        a.cylinder(x*.13,z*.08,(0,0,z*.49),STEEL,name='neck')
        a.ring(x*.46,x*.52,.025,(0,0,-z*.43),DARK,name='boot')
        a.label('TRAINING\n'+obj.object_id,(0,y*.491,z*.22),x*.75,z*.13,(0,1,0))
        a.label(obj.object_id,(0,-y*.493,0),x*.75,z*.15)
    elif k=='lever':
        a.cylinder(.016,.032,(0,0,0),BRASS,(0,-1,0),'spindle')
        a.box((x*.26,y*.55,z*.80),(0,-y*.6,z*.23),c,name='handle')
        a.cylinder(.010,.006,(0,-y*.8,0),STEEL,(0,-1,0),'retaining_bolt')
    elif k=='gauges':
        a.box((x,y,z),(0,0,0),DARK)
        for xx in (-x*.31,0,x*.31):
            a.ring(z*.30,z*.36,.018,(xx,-y*.52,0),STEEL,(0,-1,0),'bezel')
            a.cylinder(z*.30,.003,(xx,-y*.58,0),LIGHT,(0,-1,0),'dial')
            for t in np.linspace(-.75*np.pi,.75*np.pi,13):
                p=np.array([xx+z*.25*np.sin(t),-y*.61,z*.25*np.cos(t)])
                q=np.array([xx+z*.29*np.sin(t),-y*.61,z*.29*np.cos(t)])
                a.rod(p,q,.0009,DARK,'tick')
            a.rod((xx,-y*.63,0),(xx-z*.16,-y*.63,-z*.14),.0014,ORANGE,'needle')
    elif k=='cassette':
        a.box((x,y,z),(0,0,0),c,name='cassette')
        # Shallow side locks keep the source width below the receiver's .091 m
        # clear opening. The +Y alignment pins and mating frame are unchanged.
        for sign in (-1,1):
            a.box((.002,y*.45,z*.17),(sign*(x/2+.0005),-y*.17,z*.23),DARK,name='cassette_side_lock')
        a.box((x*.70,.003,z*.65),(0,-y*.52,0),LIGHT,name='inspection_window')
        for xx in (-x*.27,x*.27):a.cylinder(.005,.005,(xx,y/2+.001,0),STEEL,(0,1,0),'alignment_pin')
        a.label('TRAINING',(0,-y*.56,0),x*.76,z*.31)
    elif k=='cassette_slot':
        hollow_front(a,(x,y,z),.006,c)
        for xx in (-x*.30,x*.30):a.box((.004,y*.7,.004),(xx,0,-z*.35),STEEL,name='guide')
    elif k=='stopcock':
        a.cylinder(.009,.025,(0,0,0),STEEL,(0,-1,0),'rotor')
        a.box((x,.009,.014),(0,-y*.45,0),c,name='handle')
        a.box((.014,.009,z*.52),(0,-y*.45,z*.18),c,name='pointer')
    elif k=='training_bag':
        a.box((x,y,z*.89),(0,0,-z*.025),c,name='bag_body')
        a.box((x,.009,.016),(0,0,z*.45),LIGHT,name='welded_seal')
        a.ring(.006,.012,.005,(0,0,z*.51),LIGHT,(0,1,0),'hanger_eye')
        for xx in (-x*.23,x*.23):a.cylinder(.006,.025,(xx,0,-z*.49),LIGHT,name='sealed_port')
        text='TRAINING A' if obj.object_id=='BAG1' else 'TRAINING B'
        a.label(text+'\nSIMULATION ONLY',(0,y/2+.001,0),x*.86,z*.45,(0,1,0))
        a.label(obj.object_id,(0,-y/2-.001,0),x*.73,z*.23)
    else:
        raise ValueError(f'unknown geometry recipe {k}')
    return a


def table(a,center,size=(.90,.75),top=.03,height=.73,color=LIGHT):
    cx,cy=center;x,y=size
    a.box((x,y,.035),(cx,cy,top-.0175),color,name='worktop')
    for xx in (-x*.42,x*.42):
        for yy in (-y*.40,y*.40):
            a.box((.035,.035,height),(cx+xx,cy+yy,top-.035-height/2),DARK,metal=.55,name='table_leg')
    a.box((x*.90,.028,.025),(cx,cy+y*.40,top-height*.67),STEEL,name='cross_member')


def tube_path(a,points,radius,color=RUBBER):
    for start,end in zip(points,points[1:]):a.rod(start,end,radius,color)
    for point in points[1:-1]:a.sphere((radius,)*3,point,color)


def inlaid_work_surface(a,spec):
    """A 30 mm support datum with separate, nonoverlapping pads and grid inlays."""
    top,depth,length,center_y=.030,.003,.94,.12
    table(a,(0,center_y),(1.05,length),top=top-depth)
    mat=cq.Workplane('XY').box(1.02,length*.96,depth).edges().fillet(depth*.16)
    mat=mat.translate((0,center_y,top-depth/2))
    if spec.scene_id=='blocks':
        definitions=[('left_parts_tray',(.095,.055),(-.13,-.07),.012*.16),
                     ('right_parts_tray',(.095,.055),(.13,-.07),.012*.16)]
    elif spec.scene_id=='connector':
        definitions=[('receiver_fixture',(.19,.14),(-.10,.16),.006*.16)]
    elif spec.scene_id=='drone_bench':
        definitions=[('battery_pad',(.12,.17),(.34,-.25),.007*.16)]
    else:
        raise ValueError('No inlaid work surface contract for '+spec.scene_id)
    pads=[]
    for name,size,xy,radius in definitions:
        envelope=cq.Workplane('XY').box(*size,depth).edges('|Z').fillet(radius)
        envelope=envelope.translate((*xy,top-depth/2))
        pad=envelope
        if spec.scene_id=='drone_bench':
            bat=next(o for o in spec.objects if o.object_id=='BAT')
            x,y,z=bat.size_m
            orientation=rotation(bat.pose)
            if not np.allclose(orientation.as_matrix()[:,2],[0,0,1],atol=1e-12):
                raise ValueError('Battery support requires its declared upright pose')
            yaw=float(orientation.as_euler('xyz',degrees=True)[2])
            # These open-top pockets follow the actual rails and contact faces
            # in the declared starting pose, leaving the housing on the mat.
            for xx in (-x*.36,x*.36):
                cutter=cq.Workplane('XY').box(.008,y*.85,.004).translate((xx,0,-z/2))
                cutter=cutter.rotate((0,0,0),(0,0,1),yaw).translate(tuple(bat.pose.position_m))
                pad=pad.cut(cutter)
            for xx in np.linspace(-x*.28,x*.28,4):
                cutter=cq.Workplane('XY').box(.009,.015,.004)
                cutter=cutter.translate((float(xx),y*.30,-z/2-.0012+.002))
                cutter=cutter.rotate((0,0,0),(0,0,1),yaw).translate(tuple(bat.pose.position_m))
                pad=pad.cut(cutter)
        mat=mat.cut(envelope)
        pads.append((name,envelope,pad))
    lines=[]
    for index,xx in enumerate(np.linspace(-.48,.48,17)):
        line=cq.Workplane('XY').box(.0006,length*.91,.0004)
        line=line.translate((float(xx),center_y,top-.0002))
        for _,envelope,_ in pads:
            line=line.cut(envelope)
        mat=mat.cut(line)
        lines.append((f'mat_line_{index:02d}',line))
    a.add(cad_mesh(mat),(56,88,96),name='work_mat')
    for name,_,pad in pads:
        a.add(cad_mesh(pad),DARK,name=name)
    for name,line in lines:
        a.add(cad_mesh(line),(76,111,116),name=name)


def make_environment(spec: SceneSpec) -> Assembly:
    a=Assembly(spec.scene_id+'_environment')
    sid=spec.scene_id;objects={o.object_id:o for o in spec.objects}
    if sid in ('control_panel','connector','blocks','drone_bench','optical_bench'):
        length=1.5 if sid=='optical_bench' else .94
        center_y=.37 if sid=='optical_bench' else .12
        if sid in ('blocks','connector','drone_bench'):
            inlaid_work_surface(a,spec)
        else:
            table(a,(0,center_y),(1.05,length))
            a.box((1.02,length*.96,.003),(0,center_y,.0315),(56,88,96),name='work_mat')
            for xx in np.linspace(-.48,.48,17):a.box((.0006,length*.91,.0004),(xx,center_y,.0333),(76,111,116),name='mat_line')
        a.box((3,3,.035),(0,0,-.755),(165,176,184),name='floor')
    if sid=='control_panel':
        a.box((.41,.18,.025),(-.08,-.04,.0425),(117,137,153),name='instrument_panel')
        a.box((.145,.12,.015),(.18,.17,.0375),DARK,name='module_support')
        for oid in ('A','B'):
            p=np.asarray(objects[oid].pose.position_m)
            for t in np.linspace(0,2*np.pi,24,endpoint=False):
                a.rod(p+[.05*np.cos(t),.05*np.sin(t),-.015],p+[.056*np.cos(t),.056*np.sin(t),-.015],.0007,LIGHT,'dial_tick')
            a.label(oid,tuple(p+[0,-.067,-.013]),.027,.014,(0,0,1))
        a.label('HoloCue\nCONTROL WORKSTATION',(-.08,-.131,.044),.26,.045)
    elif sid=='connector':
        tube_path(a,[(.18,.19,.063),(.30,.26,.063),(.36,.25,.035),(.36,.42,.035)],.006)
        a.label('KEYED CONNECTOR',(0,-.255,.031),.35,.08,(0,0,1))
    elif sid=='blocks':
        a.label('CONSTRUCTION LAB',(0,-.27,.031),.40,.08,(0,0,1))
    elif sid=='drone_bench':
        body=cq.Workplane('XY').box(.19,.24,.09).edges().fillet(.008)
        opening=cq.Workplane('XY').box(.105,.153,.08).translate((0,0,.04))
        a.add(cad_mesh(body.cut(opening)),LIGHT,(0,.025,.090),name='airframe')
        a.box((.028,.040,.038),(.072,.025,.151),DARK,name='latch_support')
        for xx in (-.22,.22):
            for yy in (-.22,.22):
                a.rod((np.sign(xx)*.07,np.sign(yy)*.075,.096),(xx,yy,.099),.016,DARK,'arm')
                a.box((.05,.06,.014),(xx,yy,.087),STEEL,name='motor_mount')
        a.box((.24,.29,.016),(0,.025,.043),ORANGE,name='service_cradle')
        a.label('DRIVES DISCONNECTED',(0,-.32,.031),.40,.07,(0,0,1))
    elif sid=='optical_bench':
        a.box((.63,1.22,.022),(0,.36,.044),STEEL,name='breadboard')
        for xx in np.arange(-.28,.3,.035):
            for yy in np.arange(-.19,.96,.035):a.cylinder(.002,.001,(xx,yy,.0555),DARK,name='threaded_hole')
        for oid in ('L2','M'):
            o=objects[oid];px,py,pz=o.pose.position_m
            a.cylinder(.014,.050,(px,py,.079),STEEL,name='fixed_post')
            a.box((.09,.08,.012),(px,py,.061),DARK,name='post_base')
        a.box((.15,.13,.015),(.22,-.12,.058),DARK,name='optic_tray')
        a.cylinder(.012,.045,(-.31,.88,.058),STEEL,name='screen_post')
        a.label('OPTICAL ASSEMBLY\nSOURCE DISABLED',(.33,.45,.06),.20,.10,(0,0,1))
    elif sid=='server_rack':
        a.box((3,2.5,.06),(0,.2,-.03),(149,165,176),name='raised_floor')
        for xx in (-.28,.28):
            for yy in (-.045,.61):a.box((.035,.035,1.90),(xx,yy,.99),DARK,name='rack_post')
        for zz in (.05,1.93):a.box((.59,.70,.045),(0,.28,zz),DARK,name='rack_crossmember')
        a.box((.55,.025,1.8),(0,.64,.99),(81,100,116),name='rear_panel')
        for zz in (.25,.50,.75,1.42,1.68):
            a.box((.46,.52,.10),(0,.28,zz),(77,91,105),name='installed_module')
            for xx in np.linspace(-.19,.19,16):a.box((.007,.004,.05),(xx,.016,zz),DARK,name='vent')
        table(a,(-.72,-.22),(.55,.61),.88,.82)
        table(a,(.72,-.22),(.55,.61),.88,.82)
        a.label('RACK 04',(0,-.071,1.82),.29,.075)
    elif sid=='shelf_picking':
        a.box((3.6,3.3,.06),(.30,.55,-.03),(181,186,178),name='floor')
        for xx in (-.69,.01):
            for yy in (.01,.58):a.box((.033,.033,1.95),(xx,yy,.975),DARK,name='shelf_upright')
        for zz in (.28,.64,1.015,1.70):a.box((.74,.60,.03),(-.34,.295,zz),(163,171,174),name='shelf_deck')
        a.box((.70,.02,1.72),(-.34,.60,.95),(204,207,192),name='shelf_back')
        table(a,(-.25,-.62),(.49,.41),.81,.75)
        table(a,(.64,-.14),(.42,.40),.84,.78)
        table(a,(1.08,.70),(.44,1.05),.84,.78,DARK)
        for yy in np.linspace(.20,1.18,23):a.cylinder(.017,.40,(1.08,yy,.843),STEEL,(1,0,0),'roller')
        a.label('PICKING BAY 02',(-.34,-.011,1.49),.45,.14)
    elif sid=='dig_site':
        a.box((1.4,1.4,.06),(0,.20,-.38),(114,83,57),name='pit_floor')
        for zz,color in [(-.26,(133,99,67)),(-.14,(160,127,87)),(-.035,(174,145,103))]:
            height=.10
            for xx in (-.79,.79):a.box((.18,1.76,height),(xx,.20,zz),color,name='soil_layer')
            for yy in (-.59,.99):a.box((1.40,.18,height),(0,yy,zz),color,name='soil_layer')
        for xx in (-.80,.80):
            for yy in (-.6,1.0):a.cylinder(.015,.25,(xx,yy,.045),ORANGE,name='survey_stake')
        tube_path(a,[(-.80,-.60,.14),(.80,-.60,.14),(.80,1,.14),(-.80,1,.14),(-.80,-.60,.14)],.002,LIGHT)
        a.box((.35,.30,.03),(.85,-.46,.14),DARK,name='padded_recording_tray')
        a.box((.36,.52,.06),(-.85,-.22,0),(157,168,173),name='tool_tray')
        for t in (0,2*np.pi/3,4*np.pi/3):a.rod((.68,.98,.68),(.68+.26*np.cos(t),.98+.26*np.sin(t),.01),.018,ORANGE,'tripod_leg')
        a.label('RECORDED MATERIAL',(.85,-.613,.14),.30,.065)
    elif sid=='engine_bay':
        a.box((3,3,.06),(0,.25,-.03),(150,160,165),name='garage_floor')
        a.box((1.18,1.03,.25),(0,.20,.66),(51,79,106),name='engine_cradle')
        for xx in (-.62,.62):a.box((.14,1.13,.17),(xx,.19,.94),(42,98,136),name='fender')
        a.box((1.16,.14,.18),(0,-.40,.94),(42,98,136),name='front_crossmember')
        block=cq.Workplane('XY').box(.68,.49,.26).edges().fillet(.012)
        a.add(cad_mesh(block),STEEL,(0,.15,.84),metal=.45,rough=.62,name='engine_block')
        cover=cq.Workplane('XY').box(.54,.41,.09).edges().fillet(.015)
        cutter=cq.Workplane('XY').center(.16,.11).circle(.021).extrude(.30,both=True)
        a.add(cad_mesh(cover.cut(cutter)),DARK,(0,.15,1.04),rough=.62,name='cam_cover')
        for xx in (-.20,-.08,.04):
            a.cylinder(.022,.022,(xx,.26,1.095),DARK,name='coil_base')
            a.box((.058,.082,.029),(xx,.26,1.120),(63,71,75),name='ignition_coil')
            a.box((.028,.026,.017),(xx,.313,1.120),(74,84,90),name='coil_connector')
        for yy in np.linspace(.02,.32,8):
            a.box((.45,.008,.010),(-.035,yy,1.089),(70,80,89),name='cover_rib')
        for xx in (-.244,.244):
            for yy in (-.027,.07,.24,.326):
                a.cylinder(.006,.004,(xx,yy,1.088),STEEL,name='cover_fastener')
        for zz in np.linspace(.745,.91,6):
            a.box((.60,.014,.015),(0,-.098,zz),STEEL,name='casting_rib')
        for xx in (-.26,.26):
            a.cylinder(.018,.023,(xx,-.112,.82),BRASS,(0,-1,0),'core_plug')
        for yy in np.linspace(-.01,.30,4):
            tube_path(a,[(-.16,yy,1.00),(-.31,yy,1.04),(-.40,yy,.93)],.033,STEEL)
        tube_path(a,[(-.46,-.25,1.04),(-.32,-.12,1.06),(-.27,.06,1.03)],.052,DARK)
        a.ring(.051,.055,.023,(-.32,-.12,1.06),STEEL,(0,1,0),'clamp_band')
        a.box((.15,.13,.025),(.27,-.27,1.0075),DARK,name='sparkplug_tray')
        a.box((.12,.12,.05),(.44,-.15,.985),DARK,name='connector_rest')
        for yy in (.04,.24):a.cylinder(.073,.030,(.38,yy,.90),DARK,(1,0,0),'belt_pulley')
        tube_path(a,[(.401,.04,.975),(.401,.24,.975),(.401,.312,.90),(.401,.24,.826),(.401,.04,.826),(.401,-.033,.90),(.401,.04,.975)],.006,RUBBER)
        a.box((.13,.24,.16),(-.46,.41,.965),DARK,name='battery_case')
        a.box((.14,.25,.02),(-.46,.41,1.055),(69,83,90),name='battery_lid')
        for xx,col in [(-.502,(169,58,45)),(-.418,(48,52,56))]:
            a.cylinder(.012,.015,(xx,.35,1.073),col,name='battery_terminal')
        a.label('12 V',(-.46,.282,.99),.09,.06)
        for xx in np.linspace(-.48,.48,32):
            a.box((.008,.034,.11),(xx,-.36,.94),(96,112,120),name='radiator_fin')
        hood=rounded_box((1.21,.045,.91)).copy()
        hood.apply_transform(trimesh.transformations.rotation_matrix(-.25,[1,0,0]))
        a.add(hood,(42,98,136),(0,.76,1.49),metal=.45,name='open_hood')
        for xx in (-.46,0,.46):
            rib=rounded_box((.030,.035,.76)).copy()
            rib.apply_transform(trimesh.transformations.rotation_matrix(-.25,[1,0,0]))
            a.add(rib,(49,80,101),(xx,.729,1.49),name='hood_inner_rib')
        a.rod((-.51,.45,1),(-.51,.81,1.75),.010,STEEL,'hood_strut')
    elif sid=='cnc_toolchange':
        a.box((3,2.6,.06),(0,.30,-.03),(158,169,178),name='workshop_floor')
        table(a,(.05,-.05),(1.25,.74),.995,.92)
        a.box((.80,.30,.72),(.22,.79,1.18),(190,203,212),name='machine_column')
        for xx in (-.43,.88):
            a.box((.12,.94,1.18),(xx,.43,1.23),(190,203,212),name='machine_side_column')
        a.box((1.43,.94,.11),(.225,.43,1.875),(180,197,208),name='machine_header')
        a.box((1.43,.76,.08),(.225,.49,.60),(128,151,166),name='chip_tray')
        for zz in np.linspace(.66,1.65,20):
            a.box((.32,.018,.017),(.28,.615,zz),(108,130,146),name='way_cover_fold')
        a.box((.20,.25,.32),(.23,.60,1.62),(143,163,178),name='spindle_housing')
        a.cylinder(.063,.12,(.23,.55,1.40),STEEL,name='spindle_nose')
        for yy in np.linspace(.05,.43,7):
            a.box((.72,.012,.008),(.12,yy,1.008),DARK,name='table_t_slot')
        a.label('ISOLATED TRAINING CELL',(.225,-.045,1.875),.79,.056)
        a.box((.20,.18,.15),(.20,.25,1.005),DARK,name='tool_socket_support')
        a.box((.37,.15,.65),(-.55,.49,1.45),DARK,name='control_console')
        a.label('TEACHING FIXTURE',(0,-.425,.91),.52,.12)
        # Mount the magazine ahead of the way covers, with its hub connected
        # to the column front. Append to retain existing environment node IDs.
        a.cylinder(.03,.034,(.55,.623,1.47),axis=(0,1,0),name='magazine_mount_standoff')
    elif sid=='dive_fillstation':
        a.box((2.6,2.4,.06),(0,.26,-.03),(158,178,180),name='floor')
        a.box((1.05,.42,.12),(0,.07,.13),DARK,name='bottle_rack')
        for xx in (-.35,0,.35):
            a.ring(.093,.101,.024,(xx,.06,.44),STEEL,name='bottle_restraint')
            a.rod((xx,.16,.44),(xx,.37,.44),.012,STEEL,'restraint_bracket')
        a.box((1.10,.10,1.05),(0,.77,1.02),(124,151,166),name='manifold_panel')
        a.rod((-.42,.62,1.25),(.45,.62,1.25),.024,BRASS,'manifold')
        table(a,(.55,-.30),(.28,.25),.861,.80)
        tube_path(a,[(.34,.61,1.25),(.49,.53,1.05),(.62,.22,.58),(.70,.10,.72),(.67,.08,.90)],.012,RUBBER)
        a.cylinder(.017,.030,(.67,.08,.91),DARK,name='parked_hose_cap')
        a.rod((.67,.09,.88),(.67,.73,.88),.006,STEEL,'hose_storage_hook')
        a.label('DEPRESSURIZED\nTRAINING EQUIPMENT',(0,.712,.94),.70,.23)
    elif sid=='infusion_ward':
        a.box((2.6,2.6,.06),(0,.20,-.03),(186,199,203),name='training_room_floor')
        table(a,(-.45,-.22),(.50,.44),.95,.88)
        a.cylinder(.014,1.88,(.03,.49,.99),STEEL,name='iv_pole')
        for theta in np.linspace(0,2*np.pi,5,endpoint=False):
            end=(.03+.30*np.cos(theta),.49+.30*np.sin(theta),.075)
            a.rod((.03,.49,.13),end,.012,STEEL,'base_leg')
            a.cylinder(.032,.025,(end[0],end[1],.045),DARK,(1,0,0),'caster')
        a.rod((-.22,.49,1.945),(.25,.49,1.945),.007,STEEL,'hanger')
        for xx in (-.17,.22):tube_path(a,[(xx,.49,1.945),(xx,.40,1.945),(xx,.40,1.90)],.004,STEEL)
        a.box((.22,.11,.21),(.05,.30,1.30),LIGHT,name='pump_chassis')
        a.box((.13,.12,.09),(-.44,.62,1.27),DARK,name='monitor_support')
        a.rod((-.44,.62,1.27),(-.44,.62,.08),.015,STEEL,'monitor_stand')
        a.rod((.065,.17,1.01),(.135,.17,1.01),.007,LIGHT,'static_stopcock_body')
        a.label('TEACHING EQUIPMENT',(-.45,-.443,.88),.38,.10)
    else:
        raise ValueError(f'unknown workstation {sid}')
    return a
