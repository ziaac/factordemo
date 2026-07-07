#!/usr/bin/env bash
# Serve an open LLM with vLLM on an AMD Instinct MI300X (ROCm) as an
# OpenAI-compatible endpoint. This is the AMD compute backend that FACTOR's
# "AMD" engine calls for the Writer and Fact-checker steps.
#
# Verified on: AMD Instinct MI300X (gfx942), ROCm 7.2.4, Docker, Ubuntu.
# Endpoint: http://<host>:8000/v1  (model id: $SERVED_NAME)
#
# Usage:
#   export VLLM_API_KEY=your-secret        # required (protects the endpoint)
#   MODEL=Qwen/Qwen2.5-7B-Instruct ./vllm_mi300x.sh
#   # bigger, fits easily in 192 GB HBM3:
#   MODEL=Qwen/Qwen2.5-72B-Instruct SERVED_NAME=qwen2.5-72b MAXLEN=16384 ./vllm_mi300x.sh
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
SERVED_NAME="${SERVED_NAME:-qwen2.5-7b-instruct}"
MAXLEN="${MAXLEN:-8192}"
PORT="${PORT:-8000}"
: "${VLLM_API_KEY:?set VLLM_API_KEY (endpoint auth token)}"

docker rm -f factor-vllm 2>/dev/null || true

docker run -d --name factor-vllm \
  --restart unless-stopped \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16g \
  -p "${PORT}:8000" \
  -v /root/hf-cache:/root/.cache/huggingface \
  rocm/vllm:latest \
  bash -lc "vllm serve ${MODEL} \
      --host 0.0.0.0 --port 8000 \
      --served-model-name ${SERVED_NAME} \
      --max-model-len ${MAXLEN} \
      --gpu-memory-utilization 0.9 \
      --api-key ${VLLM_API_KEY}"

echo "Starting vLLM (${MODEL}) on ROCm/MI300X → http://0.0.0.0:${PORT}/v1"
echo "Follow logs:  docker logs -f factor-vllm"
echo "Health:       curl -H 'Authorization: Bearer \$VLLM_API_KEY' http://localhost:${PORT}/v1/models"
