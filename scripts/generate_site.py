"""
Generate Jekyll pages for each game in the output directory.
Creates a games/ directory with one .md page per game listing all tracks.

Usage:
    python scripts/generate_site.py
"""

import os
import mido
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
GAMES_DIR = REPO_ROOT / "games"


def slugify(name):
    return name.lower().replace(" ", "-").replace("'", "").replace("_", "-").replace(".", "").replace("!", "").replace(",", "")


def get_game_info(game_dir):
    """Extract track info from a game's output directory."""
    midi_dir = game_dir / "midi"
    reaper_dir = game_dir / "reaper"
    wav_dir = game_dir / "wav"

    if not midi_dir.exists():
        return None

    tracks = []
    for f in sorted(midi_dir.iterdir()):
        if not f.suffix == ".mid":
            continue

        try:
            mid = mido.MidiFile(str(f))
        except Exception:
            continue

        # Count notes per channel
        note_counts = []
        cc_counts = []
        for t in mid.tracks:
            notes = sum(1 for m in t if m.type == "note_on")
            ccs = sum(1 for m in t if m.type == "control_change")
            if notes > 0 or ccs > 0:
                note_counts.append(notes)
                cc_counts.append(ccs)

        total_notes = sum(note_counts)
        total_ccs = sum(cc_counts)

        # Get duration
        dur_ticks = sum(msg.time for t in mid.tracks for msg in t)
        dur_sec = dur_ticks / mid.ticks_per_beat * 0.467  # approximate at ~128 BPM

        # Extract name from filename
        name = f.stem
        # Remove game prefix and version suffix
        for prefix in [game_dir.name + "_", game_dir.name.replace("_", "") + "_"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        name = name.replace("_v1", "").replace("_v2", "").replace("_nsf", "")
        name = name.replace("_", " ").strip()

        # Check if REAPER project exists
        rpp_exists = any(reaper_dir.glob(f"*{f.stem}*")) if reaper_dir.exists() else False

        tracks.append({
            "name": name,
            "midi_file": f.name,
            "notes": total_notes,
            "ccs": total_ccs,
            "duration": dur_sec,
            "has_rpp": rpp_exists,
        })

    return tracks


def generate_game_page(game_name, tracks, slug):
    """Generate a Jekyll markdown page for one game."""
    clean_name = game_name.replace("_", " ").replace("  ", " ").strip()

    lines = [
        "---",
        "layout: default",
        f"title: {clean_name}",
        "---",
        "",
        f"# {clean_name}",
        "",
        f"**{len(tracks)} tracks** extracted via NSF emulation with per-frame APU register capture.",
        "",
        "Each track includes 4-channel MIDI (Pulse 1, Pulse 2, Triangle, Noise) with CC11 volume envelopes and CC12 duty cycle automation, plus a REAPER project with the ReapNES NES APU synthesizer plugin loaded.",
        "",
        "## Track List",
        "",
        "| # | Track | Notes | CCs | Duration |",
        "|---|-------|-------|-----|----------|",
    ]

    for i, t in enumerate(tracks):
        dur_str = f"{int(t['duration'])}s" if t['duration'] > 0 else "—"
        lines.append(f"| {i+1} | {t['name']} | {t['notes']} | {t['ccs']} | {dur_str} |")

    total_notes = sum(t['notes'] for t in tracks)
    total_ccs = sum(t['ccs'] for t in tracks)

    lines.extend([
        "",
        f"**Total: {total_notes:,} note events, {total_ccs:,} CC automation events**",
        "",
        "## Downloads",
        "",
        "MIDI files and REAPER projects are available in the [GitHub repository](https://github.com/t3dy/ReapNES).",
        "",
        "[← Back to Game Library](../)",
    ])

    return "\n".join(lines)


def main():
    GAMES_DIR.mkdir(exist_ok=True)

    game_dirs = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "midi").exists()])

    print(f"Found {len(game_dirs)} games with MIDI output")

    for game_dir in game_dirs:
        tracks = get_game_info(game_dir)
        if not tracks:
            continue

        slug = slugify(game_dir.name)
        page_content = generate_game_page(game_dir.name, tracks, slug)

        page_path = GAMES_DIR / f"{slug}.md"
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content)

        total_notes = sum(t['notes'] for t in tracks)
        print(f"  {game_dir.name}: {len(tracks)} tracks, {total_notes} notes -> {page_path.name}")

    print(f"\nGenerated {len(game_dirs)} game pages in games/")


if __name__ == "__main__":
    main()
