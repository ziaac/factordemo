# FACTOR — Factual Agentic Content Orchestrator

**A self-hosted, multi-agent AI pipeline that produces hallucination-free, fully-cited
content — powered by Google Gemma 3 running live on an
[AMD Radeon PRO W7900](https://www.amd.com/en/products/graphics/workstations/radeon-pro/w7900.html)
(RDNA 3 · ROCm), with the whole stack also proven on an AMD Instinct MI300X.**

> AMD Developer Hackathon (ACT II) · Track 3 — Unicorn / Open Innovation.

**Live demo:** <https://factordemo.streamlit.app>  ·  **Entry point:** [`app.py`](app.py)  ·  **Agents & live engines:** [`engine/`](engine)

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
the demo video): grounded, correctly-cited drafts + per-claim verdicts, real cosine
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

## Where the code lives (main path)

| Path | What |
|---|---|
| [`app.py`](app.py) | **Entry point** — Streamlit UI, page routing, and the run loop that drives the pipeline. |
| [`engine/state_machine.py`](engine/state_machine.py) | The 16-state machine, the 10 agents, per-step model/gate metadata, Gate-1 threshold. |
| [`engine/mock.py`](engine/mock.py) | Deterministic pipeline generator (`iter_pipeline`) — seed → grounded run, with LIVE fallbacks. |
| [`engine/live.py`](engine/live.py) | Live engines over stdlib `urllib`: **AMD** (llama.cpp/vLLM) + **Fireworks**; Writer / Fact-checker / Translator prompts. |
| [`engine/retrieval.py`](engine/retrieval.py) | Real semantic retrieval (bge-m3 / qwen3-embedding) with a per-backend vector cache. |
| [`engine/imagegen.py`](engine/imagegen.py) | SDXL featured-image client (AMD). |
| [`data/`](data) | Seed corpus, topics, and canonical runs (JSON). |
| [`deploy/`](deploy) | Scripts to **serve the models on AMD** and keep them alive (see Operations). |
| [`docs/`](docs) | Technical whitepaper + design docs. |

The pipeline on screen is produced by `mock.iter_pipeline()` in [`engine/mock.py`](engine/mock.py); live inference is layered on top by passing the callables in [`engine/live.py`](engine/live.py) — so the **main code path is: `app.py` → `engine/mock.py` → `engine/live.py`**.

## External services & configuration

The app runs fully in **MOCK** mode with **no keys**. Live engines are enabled purely by environment variables / Streamlit secrets — nothing is hard-coded, no secret is committed.

| Service | Used for | Config keys |
|---|---|---|
| **AMD Radeon PRO W7900** (self-hosted · ROCm) | Writer, Fact-checker, Translator (Gemma 3 · llama.cpp), Researcher (bge-m3), Image (SDXL) | `AMD_BASE_URL`, `AMD_MODEL`, `AMD_API_KEY`, `AMD_EMBED_URL`, `AMD_IMAGE_URL` |
| **Fireworks AI** (hosted, approved Track-3 compute) | Writer, Fact-checker (`gpt-oss-120b`), Researcher (`qwen3-embedding-8b`) | `FIREWORKS_API_KEY` |
| **Streamlit Community Cloud** | Hosts the public demo | secrets set in the app dashboard |

The three AMD servers are **OpenAI-compatible** and reached over stdlib `urllib`. On the organizer's instance they are exposed publicly through the AnRui **`/spaces/<instance>/<port>/`** proxy — ports **8000** (chat), **7860** (embeddings), **8501** (image) — authenticated with a Bearer token. Template values: [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example).

## Operations — serving the models on the AMD instance

The organizer-provided **Radeon W7900** box is a JupyterLab container (ROCm, root, **no Docker**); everything persistent lives under **`/workspace`**:

