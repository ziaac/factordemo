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

## MOCK vs LIVE

| Mode | When | Behaviour |
|------|------|-----------|
| **MOCK** (default) | No `ANTHROPIC_API_KEY` | Canonical outputs from the JSON seed. Deterministic, free, offline. Artificial 0.5–1.3 s/step so the pipeline feels alive. |
| **LIVE** (optional) | `ANTHROPIC_API_KEY` present | Only the **Writer** (`claude-sonnet-4-5`) and **Fact-checker** (`claude-opus-4-8`) call Claude, against the small seed corpus, `max_tokens ≤ 2000`. Every other step stays mock. Any API failure **falls back to mock with a warning** — it never crashes. |

Toggle **Force MOCK** in the sidebar to ignore a present key.

---

## Deploy to Streamlit Community Cloud

The flow is **push to GitHub → deploy on Streamlit Cloud**.

1. Push this folder as the repo root (see `../CLAUDE.md` for the layout note).
2. On <https://share.streamlit.io> → **New app** → pick the repo/branch.
3. **Main file path:** `app.py`  *(this folder is the repo root)*.
4. *(Optional, for LIVE mode)* **Advanced settings → Secrets:**
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
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
  live.py               # optional Claude calls (Writer, Fact-checker) + fallback
data/
  workspaces.json       # 2 workspaces
  topics.json           # 7 topics (happy / revision / weak-corpus scenarios)
  chunks.json           # 22 source chunks with credibility metadata
  canned_runs.json      # canonical agent outputs per runnable topic
requirements.txt
```

All claims in every seeded draft reference a `chunk_id` that exists in `chunks.json`
(verified: citation integrity holds across all drafts, translations, and claim reports).
