"""Integration tests for the project generator.

Verifies:
- Blunder 10: Per-track channel mode slider (slider13) set correctly
- Blunder 11: Channel remapping creates files with channels 0-3
- Generated projects pass RPP lint
- MIDI items reference the remapped file path
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import generate_project
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from test_rpp_lint import lint_rpp, _parse_tracks


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _get_slider13_values(rpp_path: Path) -> list[int | None]:
    """Extract slider13 (channel mode) value from each track.

    Slider13 is the 13th value in the slider values line (0-indexed: position 12).
    """
    text = rpp_path.read_text(encoding="utf-8", errors="replace")
    tracks = _parse_tracks(text.splitlines())
    values = []
    for t in tracks:
        for _, fields in t.get("slider_lines", []):
            if len(fields) >= 13:
                val = fields[12]
                try:
                    values.append(int(float(val)))
                except (ValueError, TypeError):
                    values.append(None)
            else:
                values.append(None)
    return values


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

class TestGenericProject:
    """Generate a generic project and validate it passes RPP lint."""

    def test_generic_project_lint(self, tmp_path: Path) -> None:
        from generate_project import generate_generic_project

        out = tmp_path / "test_generic.rpp"
        generate_generic_project(out)

        assert out.exists(), "Generic project was not created"
        errors = lint_rpp(out)
        if errors:
            pytest.fail(
                f"Generic project has lint errors:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_generic_project_has_4_tracks(self, tmp_path: Path) -> None:
        from generate_project import generate_generic_project

        out = tmp_path / "test_generic.rpp"
        generate_generic_project(out)

        text = out.read_text(encoding="utf-8")
        tracks = _parse_tracks(text.splitlines())
        assert len(tracks) == 4, f"Expected 4 tracks, got {len(tracks)}"

    def test_generic_project_track_names(self, tmp_path: Path) -> None:
        from generate_project import generate_generic_project

        out = tmp_path / "test_generic.rpp"
        generate_generic_project(out)

        text = out.read_text(encoding="utf-8")
        tracks = _parse_tracks(text.splitlines())
        names = [t["name"] for t in tracks]
        assert "NES - Pulse 1" in names
        assert "NES - Pulse 2" in names
        assert "NES - Triangle" in names
        assert "NES - Noise / Drums" in names


class TestMidiProject:
    """Generate a MIDI project and validate it."""

    def test_midi_project_lint(self, tmp_path: Path, make_test_midi) -> None:
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        assert out.exists(), "MIDI project was not created"
        errors = lint_rpp(out)
        if errors:
            pytest.fail(
                f"MIDI project has lint errors:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_channel_mode_slider_values(self, tmp_path: Path, make_test_midi) -> None:
        """Blunder 10: Each track must have its own channel mode.

        Track 1 (Pulse 1) = 0, Track 2 (Pulse 2) = 1,
        Track 3 (Triangle) = 2, Track 4 (Noise) = 3
        """
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        values = _get_slider13_values(out)
        expected = [0, 1, 2, 3]
        assert values == expected, (
            f"Channel mode slider13 values: {values}, expected {expected}"
        )

    def test_remapped_midi_created(self, tmp_path: Path, make_test_midi) -> None:
        """Blunder 11: Remapped MIDI file must be created with channels 0-3."""
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        remapped_dir = tmp_path / "midi_remapped"
        assert remapped_dir.exists(), "midi_remapped directory not created"

        remapped_files = list(remapped_dir.glob("*_nes.mid"))
        assert len(remapped_files) >= 1, "No remapped MIDI files found"

    def test_remapped_midi_channels(self, tmp_path: Path, make_test_midi) -> None:
        """Verify remapped MIDI uses channels 0-3 only."""
        import mido
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        remapped_dir = tmp_path / "midi_remapped"
        remapped_files = list(remapped_dir.glob("*_nes.mid"))
        assert remapped_files, "No remapped MIDI files"

        mid = mido.MidiFile(str(remapped_files[0]))
        channels_used = set()
        for track in mid.tracks:
            for msg in track:
                if hasattr(msg, "channel"):
                    channels_used.add(msg.channel)

        assert channels_used.issubset({0, 1, 2, 3}), (
            f"Remapped MIDI uses channels {sorted(channels_used)}, expected subset of {{0, 1, 2, 3}}"
        )

    def test_midi_items_reference_remapped_path(self, tmp_path: Path, make_test_midi) -> None:
        """MIDI items in the RPP must reference the remapped file, not the original."""
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        text = out.read_text(encoding="utf-8")

        # Find all FILE references in SOURCE MIDI blocks
        file_refs = re.findall(r'FILE\s+"([^"]+)"', text)
        assert file_refs, "No FILE references found in MIDI project"

        for ref in file_refs:
            assert "_nes.mid" in ref, (
                f"MIDI item references '{ref}' — should reference remapped '*_nes.mid' file"
            )


class TestMidiProjectWithNonStandardChannels:
    """Test that non-standard channel numbers get remapped correctly."""

    def test_nonstandard_channels_remapped(self, tmp_path: Path, make_test_midi) -> None:
        """Blunder 11: Channels 3, 5, 7 should be remapped to 0, 1, 2."""
        import mido
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[3, 5, 7], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        remapped_dir = tmp_path / "midi_remapped"
        remapped_files = list(remapped_dir.glob("*_nes.mid"))
        assert remapped_files, "No remapped MIDI files"

        mid = mido.MidiFile(str(remapped_files[0]))
        channels_used = set()
        for track in mid.tracks:
            for msg in track:
                if hasattr(msg, "channel"):
                    channels_used.add(msg.channel)

        assert channels_used.issubset({0, 1, 2, 3}), (
            f"Remapped MIDI uses channels {sorted(channels_used)}, expected subset of {{0, 1, 2, 3}}"
        )

    def test_channel_mode_with_3_channels(self, tmp_path: Path, make_test_midi) -> None:
        """3-channel MIDI should still set slider13 for all 4 tracks."""
        from generate_project import generate_midi_project

        midi_path = make_test_midi(channels=[0, 1, 2], notes_per_channel=16)
        out = tmp_path / "test_midi.rpp"
        generate_midi_project(midi_path, out)

        values = _get_slider13_values(out)
        # All 4 tracks should have their own channel mode
        assert len(values) == 4, f"Expected 4 tracks, got {len(values)}"
        assert values == [0, 1, 2, 3], f"Channel modes: {values}, expected [0, 1, 2, 3]"
