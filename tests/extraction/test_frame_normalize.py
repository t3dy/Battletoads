"""Tests for frame normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.trace_ingest import load_trace
from nesml.frame_normalize import (
    normalize_by_frame,
    frame_range,
    channel_activity_summary,
    extract_channel_writes,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_simple_pulse():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    frames = normalize_by_frame(trace)

    # Should have 4 frames with writes (0, 15, 30, 60)
    assert len(frames) == 4
    assert frames[0]["frame"] == 0
    assert frames[-1]["frame"] == 60


def test_frame_range():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    frames = normalize_by_frame(trace)
    fr = frame_range(frames)
    assert fr == (0, 60)


def test_frame_range_empty():
    assert frame_range([]) is None


def test_channel_activity():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    frames = normalize_by_frame(trace)
    activity = channel_activity_summary(frames)

    assert "pulse1" in activity
    assert "triangle" in activity
    assert "noise" in activity
    assert activity["pulse1"] >= 2
    assert activity["triangle"] >= 1


def test_extract_channel_writes():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    frames = normalize_by_frame(trace)
    pulse_writes = extract_channel_writes(frames, "pulse1")

    assert len(pulse_writes) > 0
    assert all(w["frame"] >= 0 for w in pulse_writes)


def test_normalize_empty():
    frames = normalize_by_frame({"writes": []})
    assert frames == []


def test_channels_bucketed_correctly():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    frames = normalize_by_frame(trace)

    # Frame 0 should have pulse1, triangle, noise, and status
    f0 = frames[0]
    assert "pulse1" in f0["channels"]
    assert "triangle" in f0["channels"]
    assert "noise" in f0["channels"]
