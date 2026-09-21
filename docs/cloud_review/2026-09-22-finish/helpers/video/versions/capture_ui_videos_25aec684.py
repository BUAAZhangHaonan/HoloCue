"""Real Viser UI recordings; deliberately no Blender/native-bridge acceptance.

Invoke through the existing record.py/resource_guard in a fresh RUN_DIR.
The production Audit.workflow is inherited intact. Only evidence capture and
object-view evidence are specialized for page video rather than Blender pairs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

from holocue.config import list_scenes, load_scene, root
from scripts.tests.audit_bridge_live import Audit, check_environment, save
from scripts.tests.audit_viewer_live import CLIENT_READ, client_view_errors, ui_input


SCOPE = 'Real Viser UI workflow recording; no Blender capture or native bridge validation'
PROJECT = root().resolve()
REVIEW_HELPER = PROJECT / '.work/incoming/repair_review_20260920_25bcc909/HoloCue_Repair_Review_Kit/tools/review_bundle.py'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def provenance():
    spec = importlib.util.spec_from_file_location('video_review_bundle', REVIEW_HELPER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {'source': module.source_snapshot(PROJECT),
            'assets': module.asset_snapshot(PROJECT),
            'capture_script_sha256': sha256(__file__),
            'review_helper_sha256': sha256(REVIEW_HELPER)}


class VideoAudit(Audit):
    """Preserve the real workflow; replace only its native capture mechanism."""

    def __init__(self, *args, hold_seconds=2.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.hold_seconds = hold_seconds
        self.introduction = []
        self.timeline = []
        self.recording_started = time.monotonic()

    def mark(self, kind, **data):
        self.timeline.append({'elapsed_wall_s': time.monotonic()-self.recording_started,
                              'unix_time': time.time(), 'kind': kind, **data})
        save(self.out/'ui_timeline.json', self.timeline)

    def start_exporter(self):
        # Explicit UI-only evidence mode: no frame exporter and no Blender.
        self.mark('ui_evidence_scope', scope=SCOPE)

    def frozen_page(self, directory, snapshot, view):
        if snapshot['state']['execution'] not in ('paused', 'idle'):
            raise AssertionError('UI evidence capture requires a paused/idle real session')
        client = self.page.evaluate(CLIENT_READ)
        check = client_view_errors(client, view)
        save(directory/'client_before.json', client)
        save(directory/'client_camera_check.json', check)
        if not check['passed']:
            raise AssertionError('Actual page camera differs from the exported view')
        self.page.wait_for_timeout(350)
        first = self.browser_sample(directory, 0, view)
        self.settle_browser_capture(directory, view, first)
        if self.errors:
            raise AssertionError(json.dumps(self.errors, ensure_ascii=False))
        if self.snapshot()['state'] != snapshot['state']:
            raise AssertionError('Taking UI evidence changed committed task state')

    def capture(self, name, mode=None, target=None):
        directory = self.out/name
        directory.mkdir()
        if mode is not None:
            self.select_view(mode, target)
        # A real task panel makes the returned model text and current queue
        # legible. Switching a tab does not modify camera or domain state.
        self.tab('任务')
        snapshot = self.snapshot()
        view = self.view(revision=snapshot['state']['revision'], after=time.time())
        save(directory/'snapshot.json', snapshot)
        save(directory/'view_state.json', view)
        self.frozen_page(directory, snapshot, view)
        record = {'stage': name, 'scope': SCOPE, 'session_id': self.sid,
                  'revision': view['revision'], 'epoch': view['epoch'],
                  'target': view['selected_id'], 'view': view['view_mode'],
                  'directory': str(directory), 'page_image': str(directory/'viser.png'),
                  'page_sha256': sha256(directory/'viser.png')}
        self.stages.append(record)
        save(self.out/'stages.json', self.stages)
        self.mark('verified_ui_stage', stage=name, revision=view['revision'], target=view['selected_id'])
        self.page.wait_for_timeout(self.hold_seconds*1000)
        return snapshot, view

    def open(self):
        super().open()
        # New session, initial geometry, actual GUI views. No model reply has
        # been submitted at this point. Text comes only from this scene contract.
        initial = self.snapshot()
        if initial['state']['queue'] or initial['state']['completed']:
            raise AssertionError('Scene introduction must use a fresh session')
        views = [('workspace', None, self.spec.task_contract.setting)]
        selected = []
        for step in self.spec.task_contract.ordered_steps:
            for oid in (step.target_id, step.reference_id):
                if oid and oid not in selected:
                    selected.append(oid)
        if self.spec.task_contract.interrupt_target not in selected:
            selected.append(self.spec.task_contract.interrupt_target)
        objects = {obj.object_id: obj for obj in self.spec.objects}
        for oid in selected[:3]:
            obj = objects[oid]
            views.append(('detail', oid, obj.label+'。'+obj.description))
        for index, (mode, target, text) in enumerate(views):
            directory = self.out/f'intro_{index:02d}'
            directory.mkdir()
            self.select_view(mode, target)
            snapshot = self.snapshot()
            view = self.view(revision=snapshot['state']['revision'], after=time.time())
            save(directory/'snapshot.json', snapshot)
            save(directory/'view_state.json', view)
            self.frozen_page(directory, snapshot, view)
            self.introduction.append({'index': index, 'scene_id': self.spec.scene_id,
                'session_id': self.sid, 'view': mode, 'target': view['selected_id'],
                'image': str(directory/'viser.png'), 'image_sha256': sha256(directory/'viser.png'),
                'title': self.spec.title, 'description': text,
                'task_instruction': self.spec.initial_instruction,
                'text_source': 'scene.json title/task_contract.setting/objects/initial_instruction',
                'scope': 'Initial real Viser page, before submitting any model task'})
            save(self.out/'introduction.json', self.introduction)
            self.mark('introduction_view', index=index, mode=mode, target=target)
            self.page.wait_for_timeout(self.hold_seconds*1000)
        self.select_view('workspace', self.spec.objects[0].object_id)
        self.tab('任务')
        self.mark('workflow_start')

    def object_views(self):
        self.tab('显示响应')
        ui_input(self.page, '显示任务提示').uncheck()
        for obj in self.spec.objects:
            modes = ['detail', 'inspection'] if 'inspect_back' in obj.capabilities else ['detail']
            for mode in modes:
                name = f'object_{obj.object_id}_{mode}'
                self.capture(name, mode, obj.object_id)
                self.inspected.append({'object_id': obj.object_id, 'view': mode,
                    'page_image': str(self.out/name/'viser.png'),
                    'guidance_enabled': False, 'scope': SCOPE})
        self.tab('显示响应')
        ui_input(self.page, '显示任务提示').check()
        save(self.out/'viewed_objects.json', self.inspected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--scenes', nargs='+')
    parser.add_argument('--api', default='http://127.0.0.1:8750')
    parser.add_argument('--viewer', default='http://127.0.0.1:8780')
    parser.add_argument('--browser', type=Path)
    parser.add_argument('--hold-seconds', type=float, default=2.5)
    parser.add_argument('--service-check', type=Path,
                        default=PROJECT/'.work/cloud_resume_20260921/require_services.py')
    args = parser.parse_args()
    if not 1 <= args.hold_seconds <= 10:
        raise ValueError('Hold duration must be 1 to 10 seconds')
    args.out = args.out.resolve()
    environment, blender = check_environment(args.out)
    selected = args.scenes or [row['scene_id'] for row in list_scenes()]
    if len(selected) != len(set(selected)):
        raise ValueError('Duplicate scene IDs')
    for scene in selected:
        load_scene(scene)
    args.out.mkdir(parents=True, exist_ok=False)
    before = provenance()
    save(args.out/'provenance_before.json', before)
    save(args.out/'environment.json', environment)
    headers = {'Authorization': 'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    results = []
    with httpx.Client(base_url=args.api, headers=headers, timeout=10) as http, sync_playwright() as pw:
        launch = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
        if args.browser:
            launch['executable_path'] = str(args.browser)
        browser = pw.chromium.launch(**launch)
        try:
            for scene in selected:
                subprocess.run([os.environ['APP_PYTHON'], str(args.service_check)],
                               cwd=PROJECT, check=True)
                directory = args.out/scene
                directory.mkdir()
                context = browser.new_context(viewport={'width': 1600, 'height': 1000},
                    record_video_dir=str(directory/'raw_video'),
                    record_video_size={'width': 1600, 'height': 1000})
                page = context.new_page()
                video = page.video
                audit = VideoAudit(page, http, load_scene(scene), directory, args, blender,
                                   hold_seconds=args.hold_seconds)
                save(directory/'scene_contract.json', audit.spec.model_dump(mode='json'))
                outcome = {'scene_id': scene, 'passed': False, 'scope': SCOPE}
                try:
                    outcome = {**audit.workflow(), 'scope': SCOPE,
                        'inherited_workflow': 'scripts.tests.audit_bridge_live.Audit.workflow',
                        'playback': 'Existing UI workflow speed 0.1; model waits are recorded in full'}
                    audit.mark('workflow_completed')
                    audit.tab('任务')
                    page.wait_for_timeout(4000)
                except Exception as error:
                    workflow_passed = bool(outcome.get('passed'))
                    outcome.update({'passed': False,
                                    'workflow_assertions_passed_before_failure': workflow_passed,
                                    'session_id': audit.sid, 'error_type': type(error).__name__,
                                    'error': str(error), 'stages': audit.stages,
                                    'browser_errors': audit.errors})
                    save(directory/'failure.json', outcome)
                    try:
                        page.screenshot(path=str(directory/'failure_page.png'), full_page=True)
                    except Exception as screenshot_error:
                        save(directory/'failure_page_unavailable.json',
                             {'error_type': type(screenshot_error).__name__, 'error': str(screenshot_error)})
                    if audit.sid:
                        # Best-effort failure evidence never supplies fake state.
                        try:
                            save(directory/'events_on_failure.json', audit.read(f'/api/v1/sessions/{audit.sid}/events'))
                        except httpx.HTTPError as evidence_error:
                            save(directory/'events_unavailable.json', {'error': str(evidence_error)})
                finally:
                    # Playwright completes WebM only when its context closes.
                    # Do not hash/convert a still-open recording.
                    context.close()
                    raw = Path(video.path())
                    if not raw.is_file() or raw.stat().st_size == 0:
                        raise RuntimeError('Closed browser context did not flush its raw video')
                    outcome.update({'raw_video': str(raw), 'raw_video_sha256': sha256(raw),
                        'raw_video_bytes': raw.stat().st_size,
                        'source_digest': before['source']['digest'],
                        'asset_digest': before['assets']['digest'],
                        'scene_contract_sha256': sha256(directory/'scene_contract.json'),
                        'capture_script_sha256': sha256(__file__),
                        'context_closed_before_manifest': True,
                        'time_compression_applied': False})
                    save(directory/'manifest.json', outcome)
                    results.append(outcome)
                    save(args.out/'manifest.json', {'scope': SCOPE, 'scenes': results})
                if not outcome['passed']:
                    raise RuntimeError(f'{scene} UI workflow failed; remaining recordings not started')
        finally:
            browser.close()
            after = provenance()
            save(args.out/'provenance_after.json', after)
    if (before['source']['digest'] != after['source']['digest']
            or before['assets']['digest'] != after['assets']['digest']
            or before['capture_script_sha256'] != after['capture_script_sha256']):
        raise AssertionError('Source or assets changed during video capture')
    print(json.dumps({'passed': True, 'scenes': selected, 'scope': SCOPE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
