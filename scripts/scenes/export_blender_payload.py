"""Export validated camera and scene data for Blender's bundled Python runtime."""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image

from holocue import camera
from holocue.assets import load_asset,resource
from holocue.bridge import atomic_json
from holocue.config import root,load_scene,list_scenes
from holocue.spatial import transform_points


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenes',nargs='*')
    args=parser.parse_args()
    for sid in args.scenes or [x['scene_id'] for x in list_scenes()]:
        spec=load_scene(sid)
        points=[]
        for obj in spec.objects:
            asset=load_asset(str(resource(root(),obj.asset)),spec.asset_axes)
            points.extend(transform_points(obj.pose,camera.corners(asset.bounds)))
        direction=np.asarray(spec.camera_position_m)-spec.camera_look_at_m
        pos,look=camera.fit(camera.workspace_points(spec,points),direction,aspect=1280/900)
        payload={'scene':spec.model_dump(),'camera':{'position_m':pos,'look_at_m':look},
                 'width':1280,'height':900}
        atomic_json(root()/'runs/simulation/blender_payloads'/f'{sid}.json',payload)
    y,x=np.mgrid[-3:3:128j,-3:3:128j]
    alpha=np.exp(-.5*(x*x+y*y))
    rgba=np.zeros((128,128,4),np.uint8);rgba[:,:,:3]=255;rgba[:,:,3]=np.round(alpha*255).astype(np.uint8)
    path=root()/'assets/ui/gaussian_sprite.png';path.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(rgba).save(path)


if __name__=='__main__':
    main()
