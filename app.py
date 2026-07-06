"""FACTOR — Factual Agentic Content Orchestrator · Streamlit demo.

Entry point: sidebar + page routing. Simulates the 10-agent / 8-gate pipeline
end-to-end. MOCK mode needs no API key; LIVE mode (optional) calls Claude for
the Writer and Fact-checker steps and falls back to mock on any failure.

Design: Minimalist Swiss / International Typographic Style — strict grid,
black/white with a single red accent, Helvetica-style type, flush-left.
"""

from __future__ import annotations

import html
import random
import re
import time

import streamlit as st

from engine import mock, live
from engine import state_machine as sm

# --------------------------------------------------------------------------- #
# Page config + Swiss design system
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="FACTOR — Demo", page_icon="▮", layout="wide")

ACCENT = "#E30613"  # Swiss red

VERDICT_COLORS = {
    "supported": "#111111",
    "partial": "#6B6B6B",
    "unsupported": ACCENT,
    "contradicted": ACCENT,
    "pending": "#B0B0B0",
}

SWISS_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&display=swap');

html, body, [class*="css"], .stMarkdown, .stApp {{
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    color: #111111;
}}
.stApp {{ background: #FFFFFF; }}

/* Kill rounded corners / shadows — Swiss is flat and orthogonal */
.stButton>button, .stSelectbox div, .stExpander, div[data-testid="stExpander"] {{
    border-radius: 0 !important;
}}
.stButton>button {{
    border: 1px solid #111111; background: #FFFFFF; color: #111111;
    font-weight: 700; letter-spacing: .02em; text-transform: uppercase;
    font-size: .72rem; padding: .5rem 1.1rem;
}}
.stButton>button:hover {{ background: #111111; color: #FFFFFF; border-color: #111111; }}
.stButton>button[kind="primary"] {{ background: {ACCENT}; color: #FFFFFF; border-color: {ACCENT}; }}
.stButton>button[kind="primary"]:hover {{ background: #111111; border-color: #111111; }}

h1, h2, h3, h4 {{ letter-spacing: -0.02em; font-weight: 900; }}
h1 {{ font-size: 2.4rem; line-height: 1.02; }}

hr {{ border: none; border-top: 1px solid #111111; margin: 1.1rem 0; }}

.swiss-kicker {{
    text-transform: uppercase; letter-spacing: .22em; font-size: .68rem;
    font-weight: 700; color: {ACCENT}; margin: 0 0 .2rem 0;
}}
.swiss-rule-top {{ border-top: 3px solid #111111; padding-top: .5rem; }}

.pill {{
    display: inline-block; padding: .18rem .5rem; margin: 2px 3px 2px 0;
    font-size: .64rem; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase; border: 1px solid #111; white-space: nowrap;
}}
.pill-done {{ background: #111; color: #fff; border-color: #111; }}
.pill-active {{ background: {ACCENT}; color: #fff; border-color: {ACCENT}; }}
.pill-fail {{ background: #fff; color: {ACCENT}; border-color: {ACCENT}; border-width: 2px; }}
.pill-skip {{ background: #fff; color: #BBB; border-color: #DDD; border-style: dashed; }}
.pill-todo {{ background: #fff; color: #999; border-color: #DDD; }}

.cite {{
    color: {ACCENT}; font-weight: 700; font-size: .74em; vertical-align: super;
    text-decoration: none; border-bottom: 1px solid {ACCENT}; cursor: help;
}}
.verdict-tag {{
    display: inline-block; padding: .1rem .45rem; font-size: .64rem;
    font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
    border: 1px solid; margin-left: .4rem;
}}
.meta-mono {{ font-family: 'SF Mono','Consolas',monospace; font-size: .8rem; }}
.aidisc {{ border-left: 3px solid {ACCENT}; padding: .3rem 0 .3rem .8rem; color:#444; }}

section[data-testid="stSidebar"] {{ background: #F4F4F4; border-right: 1px solid #111; }}
[data-testid="stMetricValue"] {{ font-weight: 900; }}
.stDataFrame {{ border: 1px solid #111; }}
</style>
"""


# --------------------------------------------------------------------------- #
# State bootstrap
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _seed():
    return mock.load_seed()


def init_state():
    if "seed" not in st.session_state:
        st.session_state.seed = _seed()
    st.session_state.setdefault("workspace_id", st.session_state.seed["workspaces"][0].id)
    st.session_state.setdefault("current_run", None)
    st.session_state.setdefault("history", [])          # finished runs (dicts)
    st.session_state.setdefault("force_mock", False)
    st.session_state.setdefault("selected_topic", None)


def reset_demo():
    for k in ("current_run", "history", "selected_topic"):
        st.session_state.pop(k, None)
    init_state()


def mode_is_live() -> bool:
    return live.live_available() and not st.session_state.force_mock


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
_CITE_RE = re.compile(r"\[\[chunk:([a-zA-Z0-9\-]+)\]\]")


def cited_ids(body: str) -> list[str]:
    seen, out = set(), []
    for m in _CITE_RE.finditer(body or ""):
        cid = m.group(1)
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def render_body(body: str):
    """Render markdown body with [[chunk:id]] markers turned into red superscript tags."""
    def repl(m):
        cid = m.group(1)
        return f'<sup class="cite" title="Source {cid}">[{cid}]</sup>'
    st.markdown(_CITE_RE.sub(repl, body or ""), unsafe_allow_html=True)


def render_sources(body: str):
    """One expander per unique cited chunk — click a citation's source to view it."""
    ids = cited_ids(body)
    by_id = st.session_state.seed["chunks_by_id"]
    if not ids:
        return
    st.markdown('<div class="swiss-kicker">Sources — click to trace each citation</div>',
                unsafe_allow_html=True)
    for cid in ids:
        c = by_id.get(cid)
        if not c:
            st.error(f"[{cid}] — MISSING CHUNK (citation integrity error)")
            continue
        with st.expander(f"[{cid}]  {c.citation_short} — {c.title}"):
            st.markdown(f"> {c.content}")
            st.markdown(
                f'<span class="meta-mono">type: {c.source_type} · credibility: '
                f'{"■"*c.credibility}{"□"*(5-c.credibility)} ({c.credibility}/5) · '
                f'year: {c.year} · doi: {html.escape(c.doi)}</span>',
                unsafe_allow_html=True,
            )


def render_stepper(run):
    """Horizontal Swiss pill stepper over PIPELINE_STATES."""
    gate_failed = {e.step for e in run.events if e.status == "gate_failed"}
    fact_passed_later = any(e.step == "FACT_CHECKING" and e.status == "ok" for e in run.events)

    if run.state in sm.PIPELINE_STATES:
        cur = sm.PIPELINE_STATES.index(run.state)
    elif run.outcome == "rejected":
        # find the failing gate index
        fail_states = [s for s in sm.PIPELINE_STATES if s in gate_failed]
        cur = sm.PIPELINE_STATES.index(fail_states[0]) if fail_states else len(sm.PIPELINE_STATES)
    else:
        cur = len(sm.PIPELINE_STATES)

    pills = []
    for i, s in enumerate(sm.PIPELINE_STATES):
        label = sm.step_label(s)
        if s == "REVISING" and run.revision_count == 0:
            cls = "pill-skip"
        elif s in gate_failed and not (s == "FACT_CHECKING" and fact_passed_later):
            cls = "pill-fail"
        elif s == "FACT_CHECKING" and s in gate_failed and fact_passed_later:
            cls = "pill-done"  # failed once then passed
        elif run.state == s and run.outcome != "rejected":
            cls = "pill-active"
        elif i < cur:
            cls = "pill-done"
        else:
            cls = "pill-todo"
        pills.append(f'<span class="pill {cls}">{label}</span>')

    if run.outcome == "rejected":
        pills.append(f'<span class="pill pill-fail">REJECTED</span>')
    elif run.outcome == "published":
        pills.append(f'<span class="pill pill-active">PUBLISHED</span>')

    st.markdown('<div style="line-height:2.2">' + "".join(pills) + "</div>",
                unsafe_allow_html=True)


def verdict_tag(v: str) -> str:
    col = VERDICT_COLORS.get(v, "#111")
    return (f'<span class="verdict-tag" style="color:{col};border-color:{col}">'
            f'{v}</span>')


def kicker(text: str):
    st.markdown(f'<div class="swiss-kicker">{text}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar():
    seed = st.session_state.seed
    with st.sidebar:
        st.markdown('<div class="swiss-rule-top"></div>', unsafe_allow_html=True)
        st.markdown("### FACTOR")
        st.caption("Factual Agentic Content Orchestrator")

        names = {w.id: w.name for w in seed["workspaces"]}
        ws_id = st.selectbox(
            "Topic Workspace",
            options=list(names.keys()),
            format_func=lambda i: names[i],
            index=list(names.keys()).index(st.session_state.workspace_id),
        )
        if ws_id != st.session_state.workspace_id:
            st.session_state.workspace_id = ws_id
            st.session_state.selected_topic = None
            st.rerun()

        st.markdown("---")
        live_key = live.live_available()
        mode = "LIVE" if mode_is_live() else "MOCK"
        color = ACCENT if mode == "LIVE" else "#111"
        st.markdown(
            f'<span class="pill" style="background:{color};color:#fff;border-color:{color}">'
            f'MODE · {mode}</span>', unsafe_allow_html=True)
        if live_key:
            st.checkbox("Force MOCK (ignore API key)", key="force_mock")
            st.caption("API key detected. LIVE runs Writer + Fact-checker via Claude; "
                       "other steps stay mock. Failures fall back to mock.")
        else:
            st.caption("No ANTHROPIC_API_KEY — MOCK only. Set it in st.secrets or env "
                       "to enable LIVE Writer + Fact-checker.")

        st.markdown("---")
        page = st.radio("View", ["Workspace", "Run pipeline", "Article", "Dashboard"],
                        label_visibility="collapsed")
        st.markdown("---")
        if st.button("↺ Reset demo", use_container_width=True):
            reset_demo()
            st.rerun()
        st.caption("Simulation only — no DB, no Redis, no Node. "
                   "Production stack is TypeScript/BullMQ/Postgres.")
    return page


# --------------------------------------------------------------------------- #
# Page: Workspace
# --------------------------------------------------------------------------- #
def page_workspace():
    seed = st.session_state.seed
    ws = seed["workspaces_by_id"][st.session_state.workspace_id]
    topics = [t for t in seed["topics"] if t.workspace_id == ws.id]
    chunks = [c for c in seed["chunks"] if c.workspace_id == ws.id]

    kicker("Topic Workspace")
    st.markdown(f"# {ws.name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Domain", ws.domain.split("(")[0].strip())
    c2.metric("Languages", " → ".join(l.upper() for l in ws.languages))
    c3.metric("Corpus chunks", len(chunks))
    st.markdown(ws.description)
    with st.container(border=True):
        kicker("Credibility policy")
        st.markdown(ws.credibility_policy)

    st.markdown("---")
    kicker("Topics")
    rows = []
    for t in topics:
        ok = mock.gate1_ok(t)
        support = f"{t.related_chunk_count} chunks"
        status = "Ready" if ok else "Blocked · Gate 1"
        rows.append({
            "Title": t.title_en,
            "Category": t.category,
            "Genre": t.genre,
            "Priority": "■" * t.priority + "□" * (5 - t.priority),
            "Corpus support": support,
            "Status": status,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"Gate 1 threshold: a topic needs ≥ {sm.MIN_CHUNKS_GATE1} related chunks to run.")

    st.markdown("---")
    kicker("Corpus sources & credibility")
    srows = []
    for c in chunks:
        srows.append({
            "ID": c.id,
            "Source": c.title,
            "Author": c.citation_short,
            "Type": c.source_type,
            "Cred": "■" * c.credibility + "□" * (5 - c.credibility),
        })
    st.dataframe(srows, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Page: Run pipeline
# --------------------------------------------------------------------------- #
def _record_history(run):
    seed = st.session_state.seed
    t = seed["topics_by_id"][run.topic_id]
    entry = {
        "run": run,
        "topic_title": t.title_en,
        "workspace_id": run.workspace_id,
        "genre": run.genre,
    }
    st.session_state.history.append(entry)


def _animate_run(run, topic, ws, seed):
    placeholder = st.empty()
    lw = live.live_writer if mode_is_live() else None
    lf = live.live_factchecker if mode_is_live() else None
    for r in mock.iter_pipeline(run, topic, ws, seed, live_writer=lw, live_factchecker=lf):
        last = r.events[-1]
        with placeholder.container():
            render_stepper(r)
            symbol = "✕" if last.status == "gate_failed" else "→"
            st.markdown(f"**{symbol} {sm.step_label(last.step)}** — {last.note}")
        time.sleep(random.uniform(0.5, 1.3))
    placeholder.empty()


def page_run():
    seed = st.session_state.seed
    ws = seed["workspaces_by_id"][st.session_state.workspace_id]
    topics = [t for t in seed["topics"] if t.workspace_id == ws.id]

    kicker("Pipeline")
    st.markdown("# Run pipeline")

    labels = {t.id: f"{t.title_en}  ·  {t.related_chunk_count} chunks" +
              ("" if mock.gate1_ok(t) else "  ·  ⚠ weak corpus")
              for t in topics}
    tid = st.selectbox("Topic", options=[t.id for t in topics],
                       format_func=lambda i: labels[i])
    topic = seed["topics_by_id"][tid]

    col_a, col_b = st.columns([1, 3])
    with col_a:
        run_clicked = st.button("Run pipeline ▸", type="primary", use_container_width=True)
    with col_b:
        if topic.scenario == "revision":
            st.caption("Scenario: **revision** — v1 draft contains an overclaim → Gate 3 "
                       "rejects → REVISING → v2 passes.")
        elif topic.scenario == "weak_corpus":
            st.caption("Scenario: **weak corpus** — below the Gate 1 threshold; the run is "
                       "aborted before any draft is written.")
        else:
            st.caption("Scenario: **happy path** — grounded draft clears every gate.")

    if run_clicked:
        run = mock.start_run(topic, ws)
        _animate_run(run, topic, ws, seed)
        st.session_state.current_run = run
        if run.outcome in ("rejected",):
            _record_history(run)
        st.rerun()

    run = st.session_state.current_run
    if run is None or run.topic_id != tid:
        st.info("Select a topic and press **Run pipeline** to watch the state machine advance.")
        return

    st.markdown("---")
    render_stepper(run)

    # Rejected (Gate 1) --------------------------------------------------- #
    if run.outcome == "rejected" and run.state == "REJECTED":
        st.markdown("---")
        st.markdown(f'<div class="aidisc"><b>Run aborted.</b> {run.artifacts.get("reject_reason","")}</div>',
                    unsafe_allow_html=True)
        _render_audit(run)
        return

    _render_step_expanders(run, ws)

    # Human review gate --------------------------------------------------- #
    if run.outcome == "awaiting_review":
        st.markdown("---")
        kicker("Gate 7 · Human review")
        st.markdown("You are the editor. Approve to publish, or reject.")
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("✓ Approve", type="primary"):
            mock.finish_publish(run, True)
            _record_history(run)
            st.rerun()
        if c2.button("✕ Reject"):
            mock.finish_publish(run, False)
            _record_history(run)
            st.rerun()
    elif run.outcome == "published":
        st.success("Published. See the **Article** view for the final bilingual output.")
    elif run.outcome == "rejected":
        st.error("Rejected by editor at Gate 7.")

    _render_audit(run)


def _render_step_expanders(run, ws):
    a = run.artifacts
    st.markdown("---")
    kicker("Agent outputs")

    if "research_pack" in a:
        with st.expander("① Researcher — research pack (Gate 1 passed)", expanded=False):
            st.caption(f"Average credibility {a.get('avg_credibility')} · "
                       f"{len(a['research_pack'])} chunks selected")
            by_id = st.session_state.seed["chunks_by_id"]
            for item in a["research_pack"]:
                c = by_id.get(item["chunk_id"])
                st.markdown(f"**[{item['chunk_id']}]** · score `{item['score']}` · "
                            f"{c.citation_short if c else ''}")
                st.caption(item["reason"])

    if "outline" in a:
        with st.expander("② Outliner — outline (claim → chunk_id)"):
            for o in a["outline"]:
                if o.get("chunk_id"):
                    st.markdown(f"**{o['level']} · {o['heading']}**  "
                                f'<sup class="cite">[{o["chunk_id"]}]</sup>',
                                unsafe_allow_html=True)
                    st.caption(o["claim"])
                else:
                    st.markdown(f"**{o['level']} · {o['heading']}**")

    if "draft" in a:
        ver = a.get("draft_version", 1)
        with st.expander(f"③ Writer — draft v{ver} (Gate 2 · grounded, marker per claim)",
                         expanded=False):
            render_body(a["draft"])

    if "diff" in a and a["diff"]:
        with st.expander("↻ Revision — v1 → v2 diff", expanded=True):
            d = a["diff"]
            st.markdown(f"**Reason.** {d.get('reason','')}")
            st.markdown(f'<div style="border-left:3px solid {ACCENT};padding-left:.8rem">'
                        f'<s>{html.escape(d.get("v1_claim",""))}</s></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="border-left:3px solid #111;padding-left:.8rem">'
                        f'{html.escape(d.get("v2_claim",""))}</div>', unsafe_allow_html=True)

    if "claims" in a:
        with st.expander("④ Fact-checker — per-claim verdicts (Gate 3)", expanded=True):
            for c in a["claims"]:
                st.markdown(
                    f'<b>{c["id"]}</b> {verdict_tag(c["verdict"])} '
                    f'<sup class="cite">[{c["chunk_id"]}]</sup><br>'
                    f'<span style="color:#333">{html.escape(c["text"])}</span><br>'
                    f'<span style="color:#777;font-size:.85em">{html.escape(c.get("note",""))}</span>',
                    unsafe_allow_html=True)
                st.markdown("")

    if "bias" in a and a["bias"]:
        with st.expander("⑤ Bias & safety reviewer (Gate 4)"):
            st.metric("Bias score", f"{a['bias'].get('score','-')}/5")
            for n in a["bias"].get("notes", []):
                st.markdown(f"— {n}")

    if "translation_en" in a:
        with st.expander("⑥ Translator + QA (Gate 5)"):
            if a.get("translation_note"):
                st.caption(a["translation_note"])
            render_body(a["translation_en"])
            qa = a.get("qa", {})
            if qa:
                st.caption(f"QA: {qa.get('status','')} — {qa.get('notes','')}")

    if "meta" in a and a["meta"]:
        with st.expander("⑦ Meta / SEO (Gate 6 · schema validation)"):
            st.json(a["meta"])

    if "image" in a and a["image"]:
        with st.expander("⑧ Image — prompt + placeholder"):
            img = a["image"]
            st.caption("Prompt")
            st.code(img.get("prompt", ""), language=None)
            st.markdown(
                f'<div style="border:1px solid #111;height:120px;display:flex;'
                f'align-items:center;justify-content:center;color:#999;'
                f'font-size:.7rem;letter-spacing:.2em;text-transform:uppercase">'
                f'1200 × 630 · brand-safe illustration (placeholder)</div>',
                unsafe_allow_html=True)
            st.caption(f"alt (EN): {img.get('alt_en','')}")

    if a.get("live_used"):
        st.info("LIVE mode used Claude for: " + ", ".join(sorted(set(a["live_used"]))))
    for w in a.get("live_warnings", []):
        st.warning(w)


def _render_audit(run):
    st.markdown("---")
    kicker("Audit trail · run_events")
    rows = [{
        "Step": e.step, "Status": e.status, "Model": e.model,
        "In tok": e.input_tokens, "Out tok": e.output_tokens,
        "Latency ms": e.latency_ms, "Cost $": round(e.cost_usd, 3),
    } for e in run.events]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total cost", f"${run.total_cost:.2f}")
    c2.metric("Total tokens", f"{run.total_tokens:,}")
    c3.metric("Revisions", run.revision_count)


# --------------------------------------------------------------------------- #
# Page: Article
# --------------------------------------------------------------------------- #
def page_article():
    seed = st.session_state.seed
    published = [h for h in st.session_state.history if h["run"].outcome == "published"]
    kicker("Output")
    st.markdown("# Article")

    if not published:
        st.info("No published article yet. Run a topic through **Run pipeline** and approve it "
                "at Gate 7.")
        return

    labels = {i: f'{h["topic_title"]}  ·  {h["workspace_id"]}'
              for i, h in enumerate(published)}
    idx = st.selectbox("Published article", options=list(labels.keys()),
                       format_func=lambda i: labels[i], index=len(published) - 1)
    h = published[idx]
    run = h["run"]
    ws = seed["workspaces_by_id"][run.workspace_id]
    a = run.artifacts
    genre = run.genre

    label = (f'<span class="pill" style="background:{ACCENT};color:#fff;border-color:{ACCENT}">'
             f'AI-ASSISTED</span> <span class="pill">{genre.upper()}</span>')
    if ws.id == "parakita":
        label += ' <span class="pill">TIM PARAKITA</span>'
    st.markdown(label, unsafe_allow_html=True)

    locales = ws.languages
    tab_labels = {"id": "Indonesian", "en": "English"}
    tabs = st.tabs([tab_labels[l] for l in locales])

    for tab, loc in zip(tabs, locales):
        with tab:
            body = a["draft"] if loc == "id" else a.get("translation_en", a["draft"])
            meta = a.get("meta", {}).get(loc, {})
            st.markdown("---")
            render_body(body)
            st.markdown("---")
            render_sources(body)
            st.markdown("---")
            with st.container(border=True):
                kicker("Meta / SEO")
                if meta:
                    st.markdown(f"**{meta.get('meta_title','')}**")
                    st.caption(meta.get("meta_description", ""))
                    st.markdown(f'<span class="meta-mono">slug: /{meta.get("slug","")} · '
                                f'reading time: {meta.get("reading_time_min","-")} min · '
                                f'keywords: {", ".join(meta.get("keywords", []))}</span>',
                                unsafe_allow_html=True)
            disc = a.get("disclaimer_id" if loc == "id" else "disclaimer_en", "")
            if disc:
                st.markdown(f'<div class="aidisc">{html.escape(disc)}</div>',
                            unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Page: Dashboard
# --------------------------------------------------------------------------- #
def page_dashboard():
    kicker("Metrics")
    st.markdown("# Dashboard")
    hist = st.session_state.history

    if not hist:
        st.info("No runs yet this session. Metrics accumulate as you run pipelines.")
        return

    runs = [h["run"] for h in hist]
    n = len(runs)
    published = sum(1 for r in runs if r.outcome == "published")
    revised = sum(1 for r in runs if r.revision_count > 0)
    rejected = sum(1 for r in runs if r.outcome == "rejected")
    total_cost = sum(r.total_cost for r in runs)
    total_tokens = sum(r.total_tokens for r in runs)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runs", n)
    c2.metric("Published", published)
    c3.metric("Revised", revised)
    c4.metric("Rejected", rejected)

    c5, c6, c7 = st.columns(3)
    c5.metric("Session cost", f"${total_cost:.2f}")
    c6.metric("Avg cost / run", f"${(total_cost/n):.2f}" if n else "$0.00")
    c7.metric("Total tokens", f"{total_tokens:,}")
    st.caption("Cost figures are simulated from the whitepaper (~$0.85–1.00 per bilingual article).")

    st.markdown("---")
    kicker("Gate pass-rate")
    gate_map = {
        "Gate 1 · sources": "RESEARCHING",
        "Gate 3 · fact-check": "FACT_CHECKING",
        "Gate 4 · bias": "BIAS_REVIEW",
        "Gate 5 · cross-lingual": "TRANSLATION_QA",
        "Gate 6 · schema": "META_SEO",
        "Gate 7 · human": "HUMAN_REVIEW",
    }
    grows = []
    for gname, step in gate_map.items():
        reached = passed = 0
        for r in runs:
            evs = [e for e in r.events if e.step == step]
            if not evs:
                continue
            reached += 1
            # gate passes if the LAST event for this step is not a failure/rejection
            final = evs[-1].status
            if final in ("ok", "approved", "awaiting"):
                passed += 1
        rate = f"{(100*passed/reached):.0f}%" if reached else "—"
        grows.append({"Gate": gname, "Reached": reached, "Passed": passed, "Pass-rate": rate})
    st.dataframe(grows, use_container_width=True, hide_index=True)

    st.markdown("---")
    kicker("Audit log · run_events (all runs)")
    arows = []
    for h in hist:
        for e in h["run"].events:
            arows.append({
                "Topic": h["topic_title"],
                "Step": e.step, "Status": e.status, "Model": e.model,
                "Tokens": e.input_tokens + e.output_tokens,
                "Latency ms": e.latency_ms, "Cost $": round(e.cost_usd, 3),
            })
    st.dataframe(arows, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    st.markdown(SWISS_CSS, unsafe_allow_html=True)
    init_state()
    page = sidebar()
    if page == "Workspace":
        page_workspace()
    elif page == "Run pipeline":
        page_run()
    elif page == "Article":
        page_article()
    elif page == "Dashboard":
        page_dashboard()


if __name__ == "__main__":
    main()
