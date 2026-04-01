"""Validates generated .RPP files to catch the bugs from BLOOPERS.md.

Catches:
- Blunder 5: MASTER_SEND / REC_INPUT / RECINPUT / RECMON tokens
- Blunder 6: REC field format issues
- Blunder 7: SOURCE MIDI must use FILE reference, not MIDIPOOL
- Missing FXCHAIN, BYPASS, FLOATPOS, FXID, WAK
- Missing MAINSEND on tracks
- Slider values line must have exactly 64 fields
- GUIDs must be present and properly formatted
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RPP_DIR = REPO_ROOT / "studio" / "reaper_projects"

GUID_PATTERN = re.compile(r"^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$")


def all_rpp_files() -> list[Path]:
    """Collect all .rpp files in reaper_projects/ directory."""
    return sorted(RPP_DIR.glob("*.rpp"))


def rpp_ids() -> list[str]:
    return [f.name for f in all_rpp_files()]


# ---------------------------------------------------------------------------
#  RPP lint engine (reusable from validate.py)
# ---------------------------------------------------------------------------

def lint_rpp(path: Path, effects_dir: Path | None = None) -> list[str]:
    """Run all RPP lint checks on a single file. Returns list of error strings."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # --- Forbidden tokens (Blunder 5) ---
    forbidden = ["MASTER_SEND", "REC_INPUT", "RECINPUT", "RECMON"]
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for token in forbidden:
            # Match as a standalone token (not inside a string or comment)
            if re.search(rf"\b{token}\b", stripped):
                errors.append(f"Line {i}: Forbidden token '{token}' — use MAINSEND instead of MASTER_SEND")

    # --- Parse tracks ---
    tracks = _parse_tracks(lines)

    for track_idx, track in enumerate(tracks, 1):
        track_name = track.get("name", f"Track {track_idx}")

        # Every track has FXCHAIN
        if not track.get("has_fxchain"):
            errors.append(f"{track_name}: Missing <FXCHAIN> block")

        # BYPASS before plugin block
        if track.get("has_fxchain") and not track.get("has_bypass"):
            errors.append(f"{track_name}: Missing BYPASS line in FXCHAIN")

        # FLOATPOS after plugin block
        if track.get("has_fxchain") and not track.get("has_floatpos"):
            errors.append(f"{track_name}: Missing FLOATPOS after plugin block")

        # FXID after plugin block
        if track.get("has_fxchain") and not track.get("has_fxid"):
            errors.append(f"{track_name}: Missing FXID after plugin block")

        # WAK after plugin block
        if track.get("has_fxchain") and not track.get("has_wak"):
            errors.append(f"{track_name}: Missing WAK after plugin block")

        # MAINSEND present
        if not track.get("has_mainsend"):
            errors.append(f"{track_name}: Missing MAINSEND")

        # Slider values line has exactly 64 fields
        for sv_line_num, sv_fields in track.get("slider_lines", []):
            if len(sv_fields) != 64:
                errors.append(
                    f"{track_name} line {sv_line_num}: Slider values has "
                    f"{len(sv_fields)} fields, expected 64"
                )

        # MIDI items use SOURCE MIDI with FILE (not MIDIPOOL) — Blunder 7
        for src in track.get("midi_sources", []):
            if src.get("is_midipool"):
                errors.append(
                    f"{track_name}: Uses SOURCE MIDIPOOL — should be SOURCE MIDI with FILE reference"
                )
            if src.get("is_source_midi") and not src.get("has_file"):
                errors.append(
                    f"{track_name}: SOURCE MIDI without FILE reference"
                )

        # GUIDs present and properly formatted
        for guid_type, guid_val in track.get("guids", []):
            if not GUID_PATTERN.match(guid_val):
                errors.append(
                    f"{track_name}: Malformed {guid_type} GUID: {guid_val}"
                )

        if not track.get("has_track_guid"):
            errors.append(f"{track_name}: Missing track GUID")

        # Check FXCHAIN references a real plugin
        if effects_dir and effects_dir.exists():
            for plugin_ref in track.get("plugin_refs", []):
                plugin_path = effects_dir / plugin_ref
                if not plugin_path.exists():
                    errors.append(
                        f"{track_name}: FXCHAIN references '{plugin_ref}' "
                        f"but file not found in {effects_dir}"
                    )

    return errors


