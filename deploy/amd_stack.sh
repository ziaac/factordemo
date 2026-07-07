#!/usr/bin/env bash
# Bring up FACTOR's full AMD Instinct MI300X inference stack (ROCm + Docker):
#   :8000  chat        — vLLM · Google Gemma 3 (Writer + Fact-checker)
#   :8001  embeddings  — sentence-transformers · Google EmbeddingGemma (Researcher / retrieval)
#   :8002  image       — diffusers · SDXL-Turbo (Image agent)
#
# All three share one MI300X (192 GB HBM3). GPU-memory split keeps them coexisting.
# Verified on: AMD Instinct MI300X (gfx942), ROCm 7.2.4, Docker.
#
# Gemma models are gated on Hugging Face — accept the license and set HFTOKEN.
# Usage:  export TOKEN=your-secret HFTOKEN=hf_... ; ./amd_stack.sh
set -euo pipefail
: "${TOKEN:?set TOKEN (shared endpoint auth token)}"
: "${HFTOKEN:?set HFTOKEN (Hugging Face read token with Gemma license accepted)}"
IMG=rocm/vllm:latest
HF="-e HF_TOKEN=${HFTOKEN} -e HUGGING_FACE_HUB_TOKEN=${HFTOKEN}"
GPU='--device=/dev/kfd --device=/dev/dri --group-add video --group-add render --security-opt seccomp=unconfined --ipc=host'
VOL='-v /root/hf-cache:/root/.cache/huggingface'

# 1) Chat (Gemma 3) — capped so the GPU is shared with embeddings + image.
docker rm -f factor-vllm 2>/dev/null || true
docker run -d --name factor-vllm --restart unless-stopped $GPU $HF --shm-size 16g -p 8000:8000 $VOL "$IMG" \
  bash -lc "vllm serve google/gemma-3-4b-it --host 0.0.0.0 --port 8000 \
    --served-model-name gemma-3-4b-it --max-model-len 8192 \
    --gpu-memory-utilization 0.35 --api-key ${TOKEN}"

# 2) Embeddings (EmbeddingGemma via sentence-transformers — vLLM ROCm lacks encoder attention).
docker rm -f factor-embed 2>/dev/null || true
docker run -d --name factor-embed --restart unless-stopped $GPU $HF --shm-size 8g -p 8001:8000 $VOL \
  -e EMBED_API_KEY=${TOKEN} -e EMBED_MODEL=google/embeddinggemma-300m \
  -v "$(dirname "$0")/embed_server.py":/app/embed_server.py "$IMG" \
  bash -lc "pip install -q --no-cache-dir -U sentence-transformers; python /app/embed_server.py"

# 3) Image (SDXL-Turbo via diffusers).
docker rm -f factor-sdxl 2>/dev/null || true
docker run -d --name factor-sdxl --restart unless-stopped $GPU --shm-size 8g -p 8002:8000 $VOL \
  -e IMG_API_KEY=${TOKEN} -v "$(dirname "$0")/sdxl_server.py":/app/sdxl_server.py "$IMG" \
  bash -lc "pip install -q --no-cache-dir diffusers accelerate transformers safetensors; python /app/sdxl_server.py"

echo "Bringing up chat :8000, embeddings :8001, image :8002 on the MI300X."
echo "Health:  curl -H 'Authorization: Bearer \$TOKEN' http://localhost:8000/v1/models"
echo "         curl http://localhost:8001/health   ;   curl http://localhost:8002/health"
