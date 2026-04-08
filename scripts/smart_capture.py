#!/usr/bin/env python3
"""Smart NES ROM music capture — tries multiple strategies automatically.

Attempts in order:
1. Wait 600 frames (10 seconds) — catches games with long intros
2. Press Start at frame 120, wait 600 more — catches Start-gated games
3. Press Start every 60 frames — catches games needing repeated input

For each strategy, checks for period writes ($4002/$4006/$400A).
Stops at the first strategy that produces music.

Usage:
    python scripts/smart_capture.py <rom.nes> -o output/ --game Name
    python scripts/smart_capture.py --batch <directory> -o output/
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nes_rom_capture import (load_rom, NROM, MMC1, UxROM, CNROM, MMC3, AxROM,
                              NESMemory, trigger_nmi, frames_to_mesen_csv)
from py65.devices.mpu6502 import MPU

MAPPER_CLASSES = {0: NROM, 1: MMC1, 2: UxROM, 3: CNROM, 4: MMC3, 7: AxROM}

STRATEGIES = [
    ("wait_600", 600, []),
    ("start_120", 800, [(120, 0x08, 3)]),
    ("start_every_60", 800, [(i, 0x08, 3) for i in range(60, 600, 60)]),
    ("a_start_every_60", 800, [(i, 0x09, 3) for i in range(60, 600, 60)]),
]


def try_capture(rom_path, strategy_name, num_frames, button_script):
    """Try one capture strategy. Returns (success, frames) or (False, None)."""
    prg, banks, mapper_num = load_rom(rom_path)
    if mapper_num not in MAPPER_CLASSES:
        return False, None

    mapper = MAPPER_CLASSES[mapper_num](prg, banks)
    mem = NESMemory(mapper)
    cpu = MPU()
    cpu.memory = mem
    mem.ram[0x4700] = 0x60

    reset = cpu.memory[0xFFFC] | (cpu.memory[0xFFFD] << 8)
    cpu.pc = reset
    cpu.sp = 0xFD
    cpu.p = 0x04

    # Boot with NMI
    cyc = 0
    for _ in range(2000000):
        op = cpu.memory[cpu.pc]
        if op == 0x4C:
            t = cpu.memory[cpu.pc + 1] | (cpu.memory[cpu.pc + 2] << 8)
            if t == cpu.pc:
                break
        cpu.step()
        cyc += 1
        if cyc % 29780 == 0:
            mem._ppu_vblank = True
            if mem._nmi_enabled:
                trigger_nmi(cpu)

    # Capture with button strategy
    mem.capturing = True
    all_frames = []
    found_music = False
    music_start_frame = None

    for frame in range(num_frames):
        mem._ppu_vblank = True
        mem.apu_writes = []
        mem.controller_state = 0x00
        for btn_frame, btn_mask, btn_dur in button_script:
            if btn_frame <= frame < btn_frame + btn_dur:
                mem.controller_state |= btn_mask

        if mem._nmi_enabled:
            trigger_nmi(cpu)

        for _ in range(29780):
            op = cpu.memory[cpu.pc]
            if op == 0x4C:
                t = cpu.memory[cpu.pc + 1] | (cpu.memory[cpu.pc + 2] << 8)
                if t == cpu.pc:
                    break
            cpu.step()

        all_frames.append(list(mem.apu_writes))

        if not found_music:
            if any(r in (0x4002, 0x4006, 0x400A) for r, _ in mem.apu_writes):
                found_music = True
                music_start_frame = frame

    if found_music:
        return True, all_frames
    return False, None


def smart_capture(rom_path, output_dir, game_name):
    """Try all strategies until one produces music."""
    for strategy_name, num_frames, buttons in STRATEGIES:
        success, frames = try_capture(rom_path, strategy_name, num_frames, buttons)
        if success:
            # Save and convert
            os.makedirs(output_dir, exist_ok=True)
            csv_path = os.path.join(output_dir, f'{game_name}_title.csv')
            frames_to_mesen_csv(frames, csv_path)

            try:
                from mesen_to_midi import (load_capture, build_pulse_track,
                                           build_triangle_track, build_noise_track,
                                           find_music_start)
                import mido
                fd = load_capture(csv_path)
                ms = find_music_start(fd)
                pf = fd[ms:]
                mid = mido.MidiFile(ticks_per_beat=480)
                meta = mido.MidiTrack()
                meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(128.6)))
                meta.append(mido.MetaMessage('text', text=f'Game: {game_name}'))
                meta.append(mido.MetaMessage('text', text=f'Strategy: {strategy_name}'))
                mid.tracks.append(meta)
                mid.tracks.append(build_pulse_track(pf, 'p1', 'Square 1', 0, 80))
                mid.tracks.append(build_pulse_track(pf, 'p2', 'Square 2', 1, 81))
                mid.tracks.append(build_triangle_track(pf))
                mid.tracks.append(build_noise_track(pf))
                midi_path = os.path.join(output_dir, f'{game_name}_title_rom_v1.mid')
                mid.save(midi_path)
                notes = [sum(1 for m in t if m.type == 'note_on') for t in mid.tracks[1:]]
                return strategy_name, notes
            except Exception as e:
                return strategy_name, [0, 0, 0, 0]

    return None, None


def main():
    parser = argparse.ArgumentParser(description='Smart NES ROM music capture')
    parser.add_argument('rom', nargs='?', help='ROM file path')
    parser.add_argument('--batch', help='Directory of ROMs to batch process')
    parser.add_argument('-o', '--output', default='output/', help='Output base directory')
    parser.add_argument('--game', default=None, help='Game name')
    args = parser.parse_args()

    if args.batch:
        # Batch mode
        existing = set()
        for root, dirs, files in os.walk('Projects'):
            for f in files:
                if f.endswith('_rom_v1.rpp'):
                    existing.add(os.path.basename(root).lower())

        captured = 0
        for f in sorted(os.listdir(args.batch)):
            if not f.endswith('.nes'):
                continue
            name = f.split('(')[0].strip()
            slug = name.replace(' ', '_').replace("'", '').replace(',', '').replace('.', '')
            slug = slug.replace('-', '_').replace('&', 'and').replace('!', '').replace(':', '')
            slug = slug.replace('__', '_').rstrip('_')
            if slug.lower() in existing:
                continue

            path = os.path.join(args.batch, f)
            try:
                _, _, mapper = load_rom(path)
                if mapper not in MAPPER_CLASSES:
                    continue
            except:
                continue

            out_dir = os.path.join(args.output, slug, 'rom_capture')
            strategy, notes = smart_capture(path, out_dir, slug)
            if strategy and notes and sum(notes) > 10:
                # Build RPP
                midi_path = os.path.join(out_dir, f'{slug}_title_rom_v1.mid')
                rpp_dir = os.path.join('Projects', slug)
                os.makedirs(rpp_dir, exist_ok=True)
                subprocess.run(
                    ['python', 'scripts/generate_project.py', '--midi', midi_path,
                     '--nes-native', '-o', os.path.join(rpp_dir, f'{slug}_Title_rom_v1.rpp')],
                    capture_output=True, text=True, timeout=30)
                captured += 1
                total = sum(notes)
                print(f"OK  {slug:<35} {total:>5} ({strategy})")

        print(f"\n{captured} new games captured")

    elif args.rom:
        game = args.game or Path(args.rom).stem.replace(' ', '_')
        out_dir = os.path.join(args.output, game, 'rom_capture')
        strategy, notes = smart_capture(args.rom, out_dir, game)
        if strategy:
            print(f"Captured with {strategy}: {notes}")
        else:
            print("No music found with any strategy")


if __name__ == '__main__':
    main()
