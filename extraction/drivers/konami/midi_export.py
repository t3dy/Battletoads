"""Export parsed Konami CV1 song data to MIDI via the frame IR.

Produces a 4-channel MIDI file conforming to REQUIREMENTSFORMIDI.md
and the nesmdb CC11/CC12 encoding standard.

The frame IR provides per-frame volume envelopes, so MIDI notes are
shortened to match the actual sounding duration (not the full driver
duration). This gives proper staccato articulation matching the real
game audio.

Usage:
    from extraction.drivers.konami.parser import KonamiCV1Parser
    from extraction.drivers.konami.midi_export import export_to_midi

    parser = KonamiCV1Parser("Castlevania.nes")
    song = parser.parse_track(2)
    export_to_midi(song, "vampire_killer.mid")
"""
# ---------------------------------------------------------------
# STATUS: VERIFIED
# SCOPE: shared
# VALIDATED: 2026-03-28
# TRACE_RESULT: N/A (MIDI export, not directly trace-comparable)
# KNOWN_LIMITATIONS:
#   - CC11 automation quantized to MIDI ticks (slight timing rounding)
#   - Drum mapping uses GM percussion (approximate timbral match)
# LAYER: data (export format, not engine or hardware)
# ---------------------------------------------------------------

from __future__ import annotations

from pathlib import Path

import mido

from extraction.drivers.konami.parser import (
    ParsedSong, NoteEvent, RestEvent, InstrumentChange,
    DrumEvent, RepeatMarker, PITCH_NAMES,
)
from extraction.drivers.konami.frame_ir import (
    parser_to_frame_ir, SongIR, ChannelIR, FrameState,
)


# MIDI constants
PPQ = 480           # ticks per quarter note
FRAMES_PER_SEC = 60  # NTSC

# nesmdb CC standard
CC_VELOCITY = 11    # mid-note volume changes
CC_TIMBRE = 12      # duty cycle

# Channel mapping
CHANNEL_MAP = {
    "pulse1": 0,
    "pulse2": 1,
    "triangle": 2,
}
DRUM_CHANNEL = 3

# Drum MIDI note mapping
DRUM_NOTES = {
    "snare": 38,    # GM Acoustic Snare
    "hihat": 42,    # GM Closed Hi-Hat
}

# GM program numbers for channel identification
GM_PROGRAMS = {
    "pulse1": 80,   # Lead 1 (square)
    "pulse2": 81,   # Lead 2 (sawtooth)
    "triangle": 38,  # Synth Bass 1
}


def frames_to_ticks(frames: int, bpm: float = 120.0) -> int:
    """Convert NES frame count to MIDI ticks."""
    seconds = frames / FRAMES_PER_SEC
    ticks_per_second = PPQ * bpm / 60.0
    return max(1, int(seconds * ticks_per_second + 0.5))


def frame_to_tick(frame: int, bpm: float = 120.0) -> int:
    """Convert a single frame number to absolute MIDI tick."""
    seconds = frame / FRAMES_PER_SEC
    ticks_per_second = PPQ * bpm / 60.0
    return int(seconds * ticks_per_second + 0.5)


def estimate_bpm(song: ParsedSong) -> float:
    """Estimate BPM from the song's tempo and note patterns."""
    tempos = set()
    for ch in song.channels:
        for ev in ch.events:
            if isinstance(ev, InstrumentChange):
                tempos.add(ev.tempo)

    if not tempos:
        return 120.0

    primary_tempo = max(tempos, key=lambda t: sum(
        1 for ch in song.channels for ev in ch.events
        if isinstance(ev, InstrumentChange) and ev.tempo == t
    ))

    beat_frames = primary_tempo * 4
    bpm = 60.0 * FRAMES_PER_SEC / beat_frames
    return round(bpm, 1)


def nes_vol_to_velocity(vol: int) -> int:
    """Convert NES 4-bit volume (0-15) to MIDI velocity (0-127)."""
    if vol <= 0:
        return 0
    return min(127, max(1, int(vol * 127 / 15 + 0.5)))


def nes_vol_to_cc(vol: int) -> int:
    """Convert NES 4-bit volume (0-15) to CC11 value (0-127)."""
    return min(127, max(0, int(vol * 127 / 15 + 0.5)))


