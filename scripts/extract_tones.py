#!/usr/bin/env python3
"""Extract NES instrument tone profiles from ROM-captured MIDI files.

Reads CC11 (volume envelope) and CC12 (duty cycle) automation from MIDI
files produced by mesen_to_midi.py or nes_rom_capture.py. Outputs a JSON
catalog of distinct tone profiles per game/channel, with computed ADSR
approximations.

Usage:
    python scripts/extract_tones.py -o output/tone_database/
"""

import argparse
import glob
import json
import math
import os
import sys

import mido


TICKS_PER_FRAME = 16
FRAME_MS = 1000 / 60.1  # ~16.64ms per NES frame

CHANNEL_NAMES = {0: "Square 1", 1: "Square 2", 2: "Triangle", 3: "Noise"}
DUTY_NAMES = {0: "12.5%", 1: "25%", 2: "50%", 3: "75%"}


def extract_notes_with_envelopes(midi_path):
    """Extract per-note envelope and duty data from a MIDI file.

    Returns list of note dicts:
    {
        'channel': 0-3,
        'midi_note': 60,
        'start_tick': 0,
        'duration_ticks': 96,
        'cc11_curve': [vol0, vol1, vol2, ...],  # per-frame volume (0-127)
        'cc12_values': [duty0, duty1, ...],      # per-frame duty (0-3)
        'velocity': 100,
    }
    """
    mid = mido.MidiFile(midi_path)
    notes = []

    for track_idx, track in enumerate(mid.tracks[1:], 1):  # skip meta track
        # Build timeline of events
        tick = 0
        active_note = None
        cc11_timeline = []  # (tick, value)
        cc12_timeline = []  # (tick, value)
        current_cc11 = 0
        current_cc12 = 0
        channel = None

        for msg in track:
            tick += msg.time

            if msg.type == 'control_change':
                if channel is None:
                    channel = msg.channel
                if msg.control == 11:
                    current_cc11 = msg.value
                    cc11_timeline.append((tick, msg.value))
                elif msg.control == 12:
                    current_cc12 = msg.value
                    cc12_timeline.append((tick, msg.value))

            elif msg.type == 'note_on' and msg.velocity > 0:
                if channel is None:
                    channel = msg.channel
                if active_note is not None:
                    # Close previous note
                    _finalize_note(active_note, tick, cc11_timeline, cc12_timeline)
                    notes.append(active_note)

                active_note = {
                    'channel': msg.channel,
                    'midi_note': msg.note,
                    'start_tick': tick,
                    'velocity': msg.velocity,
                    'duration_ticks': 0,
                    'cc11_curve': [],
                    'cc12_values': [],
                }

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if active_note is not None:
                    _finalize_note(active_note, tick, cc11_timeline, cc12_timeline)
                    notes.append(active_note)
                    active_note = None

        if active_note is not None:
            _finalize_note(active_note, tick, cc11_timeline, cc12_timeline)
            notes.append(active_note)

    return notes


