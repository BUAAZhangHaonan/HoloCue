"""Verify publication after archive sealing without rewriting the archives."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root=Path(os.environ['HOLOCUE_ROOT']);run=Path(os.environ['RUN_DIR'])
def read(path):return json.loads(path.read_text())
def git(*args):return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
head=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/master').split()[0]
assert head==remote and not git('status','--porcelain')
spec=importlib.util.spec_from_file_location('review_bundle',Path(os.environ['RECORD_KIT'])/'tools/review_bundle.py')
bundle=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bundle;spec.loader.exec_module(bundle)
source=bundle.source_snapshot(root);assets=bundle.asset_snapshot(root)
index=read(run/'upload/UPLOAD_INDEX.json');cleanup=read(run/'owned_process_verification.json')
assert source['digest']==index['source_digest']
assert assets['digest']==read(run/'assets_final.json')['digest']
assert all(row['bytes']<48*1048576 for row in index['archives'])
assert read(run/'verify_upload_command/execution.json')['returncode']==0
assert cleanup['passed'] and not cleanup['live_owned_identities']
result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'branch':git('branch','--show-current'),
    'head':head,'remote_head':remote,'worktree_clean':True,'source_digest':source['digest'],'asset_digest':assets['digest'],
    'commits_since_baseline':git('log','--format=%H %s','ea8c2f7838f7bf18fef6e5f64b83e641b5a0962e..HEAD').splitlines(),
    'archive_count':len(index['archives']),'archive_total_bytes':sum(row['bytes'] for row in index['archives']),
    'archive_max_bytes':max(row['bytes'] for row in index['archives']),'archive_project_files':index['total_files'],
    'upload_index_sha256':hashlib.sha256((run/'upload/UPLOAD_INDEX.json').read_bytes()).hexdigest(),
    'remote_upload_directory':str(run/'upload'),
    'local_upload_directory':'C:/Users/zhn19/Downloads/2/HoloCue_Cloud_Resume_20260921',
    'owned_process_identities_checked':len(cleanup['recorded_identities']),'live_owned_identities':cleanup['live_owned_identities'],
    'service_shutdown':read(run/'shutdown_gpu_ports.json'),'resource_stop':read(run/'RESOURCE_STOP.json'),
    'note':'This receipt records final documentation commits after ZIP sealing. Prior batch ZIPs and the new sealed ZIPs remain unchanged.'}
(run/'FINAL_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'head':head,'remote_head':remote,'worktree_clean':True,'archives':len(index['archives'])}))
