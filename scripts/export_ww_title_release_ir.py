#!/usr/bin/env python3
"""Export a release-focused IR for the W&W title triangle phrase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Dev\NSFRIPPER")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_ww_title_articulation import (  # noqa: E402
    NSF_PATH,
    WAV_PATH,
    best_audio_offset,
    build_frame_register_view,
    frame_rms_envelope,
    load_audio,
)
from scripts.nsf_to_reaper import NsfEmulator, frames_to_channel_data, load_wizards_and_warriors_note_boundaries  # noqa: E402


WINDOW_START = 920
WINDOW_END = 980
OUT_JSON = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_release_ir.json"
OUT_MD = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_release_ir_report.md"


def classify_frame(frame: int, tri: dict, prev_tri: dict, boundary: bool, hidden_retrigger: bool, low_norm: float, high_norm: float) -> str:
    sounding = tri["linear"] > 0 and tri["period"] > 2
    prev_sounding = prev_tri["linear"] > 0 and prev_tri["period"] > 2
    period_change = tri["period"] != prev_tri["period"]

    if not sounding:
        return "effectively_muted"
    if (hidden_retrigger or period_change or boundary) and low_norm >= 0.85:
        return "fresh_full_body"
    if (hidden_retrigger or period_change or boundary) and high_norm >= 0.85 and low_norm < 0.75:
        return "fresh_attack_damped_body"
    if prev_sounding and low_norm < 0.6:
        return "ringing_decay"
    return "sustain_body"


def build_release_ir() -> dict:
    emu = NsfEmulator(NSF_PATH)
    frames = emu.play_song(1, WINDOW_END + 8)
    channels = frames_to_channel_data(frames)
    boundaries = load_wizards_and_warriors_note_boundaries(NSF_PATH, 1)
    reg_view = build_frame_register_view(frames)

    audio, sr = load_audio(WAV_PATH)
    high_env = frame_rms_envelope(audio, sr, "high")
    low_env = frame_rms_envelope(audio, sr, "low")
    onset_frames = sorted(set(boundaries["pulse1"]) | set(boundaries["triangle"]))
    onset_frames = [f for f in onset_frames if 0 < f < 1500]
    alignment = best_audio_offset(high_env, onset_frames)
    audio_offset = int(alignment["offset_frames"])

    rows = []
    low_window = []
    high_window = []
    for frame in range(WINDOW_START, WINDOW_END + 1):
        idx = frame + audio_offset
        low = low_env[idx] if 0 <= idx < len(low_env) else 0.0
        high = high_env[idx] if 0 <= idx < len(high_env) else 0.0
        low_window.append(low)
        high_window.append(high)

    max_low = max(low_window) or 1.0
    max_high = max(high_window) or 1.0

    tri_notes = channels["triangle"]["notes"]
    p1_notes = channels["pulse1"]["notes"]
    tri_boundaries = boundaries["triangle"]
    p1_boundaries = boundaries["pulse1"]
    for frame in range(WINDOW_START, WINDOW_END + 1):
        idx = frame + audio_offset
        tri = tri_notes[frame]
        prev_tri = tri_notes[frame - 1] if frame > 0 else tri
        p1 = p1_notes[frame]
        prev_p1 = p1_notes[frame - 1] if frame > 0 else p1
        low = low_env[idx] if 0 <= idx < len(low_env) else 0.0
        high = high_env[idx] if 0 <= idx < len(high_env) else 0.0
        low_norm = low / max_low
        high_norm = high / max_high

        tri_hidden = (
            frame in tri_boundaries
            and tri["linear"] > 0
            and prev_tri["linear"] > 0
            and tri["period"] == prev_tri["period"]
            and reg_view[frame]["write_masks"]["triangle"] != 0
        )
        p1_hidden = (
            frame in p1_boundaries
            and p1["vol"] > 0
            and prev_p1["vol"] > 0
            and p1["period"] == prev_p1["period"]
            and reg_view[frame]["write_masks"]["pulse1"] != 0
        )

        release_class = classify_frame(
            frame,
            tri,
            prev_tri,
            frame in tri_boundaries,
            tri_hidden,
            low_norm,
            high_norm,
        )
        rows.append(
            {
                "frame": frame,
                "audio_frame": idx,
                "triangle_period": tri["period"],
                "triangle_linear": tri["linear"],
                "triangle_boundary": frame in tri_boundaries,
                "triangle_hidden_retrigger": tri_hidden,
                "pulse1_hidden_retrigger": p1_hidden,
                "composite_attack": tri_hidden and p1_hidden,
                "audio_low": low,
                "audio_high": high,
                "audio_low_norm": low_norm,
                "audio_high_norm": high_norm,
                "release_class": release_class,
            }
        )

    return {
        "meta": {
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "best_audio_offset_frames": audio_offset,
            "source_nsf": str(NSF_PATH),
            "source_wav": str(WAV_PATH),
            "class_meanings": {
                "fresh_full_body": "fresh onset with strong low-band body",
                "fresh_attack_damped_body": "fresh onset with bright attack but reduced low-band body",
                "ringing_decay": "still sounding but body continuing to decay",
                "sustain_body": "steady audible body without special onset evidence",
                "effectively_muted": "not audibly carrying body in this model",
            },
        },
        "frames": rows,
    }


def build_report(ir: dict) -> str:
    rows = ir["frames"]
    highlights = [row for row in rows if row["frame"] in (928, 960, 961, 976)]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["release_class"]] = counts.get(row["release_class"], 0) + 1
    lines = [
        "# Wizards & Warriors Title Release IR Report",
        "",
        "## Summary",
        "",
        "- This artifact classifies frame-level triangle body behavior in the disputed title phrase.",
        f"- Window: `{ir['meta']['window_start']}-{ir['meta']['window_end']}`.",
        f"- Audio offset: `{ir['meta']['best_audio_offset_frames']}` frames.",
        "",
        "## Class Counts",
        "",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- `{key}`: `{value}` frame(s).")
    lines.extend([
        "",
        "## Key Frames",
        "",
    ])
    for row in highlights:
        lines.append(
            f"- Frame `{row['frame']}`: class=`{row['release_class']}`, "
            f"tri_hidden=`{row['triangle_hidden_retrigger']}`, pulse1_hidden=`{row['pulse1_hidden_retrigger']}`, "
            f"composite=`{row['composite_attack']}`, low_norm=`{row['audio_low_norm']:.2f}`, high_norm=`{row['audio_high_norm']:.2f}`."
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Frame `928` should read as a strong bass-body onset.",
        "- Frame `960` should read as a fresh attack with reduced body, not as a continuing full sustain.",
        "- Frame `976` should read as the next full-bodied bass onset.",
        "",
        "This is the release-side evidence for adding a damping/release field to the middle layer.",
    ])
    return "\n".join(lines)


def main() -> None:
    ir = build_release_ir()
    OUT_JSON.write_text(json.dumps(ir, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_report(ir), encoding="utf-8")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()
