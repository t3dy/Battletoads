"""Trace format converters.

Converts emulator-specific trace formats into the NES Music Lab JSON trace format.

Supported conversions:
  - mesen_csv: Mesen Lua script CSV output (frame,address,value)
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConvertError(Exception):
    """Raised when trace conversion fails."""


def convert_mesen_csv(
    input_path: str | Path,
    output_path: str | Path,
    *,
    rom_name: str = "unknown",
    rom_sha256: str | None = None,
    region: str = "ntsc",
    notes: str | None = None,
) -> dict:
    """Convert a Mesen Lua script CSV to NES Music Lab trace JSON.

    CSV format: frame,address,value (with header row)
    Address format: $XXXX

    Returns the trace dict (also written to output_path).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    writes = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ConvertError("Empty CSV file")

        # Normalize header
        header = [h.strip().lower() for h in header]
        if header != ["frame", "address", "value"]:
            raise ConvertError(
                f"Unexpected CSV header: {header}. "
                f"Expected: ['frame', 'address', 'value']"
            )

        for i, row in enumerate(reader, start=2):
            if len(row) != 3:
                raise ConvertError(f"Row {i}: expected 3 columns, got {len(row)}")
            try:
                frame = int(row[0].strip())
                addr = row[1].strip()
                value = int(row[2].strip())
            except ValueError as e:
                raise ConvertError(f"Row {i}: parse error: {e}")

            # Normalize address format
            if not addr.startswith("$"):
                addr = f"${addr}"
            addr = addr.upper().replace("$", "$", 1)  # ensure $XXXX
            if len(addr) != 5:
                raise ConvertError(f"Row {i}: invalid address: {addr}")

            writes.append({
                "frame": frame,
                "address": addr,
                "value": value,
            })

    metadata: dict[str, Any] = {
        "source": "mesen",
        "rom_name": rom_name,
        "region": region,
        "converted_at": datetime.now(timezone.utc).isoformat(),
    }
    if rom_sha256:
        metadata["rom_sha256"] = rom_sha256
    if notes:
        metadata["notes"] = notes
    if writes:
        metadata["capture_start_frame"] = writes[0]["frame"]
        metadata["capture_end_frame"] = writes[-1]["frame"]

    trace = {
        "schema_version": "0.1.0",
        "metadata": metadata,
        "writes": writes,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2)

    return trace


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert emulator traces to NES Music Lab JSON format."
    )
    parser.add_argument("format", choices=["mesen_csv"],
                        help="Input trace format")
    parser.add_argument("input", help="Input trace file path")
    parser.add_argument("--output", "-o", required=True,
                        help="Output JSON path")
    parser.add_argument("--rom-name", default="unknown",
                        help="ROM name for metadata")
    parser.add_argument("--rom-sha256", default=None,
                        help="ROM SHA-256 hash")
    parser.add_argument("--region", default="ntsc",
                        choices=["ntsc", "pal", "dual"],
                        help="Region (default: ntsc)")
    parser.add_argument("--notes", default=None,
                        help="Freeform notes")

    args = parser.parse_args()

    if args.format == "mesen_csv":
        trace = convert_mesen_csv(
            args.input, args.output,
            rom_name=args.rom_name,
            rom_sha256=args.rom_sha256,
            region=args.region,
            notes=args.notes,
        )
        print(f"Converted {len(trace['writes'])} writes → {args.output}")
