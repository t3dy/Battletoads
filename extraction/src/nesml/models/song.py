"""Song-level symbolic models.

A Song is the top-level container. It holds ChannelStreams (one per NES channel),
which in turn hold Patterns (reusable sequence fragments) and events.

Critical: Pattern/subroutine structure from static analysis must NOT be
flattened into linear playback order. The export layer decides how to flatten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from nesml.models.core import Confidence, Provenance
from nesml.models.events import (
    NoteEvent, RestEvent, LoopPoint, JumpCall,
    DPCMTriggerEvent, ExpansionAudioEvent, UnknownCommand,
)
from nesml.models.timing import TempoModel, MeterHypothesis
from nesml.models.instruments import InstrumentBehavior


# Type alias for any event in a channel stream
Event = Union[
    NoteEvent, RestEvent, LoopPoint, JumpCall,
    DPCMTriggerEvent, ExpansionAudioEvent, UnknownCommand,
]


@dataclass
class Pattern:
    """A reusable sequence fragment.

    Drivers often organize music into patterns (or "phrases") that are
    referenced by index from an order list. Preserving this structure
    is essential — it reveals compositional intent and enables
    pattern-aware MIDI export.

    If the driver uses subroutine calls, the called data becomes a Pattern.
    """
    id: str
    label: str = ""
    events: list[Event] = field(default_factory=list)
    length_ticks: int | None = None     # total duration in engine ticks
    length_frames: int | None = None    # total duration in APU frames
    rom_offset: int | None = None       # byte offset in ROM where this pattern starts
    rom_length: int | None = None       # byte length of this pattern's data
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "events": [e.to_dict() for e in self.events],
            "confidence": self.confidence.to_dict(),
        }
        for attr in ("label", "length_ticks", "length_frames",
                      "rom_offset", "rom_length"):
            val = getattr(self, attr)
            if val is not None and val != "":
                d[attr] = val
        return d


@dataclass
class PatternRef:
    """A reference to a pattern in the order list.

    This is how songs reference patterns — by ID, with optional
    transposition or repeat count.
    """
    pattern_id: str
    transpose_semitones: int = 0
    repeat_count: int = 1
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "pattern_id": self.pattern_id,
            "confidence": self.confidence.to_dict(),
        }
        if self.transpose_semitones != 0:
            d["transpose_semitones"] = self.transpose_semitones
        if self.repeat_count != 1:
            d["repeat_count"] = self.repeat_count
        return d


@dataclass
class ChannelStream:
    """A single channel's musical content within a song.

    Supports two representations:
    1. Pattern-based: order_list references Patterns defined in the Song.
    2. Flat: events contains a linear sequence of events.

    Static analysis should produce pattern-based output.
    Dynamic analysis may produce flat output.
    Reconciliation aligns both.
    """
    channel: str    # "pulse1", "pulse2", "triangle", "noise", "dpcm", or expansion
    active: bool = True

    # Pattern-based representation (preferred for static analysis)
    order_list: list[PatternRef] = field(default_factory=list)

    # Flat representation (for dynamic analysis or after flattening)
    events: list[Event] = field(default_factory=list)

    # Loop structure
    loop_point: LoopPoint | None = None

    # Metadata
    rom_offset: int | None = None   # start of this channel's data in ROM
    confidence: Confidence = field(default_factory=Confidence.provisional)

    @property
    def is_pattern_based(self) -> bool:
        return len(self.order_list) > 0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "channel": self.channel,
            "active": self.active,
            "confidence": self.confidence.to_dict(),
        }
        if self.order_list:
            d["order_list"] = [p.to_dict() for p in self.order_list]
        if self.events:
            d["events"] = [e.to_dict() for e in self.events]
        if self.loop_point:
            d["loop_point"] = self.loop_point.to_dict()
        if self.rom_offset is not None:
            d["rom_offset"] = self.rom_offset
        return d


@dataclass
class Song:
    """Top-level symbolic representation of a single NES song.

    Contains per-channel streams, shared patterns, instrument behaviors,
    timing models, and full provenance.
    """
    # Identity
    song_id: str | int
    title: str = ""
    rom_name: str = ""
    rom_sha256: str = ""
    driver_family: str = ""
    driver_version: str = ""
    region: str = "ntsc"

    # Musical content
    channels: dict[str, ChannelStream] = field(default_factory=dict)
    patterns: dict[str, Pattern] = field(default_factory=dict)
    instruments: dict[str, InstrumentBehavior] = field(default_factory=dict)

    # Timing
    tempo_models: list[TempoModel] = field(default_factory=list)
    meter: MeterHypothesis | None = None

    # Structure
    total_frames: int | None = None
    loop_start_frame: int | None = None

    # Unknowns
    unknowns: list[UnknownCommand] = field(default_factory=list)

    # Provenance
    provenance: Provenance | None = None

    # Reconciliation status
    reconciliation_status: str = "none"  # "none", "partial", "full"
    discrepancies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "schema_version": "0.2.0",
            "song_id": self.song_id,
            "rom_name": self.rom_name,
            "driver_family": self.driver_family,
            "region": self.region,
            "reconciliation_status": self.reconciliation_status,
        }
        if self.title:
            d["title"] = self.title
        if self.rom_sha256:
            d["rom_sha256"] = self.rom_sha256
        if self.driver_version:
            d["driver_version"] = self.driver_version

        d["channels"] = {k: v.to_dict() for k, v in self.channels.items()}
        if self.patterns:
            d["patterns"] = {k: v.to_dict() for k, v in self.patterns.items()}
        if self.instruments:
            d["instruments"] = {k: v.to_dict() for k, v in self.instruments.items()}
        if self.tempo_models:
            d["tempo"] = [t.to_dict() for t in self.tempo_models]
        if self.meter:
            d["meter"] = self.meter.to_dict()
        if self.total_frames is not None:
            d["total_frames"] = self.total_frames
        if self.loop_start_frame is not None:
            d["loop_start_frame"] = self.loop_start_frame
        if self.unknowns:
            d["unknowns"] = [u.to_dict() for u in self.unknowns]
        if self.discrepancies:
            d["discrepancies"] = self.discrepancies
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()

        return d
