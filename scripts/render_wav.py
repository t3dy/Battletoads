#!/usr/bin/env python3
"""Render parsed Konami CV1 tracks to WAV using a simple NES APU synth.

Generates audio directly from the frame IR — no MIDI or external
synthesizer needed. Produces pulse waves (variable duty cycle),
triangle waves, and noise for drums.

Usage:
    python scripts/render_wav.py <rom_path> <track_num> <output.wav>
    python scripts/render_wav.py --all <rom_path> <output_dir>
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extraction.drivers.konami.parser import (
    KonamiCV1Parser, NoteEvent, RestEvent, InstrumentChange,
    DrumEvent, PITCH_NAMES,
)
from extraction.drivers.konami.frame_ir import (
    parser_to_frame_ir, SongIR, ChannelIR, FrameState,
    pitch_octave_to_period, CPU_CLK,
)

SAMPLE_RATE = 44100
FRAMES_PER_SEC = 60
SAMPLES_PER_FRAME = SAMPLE_RATE // FRAMES_PER_SEC  # 735

# NES pulse duty cycle waveforms (8-step sequences)
DUTY_TABLES = {
    0: [0, 1, 0, 0, 0, 0, 0, 0],  # 12.5%
    1: [0, 1, 1, 0, 0, 0, 0, 0],  # 25%
    2: [0, 1, 1, 1, 1, 0, 0, 0],  # 50%
    3: [1, 0, 0, 1, 1, 1, 1, 1],  # 75% (inverted 25%)
}

# Triangle 32-step waveform
TRIANGLE_WAVE = [
    15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
]


def render_pulse_frame(period: int, volume: int, duty: int,
                       phase: float, samples: int) -> tuple[np.ndarray, float]:
    """Render one frame of NES pulse channel audio."""
    if volume == 0 or period < 8:
        return np.zeros(samples, dtype=np.float32), phase

    freq = CPU_CLK / (16.0 * (period + 1))
    duty_table = DUTY_TABLES.get(duty, DUTY_TABLES[2])
    inc = 8.0 * freq / SAMPLE_RATE

    out = np.empty(samples, dtype=np.float32)
    vol_scale = volume / 15.0
    p = phase
    for i in range(samples):
        step = int(p) & 7
        out[i] = (duty_table[step] * 2.0 - 1.0) * vol_scale
        p += inc
        if p >= 8.0:
            p -= 8.0

    return out, p


def render_triangle_frame(period: int, sounding: bool,
                          phase: float, samples: int) -> tuple[np.ndarray, float]:
    """Render one frame of NES triangle channel audio."""
    if not sounding or period < 2:
        return np.zeros(samples, dtype=np.float32), phase

    freq = CPU_CLK / (32.0 * (period + 1))
    inc = 32.0 * freq / SAMPLE_RATE

    out = np.empty(samples, dtype=np.float32)
    p = phase
    for i in range(samples):
        step = int(p) & 31
        out[i] = (TRIANGLE_WAVE[step] / 15.0 * 2.0 - 1.0)
        p += inc
        if p >= 32.0:
            p -= 32.0

    return out, p


def render_noise_hit(samples: int, volume: float, decay: float,
                     lowpass: float = 0.0) -> np.ndarray:
    """Render a noise burst for drum hits.

    Args:
        lowpass: 0.0 = no filtering (white noise), 0.5-0.9 = low-pass
            coefficient for bass-heavy kicks. Higher = darker/bassier.
    """
    out = np.random.uniform(-1, 1, samples).astype(np.float32)
    # Optional low-pass filter for kick drums
    if lowpass > 0:
        for i in range(1, len(out)):
            out[i] = out[i - 1] * lowpass + out[i] * (1.0 - lowpass)
    # Apply decay envelope
    env = np.exp(-np.arange(samples) * decay / SAMPLE_RATE)
    return out * env * volume


def render_song(song_ir: SongIR, parsed_song=None) -> np.ndarray:
    """Render a full song from frame IR to audio samples."""
    total_frames = song_ir.total_frames
    if total_frames == 0:
        return np.zeros(SAMPLE_RATE, dtype=np.float32)

    total_samples = total_frames * SAMPLES_PER_FRAME
    mix = np.zeros(total_samples, dtype=np.float32)

    # Render each melodic channel
    for ch_ir in song_ir.channels:
        ch_type = ch_ir.channel_type
        phase = 0.0
        prev_midi = 0  # track note changes for triangle phase reset

        for f in range(total_frames):
            fs = ch_ir.get_frame(f)
            start = f * SAMPLES_PER_FRAME
            end = start + SAMPLES_PER_FRAME

            if ch_type in ("pulse1", "pulse2"):
                audio, phase = render_pulse_frame(
                    fs.period, fs.volume, fs.duty, phase, SAMPLES_PER_FRAME)
                mix[start:end] += audio * 0.25
            elif ch_type == "triangle":
                # Reset phase on new note (creates attack transient = "punch")
                if fs.midi_note != prev_midi and fs.sounding:
                    phase = 0.0
                prev_midi = fs.midi_note
                audio, phase = render_triangle_frame(
                    fs.period, fs.sounding, phase, SAMPLES_PER_FRAME)
                mix[start:end] += audio * 0.25

    # Render drums from parsed events
    if parsed_song:
        for ch_data in parsed_song.channels:
            abs_frame = 0
            for ev in ch_data.events:
                if isinstance(ev, DrumEvent):
                    start = abs_frame * SAMPLES_PER_FRAME
                    dur_samples = min(ev.duration_frames * SAMPLES_PER_FRAME,
                                     total_samples - start)
                    if dur_samples > 0 and start < total_samples:
                        dtype = ev.drum_type
                        if dtype == "kick":
                            # Bass drum: low-frequency burst, fast decay
                            # Reinforces triangle bass notes
                            noise = render_noise_hit(dur_samples, 0.8, 20.0, lowpass=0.7)
                            mix[start:start + len(noise)] += noise * 0.20
                        elif dtype == "kick_snare":
                            # Compound: kick + snare DMC overlay
                            kick = render_noise_hit(dur_samples, 0.8, 20.0, lowpass=0.7)
                            snare = render_noise_hit(dur_samples, 0.5, 10.0)
                            mix[start:start + len(kick)] += kick * 0.18
                            mix[start:start + len(snare)] += snare * 0.12
                        elif dtype == "kick_hihat":
                            # Compound: kick + hihat DMC overlay
                            kick = render_noise_hit(dur_samples, 0.8, 20.0, lowpass=0.7)
                            hat = render_noise_hit(dur_samples, 0.3, 25.0)
                            mix[start:start + len(kick)] += kick * 0.18
                            mix[start:start + len(hat)] += hat * 0.08
                        elif dtype == "snare":
                            noise = render_noise_hit(dur_samples, 0.6, 10.0)
                            mix[start:start + len(noise)] += noise * 0.15
                        elif dtype == "hihat":
                            noise = render_noise_hit(dur_samples, 0.3, 25.0)
                            mix[start:start + len(noise)] += noise * 0.10
                        else:
                            noise = render_noise_hit(dur_samples, 0.5, 12.0)
                            mix[start:start + len(noise)] += noise * 0.12
                    abs_frame += ev.duration_frames
                elif isinstance(ev, (NoteEvent, RestEvent)):
                    abs_frame += ev.duration_frames

    # Normalize to prevent clipping
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix * (0.95 / peak)

    return mix


def write_wav(samples: np.ndarray, path: str | Path, sample_rate: int = SAMPLE_RATE):
    """Write float32 samples to a 16-bit WAV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to 16-bit
    int_samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    with wave.open(str(path), 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(int_samples.tobytes())


def render_track(rom_path: str, track_num: int, output_path: str) -> Path:
    """Parse and render a single track to WAV."""
    parser = KonamiCV1Parser(rom_path)
    song = parser.parse_track(track_num)
    ir = parser_to_frame_ir(song)
    audio = render_song(ir, song)
    out = Path(output_path)
    write_wav(audio, out)
    dur = len(audio) / SAMPLE_RATE
    print(f"  Rendered: {out.name} ({dur:.1f}s)")
    return out


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Render CV1 tracks to WAV")
    ap.add_argument("rom_path", help="Path to Castlevania ROM")
    ap.add_argument("output", help="Output WAV path or directory (with --all)")
    ap.add_argument("track_num", nargs="?", type=int, default=2,
                    help="Track number (default: 2)")
    ap.add_argument("--all", action="store_true", help="Render all 15 tracks")
    args = ap.parse_args()

    if args.all:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        NAMES = {
            1: 'Prologue', 2: 'Vampire_Killer', 3: 'Stalker',
            4: 'Wicked_Child', 5: 'Walking_on_the_Edge', 6: 'Heart_of_Fire',
            7: 'Out_of_Time', 8: 'Nothing_to_Lose', 9: 'Poison_Mind',
            10: 'Black_Night', 11: 'Voyager', 12: 'Game_Over',
            13: 'Boss_Fight', 14: 'Stage_Clear', 15: 'Death_SFX',
        }
        for t in range(1, 16):
            name = NAMES.get(t, f'Track_{t}')
            wav_path = out_dir / f"cv1_{t:02d}_{name}.wav"
            try:
                render_track(args.rom_path, t, str(wav_path))
            except Exception as ex:
                print(f"  ERROR track {t}: {ex}")
    else:
        render_track(args.rom_path, args.track_num, args.output)


if __name__ == "__main__":
    main()
