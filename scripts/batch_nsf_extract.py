"""
Batch NSF extractor: finds all EMU .zophar.zip files in the root folder,
extracts NSFs, runs nsf_to_reaper.py on each, and generates proper
REAPER projects via generate_project.py.

NEVER overwrites existing files. All NSF-extracted output uses _nsf_ tag.

Usage:
    python scripts/batch_nsf_extract.py
"""

import zipfile
import subprocess
import os
import sys
import glob
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_emu_zips():
    """Find all EMU zophar zips in the root folder."""
    return sorted(glob.glob(str(REPO_ROOT / "*(EMU).zophar.zip")))


def extract_nsf(zip_path):
    """Extract NSF and M3U from a zophar EMU zip. Returns (nsf_path, m3u_path, game_name)."""
    zf = zipfile.ZipFile(zip_path)

    # Derive game name from zip filename
    basename = os.path.basename(zip_path)
    game_name = basename.replace(" (EMU).zophar.zip", "")
    game_slug = game_name.replace(" ", "_").replace("'", "").replace("-", "_").replace(":", "")

    # Extract to output/{game_slug}/nsf/
    nsf_dir = REPO_ROOT / "output" / game_slug / "nsf"
    nsf_dir.mkdir(parents=True, exist_ok=True)

    zf.extractall(str(nsf_dir))

    nsf_files = [f for f in zf.namelist() if f.endswith('.nsf')]
    m3u_files = [f for f in zf.namelist() if f.endswith('.m3u')]

    nsf_path = str(nsf_dir / nsf_files[0]) if nsf_files else None
    m3u_path = str(nsf_dir / m3u_files[0]) if m3u_files else None

    return nsf_path, m3u_path, game_name, game_slug


def read_track_names(m3u_path):
    """Extract track names from M3U playlist."""
    if not m3u_path or not os.path.exists(m3u_path):
        return None

    names = []
    with open(m3u_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            # Format: file::NSF,song_num,title,duration,...
            parts = line.split(',')
            if len(parts) >= 3:
                title = parts[2].strip()
                # Remove artist prefix if present (e.g., "Game - Artist - Title")
                if ' - ' in title:
                    segments = title.split(' - ')
                    title = segments[-1] if len(segments) > 2 else title
                names.append(title)

    return names if names else None


def process_game(nsf_path, game_name, game_slug, track_names=None):
    """Run nsf_to_reaper.py and generate_project.py for one game."""
    output_dir = str(REPO_ROOT / "output" / game_slug)

    # Build command
    cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "nsf_to_reaper.py"),
        nsf_path, "--all",
        "-o", output_dir,
    ]

    if track_names:
        cmd.extend(["--names", ",".join(track_names)])

    print(f"\n{'='*60}")
    print(f"Processing: {game_name}")
    print(f"NSF: {nsf_path}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, timeout=3600)  # 1 hour max per game

    if result.returncode != 0:
        print(f"WARNING: nsf_to_reaper.py returned {result.returncode}")
        return False

    # Now regenerate REAPER projects with proper JSFX synth
    midi_dir = os.path.join(output_dir, "midi")
    reaper_dir = os.path.join(output_dir, "reaper")

    if os.path.exists(midi_dir):
        midi_files = sorted([f for f in os.listdir(midi_dir)
                           if f.endswith('.mid') and game_slug.replace("_", "") in f.replace("_", "").lower()])

        print(f"\nRegenerating {len(midi_files)} REAPER projects with JSFX synth...")
        for mf in midi_files:
            midi_path = os.path.join(midi_dir, mf)
            # Use _nsf_ tag to distinguish from ROM-parsed versions
            rpp_name = mf.replace('.mid', '_nsf.rpp')
            rpp_path = os.path.join(reaper_dir, rpp_name)

            # Don't overwrite existing projects
            if os.path.exists(rpp_path):
                print(f"  SKIP (exists): {rpp_name}")
                continue

            sub_result = subprocess.run([
                sys.executable, str(REPO_ROOT / "scripts" / "generate_project.py"),
                "--midi", midi_path,
                "--nes-native",
                "-o", rpp_path,
            ], capture_output=True, text=True)

            if sub_result.returncode == 0:
                print(f"  OK: {rpp_name}")
            else:
                print(f"  FAIL: {rpp_name}: {sub_result.stderr[:100]}")

    return True


def main():
    zips = find_emu_zips()

    if not zips:
        print("No EMU .zophar.zip files found in root folder.")
        print("Download from zophar.net and place in:", str(REPO_ROOT))
        return

    print(f"Found {len(zips)} EMU zip(s):")
    for z in zips:
        print(f"  {os.path.basename(z)}")

    # Skip already-processed games (check if nsf dir exists with MIDI output)
    to_process = []
    for z in zips:
        nsf_path, m3u_path, game_name, game_slug = extract_nsf(z)

        if not nsf_path:
            print(f"  SKIP {game_name}: no NSF found in zip")
            continue

        # Check if already processed (has MIDI files from NSF pipeline)
        midi_dir = REPO_ROOT / "output" / game_slug / "midi"
        existing_midis = list(midi_dir.glob(f"{game_slug}*.mid")) if midi_dir.exists() else []

        if existing_midis:
            print(f"  SKIP {game_name}: already has {len(existing_midis)} MIDIs")
            continue

        track_names = read_track_names(m3u_path)
        to_process.append((nsf_path, game_name, game_slug, track_names))

    if not to_process:
        print("\nAll games already processed!")
        return

    print(f"\nProcessing {len(to_process)} game(s)...")

    for nsf_path, game_name, game_slug, track_names in to_process:
        try:
            process_game(nsf_path, game_name, game_slug, track_names)
        except Exception as e:
            print(f"ERROR processing {game_name}: {e}")
            continue

    print("\n" + "="*60)
    print("BATCH COMPLETE")
    print("="*60)

    # Summary
    for _, game_name, game_slug, _ in to_process:
        midi_dir = REPO_ROOT / "output" / game_slug / "midi"
        reaper_dir = REPO_ROOT / "output" / game_slug / "reaper"
        midi_count = len(list(midi_dir.glob("*.mid"))) if midi_dir.exists() else 0
        rpp_count = len(list(reaper_dir.glob("*.rpp"))) if reaper_dir.exists() else 0
        print(f"  {game_name}: {midi_count} MIDIs, {rpp_count} REAPER projects")


if __name__ == "__main__":
    main()
