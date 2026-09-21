"""Concatenate all twelve verified real-page scene introductions without re-encoding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from holocue.config import list_scenes

def acceptance_entries(path, root, scene_ids):
    """Explicit reviewed choices, bound to exact production bytes; never latest."""
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    def checked(value):
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        if ('..' in candidate.parts or not candidate.is_relative_to(root)
                or any(x.is_symlink() for x in [candidate, *candidate.parents])
                or not candidate.is_file()):
            raise ValueError('Invalid acceptance evidence path: ' + str(candidate))
        return candidate
    def hashed(candidate):
        with candidate.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    path = checked(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('VIDEO_ACCEPTANCE requires schema_version 1')
    accepted, rejected, seen = {}, {}, set()
    for group, decision in [('accepted', 'accepted'), ('rejected', 'rejected')]:
        for supplied in data[group]:
            row = dict(supplied)
            scene = row['scene_id']
            manifest = checked(row['production_manifest'])
            if (scene not in scene_ids or row['decision'] != decision
                    or not isinstance(row.get('reason'), str) or not row['reason'].strip()
                    or str(manifest) in seen):
                raise ValueError('Invalid or duplicate explicit visual decision')
            if hashed(manifest) != row['production_manifest_sha256']:
                raise ValueError('Accepted/rejected production manifest changed')
            product = json.loads(manifest.read_text(encoding='utf-8'))
            if product['scene_id'] != scene or product['session_id'] != row['session_id']:
                raise ValueError('Visual decision scene/session differs from production')
            row['production_manifest'] = str(manifest)
            seen.add(str(manifest))
            if decision == 'accepted':
                if scene in accepted:
                    raise ValueError('More than one accepted production for scene')
                accepted[scene] = row
            else:
                rejected[str(manifest)] = row
    if set(accepted) != set(scene_ids) or len(accepted) != 12:
        raise ValueError('Exactly twelve explicitly visually accepted scenes are required')
    return {'path': str(path), 'sha256': hashed(path), 'accepted': accepted, 'rejected': rejected}


def load_source_phases(root, run):
    """Read the explicit two-phase boundary without upgrading historical evidence."""
    def checked(value):
        path = Path(value)
        path = path if path.is_absolute() else root / path
        if ('..' in path.parts or not path.is_relative_to(root)
                or any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file()):
            raise ValueError('Unsafe phase snapshot path')
        return path
    manifest_path = checked(run / 'SOURCE_PHASES.json')
    manifest = read(manifest_path)
    if manifest.get('schema_version') != 1 or len(manifest['phases']) != 2:
        raise ValueError('Exactly two explicit source phases are required')
    phases = {}
    for phase in manifest['phases']:
        path = checked(phase['source_snapshot'])
        if digest(path) != phase['source_snapshot_sha256']:
            raise ValueError('Phase snapshot file hash mismatch')
        snapshot = read(path)
        source_digest = phase['source_digest']
        if snapshot['digest'] != source_digest or not snapshot['files'] or source_digest in phases:
            raise ValueError('Invalid or duplicate source phase snapshot')
        phases[source_digest] = {**phase, 'snapshot_path': path, 'snapshot': snapshot}
    if ({x['phase_id'] for x in phases.values()} != {'before_camera_atomic', 'camera_atomic'}
            or manifest['current_source_digest'] not in phases
            or phases[manifest['current_source_digest']]['phase_id'] != 'camera_atomic'):
        raise ValueError('Source phase boundary/current identity differs')
    old = next(x['snapshot'] for x in phases.values() if x['phase_id'] == 'before_camera_atomic')
    new = phases[manifest['current_source_digest']]['snapshot']
    old_files = {x['path']: x for x in old['files']}
    new_files = {x['path']: x for x in new['files']}
    changed = sorted(path for path in old_files.keys() | new_files.keys() if old_files.get(path) != new_files.get(path))
    if changed != manifest['changed_source_paths'] or changed != ['src/holocue/viewer_scene.py']:
        raise ValueError('Camera phase modifies more than the explicit viewer_scene boundary')
    previous = checked(manifest['previous_file'])
    expected = old_files[changed[0]]
    if digest(previous) != expected['sha256'] or previous.stat().st_size != expected['bytes']:
        raise ValueError('Preserved original camera source differs from the old snapshot')
    return manifest, phases

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--acceptance-manifest', type=Path)
args = parser.parse_args()
root = Path(os.environ['HOLOCUE_ROOT']).resolve()
run = Path(os.environ['RUN_DIR']).resolve()
acceptance = acceptance_entries(args.acceptance_manifest or run/'VIDEO_ACCEPTANCE.json', root, [row['scene_id'] for row in list_scenes()])
out = run/'videos'/'all_scenes_introduction'
read = lambda path: json.loads(path.read_text())

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def frame_count(path):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
               '-show_entries', 'stream=nb_read_frames,avg_frame_rate', '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    if result.stderr.strip():
        raise RuntimeError('Frame decoder reported an error')
    info = json.loads(result.stdout)['streams'][0]
    if info['avg_frame_rate'] != '25/1':
        raise RuntimeError('Introduction frame rate must remain 25 fps')
    return int(info['nb_read_frames'])

phase_manifest, source_phases = load_source_phases(root, run)
execution_source = phase_manifest['current_source_digest']
media_source = next(d for d, row in source_phases.items() if row['phase_id'] == 'before_camera_atomic')
phase_sha = digest(run / 'SOURCE_PHASES.json')
def verify_execution_source():
    if digest(run / 'SOURCE_PHASES.json') != phase_sha:
        raise RuntimeError('Source phase manifest changed during collection')
    for item in source_phases[execution_source]['snapshot']['files']:
        path = root / item['path']
        if ('..' in path.parts or not path.is_relative_to(root)
                or any(p.is_symlink() for p in [path, *path.parents])
                or digest(path) != item['sha256'] or path.stat().st_size != item['bytes']):
            raise RuntimeError('Collection execution source differs from its explicit current phase')
verify_execution_source()
commands = [(path, read(path)) for path in run.glob('*_command/execution.json')]
def actual_owner(script, flag, attempt, scene, media=None):
    matches = []
    for path, row in commands:
        argv = row['command']
        if not any(Path(x).name == script for x in argv) or flag not in argv:
            continue
        value = Path(argv[argv.index(flag)+1])
        value = value if value.is_absolute() else Path(row['cwd']) / value
        if value != attempt:
            continue
        if media is not None:
            media_name = argv[argv.index('--media-dir-name')+1] if '--media-dir-name' in argv else 'produced'
            if media_name != media:
                continue
        if '--scenes' in argv:
            names = []
            for token in argv[argv.index('--scenes')+1:]:
                if token.startswith('--'):
                    break
                names.append(token)
            if scene not in names:
                continue
        matches.append((path, row))
    if len(matches) != 1 or matches[0][1].get('returncode') != 0 or 'finished_at' not in matches[0][1]:
        raise RuntimeError('Accepted scene lacks unique successful capture/production execution')
    return matches[0]

sources = []
for scene in list_scenes():
    scene_id = scene['scene_id']
    candidates = [Path(acceptance['accepted'][scene_id]['production_manifest'])]
    manifest = read(candidates[0])
    if manifest['source_digest'] != media_source or manifest['asset_digest'] != phase_manifest['asset_digest']:
        raise RuntimeError('Accepted introduction media differs from the pre-camera source/assets phase')
    if manifest['scene_id'] != scene_id:
        raise RuntimeError(f'{scene_id}: production manifest scene identity differs')
    if not manifest['workflow_mp4']['frame_timing_verification']['passed']:
        raise RuntimeError(f'{scene_id}: workflow frame verification incomplete')
    directory = candidates[0].parent.parent
    attempt = directory.parent
    capture = read(directory / 'manifest.json')
    if capture.get('passed') is not True or capture['session_id'] != manifest['session_id']:
        raise RuntimeError('Accepted production is not a successful matching capture')
    capture_record, capture_execution = actual_owner('capture_ui_videos.py', '--out', attempt, scene_id)
    producer_record, producer_execution = actual_owner('produce_videos.py', '--capture-root', attempt, scene_id, candidates[0].parent.name)
    for execution in (capture_execution, producer_execution):
        if (execution['source_before']['digest'] != execution['source_after']['digest'] or execution['source_after']['digest'] != manifest['source_digest']
                or execution['assets_before']['digest'] != execution['assets_after']['digest'] or execution['assets_after']['digest'] != manifest['asset_digest']):
            raise RuntimeError('Accepted production execution source/assets differ')
    intro = manifest['introduction_mp4']
    path = Path(intro['path']).resolve(strict=True)
    if not path.is_relative_to(candidates[0].parent.resolve()) or digest(path) != intro['sha256']:
        raise RuntimeError(f'{scene_id}: introduction hash/path mismatch')
    sources.append({'scene_id': scene_id, 'path': str(path), 'sha256': intro['sha256'],
                    'source_digest': manifest['source_digest'], 'asset_digest': manifest['asset_digest'],
                    'duration_s': float(intro['probe']['format']['duration']),
                    'decoded_frames': frame_count(path),
                    'capture_command_record':str(capture_record), 'production_command_record':str(producer_record),
                    'production_manifest': str(candidates[0]),
                    'production_manifest_sha256': digest(candidates[0])})
if len(sources) != 12:
    raise RuntimeError('Expected exactly twelve scene introductions')
out.mkdir(exist_ok=False)
listing = out/'concat.txt'
listing.write_text(''.join("file '"+row['path']+"'\n" for row in sources))
movie = out/'twelve_scenes_introduction.mp4'
command = ['ffmpeg', '-nostdin', '-n', '-f', 'concat', '-safe', '0', '-i', str(listing),
           '-c', 'copy', '-movflags', '+faststart', str(movie)]
result = subprocess.run(command, capture_output=True, text=True, check=False)
save(out/'command.json', {'command': command, 'returncode': result.returncode})
(out/'stdout.log').write_text(result.stdout)
(out/'stderr.log').write_text(result.stderr)
if result.returncode:
    raise RuntimeError('Introduction concatenation failed')
probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(movie)],
                       capture_output=True, text=True, check=True)
info = json.loads(probe.stdout)
expected = sum(row['duration_s'] for row in sources)
actual = float(info['format']['duration'])
if abs(actual-expected) > .05:
    raise RuntimeError('Combined introduction duration differs from all source clips')
expected_frames = sum(row['decoded_frames'] for row in sources)
actual_frames = frame_count(movie)
if actual_frames != expected_frames:
    raise RuntimeError('Combined introduction lost or duplicated decoded frames')
verify_execution_source()
save(out/'manifest.json', {'passed': True, 'scope': 'Twelve scene introductions made from real initial Viser screenshots; slide video',
                          'source_digest': media_source, 'asset_digest': phase_manifest['asset_digest'],
                          'execution_source_digest': execution_source,
                          'source_phase_manifest': str(run / 'SOURCE_PHASES.json'), 'source_phase_manifest_sha256': phase_sha,
                          'acceptance_manifest':acceptance['path'], 'acceptance_manifest_sha256':acceptance['sha256'],
                          'sources': sources, 'video': str(movie), 'sha256': digest(movie),
                          'expected_duration_s': expected, 'actual_duration_s': actual, 'probe': info,
                          'decoded_input_frames': expected_frames, 'decoded_output_frames': actual_frames,
                          'outputs': [{'path': str(movie), 'sha256': digest(movie),
                            'command_record': str(run/'combine_introductions_command'/'execution.json'),
                            'sources': sources}]})
print(json.dumps({'scenes': len(sources), 'duration_s': actual, 'video': str(movie)}))
