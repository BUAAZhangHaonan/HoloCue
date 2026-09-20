from __future__ import annotations
import json,os
import hashlib
from functools import lru_cache
from pathlib import Path
from .models import SceneSpec

def root()->Path:
    return Path(os.environ.get('HOLOCUE_ROOT',Path(__file__).resolve().parents[2])).resolve()

def load_scene(scene_id:str)->SceneSpec:
    if not scene_id.replace('_','').isalnum():raise ValueError('Invalid scene ID')
    p=root()/'scenes'/scene_id/'scene.json'
    result=SceneSpec.model_validate(json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=unique_keys))
    if result.scene_id!=scene_id:
        raise ValueError('scene directory and scene_id differ')
    return result

def list_scenes()->list[dict]:
    return [{'scene_id':s.scene_id,'title':s.title,'initial_instruction':s.initial_instruction}
            for s in (load_scene(p.parent.name)
                      for p in sorted((root()/'scenes').glob('*/scene.json'))
                      if not p.parent.name.startswith('_'))]


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key}')
        result[key]=value
    return result

def load_policy()->dict:
    return json.loads((root()/'configs/display_policy.json').read_text())


@lru_cache(maxsize=512)
def _asset_digest(path: str,mtime_ns: int,size: int) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene_fingerprint(scene: SceneSpec) -> str:
    assets=[]
    for resource in [o.asset for o in scene.objects]+[p.asset for p in scene.environment]:
        path=(root()/resource).resolve()
        if not path.is_relative_to(root()):
            raise ValueError('scene asset is outside the project')
        stat=path.stat()
        assets.append((resource,_asset_digest(str(path),stat.st_mtime_ns,stat.st_size)))
    data={'scene':scene.model_dump(mode='json'),'assets':assets}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
