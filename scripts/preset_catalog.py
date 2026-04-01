#!/usr/bin/env python3
"""Preset catalog generator and CLI browser for the ReapNES extracted corpus.

Reads preset_bank.json (54K+ instruments extracted from NES-MDB) and provides:
- Browsable catalog grouped by game, channel, and tags
- CLI search/filter by game, channel type, tag, envelope shape
- Export selections to song set JSON for project generation
- Generate markdown catalog for offline browsing

Usage:
    python preset_catalog.py browse                       # Interactive browse
    python preset_catalog.py search --game Castlevania    # Filter by game
    python preset_catalog.py search --channel noise       # Filter by channel
    python preset_catalog.py search --tag vibrato         # Filter by tag
    python preset_catalog.py search --game MegaMan2 --song Stage1
    python preset_catalog.py games                        # List all games
    python preset_catalog.py songs --game Castlevania     # List songs in a game
    python preset_catalog.py catalog --output docs/PRESET_CATALOG.md
    python preset_catalog.py export --game Castlevania --song "01Prelude" --output song_sets/cv1_prelude.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = REPO_ROOT / "studio" / "presets" / "preset_bank.json"
JSFX_DATA_DIR = REPO_ROOT / "studio" / "presets" / "jsfx_data"
SONG_SETS_DIR = REPO_ROOT / "studio" / "song_sets"

# Channel type to REAPER channel mapping
CHANNEL_ROLES = {
    "pulse": ["lead", "harmony"],
    "triangle": ["bass"],
    "noise": ["percussion"],
}


def load_bank() -> list[dict]:
    """Load the preset bank JSON."""
    if not BANK_PATH.exists():
        print(f"Preset bank not found: {BANK_PATH}", file=sys.stderr)
        print("Run the extraction pipeline first.", file=sys.stderr)
        sys.exit(1)
    with open(BANK_PATH, encoding="utf-8") as f:
        return json.load(f)


def index_by_game(bank: list[dict]) -> dict[str, list[dict]]:
    """Group presets by source_game."""
    idx = defaultdict(list)
    for p in bank:
        idx[p.get("source_game", "unknown")].append(p)
    return dict(idx)


def index_by_game_song(bank: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Group presets by source_game → source_song."""
    idx: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for p in bank:
        game = p.get("source_game", "unknown")
        song = p.get("source_song", "unknown")
        idx[game][song].append(p)
    return {g: dict(songs) for g, songs in idx.items()}


def search_presets(
    bank: list[dict],
    *,
    game: str | None = None,
    song: str | None = None,
    channel: str | None = None,
    tag: str | None = None,
    name: str | None = None,
    min_notes: int = 0,
) -> list[dict]:
    """Filter presets by multiple criteria."""
    results = bank
    if game:
        gl = game.lower()
        results = [p for p in results if gl in p.get("source_game", "").lower()]
    if song:
        sl = song.lower()
        results = [p for p in results if sl in p.get("source_song", "").lower()]
    if channel:
        results = [p for p in results if p.get("channel") == channel]
    if tag:
        results = [p for p in results if tag in p.get("tags", [])]
    if name:
        nl = name.lower()
        results = [p for p in results if nl in p.get("name", "").lower()]
    if min_notes > 0:
        results = [p for p in results if p.get("note_count", 0) >= min_notes]
    return results


def format_preset_line(p: dict, idx: int | None = None) -> str:
    """Format a single preset as a readable line."""
    prefix = f"[{idx:4d}] " if idx is not None else ""
    name = p.get("name", "?")
    ch = p.get("channel", "?")
    game = p.get("source_game", "?")
    song = p.get("source_song", "?")
    notes = p.get("note_count", 0)
    env_len = p.get("envelope_length", 0)
    tags = ", ".join(p.get("tags", [])[:4])
    return f"{prefix}{name:<30s} {ch:<9s} {env_len:3d}fr  {notes:5d}n  {game}/{song}  [{tags}]"


