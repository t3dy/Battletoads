#!/usr/bin/env python3
"""Convenience wrapper for converting Mesen CSV traces.

Usage:
    python convert_trace.py traces/castlevania/stage1.csv --rom-name castlevania

Outputs JSON to the same directory as the input file (same name, .json extension).
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nesml.dynamic_analysis.trace_convert import convert_mesen_csv


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_trace.py <input.csv> [--rom-name NAME]")
        print("")
        print("Converts a Mesen APU capture CSV to NES Music Lab JSON format.")
        print("Output goes to the same directory with .json extension.")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    # Parse --rom-name if given
    rom_name = input_path.stem
    for i, arg in enumerate(sys.argv):
        if arg == "--rom-name" and i + 1 < len(sys.argv):
            rom_name = sys.argv[i + 1]

    output_path = input_path.with_suffix(".json")

    trace = convert_mesen_csv(
        input_path, output_path,
        rom_name=rom_name,
        region="ntsc",
    )

    print(f"Converted {len(trace['writes'])} APU writes")
    print(f"Frames: {trace['metadata'].get('capture_start_frame', '?')} - {trace['metadata'].get('capture_end_frame', '?')}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
