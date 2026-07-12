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

# --- AMD backend config ---------------------------------------------------- #
# Default chat model served on the AMD GPU (Google Gemma 3).
AMD_MODEL_DEFAULT = "gemma-3-27b-it"

# --- Fireworks AI backend config ------------------------------------------ #
# OpenAI-compatible. gpt-oss-120b is a reasoning model, so it needs generous
# max_tokens (reasoning tokens are spent before the final answer).
FIREWORKS_BASE_URL_DEFAULT = "https://api.fireworks.ai/inference/v1"
FIREWORKS_MODEL_DEFAULT = "accounts/fireworks/models/gpt-oss-120b"
FIREWORKS_EMBED_MODEL_DEFAULT = "accounts/fireworks/models/qwen3-embedding-8b"
FIREWORKS_MAX_TOKENS = 4096


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


# --- AMD embeddings (bge-m3 on MI300X) ------------------------------------ #
def amd_embed_url() -> Optional[str]:
    return _secret("AMD_EMBED_URL")


def amd_embed_model() -> str:
    return _secret("AMD_EMBED_MODEL") or "embeddinggemma"


def embeddings_available() -> bool:
    return bool(amd_embed_url())


# --- AMD image generation (SDXL on MI300X) -------------------------------- #
def amd_image_url() -> Optional[str]:
    return _secret("AMD_IMAGE_URL")


def image_available() -> bool:
    return bool(amd_image_url())


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
    """True if an AMD endpoint is configured."""
    return bool(amd_base_url())


# --- Fireworks AI config (env or st.secrets) ------------------------------ #
def fireworks_api_key() -> Optional[str]:
    return _secret("FIREWORKS_API_KEY")


def fireworks_base_url() -> str:
    return _secret("FIREWORKS_BASE_URL") or FIREWORKS_BASE_URL_DEFAULT


def fireworks_model() -> str:
    return _secret("FIREWORKS_MODEL") or FIREWORKS_MODEL_DEFAULT


def fireworks_embed_model() -> str:
    return _secret("FIREWORKS_EMBED_MODEL") or FIREWORKS_EMBED_MODEL_DEFAULT


def fireworks_available() -> bool:
    """True if a Fireworks AI API key is configured."""
    return bool(fireworks_api_key())


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


