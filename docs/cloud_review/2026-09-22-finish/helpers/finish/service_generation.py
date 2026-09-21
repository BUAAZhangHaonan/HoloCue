"""Operate a separately recorded service generation without changing app settings.

Source the RUN4 phase_env.sh first. 'start' invokes the existing record.py per
service, with its existing resource guard; it is not an unguarded service launch.
Old generation files are never reused. No model/API/viewer parameters change.
"""
import argparse
import json
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx
import psutil

SERVICES = ('model', 'api', 'viewer')
PORTS = (8000, 8750, 8780)


def context(generation):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', generation):
        raise ValueError('Generation must be a short lowercase identifier')
    root = Path(os.environ['HOLOCUE_ROOT']).resolve()
    run = Path(os.environ['RUN_DIR']).resolve()
    if not run.is_relative_to(root / 'runs/simulation'):
        raise ValueError('RUN_DIR is outside project simulation runs')
    if float(os.environ.get('HOLOCUE_HOST_MAX_USED_FRACTION', '0')) != .90:
        raise ValueError('This authorized continuation requires the existing explicit 90% guard ceiling')
    return root, run


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def live_owner(record):
    try:
        process = psutil.Process(record['pid'])
        if process.create_time() != record['create_time'] or process.status() == psutil.STATUS_ZOMBIE:
            return None
        return process
    except psutil.NoSuchProcess:
        return None


def check_services(generation):
    _, run = context(generation)
    for service in SERVICES:
        name = service + '_' + generation
        execution = run / (name + '_command') / 'execution.json'
        if execution.exists():
            raise RuntimeError(f'Refusing next phase: {name} recorder already completed; inspect {execution}')
        path = run / (name + '_repair_process.json')
        record = json.loads(path.read_text())
        if live_owner(record) is None:
            raise RuntimeError(f'Refusing next phase: {name} recorded PID/create_time owner is no longer active')
    return True


def require_closed_ports():
    for port in PORTS:
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Port {port} is already owned; refusing to touch it')


def start(generation):
    root, run = context(generation)
    python = os.environ['APP_PYTHON']
    require_closed_ports()
    # Preflight the entire namespace before launching the first service.
    for service in SERVICES:
        name = service + '_' + generation
        for suffix in ('_command', '_launcher.log', '_repair_process.json', '_resources.jsonl'):
            if (run / (name + suffix)).exists():
                raise FileExistsError('Generation already has evidence: ' + str(run / (name + suffix)))
    for service in SERVICES:
        name = service + '_' + generation
        service_command = (['bash', 'scripts/ops/serve_model.sh'] if service == 'model'
                           else ['bash', 'scripts/run_simulation.sh', service])
        command = [python, str(root / '.work/cloud_update_20260921/record.py'), name, *service_command]
        environment = os.environ.copy()
        environment['HOLOCUE_RECORD_RSS_GB'] = '32' if service == 'model' else '8'
        with (run / (name + '_launcher.log')).open('x') as log:
            process = subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record = {'name': name + '_repair', 'generation': generation, 'service': service,
                  'pid': process.pid, 'create_time': psutil.Process(process.pid).create_time(),
                  'command': command, 'cwd': str(root), 'launched_at': time.time(),
                  'host_max_used_fraction': .90}
        with (run / (name + '_repair_process.json')).open('x') as stream:
            json.dump(record, stream, indent=2)
            stream.write('\n')
        print(json.dumps(record), flush=True)


