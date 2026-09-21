#!/usr/bin/env bash
set -e
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_finish90_20260921/phase_env.sh
for scene in "$@"; do
  attempt=01
  if [ "$scene" = connector ]; then attempt=02; fi
  "$APP_PYTHON" .work/cloud_finish90_20260921/require_services_resume02.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "video_${scene}_${attempt}" "$APP_PYTHON" .work/cloud_video_20260921/capture_ui_videos.py --scenes "$scene" --out "$RUN_DIR/videos/${scene}_attempt${attempt}" --service-check .work/cloud_finish90_20260921/require_services_resume02.py
  "$APP_PYTHON" .work/cloud_update_20260921/record.py "produce_video_${scene}_${attempt}" "$APP_PYTHON" .work/cloud_video_20260921/produce_videos.py --capture-root "$RUN_DIR/videos/${scene}_attempt${attempt}"
done
