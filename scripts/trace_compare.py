#!/usr/bin/env python3
"""Compare extracted frame IR against emulator APU trace.

Produces a frame-by-frame diff showing pitch, volume, duty, and
sounding-state mismatches between our parser output and ground truth.

Usage:
    python scripts/trace_compare.py [--frames N] [--start-frame F] [--game cv1|contra]

Outputs:
    docs/TraceComparison_<game>.md  (human-readable report)
    data/trace_diff_<game>.json     (machine-readable)
"""
# ---------------------------------------------------------------
# STATUS: MULTI_GAME (supports --game parameter)
# SCOPE: cv1, contra
# VALIDATED: 2026-03-28
# TRACE_RESULT: produces 0-mismatch reports for CV1 pulse
# KNOWN_LIMITATIONS:
#   - Contra trace validation is provisional (~91% pitch match)
# LAYER: tooling
# ---------------------------------------------------------------

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extraction.drivers.konami.parser import KonamiCV1Parser
from extraction.drivers.konami.contra_parser import ContraParser
from extraction.drivers.konami.frame_ir import (
    parser_to_frame_ir, trace_to_frame_ir, SongIR, FrameState, PITCH_NAMES,
    DriverCapability,
)

# ---------------------------------------------------------------------------
# Per-game configuration
# ---------------------------------------------------------------------------
GAME_CONFIGS = {
    "cv1": {
        "rom_path": REPO_ROOT / "extraction" / "roms" / "Castlevania (U) (V1.0) [!].nes",
        "trace_path": REPO_ROOT / "extraction" / "traces" / "castlevania" / "stage1.csv",
        "trace_start_frame": 111,
        "track": 2,
        "parser_class": "KonamiCV1Parser",
        "driver": None,  # uses default CV1 driver
        "report_path": REPO_ROOT / "docs" / "TraceComparison_CV1.md",
        "diff_path": REPO_ROOT / "data" / "trace_diff_cv1.json",
    },
    "contra": {
        "rom_path": REPO_ROOT / "AllNESRoms" / "All NES Roms (GoodNES)" / "USA" / "Contra (U) [!].nes",
        "trace_path": REPO_ROOT / "extraction" / "traces" / "contra" / "jungle.csv",
        "trace_start_frame": 155,
        "track": "jungle",
        "parser_class": "ContraParser",
        "driver": "contra",  # signals to use DriverCapability.contra()
        "report_path": REPO_ROOT / "docs" / "TraceComparison_Contra.md",
        "diff_path": REPO_ROOT / "data" / "trace_diff_contra.json",
    },
}

# Legacy constants kept for backward compat with --start-frame default
TRACE_START_FRAME = 111


def note_name(midi: int) -> str:
    if midi == 0:
        return "---"
    return f"{PITCH_NAMES[midi % 12]}{midi // 12 - 1}"


