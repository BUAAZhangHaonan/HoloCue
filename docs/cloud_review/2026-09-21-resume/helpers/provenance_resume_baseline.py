import json,hashlib,importlib.util,sys,datetime,psutil
from pathlib import Path
root=Path('/home/hdd3/zhanghaonan/projects/holocue');run=root/'runs/simulation/cloud_resume_20260921_ea8c2f7';old=root/'runs/simulation/cloud_update_20260921_ce64aff5';kit=root/'.work/incoming/repair_review_20260920_25bcc909/HoloCue_Repair_Review_Kit'
out={'session':'/root/cloud_provenance_review','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_files':{}}
def j(p):
 data=p.read_bytes();out['read_files'][str(p.relative_to(root))]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)};return json.loads(data)
sp=importlib.util.spec_from_file_location('independent_resume',kit/'tools/review_bundle.py');m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
source=m.source_snapshot(root);assets=m.asset_snapshot(root)
oldsource=j(old/'source_final.json');oldassets=j(old/'assets_final.json')
out['current_source']=source;out['current_assets']=assets
out['comparison']={'source_digest_equal':source['digest']==oldsource['digest'],'source_files_equal':source['files']==oldsource['files'],'assets_digest_equal':assets['digest']==oldassets['digest'],'asset_files_equal':assets['files']==oldassets['files'],'scene_glbs':len([i for i in assets['files'] if i['path'].startswith('scenes/')]),'fixtures':len([i for i in assets['files'] if i['path'].startswith('tests/fixtures/')])}
out['readiness']=j(run/'readiness.json');out['commands']={}
for name in ['gpu_preflight','readiness','model','api','viewer']:
 dpath=run/(name+'_command');p=dpath/'execution.json'
 if not p.exists():p=dpath/'started.json'
 d=j(p);out['commands'][name]={k:d.get(k) for k in ['command','started_at','finished_at','returncode']}
 out['commands'][name].update(source_before=d['source_before']['digest'],source_after=d.get('source_after',{}).get('digest'),assets_before=d['assets_before']['digest'],complete_record=p.name=='execution.json')
out['process_trees']={}
keys=['HOLOCUE_ROOT','RUN_DIR','HOLOCUE_DB','HOLOCUE_DB_PATH','DATABASE_URL','STATE_DB','DB_PATH','CUDA_VISIBLE_DEVICES','GPUS','MODEL_PATH','MODEL_SIZE','GPU_FRACTION','HF_HOME','XDG_CACHE_HOME','TMPDIR','PYTHONPYCACHEPREFIX','TORCH_HOME']
for name in ['model','api','viewer']:
 owner=j(run/(name+'_repair_process.json'));rows=[]
 try:
  p=psutil.Process(owner['pid']);out['process_trees'][name]={'owner_pid':p.pid,'owner_create_time':p.create_time(),'owner_record_create_time':owner.get('create_time'),'processes':rows}
  for proc in [p]+p.children(recursive=True):
   try:
    env=proc.environ();selected={k:v for k,v in env.items() if k in keys or ('HOLOCUE' in k and ('DB' in k or 'STATE' in k))}
    rows.append({'pid':proc.pid,'cmdline':proc.cmdline(),'cwd':proc.cwd(),'environment':selected})
   except (psutil.NoSuchProcess,psutil.AccessDenied):pass
 except (psutil.NoSuchProcess,psutil.AccessDenied) as e:out['process_trees'][name]={'error':str(e)}
out['db']={'path':str(run/'state.sqlite'),'exists':(run/'state.sqlite').is_file(),'bytes':(run/'state.sqlite').stat().st_size,'distinct_from_old':(run/'state.sqlite').resolve()!=(old/'state.sqlite').resolve()}
print(json.dumps(out,ensure_ascii=False,indent=2))
