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

# in-process cache: chunk_id -> embedding vector
_VEC_CACHE: dict[str, list[float]] = {}

# Gate 1: a chunk counts as "related" if cosine similarity >= this.
RELATED_THRESHOLD = 0.45


def available() -> bool:
    return live.embeddings_available()


def _embed(texts: list[str]) -> list[list[float]]:
    url = live.amd_embed_url().rstrip("/") + "/embeddings"
    headers = {"Content-Type": "application/json"}
    key = live.amd_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": live.amd_embed_model(), "input": texts}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [d["embedding"] for d in data["data"]]


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


def _ensure_chunk_vecs(chunks) -> None:
    missing = [c for c in chunks if c.id not in _VEC_CACHE]
    if missing:
        for c, v in zip(missing, _embed([c.content for c in missing])):
            _VEC_CACHE[c.id] = v


def retrieve(query: str, chunks, k: int = 6) -> list[tuple[Any, float]]:
    """Return the top-k (chunk, score) for `query` over `chunks`, best first."""
    if not chunks:
        return []
    _ensure_chunk_vecs(chunks)
    qv = _embed([query])[0]
    scored = [(c, _cos(qv, _VEC_CACHE[c.id])) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def research_pack(topic, workspace, seed, k: int = 6):
    """Build a live research pack + a real Gate-1 related count for a topic."""
    chunks = [c for c in seed["chunks"] if c.workspace_id == workspace.id]
    query = f"{topic.title_id} {topic.title_en}"
    ranked = retrieve(query, chunks, k=k)
    pack = [{"chunk_id": c.id, "score": round(s, 3),
             "reason": f"cosine {s:.3f} vs topic (bge-m3 on MI300X)"}
            for c, s in ranked]
    related = sum(1 for _, s in retrieve(query, chunks, k=len(chunks))
                  if s >= RELATED_THRESHOLD)
    avg_cred = (round(sum(c.credibility for c, _ in ranked) / len(ranked), 2)
                if ranked else 0)
    return pack, related, avg_cred
