"""FACTOR — Factual Agentic Content Orchestrator · Streamlit demo.

Entry point: sidebar + page routing. Simulates the 10-agent / 8-gate pipeline
end-to-end. MOCK mode needs no API key; LIVE mode (optional) calls the hosted
LLM API for the Writer and Fact-checker steps and falls back to mock on any failure.

Design: Minimalist Swiss / International Typographic Style — strict grid,
black/white with a single red accent, Helvetica-style type, flush-left.
"""

from __future__ import annotations

import html
import random
import re
import time

import streamlit as st
import streamlit.components.v1 as components

from engine import mock, live
from engine import state_machine as sm

# --------------------------------------------------------------------------- #
# Page config + Swiss design system
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="FACTOR — Demo", page_icon="▮", layout="wide",
                   initial_sidebar_state="collapsed")

# ---- Professional dark design system (Swiss/International Typographic) ---- #
ACCENT = "#FF453A"   # refined red accent, tuned for dark backgrounds
BG     = "#0B0B0D"   # app background (near-black)
BG2    = "#141418"   # panels / cards / sidebar
BG3    = "#1C1C22"   # hover / raised
INK    = "#ECECEE"   # primary text
MUTE   = "#9A9AA4"   # secondary text
FAINT  = "#5A5A64"   # tertiary / disabled
LINE   = "#2A2A31"   # hairline borders / rules

VERDICT_COLORS = {
    "supported": "#3FB950",   # green
    "partial": "#D8A72B",     # amber
    "unsupported": ACCENT,
    "contradicted": ACCENT,
    "pending": FAINT,
}

SWISS_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&display=swap');

html, body, [class*="css"], .stMarkdown, .stApp {{
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    color: {INK};
}}
.stApp {{ background: {BG}; }}

