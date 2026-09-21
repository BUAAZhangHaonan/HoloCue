"""Ten real UI camera transitions on one paused live Shelf endpoint; no retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import httpx
import numpy as np
from playwright.sync_api import sync_playwright

from holocue.config import load_scene, root
from holocue.models import Pose
from holocue.spatial import transform_points
from scripts.tests.audit_bridge_live import Audit, check_environment, save
from scripts.tests.audit_viewer_live import CLIENT_READ, client_view_errors


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--generation', default='resume03')
    parser.add_argument('--expected-viewer-source-sha256', required=True)
    parser.add_argument('--api', default='http://127.0.0.1:8750')
    parser.add_argument('--viewer', default='http://127.0.0.1:8780')
    args = parser.parse_args()
    project = root().resolve()
    run = Path(os.environ['RUN_DIR']).resolve()
    output = args.out.resolve()
    if not output.is_relative_to(run) or output == run:
        raise ValueError('Use a new output directory strictly inside the recorded RUN')
    if float(os.environ.get('HOLOCUE_HOST_MAX_USED_FRACTION', '0')) != .90:
        raise ValueError('Keep the authorized 90% host memory policy')
    source = project/'src/holocue/viewer_scene.py'
    if digest(source) != args.expected_viewer_source_sha256:
        raise ValueError('Current application source is not the requested camera candidate')
    output.mkdir(parents=True, exist_ok=False)
    result = {'passed': False, 'scope': 'Real UI camera regression only; no Blender/native acceptance',
              'rounds_requested': 10, 'generation': args.generation,
              'viewer_source_sha256': digest(source), 'rounds': [], 'started_at': time.time()}
    audit = None
    try:
        subprocess.run([os.environ['APP_PYTHON'],
            str(project/'.work/cloud_finish90_20260921/service_generation.py'),
            'check', '--generation', args.generation], cwd=project, check=True)
        environment, blender = check_environment(output)
        save(output/'environment.json', environment)
        spec = load_scene('shelf_picking')
        save(output/'scene_contract.json', spec.model_dump(mode='json'))
        headers = {'Authorization': 'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
        with httpx.Client(base_url=args.api, headers=headers, timeout=30) as http, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = browser.new_context(viewport={'width': 1600, 'height': 1000})
            page = context.new_page()
            audit = Audit(page, http, spec, output, args, blender)
            try:
                audit.open()
                # Exercise the same manual selection before submitting the real
                # scene instruction; no model response or state is substituted.
                audit.select_view('inspection', 'BLUE')
                submitted = audit.send(spec.initial_instruction)
                save(output/'model_plan_snapshot.json', submitted)
                current = submitted['state']['queue'][0]
                assert (current['semantic']['target_id'], current['semantic']['action'],
                        current['semantic']['reference_id']) == ('RED', 'assemble', 'BASKET')
                assert any(task['semantic']['target_id'] == 'BLUE' and
                           task['semantic']['action'] == 'inspect_back'
                           for task in submitted['state']['queue'])
                obj = next(obj for obj in spec.objects if obj.object_id == 'RED')
                audit.wait_elapsed(current['task_id'], obj.interaction.duration_s)
                baseline = audit.control('暂停动作', 'paused')
                save(output/'paused_endpoint_snapshot.json', baseline)
                events = audit.read(f'/api/v1/sessions/{audit.sid}/events')
                save(output/'events_before.json', events)
                event_rows = events.get('events', []) if isinstance(events, dict) else events
                commits = [row['data'] for row in event_rows if row['kind'] == 'plan_committed']
                assert commits and all(row.get('raw_response') and row.get('backend_mode') == 'live'
                                       for row in commits), 'Missing raw live model reply'
                assert baseline['state']['backend_mode'] == 'live'
                # The original send() already preserved the raw event payload;
                # also retain the user/assistant history without rewriting it.
                save(output/'raw_model_history.json', baseline['state']['history'])
                page.screenshot(path=str(output/'paused_endpoint.png'), full_page=True)
                for number in range(1, 11):
                    directory = output/f'round_{number:02d}'
                    directory.mkdir()
                    row = {'round': number, 'views': []}
                    for mode, target in [('inspection', 'BLUE'), ('detail', 'BASKET')]:
                        view = audit.select_view(mode, target)
                        snapshot = audit.snapshot()
                        client = page.evaluate(CLIENT_READ)
                        check = client_view_errors(client, view)
                        stem = target+'_'+mode
                        save(directory/(stem+'_view.json'), view)
                        save(directory/(stem+'_snapshot.json'), snapshot)
                        save(directory/(stem+'_client.json'), client)
                        save(directory/(stem+'_camera_check.json'), check)
                        assert check['passed'], 'Actual browser/Python camera mismatch'
                        assert snapshot['state'] == baseline['state'], 'UI switching changed paused task state'
                        assert snapshot['display']['object_poses'] == baseline['display']['object_poses']
                        assert view['execution'] == 'paused' and not view['clock_advancing']
                        target_obj = next(obj for obj in spec.objects if obj.object_id == target)
                        inspection = mode == 'inspection' or any(
                            cue['target_id'] == target and cue['action'] == 'inspect_back'
                            for cue in snapshot['display']['cues'])
                        local = np.asarray(target_obj.interaction.inspect_point_local_m if inspection
                                           else target_obj.interaction.cue_offset_local_m, dtype=float)
                        if inspection:
                            local = local + np.asarray(target_obj.interaction.inspect_normal_local) * target_obj.interaction.inspect_cue_clearance_m
                        point = transform_points(Pose.model_validate(snapshot['display']['object_poses'][target]), local[None, :])[0]
                        position = np.asarray(check['client_position_in_viser_world'])
                        forward = np.asarray(check['client_target_in_viser_world'])-position
                        forward /= np.linalg.norm(forward)
                        depth = float((point-position)@forward)
                        evidence = {'mode': mode, 'target': target, 'actual_depth_m': depth,
                                    'focus_m': view['focus_m'], 'focus_point_m': point.tolist(),
                                    'positive_in_range': .05 <= depth <= 20,
                                    'focus_matches_contract': abs(view['focus_m']-depth) < 1e-6}
                        save(directory/(stem+'_focus_check.json'), evidence)
                        assert evidence['positive_in_range'], 'Contracted target is not in front/in focus range'
                        assert evidence['focus_matches_contract'], 'Actual focus differs from contracted plane'
                        page.screenshot(path=str(directory/(stem+'.png')), full_page=True)
                        row['views'].append(evidence)
                    result['rounds'].append(row)
                    save(output/'progress.json', result)
                assert not audit.errors, 'Browser emitted errors'
                save(output/'events_after.json', audit.read(f'/api/v1/sessions/{audit.sid}/events'))
                save(output/'final_snapshot.json', audit.snapshot())
                result.update(passed=True, session_id=audit.sid, browser_errors=audit.errors)
            except Exception:
                # Evidence only, never a retry of the failed UI action.
                try:
                    page.screenshot(path=str(output/'failure_page.png'), full_page=True)
                    if audit.sid:
                        save(output/'events_on_failure.json', audit.read(f'/api/v1/sessions/{audit.sid}/events'))
                except Exception as evidence_error:
                    save(output/'failure_evidence_error.json', {'error': str(evidence_error)})
                raise
            finally:
                context.close()
                browser.close()
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error),
                      session_id=audit.sid if audit else None,
                      browser_errors=audit.errors if audit else [])
        raise
    finally:
        result['finished_at'] = time.time()
        result['viewer_source_sha256_after'] = digest(source)
        if result['viewer_source_sha256_after'] != args.expected_viewer_source_sha256:
            result.update(passed=False, source_changed=True)
        save(output/'result.json', result)
    if not result['passed']:
        raise RuntimeError('Regression did not pass, including source identity')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