def _finalize_note(note, end_tick, cc11_timeline, cc12_timeline):
    """Fill in the per-frame CC11/CC12 curves for a note."""
    note['duration_ticks'] = end_tick - note['start_tick']
    duration_frames = max(1, note['duration_ticks'] // TICKS_PER_FRAME)

    # Sample CC11 at each frame within the note
    cc11_curve = []
    for frame in range(duration_frames):
        frame_tick = note['start_tick'] + frame * TICKS_PER_FRAME
        # Find the most recent CC11 value at or before this tick
        val = 0
        for t, v in cc11_timeline:
            if t <= frame_tick:
                val = v
            else:
                break
        cc11_curve.append(val)
    note['cc11_curve'] = cc11_curve

    # Sample CC12 (duty) — typically changes less often
    cc12_vals = set()
    for t, v in cc12_timeline:
        if note['start_tick'] <= t < end_tick:
            # Convert CC12 value to duty index (0-3)
            if v < 32:
                cc12_vals.add(0)
            elif v < 64:
                cc12_vals.add(1)
            elif v < 96:
                cc12_vals.add(2)
            else:
                cc12_vals.add(3)
    note['cc12_values'] = sorted(cc12_vals) if cc12_vals else [2]  # default 50%


def compute_adsr(cc11_curve):
    """Approximate an ADSR envelope from a CC11 volume curve.

    Returns dict with:
        attack_frames: frames from first non-zero to peak
        decay_frames: frames from peak to sustain level
        sustain_level: average volume in the middle 50% of the note
        release_frames: frames from sustain to silence at end
        peak_volume: maximum volume reached
        shape: 'percussive', 'sustained', 'swell', 'flat'
    """
    if not cc11_curve or max(cc11_curve) == 0:
        return {
            'attack_frames': 0, 'attack_ms': 0,
            'decay_frames': 0, 'decay_ms': 0,
            'sustain_level': 0, 'sustain_ratio': 0,
            'release_frames': 0, 'release_ms': 0,
            'peak_volume': 0, 'shape': 'silent',
        }

    peak = max(cc11_curve)
    peak_idx = cc11_curve.index(peak)

    # Attack: frames from start to peak
    attack_frames = peak_idx

    # Find sustain level: average of middle 50%
    mid_start = len(cc11_curve) // 4
    mid_end = 3 * len(cc11_curve) // 4
    if mid_end > mid_start:
        sustain_level = sum(cc11_curve[mid_start:mid_end]) / (mid_end - mid_start)
    else:
        sustain_level = peak

    # Decay: frames from peak to reaching sustain level
    decay_frames = 0
    for i in range(peak_idx, len(cc11_curve)):
        if cc11_curve[i] <= sustain_level * 1.1:
            decay_frames = i - peak_idx
            break
    else:
        decay_frames = len(cc11_curve) - peak_idx

    # Release: frames at end where volume drops to zero
    release_frames = 0
    for i in range(len(cc11_curve) - 1, -1, -1):
        if cc11_curve[i] > 10:
            release_frames = len(cc11_curve) - 1 - i
            break

    # Classify shape
    if len(cc11_curve) <= 3:
        shape = 'percussive'
    elif attack_frames == 0 and decay_frames > len(cc11_curve) * 0.5:
        shape = 'percussive'
    elif attack_frames > len(cc11_curve) * 0.3:
        shape = 'swell'
    elif sustain_level > peak * 0.7:
        shape = 'sustained'
    elif sustain_level < peak * 0.3:
        shape = 'percussive'
    else:
        shape = 'decaying'

    return {
        'attack_frames': attack_frames,
        'attack_ms': round(attack_frames * FRAME_MS),
        'decay_frames': decay_frames,
        'decay_ms': round(decay_frames * FRAME_MS),
        'sustain_level': round(sustain_level),
        'sustain_ratio': round(sustain_level / max(peak, 1), 2),
        'release_frames': release_frames,
        'release_ms': round(release_frames * FRAME_MS),
        'peak_volume': peak,
        'shape': shape,
    }


def compute_tone_profile(notes, game_name, channel):
    """Compute a representative tone profile for a game/channel.

    Analyzes all notes on a channel and returns the median envelope shape,
    dominant duty cycle, and ADSR approximation.
    """
    if not notes:
        return None

    # Compute ADSR for each note
    adsrs = [compute_adsr(n['cc11_curve']) for n in notes if n['cc11_curve']]
    if not adsrs:
        return None

    # Median ADSR values
    def median(vals):
        s = sorted(vals)
        mid = len(s) // 2
        return s[mid] if s else 0

    attack_ms = median([a['attack_ms'] for a in adsrs])
    decay_ms = median([a['decay_ms'] for a in adsrs])
    sustain_ratio = median([a['sustain_ratio'] for a in adsrs])
    release_ms = median([a['release_ms'] for a in adsrs])
    peak_vol = median([a['peak_volume'] for a in adsrs])

    # Shape distribution
    from collections import Counter
    shapes = Counter(a['shape'] for a in adsrs)
    dominant_shape = shapes.most_common(1)[0][0]

    # Duty cycle analysis
    all_duties = []
    for n in notes:
        all_duties.extend(n['cc12_values'])
    duty_counter = Counter(all_duties)
    dominant_duty = duty_counter.most_common(1)[0][0] if duty_counter else 2

    # Build representative envelope curve (average of first 30 frames)
    max_frames = 30
    avg_curve = [0] * max_frames
    count_curve = [0] * max_frames
    for n in notes:
        for i, v in enumerate(n['cc11_curve'][:max_frames]):
            avg_curve[i] += v
            count_curve[i] += 1
    avg_curve = [round(avg_curve[i] / max(count_curve[i], 1)) for i in range(max_frames)]

    # Note range
    midi_notes = [n['midi_note'] for n in notes]
    note_range = (min(midi_notes), max(midi_notes))

    # Average duration
    avg_duration = sum(n['duration_ticks'] for n in notes) / len(notes)
    avg_duration_ms = round(avg_duration / TICKS_PER_FRAME * FRAME_MS)

    # Build description
    ch_name = CHANNEL_NAMES.get(channel, f"Channel {channel}")
    duty_name = DUTY_NAMES.get(dominant_duty, f"{dominant_duty}")

    if channel == 2:  # Triangle
        description = (
            f"Triangle wave bass. No volume control — only on/off gating. "
            f"One octave below pulse for the same period value. "
            f"Average note duration {avg_duration_ms}ms. "
            f"{'Staccato articulation.' if avg_duration_ms < 100 else 'Legato phrasing.' if avg_duration_ms > 300 else 'Mixed articulation.'}"
        )
    elif channel == 3:  # Noise
        description = (
            f"Noise channel percussion. {len(notes)} hits in the capture. "
            f"{'Dense drum pattern.' if len(notes) > 200 else 'Sparse percussion.' if len(notes) < 50 else 'Moderate drum activity.'}"
        )
    else:  # Pulse
        description = (
            f"{duty_name} duty cycle pulse wave. "
            f"{'Sharp percussive attack' if dominant_shape == 'percussive' else 'Smooth sustained tone' if dominant_shape == 'sustained' else 'Gradual swell' if dominant_shape == 'swell' else 'Natural decay'}. "
            f"Attack: {attack_ms}ms, Decay: {decay_ms}ms, "
            f"Sustain: {round(sustain_ratio * 100)}%, Release: {release_ms}ms. "
            f"Peak volume {peak_vol}/127."
        )

    return {
        'game': game_name,
        'channel': channel,
        'channel_name': ch_name,
        'note_count': len(notes),
        'adsr': {
            'attack_ms': attack_ms,
            'decay_ms': decay_ms,
            'sustain_ratio': sustain_ratio,
            'release_ms': release_ms,
        },
        'peak_volume': peak_vol,
        'dominant_shape': dominant_shape,
        'shape_distribution': dict(shapes),
        'dominant_duty': dominant_duty,
        'duty_name': DUTY_NAMES.get(dominant_duty, str(dominant_duty)),
        'duty_distribution': dict(duty_counter),
        'envelope_curve': avg_curve,
        'note_range': note_range,
        'avg_duration_ms': avg_duration_ms,
        'description': description,
    }


def main():
    parser = argparse.ArgumentParser(description='Extract NES tone profiles from MIDI files')
    parser.add_argument('-o', '--output', default='output/tone_database/', help='Output directory')
    parser.add_argument('--midi-dir', default='output/', help='Directory to search for MIDI files')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Find all ROM-captured MIDI files
    midi_files = glob.glob(os.path.join(args.midi_dir, '**/*rom_v1.mid'), recursive=True)
    print(f"Found {len(midi_files)} MIDI files")

    all_tones = []

    for midi_path in sorted(midi_files):
        # Extract game name from path
        parts = midi_path.replace('\\', '/').split('/')
        game_name = None
        for p in parts:
            if p not in ('output', 'rom_capture', 'midi', 'traces', 'sections'):
                game_name = p
                break
        if not game_name:
            game_name = os.path.basename(midi_path).replace('_rom_v1.mid', '')

        try:
            notes = extract_notes_with_envelopes(midi_path)
        except Exception as e:
            print(f"  ERROR {game_name}: {e}")
            continue

        if not notes:
            continue

        # Group notes by channel
        from collections import defaultdict
        by_channel = defaultdict(list)
        for n in notes:
            by_channel[n['channel']].append(n)

        game_tones = []
        for ch in sorted(by_channel.keys()):
            profile = compute_tone_profile(by_channel[ch], game_name, ch)
            if profile:
                game_tones.append(profile)

        if game_tones:
            print(f"  {game_name}: {len(game_tones)} channels, {sum(t['note_count'] for t in game_tones)} notes")
            all_tones.extend(game_tones)

    # Save JSON
    json_path = os.path.join(args.output, 'tones.json')
    with open(json_path, 'w') as f:
        json.dump(all_tones, f, indent=2)
    print(f"\nSaved {len(all_tones)} tone profiles to {json_path}")

    return all_tones


if __name__ == '__main__':
    main()
