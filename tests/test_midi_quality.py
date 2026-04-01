"""Validates MIDI files for NES suitability before project generation.

Catches:
- Blunder 11: VGMusic MIDIs with random channel numbers
- Blunder 13: Fan transcriptions with too many channels
- Blunder 14: Classical music needing 2-3 voices for NES

Quality ratings:
  PERFECT — 2-4 channels, good register separation, drums on ch9 if present
  GOOD    — 2-4 channels, moderate register separation
  OK      — 5-6 channels, or low separation
  BAD     — >6 channels, or all channels in same register
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
#  MIDI quality engine (reusable from validate.py)
# ---------------------------------------------------------------------------

def analyze_midi_quality(path: Path) -> dict:
    """Analyze a MIDI file for NES suitability.

    Returns a dict with:
        channels: dict of channel -> {note_count, note_min, note_max, note_avg, is_drum}
        channel_count: int
        drum_channel: int | None
        avg_separation: float (average semitone distance between channels)
        rating: str (PERFECT/GOOD/OK/BAD)
        issues: list[str]
    """
    import mido

    try:
        mid = mido.MidiFile(str(path))
    except Exception as exc:
        return {
            "channels": {},
            "channel_count": 0,
            "drum_channel": None,
            "avg_separation": 0.0,
            "rating": "BAD",
            "issues": [f"Failed to parse MIDI: {exc}"],
        }

    channel_stats: dict[int, dict] = {}
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                if ch not in channel_stats:
                    channel_stats[ch] = {
                        "notes": [],
                        "note_count": 0,
                        "is_drum": ch == 9,
                    }
                channel_stats[ch]["notes"].append(msg.note)
                channel_stats[ch]["note_count"] += 1

    for ch, stats in channel_stats.items():
        if stats["notes"]:
            stats["note_min"] = min(stats["notes"])
            stats["note_max"] = max(stats["notes"])
            stats["note_avg"] = sum(stats["notes"]) / len(stats["notes"])
        else:
            stats["note_min"] = 0
            stats["note_max"] = 0
            stats["note_avg"] = 0

    n_channels = len(channel_stats)
    drum_channel = next((ch for ch, s in channel_stats.items() if s["is_drum"]), None)
    melodic = {ch: s for ch, s in channel_stats.items() if not s["is_drum"]}

    # Calculate average register separation between melodic channels
    avg_separation = 0.0
    melodic_avgs = sorted([s["note_avg"] for s in melodic.values()])
    if len(melodic_avgs) >= 2:
        separations = [melodic_avgs[i + 1] - melodic_avgs[i] for i in range(len(melodic_avgs) - 1)]
        avg_separation = sum(separations) / len(separations)

    # Determine rating and issues
    issues: list[str] = []

    if n_channels > 6:
        rating = "BAD"
        issues.append(f"Too many channels ({n_channels}) — NES has 4 channels max")
    elif n_channels > 4:
        rating = "OK"
        issues.append(f"{n_channels} channels — NES only has 4, some will be dropped")
    elif avg_separation < 6 and len(melodic_avgs) >= 2:
        if n_channels > 4:
            rating = "BAD"
            issues.append(f"Low register separation ({avg_separation:.1f} semitones avg) with {n_channels} channels")
        else:
            rating = "OK"
            issues.append(f"Low register separation ({avg_separation:.1f} semitones avg) — channels may sound muddy")
    elif n_channels <= 4 and avg_separation >= 12:
        rating = "PERFECT"
    elif n_channels <= 4 and avg_separation >= 6:
        rating = "GOOD"
    elif n_channels <= 2:
        rating = "PERFECT"
    else:
        rating = "GOOD"

    # Warn about drum channel
    if drum_channel is not None and drum_channel != 9:
        issues.append(f"Drums on non-standard channel {drum_channel} (expected ch9)")

    # Clean up raw notes from stats to save memory
    clean_stats = {}
    for ch, s in channel_stats.items():
        clean_stats[ch] = {k: v for k, v in s.items() if k != "notes"}

    return {
        "channels": clean_stats,
        "channel_count": n_channels,
        "drum_channel": drum_channel,
        "avg_separation": avg_separation,
        "rating": rating,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
#  Collect MIDI files
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
MIDI_DIR = REPO_ROOT / "studio" / "midi"


def all_midi_files() -> list[Path]:
    """Collect all .mid files recursively."""
    return sorted(MIDI_DIR.rglob("*.mid"))


def midi_ids() -> list[str]:
    return [str(f.relative_to(MIDI_DIR)) for f in all_midi_files()]


# ---------------------------------------------------------------------------
#  Pytest tests
# ---------------------------------------------------------------------------

class TestMidiChannelCount:
    """Flag MIDIs with > 6 channels as BAD."""

    @pytest.fixture(params=all_midi_files(), ids=midi_ids())
    def midi_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_channel_count_not_excessive(self, midi_path: Path) -> None:
        result = analyze_midi_quality(midi_path)
        if result["channel_count"] > 6:
            pytest.fail(
                f"{midi_path.name}: {result['channel_count']} channels — "
                f"rated BAD for NES (max useful: 4)"
            )


class TestMidiChannelCountWarning:
    """Warn (but don't fail) for > 4 channels."""

    @pytest.fixture(params=all_midi_files(), ids=midi_ids())
    def midi_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_channel_count_warning(self, midi_path: Path) -> None:
        result = analyze_midi_quality(midi_path)
        if result["channel_count"] > 4:
            import warnings
            warnings.warn(
                f"{midi_path.name}: {result['channel_count']} channels "
                f"(NES has 4) — some will be dropped",
                stacklevel=1,
            )


class TestMidiRegisterSeparation:
    """Flag MIDIs where all channels occupy the same register."""

    @pytest.fixture(params=all_midi_files(), ids=midi_ids())
    def midi_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_register_separation(self, midi_path: Path) -> None:
        result = analyze_midi_quality(midi_path)
        melodic = {ch: s for ch, s in result["channels"].items() if not s["is_drum"]}
        if len(melodic) < 2:
            pytest.skip("Single channel — separation N/A")

        if result["avg_separation"] < 6 and result["channel_count"] > 4:
            pytest.fail(
                f"{midi_path.name}: Average register separation is only "
                f"{result['avg_separation']:.1f} semitones with {result['channel_count']} channels "
                f"— will sound muddy through NES"
            )


class TestMidiDrumChannel:
    """Identify drum channel and verify it's ch9 (GM standard)."""

    @pytest.fixture(params=all_midi_files(), ids=midi_ids())
    def midi_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_drum_channel_standard(self, midi_path: Path) -> None:
        result = analyze_midi_quality(midi_path)
        drum_ch = result["drum_channel"]
        # Only report, don't fail — many valid MIDIs have no drums
        if drum_ch is not None and drum_ch != 9:
            import warnings
            warnings.warn(
                f"{midi_path.name}: Drums detected on channel {drum_ch} "
                f"(standard is ch9)",
                stacklevel=1,
            )


class TestMidiQualityRating:
    """Every MIDI should get a quality rating without errors."""

    @pytest.fixture(params=all_midi_files(), ids=midi_ids())
    def midi_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_quality_rating_assigned(self, midi_path: Path) -> None:
        result = analyze_midi_quality(midi_path)
        assert result["rating"] in ("PERFECT", "GOOD", "OK", "BAD"), (
            f"{midi_path.name}: Invalid rating '{result['rating']}'"
        )


class TestSyntheticMidi:
    """Test with a programmatically generated MIDI."""

    def test_4_channel_midi_is_good_or_perfect(self, make_test_midi) -> None:
        midi_path = make_test_midi(channels=[0, 1, 2, 9], notes_per_channel=16)
        result = analyze_midi_quality(midi_path)
        assert result["channel_count"] == 4
        assert result["rating"] in ("PERFECT", "GOOD"), (
            f"4-channel test MIDI rated {result['rating']}, expected PERFECT or GOOD"
        )
        assert result["drum_channel"] == 9

    def test_many_channel_midi_is_bad(self, make_test_midi) -> None:
        midi_path = make_test_midi(channels=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        result = analyze_midi_quality(midi_path)
        assert result["channel_count"] == 10
        assert result["rating"] == "BAD"

    def test_2_channel_midi_is_perfect(self, make_test_midi) -> None:
        midi_path = make_test_midi(channels=[0, 1], notes_per_channel=16)
        result = analyze_midi_quality(midi_path)
        assert result["channel_count"] == 2
        assert result["rating"] == "PERFECT"
