#!/usr/bin/env python3
"""Convert Mesen APU state trace captures to MIDI + REAPER projects.

Reads a Mesen 2 capture CSV (frame, parameter, value) and produces
MIDI files with CC11 (volume), CC12 (duty cycle), and note events
matching the format from nsf_to_reaper.py. Then generates REAPER
projects via generate_project.py.

Usage:
    # Single segment (manual frame range):
    python scripts/trace_to_midi.py capture.csv -o output/Game_trace/ \\
        --game Game --segment 214 5917 --name "Title_Screen"

    # Auto-detect segments from silence gaps:
    python scripts/trace_to_midi.py capture.csv -o output/Game_trace/ \\
        --game Game --auto-segment

    # Full capture as one file:
    python scripts/trace_to_midi.py capture.csv -o output/Game_trace/ \\
        --game Game --name "Full_Capture"
"""

import argparse
import csv
import math
import os
import subprocess
import sys
from pathlib import Path

import mido

# Reuse build_midi from the NSF pipeline
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nsf_to_reaper import build_midi, TICKS_PER_FRAME, TICKS_PER_BEAT

# NES noise period lookup table (timer values for 4-bit index 0-15)
NOISE_PERIOD_TABLE = [4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068]


def noise_timer_to_index(timer_val):
    """Reverse-map a decoded noise timer value to the 4-bit register index."""
    best_idx = 0
    best_dist = abs(timer_val - NOISE_PERIOD_TABLE[0])
    for i, t in enumerate(NOISE_PERIOD_TABLE):
        d = abs(timer_val - t)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def mask_period(raw_period):
    """Mask Mesen period value to 11-bit NES register range.

    Mesen captures store $4006_period as raw ($4007 << 8 | $4006), which
    includes length counter bits from $4007[7:3]. The actual NES timer
    period is only 11 bits: $4006[7:0] | ($4007[2:0] << 8). Max = 2047.
    Without masking, periods like 2717 produce MIDI notes 2 octaves low.
    """
    return raw_period & 0x7FF


def period_to_midi_trace(period, is_tri=False):
    """Convert NES APU period to MIDI note number (Mesen ground truth).

    Same formula as nsf_to_reaper.period_to_midi() but WITHOUT the -12
    workaround for NSF emulation. Mesen captures real hardware periods.
    Period must be pre-masked to 11 bits (use mask_period()).
    """
    if period <= (2 if is_tri else 8):
        return 0
    div = 32 if is_tri else 16
    freq = 1789773 / (div * (period + 1))
    if freq <= 0:
        return 0
    midi = round(69 + 12 * math.log2(freq / 440))
    if midi < 21 or midi > 120:
        return 0
    return midi


