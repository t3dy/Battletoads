#!/usr/bin/env python3
"""Full pipeline: NES ROM → MIDI + REAPER project + WAV + MP4 + YouTube description.

Extracts all tracks from a Konami NES ROM using the Maezawa driver parser,
renders audio, and packages everything for distribution.

Usage:
    python scripts/full_pipeline.py <rom_path> [--game-name NAME] [--output-dir DIR]
    python scripts/full_pipeline.py <rom_path> --tracks 1,2,5
    python scripts/full_pipeline.py <rom_path> --screenshot path/to/image.png
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extraction.drivers.konami.parser import KonamiCV1Parser, NoteEvent, RestEvent
from extraction.drivers.konami.midi_export import export_to_midi
from extraction.drivers.konami.frame_ir import parser_to_frame_ir
from scripts.render_wav import render_song, write_wav, SAMPLE_RATE


def detect_game_name(rom_path: Path) -> str:
    """Guess game name from ROM filename."""
    name = rom_path.stem
    # Strip common ROM dump suffixes
    for suffix in ["(U)", "(V1.0)", "(V1.1)", "[!]", "(VC)", "(PRG0)", "(PRG1)"]:
        name = name.replace(suffix, "")
    return name.strip().strip("-").strip()


def safe_filename(name: str) -> str:
    """Convert a name to a safe filename component."""
    return name.replace(" ", "_").replace("'", "").replace(",", "").replace(":", "")


def run_pipeline(rom_path: str, game_name: str = "", output_dir: str = "",
                 track_list: list[int] | None = None,
                 screenshot_path: str = "") -> dict:
    """Run the full extraction pipeline on a ROM.

    Returns a dict with paths to all generated files and metadata.
    """
    rom = Path(rom_path)
    if not rom.exists():
        raise FileNotFoundError(f"ROM not found: {rom}")

    if not game_name:
        game_name = detect_game_name(rom)

    game_safe = safe_filename(game_name)

    if not output_dir:
        output_dir = str(REPO_ROOT / "output" / game_safe)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    midi_dir = out_dir / "midi"
    wav_dir = out_dir / "wav"
    rpp_dir = out_dir / "reaper"
    midi_dir.mkdir(exist_ok=True)
    wav_dir.mkdir(exist_ok=True)
    rpp_dir.mkdir(exist_ok=True)

    print(f"=== {game_name} ===")
    print(f"ROM: {rom}")
    print(f"Output: {out_dir}")
    print()

    # Parse ROM
    parser = KonamiCV1Parser(str(rom))
    all_tracks = parser.list_tracks()
    num_tracks = len(all_tracks)

    if track_list:
        tracks_to_process = track_list
    else:
        tracks_to_process = list(range(1, num_tracks + 1))

    print(f"Tracks available: {num_tracks}")
    print(f"Processing: {len(tracks_to_process)} tracks")
    print()

    # Process each track
    track_results = []
    wav_files = []

    for track_num in tracks_to_process:
        track_name = f"Track {track_num:02d}"
        track_safe = f"track_{track_num:02d}"

        try:
            song = parser.parse_track(track_num)
            ir = parser_to_frame_ir(song)

            total_notes = sum(
                sum(1 for e in ch.events if isinstance(e, NoteEvent))
                for ch in song.channels
            )
            total_frames = ir.total_frames
            duration_sec = total_frames / 60.0

            if total_notes == 0:
                print(f"  SKIP Track {track_num:2d}: no notes")
                continue

            # Export MIDI
            midi_path = midi_dir / f"{game_safe}_{track_safe}.mid"
            export_to_midi(song, str(midi_path), game_name=game_name,
                           song_name=track_name)

            # Generate REAPER project
            rpp_path = rpp_dir / f"{game_safe}_{track_safe}.rpp"
            try:
                subprocess.run([
                    sys.executable, str(REPO_ROOT / "scripts" / "generate_project.py"),
                    "--midi", str(midi_path), "--nes-native",
                    "-o", str(rpp_path),
                ], capture_output=True, text=True, cwd=str(REPO_ROOT))
            except Exception as ex:
                print(f"  WARN Track {track_num:2d}: RPP generation failed ({ex})")

            # Render WAV
            wav_path = wav_dir / f"{game_safe}_{track_safe}.wav"
            audio = render_song(ir, song)
            write_wav(audio, wav_path)

            track_results.append({
                "track_num": track_num,
                "name": track_name,
                "notes": total_notes,
                "duration": duration_sec,
                "midi": str(midi_path),
                "wav": str(wav_path),
                "rpp": str(rpp_path),
            })
            wav_files.append(wav_path)

            print(f"  OK  Track {track_num:2d}: {total_notes:4d} notes  {duration_sec:5.1f}s")

        except Exception as ex:
            print(f"  ERR Track {track_num:2d}: {ex}")

    if not track_results:
        print("\nNo tracks exported successfully.")
        return {"game": game_name, "tracks": [], "error": "No tracks exported"}

    # Concatenate WAVs
    print(f"\nConcatenating {len(wav_files)} tracks...")
    silence_path = wav_dir / "silence_1s.wav"
    with wave.open(str(silence_path), 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.zeros(SAMPLE_RATE, dtype=np.int16).tobytes())

    concat_path = wav_dir / "concat.txt"
    concat_lines = []
    for i, wf in enumerate(wav_files):
        concat_lines.append(f"file '{wf.resolve().as_posix()}'")
        if i < len(wav_files) - 1:
            concat_lines.append(f"file '{silence_path.resolve().as_posix()}'")
    concat_path.write_text("\n".join(concat_lines), encoding="utf-8")

    full_wav = out_dir / f"{game_safe}_full_soundtrack.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_path), "-c:a", "pcm_s16le", str(full_wav),
    ], capture_output=True)

    # Compute timestamps
    offset = 0.0
    timestamps = []
    for tr in track_results:
        mins = int(offset // 60)
        secs = int(offset % 60)
        timestamps.append({
            "timestamp": f"{mins}:{secs:02d}",
            "name": tr["name"],
            "duration": tr["duration"],
        })
        offset += tr["duration"] + 1.0  # 1s gap

    # Create MP4
    mp4_path = out_dir / f"{game_safe}_full_soundtrack.mp4"
    img_source = screenshot_path if screenshot_path else None

    if not img_source:
        # Look for a screenshot in common locations
        for ext in ["png", "jpg", "jpeg", "bmp"]:
            candidates = list(out_dir.glob(f"*.{ext}")) + \
                         list((REPO_ROOT / "studio" / "reaper_projects").glob(f"*{game_safe}*.{ext}"))
            if candidates:
                img_source = str(candidates[0])
                break

    if img_source and Path(img_source).exists():
        print(f"Creating MP4 with image: {img_source}")
        result = subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_source,
            "-i", str(full_wav),
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", "1",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(mp4_path),
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  MP4 creation failed: {result.stderr[-200:]}")
    else:
        # No image — create audio-only MP4
        print("No screenshot found — creating audio-only MP4")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=640x480:r=1",
            "-i", str(full_wav),
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(mp4_path),
        ], capture_output=True)

    # YouTube description
    desc_path = out_dir / f"{game_safe}_youtube_description.txt"
    desc_lines = [
        f"{game_name} (NES) — Complete Soundtrack",
        f"Extracted directly from the ROM using NES Music Studio",
        "",
        f"Every track in this video was parsed from the original {game_name} ROM data.",
        f"The Konami pre-VRC sound driver (Maezawa variant) was reverse-engineered",
        f"and each channel's note data, volume envelopes, and timing were decoded",
        f"from the raw bytes.",
        "",
        "Track Listing:",
        "",
    ]
    for ts in timestamps:
        desc_lines.append(f"{ts['timestamp']} {ts['name']}")

    desc_lines.extend([
        "",
        "Technical Details:",
        "",
        f"- Source: {game_name} NES ROM",
        "- Driver: Konami Pre-VRC (Maezawa variant)",
        "- Extraction: Static ROM parsing with frame-accurate IR",
        "- Synthesis: Python NES APU emulation",
        "- Tools: NES Music Studio",
    ])
    desc_path.write_text("\n".join(desc_lines), encoding="utf-8")

    # Summary
    total_dur = sum(tr["duration"] for tr in track_results)
    print(f"\n=== Done: {game_name} ===")
    print(f"Tracks: {len(track_results)}")
    print(f"Duration: {total_dur:.0f}s ({total_dur/60:.1f} min)")
    print(f"Output: {out_dir}")
    print(f"  MIDI:  {midi_dir}")
    print(f"  WAV:   {wav_dir}")
    print(f"  RPP:   {rpp_dir}")
    print(f"  MP4:   {mp4_path}")
    print(f"  Desc:  {desc_path}")

    return {
        "game": game_name,
        "tracks": track_results,
        "timestamps": timestamps,
        "mp4": str(mp4_path),
        "wav": str(full_wav),
        "description": str(desc_path),
        "output_dir": str(out_dir),
    }


def main():
    ap = argparse.ArgumentParser(description="Full NES ROM to video pipeline")
    ap.add_argument("rom_path", help="Path to NES ROM file")
    ap.add_argument("--game-name", default="", help="Game name (auto-detected if omitted)")
    ap.add_argument("--output-dir", default="", help="Output directory")
    ap.add_argument("--tracks", default="", help="Comma-separated track numbers (default: all)")
    ap.add_argument("--screenshot", default="", help="Screenshot image for MP4 background")
    args = ap.parse_args()

    track_list = None
    if args.tracks:
        track_list = [int(t.strip()) for t in args.tracks.split(",")]

    run_pipeline(
        rom_path=args.rom_path,
        game_name=args.game_name,
        output_dir=args.output_dir,
        track_list=track_list,
        screenshot_path=args.screenshot,
    )


if __name__ == "__main__":
    main()
