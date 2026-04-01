#!/usr/bin/env python3
"""Batch render Bach mashups to WAV using NES APU synthesis.

Combines MIDI files with extracted NES instrument presets.
"""

import sys
import math
import wave
import json
import mido
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import needed from render_wav
import scripts.render_wav as render_wav

class NESInstrument:
    def __init__(self, path: Path):
        lines = path.read_text().splitlines()
        header = lines[0].split()
        self.length = int(header[0])
        self.loop_start = int(header[1]) if header[1] != "-1" else None
        self.volume = [int(v) for v in lines[1].split()]
        self.duty = [int(v) for v in lines[2].split()]
        self.pitch = [float(v) for v in lines[3].split()]

    def get_frame(self, frame_idx: int) -> tuple[int, int, float]:
        if frame_idx >= self.length:
            if self.loop_start is not None:
                loop_len = self.length - self.loop_start
                idx = self.loop_start + (frame_idx - self.loop_start) % loop_len
            else:
                return 0, self.duty[-1], self.pitch[-1]
        else:
            idx = frame_idx
        return self.volume[idx], self.duty[idx], self.pitch[idx]

def get_midi_length_secs(mid: mido.MidiFile) -> float:
    # mido.MidiFile.length can be unreliable if not fully parsed
    total_tick = 0
    for track in mid.tracks:
        t = 0
        for msg in track:
            t += msg.time
        total_tick = max(total_tick, t)
    
    # Simple estimate if no tempo events
    tempo = 500000 
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
    return (total_tick / mid.ticks_per_beat) * (tempo / 1000000.0)

def midi_to_frames(midi_path: Path, channel_instruments: dict):
    mid = mido.MidiFile(str(midi_path))
    tpb = mid.ticks_per_beat
    
    tempo = 500000 
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
    
    secs_per_tick = (tempo / 1000000.0) / tpb
    frames_per_tick = secs_per_tick * 60.0
    
    total_secs = get_midi_length_secs(mid)
    total_frames = int(total_secs * 60) + 120 # padding
    
    ch_states = [ [{"period": 0, "vol": 0, "duty": 0, "sounding": False} for _ in range(total_frames)] for _ in range(3) ]

    for track in mid.tracks:
        curr_tick = 0
        active_notes = {}
        
        for msg in track:
            curr_tick += msg.time
            curr_frame = int(curr_tick * frames_per_tick)
            
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[(msg.channel, msg.note)] = curr_frame
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                start_frame = active_notes.pop((msg.channel, msg.note), None)
                if start_frame is not None:
                    # Basic mapping: ch0,1 -> Pulse, ch2 -> Tri
                    nes_ch = -1
                    if msg.channel == 0: nes_ch = 0
                    elif msg.channel == 1: nes_ch = 1
                    elif msg.channel == 2: nes_ch = 2
                    
                    if nes_ch == -1: continue
                    
                    instr = channel_instruments.get(nes_ch)
                    if not instr: continue
                        
                    duration = curr_frame - start_frame
                    div = 16 if nes_ch < 2 else 32
                    freq = 440.0 * (2.0 ** ((msg.note - 69.0) / 12.0))
                    period = int(1789773 / (div * freq)) - 1
                    
                    for f in range(duration):
                        abs_f = start_frame + f
                        if abs_f >= total_frames: break
                        vol, duty, pitch_off = instr.get_frame(f)
                        ch_states[nes_ch][abs_f] = {
                            "period": period,
                            "vol": vol,
                            "duty": duty,
                            "sounding": vol > 0
                        }
    return ch_states

def render_mashup(midi_path: Path, song_set_path: Path, output_path: Path):
    print(f"Rendering {midi_path.name} with {song_set_path.name}...")
    with open(song_set_path) as f:
        ss = json.load(f)
    
    instr_map = {}
    data_dir = REPO_ROOT / "studio" / "presets"
    
    # Resolve instrument presets
    for ch_name, nes_idx in [("pulse1", 0), ("pulse2", 1), ("triangle", 2)]:
        if ch_name in ss["channels"]:
            p = data_dir / ss["channels"][ch_name]["preset"]
            if p.exists(): instr_map[nes_idx] = NESInstrument(p)
            
    # Try generic names
    if "pulse" in ss["channels"] and 0 not in instr_map:
        p = data_dir / ss["channels"]["pulse"]["preset"]
        if p.exists(): instr_map[0] = NESInstrument(p)
        
    # Triangle fallback - use a flat pulse if no triangle preset exists but we have a triangle channel
    # Actually, NES triangle is just a 32-step sequence.
    if 2 not in instr_map:
        # Create a "pseudo-instrument" that is just always full volume
        class TriFull:
            def get_frame(self, f): return 15, 0, 0
            def __init__(self): self.length = 999; self.loop_start = 0
        instr_map[2] = TriFull()

    frames = midi_to_frames(midi_path, instr_map)
    total_frames = len(frames[0])
    total_samples = total_frames * render_wav.SAMPLES_PER_FRAME
    mix = np.zeros(total_samples, dtype=np.float32)

    for ch_idx in range(3):
        ch_type = "pulse" if ch_idx < 2 else "triangle"
        phase = 0.0
        prev_period = -1
        for f in range(total_frames):
            fs = frames[ch_idx][f]
            start = f * render_wav.SAMPLES_PER_FRAME
            end = start + render_wav.SAMPLES_PER_FRAME
            if fs["period"] <= 0: continue
            if ch_type == "pulse":
                audio, phase = render_wav.render_pulse_frame(fs["period"], fs["vol"], fs["duty"], phase, render_wav.SAMPLES_PER_FRAME)
                mix[start:end] += audio * 0.15
            else:
                if fs["period"] != prev_period and fs["sounding"]: phase = 0.0
                prev_period = fs["period"]
                audio, phase = render_wav.render_triangle_frame(fs["period"], fs["sounding"], phase, render_wav.SAMPLES_PER_FRAME)
                mix[start:end] += audio * 0.2
    
    peak = np.max(np.abs(mix))
    if peak > 0.95: mix = mix * (0.95 / peak)
    render_wav.write_wav(mix, output_path)
    print(f"  Generated: {output_path}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--midi", required=True)
    ap.add_argument("--palette", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    render_mashup(Path(args.midi), Path(args.palette), Path(args.output))
