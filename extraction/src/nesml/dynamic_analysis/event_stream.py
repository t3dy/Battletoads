"""First-pass event stream generation from frame-normalized APU data.

Converts frame-by-frame register writes into a sequence of musical events
per channel. This is a coarse first pass — it detects state changes in
APU registers and emits events for them. Higher-level reconstruction
(note boundaries, tempo, macro identification) happens in later phases.

All events are tagged with source="trace" and confidence reflecting
how directly they map from register data.
"""

from __future__ import annotations

from nesml.static_analysis.apu import (
    decode_pulse_reg0,
    decode_pulse_period,
    decode_noise_reg2,
    parse_addr,
    CHANNEL_NAMES,
)
from nesml.dynamic_analysis.frame_normalize import extract_channel_writes


class EventStreamError(Exception):
    """Raised when event generation encounters invalid data."""


def generate_event_stream(frames: list[dict]) -> dict[str, list[dict]]:
    """Generate a first-pass event stream for all channels.

    Args:
        frames: Frame-normalized data (from frame_normalize.normalize_by_frame).

    Returns:
        Dict mapping channel name to list of event dicts, sorted by frame.
    """
    result = {}
    for channel in CHANNEL_NAMES:
        writes = extract_channel_writes(frames, channel)
        if not writes:
            result[channel] = []
            continue

        if channel in ("pulse1", "pulse2"):
            result[channel] = _pulse_events(writes, channel)
        elif channel == "triangle":
            result[channel] = _triangle_events(writes)
        elif channel == "noise":
            result[channel] = _noise_events(writes)
        elif channel == "dpcm":
            result[channel] = _dpcm_events(writes)

    return result


def _pulse_events(writes: list[dict], channel: str) -> list[dict]:
    """Generate events from pulse channel register writes.

    Tracks duty, volume, and period changes. Each state change emits an event.
    """
    events = []
    prev_duty = None
    prev_volume = None
    prev_period = None
    prev_constant_vol = None

    # Group writes by frame
    frame_groups = _group_by_frame(writes)

    for frame_num, frame_writes in frame_groups:
        reg_values: dict[int, int] = {}
        for w in frame_writes:
            addr = parse_addr(w["address"])
            reg_values[addr - _base_addr(channel)] = w["value"]

        # Decode register 0 if written
        if 0 in reg_values:
            decoded = decode_pulse_reg0(reg_values[0])
            if decoded["duty"] != prev_duty:
                events.append(_make_event(
                    frame_num, "duty_change",
                    duty=decoded["duty"],
                    confidence=1.0,
                ))
                prev_duty = decoded["duty"]

            vol = decoded["volume_envelope"]
            const = decoded["constant_volume"]
            if vol != prev_volume or const != prev_constant_vol:
                events.append(_make_event(
                    frame_num, "volume_change",
                    volume=vol if const else None,
                    confidence=1.0 if const else 0.7,
                    raw_data={"constant_volume": const, "envelope_period": vol},
                ))
                prev_volume = vol
                prev_constant_vol = const

        # Decode period if register 2 or 3 written
        if 2 in reg_values or 3 in reg_values:
            # Need both regs; use previous value if only one is written
            lo = reg_values.get(2)
            hi = reg_values.get(3)
            if lo is not None and hi is not None:
                period = decode_pulse_period(lo, hi)
                if period != prev_period:
                    events.append(_make_event(
                        frame_num, "period_change",
                        period=period,
                        confidence=1.0,
                    ))
                    prev_period = period
            elif hi is not None:
                # High byte write with length counter load often means note-on
                events.append(_make_event(
                    frame_num, "period_change",
                    period=None,
                    confidence=0.6,
                    raw_data={"reg3_only": hi},
                ))

    return events


def _triangle_events(writes: list[dict]) -> list[dict]:
    """Generate events from triangle channel register writes.

    Triangle has no volume or duty — only period and linear counter.
    """
    events = []
    prev_period = None

    frame_groups = _group_by_frame(writes)
    for frame_num, frame_writes in frame_groups:
        reg_values: dict[int, int] = {}
        for w in frame_writes:
            addr = parse_addr(w["address"])
            reg_values[addr - 0x4008] = w["value"]

        if 2 in reg_values or 3 in reg_values:
            lo = reg_values.get(2)
            hi = reg_values.get(3)
            if lo is not None and hi is not None:
                period = ((hi & 0x07) << 8) | lo
                if period != prev_period:
                    events.append(_make_event(
                        frame_num, "period_change",
                        period=period,
                        confidence=1.0,
                    ))
                    prev_period = period

    return events


