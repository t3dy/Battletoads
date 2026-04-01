"""Tests for symbolic music models."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.models.core import Confidence, SourceType, Provenance, ProvenanceSource
from nesml.models.events import NoteEvent, RestEvent, LoopPoint, JumpCall, UnknownCommand
from nesml.models.instruments import (
    InstrumentBehavior, VolumeEnvelope, PitchEnvelope, DutySequence, ArpeggioMacro,
)
from nesml.models.timing import TempoModel, MeterHypothesis
from nesml.models.song import Song, ChannelStream, Pattern, PatternRef
import pytest


class TestConfidence:
    def test_valid_range(self):
        c = Confidence(0.5, SourceType.HEURISTIC)
        assert c.score == 0.5

    def test_invalid_range(self):
        with pytest.raises(ValueError):
            Confidence(1.5, SourceType.MANUAL)

    def test_factory_methods(self):
        assert Confidence.manual().score == 1.0
        assert Confidence.manual().verified is True
        assert Confidence.provisional().score == 0.0
        assert Confidence.static_parse(0.8).source_type == SourceType.STATIC_PARSE
        assert Confidence.runtime(0.9).source_type == SourceType.RUNTIME_TRACE
        assert Confidence.reconciled(0.85).source_type == SourceType.RECONCILED

    def test_to_dict(self):
        c = Confidence.heuristic(0.6, "tempo guess")
        d = c.to_dict()
        assert d["score"] == 0.6
        assert d["source_type"] == "heuristic"
        assert d["reason"] == "tempo guess"

    def test_source_type_ordering(self):
        assert SourceType.MANUAL < SourceType.PROVISIONAL
        assert SourceType.STATIC_PARSE < SourceType.HEURISTIC


class TestNoteEvent:
    def test_minimal(self):
        e = NoteEvent(frame=10, period=253, confidence=Confidence.runtime(1.0))
        d = e.to_dict()
        assert d["type"] == "note"
        assert d["frame"] == 10
        assert d["period"] == 253

    def test_full(self):
        e = NoteEvent(
            frame=10, period=253, pitch="A4", midi_note=69,
            duration_frames=15, volume=12, duty=2,
            instrument_ref="inst_0",
            confidence=Confidence.reconciled(0.9),
        )
        d = e.to_dict()
        assert d["pitch"] == "A4"
        assert d["midi_note"] == 69
        assert d["instrument_ref"] == "inst_0"


class TestInstrumentBehavior:
    def test_volume_envelope(self):
        ve = VolumeEnvelope(
            values=[15, 14, 12, 10, 8, 6, 6, 6],
            loop_index=5,
            confidence=Confidence.static_parse(0.7),
        )
        assert ve.length == 8
        d = ve.to_dict()
        assert d["type"] == "volume_envelope"
        assert d["loop_index"] == 5

    def test_instrument_is_not_preset(self):
        inst = InstrumentBehavior(
            id="inst_0",
            is_driver_defined=False,
            volume_envelope=VolumeEnvelope(values=[15, 12, 8, 4]),
            duty_sequence=DutySequence(values=[2, 1, 2, 1]),
            confidence=Confidence.heuristic(0.5),
        )
        d = inst.to_dict()
        assert d["is_driver_defined"] is False

    def test_instrument_with_driver_support(self):
        inst = InstrumentBehavior(
            id="ft_inst_3",
            label="Lead Square",
            is_driver_defined=True,
            confidence=Confidence.static_parse(0.9),
        )
        d = inst.to_dict()
        assert d["is_driver_defined"] is True


class TestTempoModel:
    def test_derived_bpm(self):
        t = TempoModel(
            frame_rate_hz=60.0988,
            frames_per_tick=6,
            ticks_per_row=1,
        )
        bpm = t.derived_bpm
        assert bpm is not None
        assert 140 < bpm < 160  # ~150 BPM at 6 frames/tick

    def test_seconds_per_tick(self):
        t = TempoModel(frames_per_tick=6)
        assert t.seconds_per_tick is not None
        assert abs(t.seconds_per_tick - 0.0999) < 0.001


class TestSong:
    def test_empty_song(self):
        s = Song(song_id=0, rom_name="test")
        d = s.to_dict()
        assert d["schema_version"] == "0.2.0"
        assert d["song_id"] == 0
        assert d["channels"] == {}

    def test_song_with_patterns(self):
        pat = Pattern(
            id="pat_0",
            events=[
                NoteEvent(frame=0, period=253, confidence=Confidence.static_parse(0.8)),
                RestEvent(frame=15, duration_frames=5, confidence=Confidence.static_parse(0.8)),
            ],
            rom_offset=0x8100,
        )
        ch = ChannelStream(
            channel="pulse1",
            order_list=[PatternRef("pat_0", confidence=Confidence.static_parse(0.7))],
            confidence=Confidence.static_parse(0.7),
        )
        s = Song(
            song_id=1,
            rom_name="test_rom",
            channels={"pulse1": ch},
            patterns={"pat_0": pat},
        )
        d = s.to_dict()
        assert "pat_0" in d["patterns"]
        assert d["channels"]["pulse1"]["order_list"][0]["pattern_id"] == "pat_0"
        assert len(d["patterns"]["pat_0"]["events"]) == 2

    def test_channel_stream_is_pattern_based(self):
        ch = ChannelStream(channel="pulse1")
        assert ch.is_pattern_based is False
        ch.order_list.append(PatternRef("p0"))
        assert ch.is_pattern_based is True


class TestJumpCall:
    def test_kinds(self):
        j = JumpCall(kind=JumpCall.Kind.CALL, source_offset=0x8100, target_offset=0x8200)
        d = j.to_dict()
        assert d["kind"] == "call"
        assert d["source_offset"] == 0x8100


class TestUnknownCommand:
    def test_preserves_context(self):
        u = UnknownCommand(
            offset=0x8150,
            opcode=0xFE,
            surrounding_bytes=b"\x00\x01\xFE\x03\x04",
            hypothesis="possible tempo change command",
        )
        d = u.to_dict()
        assert d["opcode"] == 0xFE
        assert d["surrounding_bytes"] == "0001fe0304"
        assert "tempo" in d["hypothesis"]
