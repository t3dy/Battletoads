#!/usr/bin/env python3
"""Dump structural parse artifacts for all Wizards & Warriors songs.

This script applies the current discovery-stage parser to every song/channel in
Wizards & Warriors and writes JSON artifacts that can be inspected or diffed
later as parser semantics improve.

It is intentionally structural, not a trusted music export path.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extraction.drivers.other.wizards_and_warriors_parser import load_default_parser


OUT_DIR = REPO_ROOT / "extraction" / "analysis" / "static" / "wizards_and_warriors"

TRACK_NAMES = {
    1: "Wizards & Warriors Title",
    2: "Forest of Elrond",
    3: "Tree",
    4: "Ice Cave",
    5: "Low on Energy",
    6: "Initial Registration",
    7: "Got an Item",
    8: "Outside Castle Ironspire",
    9: "Castle Ironspire",
    10: "Entering a Door",
    11: "Map",
    12: "Potion",
    13: "Fire Cavern",
    14: "Inside the Big Tree",
    15: "Boss",
    16: "Forest of Elrond (alt)",
}


def _to_jsonable(value):
    if is_dataclass(value):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def main() -> None:
    parser = load_default_parser()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "game": "Wizards & Warriors",
        "tracks": [],
    }

    for song_number in range(1, 17):
        summary = parser.summarize_song(song_number, max_events=512)
        pointers = parser.emulate_song_init(song_number - 1)

        song_dir = OUT_DIR / f"{song_number:02d}"
        song_dir.mkdir(parents=True, exist_ok=True)

        track_record = {
            "song_number": song_number,
            "track_name": TRACK_NAMES.get(song_number, f"Song {song_number}"),
            "channels": {},
        }

        for channel, ch_summary in summary.channels.items():
            start_cpu = pointers.channel_pointers[channel]
            parsed = parser.parse_channel(start_cpu, channel, max_events=512)
            payload = {
                "song_number": song_number,
                "track_name": TRACK_NAMES.get(song_number, f"Song {song_number}"),
                "channel": channel,
                "start_cpu": f"0x{start_cpu:04X}",
                "summary": _to_jsonable(ch_summary),
                "events": [_to_jsonable(evt) for evt in parsed.events],
            }
            out_path = song_dir / f"{channel}.json"
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            track_record["channels"][channel] = {
                "start_cpu": f"0x{start_cpu:04X}",
                "event_count": ch_summary.event_count,
                "bytes_consumed": ch_summary.bytes_consumed,
                "terminal_event": ch_summary.terminal_event,
                "ended_by_loop": ch_summary.ended_by_loop,
                "artifact": str(out_path),
            }

        manifest["tracks"].append(track_record)

    (OUT_DIR / "index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote structural parse artifacts to {OUT_DIR}")


if __name__ == "__main__":
    main()
