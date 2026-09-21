"""Refuse another scene after any recorded service owner has stopped."""
import json
import os
from pathlib import Path

import psutil

run=Path(os.environ['RUN_DIR'])
for name in ('model','api','viewer'):
    execution=run/(name+'_command')/'execution.json'
    if execution.exists():
        raise SystemExit(f'Refusing next phase: {name} recorder already completed; inspect {execution}')
    identity=json.loads((run/(name+'_repair_process.json')).read_text())
    try:
        process=psutil.Process(identity['pid'])
        valid=process.create_time()==identity['create_time'] and process.status()!=psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        valid=False
    if not valid:raise SystemExit(f'Refusing next phase: {name} recorded owner is no longer alive')
print('Recorded service owners remain active at this scene boundary.')
