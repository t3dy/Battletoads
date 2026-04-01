#!/usr/bin/env python3
"""Validate a REAPER project (.rpp) against the 5 fidelity dimensions.

Checks RPP structure, MIDI CC presence, slider routing, and noise events.
Emits a structured report with sections: routing, pitch_duration,
envelope_cc, timbre_duty, noise_drums, summary.

Usage:
    python scripts/validate_project.py Projects/Super_Mario_Bros/Super_Mario_Bros._01_Running_About_v1.rpp
    python scripts/validate_project.py Projects/Super_Mario_Bros/
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SPECS_DIR = PROJECT_ROOT / "specs"


def load_spec(name):
    path = SPECS_DIR / name
    if not path.exists():
        print(f"WARNING: spec file not found: {path}", file=sys.stderr)
        return None
    with open(path) as f:
        return json.load(f)


RPP_SPEC = load_spec("rpp_fields.json")
CC_SPEC = load_spec("cc_mapping.json")
SLIDER_SPEC = load_spec("console_sliders.json")


# ---------------------------------------------------------------------------
# RPP parsing helpers
# ---------------------------------------------------------------------------

def read_rpp(path):
    """Read an RPP file and return its text content."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def find_rpp_files(path):
    """Given a file or directory, return a list of .rpp paths."""
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".rpp":
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.rpp"))
    return []


def find_midi_files(rpp_path):
    """Extract MIDI file references from an RPP file."""
    text = read_rpp(rpp_path)
    # Look for FILE references with .mid extension
    midi_refs = re.findall(r'FILE\s+"([^"]+\.mid[i]?)"', text, re.IGNORECASE)
    # Also look for bare paths
    midi_refs += re.findall(r'FILE\s+([^\s"]+\.mid[i]?)', text, re.IGNORECASE)
    return list(set(midi_refs))


# ---------------------------------------------------------------------------
# Dimension 1: Routing
# ---------------------------------------------------------------------------

def check_routing(rpp_text):
    """Check RPP structure against rpp_fields.json requirements."""
    results = {"status": "PASS", "issues": [], "checks": []}

    if RPP_SPEC is None:
        results["status"] = "NOT_IMPLEMENTED"
        results["issues"].append("rpp_fields.json not found")
        return results

    # Check required header fields
    for field in RPP_SPEC.get("header_required_fields", []):
        field_name = field.split()[0]
        if field in rpp_text or field_name in rpp_text:
            results["checks"].append(f"PASS: header field '{field_name}' present")
        else:
            results["status"] = "FAIL"
            results["issues"].append(f"Missing header field: {field}")

    # Check required header blocks
    for block in RPP_SPEC.get("header_required_blocks", []):
        if f"<{block}" in rpp_text:
            results["checks"].append(f"PASS: block '<{block}>' present")
        else:
            results["status"] = "FAIL"
            results["issues"].append(f"Missing required block: <{block}>")

    # Check forbidden tokens
    for token in RPP_SPEC.get("forbidden_tokens", []):
        if token in rpp_text:
            results["status"] = "FAIL"
            results["issues"].append(f"Forbidden token found: {token}")
        else:
            results["checks"].append(f"PASS: no forbidden token '{token}'")

    # Check REC field format (must use 5088 for MIDI routing)
    rec_matches = re.findall(r'REC\s+(\d+)\s+(\d+)', rpp_text)
    if not rec_matches:
        results["status"] = "FAIL"
        results["issues"].append("No REC fields found in any track")
    else:
        for armed, input_val in rec_matches:
            if input_val != "5088":
                results["status"] = "FAIL"
                results["issues"].append(
                    f"REC input value is {input_val}, expected 5088 "
                    f"(MIDI all devices all channels)"
                )
            else:
                results["checks"].append(f"PASS: REC uses input 5088 (armed={armed})")

    # Check track required fields
    track_fields = RPP_SPEC.get("track_required_fields", {})
    track_blocks = re.findall(r'<TRACK[^>]*>(.*?)\n  >', rpp_text, re.DOTALL)
    if not track_blocks:
        # Try less strict pattern
        track_count = rpp_text.count("<TRACK")
        if track_count == 0:
            results["status"] = "FAIL"
            results["issues"].append("No TRACK blocks found")
    else:
        for i, block in enumerate(track_blocks):
            for field_name, expected in track_fields.items():
                if field_name not in block:
                    results["status"] = "FAIL"
                    results["issues"].append(
                        f"Track {i}: missing field {field_name}"
                    )

    # Check FXCHAIN presence
    fxchain_count = rpp_text.count("<FXCHAIN")
    track_count = rpp_text.count("<TRACK")
    if track_count > 0 and fxchain_count < track_count:
        results["status"] = "FAIL"
        results["issues"].append(
            f"Only {fxchain_count}/{track_count} tracks have FXCHAIN blocks"
        )
    elif track_count > 0:
        results["checks"].append(
            f"PASS: all {track_count} tracks have FXCHAIN blocks"
        )

    # Check plugin reference
    if "ReapNES" not in rpp_text:
        results["status"] = "FAIL"
        results["issues"].append("No ReapNES plugin reference found")
    else:
        if "ReapNES_Console.jsfx" in rpp_text:
            results["checks"].append("PASS: uses ReapNES_Console.jsfx")
        elif "ReapNES_APU.jsfx" in rpp_text:
            results["checks"].append(
                "WARN: uses ReapNES_APU.jsfx (Console preferred)"
            )

    return results


# ---------------------------------------------------------------------------
# Dimension 2: Pitch / Duration
# ---------------------------------------------------------------------------

def check_pitch_duration(rpp_text, rpp_path):
    """Check MIDI files for note presence. Detailed pitch validation is
    NOT_IMPLEMENTED -- requires mido or equivalent MIDI parser."""
    results = {"status": "NOT_IMPLEMENTED", "issues": [], "checks": []}

    midi_refs = find_midi_files(rpp_path)
    if not midi_refs:
        results["issues"].append("No MIDI file references found in RPP")
        results["status"] = "FAIL"
        return results

    results["checks"].append(f"Found {len(midi_refs)} MIDI reference(s)")

    # Check that referenced MIDI files exist
    rpp_dir = Path(rpp_path).parent
    for ref in midi_refs:
        midi_path = Path(ref)
        if not midi_path.is_absolute():
            midi_path = rpp_dir / ref
        if midi_path.exists():
            size = midi_path.stat().st_size
            results["checks"].append(
                f"PASS: MIDI file exists: {midi_path.name} ({size} bytes)"
            )
        else:
            results["status"] = "FAIL"
            results["issues"].append(f"MIDI file not found: {ref}")

    if results["status"] != "FAIL":
        results["status"] = "NOT_IMPLEMENTED"
        results["issues"].append(
            "Detailed pitch/duration analysis requires mido library"
        )

    return results


# ---------------------------------------------------------------------------
# Dimension 3: Envelope / CC
# ---------------------------------------------------------------------------

def check_envelope_cc(rpp_text, rpp_path):
    """Check MIDI files for CC11 (volume) and CC12 (duty) presence."""
    results = {"status": "NOT_IMPLEMENTED", "issues": [], "checks": []}

    if CC_SPEC is None:
        results["issues"].append("cc_mapping.json not found")
        return results

    midi_refs = find_midi_files(rpp_path)
    if not midi_refs:
        results["issues"].append("No MIDI file references found in RPP")
        results["status"] = "FAIL"
        return results

    # Try to use mido for MIDI inspection
    try:
        import mido

        rpp_dir = Path(rpp_path).parent
        for ref in midi_refs:
            midi_path = Path(ref)
            if not midi_path.is_absolute():
                midi_path = rpp_dir / ref
            if not midi_path.exists():
                continue

            mid = mido.MidiFile(str(midi_path))
            cc11_count = 0
            cc12_count = 0
            note_count = 0

            for track in mid.tracks:
                for msg in track:
                    if msg.type == "control_change":
                        if msg.control == 11:
                            cc11_count += 1
                        elif msg.control == 12:
                            cc12_count += 1
                    elif msg.type == "note_on":
                        note_count += 1

            results["checks"].append(
                f"{midi_path.name}: {note_count} notes, "
                f"{cc11_count} CC11 (volume), {cc12_count} CC12 (duty)"
            )

            if cc11_count == 0:
                results["status"] = "FAIL"
                results["issues"].append(
                    f"{midi_path.name}: no CC11 volume automation found"
                )
            else:
                if results["status"] != "FAIL":
                    results["status"] = "PASS"

            if cc12_count == 0:
                results["checks"].append(
                    f"INFO: {midi_path.name}: no CC12 duty messages "
                    f"(may be correct for some games)"
                )

        if results["status"] == "NOT_IMPLEMENTED" and midi_refs:
            results["status"] = "PASS"

    except ImportError:
        results["status"] = "NOT_IMPLEMENTED"
        results["issues"].append(
            "mido not installed -- install with: pip install mido"
        )

    return results


