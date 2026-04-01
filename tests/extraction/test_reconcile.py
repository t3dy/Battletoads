"""Tests for reconciliation layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.reconcile.align import (
    reconcile_channel,
    DiscrepancyType,
    Severity,
)


def test_perfect_match():
    static = [
        {"frame": 0, "type": "note", "period": 253},
        {"frame": 15, "type": "note", "period": 212},
    ]
    dynamic = [
        {"frame": 0, "type": "period_change", "period": 253},
        {"frame": 15, "type": "period_change", "period": 212},
    ]
    result = reconcile_channel(static, dynamic, "pulse1")
    assert result.matched_events == 2
    assert result.match_ratio == 1.0
    assert result.confidence_adjustment > 0


def test_timing_tolerance():
    static = [{"frame": 10, "type": "note", "period": 253}]
    dynamic = [{"frame": 11, "type": "period_change", "period": 253}]
    result = reconcile_channel(static, dynamic, "pulse1", timing_tolerance_frames=2)
    assert result.matched_events == 1
    timing_disc = [d for d in result.discrepancies if d.type == DiscrepancyType.TIMING_MISMATCH]
    assert len(timing_disc) == 1


def test_pitch_mismatch():
    static = [{"frame": 0, "type": "note", "period": 253}]
    dynamic = [{"frame": 0, "type": "period_change", "period": 200}]
    result = reconcile_channel(static, dynamic, "pulse1")
    assert result.matched_events == 1
    pitch_disc = [d for d in result.discrepancies if d.type == DiscrepancyType.PITCH_MISMATCH]
    assert len(pitch_disc) == 1
    assert pitch_disc[0].severity == Severity.ERROR


def test_missing_in_dynamic():
    static = [
        {"frame": 0, "type": "note", "period": 253},
        {"frame": 100, "type": "note", "period": 200},
    ]
    dynamic = [
        {"frame": 0, "type": "period_change", "period": 253},
    ]
    result = reconcile_channel(static, dynamic, "pulse1")
    assert result.matched_events == 1
    missing = [d for d in result.discrepancies if d.type == DiscrepancyType.MISSING_IN_DYNAMIC]
    assert len(missing) == 1


def test_missing_in_static():
    static = [{"frame": 0, "type": "note", "period": 253}]
    dynamic = [
        {"frame": 0, "type": "period_change", "period": 253},
        {"frame": 50, "type": "period_change", "period": 200},
    ]
    result = reconcile_channel(static, dynamic, "pulse1")
    missing = [d for d in result.discrepancies if d.type == DiscrepancyType.MISSING_IN_STATIC]
    assert len(missing) == 1


def test_empty_channels():
    result = reconcile_channel([], [], "pulse1")
    assert result.matched_events == 0
    assert result.match_ratio == 0.0


def test_low_match_ratio_penalty():
    static = [{"frame": i * 10, "type": "note", "period": 253} for i in range(10)]
    dynamic = [{"frame": 0, "type": "period_change", "period": 253}]
    result = reconcile_channel(static, dynamic, "pulse1")
    assert result.confidence_adjustment < 0
