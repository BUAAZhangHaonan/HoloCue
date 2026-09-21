"""Run available test modules in isolated processes and retain actual reports."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from holocue.config import root


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--exclude',nargs='*',default=[])
    args=parser.parse_args()
    project=root()
    out=args.out.resolve()
    if not out.is_relative_to(project/'runs'):
        raise ValueError('Test evidence must be saved inside project runs')
    if not Path(os.environ['TMPDIR']).resolve().is_relative_to(project/'.work'):
        raise ValueError('TMPDIR must be inside project .work')
    out.mkdir(parents=True,exist_ok=True)
    work=project/'.work'/('pytest_'+out.name)
    work.mkdir(parents=True,exist_ok=True)
    available={p.name:p for p in sorted((project/'tests').glob('test_*.py'))}
    if not set(args.exclude).issubset(available):
        raise ValueError('Excluded test module does not exist')
    records=[]
    for name,path in available.items():
        if name in args.exclude:
            continue
        xml=out/(path.stem+'.xml')
        command=[sys.executable,'-S','-m','pytest','-q',str(path),
                 '--basetemp',str(work/path.stem),
                 '--junitxml',str(xml)]
        started=time.time()
        with (out/(path.stem+'.txt')).open('w') as stream:
            result=subprocess.run(command,cwd=project,env=os.environ.copy(),
                                  stdout=stream,stderr=subprocess.STDOUT)
        record={'module':name,'command':command,'returncode':result.returncode,
                'started_at':started,'finished_at':time.time()}
        if xml.is_file():
            document=ET.parse(xml)
            suites=document.getroot().findall('testsuite')
            record['counts']={key:sum(int(s.get(key,'0')) for s in suites)
                              for key in ('tests','failures','errors','skipped')}
        records.append(record)
        (out/'report.json').write_text(json.dumps({
            'execution':'one pytest process per test module',
            'excluded_modules':args.exclude,'results':records,
            'complete':len(records)+len(args.exclude)==len(available)
                       and result.returncode==0},indent=2))
        print(name,result.returncode,record.get('counts'),flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    totals={key:sum(r['counts'][key] for r in records)
            for key in ('tests','failures','errors','skipped')}
    print(json.dumps(totals),flush=True)


if __name__=='__main__':
    main()
