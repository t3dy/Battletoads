#!/usr/bin/env python3
"""Build a REAPER project with Kraid MIDI embedded using REAPER's native MIDI format.

This script creates an RPP with inline MIDI events (E/e/X/x format) that REAPER
can play back directly, no external file reference needed.
"""

from __future__ import annotations
import mido
import struct
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def midi_track_to_rpp_events(midi_track: mido.MidiTrack, ticks_per_beat: int) -> list[str]:
    """Convert a mido track to REAPER's inline MIDI event lines.

    REAPER inline MIDI format:
      E offset_ticks status_byte [data_bytes...]   (channel messages)
      e offset_ticks status_byte [data_bytes...]   (selected channel messages)
      X offset_ticks length data_bytes              (sysex/meta)
      x offset_ticks length data_bytes              (selected sysex/meta)

    offset_ticks is delta time from previous event.
    All values are lowercase hex.
    """
    lines = []
    for msg in midi_track:
        delta = msg.time
        if msg.is_meta:
            # Encode meta events as X lines
            meta_data = msg.bin()
            # Skip end_of_track — REAPER adds its own
            if msg.type == "end_of_track":
                continue
            hex_data = " ".join(f"{b:02x}" for b in meta_data)
            lines.append(f"X {delta} {len(meta_data)} {hex_data}")
        elif msg.type in ("note_on", "note_off", "control_change", "program_change",
                          "pitchwheel", "aftertouch", "polytouch", "channel_pressure"):
            raw = msg.bin()
            hex_data = " ".join(f"{b:02x}" for b in raw)
            lines.append(f"E {delta} {hex_data}")
    return lines


def build_project(
    midi_path: Path,
    output_path: Path,
    channel_assignments: dict[int, dict] | None = None,
) -> None:
    """Build a complete RPP with inline MIDI and ReapNES_Full on each track."""
    mid = mido.MidiFile(str(midi_path))
    tpb = mid.ticks_per_beat

    # Find tempo
    tempo_bpm = 120.0
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempo_bpm = 60_000_000 / msg.tempo
                break

    # Find tracks with notes
    note_tracks = []
    for i, track in enumerate(mid.tracks):
        channels = set()
        note_count = 0
        for msg in track:
            if hasattr(msg, "channel"):
                channels.add(msg.channel)
            if msg.type == "note_on" and msg.velocity > 0:
                note_count += 1
        if note_count > 0:
            note_tracks.append({
                "index": i,
                "track": track,
                "channels": sorted(channels),
                "note_count": note_count,
                "name": track.name or f"Track {i}",
            })

    # Default channel assignments
    if not channel_assignments:
        channel_assignments = {}
        nes_channels = [
            {"name": "NES - Pulse 1", "duty": 2, "color": 16576606},
            {"name": "NES - Pulse 2", "duty": 1, "color": 10092441},
            {"name": "NES - Triangle", "duty": 0, "color": 16744192},
            {"name": "NES - Noise / Drums", "duty": 0, "color": 11184810},
        ]
        for idx, nt in enumerate(note_tracks[:4]):
            channel_assignments[nt["index"]] = nes_channels[idx]

    # Calculate duration in seconds
    duration = mid.length

    # Build RPP
    lines = []
    lines.append(f'<REAPER_PROJECT 0.1 "7.27/win64" 1707000000')
    lines.append(f"  RIPPLE 0")
    lines.append(f"  GROUPOVERRIDE 0 0 0")
    lines.append(f"  AUTOXFADE 129")
    lines.append(f"  TEMPO {tempo_bpm} 4 4")
    lines.append(f"  PLAYRATE 1 0 0.25 4")
    lines.append(f"  MASTERAUTOMODE 0")
    lines.append(f"  MASTER_VOLUME 1 0 -1 -1 1")
    lines.append(f"  MASTER_NCH 2 2")

    for nt in note_tracks[:4]:
        cfg = channel_assignments.get(nt["index"], {})
        track_name = cfg.get("name", nt["name"])
        duty = cfg.get("duty", 2)
        color = cfg.get("color", 16576606)

        # Convert MIDI events to inline format
        events = midi_track_to_rpp_events(nt["track"], tpb)

        lines.append(f"  <TRACK")
        lines.append(f'    NAME "{track_name}"')
        lines.append(f"    PEAKCOL {color}")
        lines.append(f"    BEAT -1")
        lines.append(f"    AUTOMODE 0")
        lines.append(f"    VOLPAN 1 0 -1 -1 1")
        lines.append(f"    MUTESOLO 0 0 0")
        lines.append(f"    NCHAN 2")
        lines.append(f"    FX 1")
        lines.append(f"    MAINSEND 1 0")
        lines.append(f"    REC 0 0 1 0 0 0 0 0")
        lines.append(f"    <FXCHAIN")
        lines.append(f"      SHOW 0")
        lines.append(f"      LASTSEL 0")
        lines.append(f"      DOCKED 0")
        lines.append(f'      <JS "ReapNES Studio/ReapNES_Full.jsfx" ""')
        lines.append(f"        {float(duty)} 15.0 1.0")
        lines.append(f"        1.0 15.0 1.0")
        lines.append(f"        1.0")
        lines.append(f"        4.0 0.0 15.0 1.0")
        lines.append(f"        0.0 0.0 0.0 0.0")
        lines.append(f"        0.8")
        lines.append(f"      >")
        lines.append(f"    >")
        # MIDI item with inline data
        lines.append(f"    <ITEM")
        lines.append(f"      POSITION 0")
        lines.append(f"      LENGTH {duration}")
        lines.append(f"      LOOP 0")
        lines.append(f"      ALLTAKES 0")
        lines.append(f"      FADEIN 0 0 0 0 0 0 0")
        lines.append(f"      FADEOUT 0 0 0 0 0 0 0")
        lines.append(f"      MUTE 0 0")
        lines.append(f"      SEL 0")
        lines.append(f"      IGUID {{{nt['index']:08d}-0000-0000-0000-000000000000}}")
        lines.append(f"      <SOURCE MIDI")
        lines.append(f"        HASDATA 1 {tpb} QN")
        lines.append(f"        CCINTERP 32")
        for event_line in events:
            lines.append(f"        {event_line}")
        # End of track
        lines.append(f"        E {0} ff 2f 00")
        lines.append(f"      >")
        lines.append(f"    >")
        lines.append(f"  >")

    lines.append(f">")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")
    print(f"  Tempo: {tempo_bpm:.1f} BPM")
    print(f"  Duration: {duration:.1f}s")
    print(f"  Tracks: {len(note_tracks[:4])}")
    for nt in note_tracks[:4]:
        cfg = channel_assignments.get(nt["index"], {})
        print(f"    {cfg.get('name', nt['name'])}: {nt['note_count']} notes")


if __name__ == "__main__":
    import sys
    midi = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/Users/PC/Downloads/Kraid.mid")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT / "reaper_projects" / "kraid_inline.rpp"
    build_project(midi, out)