def compare_channels(extracted: SongIR, trace: SongIR, max_frames: int) -> dict:
    """Compare two IRs frame by frame. Returns structured diff."""
    results = {}

    ch_pairs = list(zip(extracted.channels, trace.channels))

    for ext_ch, tr_ch in ch_pairs:
        ch_name = ext_ch.channel_type
        diff = {
            "channel": ch_name,
            "total_frames": max_frames,
            "pitch_mismatches": 0,
            "volume_mismatches": 0,
            "duty_mismatches": 0,
            "sounding_mismatches": 0,
            "first_pitch_mismatch": None,
            "first_sounding_mismatch": None,
            "mismatch_regions": [],
            "frame_diffs": [],
        }

        in_mismatch = False
        mismatch_start = 0

        for f in range(max_frames):
            ext = ext_ch.get_frame(f)
            tr = tr_ch.get_frame(f)

            pitch_match = ext.midi_note == tr.midi_note
            vol_match = ext.volume == tr.volume
            duty_match = ext.duty == tr.duty or ch_name == "triangle"
            sounding_match = ext.sounding == tr.sounding

            any_mismatch = not (pitch_match and sounding_match)

            if not pitch_match and ext.sounding and tr.sounding:
                diff["pitch_mismatches"] += 1
                if diff["first_pitch_mismatch"] is None:
                    diff["first_pitch_mismatch"] = f

            if not vol_match and (ext.sounding or tr.sounding):
                diff["volume_mismatches"] += 1

            if not duty_match and (ext.sounding or tr.sounding):
                diff["duty_mismatches"] += 1

            if not sounding_match:
                diff["sounding_mismatches"] += 1
                if diff["first_sounding_mismatch"] is None:
                    diff["first_sounding_mismatch"] = f

            # Track mismatch regions
            if any_mismatch and not in_mismatch:
                mismatch_start = f
                in_mismatch = True
            elif not any_mismatch and in_mismatch:
                diff["mismatch_regions"].append((mismatch_start, f - 1))
                in_mismatch = False

            # Record individual frame diffs for first 20 mismatches
            if any_mismatch and len(diff["frame_diffs"]) < 50:
                diff["frame_diffs"].append({
                    "frame": f,
                    "ext_note": note_name(ext.midi_note),
                    "tr_note": note_name(tr.midi_note),
                    "ext_vol": ext.volume,
                    "tr_vol": tr.volume,
                    "ext_duty": ext.duty,
                    "tr_duty": tr.duty,
                    "ext_sounding": ext.sounding,
                    "tr_sounding": tr.sounding,
                })

        if in_mismatch:
            diff["mismatch_regions"].append((mismatch_start, max_frames - 1))

        results[ch_name] = diff

    return results


