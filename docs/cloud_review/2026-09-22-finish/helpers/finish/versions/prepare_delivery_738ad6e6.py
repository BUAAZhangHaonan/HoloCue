"""Prepare RUN4 evidence selection after every service/experiment recorder has ended.

Run through record.py only after shutdown. This helper never runs an experiment.
RUN2 remains ZIP-sealed; RUN3 gets a write-once inventory in RUN4. UI videos are
separate evidence, not native acceptance. Oversized media abort selection.
"""
import argparse
import copy
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path, PureWindowsPath

SCENES = ('blocks', 'cnc_toolchange', 'connector', 'control_panel', 'dig_site',
          'dive_fillstation', 'drone_bench', 'engine_bay', 'infusion_ward',
          'optical_bench', 'server_rack', 'shelf_picking')
NATIVE_EIGHT = ('blocks', 'cnc_toolchange', 'connector', 'control_panel',
                'dig_site', 'dive_fillstation', 'drone_bench', 'infusion_ward')
FOCUS_FOUR = ('engine_bay', 'optical_bench', 'server_rack', 'shelf_picking')
MEDIA_LIMIT = 47 * 1048576
MEDIA = {'.webm', '.mp4'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def option(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


def scene_options(argv):
    if '--scenes' not in argv:
        return list(SCENES)
    result = []
    for token in argv[argv.index('--scenes') + 1:]:
        if token.startswith('--'):
            break
        result.append(token)
    if not result or len(result) != len(set(result)) or set(result) - set(SCENES):
        raise ValueError('Invalid recorded scene arguments: ' + repr(result))
    return result


def generation_output_owners(commands):
    """Bind generation files to recorded argv, independently of recorder labels."""
    owners = {}
    for name, record in commands.items():
        argv = record['command']
        positions = [i for i, token in enumerate(argv) if Path(token).name == 'service_generation.py']
        if not positions:
            continue
        action = argv[positions[0] + 1]
        generation = option(argv, '--generation')
        if generation is None:
            raise RuntimeError('Service generation command lacks its explicit generation')
        filenames = ([f'service_shutdown_{generation}.json', f'shutdown_gpu_ports_{generation}.json']
                     if action == 'stop' else [f'readiness_{generation}.json'] if action == 'readiness' else [])
        for filename in filenames:
            if filename in owners:
                raise RuntimeError('Generation output has multiple recorded command owners: ' + filename)
            owners[filename] = name
    return owners


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


def review_copy_visual_frames(root, run, directory, selected_paths, oversized_paths, verify_file):
    """Bind explicitly reviewed PNGs to selected media or verified local originals."""
    manifest = directory / 'review_copy_visual_manifest.json'
    frame_directory = directory / 'review_copy_inputs'
    actual = set(frame_directory.rglob('*.png')) if frame_directory.exists() else set()
    if not manifest.is_file():
        if actual:
            raise RuntimeError('Review-copy PNGs lack their explicit manifest')
        return []

    def checked(value, base):
        path = Path(value)
        if '..' in path.parts or '\\' in str(value):
            raise ValueError('Unsafe review-copy evidence path')
        path = path if path.is_absolute() else base / path
        path.relative_to(root)
        return path

    verify_file(manifest, sha256(manifest))
    review = read(manifest)
    pairs, expected = {}, set()
    for pair in review['media_pairs']:
        pair_id = pair['pair_id']
        times = pair['requested_times_s']
        if pair_id in pairs or not times or len(set(times)) != len(times):
            raise RuntimeError('Duplicate review-copy pair or sample time')
        for time in times:
            if isinstance(time, bool) or not isinstance(time, (int, float)) or not Decimal(str(time)).is_finite() or time < 0:
                raise RuntimeError('Invalid review-copy sample time')
            expected.update((pair_id, role, time) for role in ('original', 'copy'))
        media = {}
        for role in ('original', 'copy'):
            item = pair[role]
            path = checked(item['path'], root)
            if not path.is_relative_to(run) or path.suffix.lower() not in MEDIA:
                raise RuntimeError('Review-copy source escapes current run media')
            verify_file(path, item['sha256'], item['bytes'])
            rel = path.relative_to(root).as_posix()
            if rel not in selected_paths and not (role == 'original' and rel in oversized_paths):
                raise RuntimeError('Review-copy source is neither selected nor a verified local original')
            media[role] = (path, item['sha256'])
        if media['original'][0] == media['copy'][0]:
            raise RuntimeError('Review original and copy must be distinct media')
        pairs[pair_id] = media

    result, seen, paths = [], set(), set()
    for frame in review['frames']:
        key = (frame['pair_id'], frame['role'], frame['requested_time_s'])
        if key not in expected or key in seen or frame.get('viewed_extracted_frame') is not True:
            raise RuntimeError('Unexpected, duplicate or unviewed review-copy frame')
        path = checked(frame['local_relative_path'], directory)
        if not path.is_relative_to(frame_directory) or path.suffix.lower() != '.png' or path in paths:
            raise RuntimeError('Review-copy frame escapes its explicit PNG directory or is duplicated')
        video, digest = pairs[frame['pair_id']][frame['role']]
        if checked(frame['source_remote_path'], root) != video or frame['source_video_sha256'] != digest:
            raise RuntimeError('Review-copy frame source identity differs from its media pair')
        verify_file(path, frame['sha256'])
        seen.add(key)
        paths.add(path)
        result.append((path, video, frame['requested_time_s']))
    if seen != expected or paths != actual:
        raise RuntimeError('Review-copy PNG/sample set differs from its explicit manifest')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intro-collection-manifest', type=Path,
                        help='Optional manifest with outputs: path, sha256, command_record, '
                             'sources [{scene_id,path,sha256}]. Must cover exactly 12 intros.')
    parser.add_argument('--local-video-inventory', type=Path,
                        help='Unmodified VIDEO_FILES.json copied from completed local original-media delivery')
    parser.add_argument('--acceptance-manifest', type=Path, help='Explicit twelve-scene visual acceptance manifest')
    args = parser.parse_args()
    root = Path(os.environ['HOLOCUE_ROOT']).resolve()
    run = Path(os.environ['RUN_DIR'])
    run = (root / run).resolve() if not run.is_absolute() else run.resolve()
    acceptance = acceptance_entries(args.acceptance_manifest or run / 'VIDEO_ACCEPTANCE.json', root, SCENES)
    prior = root / 'runs/simulation/cloud_continue90_20260921_6815e62'
    sealed = root / 'runs/simulation/cloud_resume_20260921_ea8c2f7'
    if run == prior or not run.is_relative_to(root / 'runs/simulation'):
        raise ValueError('RUN_DIR must be a new project simulation run')
    spec = importlib.util.spec_from_file_location(
        'review_bundle', Path(os.environ['RECORD_KIT']) / 'tools/review_bundle.py')
    bundle = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bundle
    spec.loader.exec_module(bundle)
    bundle.ALLOWED.update({'.cjs', '.diff', '.ts', '.tsx'})
    bundle.TEXT.update({'.cjs', '.diff', '.ts', '.tsx'})

    def relative(path):
        return path.relative_to(root).as_posix()

    def absolute(value, cwd=root):
        path = Path(value)
        path = path if path.is_absolute() else cwd / path
        # safe_file below rejects symlink inputs; do not erase them by resolving.
        if '..' in path.parts:
            raise ValueError('Parent traversal in recorded path: ' + str(path))
        path.relative_to(root)
        return path

    def fingerprint(path):
        rel = relative(path)
        bundle.safe_file(root, rel)
        return {'path': rel, 'bytes': path.stat().st_size, 'sha256': sha256(path)}

    def verify_file(path, digest, size=None):
        row = fingerprint(path)
        if row['sha256'] != digest or (size is not None and row['bytes'] != size):
            raise RuntimeError('Evidence identity changed: ' + row['path'])
        return row

    # Fail before writing anything if an active recorder exists. The recorder of
    # this selection/export is excluded because its execution finishes afterwards.
    ignored_commands = {'export_command', 'verify_upload_command'}
    commands = {}
    for directory in sorted(run.glob('*_command')):
        if directory.name.startswith('selection') or directory.name in ignored_commands:
            continue
        path = directory / 'execution.json'
        if not path.is_file():
            raise RuntimeError('Unfinished recorder; do not select live evidence: ' + str(directory))
        commands[directory.name.removesuffix('_command')] = read(path)
    generation_owners = generation_output_owners(commands)
    for service in ('model', 'api', 'viewer'):
        if service not in commands:
            raise RuntimeError('Missing ended service recorder: ' + service)

    source, assets = bundle.source_snapshot(root), bundle.asset_snapshot(root)
    source_paths = {row['path'] for row in source['files']}
    for name, record in commands.items():
        if not (record['source_before']['digest'] == record['source_after']['digest'] == source['digest']
                and record['assets_before']['digest'] == record['assets_after']['digest'] == assets['digest']):
            raise RuntimeError('RUN4 command does not match current source/assets: ' + name)
        if 'finished_at' not in record or 'returncode' not in record:
            raise RuntimeError('Incomplete execution record: ' + name)

    previous = read(prior / 'review_selection.json')
    old_coverage = read(prior / 'COVERAGE.json')
    if {x['scene_id'] for x in old_coverage['scenes']} != set(SCENES):
        raise ValueError('Prior coverage does not contain exactly the required 12 scenes')
    archive_index = read(sealed / 'upload/UPLOAD_INDEX.json')
    published = next(x for x in archive_index['archives'] if x['archive'] == '00_review_index.zip')
    archive = sealed / 'upload' / published['archive']
    if archive.stat().st_size != published['bytes'] or sha256(archive) != published['sha256']:
        raise RuntimeError('RUN2 published index ZIP identity changed')
    with zipfile.ZipFile(archive) as stream:
        sealed_manifest = json.loads(stream.read('HoloCue_Review/MANIFEST.json'))
    sealed_files = {x['source_path']: x for x in sealed_manifest['files']}
    # Retain the exact RUN2 seal chain, including its prior verification list.
    inherited = read(prior / 'inherited_evidence_verification.json')
    if inherited['archive_sha256'] != published['sha256'] or not inherited['passed']:
        raise RuntimeError('RUN3 inherited verification does not match RUN2 seal')
    sealed_verified = []
    for row in inherited['files']:
        expected = sealed_files[row['path']]
        if row['sha256'] != expected['sha256'] or row['bytes'] != expected['bytes']:
            raise RuntimeError('RUN3 seal reference changed: ' + row['path'])
        sealed_verified.append(verify_file(root / row['path'], expected['sha256'], expected['bytes']))

    # RUN3 is not described as sealed. Freeze exact bytes of its selection,
    # coverage and evidence not already covered by the RUN2 ZIP manifest.
    prior_paths = {row['path'] for row in previous['files']}
    prior_paths.update(relative(prior / name) for name in
                       ('review_selection.json', 'COVERAGE.json', 'cleanup_direct_execution.json',
                        'verify_cleanup_direct_stdout.log', 'verify_cleanup_direct_stderr.log'))
    frozen_rows = []
    for rel in sorted(prior_paths):
        path = root / rel
        if rel in sealed_files:
            verify_file(path, sealed_files[rel]['sha256'], sealed_files[rel]['bytes'])
        else:
            frozen_rows.append(fingerprint(path))
    inventory = {'scope': 'RUN3 unsealed bytes frozen for RUN4 inheritance; RUN2 retains its separate ZIP seal',
                 'prior_run': relative(prior), 'run2_index_zip': relative(archive),
                 'run2_index_zip_sha256': published['sha256'],
                 'selection': fingerprint(prior / 'review_selection.json'),
                 'coverage': fingerprint(prior / 'COVERAGE.json'), 'files': frozen_rows}
    frozen_path = run / 'run3_frozen_inventory.json'
    if frozen_path.exists():
        if read(frozen_path) != inventory:
            raise RuntimeError('RUN3 frozen inventory changed; never overwrite its baseline')
    else:
        # Exclusive creation avoids replacing a baseline from another invocation.
        with frozen_path.open('x', encoding='utf-8') as stream:
            json.dump(inventory, stream, ensure_ascii=False, indent=2)
            stream.write('\n')

    selection = {'package_id': 'HoloCue_Cloud_Finish90_20260921', 'privacy_reviewed': False,
                 'runs': [], 'files': [],
                 'note': 'RUN4 final continuation; preserve phase-specific failures and identities. '
                         'Eight native targets plus four historical focus results; UI video coverage is separate. '
                         'RUN2 ZIP-sealed, RUN3 write-once inventory, RUN4 current commands strictly matched.'}
    for row in previous['runs']:
        item = copy.deepcopy(row)
        item.update(run_id='r3_' + row['run_id'], scope='historical', status='recorded')
        item['note'] = 'Inherited without upgrading its original result/source phase. ' + item.get('note', '')
        selection['runs'].append(item)
    cleanup = read(prior / 'cleanup_direct_execution.json')
    if not isinstance(cleanup, list) or not cleanup or any(x['returncode'] != 0 for x in cleanup):
        raise RuntimeError('RUN3 direct cleanup evidence differs from recorded rc0 array')
    selection['runs'].append({'run_id': 'r3_direct_cleanup', 'scope': 'historical', 'status': 'recorded',
        'command_record': relative(prior / 'cleanup_direct_execution.json'),
        'report': relative(prior / 'owned_process_verification.json'),
        'note': 'Direct recorded-owner safety cleanup rc0 after guarded shutdown precheck rc1. '
                'No experiment was launched; this is not the failed shutdown command.'})
    for name, record in commands.items():
        path = relative(run / (name + '_command') / 'execution.json')
        selection['runs'].append({'run_id': name, 'scope': 'current',
            'status': 'passed' if record['returncode'] == 0 else 'failed',
            'command_record': path, 'report': path, 'source_digest': source['digest'],
            'note': f"Actual return code {record['returncode']}. UI capture/production is UI-only; "
                    'service exit must be interpreted with shutdown/guard evidence.'})
    selection['runs'].append({'run_id': 'delivery', 'scope': 'historical', 'status': 'recorded',
                             'note': 'Inventories, summaries and tools; no experimental success inferred.'})
    rows = {}
    review_copies = {}
    oversized_originals = {}
    review_index = run / 'review_videos/index.json'
    local_inventory_path = absolute(args.local_video_inventory) if args.local_video_inventory else None
    local_inventory = read(local_inventory_path) if local_inventory_path else None
    if local_inventory is not None and (local_inventory.get('passed') is not True
            or local_inventory['source_digest'] != source['digest'] or local_inventory['asset_digest'] != assets['digest']):
        raise RuntimeError('Local original-media delivery inventory is incomplete or has different identities')
    by_command_record = {relative(run / (name + '_command') / 'execution.json'): name for name in commands}

    def successful_record(value):
        rel = relative(absolute(value))
        name = by_command_record.get(rel)
        if name is None or commands[name]['returncode'] != 0:
            raise RuntimeError('Review copy prerequisite lacks successful current execution: ' + rel)
        return name

    if review_index.is_file():
        for entry in read(review_index):
            original, copy_path, proof_path = (absolute(entry[key]) for key in ('original', 'copy', 'proof'))
            if relative(original) in review_copies:
                raise RuntimeError('Duplicate review-copy original')
            if not original.is_relative_to(run) or not copy_path.is_relative_to(run / 'review_videos'):
                raise RuntimeError('Review copy/original outside this run')
            proof = read(proof_path)
            evidence_files = proof.get('verification_evidence_files', [])
            if not evidence_files:
                raise RuntimeError('Review proof lacks hashed verification evidence')
            for evidence in evidence_files:
                evidence_path = absolute(evidence['path'])
                if evidence_path.parent != proof_path.parent:
                    raise RuntimeError('Review evidence escaped its attempt directory')
                verify_file(evidence_path, evidence['sha256'], evidence['bytes'])
            hashed_evidence = {absolute(item['path']) for item in evidence_files}
            required_evidence = {absolute(proof['request']), absolute(proof['legacy_verification']),
                                 absolute(proof['decoded_original']['full_frame_record']),
                                 absolute(proof['decoded_copy']['full_frame_record']),
                                 absolute(proof['timing_helper']['path'])}
            if not required_evidence.issubset(hashed_evidence):
                raise RuntimeError('Review proof omits hashes for required verification inputs/results')
            for key, path in [('original', original), ('copy', copy_path)]:
                expected = proof[key]
                if absolute(expected['path']) != path:
                    raise RuntimeError('Review proof path differs from index')
                verify_file(path, expected['sha256'], expected['bytes'])
            flags = ('passed', 'width_height_fps_decoded_count_start_duration_verified',
                     'start_pts_equal_within_1ms', 'copy_below_47MiB')
            if not all(proof.get(key) is True for key in flags) or not 0 < proof['copy']['bytes'] < MEDIA_LIMIT:
                raise RuntimeError('Incomplete or oversized review copy proof')
            if proof['encoding']['cuts'] != 0 or proof['encoding']['speed'] != 1:
                raise RuntimeError('Review copy changed timing/cuts')
            timing = proof['time_verification']
            if not all(timing.get(key) is True for key in ('passed', 'exact_decoded_frame_count_match',
                                                         'all_normalized_frame_timestamps_checked')):
                raise RuntimeError('Review copy lacks full-frame timing verification')
            encoder = successful_record(entry['command_record'])
            verifier = successful_record(entry['verification_command_record'])
            legacy_verifier = successful_record(proof['legacy_verification_command_record'])
            if (entry['run_id'] != encoder or absolute(proof['command_record']) != absolute(entry['command_record'])
                    or absolute(proof['verification_command_record']) != absolute(entry['verification_command_record'])):
                raise RuntimeError('Review proof/index command identities differ')
            legacy_path = absolute(proof['legacy_verification'])
            request_path = absolute(proof['request'])
            verify_file(legacy_path, proof['legacy_verification_sha256'])
            verify_file(request_path, proof['request_sha256'])
            legacy = read(legacy_path)
            if legacy.get('passed') is not True or any(legacy[key] != proof[key] for key in ('original', 'copy')):
                raise RuntimeError('Review legacy proof does not bind the same media')
            if any(legacy[key] != proof[key] for key in ('original_probe', 'copy_probe')):
                raise RuntimeError('Review probe evidence differs between proof stages')
            a, b = proof['original_probe'], proof['copy_probe']
            if len(a['streams']) != 1 or len(b['streams']) != 1:
                raise RuntimeError('Review stream topology differs from verified single-video scope')
            sa, sb = a['streams'][0], b['streams'][0]
            if (any(sa[key] != sb[key] for key in ('width', 'height', 'nb_read_frames'))
                    or any(Fraction(sa[key]) != Fraction(sb[key]) for key in ('avg_frame_rate', 'r_frame_rate'))
                    or abs(Decimal(a['format']['duration']) - Decimal(b['format']['duration'])) > Decimal('.04')
                    or abs(Decimal(a['format']['start_time']) - Decimal(b['format']['start_time'])) >= Decimal('.001')):
                raise RuntimeError('Review dimensions/fps/frames/start/duration differ')
            decoded_times = []
            for key in ('decoded_original', 'decoded_copy'):
                summary = proof[key]
                frame_path = absolute(summary['full_frame_record'])
                if frame_path.parent != proof_path.parent:
                    raise RuntimeError('Full decoded-frame evidence outside this review attempt')
                decoded = read(frame_path)
                times = [Decimal(row['best_effort_timestamp_time']) for row in decoded['frames']]
                if (not times or len(times) != summary['decoded_frames']
                        or len(times) != int(decoded['streams'][0]['nb_read_frames'])
                        or any(y <= x for x, y in zip(times, times[1:]))):
                    raise RuntimeError('Incomplete/nonmonotonic review full-frame evidence')
                decoded_times.append(times)
            ta, tb = decoded_times
            if (len(ta) != len(tb) or len(ta) != int(sa['nb_read_frames'])
                    or abs(ta[0] - tb[0]) >= Decimal('.001')
                    or max(abs((x - ta[0]) - (y - tb[0])) for x, y in zip(ta, tb)) > Decimal('.002')):
                raise RuntimeError('Review copy changed full decoded frame timestamps/count')
            local_matches = [] if local_inventory is None else [row for row in local_inventory['files']
                if row.get('remote_path') == str(original) and row.get('bytes') == proof['original']['bytes']
                and row.get('sha256') == proof['original']['sha256'] and row.get('verified_size_and_sha256') is True
                and PureWindowsPath(row.get('absolute_path', '')).is_absolute()]
            if len(local_matches) != 1:
                raise RuntimeError('Review substitution requires exactly one verified local original in --local-video-inventory')
            review_copies[relative(original)] = {'entry': entry, 'proof': proof, 'encoder': encoder,
                'verifier': verifier, 'legacy_verifier': legacy_verifier, 'local_original': local_matches[0]}

    def add(path, owner='delivery', note='Original evidence; read its execution and scope.',
            scene=None, derived=None, derivation=None):
        rel = relative(path)
        if rel in source_paths:
            return
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() not in bundle.ALLOWED:
            return
        bundle.safe_file(root, rel)
        bundle.scan_text(path)
        if path.suffix.lower() in MEDIA and path.stat().st_size >= MEDIA_LIMIT:
            review = review_copies.get(rel)
            if review is None:
                raise RuntimeError('Media >=47 MiB requires a verified full review copy and local original inventory: ' + rel)
            oversized_originals[rel] = {'original': review['proof']['original'],
                'original_run_id': owner, 'original_scope_note': note,
                'review_copy': review['entry']['copy'], 'proof': review['entry']['proof'],
                'command_record': review['entry']['command_record'],
                'verification_command_record': review['entry']['verification_command_record'],
                'legacy_verification_command_record': review['proof']['legacy_verification_command_record'],
                'local_original': review['local_original'],
                'local_inventory': relative(local_inventory_path), 'local_inventory_sha256': sha256(local_inventory_path),
                'scope': 'Complete original locally delivered; full same-dimensions/fps/timing ZIP review copy. Original success/failure unchanged.'}
            return
        row = {'path': rel, 'group': 'visuals' if path.suffix.lower() in
               {'.png', '.jpg', '.jpeg', '.webp', '.webm', '.mp4'} else 'reports',
               'run_id': owner, 'note': note}
        if scene:
            row['scene_id'] = scene
        if derived:
            row.update(derived_from=relative(derived), derivation_command_record=derivation)
        if rel in rows and rows[rel]['run_id'] != owner:
            raise RuntimeError('Conflicting evidence owner: ' + rel)
        rows[rel] = row

    cleanup_names = {'cleanup_direct_execution.json', 'verify_cleanup_direct_stdout.log',
                     'verify_cleanup_direct_stderr.log', 'service_shutdown.json',
                     'owned_process_verification.json', 'shutdown_gpu_ports.json'}
    for row in previous['files']:
        path = root / row['path']
        owner = 'r3_direct_cleanup' if path.parent == prior and path.name in cleanup_names else 'r3_' + row['run_id']
        add(path, owner, row.get('note', ''), row.get('scene_id'),
            root / row['derived_from'] if row.get('derived_from') else None,
            row.get('derivation_command_record'))
        if row['path'] in rows:
            rows[row['path']]['group'] = row['group']
    for rel in prior_paths - {x['path'] for x in previous['files']}:
        path = root / rel
        add(path, 'r3_direct_cleanup' if path.name in cleanup_names else 'r3_delivery')

    def identity(name):
        if name not in commands:
            return {'run_id': name, 'status': 'not_run'}
        record = commands[name]
        return {'run_id': name, 'command_record': relative(run / (name + '_command') / 'execution.json'),
                'returncode': record['returncode'], 'source_before': record['source_before']['digest'],
                'source_after': record['source_after']['digest'], 'assets_before': record['assets_before']['digest'],
                'assets_after': record['assets_after']['digest']}

    # Exact argv paths, not guessed command labels, own each independent video attempt.
    captures, producers, native_outputs = {}, {}, {}
    for name, record in commands.items():
        argv = record['command']
        cwd = absolute(record['cwd'])
        scripts = {Path(token).name for token in argv}
        if 'scripts.tests.audit_bridge_live' in argv:
            out = absolute(option(argv, '--out'), cwd)
            if out in native_outputs:
                raise RuntimeError('Native output has multiple recorded owners')
            native_outputs[out] = {'owner': name, 'scenes': scene_options(argv)}
        if 'capture_ui_videos.py' in scripts:
            out = absolute(option(argv, '--out'), cwd)
            if not out.is_relative_to(run / 'videos') or out in captures:
                raise RuntimeError('Capture output must have a unique RUN4/videos owner')
            script = next(token for token in argv if Path(token).name == 'capture_ui_videos.py')
            captures[out] = {'owner': name, 'scenes': scene_options(argv),
                             'script_path': absolute(script, cwd)}
        if 'produce_videos.py' in scripts:
            out = absolute(option(argv, '--capture-root'), cwd)
            media_name = option(argv, '--media-dir-name') or 'produced'
            if media_name != 'produced' and not (media_name.startswith('produced_attempt') and media_name.removeprefix('produced_attempt').isdigit()):
                raise RuntimeError('Unexpected recorded media directory')
            for scene in scene_options(argv):
                if (out, scene, media_name) in producers:
                    raise RuntimeError('More than one producer owns the same scene output')
                producers[out, scene, media_name] = name

    video_coverage = {scene: [] for scene in SCENES}
    overrides = {}
    for original, review in review_copies.items():
        entry = review['entry']
        overrides[absolute(entry['copy'])] = (review['encoder'], None, root / original, entry['command_record'])
    verified_review_paths = {absolute(item['entry']['copy']) for item in review_copies.values()}
    for request_path in sorted((run / 'review_videos').glob('*/request.json')):
        request = read(request_path)
        copy_path = absolute(request['copy'])
        if copy_path in verified_review_paths or not copy_path.is_file():
            continue
        if copy_path.parent != request_path.parent or request['encode_label'] not in commands:
            raise RuntimeError('Incomplete review output has no matching recorded encoder')
        original = absolute(request['original']['path'])
        verify_file(original, request['original']['sha256'], request['original']['bytes'])
        encoder = request['encode_label']
        overrides[copy_path] = (encoder, None, original, identity(encoder)['command_record'])
    successful_intros = {}
    collection_owners = {}
    for out, capture in captures.items():
        owner = capture['owner']
        batch_path = out / 'manifest.json'
        batch = read(batch_path) if batch_path.is_file() else {'scenes': []}
        by_scene = {x['scene_id']: x for x in batch['scenes']}
        if len(by_scene) != len(batch['scenes']) or set(by_scene) - set(capture['scenes']):
            raise RuntimeError('Capture scene list differs from recorded command')
        before_path, after_path = out / 'provenance_before.json', out / 'provenance_after.json'
        before = read(before_path) if before_path.is_file() else None
        after = read(after_path) if after_path.is_file() else None
        if before:
            tools = [capture['script_path'], *(root / '.work/cloud_video_20260921/versions').glob('capture_ui_videos_*.py')]
            matching = [path for path in tools if sha256(path) == before['capture_script_sha256']]
            if not matching:
                raise RuntimeError('Capture tool has no exact preserved version')
            capture['script_evidence'] = relative(matching[0])
            for phase in [before] + ([after] if after else []):
                if phase['source']['digest'] != source['digest'] or phase['assets']['digest'] != assets['digest']:
                    raise RuntimeError('Video batch source/asset identity mismatch')
            if after and before['capture_script_sha256'] != after['capture_script_sha256']:
                raise RuntimeError('Capture script changed during recording')
        for scene in capture['scenes']:
            directory = out / scene
            item = by_scene.get(scene)
            result = {'attempt': relative(out), 'capture_execution': identity(owner),
                      'status': 'not_started' if item is None else 'failed',
                      'raw_recording_present': False, 'workflow_mp4_verified': False,
                      'introduction_mp4_verified': False}
            video_coverage[scene].append(result)
            if item is None:
                if commands[owner]['returncode'] == 0:
                    raise RuntimeError('Successful capture is missing a requested scene manifest')
                if directory.exists():
                    unfinished_raw = sorted(directory.glob('raw_video/*.webm'))
                    result.update(status='interrupted_before_manifest',
                                  raw_recording_present=bool(unfinished_raw),
                                  unfinished_raw_files=[fingerprint(path) for path in unfinished_raw])
                continue
            if read(directory / 'manifest.json') != item or before is None:
                raise RuntimeError('Per-scene capture manifest differs from batch')
            expected = {'source_digest': source['digest'], 'asset_digest': assets['digest'],
                        'capture_script_sha256': before['capture_script_sha256']}
            if any(item.get(key) != value for key, value in expected.items()):
                raise RuntimeError('Scene capture identity mismatch: ' + scene)
            raw = absolute(item['raw_video'])
            if not raw.is_relative_to(directory / 'raw_video'):
                raise RuntimeError('Raw recording escapes its capture scene')
            verify_file(raw, item['raw_video_sha256'], item['raw_video_bytes'])
            verify_file(directory / 'scene_contract.json', item['scene_contract_sha256'])
            if not item['context_closed_before_manifest'] or item['time_compression_applied']:
                raise RuntimeError('Capture flush/time provenance mismatch')
            result.update(session_id=item.get('session_id'), manifest=relative(directory / 'manifest.json'),
                          raw=relative(raw), raw_recording_present=True,
                          source_digest=item['source_digest'], asset_digest=item['asset_digest'],
                          status='passed' if item['passed'] else 'failed')
            if item['passed']:
                if after is None:
                    raise RuntimeError('Passed capture lacks final provenance')
                for required in ('events.json', 'api_reads.jsonl', 'stages.json', 'final.json',
                                 'ui_timeline.json', 'introduction.json'):
                    if not (directory / required).is_file():
                        raise RuntimeError('Passed UI recording missing raw workflow evidence: ' + required)
            result['capture_script_evidence'] = capture.get('script_evidence')
            runtime_hash = item.get('viser_client_build_sha256')
            if runtime_hash:
                if before.get('viser_client_build_sha256') != runtime_hash or (after and after.get('viser_client_build_sha256') != runtime_hash):
                    raise RuntimeError('Capture runtime client build changed')
                served = read(directory / 'served_client.json')
                documents = served['documents']
                if (served['installed_build_sha256'] != runtime_hash or len(documents) != 1
                        or documents[0]['status'] != 200 or documents[0]['sha256'] != runtime_hash):
                    raise RuntimeError('Actual browser document differs from capture runtime identity')
                result['viser_client_build_sha256'] = runtime_hash
                result['served_client'] = relative(directory / 'served_client.json')
                if item['passed']:
                    canvas_files = [directory / 'canvas_initial.json']
                    stage_dirs = [Path(stage['directory']) for stage in item['stages']]
                    stage_dirs += [Path(row['image']).parent for row in read(directory / 'introduction.json')]
                    for stage_dir in stage_dirs:
                        if not stage_dir.is_relative_to(directory):
                            raise RuntimeError('Canvas evidence outside capture scene')
                        canvas_files.extend(stage_dir / name for name in ('canvas_before.json', 'canvas_after.json'))
                    for canvas in canvas_files:
                        observation = read(canvas)
                        last = observation['observations'][-1]['canvases']
                        if (observation.get('passed') is not True or not last or any(float(c['opacity']) != 1
                                or any(float(a) != 1 for a in c['ancestor_opacities']) for c in last)):
                            raise RuntimeError('Successful new capture lacks opaque actual canvas evidence')
                    result['canvas_checks'] = [relative(path) for path in canvas_files]
            else:
                result['runtime_identity_scope'] = 'Historical capture version without per-session served client build measurement'
            result['production_attempts'] = []
            producer_entries = [(media_name, producer) for (base, sid, media_name), producer in producers.items()
                                if base == out and sid == scene]
            for media_name, producer in producer_entries:
                media = directory / media_name
                product_path = media / 'manifest.json'
                record_path = identity(producer)['command_record']
                production_result = {'directory': relative(media), 'execution': identity(producer),
                                     'status': 'failed_or_incomplete', 'workflow_mp4_verified': False,
                                     'introduction_mp4_verified': False}
                result['production_attempts'].append(production_result)
                # Keep incomplete products too, with truthful derivation ownership.
                for filename, derived in [('workflow_realtime.mp4', raw),
                                          ('scene_introduction.mp4', directory / 'introduction.json')]:
                    path = media / filename
                    if path.is_file():
                        if not derived.is_file():
                            raise RuntimeError('Incomplete product lacks its actual input evidence')
                        overrides[path] = (producer, scene, derived, record_path)
                introduction_path = directory / 'introduction.json'
                if introduction_path.is_file():
                    for index, image in enumerate(read(introduction_path)):
                        piece = media / f'intro_piece_{index:02d}.mp4'
                        if piece.is_file():
                            image_path = absolute(image['image'])
                            verify_file(image_path, image['image_sha256'])
                            overrides[piece] = (producer, scene, image_path, record_path)
                if not product_path.is_file():
                    continue
                product = read(product_path)
                producer_record = commands[producer]
                producer_script = next(token for token in producer_record['command']
                                       if Path(token).name == 'produce_videos.py')
                producer_path = absolute(producer_script, absolute(producer_record['cwd']))
                tool_versions = [producer_path, *(root / '.work/cloud_video_20260921/versions').glob('produce_videos_*.py')]
                matching_tools = [path for path in tool_versions if sha256(path) == product['production_script_sha256']]
                if not matching_tools:
                    raise RuntimeError('Product tool has no matching current or preserved producer bytes')
                production_result['production_script_evidence'] = relative(matching_tools[0])
                if not item['passed'] or any(product.get(key) != value for key, value in expected.items()) or product['session_id'] != item['session_id']:
                    raise RuntimeError('Product differs from successful source capture')
                if absolute(product['raw_video']['path']) != raw or product['raw_video']['sha256'] != item['raw_video_sha256']:
                    raise RuntimeError('Product raw recording identity mismatch')
                timing = read(media / 'frame_timing_verification.json')
                if not timing['verification']['passed'] or timing['verification'] != product['workflow_mp4']['frame_timing_verification']:
                    raise RuntimeError('Missing/failed complete-frame timing verification')
                for required in ('raw_decoded_frames.json', 'workflow_decoded_frames.json'):
                    if not (media / required).is_file():
                        raise RuntimeError('Missing full decoded frame evidence')
                if product['workflow_mp4']['speed'] != 1 or product['workflow_mp4']['cuts'] != 0:
                    raise RuntimeError('Workflow product changed speed or cut content')
                intro_sources = read(directory / 'introduction.json')
                if product['introduction_mp4']['image_sources'] != intro_sources or not intro_sources:
                    raise RuntimeError('Introduction source list mismatch')
                for image in intro_sources:
                    image_path = absolute(image['image'])
                    if not image_path.is_relative_to(directory):
                        raise RuntimeError('Introduction image outside scene')
                    verify_file(image_path, image['image_sha256'])
                for key, derived in [('workflow_mp4', raw), ('introduction_mp4', directory / 'introduction.json')]:
                    path = absolute(product[key]['path'])
                    if path.parent != media:
                        raise RuntimeError('Product escapes its producer directory')
                    verify_file(path, product[key]['sha256'])
                    overrides[path] = (producer, scene, derived, record_path)
                    production_result[key + '_verified'] = True
                    production_result[key] = relative(path)
                production_result['status'] = 'passed' if commands[producer]['returncode'] == 0 else 'outputs_verified_command_failed'
                choice = acceptance['accepted'][scene]
                accepted_here = absolute(choice['production_manifest']) == product_path
                rejected = acceptance['rejected'].get(str(product_path))
                production_result['visual_decision'] = 'accepted' if accepted_here else ('rejected' if rejected else 'retained_unselected')
                production_result['visual_reason'] = choice['reason'] if accepted_here else (rejected['reason'] if rejected else 'Not selected by explicit visual acceptance')
                if accepted_here:
                    if production_result['status'] != 'passed' or commands[owner]['returncode'] != 0:
                        raise RuntimeError('Visually accepted production/capture did not complete successfully')
                    result.update(production_status='passed', visual_accepted=True, workflow_mp4_verified=True, introduction_mp4_verified=True,
                                  visual_choice=choice, production_execution=identity(producer),
                                  workflow_mp4=production_result['workflow_mp4'], introduction_mp4=production_result['introduction_mp4'])
                    successful_intros[relative(absolute(product['introduction_mp4']['path']))] = {
                        'scene_id': scene, 'sha256': product['introduction_mp4']['sha256']}
            result.setdefault('production_status', 'failed_or_incomplete' if producer_entries else 'not_run')

    if {x['scene_id'] for x in successful_intros.values()} != set(SCENES):
        raise RuntimeError('An explicit accepted production was not matched to completed evidence')
    add(Path(acceptance['path']), note='Explicit visual decisions; rejected functionality-pass attempts remain preserved.')

    if args.intro_collection_manifest:
        collection_path = absolute(args.intro_collection_manifest)
        if not collection_path.parent.is_relative_to(run / 'videos'):
            raise RuntimeError('Collection manifest must belong to RUN4/videos')
        collection = read(collection_path)
        if collection.get('acceptance_manifest_sha256') != acceptance['sha256']:
            raise RuntimeError('Introduction collection used a different visual acceptance manifest')
        if not collection['outputs']:
            raise RuntimeError('Empty introduction collection output list')
        if (collection.get('passed') is not True
                or collection['decoded_input_frames'] != collection['decoded_output_frames']
                or abs(collection['actual_duration_s'] - collection['expected_duration_s']) > .05):
            raise RuntimeError('Introduction collection frame/duration verification did not pass')
        for output in collection['outputs']:
            sources = output['sources']
            if len(sources) != 12 or {x['scene_id'] for x in sources} != set(SCENES):
                raise RuntimeError('Introduction collection must retain exactly 12 actual scene sources')
            if sum(x['decoded_frames'] for x in sources) != collection['decoded_input_frames']:
                raise RuntimeError('Collection frame sum differs from its 12 inputs')
            for item in sources:
                path = relative(absolute(item['path']))
                if successful_intros.get(path) != {'scene_id': item['scene_id'], 'sha256': item['sha256']}:
                    raise RuntimeError('Collection source is not a verified scene introduction')
            record_path = relative(absolute(output['command_record']))
            matching = [name for name in commands if identity(name)['command_record'] == record_path]
            if len(matching) != 1 or commands[matching[0]]['returncode'] != 0:
                raise RuntimeError('Introduction collection lacks successful current producer record')
            path = absolute(output['path'])
            if path.parent != collection_path.parent:
                raise RuntimeError('Collection output outside its manifest directory')
            verify_file(path, output['sha256'])
            overrides[path] = (matching[0], None, collection_path, record_path)
            existing_owner = collection_owners.setdefault(collection_path.parent, matching[0])
            if existing_owner != matching[0]:
                raise RuntimeError('Multiple command owners in collection directory')
        add(collection_path, collection_owners[collection_path.parent],
            note='Multi-input introduction collection derivation manifest.')

    def video_owner(path):
        collection_matches = [owner for directory, owner in collection_owners.items()
                              if path.is_relative_to(directory)]
        if collection_matches:
            if len(collection_matches) != 1:
                raise RuntimeError('Ambiguous introduction collection directory ownership')
            return collection_matches[0]
        matches = [(out, capture) for out, capture in captures.items() if path.is_relative_to(out)]
        if len(matches) != 1:
            raise RuntimeError('Video evidence has no unique recorded capture owner: ' + relative(path))
        out, capture = matches[0]
        parts = path.relative_to(out).parts
        if len(parts) > 1 and parts[0] in SCENES and parts[1].startswith('produced'):
            producer = producers.get((out, parts[0], parts[1]))
            if producer is None:
                raise RuntimeError('Produced evidence lacks recorded producer')
            return producer
        if path.name.startswith('produced') and '_index_' in path.name:
            media_name = path.name.split('_index_', 1)[0]
            scenes = {row['scene_id'] for row in read(path)}
            owners = {owner for (base, scene, media), owner in producers.items()
                      if base == out and scene in scenes and media == media_name}
            if len(owners) != 1:
                raise RuntimeError('Ambiguous produced index owner')
            return owners.pop()
        return capture['owner']

    top_owner = {'pytest_final.xml': 'pytest_final', 'viser_opacity_install.json': 'install_visor_opacity_fix', 'readiness.json': 'readiness', 'service_shutdown.json': 'shutdown',
                 'shutdown_gpu_ports.json': 'shutdown', 'owned_process_verification.json': 'verify_cleanup',
                 'RESOURCE_STOP.json': 'resource_stop'}
    for path in sorted(run.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(run)
        if rel.parts[0].startswith(('upload', 'selection')) or rel.parts[0] in ignored_commands:
            continue
        if path.name in {'review_selection.json', 'state.sqlite', 'state.sqlite-wal', 'state.sqlite-shm'}:
            continue
        # Inherited native selection convention; UI screenshots/raw media are never skipped.
        if rel.parts[0] != 'videos':
            if any(x.startswith('frame_') and x.endswith('_passes') for x in rel.parts) and path.suffix == '.png':
                continue
            if 'frames' in rel.parts and path.name != 'manifest.json':
                continue
        if path in overrides:
            owner, scene, derived, command = overrides[path]
            note = ('Complete same-dimensions/fps/timing ZIP review copy; local original delivery and original success/failure retained.'
                    if path in verified_review_paths else
                    'Unverified or failed review encoding; original retained, never used as a verified substitution.'
                    if path.is_relative_to(run / 'review_videos') else
                    'Derived from preserved raw media or explicit multi-image source manifest; UI-only.')
            add(path, owner, note,
                scene, derived, command)
            continue
        if path.suffix.lower() == '.mp4' and rel.parts[0] == 'videos':
            raise RuntimeError('UI MP4 lacks an explicit derivation mapping: ' + relative(path))
        owner = rel.parts[0].removesuffix('_command')
        if rel.parts[0] == 'videos':
            owner = video_owner(path)
        elif rel.parts[0] in {'hdr_diagnostic_before', 'hdr_diagnostic_after'}:
            owner = 'hdr_display_diagnostic_' + rel.parts[0].removeprefix('hdr_diagnostic_')
        elif rel.parts[0] == 'bridge_batches':
            matches = [entry['owner'] for out, entry in native_outputs.items() if path.is_relative_to(out)]
            if len(matches) != 1:
                raise RuntimeError('Native evidence has no unique --out command owner: ' + relative(path))
            owner = matches[0]
        elif rel.parts[0] == 'changed_pairs' and len(rel.parts) > 1:
            owner = 'pairs_' + rel.parts[1]
        elif rel.parts[0] == 'review_videos' and len(rel.parts) > 2:
            review = next((item for item in review_copies.values()
                           if absolute(item['entry']['proof']).parent == path.parent), None)
            if review:
                owner = (review['legacy_verifier'] if path.name == 'legacy_verification.json'
                         else review['verifier'])
            else:
                owner = rel.parts[1] if rel.parts[1] in commands else 'delivery'
        elif len(rel.parts) == 1:
            owner = top_owner.get(path.name, 'delivery')
            for prefix, command_prefix in [('readiness_', 'readiness_'), ('service_shutdown_', 'shutdown_'),
                                           ('shutdown_gpu_ports_', 'shutdown_'),
                                           ('owned_process_verification_', 'verify_cleanup_')]:
                if path.name.startswith(prefix) and path.suffix == '.json':
                    owner = command_prefix + path.stem.removeprefix(prefix)
            for suffix in ('_resources.jsonl', '_launcher.log', '_repair_process.json', '_process.json'):
                if path.name.endswith(suffix):
                    owner = path.name.removesuffix(suffix)
                    break
            if path.name in generation_owners:
                owner = generation_owners[path.name]
        if owner not in commands:
            owner = 'delivery'
        add(path, owner)
    for directory in (root / '.work/cloud_finish90_20260921', root / '.work/cloud_video_20260921'):
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in {'.py', '.sh', '.md', '.json'}:
                add(path)
    for path in sorted((root / '.work/cloud_video_20260921/versions').glob('*.py')):
        add(path, note='Explicitly preserved video tool version; manifests retain its original SHA256.')
    runtime_directory = root / '.work/viser_hdr_opacity_fix'
    runtime_files = [
        'build_identity.json', 'original_identity.json', 'dependency_identity.json', 'node_identity.json',
        'HDRJPGEnvironment.opacity.patch', 'regression_old.json', 'regression_old_behavior.json',
        'regression_fixed_behavior.json', 'REVIEW.md', 'DELIVERY_README.md', 'build_fix.py', 'capture_intro_probe.py',
        'original/HDRJPGEnvironment.tsx', 'original/index.html', 'original/package-lock.json',
        'viser/client/src/HDRJPGEnvironment.tsx', 'viser/client/src/HDRJPGEnvironment.opacity.test.ts',
        'viser/client/build/index.html', 'viser/client/package.json', 'viser/client/package-lock.json']
    runtime_owner = {'build_identity.json': 'hdr_opacity_build',
        'regression_old.json': 'hdr_opacity_regression_old', 'regression_old_behavior.json': 'hdr_opacity_regression_old_behavior',
        'regression_fixed_behavior.json': 'hdr_opacity_regression_fixed_behavior',
        'node_identity.json': 'hdr_opacity_node', 'dependency_identity.json': 'hdr_opacity_dependencies'}
    for name in runtime_files:
        add(runtime_directory / name, runtime_owner.get(name, 'delivery'),
            'Isolated dependency client repair evidence; application source snapshot remains separate. '
            'Old regression failure is expected defect reproduction, not a successful experiment.')
    runtime_build = read(runtime_directory / 'build_identity.json')
    for key in ('patched_source', 'isolated_build', 'lock', 'test', 'old_regression', 'fixed_regression'):
        row = runtime_build[key]
        path = absolute(row['path'])
        if not path.is_relative_to(runtime_directory):
            raise RuntimeError('Isolated runtime build identity escaped its explicit directory')
        verify_file(path, row['sha256'], row['bytes'])
    runtime_install = read(run / 'viser_opacity_install.json')
    if runtime_install['identity_sha256'] != sha256(runtime_directory / 'build_identity.json'):
        raise RuntimeError('Installed runtime is not bound to this isolated build identity')
    runtime_coverage = {'scope': 'Dependency Viser client repair, separate from application source/assets',
        'build_identity': relative(runtime_directory / 'build_identity.json'),
        'installed_record': relative(run / 'viser_opacity_install.json'),
        'isolated_client_build_sha256': runtime_build['isolated_build']['sha256'],
        'files': [relative(runtime_directory / name) for name in runtime_files],
        'executions': {name: identity(name) for name in commands if name.startswith(('hdr_', 'install_visor_opacity_fix'))},
        'original_regression_expected_failure': read(runtime_directory / 'regression_old_behavior.json'),
        'fixed_regression': read(runtime_directory / 'regression_fixed_behavior.json')}
    if local_inventory_path:
        if local_inventory.get('visual_acceptance', {}).get('sha256') != acceptance['sha256']:
            raise RuntimeError('Local video delivery uses a different explicit visual acceptance')
        add(local_inventory_path, note='Exact completed local VIDEO_FILES inventory; includes local original paths, sizes and SHA256.')

    review_directory = root / '.work/cloud_finish90_20260921'
    review_manifest = review_directory / 'video_review_manifest.json'
    frame_directory = review_directory / 'video_review_inputs'
    if review_manifest.is_file():
        review = read(review_manifest)
        expected_frames = set()
        for frame in review['frames']:
            path = absolute(frame['local_relative_path'], review_directory)
            if not path.is_relative_to(frame_directory) or path.suffix.lower() != '.png':
                raise RuntimeError('Visual review frame escapes its explicit PNG directory')
            video = absolute(frame['source_video'], run)
            verify_file(path, frame['sha256'])
            verify_file(video, frame['source_video_sha256'])
            if relative(video) not in rows and relative(video) not in oversized_originals:
                raise RuntimeError('Visual review source MP4 is not selected')
            expected_frames.add(path)
            # The review manifest records extraction/time/source hashes, not a
            # record.py execution. Do not invent derivation_command_record.
            add(path, 'delivery', 'Independent visual-review extracted frame, not an original native image. '
                f"Source {relative(video)}, requested time {frame['requested_time_s']} s; "
                f"extraction provenance in {relative(review_manifest)}. Historical review evidence only.")
        if set(frame_directory.rglob('*.png')) != expected_frames:
            raise RuntimeError('Visual review PNG set differs from its explicit manifest')
        rows[relative(review_manifest)]['note'] = (
            'Independent visual review extraction manifest; original MP4 hashes and requested times. '
            'Sampled frames are not native image counts or a claim that every frame was manually watched.')
    elif frame_directory.exists() and any(frame_directory.rglob('*.png')):
        raise RuntimeError('Visual review PNGs lack their extraction manifest')

    copy_review_manifest = review_directory / 'review_copy_visual_manifest.json'
    for path, video, requested_time in review_copy_visual_frames(
            root, run, review_directory, rows, oversized_originals, verify_file):
        # The extraction manifest is evidence, not a record.py execution.
        add(path, 'delivery', 'Independent paired review-copy clarity sample, not an original native image. '
            f'Source {relative(video)}, requested time {requested_time} s; '
            f'extraction provenance in {relative(copy_review_manifest)}. No extraction command record is asserted.')
    if copy_review_manifest.is_file():
        add(copy_review_manifest, 'delivery', 'Paired original/review-copy sampled-frame manifest; '
            'source and PNG hashes verified. Finite clarity review only, not full-frame manual review or scene acceptance.')

    def current_result(scene, kind):
        if kind == 'native':
            attempts = []
            for base, entry in native_outputs.items():
                if scene not in entry['scenes']:
                    continue
                name = entry['owner']
                path = base / 'report.json'
                result = {'execution': identity(name), 'output_directory': relative(base)}
                if path.is_file():
                    report = read(path)
                    if not isinstance(report, list) or any(x['scene_id'] not in entry['scenes'] for x in report):
                        raise RuntimeError('Native report scene differs from recorded --scenes')
                    scene_report = [x for x in report if x['scene_id'] == scene]
                    if len(scene_report) > 1:
                        raise RuntimeError('Duplicate scene in native attempt report')
                    result.update(report_path=relative(path), report=scene_report,
                                  passed=bool(scene_report) and scene_report[0].get('passed') is True
                                  and commands[name]['returncode'] == 0)
                else:
                    stages = base / scene / 'stages.json'
                    result.update(status='interrupted_without_final_report', passed=False, report_exists=False,
                                  completed_captures=read(stages) if stages.is_file() else [])
                attempts.append(result)
            if not attempts:
                return 'not_run'
            successes = [x for x in attempts if x['passed']]
            return {'passed': bool(successes), 'attempts': attempts,
                    'successful_attempts': [x['execution']['command_record'] for x in successes],
                    'note': 'All actual attempts retained; an earlier failure never replaces a later success.'}
        name = ('bridge_' if kind == 'native' else 'pairs_') + scene
        base = run / ('bridge_batches' if kind == 'native' else 'changed_pairs') / scene
        path = base / 'report.json'
        if path.is_file():
            if name not in commands:
                raise RuntimeError('Current report has no recorded command owner: ' + relative(path))
            return {'execution': identity(name), 'report_path': relative(path), 'report': read(path)}
        if name in commands:
            stages = base / scene / 'stages.json'
            return {'execution': identity(name), 'status': 'interrupted_without_final_report',
                    'report_exists': False, 'completed_captures': read(stages) if stages.is_file() else []}
        return 'not_run'

    def native_attempts(node, pointer):
        result = []
        if not isinstance(node, dict):
            return result
        for key, value in node.items():
            if key in {'native_this_batch', 'native_resume', 'native_this_run'} and isinstance(value, dict):
                if 'attempts' in value:
                    for index, attempt in enumerate(value['attempts']):
                        reports = attempt.get('report', [])
                        result.append({'coverage_pointer': pointer + '/' + key + '/attempts/' + str(index),
                            'passed': attempt['passed'], 'execution': attempt['execution'],
                            'stage_count': (sum(len(x.get('stages', [])) for x in reports)
                                            if reports else len(attempt.get('completed_captures', []))),
                            'status': attempt.get('status', 'report_recorded')})
                    continue
                reports = value.get('report', [])
                passed = bool(reports) and isinstance(reports, list) and all(x.get('passed') is True for x in reports)
                execution = value.get('execution', {})
                result.append({'coverage_pointer': pointer + '/' + key, 'passed': passed and execution.get('returncode') == 0,
                    'execution': execution, 'stage_count': (sum(len(x.get('stages', [])) for x in reports)
                        if isinstance(reports, list) and reports else len(value.get('completed_captures', []))),
                    'status': value.get('status', 'report_recorded')})
            elif key in {'previous_batch', 'earlier_batch'}:
                result.extend(native_attempts(value, pointer + '/' + key))
        return result

    focus_path = root / 'runs/simulation/repair_review_20260920_25bcc909/bridge/report.json'
    if relative(focus_path) not in rows:
        raise RuntimeError('Historical four-focus native report was not inherited')
    focus = {x['scene_id']: x for x in read(focus_path)}
    focus_record_path = root / 'runs/simulation/repair_review_20260920_25bcc909/bridge_command/execution.json'
    focus_record = read(focus_record_path)
    focus_identity = {'command_record': relative(focus_record_path), 'returncode': focus_record['returncode'],
        'source_before': focus_record['source_before']['digest'], 'source_after': focus_record['source_after']['digest'],
        'assets_before': focus_record['assets_before']['digest'], 'assets_after': focus_record['assets_after']['digest']}
    add(focus_record_path, rows[relative(focus_path)]['run_id'], 'Original historical focus execution; do not substitute a later snapshot identity.')
    if set(focus) != set(FOCUS_FOUR):
        raise RuntimeError('Historical focus scope changed')
    coverage = {'source_digest': source['digest'], 'asset_digest': assets['digest'],
        'previous_coverage': relative(prior / 'COVERAGE.json'),
        'run3_frozen_inventory': relative(frozen_path), 'run3_frozen_inventory_sha256': sha256(frozen_path),
        'run2_sealed_archive_index': relative(sealed / 'upload/UPLOAD_INDEX.json'),
        'reused_checks': old_coverage['reused_checks'],
        'scope': 'Eight original full-native targets plus four historical native focus results. '
                 'UI-only videos are independent sessions and never count as native passes.',
        'host_memory_policy': {'max_used_fraction': .90, 'authorization': 'Explicit user authorization retained'},
        'native_scope': {'original_eight': list(NATIVE_EIGHT), 'historical_focus_four': list(FOCUS_FOUR)},
        'commands': {name: identity(name) for name in commands}, 'scenes': [],
        'zip_review_substitutions': list(oversized_originals.values()),
        'runtime_client_repair': runtime_coverage,
        'service_generations': {name: identity(name) for name in commands if (run / (name + '_repair_process.json')).is_file() and any(name == service or name.startswith(service + '_') for service in ('model', 'api', 'viewer'))},
        'final_source_checks': {name: identity(name) for name in ('pytest_final', 'live_final', 'viewer_response_final', 'response_final')},
        'visual_acceptance': acceptance,
        'ui_video_coverage': {'scope': 'Real Viser UI-only; no Blender/native acceptance', 'scenes': []}}
    for old_scene in old_coverage['scenes']:
        scene = old_scene['scene_id']
        current = current_result(scene, 'native')
        row = {'scene_id': scene, 'previous_batch': old_scene, 'native_this_run': current,
               'targeted_pairs_this_run': current_result(scene, 'pairs')}
        attempts = native_attempts(row, '/scenes/' + scene)
        if scene in FOCUS_FOUR:
            historical = focus[scene]
            row['native_final_summary'] = {'scope': 'Historical focus; original execution identity below, not rerun under RUN4 source',
                'passed': historical['passed'], 'report': relative(focus_path), 'execution': focus_identity,
                'original_owner': rows[relative(focus_path)]['run_id'],
                'session_id': historical['session_id'], 'stage_count': len(historical['stages'])}
        else:
            row['native_final_summary'] = {'scope': 'original eight native target',
                'passed_in_at_least_one_recorded_phase': any(x['passed'] for x in attempts),
                'attempts': attempts,
                'note': 'All phase identities and failures remain; earlier success is not current-source rerun.'}
        coverage['scenes'].append(row)
        attempts_ui = video_coverage[scene]
        coverage['ui_video_coverage']['scenes'].append({'scene_id': scene,
            'status': 'not_run' if not attempts_ui else ('passed' if any(x.get('visual_accepted') for x in attempts_ui) else 'failed_or_incomplete'),
            'raw_recording_present': any(x['raw_recording_present'] for x in attempts_ui),
            'workflow_mp4_verified': any(x['workflow_mp4_verified'] for x in attempts_ui),
            'introduction_mp4_verified': any(x['introduction_mp4_verified'] for x in attempts_ui),
            'attempts': attempts_ui})
    ui = coverage['ui_video_coverage']
    ui['counts'] = {key: sum(bool(x[key]) for x in ui['scenes']) for key in
                    ('raw_recording_present', 'workflow_mp4_verified', 'introduction_mp4_verified')}
    ui['required_scene_count'] = 12
    ui['all_twelve_complete'] = all(x['status'] == 'passed' and x['workflow_mp4_verified'] and
                                    x['introduction_mp4_verified'] for x in ui['scenes'])
    if args.intro_collection_manifest:
        ui['introduction_collection_manifest'] = relative(absolute(args.intro_collection_manifest))
    import xml.etree.ElementTree as ET
    cases = list(ET.parse(run / 'pytest_final.xml').getroot().iter('testcase'))
    coverage['final_source_checks']['pytest_final']['junit'] = {'path': relative(run / 'pytest_final.xml'), 'tests': len(cases),
        'failures': sum(case.find('failure') is not None for case in cases), 'errors': sum(case.find('error') is not None for case in cases),
        'skipped': sum(case.find('skipped') is not None for case in cases)}
    coverage['resource_interruptions'] = [{'path': relative(path), 'sha256': sha256(path)} for path in sorted(run.glob('RESOURCE_STOP_*.json'))]
    if (run / 'RESOURCE_STOP.json').is_file():
        coverage['resource_stop'] = read(run / 'RESOURCE_STOP.json')
    save(run / 'source_final.json', source)
    save(run / 'assets_final.json', assets)
    save(run / 'inherited_evidence_verification.json', {'passed': True, 'run2_archive': relative(archive),
         'run2_archive_sha256': published['sha256'], 'sealed_files': sealed_verified,
         'run3_inventory': relative(frozen_path), 'run3_inventory_sha256': sha256(frozen_path)})
    save(run / 'COVERAGE.json', coverage)
    for name in ('source_final.json', 'assets_final.json', 'inherited_evidence_verification.json', 'COVERAGE.json'):
        add(run / name)
    selection['files'] = sorted(rows.values(), key=lambda row: row['path'])
    selection['privacy_reviewed'] = True
    bundle.Selection.model_validate(selection)
    # Revalidate the immutable RUN3 baseline at the end, not just before scanning.
    for row in frozen_rows:
        verify_file(root / row['path'], row['sha256'], row['bytes'])
    save(run / 'review_selection.json', selection)
    print(json.dumps({'source_digest': source['digest'], 'asset_digest': assets['digest'],
                      'runs': len(selection['runs']), 'files': len(selection['files']),
                      'ui_video_counts': ui['counts'], 'all_twelve_ui_complete': ui['all_twelve_complete']}))


if __name__ == '__main__':
    main()
