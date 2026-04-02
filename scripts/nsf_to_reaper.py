"""
NSF to MIDI + REAPER Project converter.

Runs the NSF driver via 6502 emulation, captures APU register writes,
and produces:
- 4-track MIDI with CC11 (volume), CC12 (duty cycle), note events
- REAPER .rpp project with ReapNES_APU.jsfx synth loaded per channel
- WAV preview render

Usage:
    python scripts/nsf_to_reaper.py <nsf_file> <song#> <seconds> -o <output_dir>
    python scripts/nsf_to_reaper.py <nsf_file> --all -o <output_dir>
    python scripts/nsf_to_reaper.py <nsf_file> --all -o <output_dir> --names "Stage Select,Enemy Chosen,Cut Man,..."
"""

import sys
import os
import math
import wave
import struct
import argparse
import numpy as np
import mido
from pathlib import Path
from py65.devices.mpu6502 import MPU

SAMPLE_RATE = 44100
SPF = SAMPLE_RATE // 60
TICKS_PER_BEAT = 480
TICKS_PER_FRAME = 16  # at our tempo mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
JSFX_PATH = REPO_ROOT / "studio" / "jsfx" / "ReapNES_APU.jsfx"


class NsfEmulator:
    """Run NSF driver and capture APU register writes."""

    def __init__(self, nsf_path):
        with open(nsf_path, 'rb') as f:
            self.nsf_data = f.read()

        self.total_songs = self.nsf_data[6]
        self.starting_song = self.nsf_data[7]
        self.load_addr = self.nsf_data[8] | (self.nsf_data[9] << 8)
        self.init_addr = self.nsf_data[10] | (self.nsf_data[11] << 8)
        self.play_addr = self.nsf_data[12] | (self.nsf_data[13] << 8)
        self.title = self.nsf_data[14:46].decode('ascii', errors='replace').rstrip('\x00')
        self.artist = self.nsf_data[46:78].decode('ascii', errors='replace').rstrip('\x00')
        self.bankswitch = list(self.nsf_data[0x70:0x78])
        self.uses_bankswitch = any(b != 0 for b in self.bankswitch)
        self.rom_data = self.nsf_data[128:]

    def _load_rom(self, cpu):
        """Load ROM data into CPU memory, handling bankswitch if needed."""
        if not self.uses_bankswitch:
            # Linear loading — original behavior
            for i, byte in enumerate(self.rom_data):
                addr = self.load_addr + i
                if addr < 0x10000:
                    cpu.memory[addr] = byte
        else:
            # Bankswitched NSF: ROM data is organized as 4KB pages.
            # The bankswitch table at $70-$77 maps 8 slots to ROM pages:
            #   slot 0 → $8000-$8FFF, slot 1 → $9000-$9FFF, ...
            #   slot 7 → $F000-$FFFF
            page_size = 0x1000  # 4KB
            num_pages = (len(self.rom_data) + page_size - 1) // page_size
            for slot in range(8):
                page_num = self.bankswitch[slot]
                if page_num >= num_pages:
                    continue
                dest_addr = 0x8000 + slot * page_size
                src_offset = page_num * page_size
                for i in range(page_size):
                    if src_offset + i < len(self.rom_data):
                        cpu.memory[dest_addr + i] = self.rom_data[src_offset + i]

    def _install_bankswitch_handler(self, cpu):
        """Install write handler for NSF bankswitch registers $5FF8-$5FFF.

        When the driver writes to $5FF8+slot, swap the corresponding 4KB
        page at $8000+slot*$1000 from the ROM data.
        """
        if not self.uses_bankswitch:
            return

        page_size = 0x1000
        rom_data = self.rom_data
        num_pages = (len(rom_data) + page_size - 1) // page_size

        # py65 doesn't have write hooks, so we override the __setitem__
        # on the memory object to intercept bankswitch writes.
        original_memory = cpu.memory
        emu_self = self

        class BankswitchMemory:
            """Memory wrapper that intercepts writes to $5FF8-$5FFF."""
            def __init__(self, mem):
                self._mem = mem

            def __getitem__(self, key):
                return self._mem[key]

            def __setitem__(self, key, value):
                self._mem[key] = value
                if 0x5FF8 <= key <= 0x5FFF:
                    slot = key - 0x5FF8
                    page_num = value
                    if page_num < num_pages:
                        dest = 0x8000 + slot * page_size
                        src = page_num * page_size
                        for i in range(page_size):
                            if src + i < len(rom_data):
                                self._mem[dest + i] = rom_data[src + i]
                            else:
                                self._mem[dest + i] = 0

            def __len__(self):
                return len(self._mem)

            def __iter__(self):
                return iter(self._mem)

        cpu.memory = BankswitchMemory(original_memory)

    def play_song(self, song_num, duration_frames):
        """Run the driver and return per-frame APU state."""
        cpu = MPU()
        for i in range(0x10000):
            cpu.memory[i] = 0
        self._load_rom(cpu)
        self._install_bankswitch_handler(cpu)
        cpu.memory[0x4700] = 0x60  # RTS sentinel

        def call(addr, a=0, max_cyc=50000):
            cpu.sp = 0xFD
            cpu.stPushWord(0x46FE)
            cpu.a = a; cpu.x = 0; cpu.y = 0; cpu.pc = addr; cpu.p = 0x04
            cyc = 0
            while cyc < max_cyc and cpu.pc not in (0x46FF, 0x4700):
                cpu.step(); cyc += 1

        # INIT
        call(self.init_addr, a=song_num - 1)

        # PLAY each frame, capture APU state
        frames = []
        for frame in range(duration_frames):
            # Snapshot APU before
            old = {r: cpu.memory[r] for r in range(0x4000, 0x4018)}
            call(self.play_addr, max_cyc=30000)
            # Capture changes
            state = {}
            for r in range(0x4000, 0x4018):
                val = cpu.memory[r]
                if val != old[r] or frame == 0:
                    state[r] = val
            frames.append(state)

        return frames


