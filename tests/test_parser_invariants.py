"""Tests encoding known parser invariants.

These tests verify that parsers produce structurally valid output
that the frame IR can process correctly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extraction.drivers.konami.parser import (
    pitch_to_midi, ParsedSong, ChannelData, NoteEvent, RestEvent,
    InstrumentChange,
)


class TestPitchToMidi:
    """Pitch mapping invariants.

    Layer: DATA (game-specific octave convention)
    Evidence: CV1 trace 0 pitch mismatches, Contra trace 0 real mismatches.
    """

    def test_base_octave4_is_36(self):
        """INV-005: BASE_MIDI_OCTAVE4 = 36 (C2)."""
        assert pitch_to_midi(0, 4) == 36  # C at octave 4 = C2 = MIDI 36

    def test_triangle_offset_minus_12(self):
        """INV-004: Triangle is 1 octave lower than pulse."""
        pulse = pitch_to_midi(0, 4, is_triangle=False)
        tri = pitch_to_midi(0, 4, is_triangle=True)
        assert pulse - tri == 12

    def test_octave_0_is_highest(self):
        """Octave 0 produces highest notes, octave 4 lowest."""
        high = pitch_to_midi(0, 0)
        low = pitch_to_midi(0, 4)
        assert high > low

    def test_pitch_range_0_to_11(self):
        """All 12 pitches produce distinct MIDI notes within an octave."""
        notes = [pitch_to_midi(p, 2) for p in range(12)]
        assert len(set(notes)) == 12
        assert notes == sorted(notes)  # ascending

    def test_octave_clamp(self):
        """Octave values > 4 are clamped to 4."""
        normal = pitch_to_midi(0, 4)
        clamped = pitch_to_midi(0, 7)
        assert clamped == normal


class TestFullDurationInvariant:
    """Parser full-duration invariant.

    Layer: DATA
    Evidence: Contra parser produces 0 violations.
    """

    def test_valid_song_passes(self):
        """INV-002: A correctly parsed song has no duration violations."""
        song = ParsedSong(track_number=1)
        ch = ChannelData(
            name="test", channel_type="pulse1",
            events=[
                InstrumentChange(
                    tempo=6, raw_instrument=0, duty_cycle=0, volume=5,
                    length_halt=0, constant_vol=0, fade_start=0, fade_step=0,
                    has_sweep=False, sweep_value=0, offset=0,
                ),
                NoteEvent(pitch=0, octave=2, duration_nibble=0,
                         duration_frames=6, midi_note=60, offset=1),
                NoteEvent(pitch=0, octave=2, duration_nibble=2,
                         duration_frames=18, midi_note=60, offset=2),
            ],
            start_offset=0, start_cpu=0,
        )
        song.channels.append(ch)
        assert song.validate_full_duration() == []

    def test_truncated_duration_detected(self):
        """INV-002: Truncated note duration is caught."""
        song = ParsedSong(track_number=1)
        ch = ChannelData(
            name="test", channel_type="pulse1",
            events=[
                InstrumentChange(
                    tempo=6, raw_instrument=0, duty_cycle=0, volume=5,
                    length_halt=0, constant_vol=0, fade_start=0, fade_step=0,
                    has_sweep=False, sweep_value=0, offset=0,
                ),
                NoteEvent(pitch=0, octave=2, duration_nibble=2,
                         duration_frames=12, midi_note=60, offset=1),
                # duration should be 6*(2+1)=18, not 12
            ],
            start_offset=0, start_cpu=0,
        )
        song.channels.append(ch)
        violations = song.validate_full_duration()
        assert len(violations) == 1


class TestECPitchAdjustment:
    """INV-006: EC command shifts period table index by N semitones.

    Layer: DATA
    Evidence: Contra Jungle trace — 0 pitch mismatches after EC fix.
    """

    def test_ec_adjusts_pitch(self):
        """Contra parser applies pitch_adj from EC command."""
        from extraction.drivers.konami.contra_parser import ContraChannelParser

        # Build a minimal ROM fragment: EC 02 (set pitch_adj=2), then note A0
        # EC 02 means all subsequent notes shift +2 semitones
        # Note byte 0x90 = pitch 9 (A), duration nibble 0
        # With pitch_adj=2, effective pitch = 9+2 = 11 (B)
        rom = bytearray(0x10000 + 0x4010)  # large enough for address space
        # Place data at a known CPU address ($9000 -> ROM offset)
        from extraction.drivers.konami.contra_parser import contra_cpu_to_rom
        base_cpu = 0x9000
        base_rom = contra_cpu_to_rom(base_cpu)

        # D7 = set tempo to 7 + 1 instrument byte (triangle for simplicity: 1 byte)
        # Actually, let's use a pulse channel with EC + note
        # EC 02 = set pitch_adj to 2
        # 90 = note: pitch=9, dur_nibble=0
        # FF = end
        rom[base_rom] = 0xEC       # EC command
        rom[base_rom + 1] = 0x02   # pitch adjust = 2
        rom[base_rom + 2] = 0x90   # note: pitch 9, dur 0
        rom[base_rom + 3] = 0xFF   # end

        parser = ContraChannelParser(bytes(rom), base_cpu, "pulse1")
        events = parser.parse()

        # Find the NoteEvent
        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(notes) == 1
        # pitch should be 9+2=11 (B)
        assert notes[0].pitch == 11, f"Expected pitch 11, got {notes[0].pitch}"

    def test_ec_wraps_octave(self):
        """EC adjustment that exceeds 12 wraps to next octave."""
        from extraction.drivers.konami.contra_parser import ContraChannelParser, contra_cpu_to_rom

        rom = bytearray(0x10000 + 0x4010)
        base_cpu = 0x9000
        base_rom = contra_cpu_to_rom(base_cpu)

        # Set octave to 2 first
        rom[base_rom] = 0xE2       # E2 = octave 2
        rom[base_rom + 1] = 0xEC   # EC command
        rom[base_rom + 2] = 0x05   # pitch adjust = 5
        rom[base_rom + 3] = 0xA0   # note: pitch 10 (A#), dur 0
        rom[base_rom + 4] = 0xFF   # end

        parser = ContraChannelParser(bytes(rom), base_cpu, "pulse1")
        events = parser.parse()

        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(notes) == 1
        # pitch 10 + adj 5 = 15, wraps: pitch=3, octave=2-1=1
        assert notes[0].pitch == 3, f"Expected wrapped pitch 3, got {notes[0].pitch}"
        assert notes[0].octave == 1, f"Expected octave 1 after wrap, got {notes[0].octave}"


class TestDXByteCount:
    """INV-008: DX byte count is game-specific AND channel-specific.

    Layer: DATA
    Evidence: CV1 DX = 2 extra bytes (pulse). Contra DX = 3 (pulse) / 1 (triangle).
    """

    def test_cv1_dx_reads_2_bytes_pulse(self):
        """CV1 parser consumes DX + 2 bytes for pulse channels."""
        from extraction.drivers.konami.parser import ChannelParser, cpu_to_rom

        # Build ROM: D7 (tempo=7) + instrument byte + fade byte + note + FF
        rom = bytearray(0x10000)
        base_cpu = 0x8100
        base_rom = cpu_to_rom(base_cpu)
        rom[base_rom] = 0xD7       # DX: tempo=7
        rom[base_rom + 1] = 0xB5   # instrument: duty=2, vol=5
        rom[base_rom + 2] = 0x23   # fade: start=2, step=3
        rom[base_rom + 3] = 0x00   # note: pitch=0, dur=0
        rom[base_rom + 4] = 0xFF   # end

        parser = ChannelParser(bytes(rom), base_cpu, "pulse1")
        events = parser.parse()

        instruments = [e for e in events if isinstance(e, InstrumentChange)]
        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(instruments) == 1, f"Expected 1 instrument, got {len(instruments)}"
        assert len(notes) == 1, f"Expected 1 note, got {len(notes)}"
        assert instruments[0].fade_start == 2
        assert instruments[0].fade_step == 3

    def test_cv1_dx_reads_0_bytes_triangle(self):
        """CV1 parser consumes DX + 1 byte for triangle (no fade byte)."""
        from extraction.drivers.konami.parser import ChannelParser, cpu_to_rom

        rom = bytearray(0x10000)
        base_cpu = 0x8100
        base_rom = cpu_to_rom(base_cpu)
        rom[base_rom] = 0xD7       # DX
        rom[base_rom + 1] = 0x1C   # instrument byte (triangle config)
        rom[base_rom + 2] = 0x00   # this should be parsed as NOTE, not fade
        rom[base_rom + 3] = 0xFF   # end

        parser = ChannelParser(bytes(rom), base_cpu, "triangle")
        events = parser.parse()

        instruments = [e for e in events if isinstance(e, InstrumentChange)]
        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(instruments) == 1
        assert len(notes) == 1, (
            f"Expected 1 note (byte after DX+inst should be note), got {len(notes)}"
        )
        assert instruments[0].fade_start == 0  # triangle has no fade
        assert instruments[0].fade_step == 0

    def test_contra_dx_reads_3_bytes_pulse(self):
        """Contra parser consumes DX + 3 bytes for pulse."""
        from extraction.drivers.konami.contra_parser import ContraChannelParser, contra_cpu_to_rom

        rom = bytearray(0x10000 + 0x4010)
        base_cpu = 0x9000
        base_rom = contra_cpu_to_rom(base_cpu)
        rom[base_rom] = 0xD7       # DX: tempo=7
        rom[base_rom + 1] = 0xB5   # config byte (duty+vol)
        rom[base_rom + 2] = 0x83   # vol_env byte (bit7=auto, dur=3)
        rom[base_rom + 3] = 0x04   # unknown/decrescendo byte
        rom[base_rom + 4] = 0x00   # note: pitch=0, dur=0
        rom[base_rom + 5] = 0xFF   # end

        parser = ContraChannelParser(bytes(rom), base_cpu, "pulse1")
        events = parser.parse()

        instruments = [e for e in events if isinstance(e, InstrumentChange)]
        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(instruments) == 1
        assert len(notes) == 1, (
            f"Expected 1 note after DX+3, got {len(notes)}"
        )
        assert instruments[0].vol_duration == 3  # low nibble of 0x83

    def test_contra_dx_reads_1_byte_triangle(self):
        """Contra parser consumes DX + 1 byte for triangle."""
        from extraction.drivers.konami.contra_parser import ContraChannelParser, contra_cpu_to_rom

        rom = bytearray(0x10000 + 0x4010)
        base_cpu = 0x9000
        base_rom = contra_cpu_to_rom(base_cpu)
        rom[base_rom] = 0xD7       # DX: tempo=7
        rom[base_rom + 1] = 0x1C   # tri_config (1 byte only)
        rom[base_rom + 2] = 0x00   # this should be note, not consumed by DX
        rom[base_rom + 3] = 0xFF   # end

        parser = ContraChannelParser(bytes(rom), base_cpu, "triangle")
        events = parser.parse()

        instruments = [e for e in events if isinstance(e, InstrumentChange)]
        notes = [e for e in events if isinstance(e, NoteEvent)]
        assert len(instruments) == 1
        assert len(notes) == 1, (
            f"Expected 1 note after DX+1 (triangle), got {len(notes)}"
        )
