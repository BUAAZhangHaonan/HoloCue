"""Single fresh UI introduction probe; no workflow/model request and no deployment."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import httpx
from playwright.sync_api import sync_playwright
from holocue.config import load_scene
from scripts.tests.audit_bridge_live import check_environment, save


def main():
    root = Path(os.environ['HOLOCUE_ROOT'])
    output = Path(os.environ['RUN_DIR']) / 'hdr_capture_intro_probe'
    output.mkdir(exist_ok=False)
    helper = root / '.work/cloud_video_20260921/capture_ui_videos.py'
    spec = importlib.util.spec_from_file_location('capture_intro_under_test', helper)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    environment, blender = check_environment(output)
    save(output/'environment.json', environment)
    headers = {'Authorization': 'Bearer '+os.environ['HOLOCUE_API_KEY']} if os.environ.get('HOLOCUE_API_KEY') else {}
    start = time.monotonic()
    result = {'passed': False, 'scope': 'Fresh introduction only; no task workflow or model request',
              'capture_helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest()}
    with httpx.Client(base_url='http://127.0.0.1:8750', headers=headers, timeout=10) as http, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        context = browser.new_context(viewport={'width': 1600, 'height': 1000})
        audit = module.VideoAudit(context.new_page(), http, load_scene('connector'), output,
            SimpleNamespace(viewer='http://127.0.0.1:8780', api='http://127.0.0.1:8750'), blender, hold_seconds=1)
        try:
            audit.open()
            snapshot = audit.snapshot()
            save(output/'final_snapshot.json', snapshot)
            assert not snapshot['state']['queue'] and not snapshot['state']['completed']
            assert not audit.errors
            result.update(passed=True, session_id=audit.sid, introduction_count=len(audit.introduction),
                          browser_errors=audit.errors)
        except Exception as error:
            result.update(error_type=type(error).__name__, error=str(error), session_id=audit.sid)
            raise
        finally:
            context.close()
            browser.close()
            result['elapsed_seconds'] = time.monotonic()-start
            save(output/'result.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