def _oai_chat(base_url: str, model: str, key: Optional[str], system: str, user: str,
              temperature: float, max_tokens: int = MAX_TOKENS) -> str:
    """Call any OpenAI-compatible /chat/completions endpoint (stdlib only).

    Reasoning models (e.g. gpt-oss) put chain-of-thought in `reasoning_content`
    and the answer in `content`; we return `content`.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data["choices"][0]["message"].get("content") or "").strip()


def _amd_chat(system: str, user: str, temperature: float) -> str:
    """Call the AMD-hosted OpenAI-compatible endpoint (Gemma on the AMD GPU).

    Gemma has no `system` role — its chat template drops system messages — so we
    fold the instructions into the user turn to keep them (citations, language).
    """
    prompt = f"{system}\n\n{user}" if system else user
    return _oai_chat(amd_base_url(), amd_model(), amd_api_key(), "", prompt, temperature)


def _fireworks_chat(system: str, user: str, temperature: float) -> str:
    """Call Fireworks AI (gpt-oss-120b by default)."""
    return _oai_chat(fireworks_base_url(), fireworks_model(), fireworks_api_key(),
                     system, user, temperature, FIREWORKS_MAX_TOKENS)


# --------------------------------------------------------------------------- #
# Shared prompt builders
# --------------------------------------------------------------------------- #
def _pack_chunks(seed: dict[str, Any], canned: dict[str, Any],
                 pack: Optional[list] = None) -> list[dict[str, Any]]:
    """Resolve the research-pack chunk ids to chunk text. Uses the live `pack`
    (real retrieval) when given, otherwise the canned research pack."""
    by_id = seed["chunks_by_id"]
    items = pack if pack is not None else canned.get("research_pack", [])
    out = []
    for item in items:
        c = by_id.get(item["chunk_id"])
        if c:
            out.append({"chunk_id": c.id, "content": c.content,
                        "source": c.title, "credibility": c.credibility})
    return out


def _writer_prompt(topic, workspace, seed, canned, pack=None) -> tuple[str, str]:
    chunks = _pack_chunks(seed, canned, pack)
    corpus = "\n".join(f"[[chunk:{c['chunk_id']}]] {c['content']}" for c in chunks)
    system = (
        "You are FACTOR's Writer agent. Write ONLY from the provided source chunks. "
        "Every factual claim MUST end with an inline citation marker of the exact form "
        "[[chunk:ID]] using an ID that appears in the sources. Never invent facts or IDs. "
        "Write in English. Use Markdown with ## headings. Keep it under 350 words."
    )
    user = (f"Topic: {topic.title_en}\nGenre: {topic.genre}\n\nSOURCE CHUNKS:\n{corpus}\n\n"
            "Write the article now.")
    return system, user


def _factchecker_prompt(topic, workspace, seed, canned, draft: str, pack=None) -> tuple[str, str]:
    chunks = _pack_chunks(seed, canned, pack)
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


def _translator_prompt(draft: str) -> tuple[str, str]:
    system = (
        "You are FACTOR's Translator agent. Translate the article below from English "
        "into natural, fluent Indonesian. PRESERVE every inline citation marker of the exact "
        "form [[chunk:ID]] unchanged and in the same place, and keep the Markdown structure "
        "(## headings, lists). Output ONLY the translated article — no notes, no preamble."
    )
    return system, draft


def _parse_claims(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    start, end = raw.find("["), raw.rfind("]")
    parsed = json.loads(raw[start:end + 1])
    out = []
    for i, c in enumerate(parsed):
        if not isinstance(c, dict):
            continue
        # Coerce every field to str: the model may emit null / numbers / nested
        # objects, and `dict.get(k, default)` returns None (not default) on null.
        verdict = str(c.get("verdict") or "partial").strip().lower()
        if verdict not in ("supported", "partial", "unsupported", "contradicted"):
            verdict = "partial"
        out.append({
            "id": str(c.get("id") or f"cl{i+1}"),
            "text": str(c.get("text") or ""),
            "chunk_id": str(c.get("chunk_id") or ""),
            "verdict": verdict,
            "note": str(c.get("note") or ""),
        })
    return out


# --------------------------------------------------------------------------- #
# Anthropic backend (LIVE)
# --------------------------------------------------------------------------- #
def live_writer(topic, workspace, seed, canned, pack=None) -> str:
    system, user = _writer_prompt(topic, workspace, seed, canned, pack)
    return _anthropic_chat(system, user, WRITER_MODEL, 0.3)


def live_factchecker(topic, workspace, seed, canned, draft: str, pack=None) -> list[dict]:
    system, user = _factchecker_prompt(topic, workspace, seed, canned, draft, pack)
    return _parse_claims(_anthropic_chat(system, user, FACTCHECKER_MODEL, 0.2))


# --------------------------------------------------------------------------- #
# AMD / vLLM backend (runs on AMD Instinct MI300X via ROCm)
# --------------------------------------------------------------------------- #
def amd_writer(topic, workspace, seed, canned, pack=None) -> str:
    system, user = _writer_prompt(topic, workspace, seed, canned, pack)
    return _amd_chat(system, user, 0.3)


def amd_factchecker(topic, workspace, seed, canned, draft: str, pack=None) -> list[dict]:
    system, user = _factchecker_prompt(topic, workspace, seed, canned, draft, pack)
    return _parse_claims(_amd_chat(system, user, 0.2))


def amd_translator(draft: str) -> str:
    system, user = _translator_prompt(draft)
    return _amd_chat(system, user, 0.2)


# --------------------------------------------------------------------------- #
# Fireworks AI backend (gpt-oss-120b)
# --------------------------------------------------------------------------- #
def fireworks_writer(topic, workspace, seed, canned, pack=None) -> str:
    system, user = _writer_prompt(topic, workspace, seed, canned, pack)
    return _fireworks_chat(system, user, 0.3)


def fireworks_factchecker(topic, workspace, seed, canned, draft: str, pack=None) -> list[dict]:
    system, user = _factchecker_prompt(topic, workspace, seed, canned, draft, pack)
    return _parse_claims(_fireworks_chat(system, user, 0.2))


def fireworks_translator(draft: str) -> str:
    system, user = _translator_prompt(draft)
    return _fireworks_chat(system, user, 0.2)
