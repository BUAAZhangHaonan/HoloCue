#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SIZE="${1:-4B}"
case "$SIZE" in 4B|9B) ;; *) echo 'Only Qwen3.5-4B and Qwen3.5-9B are authorized'; exit 2;; esac
DEST="$PWD/models/Qwen3.5-$SIZE"
mkdir -p "$DEST" runs
FREE_KB=$(df -Pk "$PWD" | awk 'NR==2 {print $4}')
if (( FREE_KB < 50*1024*1024 )); then echo 'Require 50 GiB free disk before model preparation'; exit 3; fi
if [[ "${MODEL_SOURCE:-}" == 'ssh' ]]; then
  : "${SOURCE_SSH:?Set an existing authorized SSH alias for server 4028}"
  : "${SOURCE_MODEL_PATH:?Set the exact existing model directory under /home/g203-4028/Models}"
  case "$SOURCE_MODEL_PATH" in /home/g203-4028/Models/*) ;; *) echo 'Unexpected source root'; exit 4;; esac
  # Read-only source; do not add --delete or modify the remote model directory.
  rsync -a --partial --info=progress2 "$SOURCE_SSH:$SOURCE_MODEL_PATH/" "$DEST/"
elif [[ "${MODEL_SOURCE:-}" == 'hub' ]]; then
  command -v hf >/dev/null || { echo 'Install huggingface_hub in the isolated model environment to provide hf'; exit 5; }
  hf download "Qwen/Qwen3.5-$SIZE" --local-dir "$DEST" --max-workers 2
elif [[ "${MODEL_SOURCE:-}" == 'local' ]]; then
  : "${SOURCE_MODEL_PATH:?Set the exact local model directory}"
  rsync -a --partial "$SOURCE_MODEL_PATH/" "$DEST/"
else
  echo 'Choose MODEL_SOURCE=ssh, hub, or local explicitly. No automatic source switching.'; exit 6
fi
python scripts/validate_model_dir.py "$DEST" | tee "runs/model_${SIZE}_manifest.json"