def frames_to_channel_data(frames):
    """Convert per-frame APU state to per-channel note/volume/duty data."""
    channels = {
        "pulse1": {"period": 0, "vol": 0, "duty": 1, "notes": []},
        "pulse2": {"period": 0, "vol": 0, "duty": 1, "notes": []},
        "triangle": {"period": 0, "linear": 0, "notes": []},
        "noise": {"vol": 0, "period": 0, "mode": 0, "notes": []},
    }

    for frame_idx, state in enumerate(frames):
        # Update pulse 1
        if 0x4000 in state:
            channels["pulse1"]["duty"] = (state[0x4000] >> 6) & 3
            channels["pulse1"]["vol"] = state[0x4000] & 0x0F
        if 0x4002 in state:
            channels["pulse1"]["period"] = (channels["pulse1"]["period"] & 0x700) | state[0x4002]
        if 0x4003 in state:
            channels["pulse1"]["period"] = (channels["pulse1"]["period"] & 0xFF) | ((state[0x4003] & 7) << 8)

        # Update pulse 2
        if 0x4004 in state:
            channels["pulse2"]["duty"] = (state[0x4004] >> 6) & 3
            channels["pulse2"]["vol"] = state[0x4004] & 0x0F
        if 0x4006 in state:
            channels["pulse2"]["period"] = (channels["pulse2"]["period"] & 0x700) | state[0x4006]
        if 0x4007 in state:
            channels["pulse2"]["period"] = (channels["pulse2"]["period"] & 0xFF) | ((state[0x4007] & 7) << 8)

        # Update triangle
        if 0x4008 in state:
            channels["triangle"]["linear"] = state[0x4008] & 0x7F
        if 0x400A in state:
            channels["triangle"]["period"] = (channels["triangle"].get("period", 0) & 0x700) | state[0x400A]
        if 0x400B in state:
            channels["triangle"]["period"] = (channels["triangle"].get("period", 0) & 0xFF) | ((state[0x400B] & 7) << 8)

        # Update noise
        if 0x400C in state:
            channels["noise"]["vol"] = state[0x400C] & 0x0F
        if 0x400E in state:
            channels["noise"]["period"] = state[0x400E] & 0x0F
            channels["noise"]["mode"] = (state[0x400E] >> 7) & 1

        # Record per-frame state for each channel
        for ch_name in ["pulse1", "pulse2"]:
            ch = channels[ch_name]
            ch["notes"].append({
                "frame": frame_idx,
                "period": ch["period"],
                "vol": ch["vol"],
                "duty": ch["duty"],
            })

        ch = channels["triangle"]
        ch["notes"].append({
            "frame": frame_idx,
            "period": ch.get("period", 0),
            "linear": ch["linear"],
        })

        ch = channels["noise"]
        ch["notes"].append({
            "frame": frame_idx,
            "vol": ch["vol"],
            "period": ch["period"],
            "mode": ch["mode"],
        })

    return channels


