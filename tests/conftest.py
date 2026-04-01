"""Shared fixtures for ReapNES Studio test suite."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
#  Path fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the ReapNES-Studio repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def jsfx_dir(repo_root: Path) -> Path:
    return repo_root / "studio" / "jsfx"


@pytest.fixture
def rpp_dir(repo_root: Path) -> Path:
    return repo_root / "studio" / "reaper_projects"


@pytest.fixture
def midi_dir(repo_root: Path) -> Path:
    return repo_root / "studio" / "midi"


@pytest.fixture
def reaper_effects_dir() -> Path:
    """Path to REAPER Effects directory (via %APPDATA%).

    Returns the path even if it doesn't exist so tests can skip gracefully.
    """
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "REAPER" / "Effects"


@pytest.fixture
def reaper_reapnes_dir(reaper_effects_dir: Path) -> Path:
    """Path to the installed ReapNES Studio plugins."""
    return reaper_effects_dir / "ReapNES Studio"


# ---------------------------------------------------------------------------
#  MIDI generator fixture
# ---------------------------------------------------------------------------

def _write_midi_var_length(value: int) -> bytes:
    """Encode an integer as MIDI variable-length quantity."""
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.reverse()
    return bytes(result)


def _make_track_chunk(events: list[bytes]) -> bytes:
    """Build a MIDI track chunk from raw event bytes."""
    body = b"".join(events)
    # Append end-of-track meta event
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _note_on(delta: int, channel: int, note: int, velocity: int = 100) -> bytes:
    return _write_midi_var_length(delta) + bytes([0x90 | (channel & 0x0F), note & 0x7F, velocity & 0x7F])


def _note_off(delta: int, channel: int, note: int) -> bytes:
    return _write_midi_var_length(delta) + bytes([0x80 | (channel & 0x0F), note & 0x7F, 0])


def _set_tempo(delta: int, bpm: float) -> bytes:
    us = int(60_000_000 / bpm)
    return (_write_midi_var_length(delta)
            + b"\xff\x51\x03"
            + us.to_bytes(3, "big"))


@pytest.fixture
def make_test_midi(tmp_path: Path):
    """Factory fixture: creates a 4-channel MIDI file programmatically.

    Usage in tests:
        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=8)

    Returns the Path to the generated .mid file.
    """

    def _make(
        channels: list[int] | None = None,
        notes_per_channel: int = 8,
        ticks_per_beat: int = 480,
        bpm: float = 120.0,
        filename: str = "test.mid",
    ) -> Path:
        if channels is None:
            channels = [0, 1, 2, 9]

        # Header: format 1, N+1 tracks (tempo track + one per channel), ticks
        n_tracks = 1 + len(channels)
        header = b"MThd" + struct.pack(">IHhH", 6, 1, n_tracks, ticks_per_beat)

        # Tempo track
        tempo_events = [_set_tempo(0, bpm)]
        tracks = [_make_track_chunk(tempo_events)]

        # One track per channel with simple ascending notes
        for ch in channels:
            events: list[bytes] = []
            base_note = 36 if ch == 9 else (48 + ch * 12)  # drums at low range, melodic spread out
            for i in range(notes_per_channel):
                note = base_note + (i % 12)
                events.append(_note_on(0 if i == 0 else ticks_per_beat, ch, note))
                events.append(_note_off(ticks_per_beat // 2, ch, note))
            tracks.append(_make_track_chunk(events))

        out = tmp_path / filename
        out.write_bytes(header + b"".join(tracks))
        return out

    return _make
