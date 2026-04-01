"""JSON schema validation for NES Music Lab output files.

Uses Python's built-in json module for loading. Schema validation is
lightweight — checks required fields and types without a full JSON Schema
library dependency (avoiding jsonschema as an external dep in Phase 1).

For full JSON Schema validation, install jsonschema and use validate_full().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).parent.parent.parent / "docs" / "schemas"


class ValidationError(Exception):
    """Raised when a document fails validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s): {'; '.join(errors[:3])}")


def load_schema(name: str) -> dict:
    """Load a schema from the docs/schemas directory.

    Args:
        name: Schema filename without path, e.g. 'analysis_schema.json'.
    """
    path = SCHEMA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_analysis(data: dict) -> list[str]:
    """Validate an analysis document against minimal structural requirements.

    Returns a list of error strings. Empty list = valid.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Root must be a JSON object."]

    for field in ("schema_version", "metadata", "channels", "provenance"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "metadata" in data and isinstance(data["metadata"], dict):
        for field in ("rom_name", "song_id"):
            if field not in data["metadata"]:
                errors.append(f"metadata missing required field: {field}")

    if "channels" in data and isinstance(data["channels"], dict):
        valid_channels = {"pulse1", "pulse2", "triangle", "noise", "dpcm"}
        for ch in data["channels"]:
            if ch not in valid_channels:
                errors.append(f"Unknown channel: {ch}")

    if "provenance" in data and isinstance(data["provenance"], dict):
        for field in ("generated_by", "generated_at", "sources"):
            if field not in data["provenance"]:
                errors.append(f"provenance missing required field: {field}")

    # Validate confidence ranges in events
    if "channels" in data and isinstance(data["channels"], dict):
        for ch_name, ch_data in data["channels"].items():
            if isinstance(ch_data, dict) and "events" in ch_data:
                for i, evt in enumerate(ch_data["events"]):
                    if "confidence" in evt:
                        c = evt["confidence"]
                        if not isinstance(c, (int, float)) or c < 0 or c > 1:
                            errors.append(
                                f"{ch_name}.events[{i}].confidence "
                                f"must be 0.0-1.0, got {c}"
                            )
                    if "source" in evt:
                        valid_sources = {
                            "trace", "parse", "manual", "heuristic", "provisional"
                        }
                        if evt["source"] not in valid_sources:
                            errors.append(
                                f"{ch_name}.events[{i}].source "
                                f"must be one of {valid_sources}, got {evt['source']!r}"
                            )

    return errors


def validate_trace(data: dict) -> list[str]:
    """Validate a trace document against minimal structural requirements."""
    errors = []

    if not isinstance(data, dict):
        return ["Root must be a JSON object."]

    for field in ("schema_version", "metadata", "writes"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "writes" in data:
        if not isinstance(data["writes"], list):
            errors.append("'writes' must be an array.")
        else:
            for i, w in enumerate(data["writes"][:10]):  # spot-check first 10
                for field in ("frame", "address", "value"):
                    if field not in w:
                        errors.append(f"writes[{i}] missing '{field}'")

    return errors