# ---------------------------------------------------------------------------
# Dimension 4: Timbre / Duty (slider config)
# ---------------------------------------------------------------------------

def check_timbre_duty(rpp_text):
    """Check slider values for correct channel mode routing."""
    results = {"status": "PASS", "issues": [], "checks": []}

    if SLIDER_SPEC is None:
        results["status"] = "NOT_IMPLEMENTED"
        results["issues"].append("console_sliders.json not found")
        return results

    # Extract JS plugin slider lines from RPP
    # Format: <JS "plugin" ""\n  slider_values_line
    js_blocks = re.findall(
        r'<JS\s+"([^"]+)"\s+"[^"]*"\s*\n\s+(.+)',
        rpp_text
    )

    if not js_blocks:
        results["status"] = "FAIL"
        results["issues"].append("No JS plugin blocks found")
        return results

    channel_mode_index = None
    keyboard_mode_index = None
    for slider_info in SLIDER_SPEC.get("sliders", []):
        if slider_info["name"] == "Channel Mode":
            channel_mode_index = slider_info["index"]
        if slider_info["name"] == "Keyboard Mode":
            keyboard_mode_index = slider_info["index"]

    for plugin_name, slider_line in js_blocks:
        values = slider_line.strip().split()
        results["checks"].append(
            f"Plugin: {plugin_name}, {len(values)} slider values"
        )

        if channel_mode_index is not None and len(values) > channel_mode_index:
            ch_mode = values[channel_mode_index]
            try:
                ch_val = int(float(ch_mode))
                mode_labels = SLIDER_SPEC.get("channel_mode_values", {})
                label = next(
                    (k for k, v in mode_labels.items() if v == ch_val),
                    f"unknown({ch_val})"
                )
                results["checks"].append(f"Channel Mode: {ch_val} ({label})")

                # In multi-track projects, Full APU (4) should not be used
                track_count = rpp_text.count("<TRACK")
                if track_count > 1 and ch_val == 4:
                    results["status"] = "WARN"
                    results["issues"].append(
                        "Multi-track project uses Full APU (4) channel mode. "
                        "Each track should use its own channel mode (0-3)."
                    )
            except (ValueError, IndexError):
                pass

        if keyboard_mode_index is not None and len(values) > keyboard_mode_index:
            kb_mode = values[keyboard_mode_index]
            try:
                kb_val = int(float(kb_mode))
                if kb_val == 1:
                    results["checks"].append("PASS: Keyboard Mode ON")
                else:
                    results["status"] = "WARN"
                    results["issues"].append(
                        "Keyboard Mode is OFF -- MIDI input may not work"
                    )
            except (ValueError, IndexError):
                pass

        # Check enable flags for each channel
        enable_indices = {
            "P1 Enable": 2,
            "P2 Enable": 10,
            "Tri Enable": 16,
            "Noise Enable": 22,
        }
        for name, idx in enable_indices.items():
            if len(values) > idx:
                try:
                    val = int(float(values[idx]))
                    if val == 1:
                        results["checks"].append(f"PASS: {name} = ON")
                    else:
                        results["checks"].append(f"INFO: {name} = OFF")
                except (ValueError, IndexError):
                    pass

    return results


# ---------------------------------------------------------------------------
# Dimension 5: Noise / Drums
# ---------------------------------------------------------------------------

