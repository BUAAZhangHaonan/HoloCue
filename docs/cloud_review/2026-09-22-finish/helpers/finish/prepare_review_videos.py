"""Prepare full-duration ZIP review copies; preserve complete original media.

Run from the project with RUN4 phase_env.sh sourced. Explicit inputs only:
  python .work/cloud_finish90_20260921/prepare_review_videos.py \
    --original runs/simulation/.../raw_video/example.webm --attempt 01

Each encode, legacy verification and full-frame verification uses record.py.
An incomplete attempt is never reused. Use a new --attempt after inspecting it.
This changes only review encoding, never experiment settings or original media.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

LIMIT = 47 * 1048576


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def exclusive_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def identity(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def checked_path(value, root):
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    if '..' in path.parts or not path.is_relative_to(root):
        raise ValueError('Input must be a project path without parent traversal')
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Symlink evidence is not accepted: ' + str(path))
    return path


def record(root, run, label, command):
    for suffix in ('_command', '_resources.jsonl'):
        if (run / (label + suffix)).exists():
            raise FileExistsError('Recorded label already exists; use a new attempt: ' + label)
    subprocess.run([os.environ['APP_PYTHON'],
                    str(root / '.work/cloud_update_20260921/record.py'), label, *command],
                   cwd=root, check=True)
    execution = run / (label + '_command') / 'execution.json'
    if read(execution)['returncode'] != 0:
        raise RuntimeError('Recorder did not report success: ' + label)
    return execution


def verify_attempt(directory, root, run):
    """Called only inside its own record.py verification command."""
    request = read(directory / 'request.json')
    original = checked_path(request['original']['path'], root)
    copy = checked_path(request['copy'], root)
    if directory != copy.parent or identity(original) != request['original']:
        raise RuntimeError('Original changed or copy escaped its attempt')
    if not 0 < copy.stat().st_size < LIMIT:
        raise RuntimeError('Review copy must be nonempty and <47MiB; no parameter retry')
    legacy = read(directory / 'legacy_verification.json')
    if legacy.get('passed') is not True or legacy['original'] != identity(original) or legacy['copy'] != identity(copy):
        raise RuntimeError('Legacy dimension/fps/framecount/start/duration proof mismatch')
    for label in (request['encode_label'], request['legacy_label']):
        if read(run / (label + '_command') / 'execution.json')['returncode'] != 0:
            raise RuntimeError('A prerequisite recorded command failed')
    helper = checked_path(request['timing_helper']['path'], root)
    if digest(helper) != request['timing_helper']['sha256'] or digest(Path(__file__)) != request['preparation_script_sha256']:
        raise RuntimeError('Verification helper changed during this attempt')
    spec = importlib.util.spec_from_file_location('review_video_timing', helper)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Existing mature verifier records every decoded frame and rejects stderr.
    a, raw = module.decoded_probe(original, directory, 'original_decoded_frames')
    b, encoded = module.decoded_probe(copy, directory, 'copy_decoded_frames')
    timing = module.verify_frame_timing(a, raw, b, encoded)
    if abs(a[0] - b[0]) >= Decimal('.001'):
        raise AssertionError('Review encoding changed the absolute first frame PTS')
    # Detect any input/output mutation while full decoding was in progress.
    if identity(original) != request['original'] or identity(copy) != legacy['copy']:
        raise RuntimeError('Media changed during verification')
    evidence = [identity(path) for path in sorted(directory.iterdir())
                if path.is_file() and path != copy]
    result = {'passed': True,
        'scope': 'Complete ZIP review copy; original retained for full local delivery. '
                 'Original capture success/failure is unchanged; no native or workflow acceptance inferred.',
        'original': identity(original), 'copy': identity(copy),
        'original_probe': legacy['original_probe'], 'copy_probe': legacy['copy_probe'],
        'legacy_verification': str(directory / 'legacy_verification.json'),
        'legacy_verification_sha256': digest(directory / 'legacy_verification.json'),
        'decoded_original': raw, 'decoded_copy': encoded,
        'time_verification': timing, 'start_pts_equal_within_1ms': True,
        'width_height_fps_decoded_count_start_duration_verified': True,
        'copy_below_47MiB': True, 'encoding': {'crf': 23, 'threads': 4,
             'original_dimensions_and_fps': True, 'cuts': 0, 'speed': 1.0},
        'request': str(directory / 'request.json'),
        'request_sha256': digest(directory / 'request.json'),
        'command_record': str(run / (request['encode_label'] + '_command') / 'execution.json'),
        'legacy_verification_command_record': str(run / (request['legacy_label'] + '_command') / 'execution.json'),
        'verification_command_record': str(run / (request['verify_label'] + '_command') / 'execution.json'),
        'preparation_script_sha256': request['preparation_script_sha256'],
        'timing_helper': request['timing_helper']}
    result['verification_evidence_files'] = evidence
    exclusive_json(directory / 'proof.json', result)
    print(json.dumps({'passed': True, 'frames': len(a), 'bytes': copy.stat().st_size}))


def validate_existing(row, root):
    proof = read(checked_path(row['proof'], root))
    if (proof.get('passed') is not True or not proof['time_verification']['passed']
            or not proof['width_height_fps_decoded_count_start_duration_verified']):
        raise RuntimeError('Index references an incomplete verification')
    for key in ('original', 'copy'):
        path = checked_path(row[key], root)
        if identity(path) != proof[key]:
            raise RuntimeError('Indexed media changed: ' + str(path))
    if not 0 < proof['copy']['bytes'] < LIMIT:
        raise RuntimeError('Indexed review copy exceeds the size limit')
    for key in ('command_record', 'verification_command_record'):
        path = checked_path(row[key], root)
        if path != Path(proof[key]) or read(path)['returncode'] != 0:
            raise RuntimeError('Index lacks a matching completed recorded command')
    if read(checked_path(proof['legacy_verification_command_record'], root))['returncode'] != 0:
        raise RuntimeError('Indexed legacy verification command did not succeed')
    for expected in proof['verification_evidence_files']:
        if identity(checked_path(expected['path'], root)) != expected:
            raise RuntimeError('Indexed verification evidence changed or is missing')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', action='append', type=Path, help='Explicit original; repeat for several files')
    parser.add_argument('--attempt', default='01', help='Unique numeric attempt, default 01; never overwrite failures')
    parser.add_argument('--verify-attempt', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(os.environ['HOLOCUE_ROOT']).resolve()
    run = checked_path(os.environ['RUN_DIR'], root)
    if not run.is_relative_to(root / 'runs/simulation'):
        raise ValueError('RUN_DIR must be a project simulation run')
    if args.verify_attempt:
        directory = checked_path(args.verify_attempt, root)
        if directory.parent != run / 'review_videos':
            raise ValueError('Verifier attempt is outside this RUN review_videos')
        verify_attempt(directory, root, run)
        return
    if not args.original or not re.fullmatch(r'[0-9]{2,3}', args.attempt):
        parser.error('Provide one or more --original paths and a 2-3 digit --attempt')
    originals = [checked_path(path, root) for path in args.original]
    if len(set(originals)) != len(originals):
        raise ValueError('Duplicate originals')
    for path in originals:
        if not path.is_relative_to(run) or path.suffix.lower() not in {'.webm', '.mp4'} or not path.is_file():
            raise ValueError('Only existing original WebM/MP4 files within this RUN are accepted')
        if path.is_relative_to(run / 'review_videos'):
            raise ValueError('A review copy cannot be its own original')
    destination = run / 'review_videos'
    destination.mkdir(exist_ok=True)
    lock = destination / '.prepare.lock'
    # Linux advisory lock releases on interruption; incomplete attempt directories
    # remain and require a new attempt, without a stale global lock blocking it.
    import fcntl
    lock_stream = lock.open('a')
    try:
        fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_stream.close()
        raise RuntimeError('Another review-video preparation is active') from None
    try:
        index = destination / 'index.json'
        rows = read(index) if index.exists() else []
        if len({x['original'] for x in rows}) != len(rows):
            raise RuntimeError('Duplicate original entries in existing index')
        for row in rows:
            validate_existing(row, root)
        relative = lambda path: path.relative_to(root).as_posix()
        recorder = root / '.work/cloud_update_20260921/record.py'
        legacy = root / '.work/repair_review_20260920/verify_video.py'
        timing = root / '.work/cloud_video_20260921/produce_videos.py'
        for path in (recorder, legacy, timing):
            if not path.is_file():
                raise FileNotFoundError(path)
        for original in originals:
            previous = next((row for row in rows if row['original'] == relative(original)), None)
            if previous:
                validate_existing(previous, root)
                print(json.dumps({'reused_complete_verified_entry': previous['original']}), flush=True)
                continue
            tag = hashlib.sha256(relative(original).encode()).hexdigest()[:12]
            label = f'review_video_{tag}_a{args.attempt}'
            directory = destination / label
            labels = [label, label + '_legacy_verify', label + '_verify']
            if directory.exists() or any((run / (x + suffix)).exists() for x in labels
                                        for suffix in ('_command', '_resources.jsonl')):
                raise FileExistsError('Incomplete or used attempt exists; inspect it and choose a new --attempt')
            directory.mkdir()
            copy = directory / 'review.mp4'
            # Preserve actual helper bytes even if later attempts use a revision.
            helper_sources = {'preparation_script.py': Path(__file__).resolve(),
                              'timing_helper.py': timing, 'legacy_verify_video.py': legacy,
                              'record_helper.py': recorder}
            for name, path in helper_sources.items():
                shutil.copyfile(path, directory / name)
            request = {'original': identity(original), 'copy': str(copy), 'attempt': args.attempt,
                'encode_label': labels[0], 'legacy_label': labels[1], 'verify_label': labels[2],
                'preparation_script_sha256': digest(Path(__file__)),
                'timing_helper': identity(directory / 'timing_helper.py'),
                'legacy_verifier': identity(directory / 'legacy_verify_video.py'),
                'record_helper': identity(directory / 'record_helper.py'),
                'helper_original_paths': {name: str(path) for name, path in helper_sources.items()},
                'original_delivery': 'Complete original retained separately for local delivery'}
            exclusive_json(directory / 'request.json', request)
            command = ['ffmpeg', '-nostdin', '-n', '-threads', '4', '-copyts', '-i', str(original),
                '-map', '0', '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-threads', '4', '-c:a', 'copy', '-vsync', '0',
                '-enc_time_base', '-1', '-video_track_timescale', '1000000', '-movflags', '+faststart', str(copy)]
            encoded_record = record(root, run, labels[0], command)
            record(root, run, labels[1], [os.environ['APP_PYTHON'], str(directory / 'legacy_verify_video.py'),
                   str(original), str(copy), str(directory / 'legacy_verification.json')])
            verified_record = record(root, run, labels[2], [os.environ['APP_PYTHON'], str(directory / 'preparation_script.py'),
                                     '--verify-attempt', str(directory)])
            row = {'original': relative(original), 'copy': relative(copy),
                   'proof': relative(directory / 'proof.json'), 'command_record': relative(encoded_record),
                   'run_id': labels[0], 'verification_command_record': relative(verified_record)}
            validate_existing(row, root)
            rows.append(row)
            temporary = directory / 'index.next.json'
            exclusive_json(temporary, rows)
            os.replace(temporary, index)
        print(json.dumps({'verified_review_entries': len(rows), 'index': str(index)}))
    finally:
        fcntl.flock(lock_stream, fcntl.LOCK_UN)
        lock_stream.close()


if __name__ == '__main__':
    main()
