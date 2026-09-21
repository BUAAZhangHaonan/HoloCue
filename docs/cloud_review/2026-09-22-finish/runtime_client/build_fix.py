"""Recorded isolated Viser HDR opacity fix preparation; never deploys runtime files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(os.environ['HOLOCUE_ROOT']).resolve()
WORK = ROOT / '.work/viser_hdr_opacity_fix'
RUNTIME = ROOT / '.venv-simulation/lib/python3.12/site-packages/viser'
CLIENT = WORK / 'viser/client'
NODE_VERSION = '24.12.0'
NODE_HOME = WORK / 'toolchain' / ('node-v' + NODE_VERSION + '-linux-x64')
NODE = NODE_HOME / 'bin/node'
EXPECTED_TSX = 'ea854f80e057ccfbba238c645b051b1f0507c89d140e9e1902f0f6a31bf830e1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def save(name, value):
    with (WORK / name).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def environment():
    env = os.environ.copy()
    env['PATH'] = str(NODE_HOME / 'bin') + os.pathsep + env['PATH']
    env['npm_config_cache'] = str(WORK / 'cache/npm')
    env['npm_config_update_notifier'] = 'false'
    return env


def prepare():
    if CLIENT.exists():
        raise FileExistsError('Isolated client already exists; do not overwrite')
    if sha(RUNTIME / 'client/src/HDRJPGEnvironment.tsx') != EXPECTED_TSX:
        raise RuntimeError('Runtime HDR source differs from reviewed original')
    originals = {name: identity(RUNTIME / 'client' / name) for name in
                 ('src/HDRJPGEnvironment.tsx', 'package.json', 'package-lock.json', 'build/index.html')}
    save('original_identity.json', originals)
    shutil.copytree(RUNTIME / 'client', CLIENT)
    shutil.copytree(RUNTIME / '_assets', WORK / 'viser/_assets')
    (WORK / 'original').mkdir()
    shutil.copy2(RUNTIME / 'client/src/HDRJPGEnvironment.tsx', WORK / 'original/HDRJPGEnvironment.tsx')
    shutil.copy2(RUNTIME / 'client/package-lock.json', WORK / 'original/package-lock.json')
    shutil.copy2(RUNTIME / 'client/build/index.html', WORK / 'original/index.html')
    print(json.dumps({'isolated_client': str(CLIENT), 'original_identity': originals}))


def install_node():
    archive_name = f'node-v{NODE_VERSION}-linux-x64.tar.xz'
    downloads = WORK / 'cache/node'
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / archive_name
    sums = downloads / 'SHASUMS256.txt'
    if archive.exists() or sums.exists() or NODE_HOME.exists():
        raise FileExistsError('Node installation attempt exists; preserve for inspection')
    base = f'https://nodejs.org/dist/v{NODE_VERSION}/'
    for name, path in [('SHASUMS256.txt', sums), (archive_name, archive)]:
        with urllib.request.urlopen(base + name, timeout=120) as response, path.open('xb') as stream:
            shutil.copyfileobj(response, stream)
    expected = next(line.split()[0] for line in sums.read_text().splitlines()
                    if line.split()[-1] == archive_name)
    if sha(archive) != expected:
        raise RuntimeError('Official Node archive SHA256 mismatch')
    (WORK / 'toolchain').mkdir(exist_ok=True)
    with tarfile.open(archive) as stream:
        stream.extractall(WORK / 'toolchain', filter='data')
    node_version = subprocess.check_output([str(NODE), '--version'], text=True).strip()
    npm_version = subprocess.check_output([str(NODE_HOME / 'bin/npm'), '--version'], env=environment(), text=True).strip()
    if node_version != 'v' + NODE_VERSION:
        raise RuntimeError('Installed Node version mismatch')
    save('node_identity.json', {'node_version': node_version, 'npm_version': npm_version,
                              'official_archive': identity(archive), 'official_sums': identity(sums)})
    print(node_version, npm_version)


def install_dependencies():
    original = json.loads((WORK / 'original_identity.json').read_text())
    subprocess.run([str(NODE_HOME / 'bin/npm'), 'ci', '--no-audit', '--no-fund'],
                   cwd=CLIENT, env=environment(), check=True)
    if sha(CLIENT / 'package-lock.json') != original['package-lock.json']['sha256']:
        raise RuntimeError('npm ci changed the lockfile')
    save('dependency_identity.json', {'lock': identity(CLIENT / 'package-lock.json'),
                                    'node_modules_exists': (CLIENT / 'node_modules').is_dir()})


def test(label):
    result = subprocess.run([str(NODE), str(CLIENT / 'node_modules/vitest/vitest.mjs'), 'run',
        'src/HDRJPGEnvironment.opacity.test.ts', '--maxWorkers', '1', '--reporter=json',
        '--outputFile', str(WORK / (label + '.json'))], cwd=CLIENT, env=environment(), check=False)
    return result.returncode


def build():
    subprocess.run([str(NODE_HOME / 'bin/npm'), 'run', 'build', '--', '--base', './'],
                   cwd=CLIENT, env=environment(), check=True)
    original = json.loads((WORK / 'original_identity.json').read_text())
    for name, expected in original.items():
        if sha(RUNTIME / 'client' / name) != expected['sha256']:
            raise RuntimeError('Running installed client changed unexpectedly')
    if sha(CLIENT / 'package-lock.json') != original['package-lock.json']['sha256']:
        raise RuntimeError('Isolated lockfile changed')
    old_test = json.loads((WORK / 'regression_old_behavior.json').read_text())
    new_test = json.loads((WORK / 'regression_fixed_behavior.json').read_text())
    if old_test['numFailedTests'] != 1 or old_test['numPassedTests'] != 1 or old_test['success']:
        raise RuntimeError('Old-code regression did not fail exactly the opacity transition case')
    old_failures = [test for suite in old_test['testResults'] for test in suite['assertionResults']
                    if test['status'] == 'failed']
    if (len(old_failures) != 1 or
            old_failures[0]['title'] != 'restores opacity when a second texture loads after only one fade frame' or
            not any('expected 0.24 to be 1' in message for message in old_failures[0]['failureMessages'])):
        raise RuntimeError('Old failure did not establish the controlled 0.24 opacity defect')
    if new_test['numFailedTests'] != 0 or new_test['numPassedTests'] != 2 or not new_test['success']:
        raise RuntimeError('Fixed-code regression is not fully passing')
    save('build_identity.json', {'runtime_unchanged': True, 'original': original,
         'patched_source': identity(CLIENT / 'src/HDRJPGEnvironment.tsx'),
         'isolated_build': identity(CLIENT / 'build/index.html'),
         'lock': identity(CLIENT / 'package-lock.json'),
         'test': identity(CLIENT / 'src/HDRJPGEnvironment.opacity.test.ts'),
         'old_regression': identity(WORK / 'regression_old_behavior.json'),
         'fixed_regression': identity(WORK / 'regression_fixed_behavior.json'),
         'patch': identity(WORK / 'HDRJPGEnvironment.opacity.patch'),
         'scope': 'Isolated build only; running package and services unchanged. Browser runtime validation remains separate.'})
    print(json.dumps({'built': str(CLIENT / 'build/index.html'), 'sha256': sha(CLIENT / 'build/index.html'),
                      'runtime_unchanged': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'node', 'dependencies', 'test-old', 'test-fixed', 'build'))
    args = parser.parse_args()
    if float(os.environ.get('HOLOCUE_HOST_MAX_USED_FRACTION', '0')) != .90:
        raise ValueError('Keep the authorized 90% guard setting')
    if args.action.startswith('test-'):
        return test('regression_' + args.action.removeprefix('test-') + '_behavior')
    {'prepare': prepare, 'node': install_node, 'dependencies': install_dependencies, 'build': build}[args.action]()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
