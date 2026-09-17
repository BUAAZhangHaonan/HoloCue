"""Execute only an owned process tree, within explicitly allowed physical GPU indices.
Defaults are conservative project policy, not claimed server administrator thresholds.
"""
from __future__ import annotations
import argparse,csv,io,json,os,signal,subprocess,time,sys,fcntl
from pathlib import Path
import psutil
GIB=1024**3

def parse_selection(value):
    selected=[int(x.strip()) for x in value.split(',')] if value else []
    if len(selected)!=len(set(selected)) or not set(selected).issubset({1,2}):
        raise ValueError('Only physical GPUs 1 and 2 are authorized')
    return selected

def gpu_inventory():
    r=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True)
    return [{'index':int(x[0]),'uuid':x[1].strip(),'name':x[2].strip(),'total_mib':float(x[3]),'used_mib':float(x[4])} for x in csv.reader(io.StringIO(r.stdout))]

def gpu_jobs():
    r=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True)
    jobs=[]
    for row in csv.reader(io.StringIO(r.stdout)):
        if row:jobs.append({'uuid':row[0].strip(),'pid':int(row[1])})
    return jobs

def main():
    p=argparse.ArgumentParser();p.add_argument('--gpus',default='');p.add_argument('--host-reserve-gb',type=float,default=32)
    p.add_argument('--rss-limit-gb',type=float,default=32);p.add_argument('--gpu-fraction',type=float,default=.70)
    p.add_argument('--min-gpu-free-gb',type=float,default=12);p.add_argument('--log',default='runs/resource_guard.jsonl')
    p.add_argument('--execute',action='store_true');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    selected=parse_selection(a.gpus)
    if not 0<a.gpu_fraction<=.80:raise SystemExit('GPU allocation fraction must be in (0,0.80]')
    vm=psutil.virtual_memory();reserve=max(a.host_reserve_gb*GIB,.20*vm.total)
    if vm.available<reserve:raise SystemExit('Host available memory is below the reserve')
    if a.rss_limit_gb<=0 or a.rss_limit_gb*GIB>vm.total-reserve:raise SystemExit('Invalid process-tree RSS limit')
    devices=[d for d in gpu_inventory() if d['index'] in selected] if selected else []
    if len(devices)!=len(selected):raise SystemExit('Selected physical GPU does not exist')
    uuids=[d['uuid'] for d in sorted(devices,key=lambda d:selected.index(d['index']))]
    if selected:
        occupied=[x for x in gpu_jobs() if x['uuid'] in uuids]
        if occupied:raise SystemExit('Selected GPU already has compute jobs; do not kill them. '+json.dumps(occupied))
        for d in devices:
            free=(d['total_mib']-d['used_mib'])*1024**2
            if free<a.min_gpu_free_gb*GIB:raise SystemExit('Insufficient free GPU memory')
            if d['used_mib']+a.gpu_fraction*d['total_mib']>.90*d['total_mib']:
                raise SystemExit('Requested fraction would cross the GPU reserve')
    locks=[]
    for d in devices:
        lp=Path('runs/locks')/(d['uuid']+'.lock');lp.parent.mkdir(parents=True,exist_ok=True)
        f=lp.open('w');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
    command=a.command[1:] if a.command and a.command[0]=='--' else a.command
    info={'authorized_physical_gpus':selected,'cuda_visible_devices':uuids,'host_reserve_gib':reserve/GIB,'rss_limit_gib':a.rss_limit_gb,'command':command}
    print(json.dumps(info,ensure_ascii=False,indent=2))
    if not a.execute:return
    if not command:raise SystemExit('No command supplied')
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=','.join(uuids);env['CUDA_DEVICE_ORDER']='PCI_BUS_ID'
    env['OMP_NUM_THREADS']='4';env['MKL_NUM_THREADS']='4';env['OPENBLAS_NUM_THREADS']='4'
    proc=subprocess.Popen(command,env=env,start_new_session=True)
    log=Path(a.log);log.parent.mkdir(parents=True,exist_ok=True)
    reason=None
    try:
        while proc.poll() is None:
            time.sleep(1)
            vm=psutil.virtual_memory()
            try:
                parent=psutil.Process(proc.pid);tree=[parent]+parent.children(recursive=True)
                rss=sum(x.memory_info().rss for x in tree if x.is_running())
            except psutil.NoSuchProcess:rss=0
            gpus=[d for d in gpu_inventory() if d['uuid'] in uuids] if uuids else []
            rec={'time':time.time(),'pid':proc.pid,'rss_gib':rss/GIB,'host_available_gib':vm.available/GIB,'gpus':gpus}
            with log.open('a') as f:f.write(json.dumps(rec)+'\n')
            if vm.available<reserve:reason='host memory reserve reached'
            if rss>a.rss_limit_gb*GIB:reason='owned process-tree RSS limit reached'
            if any(d['used_mib']>.90*d['total_mib'] for d in gpus):reason='GPU memory reserve reached'
            if reason:break
    except KeyboardInterrupt:reason='user interruption'
    finally:
        if proc.poll() is None:
            # Never target names, unrelated PIDs, a whole user, or a GPU reset.
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    if reason:raise SystemExit('Stopped only owned process group: '+reason)
    raise SystemExit(proc.returncode)
if __name__=='__main__':main()