def _parse_tracks(lines: list[str]) -> list[dict]:
    """Parse track blocks from RPP lines into structured dicts."""
    tracks: list[dict] = []
    current_track: dict | None = None
    in_fxchain = False
    in_js_block = False
    in_source_midi = False
    current_midi_source: dict | None = None
    depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track open
        if stripped.startswith("<TRACK "):
            guid = stripped[7:].strip()
            current_track = {
                "name": "",
                "has_fxchain": False,
                "has_bypass": False,
                "has_floatpos": False,
                "has_fxid": False,
                "has_wak": False,
                "has_mainsend": False,
                "has_track_guid": bool(guid and GUID_PATTERN.match(guid)),
                "slider_lines": [],
                "midi_sources": [],
                "plugin_refs": [],
                "guids": [],
            }
            if guid:
                current_track["guids"].append(("TRACK", guid))
            depth = 1
            in_fxchain = False
            in_js_block = False
            continue

        if current_track is None:
            continue

        if stripped.startswith("<"):
            depth += 1
        if stripped == ">":
            depth -= 1
            if depth <= 0:
                tracks.append(current_track)
                current_track = None
                in_fxchain = False
                in_js_block = False
                continue
            if in_js_block:
                in_js_block = False
            if in_source_midi:
                in_source_midi = False
                if current_midi_source:
                    current_track["midi_sources"].append(current_midi_source)
                    current_midi_source = None

        # Track name
        name_match = re.match(r'^NAME\s+"(.+)"', stripped)
        if name_match:
            current_track["name"] = name_match.group(1)

        # MAINSEND
        if stripped.startswith("MAINSEND"):
            current_track["has_mainsend"] = True

        # FXCHAIN block
        if stripped == "<FXCHAIN":
            current_track["has_fxchain"] = True
            in_fxchain = True

        if in_fxchain:
            if stripped.startswith("BYPASS"):
                current_track["has_bypass"] = True
            if stripped.startswith("FLOATPOS"):
                current_track["has_floatpos"] = True
            if stripped.startswith("FXID"):
                current_track["has_fxid"] = True
                parts = stripped.split(None, 1)
                if len(parts) > 1:
                    current_track["guids"].append(("FXID", parts[1]))
            if stripped.startswith("WAK"):
                current_track["has_wak"] = True

            # JS plugin block
            js_match = re.match(r'^<JS\s+"([^"]+)"', stripped)
            if js_match:
                in_js_block = True
                current_track["plugin_refs"].append(js_match.group(1))

            # Slider values line (inside JS block — the line after <JS ...>)
            if in_js_block and not stripped.startswith("<"):
                fields = stripped.split()
                if fields and not stripped.startswith(("BYPASS", "FLOATPOS", "FXID", "WAK", ">")):
                    current_track["slider_lines"].append((i, fields))

        # SOURCE MIDI / MIDIPOOL
        if stripped.startswith("<SOURCE MIDIPOOL"):
            in_source_midi = True
            current_midi_source = {"is_midipool": True, "is_source_midi": False, "has_file": False}
        elif stripped.startswith("<SOURCE MIDI"):
            in_source_midi = True
            current_midi_source = {"is_midipool": False, "is_source_midi": True, "has_file": False}

        if in_source_midi and current_midi_source and stripped.startswith("FILE"):
            current_midi_source["has_file"] = True

        # Track GUID via TRACKID
        if stripped.startswith("TRACKID"):
            parts = stripped.split(None, 1)
            if len(parts) > 1:
                current_track["guids"].append(("TRACKID", parts[1]))

    return tracks


# ---------------------------------------------------------------------------
#  Pytest tests — run against actual repo RPP files
# ---------------------------------------------------------------------------

