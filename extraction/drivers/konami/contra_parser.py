"""Contra-specific Konami Maezawa driver parser.

Contra uses the same driver family as CV1 but with different command
semantics for the DX instrument setup, $C0 mute, and percussion.

Key differences from CV1:
- DX ($D0-$DF): reads 3 additional bytes for pulse, 1 for triangle
- $C0-$CF: mute command (no duration), not rest
- Slot 3 (noise/dmc): separate percussion parser using DMC samples
- Volume envelopes: lookup table driven, not parametric fade

Usage:
    from extraction.drivers.konami.contra_parser import ContraParser

    parser = ContraParser("Contra.nes")
    song = parser.parse_track("jungle")
"""
# ---------------------------------------------------------------
# STATUS: IN_PROGRESS
# SCOPE: contra
# VALIDATED: 2026-03-28
# TRACE_RESULT: 0 real pitch mismatches, 96.6% volume match (Jungle pulse, 2976 frames)
# KNOWN_LIMITATIONS:
#   - EB vibrato parameters skipped (not implemented)
#   - Auto-decrescendo PULSE_VOL_DURATION model is approximate
#   - UNKNOWN_SOUND_01 subtraction not modeled
# LAYER: data (Contra-specific command semantics)
# ---------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from extraction.drivers.konami.parser import (
    ParsedSong, ChannelData, NoteEvent, RestEvent, InstrumentChange,
    DrumEvent, OctaveChange, EnvelopeEnable, RepeatMarker,
    SubroutineCall, EndMarker, Event,
    CHANNEL_NAMES, PITCH_NAMES, pitch_to_midi, read_ptr_le,
    INES_HEADER_SIZE,
)


# Contra: mapper 2 (UNROM), 8 banks x 16KB
# Sound engine and all music data live in bank 1
BANK_SIZE = 16384
SOUND_BANK = 1
NUM_PRG_BANKS = 8


def contra_cpu_to_rom(cpu_addr: int) -> int:
    """Convert Contra CPU address to ROM offset (bank 1 at $8000)."""
    if 0x8000 <= cpu_addr <= 0xBFFF:
        return INES_HEADER_SIZE + SOUND_BANK * BANK_SIZE + (cpu_addr - 0x8000)
    elif 0xC000 <= cpu_addr <= 0xFFFF:
        return INES_HEADER_SIZE + (NUM_PRG_BANKS - 1) * BANK_SIZE + (cpu_addr - 0xC000)
    raise ValueError(f"Invalid CPU address: ${cpu_addr:04X}")


# Music track addresses from annotated disassembly
# Each tuple: (name, sq1_cpu, sq2_cpu, tri_cpu, noise_cpu)
CONTRA_TRACKS = {
    "title":       ("Title",                0x9195, 0x91AB, 0x91C3, 0x91D3),
    "jungle":      ("Jungle (Level 1 & 7)", 0x9428, 0x924E, 0x95C7, 0x9775),
    "waterfall":   ("Waterfall (Level 3)",  0x9985, 0x9A71, 0x9B67, 0x9BCE),
    "snowfield":   ("Snow Field (Level 5)", 0x9CA4, 0x9D32, 0x9D9A, 0x9E1E),
    "energy":      ("Energy Zone (Level 6)",0x9EA8, 0x9F46, 0x9FB8, 0xA003),
    "lair":        ("Alien's Lair (Lvl 8)", 0xA092, 0xA1A7, 0xA295, 0xA32F),
    "base":        ("Base (Levels 2 & 4)",  0xA468, 0xA570, 0xA5EB, 0xA67A),
    "boss":        ("Boss",                 0xA793, 0xA878, 0xA8FB, 0xAA0E),
    "stageclear":  ("Stage Clear",          0xAA92, 0xAAB3, 0xAAD4, 0xAAEF),
    "ending":      ("Ending",               0xAC9F, 0xAD1A, 0xAE05, 0xAE87),
    "gameover":    ("Game Over",            0xAB34, 0xAB5C, 0xAB86, 0xABB2),
}


