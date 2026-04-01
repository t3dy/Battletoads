"""Tests for first-pass event stream generation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.trace_ingest import load_trace
from nesml.frame_normalize import normalize_by_frame
from nesml.event_stream import generate_event_stream

FIXTURES = Path(__file__).parent / "fixtures"


def test_pulse_events_generated():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    frames = normalize_by_frame(trace)
    events = generate_event_stream(frames)

    pulse1_events = events["pulse1"]
    assert len(pulse1_events) > 0

    # All events must have required fields
    for e in pulse1_events:
        assert "frame" in e
        assert "type" in e
        assert "confidence" in e
        assert "source" in e
        assert e["source"] == "trace"
        assert 0.0 <= e["confidence"] <= 1.0


def test_pulse_duty_change_detected():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    frames = normalize_by_frame(trace)
    events = generate_event_stream(frames)

    duty_events = [e for e in events["pulse1"] if e["type"] == "duty_change"]
    assert len(duty_events) >= 1


def test_pulse_period_change_detected():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    frames = normalize_by_frame(trace)
    events = generate_event_stream(frames)

    period_events = [e for e in events["pulse1"] if e["type"] == "period_change"]
    assert len(period_events) >= 1


def test_multi_channel_events():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    frames = normalize_by_frame(trace)
    events = generate_event_stream(frames)

    # All 5 channel keys should exist
    for ch in ("pulse1", "pulse2", "triangle", "noise", "dpcm"):
        assert ch in events

    # pulse1, triangle, noise should have events
    assert len(events["pulse1"]) > 0
    assert len(events["triangle"]) > 0
    assert len(events["noise"]) > 0


def test_noise_events():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    frames = normalize_by_frame(trace)
    events = generate_event_stream(frames)

    noise_events = events["noise"]
    types = {e["type"] for e in noise_events}
    # Should detect volume and period changes at minimum
    assert "volume_change" in types or "period_change" in types


def test_empty_trace():
    frames = normalize_by_frame({"writes": []})
    events = generate_event_stream(frames)
    for ch in ("pulse1", "pulse2", "triangle", "noise", "dpcm"):
        assert events[ch] == []