def _build_track_from_ir(ch_ir: ChannelIR, midi_ch: int,
                          bpm: float) -> mido.MidiTrack:
    """Build a MIDI track from frame IR data.

    Walks the frame IR and emits:
    - note_on when a note starts sounding (or pitch changes)
    - CC11 when volume changes mid-note
    - CC12 when duty cycle changes
    - note_off when note stops sounding
    """
    track = mido.MidiTrack()

    role = {"pulse1": "lead", "pulse2": "harmony", "triangle": "bass"}[ch_ir.channel_type]
    track.append(mido.MetaMessage('track_name',
                                   name=f'{ch_ir.name} [{role}]', time=0))
    track.append(mido.Message('program_change',
                               channel=midi_ch,
                               program=GM_PROGRAMS[ch_ir.channel_type], time=0))

    if not ch_ir.frames:
        return track

    max_frame = max(ch_ir.frames.keys())

    # Collect all MIDI events as (abs_tick, message) pairs
    events: list[tuple[int, mido.Message]] = []

    current_note = -1
    current_vol = -1
    current_duty = -1
    note_start_vol = 0

    for f in range(max_frame + 1):
        fs = ch_ir.get_frame(f)
        tick = frame_to_tick(f, bpm)

        if fs.sounding and fs.midi_note > 0:
            if fs.midi_note != current_note:
                # New note (or pitch change)
                if current_note >= 0:
                    events.append((tick, mido.Message(
                        'note_off', channel=midi_ch,
                        note=current_note, velocity=0, time=0)))

                vel = nes_vol_to_velocity(fs.volume)
                events.append((tick, mido.Message(
                    'note_on', channel=midi_ch,
                    note=fs.midi_note, velocity=vel, time=0)))
                current_note = fs.midi_note
                note_start_vol = fs.volume
                current_vol = fs.volume

                # Emit CC11 for initial volume
                events.append((tick, mido.Message(
                    'control_change', channel=midi_ch,
                    control=CC_VELOCITY,
                    value=nes_vol_to_cc(fs.volume), time=0)))

            elif fs.volume != current_vol:
                # Volume change mid-note — emit CC11
                events.append((tick, mido.Message(
                    'control_change', channel=midi_ch,
                    control=CC_VELOCITY,
                    value=nes_vol_to_cc(fs.volume), time=0)))
                current_vol = fs.volume

            # Duty cycle change
            if fs.duty != current_duty and ch_ir.channel_type != "triangle":
                events.append((tick, mido.Message(
                    'control_change', channel=midi_ch,
                    control=CC_TIMBRE, value=fs.duty, time=0)))
                current_duty = fs.duty

        else:
            # Not sounding — end any active note
            if current_note >= 0:
                events.append((tick, mido.Message(
                    'note_off', channel=midi_ch,
                    note=current_note, velocity=0, time=0)))
                current_note = -1
                current_vol = -1

    # Final note off
    if current_note >= 0:
        tick = frame_to_tick(max_frame + 1, bpm)
        events.append((tick, mido.Message(
            'note_off', channel=midi_ch,
            note=current_note, velocity=0, time=0)))

    # Sort by tick, then convert to delta times
    events.sort(key=lambda x: x[0])
    last_tick = 0
    for abs_tick, msg in events:
        msg.time = abs_tick - last_tick
        track.append(msg)
        last_tick = abs_tick

    return track


