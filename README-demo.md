# FACTOR — Demo (Streamlit)

Interactive, **simulation** demo of FACTOR (Factual Agentic Content Orchestrator):
a topic-agnostic, grounded content pipeline with **10 agents** and **8 anti-hallucination gates**.

> This is a demo, **not** the production system. Production is Node.js/TypeScript +
> BullMQ + PostgreSQL/pgvector (see `../docs/`). This app is pure Python/Streamlit and
> **simulates** the pipeline — no database, no Redis, no Node, no network required in MOCK mode.

Design: **Professional dark, Minimalist Swiss / International Typographic Style** — strict grid,
near-black canvas with light ink and a single refined red accent, Helvetica-style type.

---

## What this showcases (AMD Developer Hackathon · Track 3)

- **AMD GPU Cloud** — the live demo serves every model from an AMD **Radeon PRO W7900** cloud
  instance; the same stack was first proven on an **AMD Instinct MI300X** (AMD Developer Cloud,
  now offline due to limited instance access).
- **ROCm porting to AMD hardware** — chat on **llama.cpp built with HIP** for `gfx1100`, embeddings
  (`sentence-transformers`) and images (`diffusers`) on **ROCm PyTorch**, and **vLLM** on the
  MI300X (`gfx942`). No CUDA anywhere in the stack.
- **Google Gemma** — generation runs on **Gemma 3**; on the MI300X, retrieval also ran on
  **EmbeddingGemma**, so both cognition and retrieval stay in the Gemma family.
- **Fireworks AI** — an alternative fully-hosted engine (`gpt-oss-120b` + `qwen3-embedding-8b`),
  covering Track 3's "AMD GPUs and/or Fireworks AI credits" compute option.

---

## What it demonstrates

- **Topic Workspaces** — two seeded workspaces, **100 topic themes each** (200 total), prove the topic-agnostic design:
  - **PARAKITA Dental Health** (English → Indonesian, dental/oral-health, YMYL medical grounding)
  - **IT in Education** (English → Indonesian, EdTech: e-learning, LMS, gamification, AI in education, assessment)
  - Topics are *themes/subjects* — the article and its title are the generated output. Topics without ingested corpus sit in the backlog (blocked at Gate 1) until their sources are added.
- **The full state machine** advancing in real time:
  `QUEUED → PLANNING → RESEARCHING → OUTLINING → DRAFTING → FACT_CHECKING → BIAS_REVIEW →
  [REVISING] → TRANSLATING → TRANSLATION_QA → META_SEO → IMAGE_GEN → HUMAN_REVIEW →
  PUBLISHING → PUBLISHED` (with `REJECTED` / `NEEDS_ATTENTION`).
- **Three canonical scenarios:**
  1. **Happy path** — *How fluoride prevents cavities* — every claim grounded, clears all gates.
  2. **Revision** — *Root canal: when it is needed* — the v1 draft overstates the success rate
     (~100%); **Gate 3** (independent fact-check) flags it as *contradicted* → **REVISING** →
     v2 reports the sourced 83–93% range → passes.
  3. **Weak corpus** — *Bruxism in adolescents* — only 3 related chunks (< 5) → **Gate 1**
     aborts the run before any draft is written.
- **Traceable citations** — every claim carries a `[[chunk:id]]` marker; on the **Article**
  page each citation resolves to the exact source chunk (content + credibility + DOI).

---

## Run locally

Requires Python ≥ 3.11.