def get_preset_filename(p: dict, bank: list[dict]) -> str | None:
    """Find the .reapnes-data filename for a preset in jsfx_data/."""
    idx = bank.index(p)
    # Filenames follow pattern: NNNN_Name_HASH.reapnes-data
    name = p.get("name", "").replace(" ", "_")
    pattern = f"{idx:04d}_{name}"
    for f in JSFX_DATA_DIR.glob(f"{idx:04d}_*.reapnes-data"):
        return f.name
    return None


# --- Commands ---

def cmd_games(bank: list[dict]) -> None:
    """List all games with preset counts."""
    by_game = index_by_game(bank)
    print(f"{'Game':<50s} {'Presets':>7s}  {'Songs':>5s}  Channels")
    print("-" * 100)
    for game in sorted(by_game.keys()):
        presets = by_game[game]
        songs = set(p.get("source_song", "") for p in presets)
        channels = set(p.get("channel", "") for p in presets)
        print(f"{game:<50s} {len(presets):>7d}  {len(songs):>5d}  {', '.join(sorted(channels))}")


def cmd_songs(bank: list[dict], game: str) -> None:
    """List all songs for a game with preset details."""
    by_gs = index_by_game_song(bank)
    gl = game.lower()
    matching_games = [g for g in by_gs if gl in g.lower()]
    if not matching_games:
        print(f"No game matching '{game}'", file=sys.stderr)
        return

    for g in sorted(matching_games):
        print(f"\n=== {g} ===")
        songs = by_gs[g]
        for song_name in sorted(songs.keys()):
            presets = songs[song_name]
            ch_counts = defaultdict(int)
            for p in presets:
                ch_counts[p.get("channel", "?")] += 1
            ch_str = ", ".join(f"{ch}:{n}" for ch, n in sorted(ch_counts.items()))
            print(f"  {song_name:<40s}  {len(presets):3d} presets  ({ch_str})")


def cmd_search(bank: list[dict], args: argparse.Namespace) -> None:
    """Search and display matching presets."""
    results = search_presets(
        bank,
        game=args.game,
        song=args.song,
        channel=args.channel,
        tag=args.tag,
        name=args.name,
        min_notes=args.min_notes or 0,
    )
    if not results:
        print("No matching presets found.")
        return

    print(f"Found {len(results)} presets:")
    print()
    # Sort by note_count descending (most common first)
    results.sort(key=lambda p: p.get("note_count", 0), reverse=True)
    for i, p in enumerate(results[:50]):
        print(format_preset_line(p, i))
    if len(results) > 50:
        print(f"\n... and {len(results) - 50} more. Use --min-notes to filter.")


def cmd_catalog(bank: list[dict], output_path: Path) -> None:
    """Generate a markdown preset catalog."""
    by_gs = index_by_game_song(bank)

    lines = [
        "# ReapNES Preset Catalog",
        "",
        f"Total presets: {len(bank)}",
        f"Total games: {len(by_gs)}",
        "",
        "## Games",
        "",
    ]

    for game in sorted(by_gs.keys()):
        songs = by_gs[game]
        total = sum(len(ps) for ps in songs.values())
        channels = set()
        for ps in songs.values():
            for p in ps:
                channels.add(p.get("channel", "?"))

        lines.append(f"### {game}")
        lines.append(f"")
        lines.append(f"**{total} presets** across {len(songs)} songs | Channels: {', '.join(sorted(channels))}")
        lines.append("")
        lines.append("| Song | Presets | Channels |")
        lines.append("|------|---------|----------|")

        for song_name in sorted(songs.keys()):
            ps = songs[song_name]
            ch_counts = defaultdict(int)
            for p in ps:
                ch_counts[p.get("channel", "?")] += 1
            ch_str = ", ".join(f"{ch}:{n}" for ch, n in sorted(ch_counts.items()))
            lines.append(f"| {song_name} | {len(ps)} | {ch_str} |")

        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Catalog written to: {output_path}")
    print(f"  {len(by_gs)} games, {len(bank)} presets")