def export_to_midi(song: ParsedSong, output_path: str | Path,
                   game_name: str = "Castlevania",
                   song_name: str = "",
                   envelope_tables: list[list[int]] | None = None) -> Path:
    """Export a parsed song to a Type 1 MIDI file via frame IR.

    Creates 5 tracks:
    - Track 0: Tempo/meta (tempo, time signature, metadata)
    - Track 1: Pulse 1 (channel 0)
    - Track 2: Pulse 2 (channel 1)
    - Track 3: Triangle (channel 2)
    - Track 4: Drums (channel 3)
    """
    output_path = Path(output_path)
    bpm = estimate_bpm(song)
    tempo_us = int(60_000_000 / bpm)

    # Build frame IR from parsed song
    ir = parser_to_frame_ir(song, envelope_tables=envelope_tables)

    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)

    # Track 0: Meta
    meta_track = mido.MidiTrack()
    mid.tracks.append(meta_track)
    meta_track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))
    meta_track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    meta_track.append(mido.MetaMessage('text', text=f'Game: {game_name}', time=0))
    if song_name:
        meta_track.append(mido.MetaMessage('text', text=f'Song: {song_name}', time=0))
    meta_track.append(mido.MetaMessage('text', text='Source: ROM static extraction (frame IR)', time=0))
    meta_track.append(mido.MetaMessage('text', text=f'Driver: Konami Pre-VRC (Maezawa)', time=0))
    meta_track.append(mido.MetaMessage('text', text=f'Track: {song.track_number}', time=0))
    meta_track.append(mido.MetaMessage('text', text=f'Tempo: {bpm} BPM (estimated)', time=0))

    # Build melodic tracks from frame IR
    for ch_ir in ir.channels:
        midi_ch = CHANNEL_MAP[ch_ir.channel_type]
        track = _build_track_from_ir(ch_ir, midi_ch, bpm)
        mid.tracks.append(track)

    # Drum track from parser events (drums aren't in the frame IR)
    drum_track = mido.MidiTrack()
    drum_track.append(mido.MetaMessage('track_name', name='Noise [drums]', time=0))
    drum_events: list[tuple[int, mido.Message]] = []

    for ch_data in song.channels:
        abs_frame = 0
        for ev in ch_data.events:
            if isinstance(ev, DrumEvent):
                abs_tick = frame_to_tick(abs_frame, bpm)
                dur_ticks = frames_to_ticks(ev.duration_frames, bpm)
                drum_note = DRUM_NOTES.get(ev.drum_type, 38)
                drum_events.append((abs_tick, mido.Message(
                    'note_on', channel=DRUM_CHANNEL,
                    note=drum_note, velocity=100, time=0)))
                drum_off_tick = abs_tick + max(1, dur_ticks // 4)
                drum_events.append((drum_off_tick, mido.Message(
                    'note_off', channel=DRUM_CHANNEL,
                    note=drum_note, velocity=0, time=0)))
                # Contra's noise channel has drums with their own
                # timeline — advance the frame counter
                if ch_data.channel_type == "noise":
                    abs_frame += ev.duration_frames
            elif isinstance(ev, (NoteEvent, RestEvent)):
                abs_frame += ev.duration_frames

    drum_events.sort(key=lambda x: x[0])
    drum_abs = 0
    for abs_t, msg in drum_events:
        msg.time = abs_t - drum_abs
        drum_track.append(msg)
        drum_abs = abs_t

    mid.tracks.append(drum_track)

    # Loop point metadata
    for ch in song.channels:
        for ev in ch.events:
            if isinstance(ev, RepeatMarker) and ev.count == 0xFF:
                total_frames = sum(
                    e.duration_frames for e in ch.events
                    if isinstance(e, (NoteEvent, RestEvent))
                )
                loop_tick = frames_to_ticks(total_frames, bpm)
                meta_track.append(mido.MetaMessage('text',
                                                    text='LOOP_END', time=loop_tick))
                break
        break

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python midi_export.py <rom_path> <output.mid> [track_num]")
        sys.exit(1)

    rom_path = sys.argv[1]
    output_path = sys.argv[2]
    track_num = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    from extraction.drivers.konami.parser import KonamiCV1Parser

    parser = KonamiCV1Parser(rom_path)
    song = parser.parse_track(track_num)

    result = export_to_midi(song, output_path,
                            game_name="Castlevania",
                            song_name=f"Track {track_num}")

    # Build IR for stats
    ir = parser_to_frame_ir(song)

    print(f"Exported to {result}")
    print(f"  Channels: {len(song.channels)} melodic + drums")
    for ch_ir in ir.channels:
        sounding = ch_ir.sounding_frames
        total = ch_ir.total_frames
        print(f"  {ch_ir.name}: {sounding}/{total} sounding frames")


if __name__ == "__main__":
    main()