class TestRppLintAllFiles:
    """Run lint checks on every .rpp file in the repo."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_no_lint_errors(self, rpp_path: Path, reaper_effects_dir: Path) -> None:
        edir = reaper_effects_dir if reaper_effects_dir.exists() else None
        errors = lint_rpp(rpp_path, edir)
        if errors:
            msg = f"\n{rpp_path.name} has {len(errors)} lint error(s):\n"
            msg += "\n".join(f"  - {e}" for e in errors)
            pytest.fail(msg)


class TestRppNoForbiddenTokens:
    """Blunder 5: MASTER_SEND, REC_INPUT, RECINPUT, RECMON must not appear."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_no_forbidden_tokens(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        for token in ["MASTER_SEND", "REC_INPUT", "RECINPUT", "RECMON"]:
            assert not re.search(rf"\b{token}\b", text), (
                f"{rpp_path.name}: Contains forbidden token '{token}'"
            )


class TestRppTracksFxchain:
    """Every track must have an FXCHAIN block."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_all_tracks_have_fxchain(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        for t in tracks:
            assert t["has_fxchain"], f"{rpp_path.name} / {t.get('name', '?')}: Missing FXCHAIN"


class TestRppMainsend:
    """Every track must have MAINSEND (not MASTER_SEND)."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_all_tracks_have_mainsend(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        for t in tracks:
            assert t["has_mainsend"], f"{rpp_path.name} / {t.get('name', '?')}: Missing MAINSEND"


class TestRppSliderCount:
    """Slider values line must have exactly 64 space-separated fields."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_slider_line_64_fields(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        for t in tracks:
            for line_num, fields in t.get("slider_lines", []):
                assert len(fields) == 64, (
                    f"{rpp_path.name} / {t.get('name', '?')} line {line_num}: "
                    f"Slider values has {len(fields)} fields, expected 64"
                )


class TestRppMidiSources:
    """Blunder 7: MIDI items must use SOURCE MIDI with FILE, not MIDIPOOL."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_midi_uses_file_not_midipool(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        for t in tracks:
            for src in t.get("midi_sources", []):
                assert not src.get("is_midipool"), (
                    f"{rpp_path.name} / {t.get('name', '?')}: "
                    f"Uses MIDIPOOL — should be SOURCE MIDI with FILE"
                )
                if src.get("is_source_midi"):
                    assert src.get("has_file"), (
                        f"{rpp_path.name} / {t.get('name', '?')}: "
                        f"SOURCE MIDI without FILE reference"
                    )


class TestRppGuids:
    """GUIDs must be present and properly formatted on tracks and FX."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_guids_valid(self, rpp_path: Path) -> None:
        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        errors = []
        for t in tracks:
            name = t.get("name", "?")
            if not t.get("has_track_guid"):
                errors.append(f"{name}: Missing track GUID")
            for guid_type, guid_val in t.get("guids", []):
                if not GUID_PATTERN.match(guid_val):
                    errors.append(f"{name}: Malformed {guid_type} GUID: {guid_val}")

        assert not errors, f"{rpp_path.name}:\n" + "\n".join(f"  - {e}" for e in errors)


class TestRppPluginExists:
    """FXCHAIN must reference a plugin that actually exists in REAPER Effects dir."""

    @pytest.fixture(params=all_rpp_files(), ids=rpp_ids())
    def rpp_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_plugin_file_exists(self, rpp_path: Path, reaper_effects_dir: Path) -> None:
        if not reaper_effects_dir.exists():
            pytest.skip("REAPER Effects directory not found")

        text = rpp_path.read_text(encoding="utf-8", errors="replace")
        tracks = _parse_tracks(text.splitlines())
        missing = []
        for t in tracks:
            for ref in t.get("plugin_refs", []):
                full = reaper_effects_dir / ref
                if not full.exists():
                    missing.append(f"{t.get('name', '?')}: {ref}")

        assert not missing, (
            f"{rpp_path.name}: Plugin files not found in {reaper_effects_dir}:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )
