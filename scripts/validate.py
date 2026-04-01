#!/usr/bin/env python3
"""Standalone validation CLI for ReapNES Studio.

Runs JSFX lint, RPP lint, and MIDI quality checks without pytest.

Usage:
    python scripts/validate.py --jsfx          # Lint all JSFX files
    python scripts/validate.py --rpp           # Lint all RPP files
    python scripts/validate.py --midi          # Quality-check all MIDI files
    python scripts/validate.py --all           # Run everything
    python scripts/validate.py --jsfx --rpp    # Combine flags

Returns non-zero exit code on any failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
#  Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
JSFX_DIR = REPO_ROOT / "studio" / "jsfx"
RPP_DIR = REPO_ROOT / "studio" / "reaper_projects"
MIDI_DIR = REPO_ROOT / "studio" / "midi"
TESTS_DIR = REPO_ROOT / "tests"

# Force UTF-8 output on Windows to handle Unicode in error messages
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add tests/ to path so we can import lint engines
sys.path.insert(0, str(TESTS_DIR))


# ---------------------------------------------------------------------------
#  JSFX validation
# ---------------------------------------------------------------------------

def validate_jsfx() -> tuple[int, int]:
    """Lint all .jsfx files. Returns (pass_count, fail_count)."""
    from test_jsfx_lint import lint_jsfx

    files = sorted(JSFX_DIR.glob("*.jsfx"))
    if not files:
        print("  No .jsfx files found.")
        return 0, 0

    passed = 0
    failed = 0

    for path in files:
        errors = lint_jsfx(path)
        if errors:
            failed += 1
            print(f"  FAIL  {path.name}")
            for e in errors:
                print(f"        {e}")
        else:
            passed += 1
            print(f"  PASS  {path.name}")

    return passed, failed


# ---------------------------------------------------------------------------
#  RPP validation
# ---------------------------------------------------------------------------

def validate_rpp() -> tuple[int, int]:
    """Lint all .rpp files. Returns (pass_count, fail_count)."""
    from test_rpp_lint import lint_rpp

    files = sorted(RPP_DIR.glob("*.rpp"))
    if not files:
        print("  No .rpp files found.")
        return 0, 0

    # Resolve REAPER Effects dir
    appdata = os.environ.get("APPDATA", "")
    effects_dir = Path(appdata) / "REAPER" / "Effects" if appdata else None
    if effects_dir and not effects_dir.exists():
        effects_dir = None

    passed = 0
    failed = 0

    for path in files:
        errors = lint_rpp(path, effects_dir)
        if errors:
            failed += 1
            print(f"  FAIL  {path.name}")
            for e in errors:
                print(f"        {e}")
        else:
            passed += 1
            print(f"  PASS  {path.name}")

    return passed, failed


# ---------------------------------------------------------------------------
#  MIDI validation
# ---------------------------------------------------------------------------

def validate_midi() -> tuple[int, int]:
    """Quality-check all MIDI files. Returns (pass_count, fail_count).

    BAD-rated files count as failures.
    """
    from test_midi_quality import analyze_midi_quality

    files = sorted(MIDI_DIR.rglob("*.mid"))
    if not files:
        print("  No .mid files found.")
        return 0, 0

    passed = 0
    failed = 0
    ratings: dict[str, list[str]] = {"PERFECT": [], "GOOD": [], "OK": [], "BAD": []}

    for path in files:
        try:
            result = analyze_midi_quality(path)
        except Exception as exc:
            failed += 1
            print(f"  ERROR {path.relative_to(MIDI_DIR)}  — {exc}")
            continue

        rating = result["rating"]
        rel = str(path.relative_to(MIDI_DIR))
        ratings[rating].append(rel)

        ch_count = result["channel_count"]
        sep = result["avg_separation"]
        issues = result["issues"]

        status = "FAIL" if rating == "BAD" else "PASS"
        if rating == "BAD":
            failed += 1
        else:
            passed += 1

        detail = f"ch={ch_count} sep={sep:.1f}"
        if issues:
            detail += f"  [{'; '.join(issues)}]"
        print(f"  {status}  {rating:<8s} {rel:<50s} {detail}")

    # Print summary by rating
    print()
    for r in ("PERFECT", "GOOD", "OK", "BAD"):
        count = len(ratings[r])
        if count:
            print(f"  {r}: {count} file(s)")

    return passed, failed


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ReapNES Studio files (JSFX, RPP, MIDI)"
    )
    parser.add_argument("--jsfx", action="store_true", help="Lint all JSFX files")
    parser.add_argument("--rpp", action="store_true", help="Lint all RPP files")
    parser.add_argument("--midi", action="store_true", help="Quality-check all MIDI files")
    parser.add_argument("--all", action="store_true", help="Run all validations")
    args = parser.parse_args()

    if not any([args.jsfx, args.rpp, args.midi, args.all]):
        parser.print_help()
        return 1

    run_jsfx = args.jsfx or args.all
    run_rpp = args.rpp or args.all
    run_midi = args.midi or args.all

    total_pass = 0
    total_fail = 0

    if run_jsfx:
        print("=" * 60)
        print("JSFX LINT")
        print("=" * 60)
        p, f = validate_jsfx()
        total_pass += p
        total_fail += f
        print()

    if run_rpp:
        print("=" * 60)
        print("RPP LINT")
        print("=" * 60)
        p, f = validate_rpp()
        total_pass += p
        total_fail += f
        print()

    if run_midi:
        print("=" * 60)
        print("MIDI QUALITY")
        print("=" * 60)
        p, f = validate_midi()
        total_pass += p
        total_fail += f
        print()

    # Summary
    print("=" * 60)
    total = total_pass + total_fail
    if total_fail == 0:
        print(f"ALL PASSED: {total_pass}/{total} files OK")
    else:
        print(f"FAILURES: {total_fail}/{total} files failed, {total_pass} passed")
    print("=" * 60)

    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
