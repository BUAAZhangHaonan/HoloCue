"""Synthetic delivery-contract tests only; never encode, download or select real evidence."""
import ast
import contextlib
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

BASE = Path(__file__).resolve().parent
NAMES = ('prepare_delivery.py', 'download_videos.py', 'combine_introductions.py')
SCENES = ('blocks', 'cnc_toolchange', 'connector', 'control_panel', 'dig_site', 'dive_fillstation',
          'drone_bench', 'engine_bay', 'infusion_ward', 'optical_bench', 'server_rack', 'shelf_picking')
SOURCE, ASSETS, TOOL = 'a' * 64, 'b' * 64, 'c' * 64
FINAL_SOURCE = 'e' * 64


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def data(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value.encode())
    return {'path': str(path), 'sha256': digest(path)}


parsers = []
remote_program = None
for name in NAMES:
    text = (BASE / name).read_text(encoding='utf-8')
    tree = ast.parse(text)
    if name == 'download_videos.py':
        remote_program = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'REMOTE_PROGRAM' for target in node.targets))
        tree = ast.parse(remote_program)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'acceptance_entries')
    namespace = {'Path': Path, 'json': json, 'hashlib': hashlib}
    exec(compile(ast.Module(body=[function], type_ignores=[]), name, 'exec'), namespace)
    parsers.append(namespace['acceptance_entries'])

tests = []
selector_tree = ast.parse((BASE / 'prepare_delivery.py').read_text(encoding='utf-8'))
functions = [node for node in selector_tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {'option', 'generation_output_owners'}]
namespace = {'Path': Path}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'generation_owners', 'exec'), namespace)
mapping = namespace['generation_output_owners']({
    'shutdown_resume01_client_fix': {'command': ['python', 'service_generation.py', 'stop', '--generation', 'resume01']},
    'custom_stop_resume02': {'command': ['python', 'service_generation.py', 'stop', '--generation', 'resume02']},
    'ready_custom': {'command': ['python', 'service_generation.py', 'readiness', '--generation', 'resume02']}})