def _noise_events(writes: list[dict]) -> list[dict]:
    """Generate events from noise channel register writes."""
    events = []
    prev_mode = None
    prev_period_idx = None
    prev_volume = None

    frame_groups = _group_by_frame(writes)
    for frame_num, frame_writes in frame_groups:
        reg_values: dict[int, int] = {}
        for w in frame_writes:
            addr = parse_addr(w["address"])
            reg_values[addr - 0x400C] = w["value"]

        if 0 in reg_values:
            decoded = decode_pulse_reg0(reg_values[0])  # same bit layout
            vol = decoded["volume_envelope"]
            const = decoded["constant_volume"]
            if vol != prev_volume:
                events.append(_make_event(
                    frame_num, "volume_change",
                    volume=vol if const else None,
                    confidence=1.0 if const else 0.7,
                ))
                prev_volume = vol

        if 2 in reg_values:
            decoded = decode_noise_reg2(reg_values[2])
            if decoded["mode"] != prev_mode:
                events.append(_make_event(
                    frame_num, "noise_mode_change",
                    confidence=1.0,
                    raw_data={"mode": decoded["mode"]},
                ))
                prev_mode = decoded["mode"]
            if decoded["period_index"] != prev_period_idx:
                events.append(_make_event(
                    frame_num, "period_change",
                    period=decoded["period_index"],
                    confidence=1.0,
                ))
                prev_period_idx = decoded["period_index"]

    return events


def _dpcm_events(writes: list[dict]) -> list[dict]:
    """Generate events from DPCM channel register writes."""
    events = []

    frame_groups = _group_by_frame(writes)
    for frame_num, frame_writes in frame_groups:
        reg_values: dict[int, int] = {}
        for w in frame_writes:
            addr = parse_addr(w["address"])
            reg_values[addr - 0x4010] = w["value"]

        # Any write to DPCM registers suggests a sample trigger
        if reg_values:
            events.append(_make_event(
                frame_num, "dpcm_trigger",
                confidence=0.8,
                raw_data={
                    f"reg{k}": v for k, v in reg_values.items()
                },
            ))

    return events


def _make_event(
    frame: int,
    event_type: str,
    *,
    pitch: str | None = None,
    period: int | None = None,
    volume: int | None = None,
    duty: int | None = None,
    duration_frames: int | None = None,
    macro_id: str | None = None,
    confidence: float = 0.5,
    raw_data: dict | None = None,
) -> dict:
    """Construct a normalized event dict."""
    event = {
        "frame": frame,
        "type": event_type,
        "confidence": confidence,
        "source": "trace",
    }
    if pitch is not None:
        event["pitch"] = pitch
    if period is not None:
        event["period"] = period
    if volume is not None:
        event["volume"] = volume
    if duty is not None:
        event["duty"] = duty
    if duration_frames is not None:
        event["duration_frames"] = {
            "value": duration_frames,
            "confidence": confidence,
            "source": "trace",
        }
    if macro_id is not None:
        event["macro_id"] = macro_id
    if raw_data is not None:
        event["raw_data"] = raw_data
    return event


def _group_by_frame(writes: list[dict]) -> list[tuple[int, list[dict]]]:
    """Group a flat list of writes into (frame_num, writes_list) pairs."""
    if not writes:
        return []

    groups: dict[int, list[dict]] = {}
    for w in writes:
        frame = w["frame"]
        if frame not in groups:
            groups[frame] = []
        groups[frame].append(w)

    return sorted(groups.items())


def _base_addr(channel: str) -> int:
    """Return the base register address for a channel."""
    return {
        "pulse1": 0x4000,
        "pulse2": 0x4004,
        "triangle": 0x4008,
        "noise": 0x400C,
        "dpcm": 0x4010,
    }[channel]
