"""
Mesen CSV -> MIDI converter.
Takes a Mesen APU capture CSV and produces a MIDI file with
CC11/CC12 automation, matching the NSF pipeline output format.

Usage:
    python scripts/mesen_to_midi.py <capture.csv> --game "Super Mario Bros." --song "Overworld" -o output/
"""
import csv, math, os, sys, argparse
import mido

CPU_CLK = 1789773
TICKS_PER_BEAT = 480
TICKS_PER_FRAME = 16


def period_to_midi_pulse(period):
    if period <= 8:
        return 0
    freq = CPU_CLK / (16.0 * (period + 1))
    return round(69 + 12 * math.log2(freq / 440.0))


def period_to_midi_tri(period):
    if period <= 2:
        return 0
    freq = CPU_CLK / (32.0 * (period + 1))
    return round(69 + 12 * math.log2(freq / 440.0))


PARAM_MAP = {
    '$4000_vol': 'p1_vol', '$4000_duty': 'p1_duty', '$4000_const': 'p1_const',
    '$4002_period': 'p1_period',
    '$4004_vol': 'p2_vol', '$4004_duty': 'p2_duty', '$4004_const': 'p2_const',
    '$4006_period': 'p2_period',
    '$400A_period': 'tri_period', '$4008_linear': 'tri_linear',
    '$400C_vol': 'noi_vol', '$400C_const': 'noi_const',
    '$400E_period': 'noi_period', '$400E_mode': 'noi_mode',
}


def load_capture(path):
    """Load Mesen CSV and return per-frame APU state list."""
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append(row)

    max_frame = max(int(r['frame']) for r in rows)

    # Build frame-indexed state
    state = {k: 0 for k in PARAM_MAP.values()}
    snapshots = {}
    for row in rows:
        frame = int(row['frame'])
        param = row['parameter']
        val = int(row['value'])
        if param in PARAM_MAP:
            state[PARAM_MAP[param]] = val
        snapshots[frame] = dict(state)

    # Fill all frames (carry forward)
    current = {k: 0 for k in PARAM_MAP.values()}
    full = []
    for frame in range(max_frame + 1):
        if frame in snapshots:
            current = dict(snapshots[frame])
        full.append(dict(current))

    return full


def find_music_start(frames, start_frame=None):
    """Find first frame where music is playing.

    If start_frame is given, use that directly (for captures that
    contain title screen or other music before the target song).
    Otherwise, search for the overworld signature pattern.
    """
    if start_frame is not None:
        return start_frame
    # Default: first frame with audible pulse
    for i, fs in enumerate(frames):
        if (fs['p1_period'] > 8 and fs['p1_vol'] > 0) or \
           (fs['p2_period'] > 8 and fs['p2_vol'] > 0):
            return i
    return 0


def build_pulse_track(frames, prefix, label, midi_ch, program):
    """Build MIDI track for a pulse channel from Mesen frames."""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage('track_name', name=label))
    if program > 0:
        track.append(mido.Message('program_change', channel=midi_ch, program=program))

    prev_midi = 0
    prev_vol = -1
    prev_duty = -1
    ticks = 0
    stable_period = 0

    for fd in frames:
        period = fd[f'{prefix}_period']
        vol = fd[f'{prefix}_vol']
        duty = fd[f'{prefix}_duty']

        # Filter 1-unit jitter from hardware timer
        if abs(period - stable_period) > 2:
            stable_period = period

        midi_note = period_to_midi_pulse(stable_period) if stable_period > 8 and vol > 0 else 0

        # CC12: duty
        if duty != prev_duty and midi_note > 0:
            cc_duty = [16, 32, 64, 96][min(3, duty)]
            track.append(mido.Message('control_change', channel=midi_ch,
                                     control=12, value=cc_duty, time=ticks))
            ticks = 0
            prev_duty = duty

        # CC11: volume
        if vol != prev_vol and midi_note > 0:
            cc_vol = round(vol * 127 / 15)
            track.append(mido.Message('control_change', channel=midi_ch,
                                     control=11, value=cc_vol, time=ticks))
            ticks = 0
            prev_vol = vol

        # Note boundary
        if midi_note != prev_midi:
            if prev_midi > 0:
                track.append(mido.Message('note_off', note=prev_midi,
                                         velocity=0, channel=midi_ch, time=ticks))
                ticks = 0
            if midi_note > 0:
                vel = round(vol * 127 / 15)
                track.append(mido.Message('note_on', note=midi_note,
                                         velocity=vel, channel=midi_ch, time=ticks))
                ticks = 0
            prev_midi = midi_note

        ticks += TICKS_PER_FRAME

    if prev_midi > 0:
        track.append(mido.Message('note_off', note=prev_midi,
                                 velocity=0, channel=midi_ch, time=ticks))
    track.append(mido.MetaMessage('end_of_track', time=0))
    return track


def build_triangle_track(frames, midi_ch=2):
    """Build MIDI track for triangle from Mesen frames."""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage('track_name', name='Triangle [bass]'))
    track.append(mido.Message('program_change', channel=midi_ch, program=38))

    prev_midi = 0
    ticks = 0
    stable_period = 0

    for fd in frames:
        period = fd['tri_period']
        linear = fd['tri_linear']

        # Filter 1-unit jitter
        if abs(period - stable_period) > 2:
            stable_period = period

        midi_note = period_to_midi_tri(stable_period) if stable_period > 2 and linear > 0 else 0

        if midi_note != prev_midi:
            if prev_midi > 0:
                track.append(mido.Message('note_off', note=prev_midi,
                                         velocity=0, channel=midi_ch, time=ticks))
                ticks = 0
            if midi_note > 0:
                track.append(mido.Message('control_change', channel=midi_ch,
                                         control=11, value=127, time=ticks))
                ticks = 0
                track.append(mido.Message('note_on', note=midi_note,
                                         velocity=127, channel=midi_ch, time=ticks))
                ticks = 0
            prev_midi = midi_note

        ticks += TICKS_PER_FRAME

    if prev_midi > 0:
        track.append(mido.Message('note_off', note=prev_midi,
                                 velocity=0, channel=midi_ch, time=ticks))
    track.append(mido.MetaMessage('end_of_track', time=0))
    return track


