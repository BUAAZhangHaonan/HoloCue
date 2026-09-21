"""Independent read-only final ZIP audit. Writes only its separate JSON report."""
import hashlib
import json
import sys
import zipfile
import zlib
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path, PurePosixPath

ROOT = Path('/home/hdd3/zhanghaonan/projects/holocue')
P = 'runs/simulation/cloud_finish90_20260921_e67b574/'
H = '.work/cloud_finish90_20260921/'
BASE = ROOT / P / 'upload'
FINAL = 'd8d73e7d849b949bfee3827d6f60dfb86351cc50b49f98027b92db1664392806'
OLD = 'c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a'
ASSETS = '36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8'
errors = []
def check(value, message):
    if not value:
        errors.append(message)
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def canonical(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
def relative(value):
    path = Path(value)
    return path.relative_to(ROOT).as_posix() if path.is_absolute() else path.as_posix()

index = json.loads((BASE / 'UPLOAD_INDEX.json').read_text())
sums = {}
for line in (BASE / 'SHA256SUMS').read_text().splitlines():
    if line.strip():
        digest, name = line.split(None, 1)
        name = name.strip().lstrip('*')
        check(name not in sums, 'Duplicate SHA256SUMS entry: ' + name)
        sums[name] = digest
with zipfile.ZipFile(BASE / '00_review_index.zip') as stream:
    manifest = json.loads(stream.read('HoloCue_Review/MANIFEST.json'))
    source = json.loads(stream.read('HoloCue_Review/SOURCE_SNAPSHOT.json'))
    assets = json.loads(stream.read('HoloCue_Review/ASSET_SNAPSHOT.json'))
    status = json.loads(stream.read('HoloCue_Review/STATUS.json'))
expected = {}
for row in manifest['files'] + index['index_files']:
    name = 'HoloCue_Review/' + row['path']
    check(name not in expected, 'Duplicate manifest/index member: ' + name)
    expected[name] = row
archives, members, seen = [], [], {}
for row in index['archives']:
    path = BASE / row['archive']
    size, digest = path.stat().st_size, sha(path)
    check(size < 48 * 1048576, 'Archive >=48MiB: ' + path.name)
    check(size == row['bytes'] and digest == row['sha256'] == sums.get(path.name), 'Archive byte/hash mismatch: ' + path.name)
    count = 0
    crc_ok = True
    with zipfile.ZipFile(path) as archive:
        check(set(archive.namelist()) == {'HoloCue_Review/' + x for x in row['files']}, 'Archive member-set mismatch: ' + path.name)
        for info in archive.infolist():
            name = info.filename
            check(name not in seen, 'Duplicate member: ' + name)
            seen[name] = path.name
            pp = PurePosixPath(name)
            check(not pp.is_absolute() and '..' not in pp.parts and '\\' not in name and not info.is_dir(), 'Unsafe member: ' + name)
            check(name in expected, 'Unexpected member: ' + name)
            h, crc, length = hashlib.sha256(), 0, 0
            try:
                with archive.open(info) as content:
                    while chunk := content.read(4 * 1048576):
                        h.update(chunk)
                        crc = zlib.crc32(chunk, crc)
                        length += len(chunk)
            except Exception as error:
                errors.append('ZIP read/CRC failure: ' + name + ' (' + type(error).__name__ + ')')
                crc_ok = False
            match = (crc & 0xffffffff) == info.CRC and length == info.file_size
            crc_ok &= match
            check(match, 'Member CRC/size mismatch: ' + name)
            target = expected.get(name, {})
            check(h.hexdigest() == target.get('sha256'), 'Member SHA mismatch: ' + name)
            check('bytes' not in target or length == target['bytes'], 'Manifest member size mismatch: ' + name)
            members.append({'archive': path.name, 'path': name, 'bytes': length, 'sha256': h.hexdigest(), 'crc32': f'{crc & 0xffffffff:08x}', 'crc_passed': match})
            count += 1
    archives.append({'archive': path.name, 'bytes': size, 'sha256': digest, 'members': count, 'crc_passed': crc_ok})
check(set(seen) == set(expected), 'Full member set mismatch')
check({x['archive'] for x in index['archives']} == set(sums) == {p.name for p in BASE.glob('*.zip')}, 'Exact ZIP set mismatch')
check(len(index['archives']) == len({x['archive'] for x in index['archives']}), 'Duplicate archive entries')
check(index['total_files'] == len(manifest['files']), 'Project file count mismatch')
by_source = {x['source_path']: x for x in manifest['files']}
check(len(by_source) == len(manifest['files']), 'Duplicate project source paths')
def raw(path):
    rel = relative(path)
    row = by_source[rel]
    name = 'HoloCue_Review/' + row['path']
    with zipfile.ZipFile(BASE / seen[name]) as archive:
        return archive.read(name)
def obj(path):
    return json.loads(raw(path))
def present(path, digest=None, size=None):
    rel = relative(path)
    row = by_source.get(rel)
    check(row is not None, 'Missing required evidence: ' + rel)
    if row:
        check(digest is None or row['sha256'] == digest, 'Required evidence hash differs: ' + rel)
        check(size is None or row['bytes'] == size, 'Required evidence size differs: ' + rel)
    return row

content = {}
check(source['digest'] == canonical(source['files']) == FINAL == index['source_digest'], 'Final source digest differs')
check(assets['digest'] == canonical(assets['files']) == ASSETS, 'Asset digest differs')
for snapshot in (source, assets):
    for row in snapshot['files']:
        present(row['path'], row['sha256'], row['bytes'])
content['asset_count'] = len(assets['files'])
content['referenced_scene_glb_count'] = sum(x['path'].startswith('scenes/') and x['path'].endswith('.glb') for x in assets['files'])
content['fixture_count'] = sum(x['path'].startswith('tests/fixtures/') for x in assets['files'])
check((content['asset_count'], content['referenced_scene_glb_count'], content['fixture_count']) == (103, 76, 27), 'Asset/fixture scope changed')
for scene, digest in {'drone_bench': 'da730c06202bb8a8f8dddb5bab234e78dbb3db72f671624167f19c61f7623093', 'engine_bay': '1f8a6bf78f82fbcc2c9a64d27cb917d0e27c206e64d1d58f331a7dfd168a286f', 'shelf_picking': '608f8d6f15fc5ee756876874a8596e5d924dc3d9f3130f9f4e97126ed230e455'}.items():
    present(f'scenes/{scene}/scene.blend', digest)
content['new_blends_preserved'] = 3
phase = obj(P + 'SOURCE_PHASES.json')
check(phase['current_source_digest'] == FINAL and phase['asset_digest'] == ASSETS, 'Phase manifest differs')
snapshots = {}
for item in phase['phases']:
    present(item['source_snapshot'], item['source_snapshot_sha256'])
    snapshot = obj(item['source_snapshot'])
    check(snapshot['digest'] == item['source_digest'] == canonical(snapshot['files']), 'Phase snapshot digest mismatch')
    snapshots[item['source_digest']] = {x['path']: x for x in snapshot['files']}
check(set(snapshots) == {OLD, FINAL}, 'Unexpected phase set')
changed = sorted(p for p in snapshots[OLD].keys() | snapshots[FINAL].keys() if snapshots[OLD].get(p) != snapshots[FINAL].get(p))
check(changed == ['src/holocue/viewer_scene.py'] == phase['changed_source_paths'], 'Unexpected app change scope')
present(phase['previous_file'], snapshots[OLD]['src/holocue/viewer_scene.py']['sha256'])
coverage = obj(P + 'COVERAGE.json')
run_status = {x['run_id']: x for x in status['runs']}
for name, identity in coverage['commands'].items():
    record = obj(identity['command_record'])
    digest = record['source_before']['digest']
    check(digest in {OLD, FINAL} and record['source_after']['digest'] == digest, 'Unstable/unknown command source: ' + name)
    check(record['assets_before']['digest'] == record['assets_after']['digest'] == ASSETS, 'Command asset drift: ' + name)
    check(identity['returncode'] == record['returncode'], 'Coverage return code differs: ' + name)
    row = run_status[name]
    check(row['source_digest'] == digest and row['scope'] == ('current' if digest == FINAL else 'historical'), 'Packaged command phase scope differs: ' + name)
    if digest == OLD:
        check(row['status'] == 'recorded', 'Historical command upgraded: ' + name)
    else:
        check(row['status'] == ('passed' if record['returncode'] == 0 else 'failed'), 'Current command status differs: ' + name)
for name, identity in coverage['before_camera_atomic_checks'].items():
    check(identity['source_before'] == OLD and identity['scope'] == 'historical', 'Old check upgraded: ' + name)
for name, identity in coverage['final_source_checks'].items():
    check(identity['source_before'] == FINAL and identity['scope'] == 'current' and identity['returncode'] == 0, 'Final check is not successful/current: ' + name)
check(coverage['final_source_checks']['pytest_camera_final']['junit'] == {'path': P + 'pytest_camera_final.xml', 'tests': 529, 'failures': 0, 'errors': 0, 'skipped': 0}, 'Final pytest summary differs')
camera = coverage['final_source_checks']['camera_atomic_live']['report']
check(camera['passed'] and len(camera['rounds']) == 10, 'Camera 10-round regression not complete')
check(coverage['final_source_checks']['pairs_shelf_picking_attempt03']['result']['passed'], 'Final Shelf attempt not passed')
content['command_count'] = len(coverage['commands'])
content['source_phase_counts'] = dict(Counter(x['source_before'] for x in coverage['commands'].values()))
content['final_checks'] = {name: {'returncode': x['returncode'], 'source': x['source_before']} for name, x in coverage['final_source_checks'].items()}
content['native_summary'] = []
for scene in coverage['scenes']:
    summary = scene['native_final_summary']
    passed = summary.get('passed_in_at_least_one_recorded_phase', summary.get('passed'))
    check(passed is True, 'Native/focus lacks historical or actual pass: ' + scene['scene_id'])
    content['native_summary'].append({'scene': scene['scene_id'], 'passed_in_recorded_scope': passed, 'scope': summary['scope']})
check(coverage['ui_video_coverage']['source_digest'] == OLD and coverage['ui_video_coverage']['all_twelve_complete'], 'UI video source/completeness differs')
preflight = json.loads(Path(sys.argv[1]).read_text())
for row in preflight['sealed_files']:
    present(row['path'], row['sha256'], row['bytes'])
present(preflight['visual_review_seal']['path'], preflight['visual_review_seal']['sha256'])
present(P + 'VIDEO_ACCEPTANCE.json', preflight['acceptance']['sha256'])
for pair in preflight['five_original_png_copies']:
    for role in ('original', 'copy'):
        row = pair[role]
        present(row['path'], row['sha256'], row['bytes'])
seal = obj(H + 'visual_review_seal.json')
for name, digest in seal['files'].items():
    present(H + name, digest)
inventory = obj(H + 'final_review_inventory.json')
for row in inventory['source_originals']:
    present(P + row['relative_path'], row['sha256'])
content['sealed_visual_counts'] = seal['counts']
content['raw_reply_checks'] = []
acceptance = obj(P + 'VIDEO_ACCEPTANCE.json')
check(len(acceptance['accepted']) == 12 and len(acceptance['rejected']) == 1, 'Acceptance scope differs')
substitutions = {relative(x['original']['path']): x for x in coverage['zip_review_substitutions']}
check(len(substitutions) == 8, 'Expected eight oversized substitutions')
for decision in acceptance['accepted'] + acceptance['rejected']:
    present(decision['production_manifest'], decision['production_manifest_sha256'])
    product = obj(decision['production_manifest'])
    check(product['source_digest'] == OLD and product['asset_digest'] == ASSETS and product['session_id'] == decision['session_id'], 'Accepted/rejected production identity differs')
    directory = str(PurePosixPath(relative(decision['production_manifest'])).parent.parent)
    present(directory + '/events.json')
    present(directory + '/api_reads.jsonl')
    events = obj(directory + '/events.json')
    replies = [x['data'] for x in events if x['kind'] == 'plan_committed']
    check(bool(replies) and all(x.get('http_status') == 200 and x.get('raw_http_body') and x.get('raw_response') for x in replies), 'Missing actual raw model reply: ' + directory)
    content['raw_reply_checks'].append({'scene': decision['scene_id'], 'decision': decision['decision'], 'model_reply_count': len(replies), 'models': sorted({x['model'] for x in replies})})
    for key in ('raw_video', 'workflow_mp4', 'introduction_mp4'):
        row = product[key]
        path = relative(row['path'])
        if path in substitutions:
            check(substitutions[path]['original']['sha256'] == row['sha256'], 'Media substitution source differs')
        else:
            present(path, row['sha256'])
proof_results = []
for original, substitution in substitutions.items():
    proof = obj(substitution['proof'])
    check(original not in by_source, 'Oversized original unexpectedly packed: ' + original)
    for flag in ('passed', 'width_height_fps_decoded_count_start_duration_verified', 'start_pts_equal_within_1ms', 'copy_below_47MiB'):
        check(proof.get(flag) is True, 'Review-copy flag not true: ' + original + ':' + flag)
    check(proof['original'] == substitution['original'], 'Review original identity differs')
    check(proof['copy']['bytes'] < 47 * 1048576, 'Review copy >=47MiB')
    present(substitution['review_copy'], proof['copy']['sha256'], proof['copy']['bytes'])
    for item in proof['verification_evidence_files']:
        present(item['path'], item['sha256'], item['bytes'])
    for key in ('command_record', 'verification_command_record', 'legacy_verification_command_record'):
        record = obj(substitution[key])
        check(record['returncode'] == 0 and record['source_before']['digest'] == record['source_after']['digest'] in {OLD, FINAL}, 'Review execution failure/drift')
        check(record['assets_before']['digest'] == record['assets_after']['digest'] == ASSETS, 'Review asset drift')
    a, b = proof['original_probe'], proof['copy_probe']
    sa, sb = a['streams'][0], b['streams'][0]
    check(all(sa[k] == sb[k] for k in ('width', 'height', 'nb_read_frames')), 'Review dimensions/frame count differ')
    check(all(Fraction(sa[k]) == Fraction(sb[k]) for k in ('avg_frame_rate', 'r_frame_rate')), 'Review fps differs')
    times = []
    for key in ('decoded_original', 'decoded_copy'):
        summary = proof[key]
        decoded = obj(summary['full_frame_record'])
        t = [Decimal(x['best_effort_timestamp_time']) for x in decoded['frames']]
        check(len(t) == summary['decoded_frames'] == int(decoded['streams'][0]['nb_read_frames']), 'Full frame count differs')
        times.append(t)
    ta, tb = times
    max_error = max(abs((x - ta[0]) - (y - tb[0])) for x, y in zip(ta, tb))
    check(len(ta) == len(tb) and max_error <= Decimal('.002'), 'Review relative PTS differs')
    present(substitution['local_inventory'], substitution['local_inventory_sha256'])
    delivery = obj(substitution['local_inventory'])
    check(delivery['passed'] is True and delivery['source_digest'] == OLD and delivery['current_source_digest'] == FINAL, 'Local inventory source/completion differs')
    local = substitution['local_original']
    check(local in delivery['files'] and local['verified_size_and_sha256'] is True and local['sha256'] == proof['original']['sha256'] and local['bytes'] == proof['original']['bytes'], 'Local original delivery proof mismatch')
    proof_results.append({'original': original, 'copy': relative(substitution['review_copy']), 'decoded_frames': len(ta), 'maximum_relative_pts_error_s': str(max_error), 'local_original': local})
content['oversize_review_proofs'] = proof_results
inherited = obj(P + 'inherited_evidence_verification.json')
check(inherited['passed'] is True, 'Inherited proof failed')
for row in inherited['sealed_files']:
    present(row['path'], row['sha256'], row['bytes'])
present(inherited['run3_inventory'], inherited['run3_inventory_sha256'])
frozen = obj(inherited['run3_inventory'])
for row in frozen['files']:
    present(row['path'], row['sha256'], row['bytes'])
content['inherited_sealed_files'] = len(inherited['sealed_files'])
content['run3_frozen_files'] = len(frozen['files'])
content['run4_png_count'] = sum(x.startswith(P) and x.endswith('.png') for x in by_source)
content['run4_video_count'] = sum(x.startswith(P) and Path(x).suffix in {'.mp4', '.webm'} for x in by_source)
for name in ('FINAL_SUMMARY.md', 'SOURCE_PHASES.json', 'service_shutdown_resume03.json', 'owned_process_verification_final.json', 'shutdown_gpu_ports_resume03.json', 'local_delivery_logs/download_failed_attempt01.log', 'local_delivery_logs/download_success_attempt02.log'):
    if name.startswith('local_delivery_logs/'):
        continue  # Exact current log filenames are enumerated below, never guessed.
    present(P + name)
content['local_delivery_logs'] = [x for x in by_source if x.startswith(P + 'local_delivery_logs/')]
check(bool(content['local_delivery_logs']), 'Local delivery logs absent')
check(obj(P + 'owned_process_verification_final.json')['passed'] is True, 'Final process cleanup failed')
check(set(obj(P + 'shutdown_gpu_ports_resume03.json')['closed_ports']) == {8000, 8750, 8780}, 'Final ports differ')
content['runtime_client_build_sha256'] = coverage['runtime_client_repair']['isolated_client_build_sha256']
check(content['runtime_client_build_sha256'] == 'db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f', 'Runtime client identity differs')
check(status['privacy_reviewed'] is True, 'Package privacy flag is not true')
result = {'reviewer_session': '/root/cloud_provenance_review', 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'passed': not errors,
          'scope': 'Independent actual sealed ZIP byte/SHA256/member CRC32/SHA256/exact-set audit plus content identity checks; no extraction, project experiment or mutation of sealed input.',
          'errors': errors, 'upload_directory': str(BASE), 'archives_verified': len(archives), 'project_members_verified': len(manifest['files']),
          'index_members_verified': len(index['index_files']), 'members_verified': len(members), 'total_archive_bytes': sum(x['bytes'] for x in archives),
          'maximum_archive_bytes': max(x['bytes'] for x in archives), 'source_digest': source['digest'], 'asset_digest': assets['digest'],
          'index_inputs': {name: sha(BASE / name) for name in ('UPLOAD_INDEX.json', 'SHA256SUMS')}, 'content_checks': content, 'archives': archives, 'members': members,
          'local_original_physical_hash_check': 'Packaged original SHA/size matched the eight originals independently read during the preceding privacy/proof audit; packaged local-delivery rows verified here. Root reports its separate complete Windows hash verification; no duplicate Windows media read in this audit.'}
Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in {'members', 'archives', 'content_checks'}}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['passed'] else 1)