/* Force readable text on every Streamlit-themed element. */
.stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, h1, h2, h3, h4, h5,
label, .stCaption, [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"], [data-testid="stMetricValue"],
.stRadio, .stSelectbox, .stExpander, [data-testid="stExpander"] summary,
[data-testid="stExpander"] p, .stTabs [data-baseweb="tab"] {{ color: {INK} !important; }}
.stCaption, [data-testid="stCaptionContainer"], [data-testid="stMetricLabel"] {{ color: {MUTE} !important; }}

/* Inputs / selects */
[data-baseweb="select"] > div, .stTextInput input, .stSelectbox div[role="button"] {{
    background: {BG2} !important; border-color: {LINE} !important; color: {INK} !important;
}}

/* Flat, orthogonal — no rounded corners */
.stButton>button, .stSelectbox div, .stExpander, div[data-testid="stExpander"],
[data-baseweb="select"] > div {{ border-radius: 0 !important; }}

.stButton>button {{
    border: 1px solid {LINE}; background: transparent; color: #FFFFFF !important;
    font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
    font-size: .72rem; padding: .5rem 1.1rem;
}}
.stButton>button * {{ color: #FFFFFF !important; }}
.stButton>button:hover {{ background: {BG3}; color: #FFFFFF !important; border-color: {ACCENT}; }}
.stButton>button[kind="primary"] {{ background: {ACCENT}; color: #FFFFFF !important; border-color: {ACCENT}; }}
.stButton>button[kind="primary"]:hover {{ background: #C4302B; border-color: #C4302B; color: #FFFFFF !important; }}

/* Larger homepage section titles — no letter-spacing, lighter red for legibility */
.hp-title {{
    text-transform: uppercase; letter-spacing: normal; font-size: 1.2rem;
    font-weight: 800; color: #FF6A5F; margin: 0 0 .5rem 0;
}}
/* Pipeline strip on the homepage: white text on every pill */
.hp-flow .pill {{ color: #FFFFFF !important; }}

h1, h2, h3, h4 {{ letter-spacing: -0.02em; font-weight: 900; }}
h1 {{ font-size: 2.4rem; line-height: 1.02; }}

hr {{ border: none; border-top: 1px solid {LINE}; margin: 1.1rem 0; }}

.swiss-kicker {{
    text-transform: uppercase; letter-spacing: .22em; font-size: .68rem;
    font-weight: 700; color: {ACCENT}; margin: 0 0 .2rem 0;
}}
.swiss-rule-top {{ border-top: 3px solid {ACCENT}; padding-top: .5rem; }}

.pill {{
    display: inline-block; padding: .18rem .5rem; margin: 2px 3px 2px 0;
    font-size: .64rem; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase; border: 1px solid {LINE}; color: {MUTE};
    white-space: nowrap;
}}
.pill-done {{ background: {INK}; color: {BG}; border-color: {INK}; }}
.pill-active {{ background: {ACCENT}; color: #0B0B0D; border-color: {ACCENT}; }}
.pill-fail {{ background: transparent; color: {ACCENT}; border-color: {ACCENT}; border-width: 2px; }}
.pill-skip {{ background: transparent; color: {FAINT}; border-color: {LINE}; border-style: dashed; }}
.pill-todo {{ background: transparent; color: {FAINT}; border-color: {LINE}; }}

.cite {{
    color: {ACCENT}; font-weight: 700; font-size: .74em; vertical-align: super;
    text-decoration: none; border-bottom: 1px solid {ACCENT}; cursor: help;
}}
.verdict-tag {{
    display: inline-block; padding: .1rem .45rem; font-size: .64rem;
    font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
    border: 1px solid; margin-left: .4rem;
}}
.meta-mono {{ font-family: 'SF Mono','Consolas',monospace; font-size: .8rem; color: {MUTE}; }}
.aidisc {{ border-left: 3px solid {ACCENT}; padding: .3rem 0 .3rem .8rem; color:{MUTE}; }}
.card {{ border: 1px solid {LINE}; background: {BG2}; }}

section[data-testid="stSidebar"] {{ background: {BG2}; border-right: 1px solid {LINE}; }}
[data-testid="stMetricValue"] {{ font-weight: 900; }}
[data-testid="stExpander"] {{ border-color: {LINE} !important; background: {BG2}; }}
.stDataFrame, [data-testid="stTable"] {{ border: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid {LINE}; }}
.stTabs [aria-selected="true"] {{ color: {ACCENT} !important; }}
[data-testid="stAlert"] {{ background: {BG2}; border: 1px solid {LINE}; color: {INK}; }}
code {{ background: {BG3}; color: {INK}; }}
</style>
"""


# --------------------------------------------------------------------------- #
# Animated pipeline illustration (self-contained SVG: SMIL + CSS, no deps)
# --------------------------------------------------------------------------- #
PIPELINE_SVG = """
<svg viewBox="0 0 1080 180" width="100%" style="max-width:100%;height:auto;display:block"
     xmlns="http://www.w3.org/2000/svg" font-family="Inter, Arial, sans-serif">
  <style>
    @keyframes flowmove { to { stroke-dashoffset: -24; } }
    @keyframes pulse    { 0%,100% { opacity:.30 } 50% { opacity:1 } }
    @keyframes softpulse{ 0%,100% { opacity:.55 } 50% { opacity:1 } }
    .flow { stroke:#3A3A44; stroke-width:2; stroke-dasharray:6 6;
            animation: flowmove 1s linear infinite; }
    .gate { fill:#FF453A; animation: pulse 2.2s ease-in-out infinite; }
    .arc  { fill:none; stroke:#FF453A; stroke-width:2; stroke-dasharray:5 5;
            animation: softpulse 2.4s ease-in-out infinite; }
    .cap  { fill:#9A9AA4; font-size:9px; font-weight:700; letter-spacing:.5px; }
    .stg  { fill:#ECECEE; font-size:13px; font-weight:800; letter-spacing:.3px; }
    .tag  { fill:#FF6A5F; font-size:10px; font-weight:800; }
    .box  { fill:#141418; stroke:#2A2A31; stroke-width:1; }
    .boxhot { fill:#141418; stroke:#FF453A; stroke-width:2; }
    .chk  { fill:#3FB950; animation: softpulse 1.8s ease-in-out infinite; }
  </style>

  <!-- connectors -->
  <line class="flow" x1="166" y1="97" x2="202" y2="97"/>
  <line class="flow" x1="342" y1="97" x2="378" y2="97"/>
  <line class="flow" x1="518" y1="97" x2="554" y2="97"/>
  <line class="flow" x1="694" y1="97" x2="730" y2="97"/>
  <line class="flow" x1="870" y1="97" x2="906" y2="97"/>

  <!-- revise loop: fact-check -> draft -->
  <path class="arc" d="M448,70 C430,22 290,22 272,70"/>
  <polygon points="272,70 266,60 278,60" fill="#FF453A"/>
  <text class="cap" x="360" y="16" text-anchor="middle" fill="#FF6A5F">REVISE  ≤ 3×</text>

  <!-- citation tag on draft -->
  <g style="animation: softpulse 2s ease-in-out infinite">
    <rect x="238" y="44" width="68" height="17" fill="none" stroke="#FF453A"/>
    <text class="tag" x="272" y="56" text-anchor="middle">[[chunk:id]]</text>
  </g>

  <!-- stage boxes -->
  <g><rect class="box"    x="26"  y="70" width="140" height="54"/>
     <text class="stg" x="96"  y="102" text-anchor="middle">RESEARCH</text></g>
  <g><rect class="box"    x="202" y="70" width="140" height="54"/>
     <text class="stg" x="272" y="102" text-anchor="middle">DRAFT</text></g>
  <g><rect class="boxhot" x="378" y="70" width="140" height="54"/>
     <text class="stg" x="448" y="102" text-anchor="middle">FACT-CHECK</text></g>
  <g><rect class="box"    x="554" y="70" width="140" height="54"/>
     <text class="stg" x="624" y="102" text-anchor="middle">BIAS</text></g>
  <g><rect class="box"    x="730" y="70" width="140" height="54"/>
     <text class="stg" x="800" y="102" text-anchor="middle">TRANSLATE</text></g>
  <g><rect class="box"    x="906" y="70" width="140" height="54"/>
     <text class="stg" x="976" y="102" text-anchor="middle">PUBLISH</text></g>

  <!-- verified check on publish -->
  <path class="chk" d="M1006,60 l5,6 l10,-13" fill="none" stroke="#3FB950" stroke-width="3"
        stroke-linecap="round" stroke-linejoin="round"/>

  <!-- gates -->
  <g><polygon class="gate" points="96,138 102,144 96,150 90,144"/>
     <text class="cap" x="96"  y="166" text-anchor="middle">GATE 1</text></g>
  <g><polygon class="gate" points="448,138 454,144 448,150 442,144"/>
     <text class="cap" x="448" y="166" text-anchor="middle">GATE 3</text></g>
  <g><polygon class="gate" points="976,138 982,144 976,150 970,144"/>
     <text class="cap" x="976" y="166" text-anchor="middle">GATE 8</text></g>

  <!-- travelling article tokens -->
  <circle r="6" fill="#FF453A">
    <animateMotion dur="7s" repeatCount="indefinite" path="M26,97 H1046"/>
  </circle>
  <circle r="6" fill="#FF453A" opacity="0.8">
    <animateMotion dur="7s" begin="-2.35s" repeatCount="indefinite" path="M26,97 H1046"/>
  </circle>
  <circle r="6" fill="#FF453A" opacity="0.6">
    <animateMotion dur="7s" begin="-4.7s" repeatCount="indefinite" path="M26,97 H1046"/>
  </circle>
</svg>
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
    st.session_state.setdefault("entered", False)
    st.session_state.setdefault("workspace_id", st.session_state.seed["workspaces"][0].id)
    st.session_state.setdefault("current_run", None)
    st.session_state.setdefault("history", [])          # finished runs (dicts)
    st.session_state.setdefault("force_mock", True)   # default to MOCK even if a key is present
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
    col = VERDICT_COLORS.get(v, INK)
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
        color = ACCENT if mode == "LIVE" else INK
        textcol = "#FFFFFF" if mode == "LIVE" else BG
        st.markdown(
            f'<span class="pill" style="background:{color};color:{textcol};border-color:{color}">'
            f'MODE · {mode}</span>', unsafe_allow_html=True)
        if live_key:
            st.checkbox("Force MOCK (ignore API key)", key="force_mock")
            st.caption("API key detected. LIVE runs Writer + Fact-checker via the hosted "
                       "LLM API; other steps stay mock. Failures fall back to mock.")
        else:
            st.caption("No ANTHROPIC_API_KEY — MOCK only. Set it in st.secrets or env "
                       "to enable LIVE Writer + Fact-checker.")

        st.markdown("---")
        page = st.radio("View", ["Workspace", "Run pipeline", "Article", "Dashboard"],
                        label_visibility="collapsed")
        st.markdown("---")
        cta1, cta2 = st.columns(2)
        if cta1.button("⌂ Home", use_container_width=True):
            st.session_state.entered = False
            st.rerun()
        if cta2.button("↺ Reset", use_container_width=True):
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
            st.markdown(f'<div style="border-left:3px solid {VERDICT_COLORS["supported"]};'
                        f'padding-left:.8rem">'
                        f'{html.escape(d.get("v2_claim",""))}</div>', unsafe_allow_html=True)

    if "claims" in a:
        with st.expander("④ Fact-checker — per-claim verdicts (Gate 3)", expanded=True):
            for c in a["claims"]:
                st.markdown(
                    f'<b>{c["id"]}</b> {verdict_tag(c["verdict"])} '
                    f'<sup class="cite">[{c["chunk_id"]}]</sup><br>'
                    f'<span style="color:{INK}">{html.escape(c["text"])}</span><br>'
                    f'<span style="color:{MUTE};font-size:.85em">{html.escape(c.get("note",""))}</span>',
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
                f'<div style="border:1px solid {LINE};background:{BG2};height:120px;display:flex;'
                f'align-items:center;justify-content:center;color:{MUTE};'
                f'font-size:.7rem;letter-spacing:.2em;text-transform:uppercase">'
                f'1200 × 630 · brand-safe illustration (placeholder)</div>',
                unsafe_allow_html=True)
            st.caption(f"alt (EN): {img.get('alt_en','')}")

    if a.get("live_used"):
        st.info("LIVE mode used the hosted LLM for: " + ", ".join(sorted(set(a["live_used"]))))
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

    label = (f'<span class="pill" style="background:{ACCENT};color:{BG};border-color:{ACCENT}">'
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
# Landing page
# --------------------------------------------------------------------------- #
def page_landing():
    live_on = live.live_available()
    # Landing-only: cap width on desktop so the page reads as a centered box.
    st.markdown(
        """<style>
        .block-container, [data-testid="stMainBlockContainer"] {
            max-width: 1080px; margin: 0 auto; padding-top: 2rem;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div style="border-top:6px solid {ACCENT};padding-top:.6rem;margin-top:1rem">
          <div class="swiss-kicker">Factual Agentic Content Orchestrator</div>
          <h1 style="font-size:4.2rem;line-height:.95;margin:.2rem 0 .4rem 0;color:{INK}">
            FACTOR<span style="color:{ACCENT}">.</span>
          </h1>
          <p style="font-size:1.7rem;line-height:1.25;max-width:34ch;font-weight:600;margin:.4rem 0 0 0;color:{INK}">
            A self-hosted, agentic pipeline that produces
            <b>hallucination-free</b> content — every claim grounded in a verified source.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, num, label, desc in [
        (c1, "10", "Agents", "Planner → Researcher → Outliner → Writer → Fact-checker → Bias → Translator → SEO → Image → Publisher."),
        (c2, "8", "Gates", "From source-sufficiency to independent fact-check to post-publish audit — fail a gate, never ship half-baked."),
        (c3, "2", "Languages", "Writes Indonesian, transcreates to English — facts validated once, inherited across locales."),
    ]:
        col.markdown(
            f"""<div style="border-top:1px solid {LINE};padding-top:.5rem;min-height:150px">
                <div style="font-size:3rem;font-weight:900;line-height:1;color:{ACCENT}">{num}</div>
                <div class="swiss-kicker" style="color:{INK}">{label}</div>
                <div style="font-size:.85rem;color:{MUTE}">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # --- Deployment profiles: hybrid vs FULL self-hosted ----------------- #
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">Runs on your own infrastructure — two profiles</div>',
                unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    d1.markdown(
        f"""<div style="border:1px solid {LINE};background:{BG2};padding:1rem 1.1rem;min-height:210px">
            <div class="swiss-kicker" style="color:{INK}">Profile A · Hybrid</div>
            <div style="font-size:1.15rem;font-weight:900;margin:.1rem 0 .5rem 0;color:{INK}">Hosted LLM API for cognition</div>
            <div style="font-size:.86rem;color:{MUTE};line-height:1.5">
              Self-hosted app + corpus on your VPS (Dokploy / Traefik / Docker); a hosted LLM API runs the
              10 agents. Fastest to launch.<br><br>
              <b>VPS:</b> 6 vCPU · 16 GB · 100 GB SSD<br>
              <b>Cost:</b> ≈ $0.85–1.00 per bilingual article<br>
              <b>At 5/day:</b> ≈ $130–160 / month
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    d2.markdown(
        f"""<div style="border:2px solid {ACCENT};background:{BG2};padding:1rem 1.1rem;min-height:210px">
            <div class="swiss-kicker">Profile B · Full self-hosted</div>
            <div style="font-size:1.15rem;font-weight:900;margin:.1rem 0 .5rem 0;color:{INK}">Zero API · data never leaves</div>
            <div style="font-size:.86rem;color:{MUTE};line-height:1.5">
              Every model runs on your hardware — nothing is sent to a third party.<br><br>
              <b>LLM:</b> vLLM · Qwen2.5-72B / Llama-3.3-70B<br>
              <b>Embeddings:</b> bge-m3 (Ollama) &nbsp;·&nbsp; <b>Images:</b> SDXL / Flux (ComfyUI)<br>
              <b>Hardware:</b> GPU 48 GB VRAM · no per-token cost
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # --- Why it won't hallucinate ---------------------------------------- #
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">Why the output won\'t hallucinate</div>',
                unsafe_allow_html=True)
    h1, h2, h3, h4 = st.columns(4)
    for col, t, d in [
        (h1, "Grounded, RAG-first", "No claim is written from model memory. Every fact comes from a verified corpus chunk."),
        (h2, "Citation-or-drop", "A claim without a valid source marker is rewritten or removed — never shipped."),
        (h3, "Independent checker", "The Fact-checker is a separate model with a clean context, so it can't rubber-stamp itself."),
        (h4, "Human-in-the-loop", "YMYL content gets editor approval at Gate 7; relax to sampling once quality proves out."),
    ]:
        col.markdown(
            f"""<div style="border-top:1px solid {LINE};padding-top:.5rem;min-height:150px">
                <div class="swiss-kicker" style="color:{ACCENT}">{t}</div>
                <div style="font-size:.82rem;color:{MUTE};line-height:1.45">{d}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # --- Pipeline flow strip --------------------------------------------- #
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">The pipeline — a state machine with 8 gates</div>',
                unsafe_allow_html=True)
    components.html(
        '<div style="margin:0;background:transparent">' + PIPELINE_SVG + "</div>",
        height=200,
    )
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    flow = "".join(
        f'<span class="pill {"pill-active" if s in ("FACT_CHECKING","HUMAN_REVIEW") else "pill-todo"}">'
        f'{sm.step_label(s)}</span>'
        for s in sm.PIPELINE_STATES
    )
    st.markdown(f'<div class="hp-flow" style="line-height:2.2">{flow}</div>', unsafe_allow_html=True)
    st.caption("Grounded generation · independent fact-check · bias & ethics review · "
               "cross-lingual QA · schema validation · human review · post-publish audit. "
               "Revisions capped at 3× before a piece is escalated to a human.")

    # --- Corpus / topic-agnostic ----------------------------------------- #
    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="border-left:3px solid {ACCENT};padding-left:.9rem;font-size:.9rem;color:{MUTE}">'
        '<b>Topic-agnostic, multi-workspace.</b> You define each Topic Workspace and its trusted '
        'sources — official sites, scientific journals, curated books. Journals are harvested '
        'automatically via OAI-PMH (≈200 open-access endpoints), chunked, embedded into '
        'PostgreSQL + pgvector, and hybrid-searched (vector + full-text) at write time. '
        'Output: 2–5 verified, bilingual articles per day, injected straight into your CMS.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">Three scenarios you can run</div>',
                unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    s1.markdown("**① Happy path**  \nA fully grounded draft clears every gate and publishes.")
    s2.markdown(f'**② Revision**  \nAn overclaim is caught by <span style="color:{ACCENT}">Gate 3</span> '
                "→ REVISING → v2 passes.", unsafe_allow_html=True)
    s3.markdown(f'**③ Weak corpus**  \nToo few sources → <span style="color:{ACCENT}">Gate 1</span> '
                "aborts before any draft.", unsafe_allow_html=True)

    st.markdown("---")
    b1, b2 = st.columns([1, 3])
    with b1:
        if st.button("Enter demo ▸", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
    with b2:
        mode = ("LIVE (LLM-backed Writer + Fact-checker)" if mode_is_live()
                else "MOCK (deterministic & free — no API calls)")
        st.caption(f"Running in **{mode}**. This is a simulation — no database, no Redis, no Node. "
                   "Production stack is TypeScript / BullMQ / PostgreSQL.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    st.markdown(SWISS_CSS, unsafe_allow_html=True)
    init_state()

    if not st.session_state.entered:
        page_landing()
        return

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
