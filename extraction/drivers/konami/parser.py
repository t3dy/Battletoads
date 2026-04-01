"""Konami pre-VRC sound driver parser (Maezawa variant).

Parses music data from Castlevania (U) and related Konami NES ROMs.
Decodes note commands, instruments, drums, repeats, and produces
structured channel data suitable for MIDI export.

Usage:
    from extraction.drivers.konami.parser import KonamiCV1Parser

    parser = KonamiCV1Parser("path/to/Castlevania (U).nes")
    song = parser.parse_track(2)  # Track 2 = Vampire Killer
    for ch in song.channels:
        print(ch.name, len(ch.events), "events")
"""
# ---------------------------------------------------------------
# STATUS: VERIFIED (CV1)
# SCOPE: cv1 + shared event types used by contra_parser
# VALIDATED: 2026-03-28
# TRACE_RESULT: 0 pitch, 0 volume, 0 sounding mismatches (CV1 pulse, 1792 frames)
# KNOWN_LIMITATIONS:
#   - pitch_to_midi uses BASE_MIDI_OCTAVE4=36, CV1-specific
#   - E5-E7 treated as invalid (may be valid in other games)
#   - Pointer table layout hardcoded for CV1 (9-byte entries, 15 tracks)
# LAYER: mixed (shared types + CV1-specific parser)
# ---------------------------------------------------------------

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NoteEvent:
    """A single note in the parsed output.

    INVARIANT: duration_frames MUST be the full hardware duration
    (tempo * (nibble + 1)). Parsers must NOT shorten notes for
    staccato/envelope effects. ALL temporal volume shaping is the
    frame IR's responsibility, dispatched via DriverCapability.
    """
    pitch: int          # 0-11 (C=0 through B=11)
    octave: int         # 0-4 (E0=0 highest, E4=4 lowest)
    duration_nibble: int  # 0-15
    duration_frames: int  # actual frames = tempo * (nibble + 1)
    midi_note: int      # computed MIDI note number
    offset: int         # byte offset in ROM where this note was found


@dataclass
class RestEvent:
    """A rest (silence) in the parsed output."""
    duration_nibble: int
    duration_frames: int
    offset: int


@dataclass
class InstrumentChange:
    """An instrument/tempo change (DX II FF sequence)."""
    tempo: int          # low nibble of DX command (1-15)
    raw_instrument: int  # APU register 0 value (DDLCVVVV)
    duty_cycle: int     # 0-3
    volume: int         # 0-15
    length_halt: int    # 0-1
    constant_vol: int   # 0-1
    fade_start: int     # high nibble of FF byte (0 if triangle)
    fade_step: int      # low nibble of FF byte (0 if triangle)
    has_sweep: bool     # whether F0 SS follows
    sweep_value: int    # sweep register value (0 if no sweep)
    offset: int
    vol_env_index: int = -1      # Contra: envelope table index (-1 = use parametric)
    decrescendo_mul: int = 0     # Contra: 3rd DX byte low nibble
    vol_duration: int = 15       # Contra: auto-decrescendo frame limit (low nibble of vol_env byte)


@dataclass
class DrumEvent:
    """A drum trigger (E9 or EA)."""
    drum_type: str      # "snare" or "hihat"
    duration_frames: int  # from preceding note
    offset: int


@dataclass
class RepeatMarker:
    """A repeat/loop command (FE XX YYYY)."""
    count: int          # repeat count ($FF = infinite)
    target_cpu: int     # CPU address to loop to
    target_rom: int     # ROM file offset
    offset: int


@dataclass
class SubroutineCall:
    """A subroutine jump (FD XX YY)."""
    target_cpu: int
    target_rom: int
    offset: int


@dataclass
class EndMarker:
    """End of channel ($FF)."""
    offset: int


@dataclass
class EnvelopeEnable:
    """E8 command — enable volume fade."""
    offset: int