assert mapping['service_shutdown_resume01.json'] == 'shutdown_resume01_client_fix'
assert mapping['shutdown_gpu_ports_resume02.json'] == 'custom_stop_resume02'
assert mapping['readiness_resume02.json'] == 'ready_custom'
tests.append('Generation output ownership follows recorded argv despite custom recorder labels')
tmp_parent = Path(os.environ.get('TMPDIR', str(BASE)))
tmp_parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='delivery-contract-', dir=tmp_parent) as tmp:
    root = Path(tmp)
    run = root / 'runs/simulation/test_run'
    run.mkdir(parents=True)

    def command(label, argv, source_digest=SOURCE):
        record = {'command': argv, 'cwd': str(root), 'returncode': 0, 'finished_at': 'synthetic',
                  'source_before': {'digest': source_digest}, 'source_after': {'digest': source_digest},
                  'assets_before': {'digest': ASSETS}, 'assets_after': {'digest': ASSETS}}
        path = run / (label + '_command/execution.json')
        save(path, record)
        return path

    previous_source = data(root / '.work/cloud_finish90_20260921/camera_fix/before/viewer_scene.py', 'old camera source')
    current_source = data(root / 'src/holocue/viewer_scene.py', 'new atomic camera source')
    phase_manifest = {'schema_version': 1, 'current_source_digest': FINAL_SOURCE, 'asset_digest': ASSETS,
                      'phases': [], 'changed_source_paths': ['src/holocue/viewer_scene.py'],
                      'previous_file': previous_source['path']}
    for name, source_id, row in [('before_camera_atomic', SOURCE, previous_source), ('camera_atomic', FINAL_SOURCE, current_source)]:
        snapshot_path = run / (name + '_source.json')
        save(snapshot_path, {'digest': source_id, 'files': [{'path': 'src/holocue/viewer_scene.py',
             'bytes': Path(row['path']).stat().st_size, 'sha256': row['sha256']}]})
        phase_manifest['phases'].append({'phase_id': name, 'source_digest': source_id,
            'source_snapshot': str(snapshot_path), 'source_snapshot_sha256': digest(snapshot_path)})
    save(run / 'SOURCE_PHASES.json', phase_manifest)

    def produce(scene, attempt_name):
        attempt = run / 'videos' / (scene + '_' + attempt_name)
        directory = attempt / scene
        media = directory / 'produced'
        session = scene + '_' + attempt_name
        raw = data(directory / 'raw_video/raw.webm', 'synthetic raw ' + session)
        workflow = data(media / 'workflow_realtime.mp4', 'synthetic workflow ' + session)
        intro = data(media / 'scene_introduction.mp4', 'synthetic intro ' + session)
        picture = data(directory / 'intro_00/viser.png', 'synthetic screenshot')
        intro_sources = [{'image': picture['path'], 'image_sha256': picture['sha256']}]
        contract = {'scene_id': scene, 'title': scene, 'initial_instruction': 'synthetic unit test'}
        save(directory / 'scene_contract.json', contract)
        capture = {'scene_id': scene, 'session_id': session, 'passed': True,
                   'source_digest': SOURCE, 'asset_digest': ASSETS, 'capture_script_sha256': TOOL,
                   'context_closed_before_manifest': True, 'time_compression_applied': False,
                   'raw_video': raw['path'], 'raw_video_sha256': raw['sha256'],
                   'raw_video_bytes': Path(raw['path']).stat().st_size,
                   'scene_contract_sha256': digest(directory / 'scene_contract.json')}
        runtime = scene == 'connector' and attempt_name == 'attempt02'
        if runtime:
            capture.update(viser_client_build_sha256='d' * 64, stages=[])
            save(directory / 'served_client.json', {'installed_build_sha256': 'd' * 64,
                 'documents': [{'status': 200, 'sha256': 'd' * 64}]})
            opaque = {'passed': True, 'observations': [{'canvases': [{'opacity': '1', 'ancestor_opacities': ['1']}]}]}
            for relative in ('canvas_initial.json', 'intro_00/canvas_before.json', 'intro_00/canvas_after.json'):
                save(directory / relative, opaque)
        save(directory / 'manifest.json', capture)
        save(attempt / 'manifest.json', {'scenes': [capture]})
        for filename in ('provenance_before.json', 'provenance_after.json'):
            phase = {'source': {'digest': SOURCE}, 'assets': {'digest': ASSETS}, 'capture_script_sha256': TOOL}
            if runtime:
                phase['viser_client_build_sha256'] = 'd' * 64
            save(attempt / filename, phase)
        save(directory / 'introduction.json', intro_sources)
        save(directory / 'events.json', [])
        data(directory / 'api_reads.jsonl', '{}\n')
        proof = {'input': {'decoded_frames': 2}, 'output': {'decoded_frames': 2}, 'verification': {'passed': True}}
        save(media / 'frame_timing_verification.json', proof)
        for filename in ('raw_decoded_frames.json', 'workflow_decoded_frames.json'):
            save(media / filename, {'frames': [{}, {}], 'streams': [{'nb_read_frames': '2'}]})
        workflow.update(speed=1, cuts=0, frame_timing_verification=proof['verification'])
        intro['image_sources'] = intro_sources
        product = {'scene_id': scene, 'session_id': session, 'source_digest': SOURCE,
                   'asset_digest': ASSETS, 'capture_script_sha256': TOOL,
                   'raw_video': raw, 'workflow_mp4': workflow, 'introduction_mp4': intro}
        manifest = media / 'manifest.json'
        save(manifest, product)
        command('capture_' + session, ['python', 'capture_ui_videos.py', '--out', str(attempt), '--scenes', scene])
        command('produce_' + session, ['python', 'produce_videos.py', '--capture-root', str(attempt), '--scenes', scene])
        return manifest, product

    accepted = []
    products = {}
    for scene in SCENES:
        manifest, product = produce(scene, 'attempt02' if scene == 'connector' else 'attempt01')
        accepted.append({'scene_id': scene, 'production_manifest': str(manifest),
                         'production_manifest_sha256': digest(manifest), 'session_id': product['session_id'],
                         'decision': 'accepted', 'reason': 'Synthetic explicit visual decision'})
        products[scene] = product
    rejected_manifest, rejected_product = produce('connector', 'attempt01')
    newer_manifest, newer_product = produce('blocks', 'attempt99')
    rejected = [{'scene_id': 'connector', 'production_manifest': str(rejected_manifest),
                 'production_manifest_sha256': digest(rejected_manifest), 'session_id': rejected_product['session_id'],
                 'decision': 'rejected', 'reason': 'Synthetic visual defect, functionality remains passed'}]
    acceptance = {'schema_version': 1, 'accepted': accepted, 'rejected': rejected}
    acceptance_path = run / 'VIDEO_ACCEPTANCE.json'
    save(acceptance_path, acceptance)
    for parser in parsers:
        result = parser(acceptance_path, root, SCENES)
        assert result['accepted']['connector']['session_id'] == 'connector_attempt02'
        assert result['accepted']['blocks']['session_id'] == 'blocks_attempt01'
    tests.append('All three parsers select exact reviewed attempts, not newer successes')
    for mutation in ('missing_scene', 'duplicate_scene', 'wrong_session', 'wrong_hash', 'wrong_decision'):
        changed = json.loads(json.dumps(acceptance))
        if mutation == 'missing_scene':
            changed['accepted'].pop()
        elif mutation == 'duplicate_scene':
            changed['accepted'].append(changed['accepted'][0])
        elif mutation == 'wrong_session':
            changed['accepted'][0]['session_id'] = 'incorrect'
        elif mutation == 'wrong_hash':
            changed['accepted'][0]['production_manifest_sha256'] = '0' * 64
        else:
            changed['rejected'][0]['decision'] = 'accepted'
        save(acceptance_path, changed)
        for parser in parsers:
            try:
                parser(acceptance_path, root, SCENES)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid acceptance allowed: ' + mutation)
        tests.append('All three reject ' + mutation)
    save(acceptance_path, acceptance)
    collection_dir = run / 'videos/all_scenes_introduction'
    movie = data(collection_dir / 'twelve_scenes_introduction.mp4', 'synthetic collection')
    sources = [{'scene_id': scene, **products[scene]['introduction_mp4'], 'decoded_frames': 2,
                'source_digest': SOURCE, 'asset_digest': ASSETS} for scene in SCENES]
    collection_command = command('combine_introductions', ['python', 'combine_introductions.py'], FINAL_SOURCE)
    save(collection_dir / 'manifest.json', {'passed': True, 'acceptance_manifest_sha256': digest(acceptance_path),
        'source_digest': SOURCE, 'asset_digest': ASSETS, 'execution_source_digest': FINAL_SOURCE,
        'source_phase_manifest_sha256': digest(run / 'SOURCE_PHASES.json'),
        'outputs': [{'path': movie['path'], 'sha256': movie['sha256'], 'sources': sources,
                     'command_record': str(collection_command)}], 'decoded_input_frames': 24, 'decoded_output_frames': 24,
        'actual_duration_s': 12, 'expected_duration_s': 12})
    original_argv = sys.argv
    stream = io.StringIO()
    try:
        sys.argv = ['synthetic_inventory', str(run), str(acceptance_path)]
        with contextlib.redirect_stdout(stream):
            exec(compile(remote_program, 'download_remote_inventory', 'exec'), {})
    finally:
        sys.argv = original_argv
    inventory = json.loads(stream.getvalue())
    assert len(inventory['scenes']) == 12
    assert inventory['source_digest'] == SOURCE and inventory['current_source_digest'] == FINAL_SOURCE
    assert inventory['collection_execution']['source_before'] == FINAL_SOURCE
    tests.append('Old-phase twelve-media identity remains separate from final-phase collection execution and current source')
    assert next(row for row in inventory['scenes'] if row['scene_id'] == 'blocks')['session_id'] == 'blocks_attempt01'
    expected = {'rejected_attempts/connector_attempt01/connector/raw.webm',
                'rejected_attempts/connector_attempt01/connector/produced/workflow_realtime.mp4',
                'rejected_attempts/connector_attempt01/connector/produced/scene_introduction.mp4',
                'rejected_attempts/connector_attempt01/connector/produced/manifest.json'}
    assert expected <= {row['relative_path'] for row in inventory['files']}
    assert any(row['relative_path'].startswith('retained_attempts/blocks_attempt99') for row in inventory['files'])
    tests.append('Full synthetic remote inventory retains rejected raw and all old MP4/manifest, including small media')
    tests.append('Unselected newer functionality-pass production is retained without entering accepted playback')
    assert any(row['relative_path'] == 'connector/served_client.json' for row in inventory['files'])
    assert any(row['relative_path'] == 'connector/intro_00/canvas_after.json' for row in inventory['files'])
    tests.append('Accepted repaired-runtime served document and canvas evidence is included')
    canvas = run / 'videos/connector_attempt02/connector/canvas_initial.json'
    save(canvas, {'passed': True, 'observations': [{'canvases': [{'opacity': '.24', 'ancestor_opacities': ['1']}]}]})
    try:
        sys.argv = ['synthetic_inventory', str(run), str(acceptance_path)]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(remote_program, 'download_remote_inventory', 'exec'), {})
        except RuntimeError as error:
            assert 'opacity' in str(error)
        else:
            raise AssertionError('False opacity pass marker was accepted')
    finally:
        sys.argv = original_argv
    tests.append('Actual low canvas opacity is rejected even if its passed marker is true')

    phase_loaders = []
    for name in NAMES:
        tree = ast.parse(remote_program if name == 'download_videos.py' else (BASE / name).read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'load_source_phases')
        namespace = {'Path': Path, 'read': lambda p: json.loads(p.read_text()), 'digest': digest, 'sha256': digest}
        exec(compile(ast.Module(body=[function], type_ignores=[]), name, 'exec'), namespace)
        phase_loaders.append(namespace['load_source_phases'])
    for loader in phase_loaders:
        loaded, phases = loader(root, run)
        assert set(phases) == {SOURCE, FINAL_SOURCE}
    tests.append('All three helpers verify explicit two-phase snapshots and exact preserved old camera bytes')
    for mutation in ('snapshot_hash', 'extra_phase', 'unexpected_changed_path'):
        changed = json.loads(json.dumps(phase_manifest))
        if mutation == 'snapshot_hash':
            changed['phases'][0]['source_snapshot_sha256'] = '0' * 64
        elif mutation == 'extra_phase':
            changed['phases'].append(changed['phases'][0])
        else:
            changed['changed_source_paths'].append('other.py')
        save(run / 'SOURCE_PHASES.json', changed)
        for loader in phase_loaders:
            try:
                loader(root, run)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid source boundary allowed: ' + mutation)
        tests.append('All phase readers reject ' + mutation)
    save(run / 'SOURCE_PHASES.json', phase_manifest)
    functions = [node for node in selector_tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'option', 'stable_execution_phase', 'pair_output_owners'}]
    namespace = {'Path': Path, 'SCENES': SCENES}
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'phase_contract', 'exec'), namespace)
    stable = json.loads(collection_command.read_text())
    assert namespace['stable_execution_phase'](stable, phases, ASSETS) == FINAL_SOURCE
    for mutation in ('cross_phase', 'unknown_phase', 'asset_drift'):
        changed = json.loads(json.dumps(stable))
        if mutation == 'cross_phase':
            changed['source_before']['digest'] = SOURCE
        elif mutation == 'unknown_phase':
            changed['source_before']['digest'] = changed['source_after']['digest'] = 'f' * 64
        else:
            changed['assets_before']['digest'] = 'f' * 64
        try:
            namespace['stable_execution_phase'](changed, phases, ASSETS)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Invalid command phase accepted: ' + mutation)
        tests.append('Stable command identity rejects ' + mutation)
    pairs = {'pairs_shelf_picking': {'cwd': str(root), 'command': ['python', 'capture_changed_pairs.py', '--scene', 'shelf_picking']},
             'pairs_shelf_picking_attempt02': {'cwd': str(root), 'command': ['python', 'capture_changed_pairs_attempt.py',
                 '--scene', 'shelf_picking', '--out', str(run / 'changed_pairs/shelf_picking_attempt02')]}}
    owners = namespace['pair_output_owners'](pairs, root, run)
    assert owners[run / 'changed_pairs/shelf_picking']['owner'] == 'pairs_shelf_picking'
    assert owners[run / 'changed_pairs/shelf_picking_attempt02']['owner'] == 'pairs_shelf_picking_attempt02'
    tests.append('Old failed pair path and new explicit output remain separately owned')
    for mutation in ('duplicate_output', 'escaping_output'):
        changed = json.loads(json.dumps(pairs))
        changed['pairs_shelf_picking_attempt02']['command'][-1] = str(
            run / ('changed_pairs/shelf_picking' if mutation == 'duplicate_output' else '../escape'))
        try:
            namespace['pair_output_owners'](changed, root, run)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Invalid pair output accepted: ' + mutation)
        tests.append('Pair output ownership rejects ' + mutation)
    pairs['pairs_shelf_picking_attempt02']['command'][-1] = str(
        (run / 'changed_pairs/shelf_picking_attempt02').relative_to(root))
    third_out = run / 'changed_pairs/shelf_picking_attempt03'
    pairs['pairs_shelf_picking_attempt03'] = {'cwd': str(root), 'command': ['python', 'capture_changed_pairs_attempt.py',
        '--scene', 'shelf_picking', '--out', str(third_out)], 'returncode': 0}
    for name in ('pairs_shelf_picking', 'pairs_shelf_picking_attempt02'):
        pairs[name]['returncode'] = 1
    owners = namespace['pair_output_owners'](pairs, root, run)
    assert owners[run / 'changed_pairs/shelf_picking_attempt02']['owner'] == 'pairs_shelf_picking_attempt02'
    assert not (run / 'changed_pairs/shelf_picking_attempt02').exists()
    save(third_out / 'report.json', {'scene_id': 'shelf_picking', 'passed': True, 'stages': []})
    main_node = next(node for node in selector_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    result_node = next(node for node in main_node.body if isinstance(node, ast.FunctionDef) and node.name == 'current_result')
    pair_namespace = {'pair_outputs': owners, 'commands': pairs,
        'identity': lambda name: {'run_id': name, 'scope': 'current', 'command_record': name + '/execution.json'},
        'relative': lambda path: path.relative_to(root).as_posix(), 'read': lambda path: json.loads(path.read_text())}
    exec(compile(ast.Module(body=[result_node], type_ignores=[]), 'pair_results', 'exec'), pair_namespace)
    result = pair_namespace['current_result']('shelf_picking', 'pairs')
    failed = next(x for x in result['attempts'] if x['execution']['run_id'] == 'pairs_shelf_picking_attempt02')
    assert failed['status'] == 'no_output_directory' and failed['passed'] is False and not failed['completed_images']
    passed = next(x for x in result['attempts'] if x['execution']['run_id'] == 'pairs_shelf_picking_attempt03')
    assert passed['passed'] is True and result['passed_on_final_source'] is True
    tests.append('Relative-output preflight rejection without a directory is retained without inferring camera/native failure')
    tests.append('Absolute-output third pair attempt is independently owned and supplies its real final-source result')

    review_functions = [node for node in selector_tree.body if isinstance(node, ast.FunctionDef)
                        and node.name in {'read', 'sha256', 'review_copy_visual_frames'}]
    review_namespace = {'Path': Path, 'json': json, 'hashlib': hashlib,
                        'Decimal': Decimal, 'MEDIA': {'.webm', '.mp4'}}
    exec(compile(ast.Module(body=review_functions, type_ignores=[]), 'review_copy_frames', 'exec'), review_namespace)
    review_directory = root / '.work/cloud_finish90_20260921'
    copy_manifest = review_directory / 'review_copy_visual_manifest.json'
    paired = {'media_pairs': [], 'frames': []}
    selected, oversized = set(), set()
    for number in range(2):
        pair_id = 'pair_' + str(number)
        pair = {'pair_id': pair_id, 'requested_times_s': [10, 20]}
        for role in ('original', 'copy'):
            media = data(run / 'review_videos' / pair_id / (role + '.mp4'), role + pair_id)
            media['bytes'] = Path(media['path']).stat().st_size
            pair[role] = media
            (oversized if role == 'original' else selected).add(Path(media['path']).relative_to(root).as_posix())
            for time in pair['requested_times_s']:
                frame = data(review_directory / 'review_copy_inputs' / pair_id / f'{role}_{time}.png',
                             f'synthetic PNG contract {pair_id} {role} {time}')
                paired['frames'].append({'pair_id': pair_id, 'role': role,
                    'local_relative_path': str(Path(frame['path']).relative_to(review_directory)),
                    'sha256': frame['sha256'], 'source_remote_path': media['path'],
                    'source_video_sha256': media['sha256'], 'requested_time_s': time,
                    'viewed_extracted_frame': True})
        paired['media_pairs'].append(pair)

    def verify_review_file(path, expected_hash, size=None):
        path.relative_to(root)
        assert not any(part.is_symlink() for part in (path, *path.parents))
        if digest(path) != expected_hash or (size is not None and path.stat().st_size != size):
            raise RuntimeError('Evidence identity changed')

    def validate_review():
        return review_namespace['review_copy_visual_frames'](
            root, run, review_directory, selected, oversized, verify_review_file)

    save(copy_manifest, paired)
    assert len(validate_review()) == 8
    tests.append('Review-copy selection includes exactly eight explicit PNGs with selected copies and verified local originals')
    for mutation in ('parent_escape', 'outside_png_directory', 'frame_hash', 'media_hash',
                     'frame_source_hash', 'unselected_source', 'missing_frame', 'duplicate_frame'):
        changed = json.loads(json.dumps(paired))
        if mutation == 'parent_escape':
            changed['frames'][0]['local_relative_path'] = '../escape.png'
        elif mutation == 'outside_png_directory':
            changed['frames'][0]['local_relative_path'] = 'other.png'
        elif mutation == 'frame_hash':
            changed['frames'][0]['sha256'] = '0' * 64
        elif mutation == 'media_hash':
            changed['media_pairs'][0]['original']['sha256'] = '0' * 64
        elif mutation == 'frame_source_hash':
            changed['frames'][0]['source_video_sha256'] = '0' * 64
        elif mutation == 'unselected_source':
            oversized.clear()
        elif mutation == 'missing_frame':
            changed['frames'].pop()
        else:
            changed['frames'].append(changed['frames'][0])
        save(copy_manifest, changed)
        try:
            validate_review()
        except (RuntimeError, ValueError):
            pass
        else:
            raise AssertionError('Invalid review-copy manifest allowed: ' + mutation)
        oversized.update(Path(pair['original']['path']).relative_to(root).as_posix()
                         for pair in paired['media_pairs'])
        tests.append('Review-copy selection rejects ' + mutation)
    save(copy_manifest, paired)
print(json.dumps({'passed': True, 'checks': tests, 'scope': 'Synthetic delivery contracts only; no real evidence selection, transfer, media encoding/decoding or experiment',
                  'helper_sha256': {name: digest(BASE / name) for name in NAMES}}, indent=2))
