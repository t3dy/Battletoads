"""REAPER metadata export from symbolic Song model.

Generates structured JSON describing how to set up a REAPER project
from NES Music Lab analysis: track routing, automation lanes,
markers, regions, and plugin metadata suggestions.

This is a separate structured output — not hidden inside MIDI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nesml.models.song import Song
from nesml.models.core import Provenance, ProvenanceSource, SourceType


@dataclass
class ReaperExportConfig:
    """Configuration for REAPER metadata export."""
    include_volume_automation: bool = True
    include_duty_automation: bool = True
    include_pitch_automation: bool = True
    include_dpcm_markers: bool = True
    include_structure_markers: bool = True
    include_loop_regions: bool = True
    include_confidence_markers: bool = False  # mark low-confidence events


def generate_reaper_metadata(
    song: Song,
    midi_files: dict[str, str],
    config: ReaperExportConfig | None = None,
) -> dict:
    """Generate REAPER-oriented metadata from a Song and its MIDI exports.

    Args:
        song: Resolved Song object.
        midi_files: Dict mapping channel name to MIDI file path.
        config: Export configuration.

    Returns:
        Dict conforming to the REAPER export schema.
    """
    if config is None:
        config = ReaperExportConfig()

    tracks = []
    for ch_name, ch in song.channels.items():
        if not ch.active:
            continue

        midi_path = midi_files.get(ch_name)
        if not midi_path:
            continue

        track: dict[str, Any] = {
            "name": _track_name(ch_name, song),
            "nes_channel": ch_name,
            "midi_file": midi_path,
            "automation": [],
        }

        # Automation lanes would be populated from instrument behaviors
        # and channel state changes — stubbed for Phase 5
        tracks.append(track)

    markers = []
    regions = []

    # Structure markers from song sections
    if config.include_structure_markers and song.loop_start_frame is not None:
        markers.append({
            "time_seconds": _frame_to_seconds(song.loop_start_frame, song),
            "label": "Loop Start",
        })

    return {
        "schema_version": "0.1.0",
        "metadata": {
            "source_analysis": f"{song.rom_name}/{song.song_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tempo_bpm": _get_bpm(song),
        },
        "tracks": tracks,
        "markers": markers,
        "regions": regions,
    }


def _track_name(channel: str, song: Song) -> str:
    """Generate a descriptive track name."""
    prefix = song.rom_name.replace("_", " ").title() if song.rom_name else "NES"
    names = {
        "pulse1": "Pulse 1",
        "pulse2": "Pulse 2",
        "triangle": "Triangle",
        "noise": "Noise",
        "dpcm": "DPCM",
    }
    return f"{prefix} — {names.get(channel, channel)}"


def _frame_to_seconds(frame: int, song: Song) -> float:
    """Convert frame number to seconds."""
    rate = 60.0988  # NTSC default
    if song.tempo_models:
        rate = song.tempo_models[0].frame_rate_hz
    return frame / rate


def _get_bpm(song: Song) -> float | None:
    """Get BPM from song tempo model."""
    if not song.tempo_models:
        return None
    t = song.tempo_models[0]
    return t.bpm_estimate or t.derived_bpm
