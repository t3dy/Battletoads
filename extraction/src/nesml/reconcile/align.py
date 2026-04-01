"""Alignment between static parser output and dynamic trace output.

The reconciliation process:
1. Take a Song from static analysis (pattern-based, symbolic)
2. Take a ChannelStream from dynamic analysis (flat, frame-timed)
3. Align events by matching timing, pitch, and duration
4. Produce a discrepancy report
5. Adjust confidence scores based on agreement/disagreement

Key rules:
- Static structure (patterns, loops, calls) is preserved even when
  runtime flattens it. Runtime VALIDATES static findings, it does
  not replace them.
- Discrepancies are reported, not silently resolved.
- Manual annotations always take precedence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nesml.models.core import Confidence, SourceType


class DiscrepancyType(Enum):
    """Types of discrepancies between static and dynamic analysis."""
    TIMING_MISMATCH = "timing_mismatch"         # frame timing differs
    PITCH_MISMATCH = "pitch_mismatch"           # period/pitch differs
    DURATION_MISMATCH = "duration_mismatch"     # note length differs
    MISSING_IN_STATIC = "missing_in_static"     # runtime event not in static output
    MISSING_IN_DYNAMIC = "missing_in_dynamic"   # static event not in runtime trace
    VOLUME_MISMATCH = "volume_mismatch"         # volume behavior differs
    LOOP_MISMATCH = "loop_mismatch"             # loop structure differs
    TEMPO_MISMATCH = "tempo_mismatch"           # tempo hypothesis doesn't match runtime
    EXTRA_EVENT = "extra_event"                 # unexpected event in one source


class Severity(Enum):
    """How serious a discrepancy is for musical correctness."""
    INFO = "info"           # minor difference, likely acceptable
    WARNING = "warning"     # may indicate a parser issue
    ERROR = "error"         # definite conflict that needs resolution


@dataclass
class Discrepancy:
    """A single discrepancy between static and dynamic findings."""
    type: DiscrepancyType
    severity: Severity
    channel: str
    frame: int | None = None
    static_value: Any = None
    dynamic_value: Any = None
    description: str = ""
    resolution: str | None = None   # how it was resolved (if at all)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": self.type.value,
            "severity": self.severity.value,
            "channel": self.channel,
            "description": self.description,
        }
        if self.frame is not None:
            d["frame"] = self.frame
        if self.static_value is not None:
            d["static_value"] = self.static_value
        if self.dynamic_value is not None:
            d["dynamic_value"] = self.dynamic_value
        if self.resolution:
            d["resolution"] = self.resolution
        return d


@dataclass
class ReconciliationReport:
    """Full reconciliation report for a song."""
    song_id: str | int
    rom_name: str
    channel_reports: dict[str, ChannelReconciliation] = field(default_factory=dict)
    overall_confidence: float = 0.0
    discrepancy_count: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "song_id": self.song_id,
            "rom_name": self.rom_name,
            "channel_reports": {
                k: v.to_dict() for k, v in self.channel_reports.items()
            },
            "overall_confidence": self.overall_confidence,
            "discrepancy_count": self.discrepancy_count,
            "notes": self.notes,
        }


@dataclass
class ChannelReconciliation:
    """Reconciliation result for a single channel."""
    channel: str
    static_event_count: int = 0
    dynamic_event_count: int = 0
    matched_events: int = 0
    discrepancies: list[Discrepancy] = field(default_factory=list)
    confidence_adjustment: float = 0.0

    @property
    def match_ratio(self) -> float:
        total = max(self.static_event_count, self.dynamic_event_count)
        if total == 0:
            return 0.0
        return self.matched_events / total

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "static_event_count": self.static_event_count,
            "dynamic_event_count": self.dynamic_event_count,
            "matched_events": self.matched_events,
            "match_ratio": round(self.match_ratio, 3),
            "discrepancy_count": len(self.discrepancies),
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "confidence_adjustment": self.confidence_adjustment,
        }


def reconcile_channel(
    static_events: list[dict],
    dynamic_events: list[dict],
    channel: str,
    *,
    timing_tolerance_frames: int = 2,
    period_tolerance: int = 1,
) -> ChannelReconciliation:
    """Align static and dynamic event lists for a single channel.

    Uses frame-based alignment with configurable tolerance.
    This is a first-pass implementation — more sophisticated alignment
    (e.g., dynamic programming / edit distance) can be added later.

    Args:
        static_events: Events from static parser (with 'frame' and optionally 'period').
        dynamic_events: Events from runtime trace (with 'frame' and 'period').
        channel: Channel name.
        timing_tolerance_frames: How many frames apart events can be and still match.
        period_tolerance: How much period values can differ and still match.
    """
    result = ChannelReconciliation(
        channel=channel,
        static_event_count=len(static_events),
        dynamic_event_count=len(dynamic_events),
    )

    # Index dynamic events by frame for O(1) lookup
    dyn_by_frame: dict[int, list[dict]] = {}
    for evt in dynamic_events:
        f = evt.get("frame", -1)
        if f not in dyn_by_frame:
            dyn_by_frame[f] = []
        dyn_by_frame[f].append(evt)

    matched_dynamic = set()

    for s_evt in static_events:
        s_frame = s_evt.get("frame")
        if s_frame is None:
            continue

        # Look for matching dynamic event within tolerance
        best_match = None
        best_delta = timing_tolerance_frames + 1

        for delta in range(timing_tolerance_frames + 1):
            for try_frame in (s_frame + delta, s_frame - delta):
                for d_evt in dyn_by_frame.get(try_frame, []):
                    d_id = id(d_evt)
                    if d_id in matched_dynamic:
                        continue

                    # Check type compatibility
                    s_type = s_evt.get("type", "")
                    d_type = d_evt.get("type", "")
                    if not _types_compatible(s_type, d_type):
                        continue

                    if abs(delta) < best_delta:
                        best_match = d_evt
                        best_delta = abs(delta)

        if best_match is not None:
            matched_dynamic.add(id(best_match))
            result.matched_events += 1

            # Check for value discrepancies
            if best_delta > 0:
                result.discrepancies.append(Discrepancy(
                    type=DiscrepancyType.TIMING_MISMATCH,
                    severity=Severity.WARNING if best_delta > 1 else Severity.INFO,
                    channel=channel,
                    frame=s_frame,
                    static_value=s_frame,
                    dynamic_value=best_match.get("frame"),
                    description=f"Timing offset of {best_delta} frames",
                ))

            s_period = s_evt.get("period")
            d_period = best_match.get("period")
            if s_period is not None and d_period is not None:
                if abs(s_period - d_period) > period_tolerance:
                    result.discrepancies.append(Discrepancy(
                        type=DiscrepancyType.PITCH_MISMATCH,
                        severity=Severity.ERROR,
                        channel=channel,
                        frame=s_frame,
                        static_value=s_period,
                        dynamic_value=d_period,
                        description=f"Period mismatch: static={s_period}, dynamic={d_period}",
                    ))
        else:
            result.discrepancies.append(Discrepancy(
                type=DiscrepancyType.MISSING_IN_DYNAMIC,
                severity=Severity.WARNING,
                channel=channel,
                frame=s_frame,
                static_value=s_evt.get("type"),
                description=f"Static event at frame {s_frame} not found in trace",
            ))

    # Check for unmatched dynamic events
    for d_evt in dynamic_events:
        if id(d_evt) not in matched_dynamic:
            result.discrepancies.append(Discrepancy(
                type=DiscrepancyType.MISSING_IN_STATIC,
                severity=Severity.INFO,
                channel=channel,
                frame=d_evt.get("frame"),
                dynamic_value=d_evt.get("type"),
                description=f"Runtime event at frame {d_evt.get('frame')} not in static output",
            ))

    # Calculate confidence adjustment
    if result.match_ratio > 0.8:
        result.confidence_adjustment = 0.2  # boost
    elif result.match_ratio > 0.5:
        result.confidence_adjustment = 0.0  # neutral
    else:
        result.confidence_adjustment = -0.2  # penalty

    return result


def _types_compatible(static_type: str, dynamic_type: str) -> bool:
    """Check if two event types are semantically compatible for matching."""
    if static_type == dynamic_type:
        return True
    compatible_pairs = {
        ("note", "period_change"),
        ("note", "note_on"),
        ("rest", "note_off"),
        ("rest", "volume_change"),
    }
    return (static_type, dynamic_type) in compatible_pairs or \
           (dynamic_type, static_type) in compatible_pairs
