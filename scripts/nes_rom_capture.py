#!/usr/bin/env python3
"""Boot an NES ROM via py65 6502 emulation and capture APU register writes.

This is a headless NES emulator — no graphics, no input, just CPU + APU
capture. It boots the ROM from RESET, fires NMI at 60Hz, and records
every write to $4000-$4017 per frame. The output is a Mesen-compatible
CSV that can be fed directly into mesen_to_midi.py.

Built specifically for Kid Icarus (mapper 1 / MMC1), but the MMC1
mapper logic is generic and should work for any MMC1 game.

Usage:
    python scripts/nes_rom_capture.py <rom.nes> -o output/ --frames 6000
    python scripts/nes_rom_capture.py <rom.nes> -o output/ --frames 6000 --poke 0x3A=0 0x81=1
"""

import argparse
import csv
import os
import struct
import sys
from pathlib import Path

from py65.devices.mpu6502 import MPU


class MMC1:
    """MMC1 mapper state machine.

    Handles the serial register protocol: 5 consecutive writes to
    $8000-$FFFF, one bit at a time (bit 0 of the written value),
    fill a 5-bit shift register. Writing with bit 7 set resets the
    shift register.

    After 5 writes, the accumulated value is dispatched to one of
    4 internal registers based on the address of the 5th write:
      $8000-$9FFF -> Control (register 0)
      $A000-$BFFF -> CHR bank 0 (register 1)
      $C000-$DFFF -> CHR bank 1 (register 2)
      $E000-$FFFF -> PRG bank (register 3)
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks
        self.shift = 0
        self.shift_count = 0
        self.control = 0x0C  # default: PRG mode 3 (fix last, switch first)
        self.chr_bank0 = 0
        self.chr_bank1 = 0
        self.prg_bank = 0

    def write(self, addr, value):
        """Handle a write to $8000-$FFFF (mapper register)."""
        if value & 0x80:
            # Reset
            self.shift = 0
            self.shift_count = 0
            self.control |= 0x0C
            return

        self.shift |= (value & 1) << self.shift_count
        self.shift_count += 1

        if self.shift_count == 5:
            reg = (addr >> 13) & 3  # 0-3 based on address range
            if reg == 0:
                self.control = self.shift
            elif reg == 1:
                self.chr_bank0 = self.shift
            elif reg == 2:
                self.chr_bank1 = self.shift
            elif reg == 3:
                self.prg_bank = self.shift & 0x0F
            self.shift = 0
            self.shift_count = 0

    def get_prg_banks(self):
        """Return (bank_at_8000, bank_at_C000) based on current PRG mode."""
        mode = (self.control >> 2) & 3
        bank = self.prg_bank % self.num_prg_banks
        last = self.num_prg_banks - 1

        if mode <= 1:
            # 32KB mode: ignore low bit, map 2 consecutive banks
            base = bank & 0xFE
            return (base, base + 1)
        elif mode == 2:
            # Fix first bank at $8000, switch $C000
            return (0, bank)
        else:
            # Fix last bank at $C000, switch $8000
            return (bank, last)


class NROM:
    """NROM mapper (mapper 0). No bank switching at all.

    PRG is either 16KB (mirrored at $8000 and $C000) or 32KB (at $8000-$FFFF).
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks

    def write(self, addr, value):
        pass  # No mapper registers

    def get_prg_banks(self):
        if self.num_prg_banks == 1:
            return (0, 0)  # 16KB mirrored
        return (0, 1)


class UxROM:
    """UxROM mapper (mapper 2). Simple switchable bank at $8000.

    Write any value to $8000-$FFFF: low bits select the 16KB bank at $8000.
    Last bank is always fixed at $C000.
    Used by: Castlevania, Contra, Mega Man 1, Duck Tales.
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks
        self.prg_bank = 0

    def write(self, addr, value):
        self.prg_bank = value % self.num_prg_banks

    def get_prg_banks(self):
        return (self.prg_bank, self.num_prg_banks - 1)


class CNROM:
    """CNROM mapper (mapper 3). CHR bank switching only — PRG is fixed.

    For audio extraction, behaves identically to NROM since we don't
    emulate CHR/graphics. PRG is always fully mapped.
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks

    def write(self, addr, value):
        pass  # CHR switch only, irrelevant for audio

    def get_prg_banks(self):
        if self.num_prg_banks == 1:
            return (0, 0)
        return (0, 1)