def cmd_export_song_set(bank: list[dict], args: argparse.Namespace) -> None:
    """Export a song's presets as a song set JSON file."""
    results = search_presets(bank, game=args.game, song=args.song)
    if not results:
        print(f"No presets found for game='{args.game}' song='{args.song}'", file=sys.stderr)
        return

    # Group by channel
    by_channel = defaultdict(list)
    for p in results:
        by_channel[p.get("channel", "unknown")].append(p)

    # Pick best preset per channel role (highest note_count = most common)
    channel_assignments = {}

    pulse_presets = sorted(by_channel.get("pulse", []),
                           key=lambda p: p.get("note_count", 0), reverse=True)
    if len(pulse_presets) >= 1:
        p1 = pulse_presets[0]
        fn = get_preset_filename(p1, bank)
        channel_assignments["pulse1"] = {
            "role": "lead",
            "preset": f"jsfx_data/{fn}" if fn else "",
            "description": f"{p1['name']} ({p1.get('note_count',0)} notes)",
            "notes": f"Tags: {', '.join(p1.get('tags', []))}",
        }
    if len(pulse_presets) >= 2:
        p2 = pulse_presets[1]
        fn = get_preset_filename(p2, bank)
        channel_assignments["pulse2"] = {
            "role": "harmony",
            "preset": f"jsfx_data/{fn}" if fn else "",
            "description": f"{p2['name']} ({p2.get('note_count',0)} notes)",
            "notes": f"Tags: {', '.join(p2.get('tags', []))}",
        }

    tri_presets = sorted(by_channel.get("triangle", []),
                          key=lambda p: p.get("note_count", 0), reverse=True)
    if tri_presets:
        t = tri_presets[0]
        fn = get_preset_filename(t, bank)
        channel_assignments["triangle"] = {
            "role": "bass",
            "preset": f"jsfx_data/{fn}" if fn else "",
            "description": f"{t['name']} ({t.get('note_count',0)} notes)",
        }

    noise_presets = sorted(by_channel.get("noise", []),
                            key=lambda p: p.get("note_count", 0), reverse=True)
    if noise_presets:
        n = noise_presets[0]
        fn = get_preset_filename(n, bank)
        channel_assignments["noise"] = {
            "role": "percussion",
            "preset": f"jsfx_data/{fn}" if fn else "",
            "description": f"{n['name']} ({n.get('note_count',0)} notes)",
        }

    # Determine actual game name
    game_names = set(p.get("source_game", "") for p in results)
    game_name = sorted(game_names)[0] if game_names else args.game
    song_names = set(p.get("source_song", "") for p in results)
    song_name = sorted(song_names)[0] if song_names else args.song

    song_set = {
        "format": "reapnes-song-set",
        "version": 1,
        "game": {
            "title": game_name.replace("_", " "),
            "platform": "NES",
        },
        "song": {
            "title": song_name.replace("_", " "),
        },
        "provenance": {
            "source": "nes-mdb-extracted",
            "confidence": "approximate",
            "notes": f"Auto-generated from NES-MDB corpus. {len(results)} presets found. "
                     f"Best-by-note-count selection.",
        },
        "channels": channel_assignments,
    }

    # Add drum map from noise presets if available
    if len(noise_presets) >= 2:
        drum_map = {}
        for i, np in enumerate(noise_presets[:4]):
            fn = get_preset_filename(np, bank)
            midi_note = [36, 38, 42, 46][i]  # kick, snare, closed hat, open hat
            drum_map[str(midi_note)] = {
                "preset": f"jsfx_data/{fn}" if fn else "",
                "description": np["name"],
            }
        song_set["drum_map"] = drum_map

    output = Path(args.output) if args.output else SONG_SETS_DIR / f"{game_name}_{song_name}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(song_set, f, indent=2, ensure_ascii=False)
    print(f"Exported song set: {output}")
    print(f"  Game: {game_name}")
    print(f"  Song: {song_name}")
    print(f"  Channels: {', '.join(channel_assignments.keys())}")


