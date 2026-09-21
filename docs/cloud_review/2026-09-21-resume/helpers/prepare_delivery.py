"""Consolidate sealed earlier evidence and the new resumed execution records."""
import copy
import hashlib
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path
root=Path(os.environ['HOLOCUE_ROOT']);run=Path(os.environ['RUN_DIR'])
prior=root/'runs/simulation/cloud_update_20260921_ce64aff5'
spec=importlib.util.spec_from_file_location('review_bundle',Path(os.environ['RECORD_KIT'])/'tools/review_bundle.py')
bundle=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bundle;spec.loader.exec_module(bundle)
bundle.ALLOWED.update({'.cjs','.diff'});bundle.TEXT.update({'.cjs','.diff'})
read=lambda path:json.loads(path.read_text())
relative=lambda path:path.relative_to(root).as_posix()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
source=bundle.source_snapshot(root);assets=bundle.asset_snapshot(root)
save(run/'source_final.json',source);save(run/'assets_final.json',assets)
source_paths={row['path'] for row in source['files']}
previous=read(prior/'review_selection.json')
archive_index=read(prior/'upload/UPLOAD_INDEX.json')
sealed_index=next(row for row in archive_index['archives'] if row['archive']=='00_review_index.zip')
sealed_zip=prior/'upload'/sealed_index['archive']
def sha256(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
if sealed_zip.stat().st_size!=sealed_index['bytes'] or sha256(sealed_zip)!=sealed_index['sha256']:
    raise RuntimeError('Previous sealed index archive no longer matches its published identity')
with zipfile.ZipFile(sealed_zip) as archive:
    sealed_manifest=json.loads(archive.read('HoloCue_Review/MANIFEST.json'))
sealed_files={row['source_path']:row for row in sealed_manifest['files']}
inherited_proof=[]
selection={'package_id':'HoloCue_Cloud_Resume_20260921','privacy_reviewed':False,'runs':[],'files':[],
    'note':'User-authorized resume after the previous resource stop. Earlier evidence keeps its original run/source/assets identities; read the new RUN FINAL_SUMMARY and COVERAGE first. Prior ZIPs remain sealed.'}
for row in previous['runs']:
    item=copy.deepcopy(row);item['run_id']='previous_'+row['run_id'];item['scope']='historical';item['status']='recorded'
    item['note']='Preserved earlier-batch record; original result and provenance remain in its command/report. '+item.get('note','')
    selection['runs'].append(item)
seen=set()
for row in previous['files']:
    item=copy.deepcopy(row);item['run_id']='previous_'+row['run_id']
    expected=sealed_files.get(item['path'])
    if expected is None:raise RuntimeError('Inherited evidence absent from sealed manifest: '+item['path'])
    path=bundle.safe_file(root,item['path'])
    if path.stat().st_size!=expected['bytes'] or sha256(path)!=expected['sha256']:
        raise RuntimeError('Inherited evidence changed since sealing: '+item['path'])
    inherited_proof.append({'path':item['path'],'sha256':expected['sha256'],'bytes':expected['bytes']})
    if item['path'] not in source_paths:selection['files'].append(item);seen.add(item['path'])
save(run/'inherited_evidence_verification.json',{'archive':relative(sealed_zip),'archive_sha256':sealed_index['sha256'],'passed':True,'files':inherited_proof})
commands={}
for directory in sorted(run.glob('*_command')):
    if directory.name.startswith('selection') or directory.name in {'export_command','verify_upload_command'}:continue
    path=directory/'execution.json'
    if not path.is_file():raise RuntimeError('Unfinished recorder: '+str(directory))
    record=read(path);name=directory.name.removesuffix('_command');commands[name]=record
    current=record['source_before']['digest']==record['source_after']['digest']==source['digest'] and record['assets_before']['digest']==record['assets_after']['digest']==assets['digest']
    selection['runs'].append({'run_id':name,'scope':'current' if current else 'historical',
        'status':('passed' if record['returncode']==0 else 'failed') if current else 'recorded',
        'command_record':relative(path),'report':relative(path),'source_digest':record['source_before']['digest'],
        'note':f"Actual return code {record['returncode']}; service exits must be read with the explicit shutdown record."})
    if name=='stopped_boundary_check':
        selection['runs'][-1]['note']='Expected negative boundary check: actual return code 1 refuses the already stopped model. No experiment started; the raw nonzero status is preserved.'
selection['runs'].append({'run_id':'delivery','scope':'historical','status':'recorded','note':'Current inventory, summaries, and review helpers; no experimental success inferred.'})
def add(path,owner='delivery',note='Original evidence; see the associated execution and its actual scope.'):
    rel=relative(path)
    if rel in seen or rel in source_paths or not path.is_file() or path.suffix.lower() not in bundle.ALLOWED:return
    bundle.safe_file(root,rel);bundle.scan_text(path);seen.add(rel)
    selection['files'].append({'path':rel,'run_id':owner,'group':'visuals' if path.suffix.lower() in {'.png','.jpg','.webm','.mp4'} else 'reports','note':note})
video_index=run/'review_videos/index.json';videos={row['original']:row for row in read(video_index)} if video_index.is_file() else {}
top_owner={'readiness.json':'readiness','service_shutdown.json':'shutdown','shutdown_gpu_ports.json':'shutdown',
    'owned_process_verification.json':'verify_cleanup','RESOURCE_STOP.json':'resource_stop'}
for path in sorted(run.rglob('*')):
    if not path.is_file():continue
    rel=path.relative_to(run)
    if rel.parts[0].startswith(('upload','selection')) or rel.parts[0] in {'export_command','verify_upload_command'}:continue
    if path.name in {'review_selection.json','state.sqlite','state.sqlite-wal','state.sqlite-shm'}:continue
    if any(part.startswith('frame_') and part.endswith('_passes') for part in rel.parts) and path.suffix=='.png':continue
    if 'frames' in rel.parts and path.name!='manifest.json':continue
    owner=rel.parts[0].removesuffix('_command')
    if len(rel.parts)==1:
        owner=top_owner.get(path.name,'delivery')
        for suffix in ('_resources.jsonl','_launcher.log','_repair_process.json','_process.json'):
            if path.name.endswith(suffix):owner=path.name.removesuffix(suffix);break
    if rel.parts[0]=='bridge_batches' and len(rel.parts)>1:owner='bridge_'+rel.parts[1]
    if rel.parts[0]=='changed_pairs' and len(rel.parts)>1:owner='pairs_'+rel.parts[1]
    if owner not in commands:owner='delivery'
    if path.suffix in {'.webm','.mp4'} and path.stat().st_size>=47*1048576:
        if relative(path) not in videos:raise RuntimeError('Large video needs a verified full-duration review copy: '+str(path))
        continue
    add(path,owner)
for row in videos.values():
    assert read(root/row['proof'])['passed']
    item=next(item for item in selection['files'] if item['path']==row['copy'])
    item.update(run_id=row['run_id'],derived_from=row['original'],derivation_command_record=row['command_record'],note='Full-duration verified review encoding; original identity and probe preserved.')
for path in (root/'.work/cloud_resume_20260921').iterdir():
    if path.is_file() and path.suffix in {'.py','.sh','.md','.json'}:add(path)
for name in ('FINAL_RECEIPT.json','provenance_archive_review.json','provenance_archive_review.md'):
    add(prior/name,'previous_delivery','Previous sealed-batch publication and archive-verification supplement.')
add(prior/'upload/UPLOAD_INDEX.json','previous_delivery');add(prior/'COVERAGE.json','previous_delivery')
def identity(name):
    if name not in commands:return {'run_id':name,'status':'not_run'}
    r=commands[name]
    return {'run_id':name,'command_record':relative(run/(name+'_command')/'execution.json'),'returncode':r['returncode'],
        'source_before':r['source_before']['digest'],'source_after':r['source_after']['digest'],
        'assets_before':r['assets_before']['digest'],'assets_after':r['assets_after']['digest']}
coverage={'source_digest':source['digest'],'asset_digest':assets['digest'],
    'previous_coverage':relative(prior/'COVERAGE.json'),'previous_archive_index':relative(prior/'upload/UPLOAD_INDEX.json'),
    'source_supplement':relative(prior/'source_supplement.json'),
    'scope':'Continuation only. Previous checks keep original execution identity; no source/asset historical result is relabeled as a fresh run.',
    'commands':{name:identity(name) for name in commands},'scenes':[]}
old=read(prior/'COVERAGE.json')
coverage['reused_checks']={key:old[key] for key in ('tests','geometry','native_builds')}
for previous_scene in old['scenes']:
    scene=previous_scene['scene_id'];native=run/'bridge_batches'/scene/'report.json';pairs=run/'changed_pairs'/scene/'report.json'
    coverage['scenes'].append({'scene_id':scene,'earlier_batch':previous_scene,
        'native_resume':{'execution':identity('bridge_'+scene),'report':read(native)} if native.is_file() else 'not_run',
        'targeted_pairs_resume':{'execution':identity('pairs_'+scene),'report':read(pairs)} if pairs.is_file() else 'not_run'})
if (run/'RESOURCE_STOP.json').is_file():coverage['resource_stop']=read(run/'RESOURCE_STOP.json')
save(run/'COVERAGE.json',coverage);add(run/'COVERAGE.json')
selection['privacy_reviewed']=True
save(run/'review_selection.json',selection)
print(json.dumps({'source_digest':source['digest'],'asset_digest':assets['digest'],'runs':len(selection['runs']),'files':len(selection['files'])}))
