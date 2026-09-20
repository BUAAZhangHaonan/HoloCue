"""Export a real API session into atomic, renderer-neutral Gaussian preview frames."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

import httpx
import numpy as np

from holocue.bridge import frame,atomic_json
from holocue.config import root,load_scene
from holocue.models import DisplayPacket
from holocue.spatial import ActionClock


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',required=True)
    parser.add_argument('--api',default='http://127.0.0.1:8750')
    parser.add_argument('--view-state',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=120.)
    parser.add_argument('--hz',type=float,default=10.)
    args=parser.parse_args()
    if not 1<=args.hz<=30 or args.seconds<=0:
        raise ValueError('invalid export duration or rate')
    headers={'Authorization':'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    clock=ActionClock();started=time.perf_counter();unmatched_since=None
    output=root()/'runs/simulation/bridge'/f'{args.session}.json'
    with httpx.Client(timeout=5.,headers=headers) as client:
        while time.perf_counter()-started<args.seconds:
            response=client.get(args.api+f'/api/v1/sessions/{args.session}/snapshot')
            response.raise_for_status();snapshot=response.json()
            if snapshot['state']['backend_mode']!='live':
                raise ValueError('live frame export requires a live model session')
            packet=DisplayPacket.model_validate(snapshot['display'])
            if packet.revision!=snapshot['state']['revision']:
                raise ValueError('snapshot revision mismatch')
            spec=load_scene(packet.scene_id)
            view=json.loads(args.view_state.read_text())
            if view['session_id']!=args.session:
                raise ValueError('view state belongs to another session')
            if time.time()-view['generated_at']>3:
                raise TimeoutError('operator camera state expired')
            if (view['revision'],view['epoch'])!=(packet.revision,packet.epoch):
                now=time.perf_counter()
                if unmatched_since is None:
                    unmatched_since=now
                if now-unmatched_since>3:
                    raise TimeoutError('operator view and API snapshot did not reach the same version')
                time.sleep(1/args.hz)
                continue
            unmatched_since=None
            position,look,focus,brightness=view['position_m'],view['look_at_m'],view['focus_m'],view['brightness']
            clock.elapsed=dict(view['elapsed_s'])
            data=frame(spec,packet,clock,0.,position,look,focus,brightness)
            data['view_mode']=view['view_mode'];data['selected_id']=view['selected_id']
            data['enabled']=view['enabled']
            data['camera']['up_direction']=view['up_direction']
            data['camera']['fov_rad']=view['fov_rad']
            data['camera']['aspect']=view['aspect']
            atomic_json(output,data)
            time.sleep(1/args.hz)


if __name__=='__main__':
    main()
