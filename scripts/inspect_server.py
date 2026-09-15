"""Read-only inventory. Does not install, download, launch a GPU job or modify other projects."""
import json,os,shutil,subprocess,platform
from pathlib import Path
import psutil

def command(args):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=12)
        return {'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    except Exception as e:return {'error':str(e)}
root=Path(__file__).resolve().parents[1]
vm=psutil.virtual_memory();disk=shutil.disk_usage(root)
report={'platform':platform.platform(),'project_root':str(root),'python':platform.python_version(),
        'memory_gib':{'total':vm.total/1024**3,'available':vm.available/1024**3},
        'disk_gib':{'free':disk.free/1024**3},'blender_in_path':shutil.which('blender'),
        'gpu_inventory':command(['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used','--format=csv']),
        'gpu_jobs':command(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv']),
        'tools':{x:shutil.which(x) for x in ['uv','python3.11','python3.12','blender','rsync','ssh','nvidia-smi']},
        'existing_project_model_dirs':[str(x) for x in (root/'models').glob('*')]}
if shutil.which('blender'):report['blender_version']=command(['blender','--version'])
p=root/'runs/server_inventory.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(p);print(json.dumps(report,ensure_ascii=False,indent=2))
