# FACTOR — Factual Agentic Content Orchestrator

**A self-hosted, multi-agent AI pipeline that produces hallucination-free, fully-cited
content — powered by Google Gemma 3 running live on an
[AMD Radeon PRO W7900](https://www.amd.com/en/products/professional-graphics/amd-radeon-pro-w7900.html)
(RDNA 3 · ROCm), with the whole stack also proven on an AMD Instinct MI300X.**

> AMD Developer Hackathon (ACT II) · Track 3 — Unicorn / Open Innovation.

---

## AMD compute usage (how this project uses AMD)

FACTOR's cognitive agents run on **AMD GPUs** via the ROCm software stack. Two AMD GPUs have
run this project — one is **live now**, the other is **proven but currently offline**.

### ● Live now — AMD Radeon PRO W7900 (RDNA 3, `gfx1100`, 48 GB, ROCm 7.2.1)

Every model in the live demo runs on a single **Radeon PRO W7900**, OpenAI-compatible:

- **Writer + Fact-checker** — Google **Gemma 3** served with **llama.cpp** built for **ROCm/HIP**
  (`-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100`). Model-agnostic — the app reports whichever model id
  is configured (`AMD_MODEL`); swap it in one env var.
- **Researcher** — real semantic retrieval via **bge-m3** (`sentence-transformers`), so citations
  are chosen by actual cosine similarity over the corpus, not a script.
- **Image agent** — **SDXL-Turbo** featured images (`diffusers`) on the same GPU.
- The app calls every endpoint over stdlib `urllib` (no extra dependency) —
  [`engine/live.py`](engine/live.py), [`engine/retrieval.py`](engine/retrieval.py),
  [`engine/imagegen.py`](engine/imagegen.py). Embedding + image servers:
  [`deploy/embed_server.py`](deploy/embed_server.py), [`deploy/sdxl_server.py`](deploy/sdxl_server.py).
- Select the **AMD · Radeon W7900** engine on the **② Run pipeline** page.

### ○ Proven, currently offline — AMD Instinct MI300X (CDNA 3, `gfx942`, 192 GB HBM3, ROCm 7.2.4)

The full stack was first built and **verified end-to-end on an AMD Instinct MI300X** (recorded in
the demo video): grounded, correctly-cited drafts + per-claim verdicts (~3 s/step), real cosine
retrieval, and generated featured images. There it ran **Gemma 3** (`google/gemma-3-4b-it`) via
**vLLM** plus **EmbeddingGemma** (`google/embeddinggemma-300m`) — generation *and* retrieval both on
the Gemma family — and **SDXL-Turbo** for images.

**This MI300X box is offline now due to limited access to the organizer-provided AMD GPU instance**,
so the live endpoints moved to the Radeon W7900 above. The MI300X bring-up scripts remain in the repo:
[`deploy/amd_stack.sh`](deploy/amd_stack.sh),
[`deploy/vllm_mi300x.sh`](deploy/vllm_mi300x.sh) (+ the shared
[`embed_server.py`](deploy/embed_server.py) / [`sdxl_server.py`](deploy/sdxl_server.py)). It scales to
Gemma-3-27B/70B on the 192 GB GPU by changing one env var.

> An optional **Fireworks AI** engine (`gpt-oss-120b` + `qwen3-embedding-8b`) is also wired in for
> Track 3's "AMD GPUs and/or Fireworks AI credits" compute option — set `FIREWORKS_API_KEY`.

## What FACTOR does

Every factual claim in every piece must be traceable to a verified source. A piece traverses a
16-state machine with **10 agents** and **8 anti-hallucination gates**
(source-sufficiency → grounded writing → **independent fact-check** → bias review →
cross-lingual QA → schema validation → human review → post-publish audit), with a capped
revision loop. Topic-agnostic, multi-workspace, bilingual (EN → ID).

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py          # MOCK mode works with no API key
```

To run on AMD, serve the models on your AMD GPU host and point the app at the endpoints:

```bash
# Radeon W7900 (RDNA 3) — chat via llama-cpp-python built with HIP:
CMAKE_ARGS="-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100" pip install llama-cpp-python
python -m llama_cpp.server --model <gemma-3.gguf> --n_gpu_layers -1 --chat_format gemma
python deploy/embed_server.py   # bge-m3   (embeddings)
python deploy/sdxl_server.py    # SDXL     (images)

# …or Instinct MI300X (CDNA 3) — chat via vLLM:
MODEL=google/gemma-3-4b-it ./deploy/vllm_mi300x.sh

# then set AMD_BASE_URL / AMD_MODEL / AMD_API_KEY (+ AMD_EMBED_URL / AMD_IMAGE_URL)
# see .streamlit/secrets.toml.example
```

Containerized (linux/amd64 judging VM):

```bash
docker buildx build --platform linux/amd64 -t <registry>/factor-demo:latest --push .
```

## Status (honest)

- ✅ **Real:** full pipeline + 8 gates (interactive); **Writer + Fact-checker + Researcher + Image
  live on an AMD Radeon PRO W7900**; the same stack **proven on an AMD Instinct MI300X** (now offline).
- 🚧 **Simulated for now:** the corpus and topic backlog are a curated seed set. Wiring a live
  corpus (Google Drive + journals → pgvector) and CMS publishing is the next build
  (~1–2 weeks for a real vertical slice). See the whitepaper for the full architecture.

## More

- Detailed guide: [`README-demo.md`](README-demo.md)
- Serve-on-AMD scripts: [`deploy/`](deploy)
- Architecture & roadmap: [FACTOR Technical Whitepaper v1.2](docs/FACTOR-Technical-Whitepaper.pdf)