def noise_period_to_drum(period):
    """Map Mesen decoded noise period to GM drum note."""
    # Mesen reports the decoded timer period from the hardware lookup table.
    # Lower period = higher pitch. Boundaries chosen from Mario analysis:
    #   period <= 32:    hi-hat (short, high)
    #   period <= 202:   snare (mid)
    #   period <= 1016:  tom / mid-low
    #   period > 1016:   kick (low, long)
    if period <= 32:
        return 42   # Closed hi-hat
    elif period <= 202:
        return 38   # Snare
    elif period <= 1016:
        return 45   # Mid tom
    else:
        return 36   # Kick


def build_noise_track(frames, midi_ch=3):
    """Build MIDI track for noise/drums from Mesen frames.

    Detects drum hits using TWO methods:
    1. Volume gate: vol transitions from 0 to >0 (standard)
    2. Period change: period changes while vol > 0 (SMB-style continuous noise)
    Both trigger a new drum note.
    """
    track = mido.MidiTrack()
    track.append(mido.MetaMessage('track_name', name='Noise [drums]'))

    prev_vol = 0
    prev_period = 0
    prev_midi = 0
    ticks = 0

    for fd in frames:
        vol = fd['noi_vol']
        period = fd['noi_period']

        new_hit = False

        # Method 1: volume gate (rising edge)
        if vol > 0 and prev_vol <= 0:
            new_hit = True

        # Method 2: period change while sounding (SMB keeps vol > 0
        # and changes period to switch between drum sounds)
        if vol > 0 and period != prev_period and prev_vol > 0:
            new_hit = True

        if new_hit:
            midi_note = noise_period_to_drum(period)
            vel = round(vol * 127 / 15)
            if prev_midi > 0:
                track.append(mido.Message('note_off', note=prev_midi,
                                         velocity=0, channel=midi_ch, time=ticks))
                ticks = 0
            track.append(mido.Message('note_on', note=midi_note,
                                     velocity=vel, channel=midi_ch, time=ticks))
            ticks = 0
            prev_midi = midi_note

        if vol <= 0 and prev_vol > 0:
            if prev_midi > 0:
                track.append(mido.Message('note_off', note=prev_midi,
                                         velocity=0, channel=midi_ch, time=ticks))
                ticks = 0
                prev_midi = 0

        prev_vol = vol
        prev_period = period
        ticks += TICKS_PER_FRAME

    if prev_midi > 0:
        track.append(mido.Message('note_off', note=prev_midi,
                                 velocity=0, channel=midi_ch, time=ticks))
    track.append(mido.MetaMessage('end_of_track', time=0))
    return track


def main():
    parser = argparse.ArgumentParser(description='Convert Mesen APU capture to MIDI')
    parser.add_argument('capture', help='Mesen capture CSV file')
    parser.add_argument('--game', default='Unknown', help='Game title')
    parser.add_argument('--song', default='Unknown', help='Song name')
    parser.add_argument('--track-num', type=int, default=1, help='Track number')
    parser.add_argument('-o', '--output', default='.', help='Output directory')
    parser.add_argument('--start-frame', type=int, default=None,
                        help='Frame number where the target song starts (skip title screen etc)')
    parser.add_argument('--end-frame', type=int, default=None,
                        help='Frame number where to stop (for trimming capture)')
    args = parser.parse_args()

    print(f"Loading capture: {args.capture}")
    all_frames = load_capture(args.capture)
    print(f"Total frames: {len(all_frames)} ({len(all_frames)/60.1:.1f}s)")

    music_start = find_music_start(all_frames, args.start_frame)
    end = args.end_frame if args.end_frame else len(all_frames)
    frames = all_frames[music_start:end]
    print(f"Music starts at frame {music_start}, using {len(frames)} frames")

    # Build MIDI
    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(128.6)))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))
    meta.append(mido.MetaMessage('text', text=f'Game: {args.game}'))
    meta.append(mido.MetaMessage('text', text=f'Song: {args.song}'))
    meta.append(mido.MetaMessage('text', text='Source: Mesen 2 APU capture (ground truth)'))
    meta.append(mido.MetaMessage('text', text=f'Track: {args.track_num}'))
    mid.tracks.append(meta)

    mid.tracks.append(build_pulse_track(frames, 'p1', 'Square 1 [lead]', 0, 80))
    mid.tracks.append(build_pulse_track(frames, 'p2', 'Square 2 [harmony]', 1, 81))
    mid.tracks.append(build_triangle_track(frames))
    mid.tracks.append(build_noise_track(frames))

    # Save
    os.makedirs(args.output, exist_ok=True)
    game_slug = args.game.replace(' ', '_').replace("'", '')
    song_slug = args.song.replace(' ', '_')
    midi_path = os.path.join(args.output, f'{game_slug}_{args.track_num:02d}_{song_slug}_mesen_v1.mid')
    mid.save(midi_path)

    for i, t in enumerate(mid.tracks[1:], 1):
        notes = sum(1 for m in t if m.type == 'note_on')
        ccs = sum(1 for m in t if m.type == 'control_change')
        print(f"  Track {i}: {notes} notes, {ccs} CCs")

    print(f"\nSaved: {midi_path}")
    return midi_path


if __name__ == '__main__':
    main()
