"""Illustrative focus-response storyboard. This is deliberately not a wave-optics solver."""
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

def response_panel(cues,focus:float,width:int=700,height:int=230):
    image=Image.new('RGB',(width,height),(245,248,251));draw=ImageDraw.Draw(image)
    draw.text((16,12),'DESIGN PREVIEW  /  NOT AN OPTICAL RECONSTRUCTION',fill=(71,87,105))
    if not cues:
        draw.text((16,90),'Submit a task to compare cue profiles.',fill=(91,103,120));return np.asarray(image)
    colwidth=width/max(len(cues),1)
    for i,c in enumerate(cues):
        xc=int((i+.5)*colwidth)
        layer=Image.new('RGBA',image.size)
        d=ImageDraw.Draw(layer)
        # Relative focus coordinates are illustrative, unrelated to physical scene metres.
        center=(i-(len(cues)-1)/2)*.5
        axial_width={'precise':.18,'persistent':.62,'neutral':1.0}[c.depth_requirement]
        blur=min(9.,abs(focus-center)/axial_width*1.4)
        y=105
        d.polygon([(xc-38,y-9),(xc+8,y-9),(xc+8,y-27),(xc+38,y),(xc+8,y+27),(xc+8,y+9),(xc-38,y+9)],fill=(79,145,164,230))
        layer=layer.filter(ImageFilter.GaussianBlur(blur))
        image.paste(layer,(0,0),layer)
        draw=ImageDraw.Draw(image)
        draw.text((xc-45,166),f'{c.target_id}  {c.task_role}',fill=(45,66,84))
        draw.text((xc-45,185),f'N={c.n_gaussians}  sigma={c.sigma_value:g}',fill=(70,88,102))
        draw.text((xc-45,204),c.sigma_profile,fill=(90,102,115))
    return np.asarray(image)
