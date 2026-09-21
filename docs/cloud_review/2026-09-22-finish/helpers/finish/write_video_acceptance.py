"""Materialize the root's explicit final video choices after visual review ends.

This does not infer visual quality. The listed decisions must be reviewed by the
root before running, and each selected movie must appear in the independent
reviewer's actual viewed-media inventory with the exact hash.
"""
import hashlib
import json
import os
from pathlib import Path

CHOICES = {
    'blocks': ('01', 'produced'),
    'cnc_toolchange': ('01', 'produced_attempt02'),
    'connector': ('02', 'produced'),
    'control_panel': ('01', 'produced'),
    'dig_site': ('01', 'produced'),
    'dive_fillstation': ('01', 'produced'),
    'drone_bench': ('01', 'produced'),
    'engine_bay': ('02', 'produced'),
    'infusion_ward': ('01', 'produced'),
    'optical_bench': ('01', 'produced'),
    'server_rack': ('01', 'produced'),
    'shelf_picking': ('01', 'produced'),
}

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    root=Path(os.environ['HOLOCUE_ROOT']).resolve()
    run=Path(os.environ['RUN_DIR']).resolve()
    if run != root/'runs/simulation/cloud_finish90_20260921_e67b574':
        raise ValueError('Explicit choices belong to RUN4 only')
    out=run/'VIDEO_ACCEPTANCE.json'
    if out.exists():
        raise FileExistsError(out)
    review=root/'.work/cloud_finish90_20260921/video_review_manifest.json'
    notes=review.with_name('visual_review.md')
    reviewed={item['relative_path']:item for item in json.loads(review.read_text())['videos']}
    accepted=[]
    for scene,(attempt,product) in CHOICES.items():
        folder=run/'videos'/f'{scene}_attempt{attempt}'/scene/product
        manifest=folder/'manifest.json'
        identity=json.loads(manifest.read_text())
        if identity['scene_id']!=scene:
            raise ValueError('Unexpected selected scene')
        for name in ('scene_introduction.mp4','workflow_realtime.mp4'):
            path=folder/name
            evidence=reviewed[str(path.relative_to(run))]
            if evidence['sha256']!=sha(path) or evidence['session_id']!=identity['session_id']:
                raise ValueError('Actual independent review identity differs')
        accepted.append({'scene_id':scene,'production_manifest':str(manifest.relative_to(root)),
            'production_manifest_sha256':sha(manifest),'session_id':identity['session_id'],
            'decision':'accepted',
            'reason':'Root accepted the independent representative-frame review; detailed viewing and geometry limits remain in visual_review.md.'})
    rejected_manifest=run/'videos/connector_attempt01/connector/produced/manifest.json'
    old=json.loads(rejected_manifest.read_text())
    rejected=[{'scene_id':'connector','production_manifest':str(rejected_manifest.relative_to(root)),
        'production_manifest_sha256':sha(rejected_manifest),'session_id':old['session_id'],
        'decision':'rejected','reason':'Functional workflow passed, but original page images and movie show persistent washed-out canvas; retain original evidence and use explicitly reviewed attempt02.'}]
    value={'schema_version':1,'accepted':accepted,'rejected':rejected,
        'decision_scope':'Video presentation only; functional assertions and native Blender coverage are reported separately.',
        'review_manifest':{'path':str(review.relative_to(root)),'sha256':sha(review)},
        'review_notes':{'path':str(notes.relative_to(root)),'sha256':sha(notes)}}
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'accepted':len(accepted),'rejected':len(rejected),'path':str(out),'sha256':sha(out)}))

if __name__=='__main__':
    main()