@dataclass
class OctaveChange:
    """E0-E4 command — set octave."""
    octave: int
    offset: int


# Union type for all events
Event = (NoteEvent | RestEvent | InstrumentChange | DrumEvent |
         RepeatMarker | SubroutineCall | EndMarker | EnvelopeEnable |
         OctaveChange)


@dataclass
class ChannelData:
    """Parsed data for one channel of a song."""
    name: str           # "Square 1", "Square 2", "Triangle"
    channel_type: str   # "pulse1", "pulse2", "triangle"
    events: list[Event] = field(default_factory=list)
    start_offset: int = 0  # ROM offset where channel data begins
    start_cpu: int = 0     # CPU address


@dataclass
class ParsedSong:
    """Complete parsed song with all channels."""
    track_number: int
    channels: list[ChannelData] = field(default_factory=list)
    instruments: list[InstrumentChange] = field(default_factory=list)

    def validate_full_duration(self) -> list[str]:
        """Check that notes have full hardware durations.

        Returns list of violations. Empty = all notes are full-duration.
        This enforces the invariant that parsers emit raw durations and
        the IR handles all temporal shaping (volume envelopes, staccato).
        """
        violations = []
        for ch in self.channels:
            tempo = 7  # default
            for ev in ch.events:
                if isinstance(ev, InstrumentChange):
                    tempo = ev.tempo
                elif isinstance(ev, NoteEvent):
                    expected = tempo * (ev.duration_nibble + 1)
                    if ev.duration_frames != expected:
                        violations.append(
                            f"{ch.name} offset 0x{ev.offset:X}: "
                            f"duration={ev.duration_frames} != "
                            f"tempo*nibble={expected}"
                        )
        return violations


# ---------------------------------------------------------------------------
# Note period table (from ROM at $079A)
# ---------------------------------------------------------------------------

PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Base MIDI notes at octave 4 (E4 = lowest, C2)
# Contra disassembly: base period 1017 = A2 (109.9 Hz), MIDI 45
# pitch_to_midi(9, 4) = 36 + 9 + 0 = 45 (A2) ✓
# At E2 (2 shifts): A4 (MIDI 69) — confirmed by ear against game
# The APU trace period 511 maps to 218 Hz via hardware formula,
# but the correct MIDI mapping is one octave higher (A4 not A3).
BASE_MIDI_OCTAVE4 = 36  # C2


def pitch_to_midi(pitch: int, octave: int, is_triangle: bool = False) -> int:
    """Convert CV1 pitch + octave to MIDI note number.

    pitch: 0-11 (C through B)
    octave: 0-4 (E0=highest through E4=lowest)
    is_triangle: True for triangle channel (plays 1 octave lower than
        pulse for the same period, because the APU triangle uses a
        32-step sequencer vs 16 for pulse)
    """
    # Clamp octave to 0-4 range (values > 4 come from misinterpreted
    # E-series commands like EC/ED which are pitch adjust, not octave)
    oct_clamped = max(0, min(4, octave))
    midi = BASE_MIDI_OCTAVE4 + pitch + (4 - oct_clamped) * 12
    if is_triangle:
        midi -= 12
    return midi


# ---------------------------------------------------------------------------
# ROM utilities
# ---------------------------------------------------------------------------

INES_HEADER_SIZE = 16


def cpu_to_rom(cpu_addr: int) -> int:
    """Convert NES CPU address to ROM file offset."""
    return cpu_addr - 0x8000 + INES_HEADER_SIZE


def rom_to_cpu(rom_offset: int) -> int:
    """Convert ROM file offset to NES CPU address."""
    return rom_offset + 0x8000 - INES_HEADER_SIZE


def read_ptr_le(data: bytes, offset: int) -> int:
    """Read a 16-bit little-endian pointer."""
    return struct.unpack_from('<H', data, offset)[0]


# ---------------------------------------------------------------------------
# Pointer table
# ---------------------------------------------------------------------------

