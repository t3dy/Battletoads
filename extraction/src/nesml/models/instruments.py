"""Instrument behavior models.

On NES, "instruments" are not fixed presets. They are temporal behaviors —
sequences of volume, duty, pitch, and arpeggio changes applied over time.
A single "instrument" may be nothing more than a volume envelope pattern
reused across notes.

This module models these behaviors explicitly, without assuming a tracker-style
instrument definition exists in the source data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nesml.models.core import Confidence


@dataclass
class VolumeEnvelope:
    """A sequence of volume values applied per-frame (or per-tick) after note-on.

    On NES, volume is 0–15 for pulse/noise channels. Triangle has no
    volume control (only on/off via linear counter).
    """
    values: list[int]                   # volume values per tick
    loop_index: int | None = None       # index where envelope loops (None = no loop)
    release_index: int | None = None    # index for release phase (None = none)
    confidence: Confidence = field(default_factory=Confidence.provisional)

    @property
    def length(self) -> int:
        return len(self.values)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "volume_envelope",
            "values": self.values,
            "length": self.length,
            "confidence": self.confidence.to_dict(),
        }
        if self.loop_index is not None:
            d["loop_index"] = self.loop_index
        if self.release_index is not None:
            d["release_index"] = self.release_index
        return d


@dataclass
class PitchEnvelope:
    """A sequence of pitch offsets (in raw period units or semitone deltas)
    applied per-tick after note-on. Used for vibrato, slides, and portamento."""
    values: list[int]                   # pitch delta per tick
    unit: str = "period_delta"          # "period_delta" or "semitone_delta"
    loop_index: int | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "pitch_envelope",
            "values": self.values,
            "unit": self.unit,
            "length": len(self.values),
            "confidence": self.confidence.to_dict(),
        }
        if self.loop_index is not None:
            d["loop_index"] = self.loop_index
        return d


@dataclass
class DutySequence:
    """A sequence of duty cycle values (0–3) applied per-tick.
    Common in NES music for timbral richness."""
    values: list[int]                   # duty values (0–3) per tick
    loop_index: int | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "duty_sequence",
            "values": self.values,
            "length": len(self.values),
            "confidence": self.confidence.to_dict(),
        }
        if self.loop_index is not None:
            d["loop_index"] = self.loop_index
        return d


@dataclass
class ArpeggioMacro:
    """A rapid pitch-cycling pattern applied per-tick.

    Values are semitone offsets from the base note. Common NES technique
    to simulate chords on a single channel.
    """
    values: list[int]                   # semitone offsets per tick
    loop_index: int | None = None
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": "arpeggio_macro",
            "values": self.values,
            "length": len(self.values),
            "confidence": self.confidence.to_dict(),
        }
        if self.loop_index is not None:
            d["loop_index"] = self.loop_index
        return d


@dataclass
class InstrumentBehavior:
    """A composite description of temporal behavior applied to notes.

    This is NOT a "preset" — it is a reconstruction of observed or parsed
    per-frame behavior. Only label this as an "instrument" if the source
    driver format explicitly defines numbered instrument slots.

    Fields:
        id: unique identifier within this analysis
        label: human-readable name (e.g., "inst_0x03" or "duty_pulse_fast_decay")
        is_driver_defined: True only if the source format has explicit instrument definitions
        volume_envelope: volume behavior over time
        pitch_envelope: pitch modulation over time
        duty_sequence: duty cycle changes over time
        arpeggio: rapid pitch cycling
        dpcm_sample_id: associated DPCM sample (if applicable)
        retrigger_behavior: description of how notes retrigger this behavior
        usage_count: how many notes reference this behavior across the analysis
        channel_affinity: which channels this behavior has been observed on
    """
    id: str
    label: str = ""
    is_driver_defined: bool = False
    volume_envelope: VolumeEnvelope | None = None
    pitch_envelope: PitchEnvelope | None = None
    duty_sequence: DutySequence | None = None
    arpeggio: ArpeggioMacro | None = None
    dpcm_sample_id: int | None = None
    retrigger_behavior: str | None = None
    usage_count: int = 0
    channel_affinity: list[str] = field(default_factory=list)
    confidence: Confidence = field(default_factory=Confidence.provisional)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "is_driver_defined": self.is_driver_defined,
            "confidence": self.confidence.to_dict(),
        }
        if self.label:
            d["label"] = self.label
        if self.volume_envelope:
            d["volume_envelope"] = self.volume_envelope.to_dict()
        if self.pitch_envelope:
            d["pitch_envelope"] = self.pitch_envelope.to_dict()
        if self.duty_sequence:
            d["duty_sequence"] = self.duty_sequence.to_dict()
        if self.arpeggio:
            d["arpeggio"] = self.arpeggio.to_dict()
        if self.dpcm_sample_id is not None:
            d["dpcm_sample_id"] = self.dpcm_sample_id
        if self.retrigger_behavior:
            d["retrigger_behavior"] = self.retrigger_behavior
        if self.usage_count:
            d["usage_count"] = self.usage_count
        if self.channel_affinity:
            d["channel_affinity"] = self.channel_affinity
        if self.raw_data:
            d["raw_data"] = self.raw_data
        return d
