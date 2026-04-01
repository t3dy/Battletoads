"""End-to-end smoke test: trace → normalize → events → validate.

Verifies the full pipeline from raw trace data through to a valid analysis document.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.trace_ingest import load_trace
from nesml.frame_normalize import (
    normalize_by_frame,
    frame_range,
    channel_activity_summary,
)
from nesml.event_stream import generate_event_stream
from nesml.schema_validator import validate_analysis

FIXTURES = Path(__file__).parent / "fixtures"


def _build_analysis_doc(
    trace_path: Path,
    rom_name: str,
    song_id: int,
) -> dict:
    """Run the full pipeline and assemble an analysis document."""
    # Step 1: Ingest
    trace = load_trace(trace_path)

    # Step 2: Normalize
    frames = normalize_by_frame(trace)
    fr = frame_range(frames)
    activity = channel_activity_summary(frames)

    # Step 3: Generate events
    events = generate_event_stream(frames)

    # Step 4: Assemble analysis document
    channels = {}
    for ch_name in ("pulse1", "pulse2", "triangle", "noise", "dpcm"):
        ch_events = events.get(ch_name, [])
        channels[ch_name] = {
            "active": ch_name in activity,
            "events": ch_events,
        }

    doc = {
        "schema_version": "0.1.0",
        "metadata": {
            "rom_name": rom_name,
            "song_id": song_id,
            "region": trace.get("metadata", {}).get("region", "ntsc"),
        },
        "timing": {
            "frame_rate_hz": 60.0988,
            "total_frames": fr[1] - fr[0] + 1 if fr else 0,
        },
        "channels": channels,
        "provenance": {
            "generated_by": "nesml/0.1.0/smoke_test",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {
                    "type": "trace",
                    "reference": str(trace_path),
                }
            ],
        },
    }

    return doc


def test_end_to_end_simple_pulse():
    """Full pipeline with simple pulse trace."""
    doc = _build_analysis_doc(
        FIXTURES / "simple_pulse_trace.json",
        rom_name="test_rom",
        song_id=0,
    )

    # Validate
    errors = validate_analysis(doc)
    assert errors == [], f"Validation errors: {errors}"

    # Check structure
    assert doc["schema_version"] == "0.1.0"
    assert doc["metadata"]["rom_name"] == "test_rom"
    assert doc["channels"]["pulse1"]["active"] is True
    assert len(doc["channels"]["pulse1"]["events"]) > 0
    assert doc["timing"]["total_frames"] == 61  # frames 0-60

    # All events must have required fields
    for evt in doc["channels"]["pulse1"]["events"]:
        assert "frame" in evt
        assert "type" in evt
        assert "confidence" in evt
        assert "source" in evt
        assert evt["source"] == "trace"
        assert 0.0 <= evt["confidence"] <= 1.0


def test_end_to_end_multi_channel():
    """Full pipeline with multi-channel trace."""
    doc = _build_analysis_doc(
        FIXTURES / "multi_channel_trace.json",
        rom_name="test_rom_multi",
        song_id=0,
    )

    errors = validate_analysis(doc)
    assert errors == [], f"Validation errors: {errors}"

    # Multiple channels should be active
    active_channels = [
        ch for ch, data in doc["channels"].items()
        if data["active"]
    ]
    assert len(active_channels) >= 3  # pulse1, triangle, noise

    # Provenance must be present
    assert doc["provenance"]["generated_by"].startswith("nesml/")
    assert len(doc["provenance"]["sources"]) >= 1


def test_end_to_end_event_types_present():
    """Verify expected event types appear in multi-channel output."""
    doc = _build_analysis_doc(
        FIXTURES / "multi_channel_trace.json",
        rom_name="test_rom_multi",
        song_id=0,
    )

    # Collect all event types across channels
    all_types = set()
    for ch_data in doc["channels"].values():
        for evt in ch_data["events"]:
            all_types.add(evt["type"])

    # Should see at least period and volume changes
    assert "period_change" in all_types
    assert "volume_change" in all_types or "duty_change" in all_types
