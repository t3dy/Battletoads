"""Tests for schema validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.schema_validator import validate_analysis, validate_trace, load_schema


def test_load_analysis_schema():
    schema = load_schema("analysis_schema.json")
    assert schema["title"].startswith("NES Music Lab")


def test_load_trace_schema():
    schema = load_schema("trace_schema.json")
    assert "writes" in str(schema)


def test_validate_analysis_minimal_valid():
    doc = {
        "schema_version": "0.1.0",
        "metadata": {"rom_name": "test", "song_id": 1},
        "channels": {},
        "provenance": {
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "sources": [],
        },
    }
    errors = validate_analysis(doc)
    assert errors == []


def test_validate_analysis_missing_fields():
    errors = validate_analysis({})
    assert len(errors) == 4  # schema_version, metadata, channels, provenance


def test_validate_analysis_bad_channel():
    doc = {
        "schema_version": "0.1.0",
        "metadata": {"rom_name": "test", "song_id": 1},
        "channels": {"bogus_channel": {}},
        "provenance": {
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "sources": [],
        },
    }
    errors = validate_analysis(doc)
    assert any("Unknown channel" in e for e in errors)


def test_validate_analysis_bad_confidence():
    doc = {
        "schema_version": "0.1.0",
        "metadata": {"rom_name": "test", "song_id": 1},
        "channels": {
            "pulse1": {
                "events": [
                    {"frame": 0, "type": "note_on", "confidence": 1.5, "source": "trace"}
                ]
            }
        },
        "provenance": {
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "sources": [],
        },
    }
    errors = validate_analysis(doc)
    assert any("confidence" in e for e in errors)


def test_validate_analysis_bad_source():
    doc = {
        "schema_version": "0.1.0",
        "metadata": {"rom_name": "test", "song_id": 1},
        "channels": {
            "pulse1": {
                "events": [
                    {"frame": 0, "type": "note_on", "confidence": 0.5, "source": "magic"}
                ]
            }
        },
        "provenance": {
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "sources": [],
        },
    }
    errors = validate_analysis(doc)
    assert any("source" in e for e in errors)


def test_validate_trace_valid():
    doc = {
        "schema_version": "0.1.0",
        "metadata": {"source": "test"},
        "writes": [
            {"frame": 0, "address": "$4000", "value": 191}
        ],
    }
    errors = validate_trace(doc)
    assert errors == []


def test_validate_trace_missing_writes():
    errors = validate_trace({"schema_version": "0.1.0", "metadata": {}})
    assert any("writes" in e for e in errors)
