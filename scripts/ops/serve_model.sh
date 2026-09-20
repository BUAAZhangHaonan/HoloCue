#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPYCACHEPREFIX="$PWD/.work/pycache"
mkdir -p "$PYTHONPYCACHEPREFIX"
ENGINE="${ENGINE:-vllm}"
SIZE="${MODEL_SIZE:-4B}"
MODEL_PATH="${MODEL_PATH:-$PWD/models/Qwen3.5-$SIZE}"
GPUS="${GPUS:-1}"
MODEL_PYTHON="${MODEL_PYTHON:-$PWD/.venv-model/bin/python}"
GPU_FRACTION="${GPU_FRACTION:-0.70}"
[[ -x "$MODEL_PYTHON" ]] || { echo 'Missing isolated model environment'; exit 2; }
case "$SIZE" in 4B|9B) ;; *) exit 3;; esac
case "$GPUS" in 1|2) TP=1;; 1,2|2,1) TP=2;; *) echo 'Only physical GPUs 1,2 allowed'; exit 4;; esac
 .venv/bin/python scripts/ops/validate_model_dir.py "$MODEL_PATH"
COMMON=(--model "$MODEL_PATH")
if [[ "$ENGINE" == vllm ]]; then
 CMD=("$MODEL_PYTHON" -m vllm.entrypoints.openai.api_server --model "$MODEL_PATH"
      --served-model-name "Qwen/Qwen3.5-$SIZE" --host 127.0.0.1 --port 8000
      --tensor-parallel-size "$TP" --max-model-len 8192 --max-num-seqs 1
      --gpu-memory-utilization "$GPU_FRACTION" --reasoning-parser qwen3
      --default-chat-template-kwargs '{"enable_thinking":false}' --enforce-eager
      --limit-mm-per-prompt '{"image":1,"video":0}')
elif [[ "$ENGINE" == sglang ]]; then
 CMD=("$MODEL_PYTHON" -m sglang.launch_server --model-path "$MODEL_PATH"
      --served-model-name "Qwen/Qwen3.5-$SIZE" --host 127.0.0.1 --port 8000
      --tp-size "$TP" --context-length 8192 --max-running-requests 1
      --mem-fraction-static "$GPU_FRACTION" --reasoning-parser qwen3 --disable-cuda-graph)
else echo 'Unsupported ENGINE'; exit 5; fi
# Check version-specific help before running on the server. No flag is silently removed.
# vLLM 0.29.0 + flashinfer 0.6.18 JIT on this server: system nvcc is CUDA 12.1 and rejects
# the '--compress-mode=size' flag flashinfer emits, so the sampling op cannot be compiled.
# Documented adaptation: use vLLM's native sampler instead (VLLM_USE_FLASHINFER_SAMPLER=0).
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
.venv/bin/python scripts/guard/resource_guard.py --gpus "$GPUS" --gpu-fraction "$GPU_FRACTION" --log "${RUN_DIR:-runs/simulation}/model_resources.jsonl" \
 --host-reserve-gb 32 --rss-limit-gb 32 --min-gpu-free-gb 12 --execute -- "${CMD[@]}"
