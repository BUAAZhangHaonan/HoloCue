#!/usr/bin/env bash
source /home/hdd3/zhanghaonan/projects/holocue/.work/cloud_update_20260921/phase_env.sh
export RUN_DIR="$HOLOCUE_ROOT/runs/simulation/cloud_finish90_20260921_e67b574"
export HOLOCUE_STATE_PATH="$RUN_DIR/state.sqlite"
export HOLOCUE_HOST_MAX_USED_FRACTION=0.90
