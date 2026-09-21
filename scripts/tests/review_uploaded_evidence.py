"""Independently read uploaded native transforms, model records and test XML."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def matrix(pose):
    result=np.eye(4)
    result[:3,:3]=Rotation.from_quat(pose['wxyz'],scalar_first=True).as_matrix()
    result[:3,3]=pose['position_m']
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    suites=ET.parse(args.run/'pytest_results.xml').getroot().findall('testsuite')
    counts={key:sum(int(s.get(key,'0')) for s in suites)
            for key in ('tests','failures','errors','skipped')}
    assert counts=={'tests':431,'failures':0,'errors':0,'skipped':0},counts
    motions=read(args.run/'geometry.json')['results']
    assert len(motions)==18 and all(row['passed'] for row in motions)
    for row in motions:
        assert row['sampled_surface_points']==1536 and row['trajectory_samples']==41
        assert row['seed']==4701 and row['penetration_threshold_m']==.00075
        assert not row['penetrations']
    live=read(args.run/'live/report.json')
    assert len(live)==12 and sum(row['steps'] for row in live)==30
    for row in live:
        assert row['passed'] and row['backend_mode']=='live'
        first=read(args.run/'live'/row['scene_id']/'initial_snapshot.json')['state']
        final=read(args.run/'live'/row['scene_id']/'final.json')
        assert first['session_id']==final['session_id']==row['session_id']
        assert not final['queue'] and not final['suspended']
        assert first['backend_mode']==final['backend_mode']=='live'
    records=[]
    bridge=read(args.run/'bridge/report.json')
    for scene in bridge:
        assert scene['passed'] and not scene['browser_errors']
        for stage in scene['stages']:
            directory=args.run/'bridge'/scene['scene_id']/stage['stage']
            source=directory/'consumed_frame_0000.json'
            assert hashlib.sha256(source.read_bytes()).hexdigest()==stage['frame_sha256']
            consumed=read(source);native=read(directory/'frame_0000.json')
            snapshot=read(directory/'snapshot.json');view=read(directory/'view_state.json')
            for data in (consumed,native,snapshot['state'],snapshot['display'],view):
                assert data['session_id']==scene['session_id']
                assert data['revision']==stage['revision'] and data['epoch']==stage['epoch']
            assert consumed['object_poses']==snapshot['display']['object_poses']
            errors={key:float(np.max(np.abs(matrix(pose)-np.asarray(native['object_matrices'][key]))))
                    for key,pose in consumed['object_poses'].items()}
            assert max(errors.values())<1e-6,errors
            camera=consumed['camera']
            forward=np.asarray(camera['look_at_m'])-camera['position_m']
            forward/=np.linalg.norm(forward)
            right=np.cross(forward,camera['up_direction']);right/=np.linalg.norm(right)
            up=np.cross(right,forward)
            forward_error=float(np.max(np.abs(forward-native['camera_native_forward'])))
            up_error=float(np.max(np.abs(up-native['camera_native_up'])))
            assert max(forward_error,up_error)<1e-6
            assert abs(camera['fov_rad']-native['camera_fov_rad'])<1e-6
            images={}
            for filename in ('viser.png','frame_0000.png'):
                with Image.open(directory/filename) as image:
                    images[filename]=list(image.size)
                    image.verify()
            records.append({'scene_id':scene['scene_id'],'stage':stage['stage'],
                            'revision':stage['revision'],'epoch':stage['epoch'],
                            'max_matrix_difference':max(errors.values()),
                            'camera_forward_difference':forward_error,'camera_up_difference':up_error,
                            'images':images})
    assert len(records)==63
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps({'basis':'uploaded records and stored native readbacks',
        'reran_model_or_native_renderer':False,'pytest':counts,'motion_paths':len(motions),
        'live_scenes':len(live),'live_steps':sum(row['steps'] for row in live),
        'native_stages':records,'verified_png_files':2*len(records)},ensure_ascii=False,indent=2))
    print('Verified 431 recorded tests, 18 recorded paths, 12 live records and 63 native stages.')


if __name__=='__main__':
    main()
