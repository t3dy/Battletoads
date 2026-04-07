from __future__ import annotations

import json
from pathlib import Path
import sys

from mido import MidiFile

REPO = Path(r"C:\Dev\NSFRIPPER")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import nsf_to_reaper as ntr
NSF_PATH = REPO / "state" / "ww_ref" / "Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).nsf"
RELEASE_IR_PATH = REPO / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_release_ir.json"
OUT_PATH = REPO / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_composite_bass_evidence.json"
MIDI_PATH = REPO / "Projects" / "Wizards_and_Warriors" / "midi" / "Wizards_&_Warriors_01_Wizards_&_Warriors_Title_releaseaware_v5.mid"

PHRASE_FRAMES = (928, 960, 976)


def load_note_events(mid_path: Path, track_index: int, frame_start: int, frame_end: int) -> list[dict[str, int | str]]:
    mid = MidiFile(str(mid_path))
    track = mid.tracks[track_index]
    out: list[dict[str, int | str]] = []
    ticks = 0
    for msg in track:
        ticks += msg.time
        if msg.type not in ("note_on", "note_off"):
            continue
        frame = ticks // ntr.TICKS_PER_FRAME
        if frame_start <= frame <= frame_end:
            out.append(
                {
                    "frame": int(frame),
                    "type": msg.type,
                    "note": int(msg.note),
                    "velocity": int(msg.velocity),
                }
            )
    return out


def main() -> None:
    emu = ntr.NsfEmulator(str(NSF_PATH))
    frames = emu.play_song(1, 1000)
    channels = ntr.frames_to_channel_data(frames)
    note_boundaries = ntr.load_wizards_and_warriors_note_boundaries(str(NSF_PATH), 1)

    release_rows = json.loads(RELEASE_IR_PATH.read_text(encoding="utf-8"))["frames"]
    release_map = {row["frame"]: row for row in release_rows}

    data = {
        "meta": {
            "nsf_path": str(NSF_PATH),
            "midi_path": str(MIDI_PATH),
            "phrase_frames": list(PHRASE_FRAMES),
            "summary": "Composite bass evidence for the disputed Wizards & Warriors title phrase. Treat pulse1+triangle as one articulation target rather than triangle alone.",
        },
        "frames": [],
        "midi_projection": {
            "pulse1_events_920_980": load_note_events(MIDI_PATH, 1, 920, 980),
            "triangle_events_920_980": load_note_events(MIDI_PATH, 3, 920, 980),
        },
    }

    for frame_idx in PHRASE_FRAMES:
        p1 = channels["pulse1"]["notes"][frame_idx]
        tri = channels["triangle"]["notes"][frame_idx]
        writes = [
            {"reg": f"0x{reg:04X}", "value": value}
            for reg, value in frames[frame_idx]["writes"]
            if reg in (0x4000, 0x4002, 0x4003, 0x4004, 0x4006, 0x4007, 0x4008, 0x400A, 0x400B, 0x4015)
        ]
        rel = release_map[frame_idx]
        data["frames"].append(
            {
                "frame": frame_idx,
                "pulse1": {
                    "period": p1["period"],
                    "midi_note": ntr.period_to_midi(p1["period"]),
                    "duty": p1["duty"],
                    "const_vol": p1["const_vol"],
                    "env_loop": p1["env_loop"],
                    "env_period": p1["env_period"],
                    "boundary": frame_idx in note_boundaries.get("pulse1", set()),
                },
                "triangle": {
                    "period": tri["period"],
                    "midi_note": ntr.period_to_midi(tri["period"], is_tri=True),
                    "linear": tri["linear"],
                    "linear_reload": tri["linear_reload"],
                    "linear_control": tri["linear_control"],
                    "boundary": frame_idx in note_boundaries.get("triangle", set()),
                },
                "writes": writes,
                "audio": {
                    "release_class": rel["release_class"],
                    "audio_low_norm": rel["audio_low_norm"],
                    "audio_high_norm": rel["audio_high_norm"],
                    "composite_attack": rel["composite_attack"],
                },
            }
        )

    OUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
