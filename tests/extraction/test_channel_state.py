"""Tests for channel state tracking."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.dynamic_analysis.channel_state import APUState, PulseState


class TestAPUState:
    def test_status_register(self):
        state = APUState()
        changes = state.apply_write(0x4015, 0x0F, frame=0)
        assert state.pulse1.enabled is True
        assert state.pulse2.enabled is True
        assert state.triangle.enabled is True
        assert state.noise.enabled is True
        assert state.dpcm.enabled is False

    def test_pulse_period(self):
        state = APUState()
        state.apply_write("$4002", 253, frame=0)
        state.apply_write("$4003", 0, frame=0)
        assert state.pulse1.period == 253

    def test_pulse_duty_volume(self):
        state = APUState()
        # Duty=2, constant vol, vol=15 => 0xBF
        changes = state.apply_write(0x4000, 0xBF, frame=0)
        assert state.pulse1.duty == 2
        assert state.pulse1.volume == 15
        assert state.pulse1.constant_volume is True
        assert "duty" in changes.get("pulse1", [])
        assert "volume" in changes.get("pulse1", [])

    def test_pulse2_separate(self):
        state = APUState()
        state.apply_write(0x4004, 0xBF, frame=0)
        assert state.pulse2.duty == 2
        assert state.pulse1.duty == 0  # pulse1 unchanged

    def test_triangle_period(self):
        state = APUState()
        state.apply_write(0x400A, 253, frame=0)
        state.apply_write(0x400B, 1, frame=0)
        assert state.triangle.period == (1 << 8) | 253

    def test_noise_mode(self):
        state = APUState()
        state.apply_write(0x400E, 0x84, frame=0)
        assert state.noise.mode == 1
        assert state.noise.period_index == 4

    def test_dpcm_sample_address(self):
        state = APUState()
        state.apply_write(0x4012, 0x10, frame=0)
        assert state.dpcm.sample_address == 0xC000 + (0x10 * 64)

    def test_snapshot(self):
        state = APUState()
        state.apply_write(0x4015, 0x1F, frame=0)
        snap = state.snapshot()
        assert "pulse1" in snap
        assert "dpcm" in snap
        assert snap["pulse1"]["enabled"] is True

    def test_string_address(self):
        state = APUState()
        changes = state.apply_write("$4000", 0xBF, frame=0)
        assert state.pulse1.duty == 2

    def test_change_detection(self):
        state = APUState()
        # First write — everything changes
        changes1 = state.apply_write(0x4000, 0xBF, frame=0)
        assert "pulse1" in changes1

        # Same value — no change
        changes2 = state.apply_write(0x4000, 0xBF, frame=1)
        assert changes2 == {}

        # Different duty
        changes3 = state.apply_write(0x4000, 0x3F, frame=2)
        assert "duty" in changes3.get("pulse1", [])
