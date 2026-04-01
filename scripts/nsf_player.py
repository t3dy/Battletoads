"""
Minimal NSF player using py65 6502 emulator.
Runs the NSF sound driver and captures APU register writes,
then renders to WAV using our NES APU synth.

Usage:
    python scripts/nsf_player.py <nsf_file> <song_number> <duration_sec> <output.wav>
    python scripts/nsf_player.py <nsf_file> --all <output_dir>
"""

import sys
import struct
import math
import wave
import os
import numpy as np
from py65.devices.mpu6502 import MPU

SAMPLE_RATE = 44100
SPF = SAMPLE_RATE // 60  # samples per frame


class NsfPlayer:
    def __init__(self, nsf_path):
        with open(nsf_path, 'rb') as f:
            self.nsf_data = f.read()

        # Parse header
        self.total_songs = self.nsf_data[6]
        self.starting_song = self.nsf_data[7]
        self.load_addr = self.nsf_data[8] | (self.nsf_data[9] << 8)
        self.init_addr = self.nsf_data[10] | (self.nsf_data[11] << 8)
        self.play_addr = self.nsf_data[12] | (self.nsf_data[13] << 8)
        self.title = self.nsf_data[14:46].decode('ascii', errors='replace').rstrip('\x00')
        self.rom_data = self.nsf_data[128:]

        # APU state captured per frame
        self.apu_state = {}
        self.apu_writes = []  # list of (frame, register, value)

    def _setup_cpu(self):
        """Initialize 6502 CPU with NSF data loaded."""
        self.cpu = MPU()

        # Clear all RAM
        for i in range(0x10000):
            self.cpu.memory[i] = 0

        # Load NSF data at load_addr
        for i, byte in enumerate(self.rom_data):
            addr = self.load_addr + i
            if addr < 0x10000:
                self.cpu.memory[addr] = byte

        # Install APU write trap: intercept writes to $4000-$4017
        # py65 doesn't have write callbacks, so we'll poll after each step.
        # Instead, put RTS at a known address and JSR to init/play.
        # We'll use $4700 as a trampoline area.

        # RTS instruction at $4700
        self.cpu.memory[0x4700] = 0x60  # RTS

        self.current_frame = 0
        self.frame_apu = {}

    def _call_subroutine(self, addr, a_reg=0, max_cycles=50000):
        """Call a 6502 subroutine and return when it hits RTS."""
        # Push return address (point to an infinite loop at $4700-1 = $46FF)
        # Actually: JSR pushes PC+2, RTS pops and adds 1.
        # We'll set PC directly and run until we return to our sentinel.

        # Set up: push sentinel return address onto stack
        sentinel = 0x46FF  # RTS will return to $4700 which is another RTS
        self.cpu.memory[0x4700] = 0x60  # RTS
        self.cpu.memory[0x4701] = 0x60  # RTS (sentinel landing)

        self.cpu.sp = 0xFD
        # Push (sentinel - 1) because RTS adds 1
        self.cpu.stPushWord(sentinel - 1)

        self.cpu.a = a_reg
        self.cpu.x = 0
        self.cpu.y = 0
        self.cpu.pc = addr
        self.cpu.p = 0x04  # IRQ disabled

        cycles = 0
        while cycles < max_cycles:
            # Check if we've returned to sentinel
            if self.cpu.pc == sentinel or self.cpu.pc == sentinel + 1:
                break

            # Capture APU writes before each instruction
            old_apu = {}
            for reg in range(0x4000, 0x4018):
                old_apu[reg] = self.cpu.memory[reg]

            self.cpu.step()
            cycles += 1

            # Check for APU changes
            for reg in range(0x4000, 0x4018):
                new_val = self.cpu.memory[reg]
                if new_val != old_apu[reg]:
                    self.apu_writes.append((self.current_frame, reg, new_val))
                    self.frame_apu[(self.current_frame, reg)] = new_val

        return cycles

    def play_song(self, song_num, duration_frames):
        """Play a song for the specified number of frames."""
        self._setup_cpu()
        self.apu_writes = []
        self.frame_apu = {}

        # Call INIT with song number (0-based in NSF format)
        print(f"  INIT song {song_num}...", end="", flush=True)
        cycles = self._call_subroutine(self.init_addr, a_reg=song_num - 1)
        print(f" {cycles} cycles")

        # Call PLAY once per frame
        print(f"  Playing {duration_frames} frames...", end="", flush=True)
        for frame in range(duration_frames):
            self.current_frame = frame
            self._call_subroutine(self.play_addr, max_cycles=30000)

            if frame % 300 == 0 and frame > 0:
                print(f" {frame}", end="", flush=True)

        print(f" done")

    def render_wav(self, output_path):
        """Render captured APU data to WAV."""
        if not self.apu_writes:
            print("  No APU data captured!")
            return 0

        max_frame = max(f for f, _, _ in self.apu_writes)
        total_samples = (max_frame + 1) * SPF
        mix = np.zeros(total_samples, dtype=np.float64)

        # Build per-frame APU state
        state = {
            "p1_vol": 0, "p1_duty": 1, "p1_period": 0,
            "p2_vol": 0, "p2_duty": 1, "p2_period": 0,
            "tri_period": 0, "tri_linear": 0,
            "noise_vol": 0, "noise_period": 0, "noise_mode": 0,
        }

        # Group writes by frame
        frame_writes = {}
        for frame, reg, val in self.apu_writes:
            frame_writes.setdefault(frame, []).append((reg, val))

        phase = {"p1": 0.0, "p2": 0.0, "tri": 0.0}
        lfsr = 1

        for frame in range(max_frame + 1):
            # Apply writes for this frame
            if frame in frame_writes:
                for reg, val in frame_writes[frame]:
                    if reg == 0x4000:
                        state["p1_duty"] = (val >> 6) & 3
                        state["p1_vol"] = val & 0x0F
                    elif reg == 0x4002:
                        state["p1_period"] = (state["p1_period"] & 0x700) | val
                    elif reg == 0x4003:
                        state["p1_period"] = (state["p1_period"] & 0xFF) | ((val & 7) << 8)
                    elif reg == 0x4004:
                        state["p2_duty"] = (val >> 6) & 3
                        state["p2_vol"] = val & 0x0F
                    elif reg == 0x4006:
                        state["p2_period"] = (state["p2_period"] & 0x700) | val
                    elif reg == 0x4007:
                        state["p2_period"] = (state["p2_period"] & 0xFF) | ((val & 7) << 8)
                    elif reg == 0x4008:
                        state["tri_linear"] = val & 0x7F
                    elif reg == 0x400A:
                        state["tri_period"] = (state["tri_period"] & 0x700) | val
                    elif reg == 0x400B:
                        state["tri_period"] = (state["tri_period"] & 0xFF) | ((val & 7) << 8)
                    elif reg == 0x400C:
                        state["noise_vol"] = val & 0x0F
                    elif reg == 0x400E:
                        state["noise_period"] = val & 0x0F
                        state["noise_mode"] = (val >> 7) & 1

            s = frame * SPF
            e = s + SPF

            # Pulse 1
            p, v, d = state["p1_period"], state["p1_vol"], state["p1_duty"]
            if p >= 8 and v > 0:
                freq = 1789773 / (16 * (p + 1))
                dv = [0.125, 0.25, 0.5, 0.75][d]
                a = v / 15 * 0.25
                pa = (np.arange(SPF) * freq / SAMPLE_RATE + phase["p1"]) % 1.0
                mix[s:e] += np.where(pa < dv, a, -a)
                phase["p1"] = (phase["p1"] + SPF * freq / SAMPLE_RATE) % 1.0

            # Pulse 2
            p, v, d = state["p2_period"], state["p2_vol"], state["p2_duty"]
            if p >= 8 and v > 0:
                freq = 1789773 / (16 * (p + 1))
                dv = [0.125, 0.25, 0.5, 0.75][d]
                a = v / 15 * 0.25
                pa = (np.arange(SPF) * freq / SAMPLE_RATE + phase["p2"]) % 1.0
                mix[s:e] += np.where(pa < dv, a, -a)
                phase["p2"] = (phase["p2"] + SPF * freq / SAMPLE_RATE) % 1.0

            # Triangle
            p, lin = state["tri_period"], state["tri_linear"]
            if p >= 2 and lin > 0:
                freq = 1789773 / (32 * (p + 1))
                a = 0.25
                pa = (np.arange(SPF) * freq / SAMPLE_RATE + phase["tri"]) % 1.0
                mix[s:e] += np.where(pa < 0.5, a * (4 * pa - 1), a * (3 - 4 * pa))
                phase["tri"] = (phase["tri"] + SPF * freq / SAMPLE_RATE) % 1.0

            # Noise
            nv = state["noise_vol"]
            if nv > 0:
                na = nv / 15 * 0.12
                mix[s:e] += np.random.uniform(-na, na, SPF)

        # Normalize and save
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