# Master pointer table starts at ROM offset $0825
# Each track has 3 pointers (Sq1, Sq2, Tri) at 3-byte intervals
# 9 bytes per track: ptr1(2) + gap(1) + ptr2(2) + gap(1) + ptr3(2) + gap(1)
# Actually: examining the ROM, the pointers are packed as:
# offset+0: Sq1 ptr (2 bytes LE)
# offset+2: separator byte
# offset+3: Sq2 ptr (2 bytes LE)
# offset+5: separator byte
# offset+6: Tri ptr (2 bytes LE)
# offset+8: separator byte
# Total: 9 bytes per track

POINTER_TABLE_ROM_OFFSET = 0x0825
TRACK_ENTRY_SIZE = 9
NUM_TRACKS = 15


def read_track_pointers(rom: bytes, track_num: int) -> tuple[int, int, int]:
    """Read the 3 channel CPU addresses for a track (1-indexed).

    Returns (sq1_cpu, sq2_cpu, tri_cpu).
    """
    if track_num < 1 or track_num > NUM_TRACKS:
        raise ValueError(f"Track number must be 1-{NUM_TRACKS}, got {track_num}")

    base = POINTER_TABLE_ROM_OFFSET + (track_num - 1) * TRACK_ENTRY_SIZE
    sq1 = read_ptr_le(rom, base)
    sq2 = read_ptr_le(rom, base + 3)
    tri = read_ptr_le(rom, base + 6)
    return sq1, sq2, tri


# ---------------------------------------------------------------------------
# Channel parser
# ---------------------------------------------------------------------------

