from __future__ import annotations
import json,os
from pathlib import Path
from .models import SceneSpec

def root()->Path:
    return Path(os.environ.get('HOLOCUE_ROOT',Path(__file__).resolve().parents[2])).resolve()

def load_scene(scene_id:str)->SceneSpec:
    if not scene_id.replace('_','').isalnum():raise ValueError('Invalid scene ID')
    p=root()/'configs'/'scenes'/f'{scene_id}.json'
    return SceneSpec.model_validate_json(p.read_text(encoding='utf-8'))

def list_scenes()->list[dict]:
    return [{'scene_id':s.scene_id,'title':s.title,'initial_instruction':s.initial_instruction}
            for s in (SceneSpec.model_validate_json(p.read_text())
                      for p in sorted((root()/'configs/scenes').glob('*.json')))]

def load_policy()->dict:
    return json.loads((root()/'configs/display_policy.json').read_text())
