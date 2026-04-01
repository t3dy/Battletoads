"""Trace ingestion — parse emulator APU write logs into normalized trace format.

Supports multiple emulator output formats. Each format gets a dedicated parser
function that returns a list of raw write dicts. The main entry point auto-detects
format or accepts explicit format selection.

Supported formats (Phase 1):
  - nesml_json: native NES Music Lab JSON trace format
  - mesen_txt:  Mesen-style plain-text APU log (planned)
  - fceux_txt:  FCEUX-style trace log (planned)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TraceIngestError(Exception):
    """Raised when trace ingestion fails."""


def load_trace(path: str | Path, format: str | None = None) -> dict:
    """Load and normalize a trace file into the internal trace format.

    Args:
        path: Path to the trace file.
        format: Explicit format name. If None, auto-detect from extension/content.

    Returns:
        A dict conforming to the trace schema (schema_version, metadata, writes).

    Raises:
        TraceIngestError: If the file cannot be parsed.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    if format is None:
        format = _detect_format(path)

    parsers = {
        "nesml_json": _parse_nesml_json,
        "mesen_txt": _parse_mesen_txt,
        "fceux_txt": _parse_fceux_txt,
    }

    parser = parsers.get(format)
    if parser is None:
        raise TraceIngestError(f"Unknown trace format: {format!r}")

    return parser(path)


def _detect_format(path: Path) -> str:
    """Auto-detect trace format from file extension and content."""
    if path.suffix.lower() == ".json":
        return "nesml_json"
    # Future: inspect file header for Mesen/FCEUX markers
    raise TraceIngestError(
        f"Cannot auto-detect trace format for {path.name}. "
        f"Specify format explicitly."
    )


def _parse_nesml_json(path: Path) -> dict:
    """Parse a NES Music Lab native JSON trace file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _validate_trace_structure(data)
    return data


def _validate_trace_structure(data: Any) -> None:
    """Validate minimal structural requirements of a trace dict."""
    if not isinstance(data, dict):
        raise TraceIngestError("Trace root must be a JSON object.")
    if "writes" not in data:
        raise TraceIngestError("Trace must contain a 'writes' array.")
    if not isinstance(data["writes"], list):
        raise TraceIngestError("'writes' must be an array.")

    for i, w in enumerate(data["writes"]):
        if not isinstance(w, dict):
            raise TraceIngestError(f"Write at index {i} must be an object.")
        for field in ("frame", "address", "value"):
            if field not in w:
                raise TraceIngestError(
                    f"Write at index {i} missing required field '{field}'."
                )


def _parse_mesen_txt(path: Path) -> dict:
    """Parse a Mesen-format APU trace log. (Stub — Phase 2)"""
    raise TraceIngestError(
        "Mesen text format parser not yet implemented. "
        "Convert to nesml_json format first."
    )


def _parse_fceux_txt(path: Path) -> dict:
    """Parse a FCEUX-format trace log. (Stub — Phase 2)"""
    raise TraceIngestError(
        "FCEUX text format parser not yet implemented. "
        "Convert to nesml_json format first."
    )