class ChannelParser:
    """Parses a single channel's command stream from ROM data."""

    def __init__(self, rom: bytes, start_cpu: int, channel_type: str):
        self.rom = rom
        self.start_cpu = start_cpu
        self.start_rom = cpu_to_rom(start_cpu)
        self.channel_type = channel_type  # "pulse1", "pulse2", "triangle"
        self.is_triangle = channel_type == "triangle"

        # State
        self.pos = self.start_rom
        self.octave = 2  # default octave E2 (middle)
        self.tempo = 7   # default tempo
        self.envelope_enabled = False
        self.events: list[Event] = []
        self.return_stack: list[int] = []
        self.repeat_counters: dict[int, int] = {}  # rom_offset -> remaining count

        # Safety limits
        self.max_events = 5000
        self.max_bytes = 8000

    def parse(self) -> list[Event]:
        """Parse the entire channel data stream. Returns list of events."""
        bytes_read = 0

        while len(self.events) < self.max_events and bytes_read < self.max_bytes:
            if self.pos >= len(self.rom):
                break

            byte = self.rom[self.pos]
            offset = self.pos
            hi = (byte >> 4) & 0xF
            lo = byte & 0xF

            if hi <= 0xB:
                # Note command
                dur_frames = self.tempo * (lo + 1)
                midi = pitch_to_midi(hi, self.octave, self.is_triangle)
                self.events.append(NoteEvent(
                    pitch=hi, octave=self.octave,
                    duration_nibble=lo, duration_frames=dur_frames,
                    midi_note=midi, offset=offset,
                ))
                self.pos += 1

                # Check for drum trigger following the note
                if self.pos < len(self.rom):
                    next_byte = self.rom[self.pos]
                    if next_byte == 0xE9:
                        self.events.append(DrumEvent("snare", dur_frames, self.pos))
                        self.pos += 1
                    elif next_byte == 0xEA:
                        self.events.append(DrumEvent("hihat", dur_frames, self.pos))
                        self.pos += 1

            elif hi == 0xC:
                # Rest
                dur_frames = self.tempo * (lo + 1)
                self.events.append(RestEvent(lo, dur_frames, offset))
                self.pos += 1

            elif hi == 0xD:
                # Tempo + instrument
                self._parse_instrument(offset, lo)

            elif hi == 0xE:
                self._parse_e_command(byte, offset)

            elif hi == 0xF:
                should_stop = self._parse_f_command(byte, offset)
                if should_stop:
                    break

            else:
                self.pos += 1

            bytes_read = self.pos - self.start_rom

        return self.events

    def _parse_instrument(self, offset: int, tempo_val: int):
        """Parse DX II [FF] [F0 SS] instrument sequence."""
        self.tempo = tempo_val
        self.pos += 1

        if self.pos >= len(self.rom):
            return

        # Read instrument byte
        inst_byte = self.rom[self.pos]
        self.pos += 1

        duty = (inst_byte >> 6) & 3
        lh = (inst_byte >> 5) & 1
        cv = (inst_byte >> 4) & 1
        vol = inst_byte & 0xF

        fade_start = 0
        fade_step = 0
        has_sweep = False
        sweep_val = 0

        # Read fade parameters (pulse channels only)
        if not self.is_triangle and self.pos < len(self.rom):
            fade_byte = self.rom[self.pos]
            # Heuristic: if the next byte looks like a valid fade parameter
            # (not a note, not a control command we'd expect here)
            # The fade byte should be consumed.
            # From disassembly: triangle skips this, pulse always reads it.
            fade_start = (fade_byte >> 4) & 0xF
            fade_step = fade_byte & 0xF
            self.pos += 1

            # Check for optional F0 sweep
            if self.pos < len(self.rom) and self.rom[self.pos] == 0xF0:
                self.pos += 1
                if self.pos < len(self.rom):
                    sweep_val = self.rom[self.pos]
                    has_sweep = True
                    self.pos += 1

        inst = InstrumentChange(
            tempo=tempo_val, raw_instrument=inst_byte,
            duty_cycle=duty, volume=vol,
            length_halt=lh, constant_vol=cv,
            fade_start=fade_start, fade_step=fade_step,
            has_sweep=has_sweep, sweep_value=sweep_val,
            offset=offset,
        )
        self.events.append(inst)

    def _parse_e_command(self, byte: int, offset: int):
        """Parse E-series commands."""
        lo = byte & 0xF

        if byte == 0xE8:
            self.envelope_enabled = True
            self.events.append(EnvelopeEnable(offset))
            self.pos += 1
        elif byte == 0xE9:
            # Standalone drum (shouldn't happen without preceding note, but handle it)
            self.events.append(DrumEvent("snare", self.tempo, offset))
            self.pos += 1
        elif byte == 0xEA:
            self.events.append(DrumEvent("hihat", self.tempo, offset))
            self.pos += 1
        elif lo <= 4:
            self.octave = lo
            self.events.append(OctaveChange(lo, offset))
            self.pos += 1
        else:
            # E5-E7, EB-EF: treat as octave set (effectively silent)
            self.octave = lo
            self.events.append(OctaveChange(lo, offset))
            self.pos += 1

    def _parse_f_command(self, byte: int, offset: int) -> bool:
        """Parse F-series control commands. Returns True if should stop."""
        if byte == 0xFD:
            # Subroutine call
            if self.pos + 2 < len(self.rom):
                ptr = read_ptr_le(self.rom, self.pos + 1)
                self.events.append(SubroutineCall(ptr, cpu_to_rom(ptr), offset))
                # Save return position and jump
                self.return_stack.append(self.pos + 3)
                self.pos = cpu_to_rom(ptr)
            else:
                self.pos += 3
            return False

        elif byte == 0xFE:
            # Repeat: FE count ptr_lo ptr_hi
            if self.pos + 3 < len(self.rom):
                count = self.rom[self.pos + 1]
                ptr = read_ptr_le(self.rom, self.pos + 2)
                target_rom = cpu_to_rom(ptr)

                # Infinite loop = end of song
                if count == 0xFF:
                    self.events.append(RepeatMarker(count, ptr, target_rom, offset))
                    self.pos += 4
                    return True

                # Finite repeat semantics (from disassembly _loc_0352):
                # Driver has counter at $06,x starting at 0.
                # Each FE hit: counter++, compare with count byte.
                # counter == count -> done (skip past FE)
                # counter < count -> loop back
                #
                # count=2: pass1 (0->1,loop), pass2 (1->2,done) = 2 passes, 1 loop-back
                # count=3: 3 passes, 2 loop-backs
                # count=N: N passes, N-1 loop-backs
                #
                # Parser first encounters FE at end of pass 1.
                # Need (count-1) total loop-backs. First encounter does 1,
                # so (count-2) more needed after that.
                if offset not in self.repeat_counters:
                    self.repeat_counters[offset] = max(0, count - 2)
                    self.events.append(RepeatMarker(count, ptr, target_rom, offset))
                    if count >= 2:
                        self.pos = target_rom  # loop back (loop-back #1)
                    else:
                        # count=1: 1 pass total, 0 loop-backs. Skip past.
                        del self.repeat_counters[offset]
                        self.pos += 4
                else:
                    remaining = self.repeat_counters[offset]
                    if remaining > 0:
                        self.repeat_counters[offset] = remaining - 1
                        self.pos = target_rom
                    else:
                        del self.repeat_counters[offset]
                        self.pos += 4
            else:
                self.pos += 4
            return False

        elif byte == 0xFF:
            # End or return from subroutine
            if self.return_stack:
                self.pos = self.return_stack.pop()
                return False
            else:
                self.events.append(EndMarker(offset))
                return True

        else:
            # Unknown F command — skip
            self.pos += 1
            return False


