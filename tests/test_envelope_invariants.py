"""Tests encoding known envelope invariants.

These tests exist because we discovered bugs through cross-game
trace comparison. Each test encodes a verified behavior that must
not regress.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extraction.drivers.konami.frame_ir import (
    _cv1_parametric_envelope,
    _contra_lookup_envelope,
)


class TestCV1ParametricEnvelope:
    """CV1 two-phase parametric envelope invariants.

    Layer: ENGINE
    Evidence: Mesen APU trace, 0 mismatches on CV1 Vampire Killer pulse.
    """

    def test_frame0_always_initial_volume(self):
        """INV-001: Frame 0 must always be the initial volume."""
        # This was broken when phase2_start went negative
        for vol in range(1, 16):
            for fs in range(0, 8):
                for fstep in range(0, 16):
                    vols = _cv1_parametric_envelope(10, vol, fs, fstep)
                    assert vols[0] == vol, (
                        f"Frame 0 != initial vol for vol={vol} "
                        f"fade_start={fs} fade_step={fstep}: got {vols[0]}"
                    )

    def test_phase2_start_clamped(self):
        """INV-001: phase2_start = max(1, duration - fade_step).

        When fade_step > duration, phase 2 must not begin before frame 1.
        This bug caused 45 mismatches on CV1 Vampire Killer.
        """
        # fade_step=9 > duration=7: phase2_start would be -2 without clamping
        vols = _cv1_parametric_envelope(7, 5, 2, 9)
        assert vols == [5, 4, 3, 2, 1, 0, 0], f"Got {vols}"

    def test_verified_b5_vol5_fade2_3(self):
        """Verified against APU trace: $B5 instrument."""
        vols = _cv1_parametric_envelope(10, 5, 2, 3)
        assert vols == [5, 4, 3, 3, 3, 3, 3, 2, 1, 0]

    def test_fade_step_zero_holds_forever(self):
        """When fade_step=0, no phase 2 release -- hold indefinitely."""
        vols = _cv1_parametric_envelope(20, 5, 2, 0)
        # After 2 decrements: 5, 4, 3, then hold at 3 forever
        assert vols[0] == 5
        assert vols[3:] == [3] * 17

    def test_volume_never_negative(self):
        """Volume must never go below 0."""
        for dur in [1, 5, 10, 20, 50]:
            for vol in [1, 5, 10, 15]:
                for fs in [0, 2, 5, 10]:
                    for fstep in [0, 3, 8, 15]:
                        vols = _cv1_parametric_envelope(dur, vol, fs, fstep)
                        assert all(v >= 0 for v in vols), (
                            f"Negative vol: dur={dur} vol={vol} "
                            f"fs={fs} fstep={fstep}: {vols}"
                        )


class TestContraLookupEnvelope:
    """Contra lookup-table envelope invariants.

    Layer: ENGINE + DATA
    Evidence: 54 tables extracted from ROM, 96.6% trace match.
    """

    def test_bounce_at_1_during_decrescendo(self):
        """INV-003: Volume holds at 1 during resume decrescendo, never 0.

        The engine does 'inc PULSE_VOLUME' when vol hits 0 during
        resume_decrescendo (disassembly line 411).
        """
        # Table that ends quickly, long note with decrescendo
        table = [5, 4, 3, 2]
        vols = _contra_lookup_envelope(
            duration=60, vol_env_index=0, decrescendo_mul=4,
            initial_volume=5, envelope_tables=[table],
        )
        # After table: hold at 2, then decrescendo starts
        # Volume should never be 0 during the tail
        decr_start = 60 - ((4 * 60) >> 4)  # frame 45
        tail = vols[decr_start:]
        assert all(v >= 1 for v in tail), f"Vol went to 0 in tail: {tail}"

    def test_auto_decrescendo_vol_duration(self):
        """INV-003 variant: auto mode respects PULSE_VOL_DURATION."""
        vols = _contra_lookup_envelope(
            duration=48, vol_env_index=-1, decrescendo_mul=8,
            initial_volume=5, envelope_tables=[],
            vol_duration=4,
        )
        # Decay 4 frames: 5,4,3,2,1 then hold at 1
        assert vols[0] == 5
        assert vols[4] == 1  # paused after 4 decrements
        assert vols[10] == 1  # still holding

    def test_empty_table_uses_initial_volume(self):
        """Edge case: empty envelope table."""
        vols = _contra_lookup_envelope(
            duration=10, vol_env_index=0, decrescendo_mul=0,
            initial_volume=7, envelope_tables=[[]],
        )
        # Should hold at initial volume (no table data)
        assert vols[0] == 7


class TestEnvelopeLayerSeparation:
    """Verify envelope functions don't leak game-specific assumptions."""

    def test_cv1_envelope_is_pure_function(self):
        """CV1 envelope depends only on its parameters, no global state."""
        a = _cv1_parametric_envelope(10, 5, 2, 3)
        b = _cv1_parametric_envelope(10, 5, 2, 3)
        assert a == b

    def test_contra_envelope_is_pure_function(self):
        """Contra envelope depends only on its parameters."""
        table = [5, 4, 3]
        a = _contra_lookup_envelope(10, 0, 2, 5, [table])
        b = _contra_lookup_envelope(10, 0, 2, 5, [table])
        assert a == b


