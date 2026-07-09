"""Mock pipeline engine — deterministic, canonical outputs from the seed data.

The engine is a generator: it mutates a `Run` and yields it after each step so
the Streamlit UI can render the stepper advancing in real time. It never needs
network access; LIVE mode is layered on top by passing optional callables that
override just the Writer and Fact-checker steps (see `engine/live.py`).
"""

from __future__ import annotations

import json
import os
import random
from typing import Any, Callable, Iterator, Optional

from .models import Chunk, Topic, Workspace, Run, RunEvent, Claim
from . import state_machine as sm

# --------------------------------------------------------------------------- #
# Seed loading
# --------------------------------------------------------------------------- #
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_json(name: str) -> Any:
    with open(os.path.join(_DATA_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_seed() -> dict[str, Any]:
    """Load all seed data once and index it for convenient lookup."""
    workspaces = [Workspace.from_dict(w) for w in _load_json("workspaces.json")]
    topics = [Topic.from_dict(t) for t in _load_json("topics.json")]
    chunks = [Chunk.from_dict(c) for c in _load_json("chunks.json")]
    canned = _load_json("canned_runs.json")
    return {
        "workspaces": workspaces,
        "workspaces_by_id": {w.id: w for w in workspaces},
        "topics": topics,
        "topics_by_id": {t.id: t for t in topics},
        "chunks": chunks,
        "chunks_by_id": {c.id: c for c in chunks},
        "canned": canned,
    }


# --------------------------------------------------------------------------- #
# Per-step token / cost simulation (numbers from whitepaper §9)
# --------------------------------------------------------------------------- #
# step -> (input_tokens, output_tokens, cost_usd)
_STEP_SIM: dict[str, tuple[int, int, float]] = {
    "PLANNING":       (3000, 800, 0.02),
    "RESEARCHING":    (8000, 500, 0.03),
    "OUTLINING":      (12000, 2000, 0.07),
    "DRAFTING":       (28000, 3500, 0.10),
    "FACT_CHECKING":  (34000, 2800, 0.45),
    "BIAS_REVIEW":    (15000, 1200, 0.05),
    "REVISING":       (18000, 3000, 0.08),
    "TRANSLATING":    (12000, 3500, 0.07),
    "TRANSLATION_QA": (8000, 900, 0.03),
    "META_SEO":       (2500, 700, 0.01),
    "IMAGE_GEN":      (0, 0, 0.05),
    "HUMAN_REVIEW":   (0, 0, 0.0),
    "PUBLISHING":     (0, 0, 0.0),
    "PUBLISHED":      (0, 0, 0.0),
    "RESEARCHING_FAIL": (8000, 200, 0.03),
}


def _mk_event(step: str, status: str, note: str = "", key: str | None = None) -> RunEvent:
    in_tok, out_tok, cost = _STEP_SIM.get(key or step, (0, 0, 0.0))
    latency = random.randint(600, 2200)
    return RunEvent(
        step=step,
        status=status,
        model=sm.STEP_META.get(step, {}).get("model", "-"),
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency,
        cost_usd=cost,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Pipeline generator
# --------------------------------------------------------------------------- #
def start_run(topic: Topic, workspace: Workspace) -> Run:
    return Run(topic_id=topic.id, workspace_id=workspace.id, genre=topic.genre)


def gate1_ok(topic: Topic) -> bool:
    return topic.related_chunk_count >= sm.MIN_CHUNKS_GATE1


def iter_pipeline(
    run: Run,
    topic: Topic,
    workspace: Workspace,
    seed: dict[str, Any],
    live_writer: Optional[Callable[..., str]] = None,
    live_factchecker: Optional[Callable[..., list[dict]]] = None,
    live_retriever: Optional[Callable[..., tuple]] = None,
    live_imager: Optional[Callable[..., Optional[str]]] = None,
) -> Iterator[Run]:
    """Drive the run through the state machine, yielding `run` after each step.

    Stops (returns) at HUMAN_REVIEW so the UI can present Approve/Reject.
    Call `finish_publish()` to complete after the editor decides.
    """
    canned = seed["canned"].get(topic.id, {})

    # --- PLANNING --------------------------------------------------------- #
    run.state = "PLANNING"
    run.artifacts["plan"] = {
        "article_type": topic.genre,
        "angle": topic.title_en,
        "target_audience": "general public" if workspace.id == "parakita" else "developers",
    }
    run.events.append(_mk_event("PLANNING", "ok", "Selected topic; set angle & audience."))
    yield run

    # --- RESEARCHING (Gate 1) -------------------------------------------- #
    run.state = "RESEARCHING"
    if not gate1_ok(topic):
        run.events.append(
            _mk_event(
                "RESEARCHING", "gate_failed",
                f"Gate 1 FAILED: only {topic.related_chunk_count} related chunks "
                f"(< {sm.MIN_CHUNKS_GATE1}). Aborting run; topic marked insufficient_sources.",
                key="RESEARCHING_FAIL",
            )
        )
        run.state = "REJECTED"
        run.outcome = "rejected"
        run.artifacts["reject_reason"] = (
            f"Gate 1 (source sufficiency): topic has {topic.related_chunk_count} related "
            f"chunks, below the threshold of {sm.MIN_CHUNKS_GATE1}. "
            "No draft was produced — this is the anti-hallucination gate working."
        )
        yield run
        return

    pack = canned.get("research_pack", [])
    avg = canned.get("avg_credibility")
    src = "seed"
    if live_retriever is not None:
        try:
            pack, _related, avg = live_retriever(topic, workspace, seed)
            reason = pack[0].get("reason", "") if pack and isinstance(pack[0], dict) else ""
            src = reason[reason.rfind("(") + 1:-1] if reason.endswith(")") and "(" in reason else "live embeddings"
            run.artifacts["retrieval"] = src
            run.artifacts.setdefault("live_used", []).append("Researcher (embeddings)")
        except Exception as exc:
            run.artifacts.setdefault("live_warnings", []).append(
                f"Retrieval LIVE failed ({exc}); used seed pack.")
    run.artifacts["research_pack"] = pack
    run.artifacts["avg_credibility"] = avg
    run.events.append(
        _mk_event("RESEARCHING", "ok",
                  f"Gate 1 PASSED: {len(pack)} chunks ranked by {src} "
                  f"(avg credibility {avg}).")
    )
    yield run

    # --- OUTLINING -------------------------------------------------------- #
    run.state = "OUTLINING"
    run.artifacts["outline"] = canned.get("outline", [])
    run.events.append(_mk_event("OUTLINING", "ok", "Produced H2/H3 outline with chunk_id per claim."))
    yield run

    # --- DRAFTING --------------------------------------------------------- #
    run.state = "DRAFTING"
    draft = canned.get("draft_id", "")
    is_revision = "draft_id_v1" in canned
    if is_revision:
        draft = canned.get("draft_id_v1", draft)  # first pass uses v1

    if live_writer is not None:
        try:
            draft = live_writer(topic, workspace, seed, canned, run.artifacts.get("research_pack"))
            run.artifacts.setdefault("live_used", []).append("Writer")
        except Exception as exc:  # graceful fallback to mock
            run.artifacts.setdefault("live_warnings", []).append(f"Writer LIVE failed ({exc}); used mock draft.")
    run.artifacts["draft"] = draft
    run.artifacts["draft_version"] = 1
    run.events.append(_mk_event("DRAFTING", "ok", "Wrote grounded draft with [[chunk:id]] markers (Gate 2)."))
    yield run

    # --- FACT_CHECKING (Gate 3) + optional REVISING ---------------------- #
    def _run_factcheck(claims_key: str, verdict_key: str) -> tuple[list[dict], str]:
        claims = canned.get(claims_key, [])
        verdict = canned.get(verdict_key, "pass")
        if live_factchecker is not None:
            try:
                claims = live_factchecker(topic, workspace, seed, canned,
                                          run.artifacts.get("draft", ""),
                                          run.artifacts.get("research_pack"))
                verdict = "revise" if any(c["verdict"] in ("unsupported", "contradicted") for c in claims) else "pass"
                run.artifacts.setdefault("live_used", []).append("Fact-checker")
            except Exception as exc:
                run.artifacts.setdefault("live_warnings", []).append(f"Fact-checker LIVE failed ({exc}); used mock report.")
        return claims, verdict

    if is_revision:
        # First fact-check pass on v1 → should flag an unsupported/contradicted claim.
        run.state = "FACT_CHECKING"
        claims_v1, verdict_v1 = _run_factcheck("claims_v1", "verdict_v1")
        run.artifacts["claims"] = claims_v1
        bad = [c for c in claims_v1 if c["verdict"] in ("unsupported", "contradicted")]
        run.events.append(
            _mk_event("FACT_CHECKING", "gate_failed",
                      f"Gate 3: {len(bad)} claim(s) {', '.join(c['verdict'] for c in bad)} "
                      f"→ verdict '{verdict_v1}'. Sending back to REVISING.")
        )
        yield run

        # REVISING
        run.state = "REVISING"
        run.revision_count += 1
        run.artifacts["draft"] = canned.get("draft_id", "")
        run.artifacts["draft_version"] = 2
        run.artifacts["diff"] = canned.get("diff", {})
        run.events.append(
            _mk_event("REVISING", "ok",
                      f"Revision {run.revision_count}/{sm.MAX_REVISIONS}: rewrote flagged claim to match source.")
        )
        yield run

        # Second fact-check pass on v2 → pass.
        run.state = "FACT_CHECKING"
        claims_final, verdict_final = _run_factcheck("claims", "verdict")
        run.artifacts["claims"] = claims_final
        run.events.append(
            _mk_event("FACT_CHECKING", "ok",
                      f"Gate 3 re-check: verdict '{verdict_final}' — all claims supported/partial.")
        )
        yield run
    else:
        run.state = "FACT_CHECKING"
        claims_final, verdict_final = _run_factcheck("claims", "verdict")
        run.artifacts["claims"] = claims_final
        bad = [c for c in claims_final if c["verdict"] in ("unsupported", "contradicted")]
        status = "ok" if not bad else "gate_failed"
        run.events.append(
            _mk_event("FACT_CHECKING", status,
                      f"Gate 3: verdict '{verdict_final}' ({len(bad)} unsupported/contradicted).")
        )
        yield run

    # --- BIAS_REVIEW (Gate 4) -------------------------------------------- #
    run.state = "BIAS_REVIEW"
    run.artifacts["bias"] = canned.get("bias", {})
    run.events.append(
        _mk_event("BIAS_REVIEW", "ok",
                  f"Gate 4: bias score {canned.get('bias', {}).get('score', '-')}/5 — no revision needed.")
    )
    yield run

    # --- TRANSLATING ------------------------------------------------------ #
    run.state = "TRANSLATING"
    trans = canned.get("translation_en", "")
    if trans == "SAME_AS_SOURCE":
        trans = canned.get("draft_id", "")
        run.artifacts["translation_note"] = "Workspace is English-only; translator is a no-op."
    run.artifacts["translation_en"] = trans
    run.events.append(_mk_event("TRANSLATING", "ok", "Transcreated to EN, preserving citation markers."))
    yield run

    # --- TRANSLATION_QA (Gate 5) ----------------------------------------- #
    run.state = "TRANSLATION_QA"
    run.artifacts["qa"] = canned.get("qa", {})
    run.events.append(
        _mk_event("TRANSLATION_QA", "ok",
                  f"Gate 5: cross-lingual QA {canned.get('qa', {}).get('status', 'pass')} — no meaning drift.")
    )
    yield run

    # --- META_SEO (Gate 6) ----------------------------------------------- #
    run.state = "META_SEO"
    run.artifacts["meta"] = canned.get("meta", {})
    run.events.append(_mk_event("META_SEO", "ok", "Gate 6: schema/meta JSON validated per locale."))
    yield run

    # --- IMAGE_GEN -------------------------------------------------------- #
    run.state = "IMAGE_GEN"
    image = dict(canned.get("image", {}))
    note = "Generated brand-safe featured illustration (placeholder)."
    if live_imager is not None and image.get("prompt"):
        try:
            data_uri = live_imager(image["prompt"])
            if data_uri:
                image["image_data"] = data_uri
                image["gen_model"] = "SDXL · AMD Radeon W7900"
                note = "Generated featured image on AMD MI300X (SDXL/ROCm)."
                run.artifacts.setdefault("live_used", []).append("Image (SDXL)")
            else:
                run.artifacts.setdefault("live_warnings", []).append(
                    "Image LIVE returned nothing; used placeholder.")
        except Exception as exc:
            run.artifacts.setdefault("live_warnings", []).append(
                f"Image LIVE failed ({exc}); used placeholder.")
    run.artifacts["image"] = image
    run.events.append(_mk_event("IMAGE_GEN", "ok", note))
    yield run

    # --- HUMAN_REVIEW (Gate 7) — pause ----------------------------------- #
    run.state = "HUMAN_REVIEW"
    run.outcome = "awaiting_review"
    run.artifacts["disclaimer_id"] = canned.get("disclaimer_id", "")
    run.artifacts["disclaimer_en"] = canned.get("disclaimer_en", "")
    run.events.append(_mk_event("HUMAN_REVIEW", "awaiting", "Gate 7: awaiting editor approval."))
    yield run
    return


def finish_publish(run: Run, approve: bool) -> Run:
    """Complete a run after the human editor decides at HUMAN_REVIEW."""
    if approve:
        run.events.append(_mk_event("HUMAN_REVIEW", "approved", "Editor approved."))
        run.state = "PUBLISHING"
        run.events.append(_mk_event("PUBLISHING", "ok", "Transactional insert into CMS (articles + translations + citations)."))
        run.state = "PUBLISHED"
        run.outcome = "published"
        run.events.append(_mk_event("PUBLISHED", "ok", "Gate 8: scheduled post-publish audit registered."))
    else:
        run.events.append(_mk_event("HUMAN_REVIEW", "rejected", "Editor rejected; sent back to queue."))
        run.state = "REJECTED"
        run.outcome = "rejected"
        run.artifacts["reject_reason"] = "Rejected by human editor at Gate 7."
    return run
