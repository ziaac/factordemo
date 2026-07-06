"""Core dataclasses for the FACTOR demo.

These mirror the production entities described in the whitepaper
(`sources`, `source_chunks`, `topics`, `pipeline_runs`, `run_events`,
`article_translations`, `article_citations`) but are trimmed to what the
Streamlit demo needs. Everything lives in memory / JSON — no database.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Knowledge layer
# --------------------------------------------------------------------------- #
@dataclass
class Chunk:
    """A verified source chunk (mirror of `source_chunks` + `sources`)."""

    id: str
    workspace_id: str
    content: str
    title: str
    authors: list[str]
    year: int
    doi: str
    source_type: str        # rct | systematic_review | guideline | textbook | docs | news
    credibility: int         # 1-5, guideline/SR = 5
    topic_tags: list[str] = field(default_factory=list)

    @property
    def citation_short(self) -> str:
        first = self.authors[0] if self.authors else "Anon"
        etal = " et al." if len(self.authors) > 1 else ""
        return f"{first}{etal} ({self.year})"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        return cls(**d)


# --------------------------------------------------------------------------- #
# Topics & workspaces
# --------------------------------------------------------------------------- #
@dataclass
class Topic:
    id: str
    workspace_id: str
    title_id: str
    title_en: str
    category: str            # scientific | public_info | tips | tutorial
    genre: str               # article | tutorial | review | opinion
    priority: int
    related_chunk_count: int
    status: str = "active"
    scenario: str = "happy"  # happy | revision | weak_corpus

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Topic":
        return cls(**d)


@dataclass
class Workspace:
    id: str
    name: str
    domain: str
    languages: list[str]
    credibility_policy: str
    description: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Workspace":
        return cls(**d)


# --------------------------------------------------------------------------- #
# Pipeline artifacts
# --------------------------------------------------------------------------- #
@dataclass
class Claim:
    """A single sourced claim inside a draft."""

    id: str
    text: str
    chunk_id: str
    verdict: str = "pending"   # supported | partial | unsupported | contradicted | pending
    note: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Claim":
        return cls(**d)


@dataclass
class RunEvent:
    """Audit trail entry (mirror of `run_events`)."""

    step: str
    status: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    note: str = ""


@dataclass
class Run:
    """A single pipeline run (mirror of `pipeline_runs`)."""

    topic_id: str
    workspace_id: str
    genre: str
    state: str = "QUEUED"
    revision_count: int = 0
    outcome: str = "in_progress"   # in_progress | published | needs_attention | rejected
    events: list[RunEvent] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        return round(sum(e.cost_usd for e in self.events), 4)

    @property
    def total_tokens(self) -> int:
        return sum(e.input_tokens + e.output_tokens for e in self.events)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
