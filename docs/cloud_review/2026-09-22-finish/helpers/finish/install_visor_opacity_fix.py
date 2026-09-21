"""Install the reviewed local Viser build only at a stopped-service boundary."""
import hashlib
import json
import os
from pathlib import Path
import time

from service_generation import require_closed_ports

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    root=Path(os.environ['HOLOCUE_ROOT']).resolve()
    run=Path(os.environ['RUN_DIR']).resolve()
    if run != root/'runs/simulation/cloud_finish90_20260921_e67b574':
        raise ValueError('Installer is restricted to the reviewed RUN4')
    fixed=root/'.work/viser_hdr_opacity_fix'
    runtime_client=root/'.venv-simulation/lib/python3.12/site-packages/viser/client'
    isolated_client=fixed/'viser/client'
    identity=json.loads((fixed/'build_identity.json').read_text())
    output=run/'viser_opacity_install.json'
    if output.exists():
        raise FileExistsError(output)
    require_closed_ports()
    for relative,old in identity['original'].items():
        if relative not in ('src/HDRJPGEnvironment.tsx','package.json','package-lock.json','build/index.html'):
            raise ValueError('Unexpected original file identity')
        path=Path(old['path']).resolve()
        if path != runtime_client/relative or digest(path)!=old['sha256']:
            raise ValueError('Original Viser file differs from reviewed build input: '+str(path))
    replacements=[('src/HDRJPGEnvironment.tsx','patched_source'),('build/index.html','isolated_build')]
    data=[]
    for relative,key in replacements:
        source=Path(identity[key]['path']).resolve()
        target=Path(identity['original'][relative]['path']).resolve()
        expected=identity[key]['sha256']
        if source != isolated_client/relative or target != runtime_client/relative:
            raise ValueError('Source or target is not the exact reviewed file')
        payload=source.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=expected:
            raise ValueError('Build artifact differs: '+str(source))
        backup=(fixed/'original'/target.name).resolve()
        if backup != fixed/'original'/target.name or digest(backup)!=identity['original'][relative]['sha256']:
            raise ValueError('Original byte backup missing or differs')
        pending=target.with_name(target.name+'.holocue-opacity-pending')
        if pending.exists():
            raise FileExistsError(pending)
        data.append((source,target,pending,relative,payload,expected))
    result={'started_at':time.time(),'identity_sha256':digest(fixed/'build_identity.json'),
            'scope':'Dependency client opacity fix; app source, model, scene assets and render parameters unchanged',
            'replacements':[]}
    for source,target,pending,relative,payload,expected in data:
        with pending.open('xb') as stream:
            stream.write(payload)
        pending.chmod(target.stat().st_mode)
        pending.replace(target)
        if digest(target)!=expected:
            raise AssertionError('Installed file hash differs')
        result['replacements'].append({'target':str(target),'source':str(source),
            'before_sha256':identity['original'][relative]['sha256'],'after_sha256':digest(target)})
    require_closed_ports()
    result['finished_at']=time.time()
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    main()
