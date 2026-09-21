"""One-shot RUN4 queue for closed raw recordings and completed workflow MP4s.

Run through record.py review_media_queue03 after the earlier review queue ends.
All closed productions are retained, including visually rejected attempts.
The separate VIDEO_ACCEPTANCE.json controls final presentation selection.
No service operation, encoder parameter change, failed-attempt retry or scheduler
is performed. The existing preparation helper records each encoding/verification.
"""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SCENES = {'blocks', 'cnc_toolchange', 'connector', 'control_panel', 'dig_site',
          'dive_fillstation', 'drone_bench', 'engine_bay', 'infusion_ward',
          'optical_bench', 'server_rack', 'shelf_picking'}
RUN_NAME = 'cloud_finish90_20260921_e67b574'
INTERVAL_SECONDS = 30


def argument(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


def scenes_argument(argv):
    if '--scenes' not in argv:
        return set(SCENES)
    result = set()
    for value in argv[argv.index('--scenes') + 1:]:
        if value.startswith('--'):
            break
        result.add(value)
    if not result or not result.issubset(SCENES):
        raise ValueError('Recorded producer has unexpected --scenes')
    return result


def main():
    root = Path(os.environ['HOLOCUE_ROOT']).resolve()
    run = Path(os.environ['RUN_DIR']).resolve()
    if run != root / 'runs/simulation' / RUN_NAME:
        raise ValueError('This queue is restricted to the explicitly authorized RUN4')
    if float(os.environ.get('HOLOCUE_HOST_MAX_USED_FRACTION', '0')) != .90:
        raise ValueError('Keep the existing explicit 90% guard ceiling')
    helper_path = root / '.work/cloud_finish90_20260921/prepare_review_videos.py'
    spec = importlib.util.spec_from_file_location('recorded_review_media_helper', helper_path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    helper_sha = helper.digest(helper_path)
    log_path = run / 'review_media_queue03.jsonl'
    summary_path = run / 'review_media_queue03.json'
    # A restart must not overwrite or append ambiguously to a previous queue run.
    with log_path.open('x', encoding='utf-8'):
        pass
    if summary_path.exists():
        raise FileExistsError('Existing queue summary is preserved')
    started = time.time()
    calls = 0
    last_observation = None

    def log(event, **values):
        row = {'time': time.time(), 'event': event, **values}
        with log_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)

    def finish(status, **values):
        result = {'status': status, 'started_at': started, 'finished_at': time.time(),
                  'run': str(run), 'helper': str(helper_path), 'helper_sha256': helper_sha,
                  'actual_helper_calls': calls, 'last_observation': last_observation, **values}
        with summary_path.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        log('finished', status=status, **values)

    def read_if_complete(path):
        try:
            return helper.read(path)
        except (FileNotFoundError, json.JSONDecodeError):
            # New manifests/execution files may be in their initial write. They
            # are not considered eligible until a subsequent complete read.
            return None

    def checked_file(value, sha, size=None, within=None):
        path = helper.checked_path(value, root)
        if within is not None and not path.is_relative_to(within):
            raise ValueError('Media escaped its actual attempt: ' + str(path))
        actual = helper.identity(path)
        if actual['sha256'] != sha or (size is not None and actual['bytes'] != size):
            raise RuntimeError('Closed/completed media size or SHA mismatch: ' + str(path))
        return path, actual

    def completed_services():
        return [name for name in ('model_resume02', 'api_resume02', 'viewer_resume02')
                if (run / (name + '_command') / 'execution.json').exists()]

    def index_entries():
        # Do not run concurrently with a manually started preparation helper.
        destination = run / 'review_videos'
        destination.mkdir(exist_ok=True)
        with (destination / '.prepare.lock').open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Another review preparation is active; queue must start after it ends') from None
            try:
                index = destination / 'index.json'
                rows = helper.read(index) if index.is_file() else []
                if len({row['original'] for row in rows}) != len(rows):
                    raise RuntimeError('Duplicate originals in review index')
                for row in rows:
                    original = helper.checked_path(row['original'], root)
                    copy = helper.checked_path(row['copy'], root)
                    if not original.is_relative_to(run) or not copy.is_relative_to(run / 'review_videos'):
                        raise RuntimeError('Review index contains evidence outside this one RUN')
                    helper.validate_existing(row, root)
                return {row['original']: row for row in rows}
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def discover():
        candidates = {}
        closed_raw = 0
        for manifest_path in sorted((run / 'videos').glob('*_attempt*/*/manifest.json')):
            capture = read_if_complete(manifest_path)
            if not capture or capture.get('context_closed_before_manifest') is not True:
                continue
            scene = capture.get('scene_id')
            directory = manifest_path.parent
            if scene not in SCENES or directory.name != scene:
                raise RuntimeError('Closed capture scene does not match its directory')
            raw, actual = checked_file(capture['raw_video'], capture['raw_video_sha256'],
                                       capture['raw_video_bytes'], directory / 'raw_video')
            if raw.suffix.lower() != '.webm':
                raise RuntimeError('Closed raw recording is not an original WebM')
            closed_raw += 1
            if actual['bytes'] >= helper.LIMIT:
                candidates[str(raw)] = {'scene_id': scene, 'kind': 'closed_original_webm',
                    'capture_passed': capture.get('passed') is True,
                    'capture_manifest': str(manifest_path), **actual}
        complete = {}
        for execution in sorted(run.glob('produce_video_*_command/execution.json')):
            record = read_if_complete(execution)
            if not record or record.get('returncode') != 0 or 'finished_at' not in record:
                continue
            argv = record['command']
            if not any(Path(value).name == 'produce_videos.py' for value in argv):
                raise RuntimeError('Producer command label does not invoke the expected tool')
            capture_root = Path(argument(argv, '--capture-root'))
            if not capture_root.is_absolute():
                capture_root = Path(record['cwd']) / capture_root
            capture_root = helper.checked_path(capture_root, root)
            if not capture_root.is_relative_to(run / 'videos'):
                raise RuntimeError('Producer output is outside RUN4 videos')
            media_name = argument(argv, '--media-dir-name') or 'produced'
            if media_name != 'produced' and not (media_name.startswith('produced_attempt')
                                                and media_name.removeprefix('produced_attempt').isdigit()):
                raise RuntimeError('Unexpected producer media directory')
            for scene in scenes_argument(argv):
                media = capture_root / scene / media_name
                manifest_path = media / 'manifest.json'
                if not manifest_path.is_file():
                    # A successful default producer can only process the scenes
                    # actually present in its capture batch, not all twelve.
                    if '--scenes' not in argv and not (capture_root / scene / 'manifest.json').is_file():
                        continue
                    raise RuntimeError('Successful producer lacks its complete manifest: ' + str(media))
                product = helper.read(manifest_path)
                capture = helper.read(capture_root / scene / 'manifest.json')
                if (product['scene_id'] != scene or capture.get('passed') is not True
                        or capture.get('context_closed_before_manifest') is not True
                        or product['session_id'] != capture['session_id']):
                    raise RuntimeError('Production does not match its successful closed capture')
                for key, record_key in [('source_digest', 'source'), ('asset_digest', 'assets')]:
                    if not (product[key] == capture[key] == record[record_key + '_before']['digest']
                            == record[record_key + '_after']['digest']):
                        raise RuntimeError('Producer/capture command identity mismatch')
                workflow = product['workflow_mp4']
                if workflow['speed'] != 1 or workflow['cuts'] != 0 or workflow['frame_timing_verification'].get('passed') is not True:
                    raise RuntimeError('Production lacks complete real-time frame verification')
                movie, actual = checked_file(workflow['path'], workflow['sha256'], within=media)
                if movie.suffix.lower() != '.mp4':
                    raise RuntimeError('Completed workflow product is not an MP4')
                intro = product['introduction_mp4']
                checked_file(intro['path'], intro['sha256'], within=media)
                complete.setdefault(scene, []).append(
                    {'manifest': str(manifest_path), 'command_record': str(execution)})
                if actual['bytes'] >= helper.LIMIT:
                    candidates[str(movie)] = {'scene_id': scene, 'kind': 'completed_workflow_mp4',
                        'production_manifest': str(manifest_path), 'command_record': str(execution), **actual}
        return candidates, complete, closed_raw

    log('started', helper_sha256=helper_sha, interval_seconds=INTERVAL_SECONDS,
        generation='resume02', scope='Closed originals/full productions only; no service operations or failed retries')
    try:
        while True:
            verified = index_entries()
            candidates, complete, closed_raw = discover()
            pending = [row for row in candidates.values() if Path(row['path']).relative_to(root).as_posix() not in verified]
            stopped = completed_services()
            missing = sorted(SCENES - set(complete))
            last_observation = {'complete_scenes': sorted(complete), 'missing_scenes': missing,
                'closed_successful_production_count': sum(len(rows) for rows in complete.values()),
                'closed_raw_count': closed_raw, 'eligible_large_media_count': len(candidates),
                'verified_review_count': len(verified), 'pending_originals': [row['path'] for row in pending],
                'completed_resume02_service_records': stopped}
            log('observation', **last_observation)
            if stopped and missing:
                finish('incomplete_services_ended', missing_scenes=missing, pending_originals=last_observation['pending_originals'])
                return 2
            if not pending and not missing:
                finish('passed', complete_scene_count=12, pending_original_count=0)
                return 0
            if pending:
                original = Path(pending[0]['path'])
                tag = hashlib.sha256(original.relative_to(root).as_posix().encode()).hexdigest()[:12]
                label = 'review_video_' + tag + '_a01'
                if ((run / 'review_videos' / label).exists() or any(
                        (run / (name + suffix)).exists()
                        for name in (label, label + '_legacy_verify', label + '_verify')
                        for suffix in ('_command', '_resources.jsonl'))):
                    raise RuntimeError('Unverified/failed attempt01 already exists; queue will not retry: ' + label)
                if helper.digest(helper_path) != helper_sha:
                    raise RuntimeError('Preparation helper changed during queue execution')
                command = [os.environ['APP_PYTHON'], str(helper_path), '--original', str(original), '--attempt', '01']
                log('call_started', command=command, original=pending[0], helper_sha256=helper_sha)
                calls += 1
                result = subprocess.run(command, cwd=root, check=False)
                log('call_finished', command=command, returncode=result.returncode)
                if result.returncode:
                    raise RuntimeError('Review preparation failed; no retry: return code ' + str(result.returncode))
                verified = index_entries()
                if original.relative_to(root).as_posix() not in verified:
                    raise RuntimeError('Preparation returned zero without a verified index entry')
                continue
            time.sleep(INTERVAL_SECONDS)
    except Exception as error:
        finish('failed', error_type=type(error).__name__, error=str(error))
        raise


if __name__ == '__main__':
    raise SystemExit(main())
