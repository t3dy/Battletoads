#!/usr/bin/env python3
"""Export Castlevania Stage 1 "Vampire Killer" to MIDI.

Reads the APU state trace and produces per-channel MIDI files
plus a combined file with all channels.

Usage:
    python export_castlevania_midi.py
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import mido
from nesml.dynamic_analysis.state_trace_ingest import (
    load_state_trace,
    pulse_period_to_freq,
    triangle_period_to_freq,
    freq_to_midi,
    midi_to_name,
    NTSC_CPU_CLOCK,
)

# --- Configuration ---
TRACE_PATH = "traces/castlevania/stage1.csv"
OUTPUT_DIR = Path("exports/midi/castlevania")
SONG_NAME = "Vampire Killer"

# Timing
FRAMES_PER_TICK = 7
NTSC_FPS = 60.0988
SECONDS_PER_TICK = FRAMES_PER_TICK / NTSC_FPS
BPM = 128.7  # tuned for exact 7-frame ticks: 60.0988 / 7 * 60 / 4
PPQN = 480   # pulses per quarter note

# How many loops to export
LOOP_COUNT = 2

# MIDI channels
PULSE1_CH = 0
PULSE2_CH = 1
TRIANGLE_CH = 2
NOISE_CH = 9  # GM drums

# Noise period 7 → MIDI percussion mapping
# NES noise period 7 at long mode sounds like a closed hi-hat
NOISE_MIDI_NOTE = 42  # GM Closed Hi-Hat


def frames_to_ticks(frames: int) -> int:
    """Convert NES frames to MIDI ticks."""
    seconds = frames / NTSC_FPS
    beats = seconds * (BPM / 60.0)
    return int(beats * PPQN)


def build_channel_notes(trace, param_prefix: str, channel_type: str = "pulse"):
    """Extract clean note list from period changes + volume changes.

    Returns list of (frame, duration_frames, midi_note, velocity) tuples.
    """
    # Get period and volume changes
    period_changes = [(ch["frame"], ch["value"]) for ch in trace.raw_changes
                      if ch["parameter"] == param_prefix + "_period"]
    vol_changes = [(ch["frame"], ch["value"]) for ch in trace.raw_changes
                   if ch["parameter"] == param_prefix.replace("2", "0").replace("6", "4") + "_vol"]

    if not period_changes:
        return []

    # Build frame → volume lookup
    vol_at_frame = {}
    current_vol = 0
    vol_idx = 0
    for frame in range(period_changes[0][0], period_changes[-1][0] + 200):
        while vol_idx < len(vol_changes) and vol_changes[vol_idx][0] <= frame:
            current_vol = vol_changes[vol_idx][1]
            vol_idx += 1
        vol_at_frame[frame] = current_vol

    # Each period change is a note onset
    notes = []
    for i, (frame, period) in enumerate(period_changes):
        # Duration = frames until next period change
        if i + 1 < len(period_changes):
            duration = period_changes[i + 1][0] - frame
        else:
            duration = 14  # default

        # Convert period to MIDI note
        if channel_type == "pulse":
            freq = pulse_period_to_freq(period)
        else:
            freq = triangle_period_to_freq(period)

        midi_note, cents = freq_to_midi(freq)
        if midi_note <= 0:
            continue

        # Velocity from volume at note onset
        vol = vol_at_frame.get(frame, 4)
        if isinstance(vol, bool):
            vol = 4
        velocity = min(127, max(30, int(vol * 16)))

        notes.append((frame, duration, midi_note, velocity))

    return notes


def build_noise_notes(trace):
    """Extract noise hits from volume changes."""
    vol_changes = [(ch["frame"], ch["value"]) for ch in trace.raw_changes
                   if ch["parameter"] == "$400C_vol"]

    notes = []
    note_on_frame = None
    for frame, vol in vol_changes:
        if isinstance(vol, bool):
            vol = 4 if vol else 0
        if vol > 0 and note_on_frame is None:
            note_on_frame = frame
        elif vol == 0 and note_on_frame is not None:
            duration = frame - note_on_frame
            velocity = min(127, max(40, 80))
            notes.append((note_on_frame, max(duration, 1), NOISE_MIDI_NOTE, velocity))
            note_on_frame = None

    return notes


def add_notes_to_track(track, notes, channel, loop_length_frames, loop_count):
    """Add notes to a MIDI track, handling loops."""
    all_notes = []

    # Find the loop start (first note after frame ~111 based on analysis)
    # The melody starts at the first period change after the intro
    loop_start_frame = notes[0][0] if notes else 0

    # Find loop boundary in the note sequence
    # We know the loop is 1792 frames from the analysis
    for n in notes:
        if n[0] >= loop_start_frame + loop_length_frames:
            break
        all_notes.append(n)

    one_loop = list(all_notes)

    # Add additional loops
    for loop_num in range(1, loop_count):
        offset = loop_length_frames * loop_num
        for frame, dur, midi, vel in one_loop:
            all_notes.append((frame + offset, dur, midi, vel))

    # Sort by time and convert to MIDI events
    all_notes.sort(key=lambda x: x[0])

    current_tick = 0
    for frame, duration, midi_note, velocity in all_notes:
        note_tick = frames_to_ticks(frame)
        note_dur_ticks = max(frames_to_ticks(duration) - 10, 10)

        delta = max(0, note_tick - current_tick)
        track.append(mido.Message("note_on", note=midi_note, velocity=velocity,
                                  channel=channel, time=delta))
        track.append(mido.Message("note_off", note=midi_note, velocity=0,
                                  channel=channel, time=note_dur_ticks))
        current_tick = note_tick + note_dur_ticks


def main():
    print(f"Loading trace: {TRACE_PATH}")
    trace = load_state_trace(TRACE_PATH)
    print(f"  {trace.total_frames} frames, {len(trace.raw_changes)} changes")

    # Build note lists
    pulse1_notes = build_channel_notes(trace, "$4002", "pulse")
    pulse2_notes = build_channel_notes(trace, "$4006", "pulse")
    triangle_notes = build_channel_notes(trace, "$400A", "triangle")
    noise_notes = build_noise_notes(trace)

    print(f"  Pulse 1: {len(pulse1_notes)} notes")
    print(f"  Pulse 2: {len(pulse2_notes)} notes")
    print(f"  Triangle: {len(triangle_notes)} notes")
    print(f"  Noise: {len(noise_notes)} hits")

    loop_length = 1792  # frames, from analysis

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Combined MIDI ---
    mid = mido.MidiFile(ticks_per_beat=PPQN)

    # Tempo track
    tempo_track = mido.MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(mido.MetaMessage("set_tempo",
                                         tempo=mido.bpm2tempo(BPM), time=0))
    tempo_track.append(mido.MetaMessage("track_name",
                                         name=f"Castlevania - {SONG_NAME}", time=0))

    # Pulse 1
    t1 = mido.MidiTrack()
    mid.tracks.append(t1)
    t1.append(mido.MetaMessage("track_name", name="Pulse 1 (Melody)", time=0))
    t1.append(mido.Message("program_change", program=80, channel=PULSE1_CH, time=0))
    add_notes_to_track(t1, pulse1_notes, PULSE1_CH, loop_length, LOOP_COUNT)

    # Pulse 2
    t2 = mido.MidiTrack()
    mid.tracks.append(t2)
    t2.append(mido.MetaMessage("track_name", name="Pulse 2 (Harmony)", time=0))
    t2.append(mido.Message("program_change", program=80, channel=PULSE2_CH, time=0))
    add_notes_to_track(t2, pulse2_notes, PULSE2_CH, loop_length, LOOP_COUNT)

    # Triangle
    t3 = mido.MidiTrack()
    mid.tracks.append(t3)
    t3.append(mido.MetaMessage("track_name", name="Triangle (Bass)", time=0))
    t3.append(mido.Message("program_change", program=80, channel=TRIANGLE_CH, time=0))
    add_notes_to_track(t3, triangle_notes, TRIANGLE_CH, loop_length, LOOP_COUNT)

    # Noise
    t4 = mido.MidiTrack()
    mid.tracks.append(t4)
    t4.append(mido.MetaMessage("track_name", name="Noise (Drums)", time=0))
    add_notes_to_track(t4, noise_notes, NOISE_CH, loop_length, LOOP_COUNT)

    combined_path = OUTPUT_DIR / "vampire_killer_combined.mid"
    mid.save(str(combined_path))
    print(f"\nSaved: {combined_path}")

    # --- Per-channel MIDI files ---
    for ch_name, notes, ch_num, ch_type in [
        ("pulse1", pulse1_notes, PULSE1_CH, "Pulse 1"),
        ("pulse2", pulse2_notes, PULSE2_CH, "Pulse 2"),
        ("triangle", triangle_notes, TRIANGLE_CH, "Triangle"),
        ("noise", noise_notes, NOISE_CH, "Noise"),
    ]:
        m = mido.MidiFile(ticks_per_beat=PPQN)
        tt = mido.MidiTrack()
        m.tracks.append(tt)
        tt.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
        tt.append(mido.MetaMessage("track_name", name=f"{ch_type} - {SONG_NAME}", time=0))
        if ch_num != NOISE_CH:
            tt.append(mido.Message("program_change", program=80, channel=ch_num, time=0))
        add_notes_to_track(tt, notes, ch_num, loop_length, LOOP_COUNT)
        path = OUTPUT_DIR / f"vampire_killer_{ch_name}.mid"
        m.save(str(path))
        print(f"Saved: {path}")

    print(f"\nDone. {LOOP_COUNT} loops exported at {BPM} BPM.")
    print(f"Import into REAPER and assign an NES-style synth (Plogue Chipsounds, etc.)")


if __name__ == "__main__":
    main()
