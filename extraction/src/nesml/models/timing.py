"""Timing and meter models.

NES music timing is frame-based: the APU updates at 60Hz (NTSC) or 50Hz (PAL).
Sound drivers typically subdivide this further with a "speed" or "tick divider"
that controls how fast the music engine steps through sequence data.

Tempo and meter are always hypotheses unless verified against driver bytecode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nesml.models.core import Confidence


@dataclass
class TempoModel:
    """Describes the timing structure of a song.

    Multiple tempo models may coexist if tempo changes occur mid-song.
    """
    frame_rate_hz: float = 60.0988      # NTSC default
    engine_speed: int | None = None     # driver-specific speed/divider value
    frames_per_tick: int | None = None  # how many APU frames per engine tick
    ticks_per_row: int | None = None    # how many engine ticks per "row" (if applicable)
    bpm_estimate: float | None = None   # derived BPM hypothesis
    start_frame: int = 0                # frame where this tempo begins
    end_frame: int | None = None        # frame where this tempo ends (None = end of song)
    confidence: Confidence = field(default_factory=Confidence.provisional)

    @property
    def seconds_per_tick(self) -> float | None:
        if self.frames_per_tick is None:
            return None
        return self.frames_per_tick / self.frame_rate_hz

    @property
    def derived_bpm(self) -> float | None:
        """Derive BPM from frames_per_tick, assuming 4 ticks per beat (common default)."""
        if self.frames_per_tick is None or self.frames_per_tick == 0:
            return None
        ticks_per_second = self.frame_rate_hz / self.frames_per_tick
        tpr = self.ticks_per_row or 1
        rows_per_second = ticks_per_second / tpr
        # Assume 4 rows per beat as default hypothesis
        return rows_per_second * 60.0 / 4.0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "frame_rate_hz": self.frame_rate_hz,
            "start_frame": self.start_frame,
            "confidence": self.confidence.to_dict(),
        }
        for attr in ("engine_speed", "frames_per_tick", "ticks_per_row",
                      "bpm_estimate", "end_frame"):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val
        if self.derived_bpm is not None and self.bpm_estimate is None:
            d["derived_bpm"] = round(self.derived_bpm, 2)
        return d


@dataclass
class MeterHypothesis:
    """A hypothesized time signature / metric structure.

    Always inferred — NES drivers do not encode meter explicitly.
    """
    numerator: int = 4
    denominator: int = 4
    beats_per_measure: int = 4
    ticks_per_beat: int | None = None
    start_frame: int = 0
    confidence: Confidence = field(
        default_factory=lambda: Confidence.heuristic(0.3, "meter always inferred")
    )

    def to_dict(self) -> dict:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "beats_per_measure": self.beats_per_measure,
            "ticks_per_beat": self.ticks_per_beat,
            "start_frame": self.start_frame,
            "confidence": self.confidence.to_dict(),
        }
