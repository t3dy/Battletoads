"""NES Music Lab — Typed symbolic music models.

This package defines the middle-layer symbolic representation between
low-level APU events and exported MIDI/REAPER artifacts.

Key design principles:
- NES "instruments" are temporal behaviors, not fixed presets.
- Pattern/subroutine structure from static analysis must be preserved,
  not flattened into playback order prematurely.
- Every inferred value carries confidence and provenance.
"""

from nesml.models.core import (
    Confidence,
    Provenance,
    SourceType,
)
from nesml.models.song import (
    Song,
    ChannelStream,
    Pattern,
    PatternRef,
)
from nesml.models.events import (
    NoteEvent,
    RestEvent,
    LoopPoint,
    JumpCall,
    DPCMTriggerEvent,
    ExpansionAudioEvent,
    UnknownCommand,
)
from nesml.models.timing import (
    TempoModel,
    MeterHypothesis,
)
from nesml.models.instruments import (
    InstrumentBehavior,
    VolumeEnvelope,
    PitchEnvelope,
    DutySequence,
    ArpeggioMacro,
)
