#!/usr/bin/env python3
"""Analyze a MIDI file and output a detailed log for project documentation.

Usage:
    python scripts/analyze_midi_for_log.py <midi_file>
"""

import sys
import math
from pathlib import Path
from collections import Counter

def analyze(midi_path: Path):
    import mido
    mid = mido.MidiFile(str(midi_path))

    print(f"FILE: {midi_path.name}")
    print(f"Duration: {mid.length:.1f} seconds")
    print(f"Ticks/beat: {mid.ticks_per_beat}")
    print(f"Tracks: {len(mid.tracks)}")
    print()

    for i, track in enumerate(mid.tracks):
        print(f"=== Track {i}: {track.name or '(unnamed)'} ===")

        notes_on = []
        notes_off = []
        cc11_msgs = []
        cc12_msgs = []
        other_cc = Counter()
        note_durations = []
        velocities = []
        cc11_values = []
        cc12_values = []

        # Compute note durations
        active_notes = {}  # note_num -> start_tick
        abs_tick = 0

        for msg in track:
            abs_tick += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                notes_on.append(msg)
                velocities.append(msg.velocity)
                active_notes[msg.note] = abs_tick

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                notes_off.append(msg)
                note_num = msg.note
                if note_num in active_notes:
                    dur = abs_tick - active_notes[note_num]
                    note_durations.append(dur)
                    del active_notes[note_num]

            elif msg.type == 'control_change':
                if msg.control == 11:
                    cc11_msgs.append(msg)
                    cc11_values.append(msg.value)
                elif msg.control == 12:
                    cc12_msgs.append(msg)
                    cc12_values.append(msg.value)
                else:
                    other_cc[msg.control] += 1

        print(f"  Notes: {len(notes_on)} on, {len(notes_off)} off")
        print(f"  CC11 (volume): {len(cc11_msgs)} messages")
        print(f"  CC12 (duty):   {len(cc12_msgs)} messages")
        if other_cc:
            print(f"  Other CCs: {dict(other_cc)}")

        if notes_on:
            print(f"  CC11/note ratio: {len(cc11_msgs)/len(notes_on):.1f}")
            if cc12_msgs:
                print(f"  CC12/note ratio: {len(cc12_msgs)/len(notes_on):.1f}")

        if velocities:
            print(f"  Velocity range: {min(velocities)}-{max(velocities)}")
            vc = Counter(velocities)
            top3 = vc.most_common(3)
            print(f"  Top velocities: {', '.join(f'{v}({c}x)' for v,c in top3)}")

        if note_durations:
            dur_frames = [d / 16 for d in note_durations]
            dur_ms = [d / 16 * (1000/60.0988) for d in note_durations]
            print(f"  Duration range: {min(note_durations)}-{max(note_durations)} ticks"
                  f" ({min(dur_frames):.0f}-{max(dur_frames):.0f} frames,"
                  f" {min(dur_ms):.0f}-{max(dur_ms):.0f} ms)")
            avg_dur = sum(note_durations) / len(note_durations)
            print(f"  Duration avg: {avg_dur:.0f} ticks ({avg_dur/16:.1f} frames, {avg_dur/16*(1000/60.0988):.0f} ms)")

            # Duration distribution
            buckets = {"<50ms": 0, "50-100ms": 0, "100-200ms": 0, "200-500ms": 0, "500ms-1s": 0, ">1s": 0}
            for d in dur_ms:
                if d < 50: buckets["<50ms"] += 1
                elif d < 100: buckets["50-100ms"] += 1
                elif d < 200: buckets["100-200ms"] += 1
                elif d < 500: buckets["200-500ms"] += 1
                elif d < 1000: buckets["500ms-1s"] += 1
                else: buckets[">1s"] += 1
            print(f"  Duration distribution: {buckets}")

        if cc11_values:
            print(f"  CC11 range: {min(cc11_values)}-{max(cc11_values)}")
            vc = Counter(cc11_values)
            top5 = vc.most_common(5)
            print(f"  Top CC11 values: {', '.join(f'{v}({c}x)' for v,c in top5)}")

        if cc12_values:
            duty_map = {16: "12.5%", 32: "25%", 64: "50%", 96: "75%"}
            dc = Counter(cc12_values)
            print(f"  Duty distribution: {', '.join(f'{duty_map.get(v,str(v))}({c}x)' for v,c in dc.most_common())}")

        # Show first few note-on/CC11 pairs to illustrate envelope shape
        if notes_on and cc11_msgs:
            print(f"\n  First 3 notes with envelope shape:")
            abs_tick = 0
            events = []
            for msg in track:
                abs_tick += msg.time
                if msg.type in ('note_on', 'note_off', 'control_change'):
                    events.append((abs_tick, msg))

            note_starts = [(t, m) for t, m in events if m.type == 'note_on' and m.velocity > 0]
            for ni in range(min(3, len(note_starts))):
                start_tick, note_msg = note_starts[ni]
                end_tick = start_tick + 9999
                if ni + 1 < len(note_starts):
                    end_tick = note_starts[ni + 1][0]

                # Find CC11 values during this note
                ccs = [(t, m.value) for t, m in events
                       if m.type == 'control_change' and m.control == 11
                       and start_tick <= t < end_tick]

                dur_ticks = end_tick - start_tick
                print(f"    Note {ni+1}: note={note_msg.note} vel={note_msg.velocity}"
                      f" dur={dur_ticks}t ({dur_ticks/16:.0f}f, {dur_ticks/16*(1000/60.0988):.0f}ms)")
                if ccs:
                    cc_str = " > ".join(f"{v}" for _, v in ccs[:8])
                    if len(ccs) > 8:
                        cc_str += f" ... ({len(ccs)} total)"
                    print(f"           CC11: {cc_str}")

        print()


if __name__ == "__main__":
    path = Path(sys.argv[1])
    analyze(path)
