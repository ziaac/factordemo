# FACTOR — Demo (Streamlit)

Interactive, **simulation** demo of FACTOR (Factual Agentic Content Orchestrator):
a topic-agnostic, grounded content pipeline with **10 agents** and **8 anti-hallucination gates**.

> This is a demo, **not** the production system. Production is Node.js/TypeScript +
> BullMQ + PostgreSQL/pgvector (see `../docs/`). This app is pure Python/Streamlit and
> **simulates** the pipeline — no database, no Redis, no Node, no network required in MOCK mode.

Design: **Professional dark, Minimalist Swiss / International Typographic Style** — strict grid,
near-black canvas with light ink and a single refined red accent, Helvetica-style type.

---

## What it demonstrates

- **Topic Workspaces** — two seeded workspaces prove the topic-agnostic design:
  - **PARAKITA Dental Health** (Indonesian → English, `article` genre, YMYL medical grounding)
  - **DevOps Tutorials** (English, `tutorial` genre, version-pinned to official docs)
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

Pick the engine in the sidebar. The **Writer** and **Fact-checker** steps run on the
chosen engine; every other step stays mock. Any live failure **falls back to mock with a
warning** — it never crashes.

| Engine | When available | Behaviour |
|--------|----------------|-----------|
| **MOCK** (default) | always | Canonical outputs from the JSON seed. Deterministic, free, offline. Artificial 0.5–1.3 s/step so the pipeline feels alive. |
| **AMD · MI300X** | `AMD_BASE_URL` set | Writer + Fact-checker run on an **AMD Instinct MI300X (ROCm + vLLM)** via an OpenAI-compatible endpoint. Called with stdlib `urllib` (no extra dependency), `max_tokens ≤ 2000`. |
| **CLAUDE LIVE** | `ANTHROPIC_API_KEY` set | Writer + Fact-checker call the hosted LLM API. |

### Running the AMD MI300X backend

FACTOR's "full self-hosted" profile runs open models on AMD GPUs. To serve one:

```bash
# on an AMD Instinct host (ROCm + Docker), e.g. AMD Developer Cloud:
export VLLM_API_KEY=your-secret
MODEL=Qwen/Qwen2.5-7B-Instruct ./deploy/vllm_mi300x.sh
# 192 GB HBM3 fits much bigger single-GPU models:
# MODEL=Qwen/Qwen2.5-72B-Instruct SERVED_NAME=qwen2.5-72b MAXLEN=16384 ./deploy/vllm_mi300x.sh
```

Then point the app at it (env or `.streamlit/secrets.toml`, see `.streamlit/secrets.toml.example`):

```toml
AMD_BASE_URL = "http://YOUR_MI300X_HOST:8000/v1"
AMD_MODEL    = "qwen2.5-7b-instruct"
AMD_API_KEY  = "your-secret"
```

Verified on AMD Instinct MI300X (gfx942), ROCm 7.2.4 — Writer + Fact-checker
returned grounded, correctly-cited output in ~3 s/step.

### Containerized (for graders / reproducible runs)

```bash
docker buildx build --platform linux/amd64 -t <registry>/factor-demo:latest --push .
docker run -p 8501:8501 \
  -e AMD_BASE_URL=http://<mi300x-host>:8000/v1 -e AMD_MODEL=qwen2.5-7b-instruct \
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
   # AMD MI300X engine:
   AMD_BASE_URL = "http://YOUR_MI300X_HOST:8000/v1"
   AMD_MODEL    = "qwen2.5-7b-instruct"
   AMD_API_KEY  = "your-secret"
   # or the hosted LLM API:
   # ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy. The repo must be public, or your Streamlit account linked to the private repo.

Everything uses relative paths and only `streamlit` + `anthropic` + stdlib, so it deploys
without modification.

---

## Structure

```
app.py                  # entry: sidebar + routing + Swiss design system
engine/
  models.py             # dataclasses: Workspace, Topic, Chunk, Run, Claim, RunEvent
  state_machine.py      # states, per-step agent/model/gate metadata, thresholds
  mock.py               # seed loader + deterministic pipeline generator
  live.py               # live engines: AMD/vLLM (urllib) + hosted LLM API, with fallback
data/
  workspaces.json       # 2 workspaces
  topics.json           # 7 topics (happy / revision / weak-corpus scenarios)
  chunks.json           # 22 source chunks with credibility metadata
  canned_runs.json      # canonical agent outputs per runnable topic
deploy/
  vllm_mi300x.sh        # serve an open model with vLLM on AMD Instinct MI300X (ROCm)
Dockerfile              # containerize the Streamlit app (linux/amd64)
requirements.txt
```

All claims in every seeded draft reference a `chunk_id` that exists in `chunks.json`
(verified: citation integrity holds across all drafts, translations, and claim reports).