def check_noise_drums(rpp_text, rpp_path):
    """Check that noise track has events."""
    results = {"status": "NOT_IMPLEMENTED", "issues": [], "checks": []}

    # Check that there is a noise track in the RPP
    noise_track = bool(
        re.search(r'NAME\s+"[^"]*[Nn]oise[^"]*"', rpp_text)
        or re.search(r'NAME\s+"[^"]*[Dd]rum[^"]*"', rpp_text)
    )

    if noise_track:
        results["checks"].append("PASS: Noise/Drum track found in RPP")
    else:
        results["checks"].append(
            "INFO: No dedicated noise/drum track name found"
        )

    # Try mido for deeper check
    try:
        import mido

        midi_refs = find_midi_files(rpp_path)
        rpp_dir = Path(rpp_path).parent
        for ref in midi_refs:
            midi_path = Path(ref)
            if not midi_path.is_absolute():
                midi_path = rpp_dir / ref
            if not midi_path.exists():
                continue

            mid = mido.MidiFile(str(midi_path))
            # Check channel 9 (noise/drums, 0-indexed) or last track
            noise_notes = 0
            for track in mid.tracks:
                for msg in track:
                    if msg.type == "note_on" and msg.channel == 9:
                        noise_notes += 1

            if noise_notes > 0:
                results["status"] = "PASS"
                results["checks"].append(
                    f"PASS: {noise_notes} noise/drum events on channel 10"
                )
            else:
                # Check last track regardless of channel
                if len(mid.tracks) >= 5:
                    last_track_notes = sum(
                        1 for msg in mid.tracks[4]
                        if msg.type == "note_on"
                    )
                    if last_track_notes > 0:
                        results["status"] = "PASS"
                        results["checks"].append(
                            f"PASS: {last_track_notes} events in track 5 "
                            f"(noise)"
                        )
                    else:
                        results["checks"].append(
                            "INFO: no events in track 5"
                        )

        if results["status"] == "NOT_IMPLEMENTED":
            results["issues"].append(
                "Could not confirm noise events in MIDI"
            )

    except ImportError:
        results["issues"].append(
            "mido not installed -- install with: pip install mido"
        )

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def validate_rpp(rpp_path):
    """Run all 5 dimension checks on a single RPP file."""
    rpp_path = Path(rpp_path)
    rpp_text = read_rpp(rpp_path)

    report = {
        "file": str(rpp_path),
        "routing": check_routing(rpp_text),
        "pitch_duration": check_pitch_duration(rpp_text, rpp_path),
        "envelope_cc": check_envelope_cc(rpp_text, rpp_path),
        "timbre_duty": check_timbre_duty(rpp_text),
        "noise_drums": check_noise_drums(rpp_text, rpp_path),
    }

    # Summary
    statuses = {
        dim: report[dim]["status"]
        for dim in [
            "routing", "pitch_duration", "envelope_cc",
            "timbre_duty", "noise_drums"
        ]
    }
    fail_count = sum(1 for s in statuses.values() if s == "FAIL")
    pass_count = sum(1 for s in statuses.values() if s == "PASS")
    not_impl = sum(1 for s in statuses.values() if s == "NOT_IMPLEMENTED")

    report["summary"] = {
        "pass": pass_count,
        "fail": fail_count,
        "not_implemented": not_impl,
        "overall": "FAIL" if fail_count > 0 else (
            "PASS" if not_impl == 0 else "PARTIAL"
        ),
        "statuses": statuses,
    }

    return report


def print_report(report):
    """Print a human-readable validation report."""
    print("=" * 70)
    print(f"VALIDATION REPORT: {report['file']}")
    print("=" * 70)

    dimensions = [
        ("routing", "1. Routing"),
        ("pitch_duration", "2. Pitch / Duration"),
        ("envelope_cc", "3. Envelope / CC"),
        ("timbre_duty", "4. Timbre / Duty"),
        ("noise_drums", "5. Noise / Drums"),
    ]

    for key, label in dimensions:
        dim = report[key]
        status = dim["status"]
        status_icon = {
            "PASS": "[PASS]",
            "FAIL": "[FAIL]",
            "WARN": "[WARN]",
            "NOT_IMPLEMENTED": "[----]",
        }.get(status, f"[{status}]")

        print(f"\n{status_icon} {label}")

        for check in dim.get("checks", []):
            print(f"  + {check}")
        for issue in dim.get("issues", []):
            print(f"  ! {issue}")

    # Summary
    summary = report["summary"]
    print("\n" + "=" * 70)
    print(
        f"SUMMARY: {summary['overall']}  "
        f"({summary['pass']} pass, {summary['fail']} fail, "
        f"{summary['not_implemented']} not implemented)"
    )
    for dim, status in summary["statuses"].items():
        print(f"  {dim}: {status}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Validate REAPER projects against 5 fidelity dimensions."
    )
    parser.add_argument(
        "path",
        help="Path to an RPP file or a game directory in Projects/"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output report as JSON instead of human-readable text"
    )
    args = parser.parse_args()

    rpp_files = find_rpp_files(args.path)
    if not rpp_files:
        print(f"ERROR: No .rpp files found at: {args.path}", file=sys.stderr)
        sys.exit(1)

    all_reports = []
    for rpp_file in rpp_files:
        report = validate_rpp(rpp_file)
        all_reports.append(report)

    if args.json:
        print(json.dumps(all_reports, indent=2))
    else:
        for report in all_reports:
            print_report(report)
            if len(all_reports) > 1:
                print()

    # Exit with failure code if any report has failures
    if any(r["summary"]["overall"] == "FAIL" for r in all_reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
