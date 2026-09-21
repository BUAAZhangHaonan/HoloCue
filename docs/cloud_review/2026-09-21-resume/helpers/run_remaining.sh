#!/usr/bin/env bash
set -e
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_resume_20260921/phase_env.sh
for scene in cnc_toolchange connector control_panel dig_site dive_fillstation drone_bench infusion_ward; do
  "$APP_PYTHON" .work/cloud_resume_20260921/require_services.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "bridge_$scene" "$APP_PYTHON" -m scripts.tests.audit_bridge_live --scenes "$scene" --out "$RUN_DIR/bridge_batches/$scene"
done
for scene in engine_bay shelf_picking dig_site; do
  "$APP_PYTHON" .work/cloud_resume_20260921/require_services.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "pairs_$scene" "$APP_PYTHON" .work/cloud_update_20260921/capture_changed_pairs.py --scene "$scene"
done