def generate_report(results: dict, max_frames: int, config: dict) -> str:
    """Generate a human-readable markdown report."""
    game_name = [k for k, v in GAME_CONFIGS.items() if v is config][0]
    trace_start = config["trace_start_frame"]

    lines = [
        f"# Trace Comparison: {game_name.upper()} (track: {config['track']})",
        "",
        f"Comparing parser output against emulator APU trace.",
        f"Trace start offset: frame {trace_start}",
        f"Frames compared: {max_frames}",
        "",
    ]

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Channel | Pitch Mismatches | Volume Mismatches | Duty Mismatches | Sounding Mismatches | First Pitch Error |")
    lines.append("|---------|-----------------|-------------------|-----------------|--------------------|--------------------|")

    for ch_name in ["pulse1", "pulse2", "triangle"]:
        if ch_name not in results:
            continue
        d = results[ch_name]
        fp = f"frame {d['first_pitch_mismatch']}" if d['first_pitch_mismatch'] is not None else "none"
        lines.append(
            f"| {ch_name} | {d['pitch_mismatches']} | {d['volume_mismatches']} "
            f"| {d['duty_mismatches']} | {d['sounding_mismatches']} | {fp} |"
        )

    lines.append("")

    # Mismatch regions
    lines.append("## Mismatch Regions")
    lines.append("")
    for ch_name in ["pulse1", "pulse2", "triangle"]:
        if ch_name not in results:
            continue
        d = results[ch_name]
        if d["mismatch_regions"]:
            lines.append(f"### {ch_name}")
            for start, end in d["mismatch_regions"][:20]:
                dur = end - start + 1
                lines.append(f"- frames {start}-{end} ({dur} frames, {dur/60:.2f}s)")
            if len(d["mismatch_regions"]) > 20:
                lines.append(f"- ... ({len(d['mismatch_regions']) - 20} more regions)")
            lines.append("")

    # Detailed frame diffs
    lines.append("## First Frame Diffs (per channel)")
    lines.append("")
    for ch_name in ["pulse1", "pulse2", "triangle"]:
        if ch_name not in results:
            continue
        d = results[ch_name]
        if d["frame_diffs"]:
            lines.append(f"### {ch_name}")
            lines.append("")
            lines.append("| Frame | Extracted | Trace | Ext Vol | Tr Vol | Ext Snd | Tr Snd |")
            lines.append("|-------|-----------|-------|---------|--------|---------|--------|")
            for fd in d["frame_diffs"][:30]:
                lines.append(
                    f"| {fd['frame']} | {fd['ext_note']} | {fd['tr_note']} "
                    f"| {fd['ext_vol']} | {fd['tr_vol']} "
                    f"| {fd['ext_sounding']} | {fd['tr_sounding']} |"
                )
            lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Compare extraction vs APU trace")
    ap.add_argument("--game", default="cv1", choices=list(GAME_CONFIGS.keys()),
                    help="Game to compare (default: cv1)")
    ap.add_argument("--frames", type=int, default=600, help="Number of frames to compare")
    ap.add_argument("--start-frame", type=int, default=None,
                    help="Trace frame where music starts (default: from game config)")
    ap.add_argument("--dump-frames", help="Dump raw trace values for frame range (e.g. 0-20)")
    ap.add_argument("--channel", default="all",
                    help="Channel to dump: pulse1, pulse2, triangle, all")
    args = ap.parse_args()

    config = GAME_CONFIGS[args.game]
    trace_path = config["trace_path"]
    trace_start = args.start_frame if args.start_frame is not None else config["trace_start_frame"]

    if args.dump_frames:
        # Dump mode: show raw trace values without parser comparison
        parts = args.dump_frames.split("-")
        dump_start = int(parts[0])
        dump_end = int(parts[1]) if len(parts) > 1 else dump_start + 20

        trace_ir = trace_to_frame_ir(
            str(trace_path),
            start_frame=trace_start,
            end_frame=trace_start + dump_end + 1,
        )

        channels = ["pulse1", "pulse2", "triangle"] if args.channel == "all" \
            else [args.channel]

        for ch_ir in trace_ir.channels:
            if ch_ir.channel_type not in channels:
                continue
            print(f"=== {ch_ir.name} (frames {dump_start}-{dump_end}) ===")
            print(f"{'frame':>5s} {'note':>5s} {'vol':>4s} {'duty':>4s} {'snd':>4s} {'period':>6s}")
            for f in range(dump_start, dump_end + 1):
                fs = ch_ir.get_frame(f)
                nn = note_name(fs.midi_note)
                print(f"{f:5d} {nn:>5s} {fs.volume:4d} {fs.duty:4d} "
                      f"{'Y' if fs.sounding else '.':>4s} {fs.period:6d}")
            print()
        sys.exit(0)

    # Parse track using the appropriate parser
    if config["parser_class"] == "ContraParser":
        print(f"Loading ROM and parsing track '{config['track']}' (Contra)...")
        parser_obj = ContraParser(str(config["rom_path"]))
        song = parser_obj.parse_track(config["track"])
        driver = DriverCapability.contra(parser_obj.envelope_tables)
        print("Converting to frame IR...")
        extracted_ir = parser_to_frame_ir(song, driver=driver)
    else:
        print(f"Loading ROM and parsing track {config['track']}...")
        parser_obj = KonamiCV1Parser(str(config["rom_path"]))
        song = parser_obj.parse_track(config["track"])
        print("Converting to frame IR...")
        extracted_ir = parser_to_frame_ir(song)

    print(f"Loading trace from {trace_path}...")
    trace_ir = trace_to_frame_ir(
        str(trace_path),
        start_frame=trace_start,
        end_frame=trace_start + args.frames,
    )

    print(f"Comparing {args.frames} frames...")
    results = compare_channels(extracted_ir, trace_ir, args.frames)

    # Print summary
    for ch_name in ["pulse1", "pulse2", "triangle"]:
        if ch_name not in results:
            continue
        d = results[ch_name]
        print(f"  {ch_name}: pitch={d['pitch_mismatches']} vol={d['volume_mismatches']} "
              f"sounding={d['sounding_mismatches']} mismatches")

    # Write report
    report = generate_report(results, args.frames, config)
    report_path = config["report_path"]
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport: {report_path}")

    # Write machine-readable diff
    diff_path = config["diff_path"]
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert tuples to lists for JSON
    json_results = {}
    for ch, d in results.items():
        jd = dict(d)
        jd["mismatch_regions"] = [list(r) for r in d["mismatch_regions"]]
        json_results[ch] = jd
    diff_path.write_text(json.dumps(json_results, indent=2), encoding="utf-8")
    print(f"Diff: {diff_path}")


if __name__ == "__main__":
    main()