# ---------------------------------------------------------------------------
# Song parser
# ---------------------------------------------------------------------------

CHANNEL_NAMES = {
    "pulse1": "Square 1",
    "pulse2": "Square 2",
    "triangle": "Triangle",
}


class KonamiCV1Parser:
    """High-level parser for Castlevania 1 NES music."""

    def __init__(self, rom_path: str | Path):
        self.rom_path = Path(rom_path)
        with open(self.rom_path, 'rb') as f:
            self.rom = f.read()

        # Validate iNES header
        if self.rom[:4] != b'NES\x1a':
            raise ValueError(f"Not a valid NES ROM: {self.rom_path}")

    def list_tracks(self) -> list[dict]:
        """List all available tracks with their pointer addresses."""
        tracks = []
        for i in range(1, NUM_TRACKS + 1):
            sq1, sq2, tri = read_track_pointers(self.rom, i)
            tracks.append({
                "track": i,
                "sq1_cpu": f"${sq1:04X}",
                "sq2_cpu": f"${sq2:04X}",
                "tri_cpu": f"${tri:04X}",
            })
        return tracks

    def parse_track(self, track_num: int) -> ParsedSong:
        """Parse all 3 channels of a track."""
        sq1_cpu, sq2_cpu, tri_cpu = read_track_pointers(self.rom, track_num)

        song = ParsedSong(track_number=track_num)

        for cpu_addr, ch_type in [(sq1_cpu, "pulse1"),
                                   (sq2_cpu, "pulse2"),
                                   (tri_cpu, "triangle")]:
            parser = ChannelParser(self.rom, cpu_addr, ch_type)
            events = parser.parse()

            channel = ChannelData(
                name=CHANNEL_NAMES[ch_type],
                channel_type=ch_type,
                events=events,
                start_offset=cpu_to_rom(cpu_addr),
                start_cpu=cpu_addr,
            )
            song.channels.append(channel)

        # Collect all instrument changes
        for ch in song.channels:
            for ev in ch.events:
                if isinstance(ev, InstrumentChange):
                    song.instruments.append(ev)

        return song

    def parse_channel(self, track_num: int, channel: str) -> ChannelData:
        """Parse a single channel of a track.

        channel: "pulse1", "pulse2", or "triangle"
        """
        sq1_cpu, sq2_cpu, tri_cpu = read_track_pointers(self.rom, track_num)
        cpu_map = {"pulse1": sq1_cpu, "pulse2": sq2_cpu, "triangle": tri_cpu}

        if channel not in cpu_map:
            raise ValueError(f"Unknown channel: {channel}")

        cpu_addr = cpu_map[channel]
        parser = ChannelParser(self.rom, cpu_addr, channel)
        events = parser.parse()

        return ChannelData(
            name=CHANNEL_NAMES[channel],
            channel_type=channel,
            events=events,
            start_offset=cpu_to_rom(cpu_addr),
            start_cpu=cpu_addr,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Parse a track and print the events."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parser.py <rom_path> [track_num]")
        print("  track_num defaults to 2 (Vampire Killer)")
        sys.exit(1)

    rom_path = sys.argv[1]
    track_num = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    parser = KonamiCV1Parser(rom_path)

    print(f"=== All Tracks ===")
    for t in parser.list_tracks():
        print(f"  Track {t['track']:2d}: Sq1={t['sq1_cpu']} Sq2={t['sq2_cpu']} Tri={t['tri_cpu']}")

    print(f"\n=== Parsing Track {track_num} ===\n")
    song = parser.parse_track(track_num)

    for ch in song.channels:
        notes = sum(1 for e in ch.events if isinstance(e, NoteEvent))
        rests = sum(1 for e in ch.events if isinstance(e, RestEvent))
        drums = sum(1 for e in ch.events if isinstance(e, DrumEvent))
        instruments = sum(1 for e in ch.events if isinstance(e, InstrumentChange))
        total_frames = sum(
            e.duration_frames for e in ch.events
            if isinstance(e, (NoteEvent, RestEvent))
        )

        print(f"--- {ch.name} (CPU ${ch.start_cpu:04X}) ---")
        print(f"  Events: {len(ch.events)} total ({notes} notes, {rests} rests, "
              f"{drums} drums, {instruments} instruments)")
        print(f"  Duration: {total_frames} frames ({total_frames/60:.1f} sec)")

        # Print first 30 events
        for i, ev in enumerate(ch.events[:30]):
            if isinstance(ev, NoteEvent):
                name = PITCH_NAMES[ev.pitch]
                oct_label = 6 - ev.octave  # E0=oct6, E4=oct2
                print(f"  [{i:3d}] NOTE {name}{oct_label} "
                      f"dur={ev.duration_nibble} ({ev.duration_frames}f) "
                      f"MIDI={ev.midi_note}")
            elif isinstance(ev, RestEvent):
                print(f"  [{i:3d}] REST dur={ev.duration_nibble} ({ev.duration_frames}f)")
            elif isinstance(ev, InstrumentChange):
                duty_pct = ['12.5%', '25%', '50%', '75%'][ev.duty_cycle]
                print(f"  [{i:3d}] INSTRUMENT tempo={ev.tempo} duty={duty_pct} "
                      f"vol={ev.volume} fade={ev.fade_start}/{ev.fade_step}")
            elif isinstance(ev, DrumEvent):
                print(f"  [{i:3d}] DRUM {ev.drum_type} ({ev.duration_frames}f)")
            elif isinstance(ev, OctaveChange):
                print(f"  [{i:3d}] OCTAVE E{ev.octave}")
            elif isinstance(ev, EnvelopeEnable):
                print(f"  [{i:3d}] ENVELOPE ON")
            elif isinstance(ev, RepeatMarker):
                inf = " (infinite)" if ev.count == 0xFF else ""
                print(f"  [{i:3d}] REPEAT x{ev.count}{inf} -> ${ev.target_cpu:04X}")
            elif isinstance(ev, SubroutineCall):
                print(f"  [{i:3d}] CALL ${ev.target_cpu:04X}")
            elif isinstance(ev, EndMarker):
                print(f"  [{i:3d}] END")

        if len(ch.events) > 30:
            print(f"  ... ({len(ch.events) - 30} more events)")
        print()


if __name__ == "__main__":
    main()
