"""Castlevania II: Simon's Quest sound driver parser (Fujio variant).

Parses music data from the CV2 ROM using the hierarchical phrase system
discovered via trace analysis on 2026-03-29.

Architecture:
  - 32-entry multi-octave period table at ROM 0x01C1D (E1-B3)
  - Phrase library at ROM 0x00B60 (30 short melodic motifs)
  - Song table at ROM 0x00CE0 (17 songs, pointer-based)
  - Notes encoded as: bits 4-0 = table index, bits 6-5 = duration class, bit 7 = flag
  - Phrase chaining via Fx commands (F0-F7 = jump to phrase x)
  - FF = end, FE = repeat (shared with Maezawa)

This is a PROTOTYPE parser. Many command meanings are hypotheses.
Unknown commands are logged, not crashed on (per FLEXIBILITYGOALS).

Usage:
    from extraction.drivers.konami.cv2_parser import CV2Parser
    parser = CV2Parser("extraction/roms/cv2.nes")
    song = parser.parse_track(0)
"""
# ---------------------------------------------------------------
# STATUS: PROTOTYPE
# SCOPE: cv2 only
# VALIDATED: not yet
# TRACE_RESULT: pending
# KNOWN_LIMITATIONS:
#   - Note encoding hypothesis (5-bit index + 2-bit dur + 1-bit flag) not confirmed via disassembly
#   - Phrase chaining (Fx) is hypothesis — may be wrong for F8-FF range
#   - Song-level data (0x20-0x3F bytes) interpretation unclear
#   - Envelope model not implemented (trace shows max vol 6, 3-frame attack)
#   - MMC1 bank switching not fully modeled (assumes all data in bank 0)
# LAYER: DATA (CV2-specific parser)
# ---------------------------------------------------------------

from __future__ import annotations

import struct
import math
from dataclasses import dataclass, field
from pathlib import Path

# Import shared types from the main parser
from extraction.drivers.konami.parser import (
    NoteEvent, RestEvent, InstrumentChange, EndMarker, RepeatMarker,
    ChannelData, ParsedSong, Event, INES_HEADER_SIZE, PITCH_NAMES,
)


# ---------------------------------------------------------------------------
# CV2 Constants
# ---------------------------------------------------------------------------

# 32-entry period table at ROM 0x01C1D
# E1(28) through B3(59), pre-computed across 2.67 octaves
PERIOD_TABLE_ROM = 0x01C1D
PERIOD_TABLE_ENTRIES = 32
PERIOD_TABLE_MIDI_BASE = 28  # E1

# Phrase library: 30 pointers at ROM 0x00B60
PHRASE_LIBRARY_ROM = 0x00B60
PHRASE_LIBRARY_COUNT = 30

# Song table: pointer at phrase library entry 30 -> ROM 0x00CE0
SONG_TABLE_ROM = 0x00CE0
SONG_TABLE_COUNT = 17  # unique songs before padding

# Duration class frame multipliers (hypothesis)
# The trace shows 10-frame notes. If base tempo is 10 and dur_class 0 = 1x:
# dur 0 = 10 frames, dur 1 = 20 frames, dur 2 = 30 frames, dur 3 = 40 frames?
# This is a guess. Will be refined against trace.
DURATION_MULTIPLIERS = [1, 2, 3, 4]
DEFAULT_TEMPO = 10  # frames per beat (from trace: 10-frame notes)


@dataclass
class UnknownCommand:
    """An unrecognized command byte. Logged, not crashed."""
    byte: int
    offset: int
    context: str = ""


@dataclass
class PhraseChain:
    """Fx command: chain to another phrase."""
    target_phrase: int
    offset: int


# Extend the event union
CV2Event = Event | UnknownCommand | PhraseChain


def cv2_cpu_to_rom(cpu_addr: int, bank: int = 0) -> int:
    """Convert CPU address to ROM offset for CV2 (MMC1, mapper 1).

    MMC1 has 16KB switchable bank at $8000-$BFFF and
    16KB fixed bank (last) at $C000-$FFFF.
    """
    if 0x8000 <= cpu_addr <= 0xBFFF:
        return INES_HEADER_SIZE + bank * 16384 + (cpu_addr - 0x8000)
    elif 0xC000 <= cpu_addr <= 0xFFFF:
        # Fixed last bank (bank 7 for 8-bank ROM)
        return INES_HEADER_SIZE + 7 * 16384 + (cpu_addr - 0xC000)
    else:
        raise ValueError(f"CPU address 0x{cpu_addr:04X} out of range")


def table_index_to_midi(index: int) -> int:
    """Convert CV2 period table index (0-31) to MIDI note number."""
    return PERIOD_TABLE_MIDI_BASE + index


