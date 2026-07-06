r"""FACTOR pipeline state machine.

Mirrors the whitepaper flow:

    QUEUED -> PLANNING -> RESEARCHING -> OUTLINING -> DRAFTING
      -> FACT_CHECKING -> BIAS_REVIEW -> [REVISING loop <=3]
      -> TRANSLATING -> TRANSLATION_QA -> META_SEO -> IMAGE_GEN
      -> [HUMAN_REVIEW] -> PUBLISHING -> PUBLISHED
                        \-> REJECTED / NEEDS_ATTENTION

The demo drives states explicitly, but this module is the single source of
truth for the ordered "happy path" and the human-readable labels / agents so
the UI stepper and the mock engine never disagree.
"""

from __future__ import annotations

# Canonical ordered happy-path states shown in the horizontal stepper.
PIPELINE_STATES: list[str] = [
    "QUEUED",
    "PLANNING",
    "RESEARCHING",
    "OUTLINING",
    "DRAFTING",
    "FACT_CHECKING",
    "BIAS_REVIEW",
    "REVISING",
    "TRANSLATING",
    "TRANSLATION_QA",
    "META_SEO",
    "IMAGE_GEN",
    "HUMAN_REVIEW",
    "PUBLISHING",
    "PUBLISHED",
]

# Terminal / off-path states.
TERMINAL_STATES: set[str] = {"PUBLISHED", "REJECTED", "NEEDS_ATTENTION"}

# Which agent owns each step (whitepaper §4) + the model tier used in LIVE mode.
STEP_META: dict[str, dict[str, str]] = {
    "QUEUED":         {"agent": "Orchestrator", "model": "-",                 "gate": ""},
    "PLANNING":       {"agent": "Planner",       "model": "LLM · fast"    , "gate": ""},
    "RESEARCHING":    {"agent": "Researcher",    "model": "hybrid-search",    "gate": "Gate 1 · source sufficiency"},
    "OUTLINING":      {"agent": "Outliner",      "model": "LLM · standard","gate": ""},
    "DRAFTING":       {"agent": "Writer (ID)",   "model": "LLM · standard","gate": "Gate 2 · grounded writing"},
    "FACT_CHECKING":  {"agent": "Fact-checker",  "model": "LLM · frontier",  "gate": "Gate 3 · independent fact-check"},
    "BIAS_REVIEW":    {"agent": "Bias reviewer", "model": "LLM · standard","gate": "Gate 4 · bias & ethics"},
    "REVISING":       {"agent": "Writer (ID)",   "model": "LLM · standard","gate": ""},
    "TRANSLATING":    {"agent": "Translator",    "model": "LLM · standard","gate": ""},
    "TRANSLATION_QA": {"agent": "Translator QA", "model": "LLM · standard","gate": "Gate 5 · cross-lingual consistency"},
    "META_SEO":       {"agent": "Meta / SEO",    "model": "LLM · fast"    , "gate": "Gate 6 · schema validation"},
    "IMAGE_GEN":      {"agent": "Image",         "model": "imagen-3",         "gate": ""},
    "HUMAN_REVIEW":   {"agent": "Human editor",  "model": "-",                "gate": "Gate 7 · human review"},
    "PUBLISHING":     {"agent": "Publisher",     "model": "-",                "gate": ""},
    "PUBLISHED":      {"agent": "Publisher",     "model": "-",                "gate": "Gate 8 · post-publish audit"},
    "REJECTED":       {"agent": "-",             "model": "-",                "gate": ""},
    "NEEDS_ATTENTION":{"agent": "-",             "model": "-",                "gate": ""},
}

MAX_REVISIONS = 3
MIN_CHUNKS_GATE1 = 5  # Gate 1 threshold: need >= 5 related chunks to run.


def next_state(current: str) -> str | None:
    """Return the next happy-path state, or None if terminal / unknown."""
    if current in TERMINAL_STATES:
        return None
    try:
        idx = PIPELINE_STATES.index(current)
    except ValueError:
        return None
    if idx + 1 < len(PIPELINE_STATES):
        return PIPELINE_STATES[idx + 1]
    return None


def step_label(state: str) -> str:
    return state.replace("_", " ").title()
