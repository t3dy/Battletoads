#!/usr/bin/env python3
"""Batch process all games that have NSF files but no MIDI output yet.

Reads track names and durations from M3U files, then runs nsf_to_reaper.py
for each game. Fully deterministic — no LLM involvement needed.

Usage:
    python scripts/batch_nsf_all.py              # Process all unprocessed games
    python scripts/batch_nsf_all.py --dry-run    # Show what would be processed
    python scripts/batch_nsf_all.py --force      # Re-process even if MIDI exists
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"


def parse_m3u(m3u_path: Path) -> list[dict]:
    """Parse M3U file to extract track names and durations."""
    tracks = []
    with open(m3u_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            # Format: filename.nsf::NSF,tracknum,name,duration,,fadeout
            match = re.match(r'.*::NSF,(\d+),([^,]*),([^,]*)', line)
            if match:
                track_num = int(match.group(1))
                name = match.group(2).strip()
                duration_str = match.group(3).strip()
                # Parse duration H:MM:SS.mmm or MM:SS.mmm
                seconds = parse_duration(duration_str) if duration_str else 90
                tracks.append({
                    'num': track_num,
                    'name': name if name else f'Song {track_num}',
                    'seconds': max(seconds, 10),  # minimum 10 seconds
                })
    return tracks


def parse_duration(dur_str: str) -> float:
    """Convert M3U duration string to seconds."""
    parts = dur_str.split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return 90  # fallback


def find_games_to_process(force: bool = False) -> list[dict]:
    """Find all games with NSF but no MIDI output."""
    games = []
    for game_dir in sorted(OUTPUT_DIR.iterdir()):
        if not game_dir.is_dir():
            continue
        nsf_dir = game_dir / "nsf"
        midi_dir = game_dir / "midi"

        if not nsf_dir.exists():
            continue

        nsf_files = list(nsf_dir.glob("*.nsf"))
        if not nsf_files:
            continue

        midi_files = list(midi_dir.glob("*.mid")) if midi_dir.exists() else []

        if midi_files and not force:
            continue

        # Find M3U for track names
        m3u_files = list(nsf_dir.glob("*.m3u"))
        tracks = parse_m3u(m3u_files[0]) if m3u_files else []

        games.append({
            'name': game_dir.name,
            'dir': game_dir,
            'nsf': nsf_files[0],
            'tracks': tracks,
            'total_songs': len(tracks) if tracks else None,
        })

    return games


def process_game(game: dict) -> bool:
    """Run nsf_to_reaper.py for a single game."""
    nsf_path = game['nsf']
    output_dir = game['dir']
    tracks = game['tracks']

    if tracks:
        names = ','.join(t['name'] for t in tracks)
        # Use max duration from M3U, capped at 180s
        max_dur = min(max(t['seconds'] for t in tracks), 180)
    else:
        names = None
        max_dur = 90

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "nsf_to_reaper.py"),
        str(nsf_path),
        "--all",
        str(max_dur),
        "-o", str(output_dir),
    ]
    if names:
        cmd.extend(["--names", names])

    print(f"\n{'='*60}")
    print(f"Processing: {game['name']}")
    print(f"NSF: {nsf_path.name}")
    print(f"Tracks: {len(tracks) if tracks else '(unknown)'}")
    print(f"Duration cap: {max_dur}s")
    print(f"{'='*60}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return True
        else:
            print(f"FAILED: {result.stderr[-300:]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {game['name']} took >600s")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Batch NSF to MIDI+REAPER for all games')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--force', action='store_true', help='Re-process even if MIDI exists')
    args = parser.parse_args()

    games = find_games_to_process(force=args.force)

    if not games:
        print("All games already have MIDI output. Use --force to re-process.")
        return

    print(f"Games to process: {len(games)}")
    for g in games:
        track_info = f"{len(g['tracks'])} tracks" if g['tracks'] else "unknown tracks"
        print(f"  {g['name']:<45s} {track_info}")

    if args.dry_run:
        return

    results = {'ok': [], 'fail': []}
    for game in games:
        if process_game(game):
            results['ok'].append(game['name'])
        else:
            results['fail'].append(game['name'])

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE")
    print(f"  Success: {len(results['ok'])}")
    print(f"  Failed:  {len(results['fail'])}")
    if results['fail']:
        print(f"  Failed games: {', '.join(results['fail'])}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
