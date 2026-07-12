#!/usr/bin/env bash
# Serve all three FACTOR models on one AMD Radeon PRO W7900 (RDNA3, gfx1100, ROCm).
# Ports: 8000 chat (Gemma 3 · llama.cpp/HIP) · 7860 embeddings (bge-m3) · 8501 image (SDXL-Turbo).
# OpenAI-compatible; all share the Bearer token below (mirror it in AMD_API_KEY / AMD_*_URL).
set -u
cd /workspace
export HF_ENDPOINT=https://hf-mirror.com          # China-network instance
export HF_HOME=/workspace/hf-cache
source /workspace/factor-venv/bin/activate 2>/dev/null || true   # built by rebuild.sh
TOKEN="${AMD_TOKEN:-factor-local}"
# rebuild.sh writes the downloaded weight path to /workspace/GEMMA_PATH
MODEL_GGUF="${MODEL_GGUF:-$(cat /workspace/GEMMA_PATH 2>/dev/null || echo /workspace/models/gemma-3-27b-it-Q4_K_M.gguf)}"

# chat — Gemma 3 27B via llama.cpp built with HIP (-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100)
curl -sf -o /dev/null http://127.0.0.1:8000/v1/models 2>/dev/null || \
  python -m llama_cpp.server --model "$MODEL_GGUF" --n_gpu_layers -1 --n_ctx 8192 \
    --host 0.0.0.0 --port 8000 --api_key "$TOKEN" --chat_format gemma > /tmp/llama.log 2>&1 &

# embeddings — bge-m3 (sentence-transformers on ROCm torch)
(exec 3<>/dev/tcp/127.0.0.1/7860) 2>/dev/null || \
  EMBED_MODEL=BAAI/bge-m3 PORT=7860 EMBED_API_KEY="$TOKEN" \
    python /workspace/demo/deploy/embed_server.py > /tmp/embed.log 2>&1 &

# image — SDXL-Turbo (diffusers on ROCm)
(exec 3<>/dev/tcp/127.0.0.1/8501) 2>/dev/null || \
  PORT=8501 IMG_MODEL=stabilityai/sdxl-turbo IMG_API_KEY="$TOKEN" \
    python /workspace/demo/deploy/sdxl_server.py > /tmp/sdxl.log 2>&1 &

echo "up: 8000(gemma-27b) 7860(bge-m3) 8501(sdxl)"
