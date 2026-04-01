"""Note segmentation — extract discrete note events from channel state timelines.

A "note" on NES is not explicitly marked. We infer note boundaries from:
1. Period changes (new pitch = new note)
2. Volume drops to zero (note off)
3. Volume rises from zero (note on)
4. Length counter reloads (triangle channel note restarts)

Every inferred note carries confidence based on how clearly it was delineated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nesml.dynamic_analysis.state_trace_ingest import (
    StateTrace,
    ChannelFrame,
    pulse_period_to_freq,
    triangle_period_to_freq,
    freq_to_midi,
    midi_to_name,
)
from nesml.models.core import Confidence
from nesml.models.events import NoteEvent, RestEvent


@dataclass
class SegmentedChannel:
    """Result of note segmentation for one channel."""
    channel: str
    notes: list[NoteEvent] = field(default_factory=list)
    rests: list[RestEvent] = field(default_factory=list)
    all_events: list = field(default_factory=list)  # interleaved notes+rests


def segment_pulse_channel(
    frames: list[ChannelFrame],
    channel: str,
) -> SegmentedChannel:
    """Segment a pulse channel into discrete note and rest events.

    Uses period changes and volume-to-zero transitions as note boundaries.
    """
    result = SegmentedChannel(channel=channel)
    if not frames:
        return result

    current_period = None
    current_volume = 0
    note_start_frame = None
    note_start_period = None

    def emit_note(end_frame: int):
        nonlocal note_start_frame, note_start_period
        if note_start_frame is not None and note_start_period is not None:
            freq = pulse_period_to_freq(note_start_period)
            midi, cents = freq_to_midi(freq)
            duration = end_frame - note_start_frame

            # Higher confidence if note boundary is clear
            conf = 0.9 if abs(cents) < 20 else 0.7

            note = NoteEvent(
                frame=note_start_frame,
                duration_frames=duration,
                period=note_start_period,
                pitch=midi_to_name(midi) if midi > 0 else None,
                midi_note=midi if midi > 0 else None,
                volume=current_volume,
                duty=None,
                confidence=Confidence.runtime(conf, f"period={note_start_period}, {cents:+.0f}c"),
            )
            result.notes.append(note)
            result.all_events.append(note)
        note_start_frame = None
        note_start_period = None

    def emit_rest(start_frame: int, end_frame: int):
        if end_frame > start_frame:
            rest = RestEvent(
                frame=start_frame,
                duration_frames=end_frame - start_frame,
                confidence=Confidence.runtime(0.9, "volume=0"),
            )
            result.rests.append(rest)
            result.all_events.append(rest)

    rest_start = None

    for cf in frames:
        vol = cf.volume if cf.volume is not None else current_volume
        period = cf.period if cf.period is not None else current_period

        # Detect note-off: volume drops to 0
        if vol == 0 and current_volume > 0:
            emit_note(cf.frame)
            rest_start = cf.frame

        # Detect note-on or pitch change
        elif vol > 0:
            if current_volume == 0:
                # Coming out of rest
                if rest_start is not None:
                    emit_rest(rest_start, cf.frame)
                    rest_start = None
                note_start_frame = cf.frame
                note_start_period = period

            elif period != current_period and period is not None:
                # Pitch change while volume > 0 = new note
                emit_note(cf.frame)
                note_start_frame = cf.frame
                note_start_period = period

        current_volume = vol
        if period is not None:
            current_period = period

    # Close any open note at end
    if note_start_frame is not None and frames:
        emit_note(frames[-1].frame + 1)
    if rest_start is not None and frames:
        emit_rest(rest_start, frames[-1].frame + 1)

    return result


def segment_triangle_channel(
    frames: list[ChannelFrame],
) -> SegmentedChannel:
    """Segment triangle channel into notes.

    Triangle has no volume control — it's either on or off via the
    linear counter / length counter. We use period changes as note
    boundaries and length_counter changes as note triggers.
    """
    result = SegmentedChannel(channel="triangle")
    if not frames:
        return result

    current_period = None
    note_start_frame = None

    for cf in frames:
        period = cf.period if cf.period is not None else current_period

        if period is not None and period != current_period:
            # New pitch = new note
            if note_start_frame is not None:
                freq = triangle_period_to_freq(current_period)
                midi, cents = freq_to_midi(freq)
                note = NoteEvent(
                    frame=note_start_frame,
                    duration_frames=cf.frame - note_start_frame,
                    period=current_period,
                    pitch=midi_to_name(midi) if midi > 0 else None,
                    midi_note=midi if midi > 0 else None,
                    confidence=Confidence.runtime(0.8, f"tri period change, {cents:+.0f}c"),
                )
                result.notes.append(note)
                result.all_events.append(note)

            note_start_frame = cf.frame
            current_period = period

    # Close final note
    if note_start_frame is not None and current_period is not None and frames:
        freq = triangle_period_to_freq(current_period)
        midi, cents = freq_to_midi(freq)
        note = NoteEvent(
            frame=note_start_frame,
            duration_frames=frames[-1].frame - note_start_frame + 1,
            period=current_period,
            pitch=midi_to_name(midi) if midi > 0 else None,
            midi_note=midi if midi > 0 else None,
            confidence=Confidence.runtime(0.8, "tri final note"),
        )
        result.notes.append(note)
        result.all_events.append(note)

    return result


def segment_noise_channel(
    frames: list[ChannelFrame],
) -> SegmentedChannel:
    """Segment noise channel into hits.

    Each volume-above-zero with a period setting is a noise hit.
    """
    result = SegmentedChannel(channel="noise")
    if not frames:
        return result

    current_volume = 0
    hit_start = None
    hit_period = None

    for cf in frames:
        vol = cf.volume if cf.volume is not None else current_volume
        period = cf.period

        if vol > 0 and current_volume == 0:
            hit_start = cf.frame
            hit_period = period if period is not None else hit_period

        elif vol == 0 and current_volume > 0 and hit_start is not None:
            note = NoteEvent(
                frame=hit_start,
                duration_frames=cf.frame - hit_start,
                period=hit_period,
                volume=current_volume,
                confidence=Confidence.runtime(0.85, "noise hit"),
            )
            result.notes.append(note)
            result.all_events.append(note)
            hit_start = None

        current_volume = vol

    return result


def segment_all_channels(trace: StateTrace) -> dict[str, SegmentedChannel]:
    """Segment all channels from a state trace."""
    results = {}

    for ch in ("pulse1", "pulse2"):
        frames = trace.channel_states.get(ch, [])
        results[ch] = segment_pulse_channel(frames, ch)

    results["triangle"] = segment_triangle_channel(
        trace.channel_states.get("triangle", [])
    )
    results["noise"] = segment_noise_channel(
        trace.channel_states.get("noise", [])
    )

    return results
