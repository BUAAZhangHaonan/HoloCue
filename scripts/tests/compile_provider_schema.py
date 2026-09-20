"""Compile real provider JSON schemas with the installed model grammar engine."""
import argparse
import importlib.util
import json
from pathlib import Path

import xgrammar

from holocue.models import Session,Task,CueSemantic
from holocue.config import load_scene,list_scenes
from holocue.provider import decision_schema


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--provider-source',type=Path)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    schema_factory=decision_schema
    if args.provider_source:
        definition=importlib.util.spec_from_file_location('holocue.provider_candidate',args.provider_source)
        provider=importlib.util.module_from_spec(definition)
        definition.loader.exec_module(provider)
        schema_factory=provider.decision_schema
    task=Task(task_id='schema-domain',semantic=CueSemantic(target_id='B',action='rotate',
        angle_deg=30,cue_type='ring_arrow',task_role='current',priority=3,
        depth_requirement='precise',instruction='语义约束编译检查'))
    records=[]
    for item in list_scenes():
        scene=load_scene(item['scene_id'])
        for queue,suspended in ((False,False),(True,False),(True,True),(False,True)):
            state=Session(session_id='schema-domain',scene_id=scene.scene_id,backend_mode='domain_test',
                queue=[task] if queue else [],suspended=[[task]] if suspended else [],execution='planning')
            schema=schema_factory(state,scene)
            grammar=xgrammar.Grammar.from_json_schema(json.dumps(schema,ensure_ascii=False))
            name=f'{scene.scene_id}_queue_{int(queue)}_suspended_{int(suspended)}'
            (args.out/(name+'.json')).write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
            (args.out/(name+'.ebnf')).write_text(str(grammar),encoding='utf-8')
            records.append({'case':name,'compiled':True})
    (args.out/'report.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps(records))


if __name__=='__main__':
    main()