def extract_envelope_tables(rom: bytes) -> list[list[int]]:
    """Extract all 54 pulse volume envelope tables from the ROM.

    Returns a list of 54 envelopes, each a list of per-frame volume values.
    The $FF terminator is NOT included in the returned data.
    """
    ptr_tbl_rom = INES_HEADER_SIZE + SOUND_BANK * BANK_SIZE + 1  # CPU $8001
    TOTAL_ENTRIES = 54  # 8*6 levels + 6 for level 7

    tables = []
    for i in range(TOTAL_ENTRIES):
        off = ptr_tbl_rom + i * 2
        cpu_addr = rom[off] | (rom[off + 1] << 8)
        rom_off = contra_cpu_to_rom(cpu_addr)

        envelope = []
        pos = rom_off
        while pos < len(rom) and rom[pos] != 0xFF and len(envelope) < 64:
            envelope.append(rom[pos] & 0x1F)  # low 5 bits = volume
            pos += 1
        tables.append(envelope)

    return tables


class ContraChannelParser:
    """Parses a single Contra channel's high-sound command stream."""

    def __init__(self, rom: bytes, start_cpu: int, channel_type: str):
        self.rom = rom
        self.start_cpu = start_cpu
        self.start_rom = contra_cpu_to_rom(start_cpu)
        self.channel_type = channel_type
        self.is_triangle = channel_type == "triangle"
        self.is_noise = channel_type == "noise"

        # State
        self.pos = self.start_rom
        self.octave = 2
        self.tempo = 7  # SOUND_LENGTH_MULTIPLIER
        self.decrescendo_mul = 0  # UNKNOWN_SOUND_00 — controls note end silence
        self.vol_env_index = -1   # current envelope table index (-1 = auto decrescendo)
        self.pitch_adj = 0        # EC command: semitone offset into period table
        self.events: list[Event] = []
        self.return_stack: list[int] = []
        self.repeat_counters: dict[int, int] = {}

        self.max_events = 5000
        self.max_bytes = 16000

    def parse(self) -> list[Event]:
        bytes_read = 0

        while len(self.events) < self.max_events and bytes_read < self.max_bytes:
            if self.pos >= len(self.rom):
                break

            byte = self.rom[self.pos]
            offset = self.pos
            hi = (byte >> 4) & 0xF
            lo = byte & 0xF

            if self.is_noise:
                # Percussion channel: different parsing
                should_stop = self._parse_percussion(byte, offset)
                if should_stop:
                    break
            elif hi < 0xC:
                # Note command (high nibble 0-B)
                self._parse_note(byte, offset)
            elif hi == 0xC:
                # $C0-$CF: mute with duration (same as CV1 rest)
                # Calls calc_cmd_delay with low nibble as multiplier
                # Duration = tempo * (low_nibble + 1)
                dur_frames = self.tempo * (lo + 1)
                self.events.append(RestEvent(
                    duration_nibble=lo,
                    duration_frames=dur_frames,
                    offset=offset,
                ))
                self.pos += 1
            elif hi == 0xD:
                # $D0-$DF: set SOUND_LENGTH_MULTIPLIER + channel config
                self._parse_instrument(byte, offset)
            elif hi == 0xE:
                # $E0-$EF: octave/pitch adjust
                self._parse_e_command(byte, offset)
            elif hi == 0xF:
                should_stop = self._parse_f_command(byte, offset)
                if should_stop:
                    break
            else:
                self.pos += 1

            bytes_read = self.pos - self.start_rom

        return self.events

    def _parse_note(self, byte: int, offset: int):
        """Parse a note command (high nibble < $C).

        Emit the note with FULL duration. Volume shaping (envelope table
        + decrescendo tail) is handled by the frame IR, not here.
        """
        hi = (byte >> 4) & 0xF  # pitch (0-11 = C through B)
        lo = byte & 0xF         # duration multiplier

        dur_frames = self.tempo * (lo + 1)
        # Apply EC pitch adjustment (shifts note within period table)
        adjusted_pitch = hi + self.pitch_adj
        adj_octave = self.octave
        while adjusted_pitch >= 12:
            adjusted_pitch -= 12
            adj_octave = max(0, adj_octave - 1)  # lower octave = higher pitch
        midi = pitch_to_midi(adjusted_pitch, adj_octave, self.is_triangle)

        self.events.append(NoteEvent(
            pitch=adjusted_pitch, octave=adj_octave,
            duration_nibble=lo, duration_frames=dur_frames,
            midi_note=midi, offset=offset,
        ))

        self.pos += 1

    def _parse_instrument(self, byte: int, offset: int):
        """Parse DX instrument/config command.

        Contra format:
        - Low nibble → SOUND_LENGTH_MULTIPLIER (tempo)
        - For pulse (slots 0,1): reads 3 more bytes
          (channel_config, vol_env, unknown)
        - For triangle (slot 2): reads 1 more byte (tri_config)
        """
        lo = byte & 0xF
        self.tempo = lo if lo > 0 else self.tempo
        self.pos += 1

        if self.pos >= len(self.rom):
            return

        if self.is_triangle:
            # Triangle: 1 additional byte (triangle config = $4008 value)
            tri_config = self.rom[self.pos]
            self.pos += 1

            self.events.append(InstrumentChange(
                tempo=self.tempo,
                raw_instrument=tri_config,
                duty_cycle=0,
                volume=0,
                length_halt=0,
                constant_vol=0,
                fade_start=0,
                fade_step=0,
                has_sweep=False,
                sweep_value=0,
                offset=offset,
            ))
        else:
            # Pulse: 3 additional bytes
            config_byte = self.rom[self.pos]
            self.pos += 1

            duty = (config_byte >> 6) & 3
            vol = config_byte & 0xF

            vol_env_byte = 0
            unknown = 0
            if self.pos < len(self.rom):
                vol_env_byte = self.rom[self.pos]
                self.pos += 1
            if self.pos < len(self.rom):
                unknown = self.rom[self.pos] & 0xF
                self.decrescendo_mul = unknown  # controls note-end silence
                self.pos += 1

            # Determine envelope mode from vol_env byte:
            # bit 7 set = automatic decrescendo (1/frame decay)
            #   low nibble = PULSE_VOL_DURATION (how many frames to decay)
            # bit 7 clear = use pulse_volume_ptr_tbl lookup
            if vol_env_byte & 0x80:
                # Auto decrescendo mode
                self.vol_env_index = -1
                env_index = -1
                vol_dur = vol_env_byte & 0x0F  # PULSE_VOL_DURATION
            else:
                # Lookup table mode — vol_env_byte is the table index
                self.vol_env_index = vol_env_byte
                env_index = vol_env_byte
                vol_dur = vol_env_byte & 0x0F  # also set for note start

            self.events.append(InstrumentChange(
                tempo=self.tempo,
                raw_instrument=config_byte,
                duty_cycle=duty,
                volume=vol,
                length_halt=(config_byte >> 5) & 1,
                constant_vol=(config_byte >> 4) & 1,
                fade_start=0,
                fade_step=0,
                has_sweep=False,
                sweep_value=0,
                offset=offset,
                vol_env_index=env_index,
                decrescendo_mul=self.decrescendo_mul,
                vol_duration=vol_dur,
            ))

    def _parse_e_command(self, byte: int, offset: int):
        """Parse E-series commands."""
        lo = byte & 0xF

        if lo <= 4:
            # E0-E4: set octave (same as CV1)
            self.octave = lo
            self.events.append(OctaveChange(lo, offset))
            self.pos += 1
        elif lo == 0x8:
            # E8: flatten note flag (different from CV1's envelope enable)
            self.events.append(EnvelopeEnable(offset))
            self.pos += 1
        elif lo == 0xB:
            # EB: vibrato setup — read 2 parameter bytes
            self.pos += 1
            if self.pos + 1 < len(self.rom):
                self.pos += 2  # skip vibrato params
        elif lo == 0xC:
            # EC: set pitch adjustment — shifts note index into period table
            # Parameter is in semitones (the engine doubles it for 2-byte entries)
            self.pos += 1
            if self.pos < len(self.rom):
                self.pitch_adj = self.rom[self.pos]
                self.pos += 1
        else:
            # Unknown E command, just advance
            self.pos += 1

    def _parse_f_command(self, byte: int, offset: int) -> bool:
        """Parse F-series control commands. Returns True if should stop."""
        if byte == 0xFD:
            # Subroutine call (same as CV1)
            if self.pos + 2 < len(self.rom):
                ptr = read_ptr_le(self.rom, self.pos + 1)
                self.events.append(SubroutineCall(ptr, contra_cpu_to_rom(ptr), offset))
                self.return_stack.append(self.pos + 3)
                self.pos = contra_cpu_to_rom(ptr)
            else:
                self.pos += 3
            return False

        elif byte == 0xFE:
            # Repeat (same semantics as CV1)
            if self.pos + 3 < len(self.rom):
                count = self.rom[self.pos + 1]
                ptr = read_ptr_le(self.rom, self.pos + 2)
                target_rom = contra_cpu_to_rom(ptr)

                if count == 0xFF:
                    self.events.append(RepeatMarker(count, ptr, target_rom, offset))
                    self.pos += 4
                    return True

                if offset not in self.repeat_counters:
                    self.repeat_counters[offset] = max(0, count - 2)
                    self.events.append(RepeatMarker(count, ptr, target_rom, offset))
                    if count >= 2:
                        self.pos = target_rom
                    else:
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
            if self.return_stack:
                self.pos = self.return_stack.pop()
                return False
            else:
                self.events.append(EndMarker(offset))
                return True

        else:
            self.pos += 1
            return False

    def _parse_percussion(self, byte: int, offset: int) -> bool:
        """Parse noise/dmc percussion commands.

        Contra percussion format:
        - $Fx: F-series control (FD/FE/FF = sub/repeat/end)
        - $Dx: set SOUND_LENGTH_MULTIPLIER to low nibble
        - Other: high nibble selects percussion sample,
                 low nibble = duration multiplier
        """
        hi = (byte >> 4) & 0xF
        lo = byte & 0xF

        if hi == 0xF:
            return self._parse_f_command(byte, offset)

        elif hi == 0xD:
            # Set tempo/multiplier
            self.tempo = lo if lo > 0 else self.tempo
            self.pos += 1
            return False

        else:
            # Percussion hit: high nibble = sample type, low = duration
            dur_frames = self.tempo * (lo + 1)

            # From disassembly percussion_tbl: $02,$5a,$5b,$5a,$5b,$25,$5c,$5d
            # Nibbles >= 3 also trigger sound_02 (bass drum on noise channel).
            # The bass drum is a short noise burst that reinforces triangle.
            # Mapping:
            #   0: kick only (sound_02 = bass drum on noise channel)
            #   1: snare only (DMC sound_5a, no noise)
            #   2: hihat only (DMC sound_5b, no noise)
            #   3: kick+snare (sound_5a + sound_02)
            #   4: kick+hihat (sound_5b + sound_02)
            #   5: snare (sound_25)
            #   6: kick+snare (sound_5c + sound_02)
            #   7: kick+snare (sound_5d + sound_02)
            if hi == 0:
                drum_type = "kick"
            elif hi == 1:
                drum_type = "snare"
            elif hi == 2:
                drum_type = "hihat"
            elif hi in (3, 6, 7):
                drum_type = "kick_snare"
            elif hi == 4:
                drum_type = "kick_hihat"
            elif hi == 5:
                drum_type = "snare"
            else:
                drum_type = "kick"

            self.events.append(DrumEvent(drum_type, dur_frames, offset))
            self.pos += 1
            return False