def parse_mesen_csv(csv_path, start_frame=0, end_frame=0):
    """Parse Mesen capture CSV into dense per-frame channel data.

    Returns the same format as nsf_to_reaper.frames_to_channel_data():
    {
        "pulse1":   {"notes": [{"frame": N, "period": P, "vol": V, "duty": D}, ...]},
        "pulse2":   {"notes": [{"frame": N, "period": P, "vol": V, "duty": D}, ...]},
        "triangle": {"notes": [{"frame": N, "period": P, "linear": L}, ...]},
        "noise":    {"notes": [{"frame": N, "vol": V, "period": P, "mode": M}, ...]},
    }
    """
    # First pass: collect all changes per frame
    updates = {}
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row['frame'])
            if end_frame > 0 and frame > end_frame:
                break
            if frame < start_frame:
                # Still accumulate state for initial conditions
                pass
            param = row['parameter']
            val_str = row['value']
            try:
                val = int(float(val_str))
            except ValueError:
                continue
            if frame not in updates:
                updates[frame] = {}
            updates[frame][param] = val

    if not updates:
        return {"pulse1": {"notes": []}, "pulse2": {"notes": []},
                "triangle": {"notes": []}, "noise": {"notes": []}}

    min_frame = min(updates.keys())
    max_frame = max(updates.keys())
    if end_frame > 0:
        max_frame = min(max_frame, end_frame)

    # Running state
    p1_period, p1_vol, p1_duty = 0, 0, 0
    p2_period, p2_vol, p2_duty = 0, 0, 0
    tr_period, tr_linear = 0, 0
    n_vol, n_period_raw, n_mode = 0, 0, 0

    channels = {
        "pulse1": {"notes": []},
        "pulse2": {"notes": []},
        "triangle": {"notes": []},
        "noise": {"notes": []},
    }

    # Walk all frames from min to max, building up state
    for f in range(min_frame, max_frame + 1):
        if f in updates:
            u = updates[f]
            if '$4002_period' in u:
                p1_period = mask_period(u['$4002_period'])
            if '$4000_vol' in u:
                p1_vol = u['$4000_vol']
            if '$4000_duty' in u:
                p1_duty = u['$4000_duty']
            if '$4006_period' in u:
                p2_period = mask_period(u['$4006_period'])
            if '$4004_vol' in u:
                p2_vol = u['$4004_vol']
            if '$4004_duty' in u:
                p2_duty = u['$4004_duty']
            if '$400A_period' in u:
                tr_period = mask_period(u['$400A_period'])
            if '$4008_linear' in u:
                tr_linear = u['$4008_linear']
            if '$400C_vol' in u:
                n_vol = u['$400C_vol']
            if '$400E_period' in u:
                n_period_raw = u['$400E_period']
            if '$400E_mode' in u:
                n_mode = u['$400E_mode']

        # Only emit frames within the requested range
        if f >= start_frame:
            channels["pulse1"]["notes"].append({
                "frame": f - start_frame,
                "period": p1_period,
                "vol": p1_vol,
                "duty": p1_duty,
            })
            channels["pulse2"]["notes"].append({
                "frame": f - start_frame,
                "period": p2_period,
                "vol": p2_vol,
                "duty": p2_duty,
            })
            channels["triangle"]["notes"].append({
                "frame": f - start_frame,
                "period": tr_period,
                "linear": tr_linear,
            })
            # Reverse-map noise period from timer value to 4-bit index
            n_idx = noise_timer_to_index(n_period_raw)
            channels["noise"]["notes"].append({
                "frame": f - start_frame,
                "vol": n_vol,
                "period": n_idx,
                "mode": n_mode,
            })

    return channels


def parse_mesen_registers(csv_path, start_frame=0, end_frame=0):
    """Parse Mesen CSV into per-frame full APU register state.

    Returns a list of dicts, one per frame, each containing the packed
    register bytes for all 4 channels ($4000-$400F) as the NES APU sees them.
    This is used to build SysEx messages for the APU2 synth.
    """
    # Running register state (decoded fields from Mesen)
    state = {
        'p1_duty': 0, 'p1_vol': 0, 'p1_const': 1, 'p1_period': 0, 'p1_sweep': 0,
        'p2_duty': 0, 'p2_vol': 0, 'p2_const': 1, 'p2_period': 0, 'p2_sweep': 0,
        'tr_linear': 0, 'tr_period': 0, 'tr_length': 0,
        'n_vol': 0, 'n_const': 1, 'n_period': 0, 'n_mode': 0,
    }

    # Map Mesen parameter names to our state keys
    param_map = {
        '$4000_duty': 'p1_duty', '$4000_vol': 'p1_vol', '$4000_const': 'p1_const',
        '$4002_period': 'p1_period', '$4001_sweep': 'p1_sweep',
        '$4004_duty': 'p2_duty', '$4004_vol': 'p2_vol', '$4004_const': 'p2_const',
        '$4006_period': 'p2_period', '$4005_sweep': 'p2_sweep',
        '$4008_linear': 'tr_linear', '$400A_period': 'tr_period', '$400B_length': 'tr_length',
        '$400C_vol': 'n_vol', '$400C_const': 'n_const',
        '$400E_period': 'n_period', '$400E_mode': 'n_mode',
    }

    # First pass: collect updates per frame
    updates = {}
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row['frame'])
            if end_frame > 0 and frame > end_frame:
                break
            param = row['parameter']
            if param not in param_map:
                continue
            try:
                val = int(float(row['value']))
            except ValueError:
                continue
            if frame not in updates:
                updates[frame] = {}
            updates[frame][param_map[param]] = val

    if not updates:
        return []

    min_f = min(updates.keys())
    max_f = max(updates.keys())
    if end_frame > 0:
        max_f = min(max_f, end_frame)

    # Second pass: build per-frame packed register state
    registers = []
    for f in range(min_f, max_f + 1):
        if f in updates:
            for k, v in updates[f].items():
                state[k] = v

        if f >= start_frame:
            # Pack decoded fields back into NES register bytes
            # $4000: [duty:2][loop:1][const:1][vol:4]
            r4000 = ((state['p1_duty'] & 3) << 6) | ((state['p1_const'] & 1) << 4) | (state['p1_vol'] & 0xF)
            r4001 = state['p1_sweep'] & 0xFF
            r4002 = state['p1_period'] & 0xFF
            r4003 = (state['p1_period'] >> 8) & 0x07

            r4004 = ((state['p2_duty'] & 3) << 6) | ((state['p2_const'] & 1) << 4) | (state['p2_vol'] & 0xF)
            r4005 = state['p2_sweep'] & 0xFF
            r4006 = state['p2_period'] & 0xFF
            r4007 = (state['p2_period'] >> 8) & 0x07

            r4008 = state['tr_linear'] & 0x7F
            r4009 = 0  # unused
            r400A = state['tr_period'] & 0xFF
            r400B = ((state['tr_period'] >> 8) & 0x07) | ((state['tr_length'] & 0x1F) << 3)

            # Noise: period in Mesen is the decoded timer value, need to reverse-map
            n_idx = noise_timer_to_index(state['n_period'])
            r400C = ((state['n_const'] & 1) << 4) | (state['n_vol'] & 0xF)
            r400D = 0  # unused
            r400E = ((state['n_mode'] & 1) << 7) | (n_idx & 0xF)
            r400F = 0

            # Enable bits: derive from volume/linear counter
            enable = 0
            if state['p1_vol'] > 0: enable |= 1
            if state['p2_vol'] > 0: enable |= 2
            if state['tr_linear'] > 0: enable |= 4
            if state['n_vol'] > 0: enable |= 8

            registers.append({
                'frame': f - start_frame,
                'regs': [
                    [r4000, r4001, r4002, r4003],  # Pulse 1
                    [r4004, r4005, r4006, r4007],  # Pulse 2
                    [r4008, r4009, r400A, r400B],  # Triangle
                    [r400C, r400D, r400E, r400F],  # Noise
                ],
                'enable': enable,
            })

    return registers


