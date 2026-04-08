#!/usr/bin/env python3
"""Export a first-class audible-state IR for the W&W title phrase.

This turns the articulation breakthrough into an inspectable middle-layer
artifact instead of leaving it as a prose conclusion.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(r"C:\Dev\NSFRIPPER")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_ww_title_articulation import (  # noqa: E402
    ATTACK_FOCUS,
    NSF_PATH,
    PHRASE_FRAMES,
    WAV_PATH,
    best_audio_offset,
    build_frame_register_view,
    channel_frame_metrics,
    frame_rms_envelope,
    load_audio,
    zscores,
)
from scripts.nsf_to_reaper import NsfEmulator, frames_to_channel_data, load_wizards_and_warriors_note_boundaries  # noqa: E402


OUT_JSON = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_audible_state_ir.json"
OUT_MD = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_audible_state_ir_report.md"

TARGET_CHANNELS = ("pulse1", "pulse2", "triangle")
WINDOW_START = 880
WINDOW_END = 1016


def midi_note_for_frame(channel: str, frame_data: dict) -> int:
    period = frame_data["period"]
    if channel == "triangle":
        if frame_data["linear"] <= 0 or period <= 2:
            return 0
        div = 32
    else:
        if frame_data["vol"] <= 0 or period <= 8:
            return 0
        div = 16
    import math

    freq = 1789773 / (div * (period + 1))
    return round(69 + 12 * math.log2(freq / 440))


def build_frame_ir(frames: list[dict], channels: dict, boundaries: dict, reg_view: list[dict]) -> dict:
    metric_maps = {
        ch: {row["frame"]: row for row in channel_frame_metrics(ch, channels, boundaries, reg_view)}
        for ch in TARGET_CHANNELS
    }

    audio, sr = load_audio(WAV_PATH)
    high_env = frame_rms_envelope(audio, sr, "high")
    low_env = frame_rms_envelope(audio, sr, "low")
    onset_frames = sorted(set(boundaries["pulse1"]) | set(boundaries["triangle"]))
    onset_frames = [f for f in onset_frames if 0 < f < 1500]
    alignment = best_audio_offset(high_env, onset_frames)
    audio_offset = int(alignment["offset_frames"])

    frame_rows = []
    for frame in range(WINDOW_START, WINDOW_END + 1):
        channel_rows = {}
        hidden_channels = []
        parser_channels = []
        visible_period_channels = []
        for ch in TARGET_CHANNELS:
            note = channels[ch]["notes"][frame]
            prev = channels[ch]["notes"][frame - 1] if frame > 0 else note
            metric = metric_maps[ch].get(frame)
            if ch == "triangle":
                sounding = note["linear"] > 0 and note["period"] > 2
                effective_level = note["linear"]
            else:
                sounding = note["vol"] > 0 and note["period"] > 8
                effective_level = note["vol"]
            parser_boundary = frame in boundaries.get(ch, set())
            visible_period_attack = note["period"] != prev["period"] and sounding
            hidden_retrigger = bool(metric and metric["hidden_retrigger"])
            if hidden_retrigger:
                hidden_channels.append(ch)
            if parser_boundary:
                parser_channels.append(ch)
            if visible_period_attack:
                visible_period_channels.append(ch)
            if hidden_retrigger:
                articulation = "hidden_retrigger"
            elif visible_period_attack:
                articulation = "period_attack"
            elif parser_boundary and sounding:
                articulation = "parser_attack"
            elif sounding:
                articulation = "sustain"
            else:
                articulation = "silent"
            channel_rows[ch] = {
                "period": note["period"],
                "midi_note": midi_note_for_frame(ch, note),
                "sounding": sounding,
                "effective_level": effective_level,
                "parser_boundary": parser_boundary,
                "visible_period_attack": visible_period_attack,
                "write_mask": reg_view[frame]["write_masks"][ch],
                "same_value_writes": reg_view[frame]["same_value_writes"][ch],
                "hidden_retrigger": hidden_retrigger,
                "articulation": articulation,
            }

        audio_frame = frame + audio_offset
        row = {
            "frame": frame,
            "audio_frame": audio_frame,
            "audio_high_env": high_env[audio_frame] if 0 <= audio_frame < len(high_env) else None,
            "audio_low_env": low_env[audio_frame] if 0 <= audio_frame < len(low_env) else None,
            "channels": channel_rows,
            "composite_attack": len([ch for ch in ("pulse1", "triangle") if ch in hidden_channels]) >= 2,
            "composite_attack_channels": [ch for ch in ("pulse1", "triangle") if ch in hidden_channels],
            "parser_attack_channels": parser_channels,
            "visible_period_attack_channels": visible_period_channels,
        }
        frame_rows.append(row)

    high_vals = [row["audio_high_env"] for row in frame_rows if row["frame"] in PHRASE_FRAMES]
    low_vals = [row["audio_low_env"] for row in frame_rows if row["frame"] in PHRASE_FRAMES]
    high_z = zscores(high_vals)
    low_z = zscores(low_vals)
    phrase_positions = [i for i, row in enumerate(frame_rows) if row["frame"] in PHRASE_FRAMES]
    for idx, pos in enumerate(phrase_positions):
        frame_rows[pos]["audio_high_z_phrase"] = high_z[idx]
        frame_rows[pos]["audio_low_z_phrase"] = low_z[idx]

    return {
        "meta": {
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "best_audio_offset_frames": audio_offset,
            "best_audio_offset_seconds": audio_offset / 60.0,
            "source_nsf": str(NSF_PATH),
            "source_wav": str(WAV_PATH),
        },
        "frames": frame_rows,
    }


def compare_routes(frame_ir: dict) -> dict:
    note_only_missed = []
    latch_only_missed = []
    write_aware_hits = []
    composite_attack_frames = []

    for row in frame_ir["frames"]:
        frame = row["frame"]
        if row["composite_attack"]:
            composite_attack_frames.append(frame)
        for ch in ("pulse1", "triangle"):
            ch_state = row["channels"][ch]
            if not ch_state["hidden_retrigger"]:
                continue
            if not ch_state["visible_period_attack"]:
                latch_only_missed.append({"frame": frame, "channel": ch})
            if ch_state["parser_boundary"] and not ch_state["visible_period_attack"]:
                note_only_missed.append({"frame": frame, "channel": ch})
            if ch_state["write_mask"]:
                write_aware_hits.append({"frame": frame, "channel": ch})

    return {
        "note_only_missed_hidden_retriggers": note_only_missed,
        "latch_only_missed_hidden_retriggers": latch_only_missed,
        "write_aware_detectable_hidden_retriggers": write_aware_hits,
        "composite_attack_frames": composite_attack_frames,
        "conclusion": {
            "note_only": "Loses same-pitch attacks unless parser boundaries are explicitly projected.",
            "latch_only": "Still loses same-pitch attacks because latched period and gate look continuous.",
            "write_aware": "Can detect per-channel hidden retriggers, but does not by itself carry composite cross-channel attack classification.",
            "audible_state_ir": "Preserves per-channel retriggers plus composite attack markers needed for downstream playback decisions.",
        },
    }


def build_report(frame_ir: dict, route_compare: dict) -> str:
    composite_rows = [row for row in frame_ir["frames"] if row["composite_attack"]]
    phrase_rows = [row for row in frame_ir["frames"] if row["frame"] in PHRASE_FRAMES]

    lines = [
        "# Wizards & Warriors Title Audible-State IR Report",
        "",
        "## Summary",
        "",
        "- This artifact promotes the title breakthrough into a first-class middle layer.",
        "- It stores per-frame articulation state, hidden retriggers, and composite attacks.",
        f"- Window: `{WINDOW_START}-{WINDOW_END}`.",
        f"- Audio alignment offset: `{frame_ir['meta']['best_audio_offset_frames']}` frames.",
        "",
        "## Route Comparison",
        "",
        f"- Note-only misses `{len(route_compare['note_only_missed_hidden_retriggers'])}` hidden retrigger events in this window.",
        f"- Latch-only misses `{len(route_compare['latch_only_missed_hidden_retriggers'])}` hidden retrigger events in this window.",
        f"- Write-aware can see `{len(route_compare['write_aware_detectable_hidden_retriggers'])}` hidden retrigger events, but still lacks explicit composite classification.",
        f"- Composite attack frames in this window: `{route_compare['composite_attack_frames']}`.",
        "",
        "## Phrase Frames",
        "",
    ]
    for row in phrase_rows:
        p1 = row["channels"]["pulse1"]
        tri = row["channels"]["triangle"]
        lines.append(
            f"- Frame `{row['frame']}`: pulse1=`{p1['articulation']}`, "
            f"triangle=`{tri['articulation']}`, composite_attack=`{row['composite_attack']}`, "
            f"high-z=`{row.get('audio_high_z_phrase', 0.0):.2f}`, low-z=`{row.get('audio_low_z_phrase', 0.0):.2f}`."
        )
    lines.extend([
        "",
        "## Consequence",
        "",
        "The middle layer should preserve at least:",
        "",
        "- per-channel parser boundaries",
        "- per-channel write-aware hidden retriggers",
        "- composite cross-channel attack markers",
        "- attack vs sustain classification independent of note pitch change",
        "",
        "This is the information plain MIDI and latch-only replay fail to carry on their own.",
        "",
    ])
    if composite_rows:
        frames = ", ".join(str(row["frame"]) for row in composite_rows)
        lines.append(f"Strongest current composite-attack evidence frame(s): `{frames}`.")
    return "\n".join(lines)


def main() -> None:
    emu = NsfEmulator(NSF_PATH)
    frames = emu.play_song(1, WINDOW_END + 8)
    channels = frames_to_channel_data(frames)
    boundaries = load_wizards_and_warriors_note_boundaries(NSF_PATH, 1)
    reg_view = build_frame_register_view(frames)

    frame_ir = build_frame_ir(frames, channels, boundaries, reg_view)
    route_compare = compare_routes(frame_ir)
    artifact = {
        "frame_audible_state_ir": frame_ir,
        "route_comparison": route_compare,
    }

    OUT_JSON.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_report(frame_ir, route_compare), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