class ContraParser:
    """High-level parser for Contra NES music."""

    def __init__(self, rom_path: str | Path):
        self.rom_path = Path(rom_path)
        with open(self.rom_path, 'rb') as f:
            self.rom = f.read()

        if self.rom[:4] != b'NES\x1a':
            raise ValueError(f"Not a valid NES ROM: {self.rom_path}")

        self.envelope_tables = extract_envelope_tables(self.rom)

    def list_tracks(self) -> list[dict]:
        return [{"key": k, "name": v[0]} for k, v in CONTRA_TRACKS.items()]

    def parse_track(self, track_key: str | int) -> ParsedSong:
        """Parse a Contra music track by key name or index (1-based)."""
        if isinstance(track_key, int):
            keys = list(CONTRA_TRACKS.keys())
            if 1 <= track_key <= len(keys):
                track_key = keys[track_key - 1]
            else:
                raise ValueError(f"Track index {track_key} out of range")

        if track_key not in CONTRA_TRACKS:
            raise ValueError(f"Unknown track: {track_key}. "
                             f"Available: {list(CONTRA_TRACKS.keys())}")

        name, sq1, sq2, tri, noi = CONTRA_TRACKS[track_key]

        song = ParsedSong(track_number=list(CONTRA_TRACKS.keys()).index(track_key) + 1)

        for cpu_addr, ch_type in [(sq1, "pulse1"), (sq2, "pulse2"),
                                   (tri, "triangle")]:
            parser = ContraChannelParser(self.rom, cpu_addr, ch_type)
            events = parser.parse()

            channel = ChannelData(
                name=CHANNEL_NAMES[ch_type],
                channel_type=ch_type,
                events=events,
                start_offset=contra_cpu_to_rom(cpu_addr),
                start_cpu=cpu_addr,
            )
            song.channels.append(channel)

        # Parse noise channel as its own channel
        # (unlike CV1 where drums are inline E9/EA triggers,
        # Contra has a full separate percussion data stream)
        noi_parser = ContraChannelParser(self.rom, noi, "noise")
        noi_events = noi_parser.parse()

        noise_channel = ChannelData(
            name="Noise",
            channel_type="noise",
            events=noi_events,
            start_offset=contra_cpu_to_rom(noi),
            start_cpu=noi,
        )
        song.channels.append(noise_channel)

        # Collect instruments
        for ch in song.channels:
            for ev in ch.events:
                if isinstance(ev, InstrumentChange):
                    song.instruments.append(ev)

        return song


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python contra_parser.py <rom_path> [track_key]")
        print(f"  Available tracks: {list(CONTRA_TRACKS.keys())}")
        sys.exit(1)

    rom_path = sys.argv[1]
    track_key = sys.argv[2] if len(sys.argv) > 2 else "jungle"

    parser = ContraParser(rom_path)

    print("Available tracks:")
    for t in parser.list_tracks():
        print(f"  {t['key']:15s} {t['name']}")

    print(f"\nParsing: {track_key}")
    song = parser.parse_track(track_key)

    for ch in song.channels:
        notes = sum(1 for e in ch.events if isinstance(e, NoteEvent))
        rests = sum(1 for e in ch.events if isinstance(e, RestEvent))
        drums = sum(1 for e in ch.events if isinstance(e, DrumEvent))
        total_frames = sum(
            e.duration_frames for e in ch.events
            if isinstance(e, (NoteEvent, RestEvent))
        )
        print(f"  {ch.name}: {notes} notes, {rests} rests, {drums} drums, "
              f"{total_frames} frames ({total_frames/60:.1f}s)")


if __name__ == "__main__":
    main()