def main():
    if len(sys.argv) < 4:
        print("Usage: python nsf_player.py <nsf> <song#> <seconds> <output.wav>")
        print("       python nsf_player.py <nsf> --all <output_dir>")
        sys.exit(1)

    nsf_path = sys.argv[1]
    player = NsfPlayer(nsf_path)
    print(f"NSF: {player.title}, {player.total_songs} songs")

    if sys.argv[2] == "--all":
        output_dir = sys.argv[3]
        os.makedirs(output_dir, exist_ok=True)

        # Track list with durations (Mega Man 1 specific, but works generically)
        for song in range(1, player.total_songs + 1):
            duration_sec = 90  # default 90 seconds per track
            duration_frames = int(duration_sec * 60)

            print(f"\nSong {song}/{player.total_songs}:")
            player.play_song(song, duration_frames)

            output_path = os.path.join(output_dir, f"song_{song:02d}_v1.wav")
            dur = player.render_wav(output_path)
            print(f"  -> {output_path} ({dur:.1f}s)")
    else:
        song = int(sys.argv[2])
        seconds = float(sys.argv[3])
        output = sys.argv[4]
        frames = int(seconds * 60)

        print(f"Playing song {song} for {seconds}s ({frames} frames)...")
        player.play_song(song, frames)
        dur = player.render_wav(output)
        print(f"Rendered: {output} ({dur:.1f}s)")


if __name__ == "__main__":
    main()