def build_sysex_track(registers):
    """Build a MIDI track with SysEx APU register messages.

    Format matches nsf_to_reaper.py and what APU2 synth expects:
    F0 7D 01 <ch> <r0_lo> <r0_hi> <r1_lo> <r1_hi> <r2_lo> <r2_hi> <r3_lo> <r3_hi> <en> F7
    """
    track = mido.MidiTrack()

    for reg_frame in registers:
        first_ch = True
        for ch_idx in range(4):
            r = reg_frame['regs'][ch_idx]
            en = (reg_frame['enable'] >> ch_idx) & 1

            # Split each register byte into 7-bit safe pairs
            data = [
                0x7D,       # Non-commercial SysEx ID
                0x01,       # Message type: APU frame
                ch_idx,     # Channel 0-3
                r[0] & 0x7F, (r[0] >> 7) & 0x01,
                r[1] & 0x7F, (r[1] >> 7) & 0x01,
                r[2] & 0x7F, (r[2] >> 7) & 0x01,
                r[3] & 0x7F, (r[3] >> 7) & 0x01,
                en,
            ]

            delta = TICKS_PER_FRAME if first_ch else 0
            first_ch = False

            track.append(mido.Message('sysex', data=data, time=delta))

    return track


def detect_segments(channels, min_silence_frames=30):
    """Detect song segments by finding silence gaps.

    A frame is silent when all channels have zero volume/activity.
    Returns list of (start_frame, end_frame, label) tuples.
    """
    num_frames = len(channels["pulse1"]["notes"])
    if num_frames == 0:
        return []

    # Find silent frames
    silent = []
    for i in range(num_frames):
        p1_vol = channels["pulse1"]["notes"][i]["vol"]
        p2_vol = channels["pulse2"]["notes"][i]["vol"]
        tr_lin = channels["triangle"]["notes"][i]["linear"]
        n_vol = channels["noise"]["notes"][i]["vol"]
        silent.append(p1_vol == 0 and p2_vol == 0 and tr_lin == 0 and n_vol == 0)

    # Find silence gaps >= min_silence_frames
    segments = []
    in_music = False
    seg_start = 0

    for i in range(num_frames):
        if not silent[i]:
            if not in_music:
                seg_start = i
                in_music = True
        else:
            if in_music:
                # Check if this silence gap is long enough to be a boundary
                gap_end = i
                while gap_end < num_frames and silent[gap_end]:
                    gap_end += 1
                gap_len = gap_end - i
                if gap_len >= min_silence_frames or gap_end == num_frames:
                    segments.append((seg_start, i - 1, f"Segment_{len(segments) + 1}"))
                    in_music = False

    # Handle music that runs to the end
    if in_music:
        segments.append((seg_start, num_frames - 1, f"Segment_{len(segments) + 1}"))

    return segments