```
/workspace
├── demo/                  # this repo (app + engine + deploy)
├── factor-venv/           # Python venv (ROCm torch, transformers, llama-cpp-python)
├── models/                # GGUF weights (gemma-3-27b-it-Q4_K_M.gguf)
├── hf-cache/              # HuggingFace cache (bge-m3, sdxl-turbo)
├── GEMMA_PATH             # file: absolute path of the downloaded GGUF
├── rebuild.sh             # build the whole env from scratch    (deploy/rebuild.sh)
├── start_all.sh           # bring up the 3 servers              (deploy/start_all.sh)
├── factor_watchdog.sh     # keep-alive: restart if any port drops (deploy/factor_watchdog.sh)
├── _arm_watchdog.py       # idempotent launcher for the watchdog  (deploy/arm_watchdog.py)
├── restart.sh             # one-shot recovery after a reboot      (deploy/restart.sh)
└── start_all.log / watchdog.log
```

**Build the environment from scratch** ([`deploy/rebuild.sh`](deploy/rebuild.sh)) — one command sets up
everything on a fresh instance: a venv, **ROCm torch 2.7.1** (`rocm6.3` wheels), `sentence-transformers` +
`diffusers`, **`llama-cpp-python` compiled with HIP** (`-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100`), downloads the
**Gemma-3-27B Q4_K_M GGUF** (~16 GB), and warms the **bge-m3** + **SDXL-Turbo** caches. HuggingFace assets are
pulled via **`hf-mirror.com`** (`HF_ENDPOINT`) because the instance is on a China network.

```bash
bash deploy/rebuild.sh      # first-time setup (compile + downloads)
bash deploy/start_all.sh    # then bring the servers up
```

**Serving recipe** — all three models on the single 48 GB GPU ([`deploy/start_all.sh`](deploy/start_all.sh), run inside `factor-venv`):

```bash
# chat — Gemma 3 27B via llama.cpp (ROCm/HIP)
python -m llama_cpp.server --model /workspace/models/gemma-3-27b-it-Q4_K_M.gguf \
  --n_gpu_layers -1 --n_ctx 8192 --host 0.0.0.0 --port 8000 --api_key factor-local --chat_format gemma &
# embeddings — bge-m3
EMBED_MODEL=BAAI/bge-m3 PORT=7860 EMBED_API_KEY=factor-local python /workspace/demo/deploy/embed_server.py &
# image — SDXL-Turbo
PORT=8501 IMG_MODEL=stabilityai/sdxl-turbo IMG_API_KEY=factor-local python /workspace/demo/deploy/sdxl_server.py &
```

**Resilience.** The organizer instance restarts often, so a small **watchdog** ([`deploy/factor_watchdog.sh`](deploy/factor_watchdog.sh)) polls all three ports every 30 s and re-runs `start_all.sh` if any becomes unreachable; it is armed automatically on kernel/server start via a Jupyter startup hook, and [`deploy/restart.sh`](deploy/restart.sh) brings everything back in one command after a reboot. This is why a transient GPU-endpoint outage only degrades a run to the deterministic fallback (the in-app *"external infrastructure, not a FACTOR error"* notice) instead of breaking it.

## Status (honest)

- ✅ **Real:** the full pipeline + 8 gates run interactively, and **Writer, Fact-checker, Translator,
  Researcher (embeddings), and Image run live on an AMD Radeon PRO W7900** (the same stack **proven
  on an AMD Instinct MI300X**, now offline). Every run produces the complete deliverable end-to-end —
  a **bilingual (EN → ID) article**, per-claim fact-check verdicts, inline **citations** traceable to
  the source chunk, **meta/SEO JSON**, a featured image, and a **CMS-ready article preview** — all
  shown in the UI.
- 🚧 **Seed / not-yet-live:** only the **corpus and topic backlog** are a curated seed set (not yet
  harvested live from Google Drive / open journals / OJS), and the final publish step renders that
  **CMS preview instead of writing to a real database/CMS**. Wiring live corpus ingestion (→ pgvector)
  and the actual CMS injection is the next build. See the whitepaper for the full architecture.

## More

- Detailed guide: [`README-demo.md`](README-demo.md)
- Serve-on-AMD scripts: [`deploy/`](deploy)
- Architecture & roadmap: [FACTOR Technical Whitepaper v1.2](docs/FACTOR-Technical-Whitepaper.pdf)