def readiness(generation):
    _, run = context(generation)
    output = run / ('readiness_' + generation + '.json')
    if output.exists():
        raise FileExistsError('Readiness evidence already exists; preserve it: ' + str(output))
    checks = []
    headers = {'Authorization': 'Bearer ' + os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        check_services(generation)
        row = {'time': time.time(), 'generation': generation,
               'host_available_gib': psutil.virtual_memory().available / 1024**3, 'responses': {}}
        for name, url in [('model', 'http://127.0.0.1:8000/v1/models'),
                          ('api', 'http://127.0.0.1:8750/health'), ('viewer', 'http://127.0.0.1:8780/')]:
            try:
                response = httpx.get(url, headers=headers if name == 'api' else {}, timeout=10)
                row['responses'][name] = {'status': response.status_code}
                if name != 'viewer':
                    row['responses'][name]['body'] = response.text
            except httpx.HTTPError as error:
                row['responses'][name] = {'error': type(error).__name__}
        checks.append(row)
        save(output, checks)
        if all(value.get('status') == 200 for value in row['responses'].values()):
            check_services(generation)
            print('Recorded ' + generation + ' model/API/viewer ready; original settings retained.')
            return
        time.sleep(5)
    raise TimeoutError('Services did not become ready within ten minutes')


def stop(generation):
    _, run = context(generation)
    output = run / ('service_shutdown_' + generation + '.json')
    ports_output = run / ('shutdown_gpu_ports_' + generation + '.json')
    if output.exists() or ports_output.exists():
        raise FileExistsError('Shutdown evidence already exists; preserve this generation record')
    results = []
    for service, module in [('model', 'vllm.entrypoints.openai.api_server'),
                            ('viewer', 'holocue.viewer'), ('api', 'holocue.api')]:
        name = service + '_' + generation
        record = json.loads((run / (name + '_repair_process.json')).read_text())
        row = {'name': name, 'owner': record, 'requested_at': time.time(), 'signals': []}
        try:
            owner = psutil.Process(record['pid'])
            if owner.create_time() != record['create_time']:
                raise RuntimeError('PID was reused; refusing any signal: ' + name)
            children = []
            identities = {}
            for process in owner.children(recursive=True):
                try:
                    identities[process.pid] = process.create_time()
                    children.append(process)
                except psutil.NoSuchProcess:
                    continue
            row['owned_descendants'] = identities
            for process in children:
                try:
                    if process.create_time() != identities[process.pid]:
                        continue
                    if process.cmdline()[1:3] == ['-m', module]:
                        process.send_signal(signal.SIGINT)
                        row['signals'].append({'pid': process.pid, 'signal': 'SIGINT'})
                except psutil.NoSuchProcess:
                    continue
            psutil.wait_procs([owner], timeout=45)
            _, alive = psutil.wait_procs(children, timeout=5)
            for process in alive:
                try:
                    if process.create_time() == identities[process.pid] and process.status() != psutil.STATUS_ZOMBIE:
                        process.terminate()
                        row['signals'].append({'pid': process.pid, 'signal': 'SIGTERM'})
                except psutil.NoSuchProcess:
                    continue
            _, alive = psutil.wait_procs(alive, timeout=10)
            for process in alive:
                try:
                    if process.create_time() == identities[process.pid] and process.status() != psutil.STATUS_ZOMBIE:
                        process.kill()
                        row['signals'].append({'pid': process.pid, 'signal': 'SIGKILL'})
                except psutil.NoSuchProcess:
                    continue
            psutil.wait_procs(alive, timeout=5)
            row['remaining_owned_processes'] = []
            for process in children:
                try:
                    if (process.create_time() == identities[process.pid] and process.is_running()
                            and process.status() != psutil.STATUS_ZOMBIE):
                        row['remaining_owned_processes'].append(process.pid)
                except psutil.NoSuchProcess:
                    continue
            if row['remaining_owned_processes']:
                raise RuntimeError('Recorded descendants remain alive')
        except psutil.NoSuchProcess:
            row['owner_already_exited_before_children_snapshot'] = True
        row['finished_at'] = time.time()
        results.append(row)
        save(output, results)
    require_closed_ports()
    gpu_memory = subprocess.run(['nvidia-smi', '--query-gpu=index,uuid,memory.used', '--format=csv,noheader'],
                                check=True, capture_output=True, text=True).stdout
    save(ports_output, {'generation': generation, 'closed_ports': list(PORTS),
                        'gpu_memory': gpu_memory, 'checked_at': time.time()})
    print('Recorded ' + generation + ' services stopped; ports 8000/8750/8780 closed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'check', 'readiness', 'stop'))
    parser.add_argument('--generation', required=True)
    args = parser.parse_args()
    if args.action == 'check':
        check_services(args.generation)
        print('Recorded ' + args.generation + ' service owners remain active at this scene boundary.')
    else:
        {'start': start, 'readiness': readiness, 'stop': stop}[args.action](args.generation)


if __name__ == '__main__':
    main()