class TestTriangleExpectedMismatch:
    """Triangle linear counter is known APPROXIMATE.

    Layer: HARDWARE
    Evidence: 195 sounding mismatches on CV1 Vampire Killer (1792 frames).
    Purpose: Prevent accidental "false fixes" — if someone changes the
    triangle model, these tests catch unintended regressions or false
    improvements that break the documented behavior.
    """

    def test_triangle_linear_counter_approximation(self):
        """INV-007: (reload+3)//4 is approximate, not exact.

        The formula is correct to within 1 frame for all observed reload
        values. Verify it produces the documented approximation.
        """
        from extraction.drivers.konami.frame_ir import parser_to_frame_ir, DriverCapability
        from extraction.drivers.konami.parser import (
            ParsedSong, ChannelData, NoteEvent, InstrumentChange,
        )

        # Build a triangle note with known linear counter reload
        # tri_config = 0x1C means control=0, reload=28
        # Expected sounding: (28+3)//4 = 7 frames
        song = ParsedSong(track_number=1)
        ch = ChannelData(
            name="Triangle", channel_type="triangle",
            events=[
                InstrumentChange(
                    tempo=6, raw_instrument=0x1C,  # control=0, reload=28
                    duty_cycle=0, volume=0, length_halt=0, constant_vol=0,
                    fade_start=0, fade_step=0, has_sweep=False, sweep_value=0,
                    offset=0,
                ),
                NoteEvent(pitch=0, octave=2, duration_nibble=3,
                         duration_frames=24, midi_note=36, offset=1),
            ],
            start_offset=0, start_cpu=0,
        )
        song.channels.append(ch)

        ir = parser_to_frame_ir(song, DriverCapability.cv1())
        tri_ch = ir.channels[0]

        # Count sounding frames
        sounding = sum(1 for f in range(24) if tri_ch.get_frame(f).sounding)
        assert sounding == 7, f"Expected 7 sounding frames, got {sounding}"

        # Verify non-sounding frames have volume 0
        for f in range(7, 24):
            assert tri_ch.get_frame(f).volume == 0

    def test_triangle_control_bit_overrides_counter(self):
        """When control bit is set, triangle sounds for full duration."""
        from extraction.drivers.konami.frame_ir import parser_to_frame_ir, DriverCapability
        from extraction.drivers.konami.parser import (
            ParsedSong, ChannelData, NoteEvent, InstrumentChange,
        )

        # tri_config = 0x9C means control=1, reload=28
        song = ParsedSong(track_number=1)
        ch = ChannelData(
            name="Triangle", channel_type="triangle",
            events=[
                InstrumentChange(
                    tempo=6, raw_instrument=0x9C,  # control=1, reload=28
                    duty_cycle=0, volume=0, length_halt=0, constant_vol=0,
                    fade_start=0, fade_step=0, has_sweep=False, sweep_value=0,
                    offset=0,
                ),
                NoteEvent(pitch=0, octave=2, duration_nibble=3,
                         duration_frames=24, midi_note=36, offset=1),
            ],
            start_offset=0, start_cpu=0,
        )
        song.channels.append(ch)

        ir = parser_to_frame_ir(song, DriverCapability.cv1())
        tri_ch = ir.channels[0]

        sounding = sum(1 for f in range(24) if tri_ch.get_frame(f).sounding)
        assert sounding == 24, f"Control=1 should sound full duration, got {sounding}"


class TestDecrescendoThreshold:
    """INV-009: Decrescendo end pause formula (PROVISIONAL).

    Layer: ENGINE
    Evidence: Derived from Contra disassembly resume_decrescendo routine.
    """

    def test_decrescendo_threshold_formula(self):
        """INV-009: threshold = (mul * duration) >> 4."""
        # mul=4, duration=60: threshold = (4*60)>>4 = 15
        table = [5, 4, 3, 2]
        vols = _contra_lookup_envelope(
            duration=60, vol_env_index=0, decrescendo_mul=4,
            initial_volume=5, envelope_tables=[table],
        )
        # Decrescendo starts at frame 60-15=45
        # Before that, hold at last table vol (2)
        assert vols[44] == 2, f"Frame 44 should hold at 2, got {vols[44]}"
        # After decrescendo start, volume should decrease
        assert vols[45] < vols[44], (
            f"Frame 45 should start decrescendo: {vols[44]} -> {vols[45]}"
        )

    def test_decrescendo_mul_zero_no_tail(self):
        """When mul=0, no decrescendo tail (threshold = 0)."""
        table = [5, 4, 3]
        vols = _contra_lookup_envelope(
            duration=30, vol_env_index=0, decrescendo_mul=0,
            initial_volume=5, envelope_tables=[table],
        )
        # After table exhausted, should hold at last value forever
        assert all(v == 3 for v in vols[3:])
