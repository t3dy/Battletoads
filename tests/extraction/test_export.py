"""Tests for export layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.export.midi_export import (
    validate_export_readiness,
    frames_to_midi_ticks,
    note_event_to_midi_note,
    _pitch_string_to_midi,
)
from nesml.models.song import Song, ChannelStream
from nesml.models.events import NoteEvent
from nesml.models.timing import TempoModel
from nesml.models.core import Confidence


class TestMIDIExport:
    def test_readiness_empty(self):
        s = Song(song_id=0)
        issues = validate_export_readiness(s)
        assert any("no channels" in i.lower() for i in issues)

    def test_readiness_no_events(self):
        s = Song(
            song_id=0,
            channels={"pulse1": ChannelStream(channel="pulse1", events=[])},
        )
        issues = validate_export_readiness(s)
        assert any("no channels have events" in i.lower() for i in issues)

    def test_readiness_ok(self):
        s = Song(
            song_id=0,
            channels={"pulse1": ChannelStream(
                channel="pulse1",
                events=[NoteEvent(frame=0, period=253, confidence=Confidence.runtime(0.9))],
            )},
            tempo_models=[TempoModel(frames_per_tick=6)],
        )
        issues = validate_export_readiness(s)
        errors = [i for i in issues if i.startswith("ERROR")]
        assert len(errors) == 0

    def test_pitch_string_to_midi(self):
        assert _pitch_string_to_midi("C4") == 60
        assert _pitch_string_to_midi("A4") == 69
        assert _pitch_string_to_midi("C#4") == 61
        assert _pitch_string_to_midi("Bb3") == 58
        assert _pitch_string_to_midi("C0") == 12

    def test_note_event_to_midi(self):
        e = NoteEvent(frame=0, midi_note=69)
        assert note_event_to_midi_note(e) == 69

        e2 = NoteEvent(frame=0, pitch="A4")
        assert note_event_to_midi_note(e2) == 69

        e3 = NoteEvent(frame=0, period=253)
        assert note_event_to_midi_note(e3) is None

    def test_frames_to_ticks(self):
        t = TempoModel(bpm_estimate=120.0)
        ticks = frames_to_midi_ticks(60, t, ppqn=480)
        # 60 frames at 60Hz = 1 second; 120 BPM = 2 beats/sec; 2 * 480 = 960
        assert abs(ticks - 960) < 10

    def test_frames_to_ticks_no_tempo(self):
        ticks = frames_to_midi_ticks(60, None, ppqn=480)
        # Should use 120 BPM default
        assert ticks > 0
