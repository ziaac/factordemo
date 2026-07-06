"""Optional LIVE mode — real Claude API calls for the Writer and Fact-checker.

Everything here is best-effort: if the `anthropic` package is missing, no API
key is present, or a call fails, the caller (mock engine) catches the exception
and falls back to the canned output. Only two steps are ever "live" — the rest
of the pipeline stays mock so the demo remains cheap and deterministic.

Model choices follow docs/demo-spec.md: Sonnet for the writer, Opus for the
fact-checker, max_tokens capped at 2000/step.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

WRITER_MODEL = "claude-sonnet-4-5"
FACTCHECKER_MODEL = "claude-opus-4-8"
MAX_TOKENS = 2000


def api_key() -> Optional[str]:
    """Resolve the key from st.secrets (if Streamlit) or the environment."""
    try:
        import streamlit as st  # local import: keep engine importable without st
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def live_available() -> bool:
    if not api_key():
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=api_key())


def _chunks_for_topic(seed: dict[str, Any], canned: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = seed["chunks_by_id"]
    out = []
    for item in canned.get("research_pack", []):
        c = by_id.get(item["chunk_id"])
        if c:
            out.append({"chunk_id": c.id, "content": c.content,
                        "source": c.title, "credibility": c.credibility})
    return out


# --------------------------------------------------------------------------- #
# Writer
# --------------------------------------------------------------------------- #
def live_writer(topic, workspace, seed, canned) -> str:
    """Ask Claude to write a grounded draft from ONLY the research-pack chunks."""
    chunks = _chunks_for_topic(seed, canned)
    corpus = "\n".join(f"[[chunk:{c['chunk_id']}]] {c['content']}" for c in chunks)
    lang = "Bahasa Indonesia" if workspace.id == "parakita" else "English"
    system = (
        "You are FACTOR's Writer agent. Write ONLY from the provided source chunks. "
        "Every factual claim MUST end with an inline citation marker of the exact form "
        "[[chunk:ID]] using an ID that appears in the sources. Never invent facts or IDs. "
        f"Write in {lang}. Use Markdown with ## headings. Keep it under 350 words."
    )
    user = (
        f"Topic: {topic.title_en}\nGenre: {topic.genre}\n\nSOURCE CHUNKS:\n{corpus}\n\n"
        "Write the article now."
    )
    msg = _client().messages.create(
        model=WRITER_MODEL, max_tokens=MAX_TOKENS, temperature=0.3,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


# --------------------------------------------------------------------------- #
# Fact-checker
# --------------------------------------------------------------------------- #
def live_factchecker(topic, workspace, seed, canned, draft: str) -> list[dict]:
    """Ask a separate model to verify each claim against the original chunks."""
    chunks = _chunks_for_topic(seed, canned)
    corpus = "\n".join(f"[[chunk:{c['chunk_id']}]] {c['content']}" for c in chunks)
    system = (
        "You are FACTOR's independent Fact-checker agent. You did NOT write this draft. "
        "For each cited claim, compare it against the referenced source chunk and assign a "
        "verdict: supported | partial | unsupported | contradicted. "
        "Return ONLY a JSON array of objects: "
        '[{"id","text","chunk_id","verdict","note"}]. No prose.'
    )
    user = f"SOURCE CHUNKS:\n{corpus}\n\nDRAFT:\n{draft}\n\nReturn the JSON array."
    msg = _client().messages.create(
        model=FACTCHECKER_MODEL, max_tokens=MAX_TOKENS, temperature=0.2,
        system=system, messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    # Be forgiving about code fences.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    start, end = raw.find("["), raw.rfind("]")
    parsed = json.loads(raw[start:end + 1])
    # Normalize keys.
    out = []
    for i, c in enumerate(parsed):
        out.append({
            "id": c.get("id", f"cl{i+1}"),
            "text": c.get("text", ""),
            "chunk_id": c.get("chunk_id", ""),
            "verdict": c.get("verdict", "partial"),
            "note": c.get("note", ""),
        })
    return out
