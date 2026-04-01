"""Core types shared across all symbolic models.

Provenance and confidence are first-class concerns — every extracted
or inferred value must carry both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(Enum):
    """Origin of an extracted claim. Ordered by evidence strength (highest first)."""
    MANUAL = "manual"               # Human-verified reverse-engineering
    STATIC_PARSE = "static_parse"   # Deterministic parser from known format
    RUNTIME_TRACE = "runtime_trace" # Exact APU observation from emulator trace
    RECONCILED = "reconciled"       # Confirmed by both static and dynamic evidence
    HEURISTIC = "heuristic"         # Rule-based inference from one source
    PROVISIONAL = "provisional"     # Untested assumption or placeholder

    @property
    def rank(self) -> int:
        """Lower number = stronger evidence."""
        return {
            SourceType.MANUAL: 1,
            SourceType.STATIC_PARSE: 2,
            SourceType.RUNTIME_TRACE: 3,
            SourceType.RECONCILED: 4,
            SourceType.HEURISTIC: 5,
            SourceType.PROVISIONAL: 6,
        }[self]

    def __lt__(self, other: SourceType) -> bool:
        return self.rank < other.rank


@dataclass
class Confidence:
    """Confidence annotation for any extracted value.

    score: 0.0 (no confidence) to 1.0 (verified certain)
    source_type: where this evidence came from
    reason: human-readable explanation of why this confidence level
    evidence_refs: pointers to supporting evidence (file paths, frame ranges, etc.)
    verified: True if a human has confirmed this value
    overridden_by_manual: True if a manual annotation supersedes this
    """
    score: float
    source_type: SourceType
    reason: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    verified: bool = False
    overridden_by_manual: bool = False

    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Confidence score must be 0.0–1.0, got {self.score}")

    def to_dict(self) -> dict:
        d = {
            "score": self.score,
            "source_type": self.source_type.value,
        }
        if self.reason:
            d["reason"] = self.reason
        if self.evidence_refs:
            d["evidence_refs"] = self.evidence_refs
        if self.verified:
            d["verified"] = True
        if self.overridden_by_manual:
            d["overridden_by_manual"] = True
        return d

    @classmethod
    def manual(cls, reason: str = "human-verified") -> Confidence:
        return cls(1.0, SourceType.MANUAL, reason, verified=True)

    @classmethod
    def static_parse(cls, score: float, reason: str = "") -> Confidence:
        return cls(score, SourceType.STATIC_PARSE, reason)

    @classmethod
    def runtime(cls, score: float, reason: str = "") -> Confidence:
        return cls(score, SourceType.RUNTIME_TRACE, reason)

    @classmethod
    def reconciled(cls, score: float, reason: str = "") -> Confidence:
        return cls(score, SourceType.RECONCILED, reason)

    @classmethod
    def heuristic(cls, score: float, reason: str = "") -> Confidence:
        return cls(score, SourceType.HEURISTIC, reason)

    @classmethod
    def provisional(cls, reason: str = "untested assumption") -> Confidence:
        return cls(0.0, SourceType.PROVISIONAL, reason)


@dataclass
class Provenance:
    """Full provenance record for a compound object (Song, ChannelStream, etc.).

    Tracks which pipeline produced this object and what sources informed it.
    """
    generated_by: str                       # Pipeline/tool identifier
    generated_at: str                       # ISO 8601 datetime
    sources: list[ProvenanceSource] = field(default_factory=list)
    pipeline_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "generated_by": self.generated_by,
            "generated_at": self.generated_at,
            "sources": [s.to_dict() for s in self.sources],
            "pipeline_config": self.pipeline_config,
        }


@dataclass
class ProvenanceSource:
    """A single source contributing to a provenance record."""
    source_type: SourceType
    reference: str      # File path, URL, or description
    notes: str = ""

    def to_dict(self) -> dict:
        d = {
            "source_type": self.source_type.value,
            "reference": self.reference,
        }
        if self.notes:
            d["notes"] = self.notes
        return d