```bash
cd demo                     # this folder is the repo root on Streamlit Cloud
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). **No API key is needed** —
MOCK mode is fully functional and deterministic.

---

## Inference engines

Pick the engine on the **② Run pipeline** page. The **Writer** and **Fact-checker** steps run on
the chosen engine; on the AMD engine the **Researcher** (retrieval) and **Image** steps also run
live when their endpoints are configured. Every other step stays mock, and any live failure
**falls back to mock with a warning** — it never crashes.

| Engine | When available | Behaviour |
|--------|----------------|-----------|
| **MOCK** (default) | always | Canonical outputs from the JSON seed. Deterministic, free, offline. Artificial 0.5–1.3 s/step so the pipeline feels alive. |
| **AMD · Radeon W7900** ● live | `AMD_BASE_URL` set | Writer + Fact-checker + Translator on **Gemma 3** via **llama.cpp (ROCm/HIP)**; Researcher on **bge-m3** and Image on **SDXL-Turbo** when `AMD_EMBED_URL` / `AMD_IMAGE_URL` are set. OpenAI-compatible, called with stdlib `urllib`. |
| **FIREWORKS · gpt-oss-120b** | `FIREWORKS_API_KEY` set | Writer + Fact-checker on **`gpt-oss-120b`**; Researcher on **`qwen3-embedding-8b`**. Image stays placeholder. |

> The same AMD engine was first **proven end-to-end on an AMD Instinct MI300X** (`gfx942`,
> 192 GB HBM3, ROCm 7.2.4) running Gemma 3 + EmbeddingGemma via **vLLM** — recorded in the demo
> video. That box is offline now (limited organizer instance access), so live endpoints moved to
> the Radeon W7900.

### Serving the models on AMD

**Radeon PRO W7900 (RDNA 3, `gfx1100`) — live now:**

```bash
# chat: llama-cpp-python built with HIP for ROCm
CMAKE_ARGS="-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1100" pip install llama-cpp-python
python -m llama_cpp.server --model <gemma-3.gguf> --n_gpu_layers -1 --chat_format gemma  # :8000
python deploy/embed_server.py   # bge-m3   (embeddings)  :7860
python deploy/sdxl_server.py    # SDXL     (images)      :8501
```

**Instinct MI300X (CDNA 3, `gfx942`) — proven, via vLLM:**

```bash
MODEL=google/gemma-3-4b-it ./deploy/vllm_mi300x.sh        # :8000 (OpenAI-compatible)
# 192 GB HBM3 scales to a much bigger single-GPU model:
# MODEL=google/gemma-3-27b-it SERVED_NAME=gemma-3-27b MAXLEN=16384 ./deploy/vllm_mi300x.sh
```

Then point the app at the endpoints (env or `.streamlit/secrets.toml`, see
`.streamlit/secrets.toml.example`):

```toml
AMD_BASE_URL  = "http://YOUR_AMD_HOST:8000/v1"
AMD_MODEL     = "gemma-3-27b-it"
AMD_API_KEY   = "your-secret"
AMD_EMBED_URL = "http://YOUR_AMD_HOST:7860/v1"   # bge-m3 (W7900)
AMD_IMAGE_URL = "http://YOUR_AMD_HOST:8501"      # SDXL   (W7900)
# or the fully-hosted engine:
# FIREWORKS_API_KEY = "fw-..."
```

### Containerized (for graders / reproducible runs)

```bash
docker buildx build --platform linux/amd64 -t <registry>/factor-demo:latest --push .
docker run -p 8501:8501 \
  -e AMD_BASE_URL=http://<amd-host>:8000/v1 -e AMD_MODEL=gemma-3-27b-it \
  -e AMD_API_KEY=... <registry>/factor-demo:latest
```

---

## Deploy to Streamlit Community Cloud

The flow is **push to GitHub → deploy on Streamlit Cloud**.

1. Push this folder to GitHub — it is the repo root (`app.py` sits at the top level).
2. On <https://share.streamlit.io> → **New app** → pick the repo/branch.
3. **Main file path:** `app.py`  *(this folder is the repo root)*.
4. *(Optional, for a live engine)* **Advanced settings → Secrets:**
   ```toml
   # AMD engine (Radeon W7900 / Instinct MI300X):
   AMD_BASE_URL  = "http://YOUR_AMD_HOST:8000/v1"
   AMD_MODEL     = "gemma-3-27b-it"
   AMD_API_KEY   = "your-secret"
   AMD_EMBED_URL = "http://YOUR_AMD_HOST:7860/v1"   # bge-m3
   AMD_IMAGE_URL = "http://YOUR_AMD_HOST:8501"      # SDXL
   # or the fully-hosted Fireworks engine:
   # FIREWORKS_API_KEY = "fw-..."
   ```
5. Deploy. The repo must be public, or your Streamlit account linked to the private repo.

Everything uses relative paths and only `streamlit` + stdlib in MOCK mode, so it deploys
without modification; live engines are reached over stdlib `urllib`.

---

## Structure

```
app.py                  # entry: sidebar + routing + Swiss design system
engine/
  models.py             # dataclasses: Workspace, Topic, Chunk, Run, Claim, RunEvent
  state_machine.py      # states, per-step agent/model/gate metadata, thresholds
  mock.py               # seed loader + deterministic pipeline generator
  live.py               # live engines: AMD (llama.cpp/vLLM) + Fireworks, over urllib, with fallback
  retrieval.py          # real semantic retrieval (bge-m3 / qwen3-embedding) with vector cache
  imagegen.py           # SDXL image generation client (AMD)
data/
  workspaces.json       # 2 workspaces
  topics.json           # 200 topic themes (100 dental + 100 IT-in-education); runnable + backlog
  chunks.json           # 25 source chunks with credibility metadata (dental + edutech)
  canned_runs.json      # canonical agent outputs per runnable topic (happy / revision)
deploy/
  vllm_mi300x.sh        # serve Gemma 3 with vLLM on AMD Instinct MI300X (ROCm)
  amd_stack.sh          # bring up the full MI300X stack (chat + embed + image)
  embed_server.py       # bge-m3 embeddings server (sentence-transformers, ROCm)
  sdxl_server.py        # SDXL-Turbo image server (diffusers, ROCm)
Dockerfile              # containerize the Streamlit app (linux/amd64)
requirements.txt
```

All claims in every seeded draft reference a `chunk_id` that exists in `chunks.json`
(verified: citation integrity holds across all drafts, translations, and claim reports).