def filter_sfx(channels, verbose=False):
    """Filter obvious sound effect artifacts from trace data.

    Conservative approach — only removes clear non-musical artifacts:
    - Ultrasonic periods (< 30 for pulse, < 20 for triangle) while sounding
    - Single-frame volume spikes that are clearly glitches

    Battletoads has intentionally aggressive arpeggios and rapid pitch changes
    in its music, so we do NOT filter based on period jump size.
    """
    sfx_count = 0

    # Triangle: filter extremely high notes (period < 20) — hardware artifact
    tri_frames = channels["triangle"]["notes"]
    for i in range(len(tri_frames)):
        period = tri_frames[i]["period"]
        linear = tri_frames[i]["linear"]
        if linear > 0 and 0 < period < 20:
            tri_frames[i]["linear"] = 0
            sfx_count += 1

    # Pulse: only filter ultrasonic artifacts
    for ch_name in ("pulse1", "pulse2"):
        frames = channels[ch_name]["notes"]
        for i in range(len(frames)):
            period = frames[i]["period"]
            vol = frames[i]["vol"]
            if vol > 0 and 0 < period < 20:
                frames[i]["vol"] = 0
                sfx_count += 1

    if verbose and sfx_count > 0:
        print(f"  SFX filter: zeroed {sfx_count} artifact frames")

    return channels


def extract_segment(channels, start, end):
    """Extract a frame range from channel data, returning a new channels dict."""
    result = {
        "pulse1": {"notes": []},
        "pulse2": {"notes": []},
        "triangle": {"notes": []},
        "noise": {"notes": []},
    }
    for ch_name in result:
        for frame_data in channels[ch_name]["notes"]:
            f = frame_data["frame"]
            if start <= f <= end:
                new_data = dict(frame_data)
                new_data["frame"] = f - start
                result[ch_name]["notes"].append(new_data)
    return result


def process_segment(channels, game, name, seg_num, output_dir,
                    no_sfx_filter=False, registers=None):
    """Convert a segment's channel data to MIDI + REAPER project.

    If registers are provided (from parse_mesen_registers), a SysEx track
    is appended to the MIDI for APU2 hardware-accurate replay, and an
    APU2-based REAPER project is also generated.
    """
    game_slug = game.replace(' ', '_')
    name_slug = name.replace(' ', '_').replace("'", "").replace('!', '')

    if not no_sfx_filter:
        channels = filter_sfx(channels, verbose=True)

    # Build MIDI
    midi_dir = os.path.join(output_dir, "midi")
    os.makedirs(midi_dir, exist_ok=True)

    mid = build_midi(
        channels, game, name, seg_num,
        period_fn=period_to_midi_trace,
        source_text='Mesen APU trace capture (ground truth)',
    )

    # Append SysEx APU register track if we have register data
    if registers:
        sysex_track = build_sysex_track(registers)
        mid.tracks.append(sysex_track)
        sysex_frames = len(registers)
        print(f"  SysEx: {sysex_frames * 4} register messages ({sysex_frames} frames)")

    midi_filename = f"{game_slug}_trace_{seg_num:02d}_{name_slug}_v1.mid"
    midi_path = os.path.join(midi_dir, midi_filename)
    mid.save(midi_path)

    # Stats
    note_counts = [sum(1 for m in t if m.type == 'note_on') for t in mid.tracks[1:5]]
    cc_counts = [sum(1 for m in t if m.type == 'control_change') for t in mid.tracks[1:5]]
    print(f"  MIDI: {midi_path}")
    labels = ["P1", "P2", "Tri", "Noise"]
    print(f"    Notes: {' '.join(f'{l}={c}' for l, c in zip(labels, note_counts))}")
    print(f"    CCs:   {' '.join(f'{l}={c}' for l, c in zip(labels[:3], cc_counts[:3]))}")

    # REAPER projects via generate_project.py
    rpp_dir = os.path.join(output_dir, "reaper")
    os.makedirs(rpp_dir, exist_ok=True)
    gen_script = os.path.join(os.path.dirname(__file__), "generate_project.py")

    # Console synth project (CC-driven, good for keyboard play)
    rpp_filename = f"{game_slug}_trace_{seg_num:02d}_{name_slug}_v1.rpp"
    rpp_path = os.path.join(rpp_dir, rpp_filename)
    subprocess.run([
        sys.executable, gen_script,
        "--midi", midi_path, "--nes-native",
        "-o", rpp_path,
    ], check=True)
    print(f"  REAPER (Console): {rpp_path}")

    # APU2 synth project (SysEx register replay, maximum fidelity)
    if registers:
        rpp_apu2_filename = f"{game_slug}_trace_{seg_num:02d}_{name_slug}_APU2_v1.rpp"
        rpp_apu2_path = os.path.join(rpp_dir, rpp_apu2_filename)
        subprocess.run([
            sys.executable, gen_script,
            "--midi", midi_path, "--nes-native", "--synth", "apu2",
            "-o", rpp_apu2_path,
        ], check=True)
        print(f"  REAPER (APU2):    {rpp_apu2_path}")

    return midi_path, rpp_path


