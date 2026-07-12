#!/usr/bin/env bash
# From-scratch environment for the FACTOR AMD stack on a Radeon PRO W7900
# (RDNA3, gfx1100, ROCm) JupyterLab instance. China-network friendly: pulls
# HuggingFace assets via hf-mirror. Run once, then ./start_all.sh.
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/workspace/hf-cache
export ROCM_PATH=/opt/rocm PATH=/opt/rocm/bin:$PATH
export HIPCXX="$(/opt/rocm/bin/hipconfig -l)/clang"
export HIP_PATH="$(/opt/rocm/bin/hipconfig -R)"
mkdir -p /workspace/models /workspace/hf-cache
[ -f /workspace/demo/deploy/embed_server.py ] || { echo "!! /workspace/demo hilang — perlu upload ulang zip"; exit 1; }

echo ">>> [1/6] venv @ /workspace/factor-venv"
python3 -m venv /workspace/factor-venv
source /workspace/factor-venv/bin/activate
pip install -q -U pip huggingface_hub

echo ">>> [2/6] torch ROCm 2.7.1 (~2GB)"
pip install -q --no-cache-dir --index-url https://download.pytorch.org/whl/rocm6.3 torch==2.7.1

echo ">>> [3/6] sentence-transformers + diffusers"
pip install -q --no-cache-dir sentence-transformers diffusers accelerate transformers safetensors

echo ">>> [4/6] llama-cpp-python (HIP/gfx1100) — compile beberapa menit"
CMAKE_ARGS="-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100" FORCE_CMAKE=1 \
  pip install --no-cache-dir "llama-cpp-python[server]" 2>&1 | tail -2

echo ">>> [5/6] unduh Gemma-3-27B GGUF (~16GB) ke /workspace/models"
python - <<'PY'
from huggingface_hub import hf_hub_download
p=hf_hub_download("unsloth/gemma-3-27b-it-GGUF","gemma-3-27b-it-Q4_K_M.gguf",local_dir="/workspace/models")
open("/workspace/GEMMA_PATH","w").write(p); print("GEMMA:",p)
PY

echo ">>> [6/6] warm bge-m3 + sdxl-turbo ke cache /workspace/hf-cache"
python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("BAAI/bge-m3")
import torch
from diffusers import AutoPipelineForText2Image
AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
print("bge-m3 + sdxl-turbo cached")
PY
echo "=== REBUILD SELESAI — jalankan ./start_all.sh ==="
