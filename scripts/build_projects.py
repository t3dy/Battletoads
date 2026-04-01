#!/usr/bin/env python3
"""Build self-contained REAPER projects for all processed games.

Creates Projects/<Game>/midi/*.mid + *.rpp with updated generate_project.py
(includes Live Patch sliders). Each game folder is portable — MIDI files
are co-located and RPPs reference them by absolute path.

Usage:
    python scripts/build_projects.py              # all games
    python scripts/build_projects.py Mega_Man_2   # single game
    python scripts/build_projects.py --list       # show what would be built
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
PROJECTS_DIR = REPO_ROOT / "Projects"
GENERATE_SCRIPT = REPO_ROOT / "scripts" / "generate_project.py"

# Games to skip (duplicates, partial, or special folders)
SKIP = {
    "bach_mashups", "cv1_tracks", "cv1_wav",
    "vampire_killer_v2.mid", "vampire_killer_v4.mid",
    "vampire_killer_v4b.mid", "vampire_killer_v4c.mid",
}


def find_games() -> list[Path]:
    """Find all game folders in output/ that have MIDI files."""
    games = []
    for d in sorted(OUTPUT_DIR.iterdir()):
        if not d.is_dir() or d.name in SKIP:
            continue
        midi_dir = d / "midi"
        if midi_dir.is_dir() and list(midi_dir.glob("*.mid")):
            games.append(d)
    return games


def build_game(game_dir: Path, force: bool = False) -> int:
    """Build Projects/<Game>/ with midi/ and RPP files.

    Returns number of RPPs generated.
    """
    game_name = game_dir.name
    proj_dir = PROJECTS_DIR / game_name
    midi_src = game_dir / "midi"
    midi_dst = proj_dir / "midi"

    midi_files = sorted(midi_src.glob("*.mid"))
    if not midi_files:
        return 0

    # Create target directories
    proj_dir.mkdir(parents=True, exist_ok=True)
    midi_dst.mkdir(parents=True, exist_ok=True)

    count = 0
    for mid in midi_files:
        # Copy MIDI to Projects/<Game>/midi/
        dst_mid = midi_dst / mid.name
        if not dst_mid.exists() or force:
            shutil.copy2(mid, dst_mid)

        # Generate RPP alongside the midi/ folder
        rpp_name = mid.stem + ".rpp"
        rpp_path = proj_dir / rpp_name

        if rpp_path.exists() and not force:
            count += 1
            continue

        result = subprocess.run(
            [
                sys.executable, str(GENERATE_SCRIPT),
                "--midi", str(dst_mid),
                "--nes-native",
                "-o", str(rpp_path),
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: {rpp_name}: {result.stderr.strip()}")
        else:
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Build Projects/ folder with REAPER projects")
    parser.add_argument("games", nargs="*", help="Specific game folder names (default: all)")
    parser.add_argument("--list", action="store_true", help="List games and MIDI counts, don't build")
    parser.add_argument("--force", action="store_true", help="Regenerate even if RPP exists")
    args = parser.parse_args()

    all_games = find_games()

    if args.games:
        selected = []
        for name in args.games:
            matches = [g for g in all_games if g.name == name]
            if not matches:
                print(f"Not found: {name}", file=sys.stderr)
                sys.exit(1)
            selected.extend(matches)
    else:
        selected = all_games

    if args.list:
        print(f"{'Game':<50s} {'MIDIs':>6s}")
        print("-" * 58)
        for g in selected:
            n = len(list((g / "midi").glob("*.mid")))
            print(f"{g.name:<50s} {n:>6d}")
        total = sum(len(list((g / "midi").glob("*.mid"))) for g in selected)
        print(f"\n{len(selected)} games, {total} total MIDIs")
        return

    print(f"Building {len(selected)} games into Projects/\n")
    total_rpps = 0
    for game in selected:
        midi_count = len(list((game / "midi").glob("*.mid")))
        print(f"{game.name} ({midi_count} tracks)...")
        n = build_game(game, force=args.force)
        total_rpps += n

    print(f"\nDone: {total_rpps} REAPER projects across {len(selected)} games in Projects/")


if __name__ == "__main__":
    main()
