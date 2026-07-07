"""Optional LIVE modes — real LLM calls for the Writer and Fact-checker.

Two backends are supported, both best-effort (any failure is caught by the mock
engine, which falls back to the canned output):

  * ANTHROPIC  — hosted LLM API via the `anthropic` SDK (needs ANTHROPIC_API_KEY).
  * AMD        — an OpenAI-compatible endpoint served by **vLLM on an AMD Instinct
                 MI300X (ROCm)**. Called over plain HTTP with stdlib `urllib`, so
                 it adds no dependency. Configure with AMD_BASE_URL / AMD_MODEL /
                 AMD_API_KEY (env or st.secrets).

Only the Writer and Fact-checker steps are ever "live"; the rest of the pipeline
stays mock so the demo remains cheap and deterministic.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Optional

# --- Anthropic backend config --------------------------------------------- #
WRITER_MODEL = "claude-sonnet-4-5"
FACTCHECKER_MODEL = "claude-opus-4-8"
MAX_TOKENS = 2000

# --- AMD / vLLM backend config -------------------------------------------- #
AMD_MODEL_DEFAULT = "qwen2.5-7b-instruct"


# --------------------------------------------------------------------------- #
# Config resolution (env or st.secrets)
# --------------------------------------------------------------------------- #
def _secret(name: str) -> Optional[str]:
    try:
        import streamlit as st  # local import: keep engine importable without st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def api_key() -> Optional[str]:
    return _secret("ANTHROPIC_API_KEY")


def amd_base_url() -> Optional[str]:
    """OpenAI-compatible base URL of the vLLM/MI300X server, e.g. http://host:8000/v1."""
    return _secret("AMD_BASE_URL")


def amd_model() -> str:
    return _secret("AMD_MODEL") or AMD_MODEL_DEFAULT


def amd_api_key() -> Optional[str]:
    return _secret("AMD_API_KEY")


def live_available() -> bool:
    """True if the Anthropic backend can be used."""
    if not api_key():
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def amd_available() -> bool:
    """True if an AMD/vLLM endpoint is configured."""
    return bool(amd_base_url())


# --------------------------------------------------------------------------- #
# Backend calls
# --------------------------------------------------------------------------- #
def _anthropic_chat(system: str, user: str, model: str, temperature: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key())
    msg = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, temperature=temperature,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def _amd_chat(system: str, user: str, temperature: float) -> str:
    """Call the vLLM OpenAI-compatible /chat/completions endpoint (stdlib only)."""
    url = amd_base_url().rstrip("/") + "/chat/completions"
    payload = {
        "model": amd_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}
    key = amd_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------------------------- #
# Shared prompt builders
# --------------------------------------------------------------------------- #
def _chunks_for_topic(seed: dict[str, Any], canned: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = seed["chunks_by_id"]
    out = []
    for item in canned.get("research_pack", []):
        c = by_id.get(item["chunk_id"])
        if c:
            out.append({"chunk_id": c.id, "content": c.content,
                        "source": c.title, "credibility": c.credibility})
    return out


def _writer_prompt(topic, workspace, seed, canned) -> tuple[str, str]:
    chunks = _chunks_for_topic(seed, canned)
    corpus = "\n".join(f"[[chunk:{c['chunk_id']}]] {c['content']}" for c in chunks)
    lang = "Bahasa Indonesia" if workspace.id == "parakita" else "English"
    system = (
        "You are FACTOR's Writer agent. Write ONLY from the provided source chunks. "
        "Every factual claim MUST end with an inline citation marker of the exact form "
        "[[chunk:ID]] using an ID that appears in the sources. Never invent facts or IDs. "
        f"Write in {lang}. Use Markdown with ## headings. Keep it under 350 words."
    )
    user = (f"Topic: {topic.title_en}\nGenre: {topic.genre}\n\nSOURCE CHUNKS:\n{corpus}\n\n"
            "Write the article now.")
    return system, user


def _factchecker_prompt(topic, workspace, seed, canned, draft: str) -> tuple[str, str]:
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
    return system, user


def _parse_claims(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    start, end = raw.find("["), raw.rfind("]")
    parsed = json.loads(raw[start:end + 1])
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


# --------------------------------------------------------------------------- #
# Anthropic backend (LIVE)
# --------------------------------------------------------------------------- #
def live_writer(topic, workspace, seed, canned) -> str:
    system, user = _writer_prompt(topic, workspace, seed, canned)
    return _anthropic_chat(system, user, WRITER_MODEL, 0.3)


def live_factchecker(topic, workspace, seed, canned, draft: str) -> list[dict]:
    system, user = _factchecker_prompt(topic, workspace, seed, canned, draft)
    return _parse_claims(_anthropic_chat(system, user, FACTCHECKER_MODEL, 0.2))


# --------------------------------------------------------------------------- #
# AMD / vLLM backend (runs on AMD Instinct MI300X via ROCm)
# --------------------------------------------------------------------------- #
def amd_writer(topic, workspace, seed, canned) -> str:
    system, user = _writer_prompt(topic, workspace, seed, canned)
    return _amd_chat(system, user, 0.3)


def amd_factchecker(topic, workspace, seed, canned, draft: str) -> list[dict]:
    system, user = _factchecker_prompt(topic, workspace, seed, canned, draft)
    return _parse_claims(_amd_chat(system, user, 0.2))
