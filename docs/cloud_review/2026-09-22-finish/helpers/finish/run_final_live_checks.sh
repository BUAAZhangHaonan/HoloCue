#!/usr/bin/env bash
set -e
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/phase_env.sh
"$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume02.py
"$APP_PYTHON" .work/cloud_update_20260921/record.py live_final "$APP_PYTHON" scripts/tests/live_twelve_scenes.py --out "$RUN_DIR/live_final"
"$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume02.py
"$APP_PYTHON" .work/cloud_update_20260921/record.py viewer_response_final "$APP_PYTHON" scripts/tests/audit_viewer_live.py --scenes optical_bench --out "$RUN_DIR/viewer_response_final"
"$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume02.py
"$APP_PYTHON" .work/cloud_update_20260921/record.py response_final "$APP_PYTHON" scripts/tests/audit_response_live.py --out "$RUN_DIR/response_final"