class CV2Parser:
    """Prototype parser for Castlevania II: Simon's Quest."""

    def __init__(self, rom_path: str):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()

        # Validate iNES header
        if self.rom[:4] != b'NES\x1a':
            raise ValueError("Not a valid iNES ROM file")

        self.prg_banks = self.rom[4]
        mapper = (self.rom[6] >> 4) | (self.rom[7] & 0xF0)
        if mapper != 1:
            print(f"WARNING: Expected mapper 1 (MMC1), got {mapper}")

        # Load period table
        self.period_table = []
        for i in range(PERIOD_TABLE_ENTRIES):
            val = struct.unpack_from('<H', self.rom, PERIOD_TABLE_ROM + i * 2)[0]
            self.period_table.append(val)

        # Load phrase library pointers
        self.phrase_ptrs = []
        for i in range(PHRASE_LIBRARY_COUNT):
            val = struct.unpack_from('<H', self.rom, PHRASE_LIBRARY_ROM + i * 2)[0]
            self.phrase_ptrs.append(val)

        # Load song table pointers
        self.song_ptrs = []
        for i in range(SONG_TABLE_COUNT):
            val = struct.unpack_from('<H', self.rom, SONG_TABLE_ROM + i * 2)[0]
            self.song_ptrs.append(val)

        # Parse stats
        self.unknown_commands = []

    def _read_phrase(self, phrase_index: int, max_depth: int = 8) -> list[CV2Event]:
        """Read a phrase from the phrase library, following chains.

        max_depth prevents infinite loops from circular chains.
        """
        if phrase_index >= PHRASE_LIBRARY_COUNT or max_depth <= 0:
            return []

        cpu_addr = self.phrase_ptrs[phrase_index]
        rom_offset = cv2_cpu_to_rom(cpu_addr, bank=0)

        events = []
        pos = rom_offset
        tempo = DEFAULT_TEMPO

        while pos < len(self.rom):
            b = self.rom[pos]

            if b == 0xFF:
                # End marker
                events.append(EndMarker(offset=pos))
                break

            elif b == 0xFE:
                # Repeat marker (FE xx)
                if pos + 1 < len(self.rom):
                    count = self.rom[pos + 1]
                    events.append(RepeatMarker(
                        count=count,
                        target_cpu=cpu_addr,
                        target_rom=rom_offset,
                        offset=pos,
                    ))
                    pos += 2
                else:
                    pos += 1

            elif b == 0xFB:
                # Parameter prefix (FB xx) — instrument/volume/tempo change
                if pos + 1 < len(self.rom):
                    param = self.rom[pos + 1]
                    # Log as unknown for now — we don't know what FB does yet
                    events.append(UnknownCommand(
                        byte=b, offset=pos,
                        context=f"FB {param:02X} (parameter prefix)"
                    ))
                    pos += 2
                else:
                    pos += 1

            elif 0xF0 <= b <= 0xF7:
                # Phrase chain: Fx = chain to phrase x
                target = b & 0x07
                events.append(PhraseChain(target_phrase=target, offset=pos))
                # Follow the chain
                chain_events = self._read_phrase(target, max_depth - 1)
                events.extend(chain_events)
                pos += 1
                # After a chain, the current phrase ends
                break

            elif b == 0xC0:
                # Rest (hypothesis)
                events.append(RestEvent(
                    duration_nibble=0,
                    duration_frames=tempo,
                    offset=pos,
                ))
                pos += 1

            elif b >= 0x80:
                # High-bit note (long/tied/modified)
                index = b & 0x1F
                dur_class = (b >> 5) & 0x03
                if index < PERIOD_TABLE_ENTRIES:
                    midi = table_index_to_midi(index)
                    pitch = index % 12
                    octave = 4 - (index // 12)  # map to Maezawa octave convention
                    frames = tempo * DURATION_MULTIPLIERS[dur_class]
                    events.append(NoteEvent(
                        pitch=pitch,
                        octave=octave,
                        duration_nibble=dur_class,
                        duration_frames=frames * 2,  # 0x80 flag = double duration (hypothesis)
                        midi_note=midi,
                        offset=pos,
                    ))
                else:
                    events.append(UnknownCommand(byte=b, offset=pos,
                        context=f"high-bit byte, index {index} out of range"))
                pos += 1

            else:
                # Standard note byte
                index = b & 0x1F
                dur_class = (b >> 5) & 0x03
                if index < PERIOD_TABLE_ENTRIES:
                    midi = table_index_to_midi(index)
                    pitch = index % 12
                    octave = 4 - (index // 12)
                    frames = tempo * DURATION_MULTIPLIERS[dur_class]
                    events.append(NoteEvent(
                        pitch=pitch,
                        octave=octave,
                        duration_nibble=dur_class,
                        duration_frames=frames,
                        midi_note=midi,
                        offset=pos,
                    ))
                else:
                    events.append(UnknownCommand(byte=b, offset=pos,
                        context=f"note byte, index {index} >= {PERIOD_TABLE_ENTRIES}"))
                pos += 1

        return events

    def parse_bloody_tears_bass(self) -> ParsedSong:
        """Parse the Bloody Tears bass line from known phrase chains.

        This is a targeted extraction using the phrases identified
        in the trace analysis: phrases 19, 5, 6, 20 contain the
        chromatic ascending bass pattern.
        """
        # Build the full bass by reading phrase 20 (which chains through 6, 5, etc.)
        events = []

        # Phrase 20 is the most complete bass entry point:
        # 14 16 17 F6 F5 F5 F4 F4 F4 F3 F2
        # = C3 D3 D#3, then chain through phrases 6,5,5,4,4,4,3,2
        events = self._read_phrase(20)

        channel = ChannelData(
            name="Square 1",
            channel_type="pulse1",
            events=events,
            start_offset=PHRASE_LIBRARY_ROM + 20 * 2,
            start_cpu=self.phrase_ptrs[20] if 20 < len(self.phrase_ptrs) else 0,
        )

        song = ParsedSong(
            track_number=2,  # Bloody Tears
            channels=[channel],
        )

        return song

    def parse_all_phrases(self) -> dict[int, list[CV2Event]]:
        """Parse all 30 phrases from the library. Returns dict of phrase_index -> events."""
        result = {}
        for i in range(PHRASE_LIBRARY_COUNT):
            result[i] = self._read_phrase(i, max_depth=4)
        return result

    def get_period(self, index: int) -> int:
        """Get the NES period value for a table index."""
        if 0 <= index < len(self.period_table):
            return self.period_table[index]
        return 0

    def report(self) -> str:
        """Generate a human-readable report of what was parsed."""
        lines = [
            "=== CV2 Parser Report ===",
            f"ROM: {self.prg_banks} PRG banks, mapper 1 (MMC1)",
            f"Period table: {PERIOD_TABLE_ENTRIES} entries at ROM 0x{PERIOD_TABLE_ROM:05X}",
            f"Phrase library: {PHRASE_LIBRARY_COUNT} phrases at ROM 0x{PHRASE_LIBRARY_ROM:05X}",
            f"Song table: {SONG_TABLE_COUNT} songs at ROM 0x{SONG_TABLE_ROM:05X}",
            "",
        ]

        # Parse all phrases and summarize
        phrases = self.parse_all_phrases()
        for i, events in phrases.items():
            notes = [e for e in events if isinstance(e, NoteEvent)]
            unknowns = [e for e in events if isinstance(e, UnknownCommand)]
            chains = [e for e in events if isinstance(e, PhraseChain)]
            note_names = [f"{PITCH_NAMES[n.pitch]}{4-n.octave}" for n in notes[:8]]
            line = f"  Phrase {i:2d}: {len(notes):2d} notes, {len(chains)} chains, {len(unknowns)} unknown"
            if note_names:
                line += f"  [{' '.join(note_names)}]"
            lines.append(line)

        if self.unknown_commands:
            lines.append(f"\nUnknown commands: {len(self.unknown_commands)}")
            for uc in self.unknown_commands[:10]:
                lines.append(f"  0x{uc.offset:05X}: {uc.byte:02X} — {uc.context}")

        return '\n'.join(lines)


if __name__ == '__main__':
    import sys

    rom_path = sys.argv[1] if len(sys.argv) > 1 else "extraction/roms/cv2.nes"
    parser = CV2Parser(rom_path)

    # Print report
    print(parser.report())

    print("\n=== Bloody Tears Bass (Phrase Chain) ===")
    song = parser.parse_bloody_tears_bass()
    for ch in song.channels:
        print(f"\n{ch.name}:")
        for ev in ch.events:
            if isinstance(ev, NoteEvent):
                name = PITCH_NAMES[ev.pitch]
                print(f"  {name}{4-ev.octave} (MIDI {ev.midi_note}) - {ev.duration_frames} frames")
            elif isinstance(ev, RestEvent):
                print(f"  REST - {ev.duration_frames} frames")
            elif isinstance(ev, PhraseChain):
                print(f"  -> Chain to phrase {ev.target_phrase}")
            elif isinstance(ev, UnknownCommand):
                print(f"  ?? {ev.byte:02X} ({ev.context})")
            elif isinstance(ev, EndMarker):
                print(f"  END")
