#!/usr/bin/env bash
set -e
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/phase_env.sh
"$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume01.py
"$APP_PYTHON" .work/cloud_update_20260921/record.py bridge_drone_bench_attempt02 "$APP_PYTHON" -m scripts.tests.audit_bridge_live --scenes drone_bench --out "$RUN_DIR/bridge_batches/drone_bench_attempt02"
"$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume01.py
"$APP_PYTHON" .work/cloud_update_20260921/record.py bridge_infusion_ward "$APP_PYTHON" -m scripts.tests.audit_bridge_live --scenes infusion_ward --out "$RUN_DIR/bridge_batches/infusion_ward"
for scene in engine_bay shelf_picking dig_site; do
  "$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume01.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "pairs_$scene" "$APP_PYTHON" .work/cloud_update_20260921/capture_changed_pairs.py --scene "$scene"
done
