"""MIDI export from symbolic Song model.

Exports one MIDI track per NES channel from a resolved Song object.
Never operates directly on raw trace data — always downstream of
the symbolic model.

Requires the `mido` library (Phase 5 dependency).

Export choices:
- Note timing: uses resolved frame-based timing converted to MIDI ticks
- Loop handling: configurable (export one pass, or N repetitions)
- Confidence filtering: can skip events below a confidence threshold
- Ambiguity: low-confidence events are exported with annotations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nesml.models.song import Song, ChannelStream
from nesml.models.events import NoteEvent, RestEvent, DPCMTriggerEvent
from nesml.models.timing import TempoModel
from nesml.static_analysis.apu import NTSC_FRAME_RATE


class MIDIExportError(Exception):
    """Raised when MIDI export fails."""


@dataclass
class MIDIExportConfig:
    """Configuration for MIDI export."""
    loop_count: int = 1             # how many times to unroll loops (0 = no loop)
    min_confidence: float = 0.0     # skip events below this confidence
    include_markers: bool = True    # include text markers for structure
    ppqn: int = 480                 # pulses per quarter note
    default_velocity: int = 100
    noise_channel_number: int = 9   # MIDI channel for noise (GM drums)
    dpcm_channel_number: int = 9    # MIDI channel for DPCM samples

    # Channel-to-MIDI-channel mapping
    channel_map: dict[str, int] = field(default_factory=lambda: {
        "pulse1": 0,
        "pulse2": 1,
        "triangle": 2,
        "noise": 9,
        "dpcm": 9,
    })


@dataclass
class MIDIExportResult:
    """Result of a MIDI export operation."""
    files: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence_summary: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "files": self.files,
            "warnings": self.warnings,
            "confidence_summary": self.confidence_summary,
        }


def validate_export_readiness(song: Song) -> list[str]:
    """Check if a Song is ready for MIDI export.

    Returns list of warnings/errors. Empty = ready.
    """
    issues = []

    if not song.channels:
        issues.append("ERROR: Song has no channels")
        return issues

    has_events = False
    for ch_name, ch in song.channels.items():
        if ch.events or ch.order_list:
            has_events = True

    if not has_events:
        issues.append("ERROR: No channels have events or patterns")

    if not song.tempo_models:
        issues.append("WARNING: No tempo model — timing will use raw frame counts")

    # Check confidence levels
    low_conf_count = 0
    total_events = 0
    for ch in song.channels.values():
        for evt in ch.events:
            total_events += 1
            if hasattr(evt, 'confidence') and evt.confidence.score < 0.3:
                low_conf_count += 1

    if total_events > 0 and low_conf_count / total_events > 0.5:
        issues.append(
            f"WARNING: {low_conf_count}/{total_events} events have confidence < 0.3"
        )

    return issues


def frames_to_midi_ticks(
    frames: int,
    tempo: TempoModel | None,
    ppqn: int = 480,
) -> int:
    """Convert APU frame count to MIDI ticks.

    Uses tempo model if available, otherwise assumes 120 BPM.
    """
    frame_rate = tempo.frame_rate_hz if tempo else NTSC_FRAME_RATE
    bpm = 120.0
    if tempo and tempo.bpm_estimate:
        bpm = tempo.bpm_estimate
    elif tempo and tempo.derived_bpm:
        bpm = tempo.derived_bpm

    seconds = frames / frame_rate
    beats = seconds * (bpm / 60.0)
    return int(beats * ppqn)


def note_event_to_midi_note(event: NoteEvent) -> int | None:
    """Convert a NoteEvent to MIDI note number.

    Uses midi_note if set, otherwise tries to derive from pitch string.
    Returns None if no mapping is possible.
    """
    if event.midi_note is not None:
        return event.midi_note
    if event.pitch is not None:
        return _pitch_string_to_midi(event.pitch)
    return None


def _pitch_string_to_midi(pitch: str) -> int | None:
    """Convert a pitch string like 'C4' to MIDI note number.

    Uses standard MIDI mapping: C4 = 60.
    """
    note_map = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11,
    }
    if len(pitch) < 2:
        return None

    note_char = pitch[0].upper()
    if note_char not in note_map:
        return None

    rest = pitch[1:]
    sharp = 0
    if rest.startswith('#'):
        sharp = 1
        rest = rest[1:]
    elif rest.startswith('b'):
        sharp = -1
        rest = rest[1:]

    try:
        octave = int(rest)
    except ValueError:
        return None

    return (octave + 1) * 12 + note_map[note_char] + sharp
