"""Real semantic retrieval using bge-m3 embeddings served on the AMD MI300X.

Calls the OpenAI-compatible /v1/embeddings endpoint (vLLM) with stdlib urllib,
then ranks the workspace corpus by cosine similarity — pure Python, no numpy,
no new dependency. Chunk embeddings are cached per process.
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any, Optional

from . import live

# in-process cache: backend_key -> {chunk_id -> embedding vector}. Kept per
# backend so vectors from different embedders (e.g. bge-m3 dim 1024 vs
# qwen3-embedding dim 4096) are never mixed in a cosine comparison.
_VEC_CACHE: dict[str, dict[str, list[float]]] = {}

# Gate 1: a chunk counts as "related" if cosine similarity >= this.
RELATED_THRESHOLD = 0.45


def available() -> bool:
    return live.embeddings_available()


def _embed(texts: list[str], url: Optional[str] = None, model: Optional[str] = None,
           key: Optional[str] = None) -> list[list[float]]:
    """POST to any OpenAI-compatible /embeddings endpoint. Defaults to the AMD one."""
    base = url or live.amd_embed_url()
    endpoint = base.rstrip("/") + "/embeddings"
    headers = {"Content-Type": "application/json"}
    k = key if key is not None else live.amd_api_key()
    if k:
        headers["Authorization"] = f"Bearer {k}"
    payload = {"model": model or live.amd_embed_model(), "input": texts}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [d["embedding"] for d in data["data"]]


def _amd_embedder(texts: list[str]) -> list[list[float]]:
    return _embed(texts)


def _fireworks_embedder(texts: list[str]) -> list[list[float]]:
    return _embed(texts, url=live.fireworks_base_url(),
                  model=live.fireworks_embed_model(), key=live.fireworks_api_key())


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


def _ensure_chunk_vecs(chunks, embedder, cache_key: str) -> None:
    cache = _VEC_CACHE.setdefault(cache_key, {})
    missing = [c for c in chunks if c.id not in cache]
    if missing:
        for c, v in zip(missing, embedder([c.content for c in missing])):
            cache[c.id] = v


def retrieve(query: str, chunks, k: int = 6, embedder=None,
             cache_key: str = "amd") -> list[tuple[Any, float]]:
    """Return the top-k (chunk, score) for `query` over `chunks`, best first."""
    if not chunks:
        return []
    emb = embedder or _amd_embedder
    _ensure_chunk_vecs(chunks, emb, cache_key)
    cache = _VEC_CACHE[cache_key]
    qv = emb([query])[0]
    scored = [(c, _cos(qv, cache[c.id])) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def research_pack(topic, workspace, seed, k: int = 6, embedder=None,
                  cache_key: str = "amd", label: str = "bge-m3 on AMD W7900"):
    """Build a live research pack + a real Gate-1 related count for a topic."""
    chunks = [c for c in seed["chunks"] if c.workspace_id == workspace.id]
    query = f"{topic.title_id} {topic.title_en}"
    ranked = retrieve(query, chunks, k=k, embedder=embedder, cache_key=cache_key)
    pack = [{"chunk_id": c.id, "score": round(s, 3),
             "reason": f"cosine {s:.3f} vs topic ({label})"}
            for c, s in ranked]
    related = sum(1 for _, s in retrieve(query, chunks, k=len(chunks),
                                         embedder=embedder, cache_key=cache_key)
                  if s >= RELATED_THRESHOLD)
    avg_cred = (round(sum(c.credibility for c, _ in ranked) / len(ranked), 2)
                if ranked else 0)
    return pack, related, avg_cred


def fireworks_research_pack(topic, workspace, seed, k: int = 6):
    """Research pack using Fireworks embeddings (qwen3-embedding-8b)."""
    return research_pack(topic, workspace, seed, k=k, embedder=_fireworks_embedder,
                         cache_key="fireworks", label="qwen3-embedding-8b on Fireworks")
