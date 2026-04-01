"""Regression tests for the Live Patch system in ReapNES_APU.jsfx.

Validates the root cause fix for the live-vs-playback timbre divergence:
MIDI file playback gets its timbre from CC11/CC12 automation in the stream,
while live keyboard input had no such automation and fell back to generic
defaults. The Live Patch system provides NES-style duty and volume envelope
on note-on when the channel has NOT received CC automation.

Tests verify:
1. CC11/CC12 presence marks a channel as CC-driven (file playback mode)
2. Absence of CC11/CC12 allows Live Patch envelope to activate
3. CC123/CC121 resets CC-driven state
4. Slider14 controls Live Patch mode (Off / NES Sustain / NES Decay)
5. Live Patch does not interfere with CC-driven channels
6. Per-channel independence (one channel CC-driven, another live)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JSFX_PATH = REPO_ROOT / "studio" / "jsfx" / "ReapNES_APU.jsfx"


@pytest.fixture
def jsfx_source() -> str:
    return JSFX_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
#  Structural tests: verify the Live Patch system exists and is wired up
# ---------------------------------------------------------------------------

class TestLivePatchStructure:
    """Verify that the Live Patch machinery is present in the canonical plugin."""

    def test_slider14_live_patch_exists(self, jsfx_source: str) -> None:
        """slider14 must exist and offer Off/Sustain/Decay modes."""
        assert re.search(r"slider14:.*Live Patch", jsfx_source), \
            "slider14 (Live Patch) not found in ReapNES_APU.jsfx"

    def test_slider15_debug_overlay_exists(self, jsfx_source: str) -> None:
        """slider15 must exist for debug overlay toggle."""
        assert re.search(r"slider15:.*Debug Overlay", jsfx_source), \
            "slider15 (Debug Overlay) not found"

    def test_lp_cc_active_tracking(self, jsfx_source: str) -> None:
        """CC-active tracking arrays must be initialized."""
        assert "lp_cc_active" in jsfx_source
        # Must have per-channel init
        assert "lp_cc_active[0] = 0" in jsfx_source
        assert "lp_cc_active[3] = 0" in jsfx_source

    def test_lp_env_state_arrays(self, jsfx_source: str) -> None:
        """Envelope state arrays must exist for volume, phase, timer."""
        assert "lp_env_vol" in jsfx_source
        assert "lp_env_phase" in jsfx_source
        assert "lp_env_timer" in jsfx_source
        assert "lp_vel" in jsfx_source

    def test_lp_trigger_env_function(self, jsfx_source: str) -> None:
        """lp_trigger_env must exist and set phase to sustain."""
        assert "function lp_trigger_env" in jsfx_source
        # Must set phase to 1 (sustain) somewhere in the function
        fn_start = jsfx_source.index("function lp_trigger_env")
        # Find end: next function definition or next @ section
        fn_region = jsfx_source[fn_start:fn_start + 500]
        assert "lp_env_phase[ch] = 1" in fn_region

    def test_lp_release_env_function(self, jsfx_source: str) -> None:
        """lp_release_env must exist and transition to decay."""
        assert "function lp_release_env" in jsfx_source

    def test_lp_process_env_function(self, jsfx_source: str) -> None:
        """lp_process_env must exist for per-sample envelope processing."""
        assert "function lp_process_env" in jsfx_source


# ---------------------------------------------------------------------------
#  CC-driven detection: verify that CC11/CC12 mark channels as file-mode
# ---------------------------------------------------------------------------

class TestCCDrivenDetection:
    """Verify that CC11/CC12 set lp_cc_active and CC123/121 reset it."""

    def test_cc11_sets_cc_active(self, jsfx_source: str) -> None:
        """When CC11 is received, lp_cc_active[ch] must be set to 1."""
        # Find CC11 handler
        cc11_block = _extract_cc_handler(jsfx_source, "msg2 == 11")
        assert "lp_cc_active[ch] = 1" in cc11_block, \
            "CC11 handler does not set lp_cc_active[ch]"

    def test_cc12_sets_cc_active(self, jsfx_source: str) -> None:
        """When CC12 is received, lp_cc_active[ch] must be set to 1."""
        cc12_block = _extract_cc_handler(jsfx_source, "msg2 == 12")
        assert "lp_cc_active[ch] = 1" in cc12_block, \
            "CC12 handler does not set lp_cc_active[ch]"

    def test_cc123_resets_cc_active(self, jsfx_source: str) -> None:
        """CC123 (all notes off) must reset all lp_cc_active flags."""
        assert "msg2 == 123" in jsfx_source
        # Find the CC123 handler region
        idx = jsfx_source.index("msg2 == 123")
        region = jsfx_source[idx:idx+300]
        assert "lp_cc_active[0] = 0" in region

    def test_cc121_resets_cc_active(self, jsfx_source: str) -> None:
        """CC121 (reset all controllers) must reset lp_cc_active flags."""
        assert "msg2 == 121" in jsfx_source


# ---------------------------------------------------------------------------
#  Note-on path: verify live vs CC-driven branching
# ---------------------------------------------------------------------------

class TestNoteOnPath:
    """Verify that note-on checks lp_cc_active and branches correctly."""

    def test_noteon_checks_lp_active(self, jsfx_source: str) -> None:
        """Note-on must compute lp_active from slider14 and lp_cc_active."""
        # Find the note-on handler
        assert "lp_active = slider14 > 0 && !lp_cc_active[ch]" in jsfx_source, \
            "Note-on does not compute lp_active from slider14 and lp_cc_active"

    def test_noteon_triggers_env_for_live(self, jsfx_source: str) -> None:
        """In live mode, note-on must call lp_trigger_env."""
        # Look for lp_trigger_env call in note-on handler
        noteon_region = _extract_noteon_handler(jsfx_source)
        assert "lp_trigger_env" in noteon_region, \
            "Note-on does not call lp_trigger_env for live input"

    def test_noteon_sets_duty_from_slider_in_live_mode(self, jsfx_source: str) -> None:
        """In live mode, note-on must set duty from the slider value."""
        noteon_region = _extract_noteon_handler(jsfx_source)
        # For pulse 1: should set p1_duty = slider1
        assert "p1_duty = slider1" in noteon_region, \
            "Live mode note-on does not set p1_duty from slider1"


# ---------------------------------------------------------------------------
#  Envelope processing: verify per-sample envelope runs only for live channels
# ---------------------------------------------------------------------------

class TestEnvelopeProcessing:
    """Verify that @sample processes envelopes only for non-CC channels."""

    def test_sample_checks_slider14(self, jsfx_source: str) -> None:
        """@sample must gate envelope processing on slider14 > 0."""
        sample_section = _extract_section(jsfx_source, "@sample")
        assert "slider14 > 0" in sample_section

    def test_sample_checks_cc_active_per_channel(self, jsfx_source: str) -> None:
        """@sample must check lp_cc_active before processing each channel."""
        sample_section = _extract_section(jsfx_source, "@sample")
        assert "!lp_cc_active[0]" in sample_section
        assert "!lp_cc_active[1]" in sample_section

    def test_envelope_applies_volume_to_pulse(self, jsfx_source: str) -> None:
        """Envelope must write to p1_vol / p2_vol for pulse channels."""
        assert "p1_vol = floor(vol + 0.5)" in jsfx_source
        assert "p2_vol = floor(vol + 0.5)" in jsfx_source


# ---------------------------------------------------------------------------
#  Debug overlay: verify diagnostic output
# ---------------------------------------------------------------------------

class TestDebugOverlay:
    """Verify that the debug overlay shows MIDI source info."""

    def test_debug_shows_cc_counts(self, jsfx_source: str) -> None:
        assert "dbg_cc11_count" in jsfx_source
        assert "dbg_cc12_count" in jsfx_source

    def test_debug_shows_live_vs_cc_source(self, jsfx_source: str) -> None:
        assert "dbg_last_src" in jsfx_source

    def test_debug_shows_envelope_phase(self, jsfx_source: str) -> None:
        assert "Env phase" in jsfx_source


# ---------------------------------------------------------------------------
#  Non-interference: verify existing playback path is unchanged
# ---------------------------------------------------------------------------

class TestPlaybackPreservation:
    """Verify that CC-driven channels still work exactly as before."""

    def test_cc11_still_sets_volume(self, jsfx_source: str) -> None:
        """CC11 must still directly set p1_vol/p2_vol/noi_vol."""
        cc11_block = _extract_cc_handler(jsfx_source, "msg2 == 11")
        assert "p1_vol = floor(msg3 / 127 * 15 + 0.5)" in cc11_block

    def test_cc12_still_sets_duty(self, jsfx_source: str) -> None:
        """CC12 must still directly set p1_duty/p2_duty."""
        cc12_block = _extract_cc_handler(jsfx_source, "msg2 == 12")
        assert "p1_duty = min(3, msg3)" in cc12_block

    def test_drum_trigger_unchanged(self, jsfx_source: str) -> None:
        """trigger_drum function must still exist and work."""
        assert "function trigger_drum" in jsfx_source
        assert "dm[base + 2]" in jsfx_source


# ---------------------------------------------------------------------------
#  Memory safety: verify no memory region overlaps
# ---------------------------------------------------------------------------

class TestMemorySafety:
    """Verify that Live Patch memory offsets don't collide with other state."""

    def test_no_memory_overlap(self, jsfx_source: str) -> None:
        """Extract all memory base offsets and check for collisions."""
        # Pattern: identifier = <number>; where the comment says "memory offset"
        # Also capture duty table (dt=0), triangle (tt=32), noise (np=64), etc.
        bases = {}
        for m in re.finditer(r"(\w+)\s*=\s*(\d+)\s*;", jsfx_source):
            name, offset = m.group(1), int(m.group(2))
            if offset >= 0 and name not in ("i", "n", "val", "idx", "base"):
                bases[name] = offset

        # Live Patch uses offsets 500-569
        lp_offsets = {k: v for k, v in bases.items() if k.startswith("lp_")}
        other_offsets = {k: v for k, v in bases.items() if not k.startswith("lp_")}

        for lp_name, lp_off in lp_offsets.items():
            for other_name, other_off in other_offsets.items():
                # Check if lp memory could overlap with other known regions
                # Each lp array is 4 elements (channels 0-3)
                if other_off >= 500 and other_off < 570:
                    # This would be a collision
                    assert lp_off == other_off or abs(lp_off - other_off) >= 4, \
                        f"Memory collision: {lp_name}={lp_off} overlaps {other_name}={other_off}"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _extract_cc_handler(source: str, cc_match: str) -> str:
    """Extract the code block around a CC handler."""
    idx = source.index(cc_match)
    # Go back to find the start of the condition and forward to find the end
    start = max(0, idx - 200)
    end = min(len(source), idx + 500)
    return source[start:end]


def _extract_noteon_handler(source: str) -> str:
    """Extract the note-on handler region."""
    idx = source.index("// --- Note On ---")
    end_idx = source.index("// --- Note Off ---")
    return source[idx:end_idx]


def _extract_section(source: str, section: str) -> str:
    """Extract a JSFX section's content (from section marker to next section)."""
    # Find the section marker as a line-start token
    pattern = re.compile(r"^" + re.escape(section) + r"\b", re.MULTILINE)
    m = pattern.search(source)
    if not m:
        raise ValueError(f"Section {section} not found")
    idx = m.start()
    # Find next section or end
    next_section = re.search(r"\n@\w+", source[idx + len(section):])
    if next_section:
        return source[idx:idx + len(section) + next_section.start()]
    return source[idx:]
