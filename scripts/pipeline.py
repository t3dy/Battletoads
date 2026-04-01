#!/usr/bin/env python3
"""End-to-end NES Music Studio pipeline.

Takes a ROM file and song identifier, runs extraction (when available),
generates MIDI + presets, creates a REAPER project, and validates the output.

Usage:
    python scripts/pipeline.py --rom roms/castlevania.nes --song "Stage 1" --output project.rpp
    python scripts/pipeline.py --rom roms/castlevania.nes --song "Stage 1" --dry-run
    python scripts/pipeline.py --midi studio/midi/nes/castlevania1/cv1s1-6.mid --output project.rpp

Currently a pipeline stub that reports what's real vs what's planned.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTION_DIR = REPO_ROOT / "extraction"
STUDIO_DIR = REPO_ROOT / "studio"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Add scripts to path for generate_project import
sys.path.insert(0, str(SCRIPTS_DIR))


def check_rom(rom_path: Path) -> dict:
    """Check that the ROM exists and attempt driver identification."""
    result = {"exists": False, "driver": None, "driver_status": "not_identified"}

    if not rom_path.exists():
        print(f"  [FAIL] ROM not found: {rom_path}")
        return result

    result["exists"] = True
    print(f"  [OK]   ROM found: {rom_path.name} ({rom_path.stat().st_size} bytes)")

    # Try to identify driver using extraction engine
    try:
        sys.path.insert(0, str(EXTRACTION_DIR / "src"))
        from nesml.static_analysis.driver_identify import identify_driver
        driver = identify_driver(rom_path)
        if driver:
            result["driver"] = driver
            result["driver_status"] = "identified"
            print(f"  [OK]   Driver identified: {driver}")
        else:
            print(f"  [STUB] Driver identification returned no result")
            result["driver_status"] = "no_match"
    except ImportError:
        print(f"  [STUB] Driver identification not yet available (extraction engine not importable)")
        result["driver_status"] = "not_available"
    except Exception as e:
        print(f"  [STUB] Driver identification failed: {e}")
        result["driver_status"] = "error"

    return result


def check_extraction(rom_path: Path, song_name: str) -> dict:
    """Check for existing extracted MIDI and presets."""
    result = {"midi_found": False, "presets_found": False, "midi_path": None, "presets_path": None}

    rom_stem = rom_path.stem.lower().replace(" ", "_").split("(")[0].strip("_")

    # Check for extracted MIDI in extraction/exports/midi/
    midi_dir = EXTRACTION_DIR / "exports" / "midi" / rom_stem
    if midi_dir.exists():
        midi_files = list(midi_dir.glob("*.mid"))
        if midi_files:
            result["midi_found"] = True
            result["midi_path"] = midi_files[0]
            print(f"  [OK]   Extracted MIDI found: {midi_files[0].name}")
        else:
            print(f"  [STUB] MIDI export directory exists but no .mid files")
    else:
        print(f"  [STUB] No extracted MIDI found (extraction not yet run)")

    # Check for song set presets
    song_sets_dir = STUDIO_DIR / "song_sets"
    matches = []
    if song_sets_dir.exists():
        for ss in song_sets_dir.glob("*.json"):
            if rom_stem in ss.stem.lower() or song_name.lower().replace(" ", "_") in ss.stem.lower():
                matches.append(ss)
    if matches:
        result["presets_found"] = True
        result["presets_path"] = matches[0]
        print(f"  [OK]   Song set found: {matches[0].name}")
    else:
        print(f"  [STUB] No matching song set found")

    return result


def find_fallback_midi(rom_path: Path, song_name: str) -> Path | None:
    """Look for community MIDI files as a fallback."""
    rom_stem = rom_path.stem.lower().replace(" ", "_").split("(")[0].strip("_")
    midi_dir = STUDIO_DIR / "midi" / "nes"

    # Search all subdirectories for matching MIDI files
    if midi_dir.exists():
        for mid_file in midi_dir.rglob("*.mid"):
            if rom_stem[:5] in mid_file.parent.name.lower() or rom_stem[:5] in mid_file.stem.lower():
                print(f"  [OK]   Fallback community MIDI: {mid_file.relative_to(STUDIO_DIR)}")
                print(f"         WARNING: Community MIDIs are unreliable (Blunder 14)")
                return mid_file

    print(f"  [FAIL] No MIDI source available (extraction or community)")
    return None


def generate_project(midi_path: Path, output_path: Path, song_set_path: Path | None = None) -> bool:
    """Generate the REAPER project from MIDI."""
    try:
        from generate_project import generate_midi_project
        generate_midi_project(midi_path, output_path, song_set_path)
        return True
    except Exception as e:
        print(f"  [FAIL] Project generation failed: {e}")
        return False


def validate_output(output_path: Path) -> bool:
    """Run validation on the generated project."""
    try:
        from test_rpp_lint import lint_rpp
        sys.path.insert(0, str(REPO_ROOT / "tests"))
        errors = lint_rpp(output_path)
        if errors:
            print(f"  [FAIL] Validation found {len(errors)} error(s):")
            for e in errors:
                print(f"         {e}")
            return False
        else:
            print(f"  [OK]   Validation passed")
            return True
    except Exception as e:
        print(f"  [FAIL] Validation could not run: {e}")
        return False


def run_pipeline(
    rom_path: Path | None,
    song_name: str,
    midi_path: Path | None,
    output_path: Path,
    dry_run: bool = False,
) -> int:
    """Run the full pipeline. Returns 0 on success, 1 on failure."""

    print("=" * 60)
    print("NES Music Studio Pipeline")
    print("=" * 60)

    status = {"real": [], "stubbed": [], "failed": []}

    # Step 1: ROM check
    if rom_path:
        print("\n[Step 1] ROM Check")
        rom_result = check_rom(rom_path)
        if not rom_result["exists"]:
            status["failed"].append("ROM not found")
            print("\nPipeline aborted: ROM not found")
            return 1
        status["real"].append("ROM exists")
        if rom_result["driver_status"] == "identified":
            status["real"].append(f"Driver: {rom_result['driver']}")
        else:
            status["stubbed"].append("Driver identification")

    # Step 2: Check for extracted data
    if rom_path:
        print("\n[Step 2] Extraction Check")
        extract_result = check_extraction(rom_path, song_name)
        if extract_result["midi_found"]:
            midi_path = extract_result["midi_path"]
            status["real"].append("ROM-extracted MIDI")
        else:
            status["stubbed"].append("ROM extraction (using fallback)")

    # Step 3: Fallback to community MIDI
    if midi_path is None and rom_path:
        print("\n[Step 3] Fallback MIDI Search")
        midi_path = find_fallback_midi(rom_path, song_name)
        if midi_path:
            status["real"].append("Community MIDI fallback")
        else:
            status["failed"].append("No MIDI source")
            print("\nPipeline aborted: No MIDI available")
            return 1
    elif midi_path and not midi_path.exists():
        print(f"\n[FAIL] MIDI file not found: {midi_path}")
        return 1

    if midi_path:
        status["real"].append(f"MIDI source: {midi_path.name}")

    if dry_run:
        print("\n[Dry Run] Would generate project, stopping here.")
    else:
        # Step 4: Generate project
        print("\n[Step 4] Project Generation")
        song_set = None
        if rom_path:
            extract_result_local = check_extraction(rom_path, song_name)
            song_set = extract_result_local.get("presets_path")

        success = generate_project(midi_path, output_path, song_set)
        if success:
            status["real"].append("RPP project generated")
        else:
            status["failed"].append("Project generation")
            return 1

        # Step 5: Validate
        print("\n[Step 5] Validation")
        valid = validate_output(output_path)
        if valid:
            status["real"].append("Validation passed")
        else:
            status["failed"].append("Validation")

    # Report
    print("\n" + "=" * 60)
    print("Pipeline Status Report")
    print("=" * 60)
    if status["real"]:
        print("\n  WORKING (real):")
        for item in status["real"]:
            print(f"    + {item}")
    if status["stubbed"]:
        print("\n  STUBBED (planned):")
        for item in status["stubbed"]:
            print(f"    ~ {item}")
    if status["failed"]:
        print("\n  FAILED:")
        for item in status["failed"]:
            print(f"    ! {item}")
        return 1

    print("\n  Result: " + ("DRY RUN OK" if dry_run else "SUCCESS"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="NES Music Studio end-to-end pipeline: ROM -> REAPER project"
    )
    parser.add_argument("--rom", metavar="PATH", help="Path to NES ROM file")
    parser.add_argument("--song", metavar="NAME", default="", help="Song name/identifier")
    parser.add_argument("--midi", metavar="PATH", help="Direct MIDI file (skip extraction)")
    parser.add_argument("--output", "-o", metavar="PATH",
                        default="studio/reaper_projects/pipeline_output.rpp",
                        help="Output .RPP file path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check inputs without generating")

    args = parser.parse_args()

    if not args.rom and not args.midi:
        parser.print_help()
        print("\nError: Provide --rom or --midi")
        return 1

    rom_path = Path(args.rom) if args.rom else None
    midi_path = Path(args.midi) if args.midi else None
    output_path = Path(args.output)

    # Make relative paths absolute from repo root
    if rom_path and not rom_path.is_absolute():
        rom_path = REPO_ROOT / rom_path
    if midi_path and not midi_path.is_absolute():
        midi_path = REPO_ROOT / midi_path
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    return run_pipeline(rom_path, args.song, midi_path, output_path, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