def cmd_browse(bank: list[dict]) -> None:
    """Interactive browse mode."""
    by_gs = index_by_game_song(bank)

    print(f"\nReapNES Preset Browser — {len(bank)} instruments from {len(by_gs)} games")
    print("=" * 70)
    print("\nCommands:")
    print("  games                  - List all games")
    print("  songs <game>           - List songs for a game")
    print("  show <game> <song>     - Show presets for a specific song")
    print("  search <term>          - Search preset names")
    print("  export <game> <song>   - Export as song set JSON")
    print("  quit                   - Exit")
    print()

    while True:
        try:
            line = input("browse> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break
        elif cmd == "games":
            cmd_games(bank)
        elif cmd == "songs" and len(parts) >= 2:
            cmd_songs(bank, parts[1])
        elif cmd == "show" and len(parts) >= 3:
            results = search_presets(bank, game=parts[1], song=parts[2])
            results.sort(key=lambda p: p.get("note_count", 0), reverse=True)
            for i, p in enumerate(results[:30]):
                print(format_preset_line(p, i))
            if len(results) > 30:
                print(f"  ... {len(results) - 30} more")
        elif cmd == "search" and len(parts) >= 2:
            term = " ".join(parts[1:]).lower()
            results = [p for p in bank if term in p.get("name", "").lower()
                       or term in p.get("source_game", "").lower()
                       or term in str(p.get("tags", []))]
            results.sort(key=lambda p: p.get("note_count", 0), reverse=True)
            print(f"Found {len(results)} matches:")
            for i, p in enumerate(results[:30]):
                print(format_preset_line(p, i))
        elif cmd == "export" and len(parts) >= 3:
            results = search_presets(bank, game=parts[1], song=parts[2])
            if results:
                game_name = results[0].get("source_game", parts[1])
                song_name = results[0].get("source_song", parts[2])
                out = SONG_SETS_DIR / f"{game_name}_{song_name}.json"
                # Create a fake args namespace for export
                class FakeArgs:
                    pass
                fa = FakeArgs()
                fa.game = parts[1]
                fa.song = parts[2]
                fa.output = str(out)
                cmd_export_song_set(bank, fa)
            else:
                print("No presets found for that game/song combination.")
        else:
            print("Unknown command. Type 'quit' to exit.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ReapNES Preset Catalog — browse, search, and export NES instrument presets",
    )
    sub = parser.add_subparsers(dest="command")

    # games
    sub.add_parser("games", help="List all games with preset counts")

    # songs
    p_songs = sub.add_parser("songs", help="List songs for a game")
    p_songs.add_argument("--game", required=True, help="Game name (partial match)")

    # search
    p_search = sub.add_parser("search", help="Search/filter presets")
    p_search.add_argument("--game", help="Filter by game name (partial match)")
    p_search.add_argument("--song", help="Filter by song name (partial match)")
    p_search.add_argument("--channel", choices=["pulse", "triangle", "noise"])
    p_search.add_argument("--tag", help="Filter by tag")
    p_search.add_argument("--name", help="Filter by preset name")
    p_search.add_argument("--min-notes", type=int, default=0, help="Minimum note count")

    # catalog
    p_cat = sub.add_parser("catalog", help="Generate markdown catalog")
    p_cat.add_argument("--output", default="docs/PRESET_CATALOG.md")

    # export
    p_exp = sub.add_parser("export", help="Export a song's presets as a song set")
    p_exp.add_argument("--game", required=True, help="Game name (partial match)")
    p_exp.add_argument("--song", required=True, help="Song name (partial match)")
    p_exp.add_argument("--output", help="Output JSON path")

    # browse
    sub.add_parser("browse", help="Interactive preset browser")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    bank = load_bank()

    if args.command == "games":
        cmd_games(bank)
    elif args.command == "songs":
        cmd_songs(bank, args.game)
    elif args.command == "search":
        cmd_search(bank, args)
    elif args.command == "catalog":
        cmd_catalog(bank, Path(args.output))
    elif args.command == "export":
        cmd_export_song_set(bank, args)
    elif args.command == "browse":
        cmd_browse(bank)


if __name__ == "__main__":
    main()
