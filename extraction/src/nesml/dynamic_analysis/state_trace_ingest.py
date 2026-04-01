"""State trace ingest — parse Mesen 2 APU state captures.

The v7 capture script polls decoded APU state each frame via emu.getState()
and logs parameter changes. This produces a CSV with columns:
  frame, parameter, value

Parameters use pseudo-register addresses like "$4002_period" that encode
both the APU register group and the decoded field name.

This module converts that format into per-channel event streams suitable
for note segmentation and musical analysis.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NTSC_CPU_CLOCK = 1789773

# Parameter to channel mapping
PARAM_CHANNEL = {
    "$4000_duty": "pulse1", "$4000_const": "pulse1", "$4000_vol": "pulse1",
    "$4002_period": "pulse1", "$4001_sweep": "pulse1",
    "$4004_duty": "pulse2", "$4004_const": "pulse2", "$4004_vol": "pulse2",
    "$4006_period": "pulse2", "$4005_sweep": "pulse2",
    "$400A_period": "triangle", "$4008_linear": "triangle",
    "$400B_length": "triangle",
    "$400C_vol": "noise", "$400C_const": "noise",
    "$400E_period": "noise", "$400E_mode": "noise",
    "$4011_dac": "dpcm", "$4012_addr": "dpcm",
    "$4013_len": "dpcm", "$4010_rate": "dpcm",
}

# Parameter field name (strip register prefix)
PARAM_FIELD = {
    "$4000_duty": "duty", "$4000_const": "constant_volume", "$4000_vol": "volume",
    "$4002_period": "period", "$4001_sweep": "sweep",
    "$4004_duty": "duty", "$4004_const": "constant_volume", "$4004_vol": "volume",
    "$4006_period": "period", "$4005_sweep": "sweep",
    "$400A_period": "period", "$4008_linear": "linear_counter",
    "$400B_length": "length_counter",
    "$400C_vol": "volume", "$400C_const": "constant_volume",
    "$400E_period": "period", "$400E_mode": "mode",
    "$4011_dac": "dac", "$4012_addr": "sample_addr",
    "$4013_len": "sample_len", "$4010_rate": "rate",
}


@dataclass
class ChannelFrame:
    """Snapshot of one channel's state at a given frame."""
    frame: int
    period: int | None = None
    volume: int | None = None
    duty: int | None = None
    constant_volume: bool = True
    sweep: int | None = None
    # noise-specific
    mode: int | None = None
    # triangle-specific
    linear_counter: int | None = None
    length_counter: int | None = None


@dataclass
class StateTrace:
    """Parsed state trace with per-channel frame data."""
    channel_states: dict[str, list[ChannelFrame]] = field(default_factory=dict)
    total_frames: int = 0
    raw_changes: list[dict] = field(default_factory=list)


def load_state_trace(path: str | Path) -> StateTrace:
    """Load a Mesen 2 state trace CSV.

    Returns a StateTrace with per-channel state snapshots at every
    frame where something changed.
    """
    path = Path(path)
    changes: list[dict] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            param = row["parameter"]
            val_str = row["value"]

            # Parse value — booleans only for known boolean fields
            is_bool_field = "const" in param or "sweep" in param or "mode" in param
            if is_bool_field and val_str in ("true", "True", "1"):
                value: Any = True
            elif is_bool_field and val_str in ("false", "False", "0"):
                value = False
            else:
                try:
                    value = int(float(val_str))
                except ValueError:
                    value = val_str

            changes.append({
                "frame": frame,
                "parameter": param,
                "value": value,
                "channel": PARAM_CHANNEL.get(param, "unknown"),
                "field": PARAM_FIELD.get(param, param),
            })

    # Build per-channel state timelines
    # Track current state per channel, emit a snapshot when anything changes
    current: dict[str, dict] = {
        ch: {"period": None, "volume": 0, "duty": 0, "constant_volume": True}
        for ch in ("pulse1", "pulse2", "triangle", "noise", "dpcm")
    }
    channel_frames: dict[str, list[ChannelFrame]] = {
        ch: [] for ch in ("pulse1", "pulse2", "triangle", "noise", "dpcm")
    }
    last_frame_per_channel: dict[str, int] = {}
    max_frame = 0

    for change in changes:
        ch = change["channel"]
        if ch == "unknown":
            continue
        fld = change["field"]
        frame = change["frame"]
        max_frame = max(max_frame, frame)

        current[ch][fld] = change["value"]

        # Emit a snapshot if this is a new frame for this channel
        if frame != last_frame_per_channel.get(ch):
            cf = ChannelFrame(frame=frame)
            for k, v in current[ch].items():
                if hasattr(cf, k):
                    setattr(cf, k, v)
            channel_frames[ch].append(cf)
            last_frame_per_channel[ch] = frame

    return StateTrace(
        channel_states=channel_frames,
        total_frames=max_frame,
        raw_changes=changes,
    )


def pulse_period_to_freq(period: int) -> float:
    """Convert pulse channel timer period to frequency (Hz)."""
    if period < 8:
        return 0.0
    return NTSC_CPU_CLOCK / (16 * (period + 1))


def triangle_period_to_freq(period: int) -> float:
    """Convert triangle channel timer period to frequency (Hz)."""
    if period < 2:
        return 0.0
    return NTSC_CPU_CLOCK / (32 * (period + 1))


def freq_to_midi(freq: float) -> tuple[int, float]:
    """Convert frequency to MIDI note number and cents offset."""
    if freq <= 0:
        return 0, 0.0
    midi = 69 + 12 * math.log2(freq / 440)
    midi_rounded = round(midi)
    cents = (midi - midi_rounded) * 100
    return midi_rounded, cents


def midi_to_name(midi_note: int) -> str:
    """Convert MIDI note number to name like 'C4'."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    note = names[midi_note % 12]
    return f"{note}{octave}"
