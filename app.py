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

from engine import mock, live, retrieval, imagegen
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
LABEL  = "#9AA0AC"   # readable section labels (kickers) — was red, hard to read
CTA    = "#FF7A6E"   # softer, more legible coral for call-to-action prompts
FIELD  = "#52535F"   # clearly visible resting border for form fields

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

/* Prominent selection widgets — draw the user to pick first */
.pick-label {{
    text-transform: uppercase; letter-spacing: .08em; font-size: .74rem; font-weight: 800;
    color: {CTA}; margin: .1rem 0 .35rem 0;
}}
/* A selectbox always holds a value, so render it in the 'selected' state:
   red accent border + subtle tint, matching a chosen radio chip.
   NOTE: this Streamlit build renders selectboxes as a React-Aria ComboBox
   (.react-aria-ComboBox), not a baseweb select — target that control box. */
[data-testid="stSelectbox"] .react-aria-ComboBox > div {{
    border: 2px solid {ACCENT} !important; border-radius: 0 !important;
    background: rgba(255,69,58,.10) !important; min-height: 3rem;
}}
[data-testid="stSelectbox"] .react-aria-ComboBox > div:hover {{
    background: rgba(255,69,58,.18) !important;
}}
/* Radio groups rendered as bordered chips (engine + publishing mode) */
.st-key-pick_engine div[role="radiogroup"], .st-key-pick_pub div[role="radiogroup"] {{
    gap: .5rem; flex-wrap: wrap; margin-top: .1rem;
}}
.st-key-pick_engine div[role="radiogroup"] > label, .st-key-pick_pub div[role="radiogroup"] > label {{
    border: 1.5px solid {FIELD}; background: {BG2}; padding: .5rem .9rem; margin: 0;
    transition: border-color .12s, background .12s;
}}
.st-key-pick_engine div[role="radiogroup"] > label:hover, .st-key-pick_pub div[role="radiogroup"] > label:hover {{
    border-color: {ACCENT};
}}
.st-key-pick_engine div[role="radiogroup"] > label:has(input:checked),
.st-key-pick_pub div[role="radiogroup"] > label:has(input:checked) {{
    border-color: {ACCENT}; background: rgba(255,69,58,.14);
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
h1 {{ font-size: 1.8rem; line-height: 1.12; margin-bottom: .15rem; }}

/* Guiding subtitle under a page title */
.page-sub {{
    font-size: .92rem; color: {MUTE}; line-height: 1.5;
    max-width: 72ch; margin: .1rem 0 1.1rem 0;
}}
.page-sub b {{ color: {INK}; }}
/* Numbered workflow nav in the sidebar */
section[data-testid="stSidebar"] .stRadio label {{ font-size: .9rem; }}

hr {{ border: none; border-top: 1px solid {LINE}; margin: 1.1rem 0; }}

.swiss-kicker {{
    text-transform: uppercase; letter-spacing: .14em; font-size: .7rem;
    font-weight: 700; color: {LABEL}; margin: 0 0 .2rem 0;
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

/* "Agent working" indicator, shown next to the pipeline while a step runs */
.agent-working {{
    display: flex; align-items: center; gap: .7rem;
    border: 1px solid {ACCENT}; border-left-width: 3px;
    background: rgba(255,69,58,.08); padding: .55rem .85rem; margin: .5rem 0;
}}
.agent-working b {{ text-transform: uppercase; letter-spacing: .04em; font-size: .8rem; }}
.agent-working .aw-note {{ color: {MUTE}; font-weight: 400; font-size: .85rem; }}
.spinner {{
    width: 15px; height: 15px; flex: 0 0 auto; border-radius: 50%;
    border: 3px solid {LINE}; border-top-color: {ACCENT};
    animation: awspin .8s linear infinite;
}}
@keyframes awspin {{ to {{ transform: rotate(360deg); }} }}
.agent-fail {{ border-left: 3px solid {ACCENT}; padding: .45rem .85rem; margin: .5rem 0;
    color: {INK}; background: rgba(255,69,58,.06); }}

/* Full-width sticky footer nav bar (translucent) */
.st-key-stickybar {{
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 1000000;
    background: rgba(11,11,13,0.72);
    -webkit-backdrop-filter: blur(9px); backdrop-filter: blur(9px);
    border-top: 1px solid {LINE};
    padding: .4rem 1.2rem .45rem;
}}
.st-key-stickybar [data-testid="stHorizontalBlock"] {{ justify-content: center; align-items: center; gap: .55rem; flex-wrap: wrap; }}
.st-key-stickybar [data-testid="stColumn"] {{ width: auto !important; flex: 0 0 auto !important; min-width: 0 !important; }}
.st-key-stickybar .stButton > button {{ white-space: nowrap; box-shadow: 0 4px 16px rgba(0,0,0,.45); }}
/* keep page + sidebar content clear of the fixed bar */
.block-container {{ padding-bottom: 5.5rem !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-bottom: 5rem; }}

/* Read-only workflow progress in the sidebar */
.wf-list {{ margin: .15rem 0 .1rem 0; }}
.wf-step {{ font-size: .92rem; padding: .3rem 0 .3rem .1rem; color: {MUTE}; }}
.wf-step .wf-mark {{ display: inline-block; width: 1.3rem; text-align: center; }}
.wf-done {{ color: {INK}; }}
.wf-done .wf-mark {{ color: {ACCENT}; }}
.wf-current {{ color: {INK}; font-weight: 800; border-left: 3px solid {ACCENT};
    padding-left: .55rem; margin-left: -.65rem; }}
.wf-current .wf-mark {{ color: {ACCENT}; }}
.wf-todo {{ color: {FAINT}; }}
.sb-meta {{ font-size: .82rem; color: {MUTE}; line-height: 1.4; margin: .25rem 0 0 0; }}
.sb-meta b {{ color: {INK}; font-size: .95rem; }}

section[data-testid="stSidebar"] {{ background: {BG2}; border-right: 1px solid {LINE}; }}
[data-testid="stMetricValue"] {{ font-weight: 900; font-size: 1.4rem; line-height: 1.15;
    white-space: normal !important; overflow: visible !important; }}
[data-testid="stMetricLabel"] {{ font-size: .72rem; letter-spacing: .04em; }}
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
    # Default to MOCK: deterministic, no API/GPU dependency, so a cold-opened
    # demo never fails on the first run. Live engines are one click away.
    st.session_state.setdefault("engine", "mock")
    st.session_state.setdefault("selected_topic", None)
    st.session_state.setdefault("cms_mode", False)
    st.session_state.setdefault("running", False)
    st.session_state.setdefault("options_locked", False)   # freeze pickers after a successful run
    st.session_state.setdefault("nav", "Workspace")


def reset_demo():
    for k in ("current_run", "history", "selected_topic", "options_locked"):
        st.session_state.pop(k, None)
    init_state()


# --- Inference engine selection -------------------------------------------- #
ENGINE_LABELS = {
    "mock": "MOCK",
    "amd": "AMD · Radeon W7900",
    "fireworks": "FIREWORKS · gpt-oss-120b",
}


def available_engines() -> list[str]:
    opts = ["mock"]
    if live.amd_available():
        opts.append("amd")
    if live.fireworks_available():
        opts.append("fireworks")
    return opts


def active_engine() -> str:
    eng = st.session_state.get("engine", "mock")
    return eng if eng in available_engines() else "mock"


def engine_backends(eng: str):
    """Return (writer_fn, factchecker_fn) for the chosen engine; (None, None) = mock."""
    if eng == "amd":
        return live.amd_writer, live.amd_factchecker
    if eng == "fireworks":
        return live.fireworks_writer, live.fireworks_factchecker
    return None, None


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


def page_header(kick: str, title: str, subtitle: str | None = None):
    """Consistent page intro: kicker + title + a one-line 'what to do' subtitle."""
    kicker(kick)
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


def _go_home():
    st.session_state.entered = False


def _enter_demo():
    st.session_state.entered = True
    st.session_state.nav = "Workspace"


def _reset_cb():
    """Reset the whole session and return the user to Step 1 (Workspace)."""
    for k in ("current_run", "history", "selected_topic", "cms_mode", "running",
              "options_locked"):
        st.session_state.pop(k, None)
    st.session_state.entered = True
    st.session_state.nav = "Workspace"


def _engine_caption(eng: str) -> str:
    if eng == "amd":
        extra = []
        if retrieval.available():
            extra.append("Researcher (bge-m3)")
        if imagegen.available():
            extra.append("Image (SDXL)")
        more = (" + " + " + ".join(extra)) if extra else ""
        return (f"On an **AMD Radeon PRO W7900** (RDNA3 · ROCm): Writer + Fact-checker "
                f"(`{live.amd_model()}` via llama.cpp){more}. Remaining steps stay mock; failures fall back.")
    if eng == "fireworks":
        extra = " + Researcher (qwen3-embedding-8b)" if live.fireworks_available() else ""
        return (f"On **Fireworks AI**: Writer + Fact-checker (`gpt-oss-120b`){extra}. "
                f"Image + remaining steps stay mock; failures fall back.")
    if live.amd_available() or live.fireworks_available():
        return "MOCK: deterministic canned output, no API calls. Pick a live engine to run on AMD / Fireworks."
    return "MOCK only. Set AMD_BASE_URL (AMD GPU) or FIREWORKS_API_KEY in st.secrets/env to enable a live engine."


def _toggle_cms():
    st.session_state.cms_mode = not st.session_state.get("cms_mode", False)


def _view_reader():
    st.session_state.cms_mode = False
    st.session_state.nav = "Article"


def _view_cms():
    st.session_state.cms_mode = True
    st.session_state.nav = "Article"


def _approve_run():
    run = st.session_state.get("current_run")
    if run is not None and run.outcome == "awaiting_review":
        mock.finish_publish(run, True)
        _record_history(run)


def _reject_run():
    run = st.session_state.get("current_run")
    if run is not None and run.outcome == "awaiting_review":
        mock.finish_publish(run, False)
        _record_history(run)


def _start_run():
    st.session_state.running = True
    st.session_state._want_scroll = True   # scroll to the stepper on the result render too


def _change_options():
    """Unlock the Topic / Engine / Publishing pickers after a successful run,
    so the user can adjust them and press Run pipeline again. Also clears the
    finished run so everything below the pickers (stepper, agent outputs, audit,
    review gate) resets to the pristine 'choose a topic' state."""
    st.session_state.options_locked = False
    st.session_state.current_run = None
    st.session_state.cms_mode = False
    st.session_state._scroll_top = True   # bring the pickers back into view


def sticky_footer(*specs):
    """Full-width translucent bar with compact, centered buttons.

    Each spec is (label, action, kind); action is a nav-target string or a
    callable callback. Only the specs passed are rendered — callers decide which
    buttons are unlocked yet, so a step's button appears only once reachable.
    """
    specs = [s for s in specs if s]
    if not specs:
        return
    with st.container(key="stickybar"):
        cols = st.columns(len(specs))
        for i, (col, (label, action, kind)) in enumerate(zip(cols, specs)):
            if action is None:                       # non-actionable (e.g. "Running…")
                col.button(label, key=f"sf_{i}", type=kind, disabled=True)
            elif callable(action):
                col.button(label, key=f"sf_{i}", type=kind, on_click=action)
            else:
                col.button(label, key=f"sf_{i}", type=kind, on_click=_nav_to, args=(action,))


def _nav_to(page: str):
    """on_click callback: switch the sidebar workflow nav to `page`.

    Must run as a callback (before widgets are instantiated) — Streamlit forbids
    setting a widget-keyed value after its widget is created in the same run.
    """
    st.session_state.nav = page




def _audit_models(eng: str) -> dict[str, str]:
    """Model label per step for the audit trail, matching the active engine.

    Only Researcher, Writer, Fact-checker, Translator and Image call a live
    model in this demo; the rest are simulated/canned and labelled as such.
    """
    if eng == "amd":
        llm = f"Gemma · {live.amd_model()}"
        emb = "bge-m3" if retrieval.available() else "seed corpus"
        img = "SDXL-Turbo · AMD" if imagegen.available() else "placeholder"
    elif eng == "fireworks":
        llm = "Fireworks · gpt-oss-120b"
        emb = "qwen3-embedding-8b" if live.fireworks_available() else "seed corpus"
        img = "placeholder"
    else:
        return {"IMAGE_GEN": "placeholder"}  # mock: keep STEP_META tiers, fix image
    sim = "simulated"
    return {
        "PLANNING": sim, "OUTLINING": sim, "BIAS_REVIEW": sim, "REVISING": sim,
        "TRANSLATION_QA": sim, "META_SEO": sim,
        "RESEARCHING": emb, "DRAFTING": llm, "FACT_CHECKING": llm,
        "TRANSLATING": llm, "IMAGE_GEN": img,
    }


# Ordered workflow steps shown in the sidebar nav.
NAV_STEPS = ["Workspace", "Run pipeline", "Article", "Dashboard"]
NAV_LABELS = {
    "Workspace": "① Workspace",
    "Run pipeline": "② Run pipeline",
    "Article": "③ Article",
    "Dashboard": "④ Dashboard",
}


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar():
    """Read-only status panel. All navigation happens via the sticky footer."""
    seed = st.session_state.seed
    with st.sidebar:
        a1, a2 = st.columns(2)
        a1.button("⌂ Home", key="sb_home", use_container_width=True, on_click=_go_home)
        a2.button("↻ Reset", key="sb_reset", use_container_width=True, on_click=_reset_cb)

        st.markdown('<div class="swiss-rule-top"></div>', unsafe_allow_html=True)
        st.markdown("### FACTOR")
        st.caption("Factual Agentic Content Orchestrator")
        cur_ws = seed["workspaces_by_id"][st.session_state.workspace_id]
        st.markdown(f'<div class="sb-meta">Workspace<br><b>{cur_ws.name}</b></div>',
                    unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="swiss-kicker">Workflow</div>', unsafe_allow_html=True)
        nav = st.session_state.get("nav", "Workspace")
        cur_i = NAV_STEPS.index(nav) if nav in NAV_STEPS else 0
        rows = []
        for i, s in enumerate(NAV_STEPS):
            cls, mark = (("wf-done", "✓") if i < cur_i else
                         ("wf-current", "●") if i == cur_i else ("wf-todo", "○"))
            rows.append(f'<div class="wf-step {cls}"><span class="wf-mark">{mark}</span>{NAV_LABELS[s]}</div>')
        st.markdown('<div class="wf-list">' + "".join(rows) + "</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="swiss-kicker">Inference engine</div>', unsafe_allow_html=True)
        eng = active_engine()
        color = ACCENT if eng in ("amd", "fireworks") else INK
        textcol = "#FFFFFF" if eng in ("amd", "fireworks") else BG
        st.markdown(
            f'<span class="pill" style="background:{color};color:{textcol};border-color:{color}">'
            f'{ENGINE_LABELS[eng]}</span>', unsafe_allow_html=True)
        st.caption(_engine_caption(eng))
        st.caption("Change it on the ② Run pipeline page.")

        st.markdown("---")
        st.caption("Read-only status — navigate with the buttons in the bottom bar. "
                   "Simulation only: no DB, no Redis, no Node (production = TypeScript / BullMQ / Postgres).")


# --------------------------------------------------------------------------- #
# Page: Workspace
# --------------------------------------------------------------------------- #
def page_workspace():
    seed = st.session_state.seed
    names = {w.id: w.name for w in seed["workspaces"]}

    kicker("Step 1 · Topic Workspace")
    st.markdown('<div class="pick-label">▸ Start here — choose a workspace</div>',
                unsafe_allow_html=True)
    ws_id = st.selectbox(
        "Topic Workspace", options=list(names.keys()),
        format_func=lambda i: names[i], label_visibility="collapsed",
        index=list(names.keys()).index(st.session_state.workspace_id),
        key="ws_select")
    if ws_id != st.session_state.workspace_id:
        st.session_state.workspace_id = ws_id
        st.session_state.selected_topic = None
        st.rerun()

    ws = seed["workspaces_by_id"][st.session_state.workspace_id]
    topics = [t for t in seed["topics"] if t.workspace_id == ws.id]
    chunks = [c for c in seed["chunks"] if c.workspace_id == ws.id]

    st.markdown(
        '<div class="page-sub" style="margin-top:.6rem">The selected workspace = your topic + your '
        'curated sources. Review the domain, credibility policy, corpus and topic backlog below — '
        'then continue to <b>② Run pipeline</b> to generate an article.</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.metric("Domain", ws.domain.split("(")[0].strip())
    c2.metric("Languages", " → ".join(l.upper() for l in ws.languages))
    c3.metric("Corpus chunks", len(chunks))
    st.markdown(ws.description)
    with st.container(border=True):
        kicker("Credibility policy")
        st.markdown(ws.credibility_policy)

    st.markdown("---")
    ready = [t for t in topics if getattr(t, "scenario", "") != "backlog" and mock.gate1_ok(t)]
    kicker(f"Topics — {len(topics)} in backlog · {len(ready)} corpus-ready")
    rows = []
    for t in topics:
        is_backlog = getattr(t, "scenario", "") == "backlog"
        ok = mock.gate1_ok(t)
        support = f"{t.related_chunk_count} chunks"
        if is_backlog:
            status = "Backlog · awaiting corpus"
        elif ok:
            status = "Ready"
        else:
            status = "Blocked · Gate 1"
        rows.append({
            "Topic": t.title_id,
            "Topic (EN)": t.title_en,
            "Category": t.category,
            "Genre": t.genre,
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
    # Workspace is always selected (default) → the next step is unlocked.
    sticky_footer(("⌂ Home", _go_home, "secondary"),
                  ("② Pick a topic & run ▸", "Run pipeline", "primary"))


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


def _scroll_to_stepper():
    """Scroll the page to the pipeline stepper (QUEUED pill) when a run starts,
    so the animated process box is visible without manual scrolling. Retries
    because the stepper streams in during the animation."""
    components.html(
        """
        <script>
        (function(){
          function go(n){
            try {
              const d = window.parent.document;
              const pill = [...d.querySelectorAll('.pill')]
                .find(p => (p.textContent||'').trim().toUpperCase() === 'QUEUED');
              if (pill) { pill.scrollIntoView({behavior:'smooth', block:'start'}); return; }
            } catch(e){}
            if (n > 0) setTimeout(function(){ go(n-1); }, 200);
          }
          go(25);
        })();
        </script>
        """, height=0)


def _scroll_to_top():
    """Smoothly scroll the app back to the top (used after 'Change options')."""
    components.html(
        """
        <script>
        (function(){
          try{
            const d = window.parent.document;
            const c = d.querySelector('[data-testid="stMain"]')
                   || d.querySelector('section.stMain')
                   || d.scrollingElement;
            if (c) c.scrollTo({top:0, behavior:'smooth'});
          }catch(e){}
        })();
        </script>
        """, height=0)


def _animate_run(run, topic, ws, seed):
    placeholder = st.empty()
    eng = active_engine()
    mock.set_active_models(_audit_models(eng))
    lw, lf = engine_backends(eng)
    if eng == "amd":
        retr = retrieval.research_pack if retrieval.available() else None
        imgr = imagegen.generate if imagegen.available() else None
        trl = live.amd_translator
    elif eng == "fireworks":
        retr = retrieval.fireworks_research_pack if live.fireworks_available() else None
        imgr = None
        trl = live.fireworks_translator
    else:
        retr = imgr = trl = None
    for r in mock.iter_pipeline(run, topic, ws, seed, live_writer=lw, live_factchecker=lf,
                                live_retriever=retr, live_imager=imgr, live_translator=trl):
        last = r.events[-1]
        with placeholder.container():
            render_stepper(r)
            if last.status == "gate_failed":
                st.markdown(f'<div class="agent-fail">✕ <b>{sm.step_label(last.step)}</b> — '
                            f'{last.note}</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="agent-working"><span class="spinner"></span>'
                    f'<span><b>Working · {sm.step_label(last.step)}</b>'
                    f'<span class="aw-note"> — {last.note}</span></span></div>',
                    unsafe_allow_html=True)
        time.sleep(random.uniform(0.5, 1.3))
    placeholder.empty()


def page_run():
    seed = st.session_state.seed
    ws = seed["workspaces_by_id"][st.session_state.workspace_id]
    topics = [t for t in seed["topics"] if t.workspace_id == ws.id]

    page_header("Step 2 · Pipeline", "Run pipeline")

    # Return to top when the user unlocks the pickers via "Change options",
    # so all frozen options come back into view.
    if st.session_state.pop("_scroll_top", False):
        _scroll_to_top()

    locked = st.session_state.get("options_locked", False)   # frozen after a successful run

    # 1) Topic ------------------------------------------------------------- #
    def _tag(t):
        if getattr(t, "scenario", "") == "backlog":
            return "  ·  ○ backlog (no corpus yet)"
        if not mock.gate1_ok(t):
            return "  ·  ⚠ weak corpus"
        return f"  ·  ● {t.related_chunk_count} chunks — ready"
    # corpus-ready / scenario topics first, then backlog
    topics = sorted(topics, key=lambda t: (getattr(t, "scenario", "") == "backlog", t.title_en))
    labels = {t.id: f"{t.title_id}{_tag(t)}" for t in topics}
    st.markdown('<div class="pick-label">▸ Select a topic to run</div>', unsafe_allow_html=True)
    tid = st.selectbox("Topic", options=[t.id for t in topics],
                       format_func=lambda i: labels[i], label_visibility="collapsed",
                       key="topic_select", disabled=locked)
    topic = seed["topics_by_id"][tid]

    # 2) Inference engine — chosen here; shown (read-only) in the sidebar.
    # key="engine" ties the widget directly to session state so the sidebar,
    # which renders first, always reflects the same choice (no one-render lag).
    opts = available_engines()
    if len(opts) > 1:
        cur_eng = st.session_state.get("engine")
        if cur_eng not in opts:
            st.session_state.engine = cur_eng = opts[0]
        with st.container(key="pick_engine"):
            st.markdown('<div class="pick-label">▸ Choose your inference engine</div>',
                        unsafe_allow_html=True)
            # index= keeps the chip in sync with session_state on the FIRST render
            # (a keyed radio alone falls back to option 0 on the initial paint,
            # which desynced the chip from the sidebar/caption).
            st.radio("Inference engine", opts, index=opts.index(cur_eng),
                     format_func=lambda e: ENGINE_LABELS[e],
                     horizontal=True, key="engine", label_visibility="collapsed",
                     disabled=locked)
    st.caption(_engine_caption(active_engine()))

    # 3) Publishing mode --------------------------------------------------- #
    with st.container(key="pick_pub"):
        st.markdown('<div class="pick-label">▸ Choose a publishing mode</div>', unsafe_allow_html=True)
        pub_mode = st.radio(
            "Publishing mode",
            ["Human review (approve at Gate 7)", "Auto-publish to database"],
            horizontal=True, key="pub_mode", label_visibility="collapsed", disabled=locked,
            help="Human review pauses at Gate 7 for your Approve/Reject. Auto-publish marks Gate 7 "
                 "as auto-approved, posts straight to the database, and opens the Article.")
    auto_publish = pub_mode.startswith("Auto")

    if locked:
        st.caption("🔒 Topic · engine · publishing are frozen for this run — press "
                   "**⚙ Change options** in the bottom bar to edit them and run again.")

    if topic.scenario == "revision":
        st.caption("Scenario: **revision** — v1 draft contains an overclaim → Gate 3 rejects → "
                   "REVISING → v2 passes.")
    elif topic.scenario == "weak_corpus":
        st.caption("Scenario: **weak corpus** — below the Gate 1 threshold; the run is aborted "
                   "before any draft is written.")
    else:
        st.caption("Scenario: **happy path** — grounded draft clears every gate.")

    running = st.session_state.get("running", False)
    cur = st.session_state.get("current_run")
    done_here = cur is not None and cur.topic_id == tid

    # --- Sticky footer: Workspace back + the Run button (+ outcome actions) --- #
    # After a SUCCESSFUL run the pickers are frozen (locked): we surface a
    # "Change options" button first instead of Re-run, so the user deliberately
    # unlocks Topic/Engine/Publishing before running again. After a FAILED run
    # (rejected) the pickers stay editable and we offer a direct Retry.
    foot = [("◂ ① Workspace", "Workspace", "secondary")]
    if running:
        foot.append(("⏳ Running…", None, "primary"))                    # disabled while animating
    elif locked:                                                         # success → pickers frozen
        foot.append(("⚙ Change options", _change_options, "primary"))
        if done_here and cur.outcome == "awaiting_review":               # human review chosen
            foot += [("✕ Reject", _reject_run, "secondary"),
                     ("✓ Approve & publish", _approve_run, "primary")]
        elif done_here and cur.outcome == "published":                   # published (auto/approved)
            foot += [("▤ Reader Mode", _view_reader, "secondary"),
                     ("▦ CMS Mode", _view_cms, "primary")]
    elif done_here and cur.outcome == "rejected":                        # failure → quick retry
        foot.append(("↻ Retry pipeline", _start_run, "primary"))
    else:
        foot.append(("↻ Re-run pipeline" if done_here else "▶ Run pipeline", _start_run, "primary"))
    sticky_footer(*foot)

    # Drive the pipeline while the footer button shows "Running…".
    if running:
        _scroll_to_stepper()          # bring the process box into view
        run = mock.start_run(topic, ws)
        _animate_run(run, topic, ws, seed)
        st.session_state.current_run = run
        st.session_state.running = False
        if run.outcome == "awaiting_review" and auto_publish:
            mock.finish_publish(run, True, auto=True)   # Gate 7 auto-approved
            _record_history(run)
        elif run.outcome == "rejected":
            _record_history(run)
        # Freeze the pickers only on a successful run; a failed (rejected) run
        # leaves them editable so the user can pick a different topic and retry.
        st.session_state.options_locked = run.outcome != "rejected"
        st.rerun()

    run = st.session_state.current_run
    if run is None or run.topic_id != tid:
        st.info("Choose a topic, then press **▶ Run pipeline** in the bottom bar to watch the "
                "state machine advance.")
        return

    if st.session_state.pop("_want_scroll", False):
        _scroll_to_stepper()      # keep the process box in view after the rerun
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

    # Human review gate --- actions live in the sticky footer ------------- #
    if run.outcome == "awaiting_review":
        st.markdown("---")
        kicker("Gate 7 · Human review")
        st.markdown("You are the editor — use **✓ Approve & publish** or **✕ Reject** in the footer.")
    elif run.outcome == "published":
        auto = run.artifacts.get("auto_published")
        st.success(("Auto-published to the database. " if auto else "Published. ")
                   + "Open it via **Reader Mode** or **CMS Mode** in the footer.")
    elif run.outcome == "rejected":
        st.error("Rejected by editor at Gate 7. Pickers stay editable — change the topic or "
                 "settings, or press **↻ Retry pipeline** to run the same topic again.")

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
        img = a["image"]
        real = img.get("image_data")
        title = "⑧ Image — SDXL on AMD W7900" if real else "⑧ Image — prompt + placeholder"
        with st.expander(title):
            st.caption("Prompt")
            st.code(img.get("prompt", ""), language=None)
            if real:
                st.markdown(f'<img src="{real}" style="width:100%;max-width:640px;'
                            f'border:1px solid {LINE}">', unsafe_allow_html=True)
                st.caption(f"Generated on {img.get('gen_model','AMD W7900 · SDXL')} · alt: {img.get('alt_en','')}")
            else:
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
        "Latency ms": e.latency_ms,
    } for e in run.events]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.metric("Total tokens", f"{run.total_tokens:,}")
    c2.metric("Revisions", run.revision_count)


# --------------------------------------------------------------------------- #
# CMS-style full article preview (how it would render on a real site)
# --------------------------------------------------------------------------- #
_PUB_DATE = "7 July 2026"


def _md_to_article_html(body: str, by_id: dict, ordered_ids: list[str]) -> tuple[str, str]:
    """Return (title, body_html). Converts the markdown draft to a CMS-like article body,
    turning [[chunk:id]] markers into numbered superscript reference links."""
    def cite_repl(m):
        cid = m.group(1)
        n = ordered_ids.index(cid) + 1 if cid in ordered_ids else "?"
        return f'<sup class="c"><a href="#ref-{cid}">[{n}]</a></sup>'

    def inline(t: str) -> str:
        t = html.escape(t)
        t = _CITE_RE.sub(cite_repl, t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t

    title, out, para = "", [], []
    def flush():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()
    for line in (body or "").split("\n"):
        s = line.strip()
        if not s:
            flush(); continue
        if s.startswith("# "):
            flush(); title = s[2:].strip(); continue
        if s.startswith("### "):
            flush(); out.append(f"<h3>{inline(s[4:])}</h3>"); continue
        if s.startswith("## "):
            flush(); out.append(f"<h2>{inline(s[3:])}</h2>"); continue
        if s.startswith("> "):
            flush(); out.append(f"<blockquote>{inline(s[2:])}</blockquote>"); continue
        para.append(inline(s))
    flush()
    return title, "\n".join(out)


def _cms_preview_html(run, ws, loc: str, seed: dict) -> str:
    a = run.artifacts
    body = a["draft"] if loc == "id" else a.get("translation_en", a["draft"])
    meta = a.get("meta", {}).get(loc, {})
    by_id = seed["chunks_by_id"]
    ordered = cited_ids(body)
    title, body_html = _md_to_article_html(body, by_id, ordered)
    if not title:
        title = meta.get("meta_title", run.topic_id)

    accent = "#0F6E56" if ws.id == "parakita" else "#3730A3"   # teal / indigo
    accent2 = "#12B886" if ws.id == "parakita" else "#6366F1"
    img = a.get("image", {})
    alt = img.get("alt_id" if loc == "id" else "alt_en", "") or img.get("alt_en", "")
    kw = meta.get("keywords", [])
    rt = meta.get("reading_time_min", "-")
    cat = "Kesehatan Gigi" if ws.id == "parakita" and loc == "id" else \
          ("Dental Health" if ws.id == "parakita" else
           ("Teknologi Pendidikan" if loc == "id" else "EdTech"))
    disc = a.get("disclaimer_id" if loc == "id" else "disclaimer_en", "")

    tags_html = " ".join(f'<span class="tag">#{html.escape(k)}</span>' for k in kw)
    refs = []
    for i, cid in enumerate(ordered, 1):
        c = by_id.get(cid)
        if not c:
            continue
        doi = html.escape(c.doi)
        refs.append(
            f'<li id="ref-{cid}"><span class="rn">{i}.</span> '
            f'{html.escape(", ".join(c.authors))} ({c.year}). '
            f'<i>{html.escape(c.title)}</i>. '
            f'<span class="rt">{c.source_type} · credibility {c.credibility}/5 · '
            f'<a href="https://doi.org/{doi}" target="_blank" rel="noopener">{doi}</a></span></li>')
    refs_html = "\n".join(refs)

    # Featured image: real SDXL output (AMD) if present, else a flat brand-safe SVG banner.
    real_img = img.get("image_data")
    if real_img:
        featured = (f'<div class="hero"><img src="{real_img}" alt="{html.escape(alt)}" '
                    f'style="width:100%;height:280px;object-fit:cover;display:block">'
                    f'<div class="hero-cap">Featured image · generated on AMD Radeon W7900 (SDXL/ROCm)</div></div>')
    else:
        featured = f'''
    <div class="hero">
      <svg viewBox="0 0 1200 500" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
        <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="{accent}"/><stop offset="1" stop-color="{accent2}"/></linearGradient></defs>
        <rect width="1200" height="500" fill="url(#g)"/>
        <circle cx="960" cy="120" r="220" fill="#ffffff" opacity="0.08"/>
        <circle cx="240" cy="430" r="180" fill="#000000" opacity="0.08"/>
        <rect x="80" y="360" width="70" height="70" fill="#ffffff" opacity="0.14"/>
      </svg>
      <div class="hero-cap">AI-generated featured illustration · 1200×630 <span>(SDXL/Flux on AMD — placeholder)</span></div>
    </div>'''

    return f'''<!doctype html><html lang="{loc}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{html.escape(meta.get("meta_description",""))}">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#F3F4F6; color:#1F2937;
         font-family:-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif; line-height:1.7; }}
  .wrap {{ max-width:760px; margin:0 auto; background:#FFFFFF; }}
  .hero {{ position:relative; }}
  .hero svg {{ width:100%; height:280px; display:block; }}
  .hero-cap {{ position:absolute; bottom:8px; right:12px; font-size:11px; color:#fff;
              background:rgba(0,0,0,.35); padding:3px 8px; border-radius:3px; }}
  .hero-cap span {{ opacity:.8; }}
  .content {{ padding:28px 34px 40px; }}
  .cat {{ display:inline-block; text-transform:uppercase; letter-spacing:.12em; font-size:12px;
         font-weight:700; color:{accent}; margin-bottom:10px; }}
  h1 {{ font-size:2.15rem; line-height:1.2; margin:.1rem 0 .5rem; color:#111827; font-weight:800; letter-spacing:-.01em; }}
  .byline {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; color:#6B7280; font-size:14px;
            border-bottom:1px solid #E5E7EB; padding-bottom:16px; margin-bottom:22px; }}
  .avatar {{ width:34px; height:34px; border-radius:50%; background:{accent}; color:#fff; font-weight:700;
            display:flex; align-items:center; justify-content:center; font-size:13px; }}
  .badge {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.05em;
           color:{accent}; border:1px solid {accent}; border-radius:3px; padding:1px 6px; }}
  .content h2 {{ font-size:1.4rem; margin:1.8rem 0 .6rem; color:#111827; font-weight:800; }}
  .content h3 {{ font-size:1.15rem; margin:1.3rem 0 .5rem; color:#111827; }}
  .content p {{ margin:0 0 1.05rem; font-size:1.05rem; }}
  blockquote {{ border-left:3px solid {accent}; margin:1rem 0; padding:.2rem 0 .2rem 1rem; color:#4B5563; }}
  code {{ background:#F3F4F6; padding:1px 5px; border-radius:3px; font-size:.9em; }}
  sup.c a {{ color:{accent}; text-decoration:none; font-weight:700; }}
  .disc {{ background:#FFF7ED; border-left:3px solid #F59E0B; padding:12px 14px; font-size:14px;
          color:#7C2D12; margin:22px 0; border-radius:2px; }}
  .tags {{ margin:22px 0; }}
  .tag {{ display:inline-block; background:#F3F4F6; color:#374151; font-size:13px; padding:3px 10px;
         border-radius:999px; margin:0 6px 6px 0; }}
  .refs {{ border-top:1px solid #E5E7EB; margin-top:26px; padding-top:14px; }}
  .refs h4 {{ font-size:13px; text-transform:uppercase; letter-spacing:.1em; color:#6B7280; margin:0 0 10px; }}
  .refs ol {{ list-style:none; padding:0; margin:0; }}
  .refs li {{ font-size:13.5px; color:#374151; margin-bottom:10px; padding-left:4px; }}
  .rn {{ color:{accent}; font-weight:700; margin-right:4px; }}
  .rt {{ color:#6B7280; }}
  .refs a {{ color:{accent}; }}
  .seo {{ margin-top:26px; padding:14px; background:#F9FAFB; border:1px dashed #D1D5DB; border-radius:4px;
         font-size:12.5px; color:#6B7280; font-family:ui-monospace,Consolas,monospace; }}
</style></head><body><div class="wrap">
  {featured}
  <div class="content">
    <span class="cat">{html.escape(cat)}</span>
    <h1>{html.escape(title)}</h1>
    <div class="byline">
      <div class="avatar">AI</div>
      <div><b>AI-assisted</b> · {_PUB_DATE} · {rt} min read</div>
      <span class="badge">Reviewed by editor</span>
      <span class="badge">Grounded · {len(ordered)} sources</span>
    </div>
    {body_html}
    {f'<div class="disc">{html.escape(disc)}</div>' if disc else ''}
    <div class="tags">{tags_html}</div>
    <div class="refs"><h4>References</h4><ol>{refs_html}</ol></div>
    <div class="seo">meta_title: {html.escape(meta.get("meta_title",""))}<br>
      meta_description: {html.escape(meta.get("meta_description",""))}<br>
      slug: /{html.escape(meta.get("slug",""))}</div>
  </div>
</div></body></html>'''


# --------------------------------------------------------------------------- #
# Page: Article
# --------------------------------------------------------------------------- #
def page_article():
    seed = st.session_state.seed
    published = [h for h in st.session_state.history if h["run"].outcome == "published"]
    page_header(
        "Step 3 · Output", "Article",
        "The final <b>bilingual</b> article (Indonesian source + English translation), with inline "
        "citations, references, featured image and CMS-ready SEO metadata — exactly what gets "
        "injected into your CMS.")

    if not published:
        st.info("No published article yet — run a topic and approve it at Gate 7 first.")
        sticky_footer(("◂ ② Run a pipeline first", "Run pipeline", "primary"))
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

    cms = st.session_state.get("cms_mode", False)
    sticky_footer(
        ("◂ ② Run pipeline", "Run pipeline", "secondary"),
        (("◱ Show Reader Mode" if cms else "◲ Show Web / CMS Mode"), _toggle_cms, "secondary"),
        ("④ Dashboard ▸", "Dashboard", "primary"))

    label = (f'<span class="pill" style="background:{ACCENT};color:{BG};border-color:{ACCENT}">'
             f'AI-ASSISTED</span> <span class="pill">{genre.upper()}</span> '
             f'<span class="pill">REVIEWED BY EDITOR</span>')
    st.markdown(label, unsafe_allow_html=True)

    locales = ws.languages
    tab_labels = {"id": "Indonesian", "en": "English"}

    if cms:
        st.caption("Web / CMS mode — full article as it would render on the connected CMS/website. "
                   "Use the footer button to switch back to Reader mode.")
        loc = st.radio("Language", locales, horizontal=True,
                       format_func=lambda l: tab_labels[l], label_visibility="collapsed")
        components.html(_cms_preview_html(run, ws, loc, seed), height=1500, scrolling=True)
        return

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
    page_header(
        "Step 4 · Metrics", "Dashboard",
        "Session overview — runs, gate outcomes, revisions, and estimated tokens per "
        "article. Accumulates as you run more pipelines.")
    hist = st.session_state.history
    if any(h["run"].outcome == "published" for h in hist):
        sticky_footer(("◂ ③ Article", "Article", "secondary"),
                      ("↻ Run another", "Run pipeline", "primary"))
    else:
        sticky_footer(("◂ ② Run a pipeline", "Run pipeline", "primary"))

    if not hist:
        st.info("No runs yet this session — metrics accumulate as you run pipelines.")
        return

    runs = [h["run"] for h in hist]
    n = len(runs)
    published = sum(1 for r in runs if r.outcome == "published")
    revised = sum(1 for r in runs if r.revision_count > 0)
    rejected = sum(1 for r in runs if r.outcome == "rejected")
    total_tokens = sum(r.total_tokens for r in runs)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Runs", n)
    c2.metric("Published", published)
    c3.metric("Revised", revised)
    c4.metric("Rejected", rejected)
    c5.metric("Total tokens", f"{total_tokens:,}")

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
                "Latency ms": e.latency_ms,
            })
    st.dataframe(arows, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Landing page
# --------------------------------------------------------------------------- #
def page_landing():
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
          <div style="margin-top:.9rem">
            <span class="pill" style="background:{ACCENT};color:#FFFFFF;border-color:{ACCENT}">
              ● LIVE ON AMD RADEON PRO W7900</span>
            <span class="pill">ROCm · gfx1100</span>
            <span class="pill">GEMMA 3 · BGE-M3 · SDXL</span>
            <span class="pill">+ FIREWORKS AI</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("AMD Developer Hackathon · Track 3 — runs on **AMD GPU cloud**, a fully "
               "**ROCm-ported** stack (llama.cpp/HIP · no CUDA), **Google Gemma 3** for cognition, "
               "with **Fireworks AI** as an alternative hosted engine.")

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
            <div class="swiss-kicker">Profile B · Full self-hosted on AMD &nbsp;·&nbsp; ● proven</div>
            <div style="font-size:1.15rem;font-weight:900;margin:.1rem 0 .5rem 0;color:{INK}">Zero API · data never leaves</div>
            <div style="font-size:.86rem;color:{MUTE};line-height:1.5">
              Every model runs on your own AMD GPU — nothing is sent to a third party.<br><br>
              <b>GPU:</b> AMD Radeon PRO <b>W7900</b> (48 GB · gfx1100) — <b>live now</b> on AMD GPU cloud;
              also proven on AMD Instinct <b>MI300X</b> (192 GB HBM3, ROCm)<br>
              <b>LLM:</b> Google <b>Gemma 3</b> (<b>gemma-3-27b-it</b>) via <b>llama.cpp</b> <i>(ROCm/HIP; scales to 70B on the MI300X)</i><br>
              <b>Embeddings:</b> <b>bge-m3</b> &nbsp;·&nbsp; <b>Images:</b> <b>SDXL</b> — same GPU<br>
              <b>Cost:</b> fixed GPU, <b>no per-token charge</b>
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
                <div class="swiss-kicker" style="color:{LABEL}">{t}</div>
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

    # --- Works with ANY topic (two example workspaces) ------------------- #
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">Works with any topic you choose</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:.95rem;color:{INK};max-width:70ch;margin-bottom:.7rem">'
        'FACTOR is <b>topic-agnostic</b>. Spin up a Topic Workspace for <b>any domain you want</b> — '
        'finance, law, agriculture, gaming, medicine, your product docs — point it at your own trusted '
        'sources, and it produces grounded content for that field. '
        f'<span style="color:{MUTE}">The two workspaces below are just examples that ship with this demo.</span>'
        '</div>', unsafe_allow_html=True)
    w1, w2 = st.columns(2)
    w1.markdown(
        f"""<div style="border-top:1px solid {LINE};padding-top:.5rem;min-height:120px">
            <div class="swiss-kicker" style="color:{MUTE}">Example workspace A</div>
            <div style="font-size:1.05rem;font-weight:900;color:{INK}">Dental &amp; Oral Health</div>
            <div style="font-size:.84rem;color:{MUTE};line-height:1.45">100 sample topics · YMYL medical grounding
            (kariologi, periodonsia, endodonsia, ortodonti, pedodonti …). ID → EN.</div>
        </div>""", unsafe_allow_html=True)
    w2.markdown(
        f"""<div style="border-top:1px solid {LINE};padding-top:.5rem;min-height:120px">
            <div class="swiss-kicker" style="color:{MUTE}">Example workspace B</div>
            <div style="font-size:1.05rem;font-weight:900;color:{INK}">IT in Education</div>
            <div style="font-size:.84rem;color:{MUTE};line-height:1.45">100 sample topics · EdTech
            (e-learning, LMS, gamifikasi, AI dalam pendidikan, asesmen digital …). ID → EN.</div>
        </div>""", unsafe_allow_html=True)
    st.markdown(
        f'<div style="margin-top:.9rem;border-left:3px solid {ACCENT};padding-left:.9rem;font-size:.88rem;color:{MUTE}">'
        '<b>Topics are subjects, not titles</b> — you supply the theme, FACTOR writes the article and its title. '
        'You define each workspace and its trusted sources (official sites, scientific journals, curated books); '
        'they are harvested, chunked, embedded into PostgreSQL + pgvector, and hybrid-searched at write time. '
        'A topic becomes runnable once its corpus is ingested. Output: verified, bilingual articles injected '
        'straight into your CMS.</div>',
        unsafe_allow_html=True,
    )

    # --- Honest status ---------------------------------------------------- #
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="hp-title">What is real today</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:.9rem;color:{MUTE};line-height:1.55">'
        f'This demo drives the <b>full pipeline and all 8 gates</b> end-to-end. In the '
        f'<b style="color:{INK}">AMD · Radeon W7900</b> engine, the <b>Writer</b> and <b>Fact-checker</b> run on '
        f'<b style="color:{INK}">Google Gemma 3</b> (llama.cpp), the <b>Researcher</b> retrieves with '
        f'<b style="color:{INK}">bge-m3</b>, and the <b>Image</b> agent uses SDXL — all '
        f'<b style="color:{INK}">live on an AMD Radeon PRO W7900</b> (RDNA3 · ROCm), the GPU provided by the '
        f'hackathon; the full stack is also proven on an <b>AMD Instinct MI300X</b>. A '
        f'<b style="color:{INK}">Fireworks AI</b> engine (gpt-oss-120b + qwen3-embedding-8b) is available too. '
        f'Grounded, correctly-cited '
        f'output; real cosine retrieval; real featured images. The corpus and topic backlog shown here are a curated <b>seed set</b>; '
        f'wiring to a live corpus (Google Drive + journals → pgvector) and publishing into a CMS database are '
        f'the next build (≈1–2 weeks for a real vertical slice). <i>Inference on AMD is real; the data '
        f'integrations are simulated for now.</i></div>',
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

    sticky_footer(("Enter Demo ▸", _enter_demo, "primary"))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    st.markdown(SWISS_CSS, unsafe_allow_html=True)
    init_state()

    if not st.session_state.entered:
        page_landing()
        return

    sidebar()
    page = st.session_state.get("nav", "Workspace")
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
