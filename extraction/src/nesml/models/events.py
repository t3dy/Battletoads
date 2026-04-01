"""Symbolic event types for NES music representation.

These events live in the symbolic layer between raw APU writes and
exported MIDI. They represent musical meaning, not hardware state.

Every event carries confidence and provenance indicating how it was derived.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nesml.models.core import Confidence


@dataclass
class NoteEvent:
    """A pitched note event on a channel.

    period: raw APU timer period (always present if derived from trace)
    pitch: symbolic pitch string e.g. 'C4' (only after reconstruction)
    midi_note: MIDI note number (only after pitch mapping)
    """
    frame: int
    duration_frames: int | None = None
    period: int | None = None
    pitch: str | None = None
    midi_note: int | None = None
    volume: int | None = None
    duty: int | None = None
    instrument_ref: str | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "note",
            "frame": self.frame,
            "confidence": self.confidence.to_dict(),
        }
        for attr in ("duration_frames", "period", "pitch", "midi_note",
                      "volume", "duty", "instrument_ref"):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val
        if self.raw_data:
            d["raw_data"] = self.raw_data
        return d


@dataclass
class RestEvent:
    """Silence on a channel for a measured duration."""
    frame: int
    duration_frames: int | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "rest",
            "frame": self.frame,
            "confidence": self.confidence.to_dict(),
        }
        if self.duration_frames is not None:
            d["duration_frames"] = self.duration_frames
        return d


@dataclass
class LoopPoint:
    """A loop marker in the sequence — either from static bytecode or runtime detection."""
    frame: int
    target_frame: int | None = None
    target_pattern: str | None = None
    loop_count: int | None = None   # None = infinite
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "loop_point",
            "frame": self.frame,
            "confidence": self.confidence.to_dict(),
        }
        if self.target_frame is not None:
            d["target_frame"] = self.target_frame
        if self.target_pattern is not None:
            d["target_pattern"] = self.target_pattern
        if self.loop_count is not None:
            d["loop_count"] = self.loop_count
        return d


@dataclass
class JumpCall:
    """A jump, call, or return in driver bytecode.

    Represents control flow in the static command stream — subroutine calls,
    pattern jumps, conditional branches. These are critical for understanding
    song structure and must not be flattened prematurely.
    """
    class Kind(Enum):
        JUMP = "jump"
        CALL = "call"
        RETURN = "return"
        CONDITIONAL = "conditional"
        UNKNOWN = "unknown"

    frame: int | None = None
    kind: Kind = Kind.UNKNOWN
    source_offset: int | None = None    # byte offset in ROM/data
    target_offset: int | None = None    # byte offset of target
    target_pattern: str | None = None
    condition: str | None = None        # description of branch condition
    confidence: Confidence = field(default_factory=Confidence.provisional)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "jump_call",
            "kind": self.kind.value,
            "confidence": self.confidence.to_dict(),
        }
        for attr in ("frame", "source_offset", "target_offset",
                      "target_pattern", "condition"):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val
        if self.raw_data:
            d["raw_data"] = self.raw_data
        return d


@dataclass
class DPCMTriggerEvent:
    """A DPCM sample trigger on the delta channel."""
    frame: int
    sample_address: int | None = None   # DPCM sample start address
    sample_length: int | None = None    # DPCM sample length
    sample_rate: int | None = None      # DPCM rate index (0-15)
    loop: bool | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "dpcm_trigger",
            "frame": self.frame,
            "confidence": self.confidence.to_dict(),
        }
        for attr in ("sample_address", "sample_length", "sample_rate", "loop"):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val
        if self.raw_data:
            d["raw_data"] = self.raw_data
        return d


@dataclass
class ExpansionAudioEvent:
    """An event on expansion audio hardware (VRC6, VRC7, MMC5, Sunsoft 5B, Namco 163).

    These exist outside the standard 5-channel APU and require mapper-specific handling.
    """
    frame: int
    expansion_type: str     # "vrc6", "vrc7", "mmc5", "sunsoft_5b", "namco_163"
    channel: str            # expansion-specific channel name
    register: str | None = None
    value: int | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "expansion_audio",
            "frame": self.frame,
            "expansion_type": self.expansion_type,
            "channel": self.channel,
            "confidence": self.confidence.to_dict(),
        }
        if self.register is not None:
            d["register"] = self.register
        if self.value is not None:
            d["value"] = self.value
        if self.raw_data:
            d["raw_data"] = self.raw_data
        return d


@dataclass
class UnknownCommand:
    """An opcode or data byte the parser could not interpret.

    Must be preserved with full context so humans or later parser versions
    can resolve it.
    """
    frame: int | None = None
    offset: int | None = None       # byte offset in ROM/data
    opcode: int | None = None       # the unrecognized byte
    surrounding_bytes: bytes = b""  # context bytes around the unknown
    hypothesis: str = ""            # best guess at meaning
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "unknown_command",
            "confidence": self.confidence.to_dict(),
        }
        if self.frame is not None:
            d["frame"] = self.frame
        if self.offset is not None:
            d["offset"] = self.offset
        if self.opcode is not None:
            d["opcode"] = self.opcode
        if self.surrounding_bytes:
            d["surrounding_bytes"] = self.surrounding_bytes.hex()
        if self.hypothesis:
            d["hypothesis"] = self.hypothesis
        return d
