# FACTOR — Factual Agentic Content Orchestrator

**A self-hosted, multi-agent AI pipeline that produces hallucination-free, fully-cited
content — powered by Google Gemma 3 + EmbeddingGemma running live on an
[AMD Instinct MI300X](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
(ROCm + vLLM).**

> AMD Developer Hackathon (ACT II) · Track 3 — Unicorn / Open Innovation.

---

## AMD compute usage (how this project uses AMD)

FACTOR's cognitive agents run on **AMD GPUs** via the ROCm software stack:

- **GPU:** AMD Instinct **MI300X** (CDNA 3, `gfx942`), **192 GB HBM3**, **ROCm 7.2.4**.
- **Powered by Google Gemma on AMD:**
  - **Writer + Fact-checker** — **Gemma 3** (`google/gemma-3-4b-it`) via vLLM, OpenAI-compatible `:8000`.
    (Model-agnostic — swap to Gemma-3-12B/27B or a 70B on the 192 GB GPU by changing one env var.)
  - **Researcher** — real semantic retrieval via **EmbeddingGemma** (`google/embeddinggemma-300m`,
    `sentence-transformers`), `:8001`. Generation *and* retrieval both run on the Gemma family.
  - **Image agent** — **SDXL-Turbo** featured images (`diffusers`), `:8002`.
- **Bring the whole stack up:** [`deploy/amd_stack.sh`](deploy/amd_stack.sh)
  (+ [`deploy/embed_server.py`](deploy/embed_server.py), [`deploy/sdxl_server.py`](deploy/sdxl_server.py),
  [`deploy/vllm_mi300x.sh`](deploy/vllm_mi300x.sh)).
- **Verified on MI300X (gfx942, ROCm 7.2.4):** grounded, correctly-cited drafts + per-claim
  verdicts (~3 s/step), real cosine retrieval over the corpus, and generated featured images.
- The app calls every endpoint over stdlib `urllib` (no extra dependency) —
  [`engine/live.py`](engine/live.py), [`engine/retrieval.py`](engine/retrieval.py),
  [`engine/imagegen.py`](engine/imagegen.py). Select the **AMD · MI300X** engine in the sidebar.

## What FACTOR does

Every factual claim in every piece must be traceable to a verified source. A piece traverses a
16-state machine with **10 agents** and **8 anti-hallucination gates**
(source-sufficiency → grounded writing → **independent fact-check** → bias review →
cross-lingual QA → schema validation → human review → post-publish audit), with a capped
revision loop. Topic-agnostic, multi-workspace, bilingual (ID → EN).

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py          # MOCK mode works with no API key
```

To run the AMD engine, serve a model on an AMD Instinct host and configure the endpoint:

```bash
export VLLM_API_KEY=your-secret
MODEL=Qwen/Qwen2.5-7B-Instruct ./deploy/vllm_mi300x.sh
# then set AMD_BASE_URL / AMD_MODEL / AMD_API_KEY (see .streamlit/secrets.toml.example)
```

Containerized (linux/amd64 judging VM):

```bash
docker buildx build --platform linux/amd64 -t <registry>/factor-demo:latest --push .
```

## Status (honest)

- ✅ **Real:** full pipeline + 8 gates (interactive); **Writer + Fact-checker live on AMD MI300X**.
- 🚧 **Simulated for now:** the corpus and topic backlog are a curated seed set. Wiring a live
  corpus (Google Drive + journals → pgvector) and CMS publishing is the next build
  (~1–2 weeks for a real vertical slice). See the whitepaper for the full architecture.

## More

- Detailed guide: [`README-demo.md`](README-demo.md)
- Serve-on-AMD script: [`deploy/vllm_mi300x.sh`](deploy/vllm_mi300x.sh)
- Architecture & roadmap: [FACTOR Technical Whitepaper v1.2](docs/FACTOR-Technical-Whitepaper.pdf)
