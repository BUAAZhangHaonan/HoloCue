#!/usr/bin/env bash
set -e
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/phase_env.sh
scenes=("$@")
if [ ${#scenes[@]} -eq 0 ]; then
  scenes=(cnc_toolchange connector control_panel dig_site dive_fillstation drone_bench engine_bay infusion_ward optical_bench server_rack shelf_picking)
fi
for scene in "${scenes[@]}"; do
  "$APP_PYTHON" .work/cloud_resume_20260921/require_services.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "video_${scene}_01" "$APP_PYTHON" .work/cloud_video_20260921/capture_ui_videos.py --scenes "$scene" --out "$RUN_DIR/videos/${scene}_attempt01"
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "produce_video_${scene}_01" "$APP_PYTHON" .work/cloud_video_20260921/produce_videos.py --capture-root "$RUN_DIR/videos/${scene}_attempt01"
done
