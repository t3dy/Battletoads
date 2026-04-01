# FamiTracker Driver — Research Notes

## Status: Not Started

## Overview

FamiTracker is a modern NES music tracker with a well-documented NSF export driver. Its format serves as an excellent validation target since the data structures are fully known.

## Known Characteristics

- Instrument definitions as macro sets (volume, arpeggio, pitch, hi-pitch, duty).
- Pattern-based song structure with order list.
- Effects column per channel (vibrato, portamento, arpeggio, etc.).
- Well-documented binary format.

## Value as Validation Target

Because the FamiTracker format is fully documented, it can be used to validate the pipeline:
1. Export an NSF from FamiTracker with known content.
2. Trace the NSF playback.
3. Run the pipeline.
4. Compare pipeline output against the known FamiTracker module data.

## Confidence

Format characteristics are **verified** (confidence = 1.0) — this is an open-source, documented format.