class AxROM:
    """AxROM mapper (mapper 7). 32KB bank switching.

    Write to $8000-$FFFF: bits 0-2 select a 32KB PRG bank at $8000-$FFFF.
    Used by: Battletoads, Wizards & Warriors, Marble Madness.
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks
        self.prg_bank = 0  # 32KB bank index

    def write(self, addr, value):
        self.prg_bank = (value & 0x07) % (self.num_prg_banks // 2 or 1)

    def get_prg_banks(self):
        base = self.prg_bank * 2
        return (base, base + 1)


class MMC3:
    """MMC3 mapper (mapper 4).

    Used by SMB3, Mega Man 3-6, and many others.

    Register select: write to $8000 (even) selects which internal register (0-7)
    Register data: write to $8001 (odd) sets the selected register's value

    PRG banking (8KB granularity):
      Registers 6,7 select two switchable 8KB PRG banks.
      Bit 6 of the bank select ($8000) controls the PRG mode:
        Mode 0: $8000=R6, $A000=R7, $C000=second-to-last, $E000=last
        Mode 1: $8000=second-to-last, $A000=R7, $C000=R6, $E000=last

    Mirroring: write to $A000 (bit 0: 0=vertical, 1=horizontal)
    IRQ: $C000=latch, $C001=reload, $E000=disable, $E001=enable (ignored here)
    """

    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks
        self.num_8k_banks = num_prg_banks * 2  # 16KB banks -> 8KB banks
        self.bank_select = 0   # $8000 register
        self.registers = [0] * 8
        self.prg_mode = 0      # bit 6 of bank_select

    def write(self, addr, value):
        """Handle a write to $8000-$FFFF."""
        if addr < 0xA000:
            if addr & 1 == 0:
                # $8000: Bank select
                self.bank_select = value & 0x07
                self.prg_mode = (value >> 6) & 1
            else:
                # $8001: Bank data
                self.registers[self.bank_select] = value
        # $A000-$BFFF: mirroring (ignored)
        # $C000-$DFFF: IRQ latch/reload (ignored)
        # $E000-$FFFF: IRQ disable/enable (ignored)

    def get_prg_banks_8k(self):
        """Return 4 x 8KB bank numbers for $8000/$A000/$C000/$E000."""
        r6 = self.registers[6] % self.num_8k_banks
        r7 = self.registers[7] % self.num_8k_banks
        second_last = self.num_8k_banks - 2
        last = self.num_8k_banks - 1

        if self.prg_mode == 0:
            return (r6, r7, second_last, last)
        else:
            return (second_last, r7, r6, last)

    def get_prg_banks(self):
        """Return (bank_at_8000, bank_at_C000) — approximate for 16KB compatibility."""
        b = self.get_prg_banks_8k()
        return (b[0] // 2, b[2] // 2)


class NESMemory:
    """Memory wrapper for NES emulation with MMC1 mapper and APU capture.

    Intercepts:
    - Reads from $8000-$FFFF: returns banked PRG data
    - Writes to $8000-$FFFF: routes to MMC1 shift register
    - Writes to $4000-$4017: captured as APU register writes
    - Reads from $2002: returns $80 (VBlank flag, prevents spin loops)
    - Reads from $4016/$4017: returns controller state (simulated)
    - Writes to $2000-$2007, $4014: silently absorbed (PPU/OAM)
    """

    def __init__(self, mapper):
        self.ram = [0] * 0x10000
        self.mapper = mapper
        self.apu_writes = []  # per-frame capture
        self.capturing = False
        # Controller simulation: 8 buttons per controller
        # Order: A, B, Select, Start, Up, Down, Left, Right
        self.controller_state = 0x00  # bitmask of pressed buttons
        self._controller_shift = 0  # current read index (0-7)
        self._controller_strobe = False
        # PPU status simulation: VBlank flag toggles on read
        self._ppu_vblank = True  # set during NMI, cleared on read
        self._nmi_enabled = False  # tracks $2000 bit 7 (NMI enable)

    def _resolve_prg(self, addr):
        """Resolve a $8000-$FFFF address to a PRG ROM byte."""
        if isinstance(self.mapper, MMC3):
            # MMC3: 4 x 8KB banks
            banks = self.mapper.get_prg_banks_8k()
            slot = (addr - 0x8000) // 0x2000  # 0-3
            bank = banks[slot]
            offset = bank * 0x2000 + (addr & 0x1FFF)
            if offset < len(self.mapper.prg):
                return self.mapper.prg[offset]
            return 0
        else:
            # MMC1 / UxROM / AxROM / NROM: 2 x 16KB banks
            bank8, bankC = self.mapper.get_prg_banks()
            if addr < 0xC000:
                offset = (addr - 0x8000) + bank8 * 0x4000
            else:
                offset = (addr - 0xC000) + bankC * 0x4000
            if offset < len(self.mapper.prg):
                return self.mapper.prg[offset]
            # NROM 16KB mirror: if offset is out of range, wrap
            if isinstance(self.mapper, NROM) and self.mapper.num_prg_banks == 1:
                return self.mapper.prg[offset % len(self.mapper.prg)]
            return 0

    def __getitem__(self, key):
        if isinstance(key, int):
            if 0x8000 <= key <= 0xFFFF:
                return self._resolve_prg(key)
            if key == 0x2002:
                # Return VBlank + sprite-0 flags, then clear VBlank on read
                # (matches real NES behavior: bit 7 cleared after read)
                val = (0x80 if self._ppu_vblank else 0x00) | 0x40  # + sprite-0
                self._ppu_vblank = False
                return val
            if key == 0x4016:
                # Controller 1 read: return one button bit per read
                if self._controller_strobe:
                    return self.controller_state & 1  # A button while strobe high
                bit = (self.controller_state >> self._controller_shift) & 1
                self._controller_shift = min(self._controller_shift + 1, 7)
                return bit
            if key == 0x4017:
                return 0  # Controller 2: nothing pressed
            return self.ram[key]
        return self.ram[key]

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if 0x8000 <= key <= 0xFFFF:
                self.mapper.write(key, value)
                return
            if key == 0x2000:
                # PPU control: bit 7 = NMI enable
                self._nmi_enabled = bool(value & 0x80)
                self.ram[key] = value
                return
            if key == 0x4016:
                # Controller strobe: when written with bit 0 = 1, latch buttons
                # When cleared to 0, enable sequential reads
                if value & 1:
                    self._controller_strobe = True
                else:
                    self._controller_strobe = False
                    self._controller_shift = 0  # reset read index
                self.ram[key] = value
                return
            if self.capturing and 0x4000 <= key <= 0x4017:
                self.apu_writes.append((key, value))
            self.ram[key] = value
        else:
            self.ram[key] = value

    def __len__(self):
        return 0x10000

    def __iter__(self):
        return iter(self.ram)


def load_rom(path):
    """Load an iNES ROM and return (prg_data, num_prg_banks, mapper_num)."""
    with open(path, 'rb') as f:
        header = f.read(16)
        assert header[:4] == b'NES\x1a', "Not an iNES ROM"

        prg_banks = header[4]
        flags6 = header[6]
        flags7 = header[7]
        mapper = (flags6 >> 4) | (flags7 & 0xF0)
        has_trainer = bool(flags6 & 4)

        if has_trainer:
            f.read(512)  # skip trainer

        prg_data = f.read(prg_banks * 16384)

    return prg_data, prg_banks, mapper


def run_cpu(cpu, max_cycles=30000):
    """Run CPU until RTS sentinel or cycle limit."""
    cyc = 0
    while cyc < max_cycles:
        if cpu.pc in (0x46FF, 0x4700):
            return True
        cpu.step()
        cyc += 1
    return False


def trigger_nmi(cpu):
    """Simulate an NMI: push PC and P, jump to NMI vector."""
    # Set VBlank flag for PPU status reads during NMI handler
    if hasattr(cpu.memory, '_ppu_vblank'):
        cpu.memory._ppu_vblank = True

    # Push PCH, PCL, P
    cpu.memory.ram[0x0100 + cpu.sp] = (cpu.pc >> 8) & 0xFF
    cpu.sp = (cpu.sp - 1) & 0xFF
    cpu.memory.ram[0x0100 + cpu.sp] = cpu.pc & 0xFF
    cpu.sp = (cpu.sp - 1) & 0xFF
    cpu.memory.ram[0x0100 + cpu.sp] = cpu.p | 0x20  # push P with bit 5 set
    cpu.sp = (cpu.sp - 1) & 0xFF
    cpu.p |= 0x04  # set I flag

    # Read NMI vector from $FFFA/$FFFB
    nmi_lo = cpu.memory[0xFFFA]
    nmi_hi = cpu.memory[0xFFFB]
    cpu.pc = nmi_lo | (nmi_hi << 8)


def boot_rom(rom_path, num_frames, pokes=None, press_start_at=None, button_script=None,
             poke_at_frame=None):
    """Boot an NES ROM and capture APU writes per frame.

    Args:
        rom_path: Path to .nes ROM file
        num_frames: Number of frames (NMIs) to capture
        pokes: Optional list of (addr, value) tuples to write after boot
        press_start_at: Frame number to simulate Start button press (held for 2 frames)
        button_script: List of (frame, button_mask, duration) tuples for input automation
            Button masks: 0x01=A, 0x02=B, 0x04=Select, 0x08=Start,
                         0x10=Up, 0x20=Down, 0x40=Left, 0x80=Right
        poke_at_frame: List of (frame, addr, value) tuples for frame-timed RAM pokes.
            Applied at the START of the specified frame, before the NMI fires.

    Returns:
        List of per-frame APU write lists: [[(reg, val), ...], ...]
    """
    prg_data, num_prg_banks, mapper_num = load_rom(rom_path)
    supported = {0: 'NROM', 1: 'MMC1', 2: 'UxROM', 3: 'CNROM', 4: 'MMC3', 7: 'AxROM'}
    assert mapper_num in supported, f"Mapper {mapper_num} not supported. Supported: {supported}"

    print(f"ROM: {Path(rom_path).name}")
    print(f"PRG: {num_prg_banks} x 16KB = {num_prg_banks * 16}KB")
    print(f"Mapper: {mapper_num} (MMC1)")

    mapper_classes = {0: NROM, 1: MMC1, 2: UxROM, 3: CNROM, 4: MMC3, 7: AxROM}
    mapper = mapper_classes[mapper_num](prg_data, num_prg_banks)
    mem = NESMemory(mapper)
    cpu = MPU()
    cpu.memory = mem

    # RTS sentinel for subroutine trapping
    mem.ram[0x4700] = 0x60

    # Read RESET vector and boot
    reset_lo = cpu.memory[0xFFFC]
    reset_hi = cpu.memory[0xFFFD]
    reset_addr = reset_lo | (reset_hi << 8)
    print(f"RESET vector: ${reset_addr:04X}")

    nmi_lo = cpu.memory[0xFFFA]
    nmi_hi = cpu.memory[0xFFFB]
    nmi_addr = nmi_lo | (nmi_hi << 8)
    print(f"NMI vector: ${nmi_addr:04X}")

    # Boot: run from RESET for up to 100K cycles (init routines)
    cpu.pc = reset_addr
    cpu.sp = 0xFD
    cpu.p = 0x04  # IRQ disabled

    print("Booting...")
    boot_cycles = 0
    max_boot = 2000000
    frame_cyc = 0
    while boot_cycles < max_boot:
        op = cpu.memory[cpu.pc]
        # Stop if we hit a JMP-to-self idle loop
        if op == 0x4C:
            target = cpu.memory[cpu.pc + 1] | (cpu.memory[cpu.pc + 2] << 8)
            if target == cpu.pc:
                print(f"  Hit idle loop at ${cpu.pc:04X} after {boot_cycles} cycles")
                break
        cpu.step()
        boot_cycles += 1
        frame_cyc += 1
        # Fire NMI every frame-worth of cycles if enabled
        if frame_cyc >= 29780:
            mem._ppu_vblank = True
            frame_cyc = 0
            if hasattr(mem, '_nmi_enabled') and mem._nmi_enabled:
                trigger_nmi(cpu)

    if boot_cycles >= max_boot:
        print(f"  Boot ran {max_boot} cycles (may not have finished)")

    # Apply pokes (game state manipulation)
    if pokes:
        print(f"Applying {len(pokes)} memory pokes:")
        for addr, val in pokes:
            cpu.memory.ram[addr] = val
            print(f"  ${addr:04X} = ${val:02X}")

    # Main loop: fire NMI per frame, capture APU writes
    print(f"Capturing {num_frames} frames...")
    all_frames = []
    cycles_per_frame = 29780  # NTSC: 341*262/3 ≈ 29780.67

    for frame_num in range(num_frames):
        # Controller simulation
        mem.controller_state = 0x00
        if press_start_at is not None:
            if press_start_at <= frame_num <= press_start_at + 2:
                mem.controller_state = 0x08  # Start = bit 3
        if button_script:
            for btn_frame, btn_mask, btn_dur in button_script:
                if btn_frame <= frame_num < btn_frame + btn_dur:
                    mem.controller_state |= btn_mask

        # Frame-timed pokes: apply pokes at specific frames
        # If frame number is -1, poke EVERY frame (persistent override)
        if poke_at_frame:
            for poke_frame, poke_addr, poke_val in poke_at_frame:
                if poke_frame == -1 or frame_num == poke_frame:
                    mem.ram[poke_addr] = poke_val

        mem.apu_writes = []
        mem.capturing = True

        # Fire NMI
        trigger_nmi(cpu)

        # Run CPU for one frame's worth of cycles
        frame_cycles = 0
        while frame_cycles < cycles_per_frame:
            op = cpu.memory[cpu.pc]
            # Catch infinite loops (JMP to self)
            if op == 0x4C:
                target = cpu.memory[cpu.pc + 1] | (cpu.memory[cpu.pc + 2] << 8)
                if target == cpu.pc:
                    break
            cpu.step()
            frame_cycles += 1

        mem.capturing = False
        all_frames.append(list(mem.apu_writes))

        if frame_num % 600 == 0 and frame_num > 0:
            print(f"  Frame {frame_num}/{num_frames} ({frame_num/60.1:.1f}s)")

    return all_frames


def frames_to_mesen_csv(frames, output_path):
    """Convert per-frame APU writes to Mesen-compatible CSV.

    Output format matches what mesen_to_midi.py expects:
      frame, parameter, value

    Parameter names use Mesen's decoded format ($4000_duty, $4000_vol, etc).
    """
    # Mesen parameter mapping: APU register -> decoded parameters
    reg_decoders = {
        0x4000: lambda v: [
            ('$4000_duty', (v >> 6) & 3),
            ('$4000_const', (v >> 4) & 1),
            ('$4000_vol', v & 0x0F),
        ],
        0x4001: lambda v: [('$4001_sweep', v)],
        0x4002: lambda v: [],  # period lo — combined with $4003
        0x4003: lambda v: [],  # period hi + length — handled below
        0x4004: lambda v: [
            ('$4004_duty', (v >> 6) & 3),
            ('$4004_const', (v >> 4) & 1),
            ('$4004_vol', v & 0x0F),
        ],
        0x4005: lambda v: [('$4005_sweep', v)],
        0x4006: lambda v: [],
        0x4007: lambda v: [],
        0x4008: lambda v: [('$4008_linear', v & 0x7F)],
        0x400A: lambda v: [],
        0x400B: lambda v: [],
        0x400C: lambda v: [
            ('$400C_const', (v >> 4) & 1),
            ('$400C_vol', v & 0x0F),
        ],
        0x400E: lambda v: [
            ('$400E_period', v & 0x0F),
            ('$400E_mode', (v >> 7) & 1),
        ],
        0x400F: lambda v: [],
        0x4010: lambda v: [('$4010_rate', v)],
        0x4011: lambda v: [('$4011_dac', v)],
        0x4012: lambda v: [('$4012_addr', v)],
        0x4013: lambda v: [('$4013_len', v)],
        0x4015: lambda v: [],
    }

    # Track period state for combined period output.
    # NES APU register periods are raw 11-bit values. Mesen reports
    # decoded periods = raw * 2 + 1 (accounting for the internal timer
    # divider). We output Mesen-compatible values so mesen_to_midi.py
    # produces correct pitches.
    sq1_period_lo = 0
    sq2_period_lo = 0
    tri_period_lo = 0

    rows = []
    for frame_num, writes in enumerate(frames):
        for reg, val in writes:
            if reg == 0x4002:
                sq1_period_lo = val
            elif reg == 0x4003:
                raw_period = sq1_period_lo | ((val & 7) << 8)
                period = raw_period * 2 + 1  # convert to Mesen decoded format
                rows.append((frame_num, '$4002_period', period))
                rows.append((frame_num, '$400B_length', val))
            elif reg == 0x4006:
                sq2_period_lo = val
            elif reg == 0x4007:
                raw_period = sq2_period_lo | ((val & 7) << 8)
                period = raw_period * 2 + 1
                rows.append((frame_num, '$4006_period', period))
            elif reg == 0x400A:
                tri_period_lo = val
            elif reg == 0x400B:
                raw_period = tri_period_lo | ((val & 7) << 8)
                period = raw_period * 2 + 1
                rows.append((frame_num, '$400A_period', period))
                rows.append((frame_num, '$400B_length', val))
            elif reg in reg_decoders:
                for param, decoded_val in reg_decoders[reg](val):
                    rows.append((frame_num, param, decoded_val))

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'parameter', 'value'])
        for frame, param, value in rows:
            writer.writerow([frame, param, value])

    print(f"Saved {len(rows)} state changes across {len(frames)} frames to {output_path}")
    return rows


def main():
    parser = argparse.ArgumentParser(description='Boot NES ROM and capture APU state')
    parser.add_argument('rom', help='Path to .nes ROM file')
    parser.add_argument('-o', '--output', default='.', help='Output directory')
    parser.add_argument('--frames', type=int, default=6000, help='Number of frames to capture (default: 6000 = ~100s)')
    parser.add_argument('--poke', nargs='*', help='Memory pokes after boot: ADDR=VAL (hex), e.g. 0x3A=0 0x81=1')
    parser.add_argument('--skip-boot', type=int, default=0, help='Skip N frames before starting capture')
    parser.add_argument('--press-start', type=int, default=None,
                        help='Frame number to simulate pressing Start button')
    parser.add_argument('--poke-at', nargs='*',
                        help='Frame-timed pokes: FRAME:ADDR=VAL (e.g. 5:0x0580=3)')
    parser.add_argument('--game', default=None, help='Game name for output files')
    parser.add_argument('--song', default=None, help='Song name for output files')
    args = parser.parse_args()

    # Parse pokes
    pokes = []
    if args.poke:
        for p in args.poke:
            addr_str, val_str = p.split('=')
            addr = int(addr_str, 0)
            val = int(val_str, 0)
            pokes.append((addr, val))

    # Parse frame-timed pokes: "FRAME:ADDR=VAL" or "every:ADDR=VAL"
    poke_at_frame = []
    if args.poke_at:
        for p in args.poke_at:
            frame_str, rest = p.split(':', 1)
            addr_str, val_str = rest.split('=')
            frame = -1 if frame_str == 'every' else int(frame_str, 0)
            poke_at_frame.append((frame, int(addr_str, 0), int(val_str, 0)))

    # Boot and capture
    all_frames = boot_rom(args.rom, args.frames + args.skip_boot, pokes,
                          press_start_at=args.press_start,
                          poke_at_frame=poke_at_frame or None)

    # Skip initial frames if requested
    if args.skip_boot > 0:
        print(f"Skipping first {args.skip_boot} frames")
        all_frames = all_frames[args.skip_boot:]

    # Stats
    total_writes = sum(len(f) for f in all_frames)
    active_frames = sum(1 for f in all_frames if len(f) > 0)
    print(f"Total APU writes: {total_writes}")
    print(f"Active frames: {active_frames}/{len(all_frames)}")

    # Save CSV
    game_name = args.game or Path(args.rom).stem.replace(' ', '_')
    song_name = args.song or 'capture'
    csv_path = os.path.join(args.output, f'{game_name}_{song_name}.csv')
    frames_to_mesen_csv(all_frames, csv_path)

    # Also run mesen_to_midi if available
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mesen_to_midi import load_capture, build_pulse_track, build_triangle_track, build_noise_track, find_music_start
        import mido

        print(f"\nConverting to MIDI...")
        frames_data = load_capture(csv_path)
        music_start = find_music_start(frames_data)
        play_frames = frames_data[music_start:]
        print(f"Music starts at frame {music_start}, using {len(play_frames)} frames")

        mid = mido.MidiFile(ticks_per_beat=480)
        meta = mido.MidiTrack()
        meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(128.6)))
        meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))
        meta.append(mido.MetaMessage('text', text=f'Game: {game_name}'))
        meta.append(mido.MetaMessage('text', text=f'Song: {song_name}'))
        meta.append(mido.MetaMessage('text', text='Source: NES ROM emulation (nes_rom_capture.py)'))
        mid.tracks.append(meta)
        mid.tracks.append(build_pulse_track(play_frames, 'p1', 'Square 1 [lead]', 0, 80))
        mid.tracks.append(build_pulse_track(play_frames, 'p2', 'Square 2 [harmony]', 1, 81))
        mid.tracks.append(build_triangle_track(play_frames))
        mid.tracks.append(build_noise_track(play_frames))

        midi_path = os.path.join(args.output, f'{game_name}_{song_name}_rom_v1.mid')
        mid.save(midi_path)
        for i, t in enumerate(mid.tracks[1:], 1):
            notes = sum(1 for m in t if m.type == 'note_on')
            print(f"  Track {i}: {notes} notes")
        print(f"Saved MIDI: {midi_path}")

    except Exception as e:
        print(f"MIDI conversion skipped: {e}")


if __name__ == '__main__':
    main()