def period_to_midi(period, is_tri=False):
    if period <= (2 if is_tri else 8):
        return 0
    div = 32 if is_tri else 16
    freq = 1789773 / (div * (period + 1))
    midi = round(69 + 12 * math.log2(freq / 440))
    # WORKAROUND: NSF emulation (py65) produces pulse periods that are
    # exactly half the Mesen ground truth, shifting notes +12 semitones.
    # Triangle is unaffected (confirmed via Mesen capture comparison).
    # Root cause: SMB sound driver pulse period table indexing differs
    # under NSF harness vs ROM execution. See docs/MARIODISCOVERIES.md.
    if not is_tri:
        midi -= 12
    return midi


def build_midi(channels, game_title, song_name, song_num, frames=None,
               period_fn=None, source_text=None):
    """Build a MIDI file matching the CV1 pipeline format.

    If frames (raw APU register snapshots) are provided, embeds per-frame
    SysEx messages carrying the raw register state for each channel.
    This enables hardware-accurate register-replay in the APU2 synth.

    Args:
        period_fn: Optional period-to-MIDI converter. Defaults to period_to_midi.
                   Trace-based pipelines pass a version without the NSF -12 workaround.
        source_text: Optional source description for MIDI metadata track.

    SysEx format per channel per frame:
        F0 7D 01 <ch> <reg0> <reg1> <reg2> <reg3> <enable_bit> F7
    Where ch=0-3, reg0-3 are the 4 APU register bytes for that channel,
    and enable_bit is the channel's bit from $4015.
    All data bytes are 7-bit safe (register values 0-127 as-is,
    values 128-255 split into two 7-bit bytes: low7, high1).
    """
    if period_fn is None:
        period_fn = period_to_midi
    if source_text is None:
        source_text = 'NSF emulation (6502 + APU capture)'
    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)

    # Track 0: metadata
    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(128.6)))
    meta_track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))
    meta_track.append(mido.MetaMessage('text', text=f'Game: {game_title}'))
    meta_track.append(mido.MetaMessage('text', text=f'Song: {song_name}'))
    meta_track.append(mido.MetaMessage('text', text=f'Source: {source_text}'))
    meta_track.append(mido.MetaMessage('text', text=f'Track: {song_num}'))
    mid.tracks.append(meta_track)

    # Channel tracks
    track_configs = [
        ("pulse1", "Square 1 [lead]", 0, 80),
        ("pulse2", "Square 2 [harmony]", 1, 81),
        ("triangle", "Triangle [bass]", 2, 38),
        ("noise", "Noise [drums]", 3, 0),
    ]

    for ch_name, label, midi_ch, program in track_configs:
        track = mido.MidiTrack()
        track.append(mido.MetaMessage('track_name', name=label))
        if program > 0:
            track.append(mido.Message('program_change', channel=midi_ch, program=program))

        ch_frames = channels[ch_name]["notes"]
        prev_midi = 0
        prev_vol = -1
        prev_duty = -1
        ticks = 0

        for frame_data in ch_frames:
            if ch_name in ("pulse1", "pulse2"):
                period = frame_data["period"]
                vol = frame_data["vol"]
                duty = frame_data["duty"]
                midi_note = period_fn(period) if period > 8 and vol > 0 else 0

                # CC12: duty cycle change
                if duty != prev_duty and midi_note > 0:
                    cc_duty = [16, 32, 64, 96][duty]  # map 0-3 to CC range
                    track.append(mido.Message('control_change', channel=midi_ch,
                                             control=12, value=cc_duty, time=ticks))
                    ticks = 0
                    prev_duty = duty

                # CC11: volume envelope
                if vol != prev_vol and midi_note > 0:
                    cc_vol = min(127, vol * 8)
                    track.append(mido.Message('control_change', channel=midi_ch,
                                             control=11, value=cc_vol, time=ticks))
                    ticks = 0
                    prev_vol = vol

                # Note changes
                if midi_note != prev_midi:
                    if prev_midi > 0:
                        track.append(mido.Message('note_off', note=prev_midi,
                                                  velocity=0, channel=midi_ch, time=ticks))
                        ticks = 0
                    if midi_note > 0:
                        vel = min(127, vol * 8)
                        track.append(mido.Message('note_on', note=midi_note,
                                                  velocity=vel, channel=midi_ch, time=ticks))
                        ticks = 0
                    prev_midi = midi_note

            elif ch_name == "triangle":
                period = frame_data["period"]
                linear = frame_data["linear"]
                midi_note = period_fn(period, is_tri=True) if period > 2 and linear > 0 else 0

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

            elif ch_name == "noise":
                vol = frame_data["vol"]
                period = frame_data["period"]
                mode = frame_data["mode"]

                # Track drum hit state for duration capping
                if not hasattr(frame_data, '_noise_init'):
                    # Use closure vars instead
                    pass

                if vol > 0 and prev_vol <= 0:
                    # New drum hit: map noise period to GM drum note
                    if period <= 4:
                        drum_note = 42  # closed hi-hat
                    elif period <= 8:
                        drum_note = 38  # snare
                    else:
                        drum_note = 36  # kick
                    vel = min(127, vol * 8)
                    track.append(mido.Message('note_on', note=drum_note,
                                             velocity=vel, channel=midi_ch, time=ticks))
                    ticks = 0
                    noise_hit_vol = vol  # remember initial hit volume
                    noise_hit_age = 0   # frames since hit
                elif vol > 0 and prev_vol > 0 and prev_midi > 0:
                    # Drum still sounding — check if it should end
                    noise_hit_age += 1
                    # End drum if: volume dropped to <25% of hit, or >12 frames old
                    if vol <= max(1, noise_hit_vol // 4) or noise_hit_age > 12:
                        track.append(mido.Message('note_off', note=prev_midi,
                                                 velocity=0, channel=midi_ch, time=ticks))
                        ticks = 0
                        prev_midi = 0
                elif vol <= 0 and prev_vol > 0:
                    if prev_midi > 0:
                        track.append(mido.Message('note_off', note=prev_midi,
                                                 velocity=0, channel=midi_ch, time=ticks))
                        ticks = 0
                    prev_midi = 0

                if vol > 0 and prev_midi == 0:
                    prev_midi = drum_note if 'drum_note' in dir() else 42
                prev_vol = vol

            ticks += TICKS_PER_FRAME

        # Final note off
        if prev_midi > 0:
            track.append(mido.Message('note_off', note=prev_midi,
                                      velocity=0, channel=midi_ch, time=ticks))

        mid.tracks.append(track)

    # Track 5: APU register SysEx stream (for hardware-accurate replay)
    if frames is not None:
        sysex_track = mido.MidiTrack()
        sysex_track.append(mido.MetaMessage('track_name', name='APU Registers'))

        # Channel register base addresses
        ch_regs = [
            (0x4000, 0x4001, 0x4002, 0x4003),  # Pulse 1
            (0x4004, 0x4005, 0x4006, 0x4007),  # Pulse 2
            (0x4008, 0x4009, 0x400A, 0x400B),  # Triangle
            (0x400C, 0x400D, 0x400E, 0x400F),  # Noise
        ]

        # Build full register state (not just deltas)
        full_state = {}
        for r in range(0x4000, 0x4018):
            full_state[r] = 0

        sysex_count = 0
        for frame_idx, state in enumerate(frames):
            # Update full state with this frame's changes
            for r, v in state.items():
                full_state[r] = v

            # $4015 is write-only on real hardware; py65 flat memory often
            # reads back 0x00. Derive enable from volume/period instead:
            # a channel is "enabled" if it has non-zero volume (pulse/noise)
            # or non-zero linear counter (triangle).
            enable = 0
            if (full_state[0x4000] & 0x0F) > 0:  # Pulse 1 vol > 0
                enable |= 1
            if (full_state[0x4004] & 0x0F) > 0:  # Pulse 2 vol > 0
                enable |= 2
            if (full_state[0x4008] & 0x7F) > 0:  # Triangle linear > 0
                enable |= 4
            if (full_state[0x400C] & 0x0F) > 0:  # Noise vol > 0
                enable |= 8

            # Emit SysEx for each channel
            # Format: F0 7D 01 ch r0_lo r0_hi r1_lo r1_hi r2_lo r2_hi r3_lo r3_hi en F7
            # Each register byte split into two 7-bit values: (val & 0x7F), ((val >> 7) & 0x01)
            first_ch = True
            for ch_idx, regs in enumerate(ch_regs):
                r0 = full_state[regs[0]]
                r1 = full_state[regs[1]]
                r2 = full_state[regs[2]]
                r3 = full_state[regs[3]]
                en = (enable >> ch_idx) & 1

                # SysEx data (after F0, before F7) — all bytes must be 0-127
                data = [
                    0x7D,       # Non-commercial SysEx ID
                    0x01,       # Message type: APU frame
                    ch_idx,     # Channel 0-3
                    r0 & 0x7F, (r0 >> 7) & 0x01,
                    r1 & 0x7F, (r1 >> 7) & 0x01,
                    r2 & 0x7F, (r2 >> 7) & 0x01,
                    r3 & 0x7F, (r3 >> 7) & 0x01,
                    en,         # Channel enable bit
                ]

                # Time: first SysEx in frame gets TICKS_PER_FRAME delta,
                # subsequent channels in same frame get delta=0
                if first_ch:
                    delta = TICKS_PER_FRAME
                    first_ch = False
                else:
                    delta = 0

                sysex_track.append(mido.Message('sysex', data=data, time=delta))
                sysex_count += 1

        mid.tracks.append(sysex_track)
        print(f"    SysEx: {sysex_count} register messages ({sysex_count // 4} frames)")

    return mid


def build_rpp(midi_path, song_name, duration_sec):
    """Generate a REAPER project file with ReapNES_APU.jsfx."""
    midi_abs = str(Path(midi_path).resolve())
    jsfx_rel = str(JSFX_PATH.relative_to(REPO_ROOT)) if JSFX_PATH.exists() else "studio/jsfx/ReapNES_APU.jsfx"

    tracks = [
        ("NES - Pulse 1", 0, 16576606),
        ("NES - Pulse 2", 1, 10092441),
        ("NES - Triangle", 2, 16744192),
        ("NES - Noise / Drums", 3, 11184810),
    ]

    rpp_lines = [
        '<REAPER_PROJECT 0.1 "7.0"',
        f'  TEMPO 128.6 4 4',
    ]

    for track_name, midi_ch, color in tracks:
        rpp_lines.extend([
            '  <TRACK',
            f'    NAME "{track_name}"',
            f'    PEAKCOL {color}',
            '    <ITEM',
            f'      POSITION 0',
            f'      LENGTH {duration_sec:.6f}',
            '      <SOURCE MIDI',
            f'        FILE "{midi_abs}"',
            '      >',
            '    >',
            '  >',
        ])

    rpp_lines.append('>')
    return '\n'.join(rpp_lines)


def render_wav(channels, output_path, num_frames):
    """Render WAV from channel data (same synth as trace renderer)."""
    total_samples = num_frames * SPF
    mix = np.zeros(total_samples, dtype=np.float64)
    phase = {"p1": 0.0, "p2": 0.0, "tri": 0.0}

    for frame in range(num_frames):
        s = frame * SPF
        e = s + SPF

        for ch_name, ph_key in [("pulse1", "p1"), ("pulse2", "p2")]:
            fd = channels[ch_name]["notes"][frame]
            p, v, d = fd["period"], fd["vol"], fd["duty"]
            if p >= 8 and v > 0:
                freq = 1789773 / (16 * (p + 1))
                dv = [0.125, 0.25, 0.5, 0.75][d]
                a = v / 15 * 0.25
                pa = (np.arange(SPF) * freq / SAMPLE_RATE + phase[ph_key]) % 1.0
                mix[s:e] += np.where(pa < dv, a, -a)
                phase[ph_key] = (phase[ph_key] + SPF * freq / SAMPLE_RATE) % 1.0

        fd = channels["triangle"]["notes"][frame]
        p = fd["period"]
        lin = fd["linear"]
        if p >= 2 and lin > 0:
            freq = 1789773 / (32 * (p + 1))
            a = 0.25
            pa = (np.arange(SPF) * freq / SAMPLE_RATE + phase["tri"]) % 1.0
            mix[s:e] += np.where(pa < 0.5, a * (4 * pa - 1), a * (3 - 4 * pa))
            phase["tri"] = (phase["tri"] + SPF * freq / SAMPLE_RATE) % 1.0

        fd = channels["noise"]["notes"][frame]
        nv = fd["vol"]
        if nv > 0:
            mix[s:e] += np.random.uniform(-nv / 15 * 0.12, nv / 15 * 0.12, SPF)

    pk = np.max(np.abs(mix))
    if pk > 0:
        mix = mix / pk * 0.9
    audio = (mix * 32767).astype(np.int16)

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return len(audio) / SAMPLE_RATE


def process_song(emu, song_num, song_name, duration_sec, output_dir):
    """Process one song: emulate, extract MIDI, build REAPER project, render WAV."""
    game_slug = emu.title.replace(' ', '_').replace('[', '').replace(']', '')
    song_slug = song_name.replace(' ', '_').replace("'", "").replace('!', '').replace('.', '')

    duration_frames = int(duration_sec * 60)
    print(f"  Emulating ({duration_frames} frames)...", end="", flush=True)
    frames = emu.play_song(song_num, duration_frames)
    print(f" done")

    print(f"  Extracting channel data...", end="", flush=True)
    channels = frames_to_channel_data(frames)
    print(f" done")

    # MIDI
    midi_dir = os.path.join(output_dir, "midi")
    os.makedirs(midi_dir, exist_ok=True)
    mid = build_midi(channels, emu.title, song_name, song_num, frames=frames)
    midi_path = os.path.join(midi_dir, f"{game_slug}_{song_num:02d}_{song_slug}_v1.mid")
    mid.save(midi_path)

    note_counts = [sum(1 for m in t if m.type == 'note_on') for t in mid.tracks[1:]]
    cc_counts = [sum(1 for m in t if m.type == 'control_change') for t in mid.tracks[1:]]
    print(f"  MIDI: {midi_path}")
    print(f"    Notes: P1={note_counts[0]} P2={note_counts[1]} Tri={note_counts[2]} Noise={note_counts[3]}")
    print(f"    CCs:   P1={cc_counts[0]} P2={cc_counts[1]} Tri={cc_counts[2]}")

    # REAPER project (via generate_project.py — the canonical RPP builder)
    rpp_dir = os.path.join(output_dir, "reaper")
    os.makedirs(rpp_dir, exist_ok=True)
    rpp_path = os.path.join(rpp_dir, f"{game_slug}_{song_num:02d}_{song_slug}_v1.rpp")
    import subprocess
    gen_script = os.path.join(os.path.dirname(__file__), "generate_project.py")
    subprocess.run([
        sys.executable, gen_script,
        "--midi", midi_path, "--nes-native",
        "-o", rpp_path,
    ], check=True)
    print(f"  REAPER: {rpp_path}")

    # WAV preview
    wav_dir = os.path.join(output_dir, "wav")
    os.makedirs(wav_dir, exist_ok=True)
    wav_path = os.path.join(wav_dir, f"{game_slug}_{song_num:02d}_{song_slug}_v1.wav")
    dur = render_wav(channels, wav_path, duration_frames)
    print(f"  WAV: {wav_path} ({dur:.1f}s)")

    return midi_path, rpp_path, wav_path


def main():
    parser = argparse.ArgumentParser(description='NSF to MIDI + REAPER converter')
    parser.add_argument('nsf', help='Path to NSF file')
    parser.add_argument('song', nargs='?', help='Song number or --all')
    parser.add_argument('seconds', nargs='?', type=float, default=90, help='Duration in seconds')
    parser.add_argument('-o', '--output', default='output', help='Output directory')
    parser.add_argument('--all', action='store_true', help='Process all songs')
    parser.add_argument('--names', help='Comma-separated track names')
    args = parser.parse_args()

    emu = NsfEmulator(args.nsf)
    print(f"NSF: {emu.title} by {emu.artist}")
    print(f"Songs: {emu.total_songs}")

    if args.all or args.song == '--all':
        names = args.names.split(',') if args.names else [f"Song {i}" for i in range(1, emu.total_songs + 1)]

        for i in range(emu.total_songs):
            song_num = i + 1
            name = names[i].strip() if i < len(names) else f"Song {song_num}"
            dur = args.seconds

            print(f"\n=== Song {song_num}: {name} ===")
            process_song(emu, song_num, name, dur, args.output)
    else:
        song_num = int(args.song)
        name = f"Song {song_num}"
        print(f"\n=== Song {song_num} ===")
        process_song(emu, song_num, name, args.seconds, args.output)


if __name__ == "__main__":
    main()