def main():
    parser = argparse.ArgumentParser(
        description='Convert Mesen APU trace captures to MIDI + REAPER projects')
    parser.add_argument('capture', help='Path to Mesen capture CSV')
    parser.add_argument('-o', '--output', required=True, help='Output directory')
    parser.add_argument('--game', default='Unknown', help='Game name for metadata')
    parser.add_argument('--segment', nargs=2, type=int, metavar=('START', 'END'),
                        help='Extract specific frame range')
    parser.add_argument('--seg-num', type=int, default=1,
                        help='Segment number for output filename (default 1)')
    parser.add_argument('--name', default=None, help='Song name (for single segment)')
    parser.add_argument('--auto-segment', action='store_true',
                        help='Auto-detect segments from silence gaps')
    parser.add_argument('--min-silence', type=int, default=30,
                        help='Min silence gap for auto-segmentation (frames, default 30)')
    parser.add_argument('--no-sfx-filter', action='store_true',
                        help='Disable SFX filtering')
    args = parser.parse_args()

    print(f"Loading trace: {args.capture}")
    channels = parse_mesen_csv(args.capture)
    total_frames = len(channels["pulse1"]["notes"])
    print(f"  {total_frames} frames ({total_frames / 60:.1f}s)")

    # Also parse full register state for SysEx generation
    print(f"  Parsing APU registers for SysEx...")
    all_registers = parse_mesen_registers(args.capture)
    print(f"  {len(all_registers)} register frames")

    if args.segment:
        # Manual single segment
        start, end = args.segment
        name = args.name or f"Frames_{start}_{end}"
        print(f"\n=== {name} (frames {start}-{end}) ===")
        seg_channels = extract_segment(channels, start, end)
        seg_registers = parse_mesen_registers(args.capture, start_frame=start, end_frame=end)
        process_segment(seg_channels, args.game, name, args.seg_num, args.output,
                        no_sfx_filter=args.no_sfx_filter, registers=seg_registers)

    elif args.auto_segment:
        # Auto-detect segments
        segments = detect_segments(channels, min_silence_frames=args.min_silence)
        print(f"\nDetected {len(segments)} segments:")
        for i, (start, end, label) in enumerate(segments):
            dur = (end - start + 1) / 60
            print(f"  {i + 1}. frames {start}-{end} ({dur:.1f}s)")

        for i, (start, end, label) in enumerate(segments):
            name = args.name if args.name and len(segments) == 1 else label
            print(f"\n=== {name} (frames {start}-{end}) ===")
            seg_channels = extract_segment(channels, start, end)
            seg_registers = parse_mesen_registers(args.capture, start_frame=start, end_frame=end)
            process_segment(seg_channels, args.game, name, i + 1, args.output,
                            no_sfx_filter=args.no_sfx_filter, registers=seg_registers)
    else:
        # Full capture as one file
        name = args.name or "Full_Capture"
        print(f"\n=== {name} ===")
        process_segment(channels, args.game, name, 1, args.output,
                        no_sfx_filter=args.no_sfx_filter, registers=all_registers)

    print("\nDone!")


if __name__ == '__main__':
    main()
