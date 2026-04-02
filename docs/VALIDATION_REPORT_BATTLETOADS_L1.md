# Validation Report: Battletoads Level 1 (Ragnarok's Canyon)

**Date**: 2026-04-01
**Pipeline**: trace_to_midi.py (Mesen CSV → MIDI+SysEx → REAPER)
**Source**: Mesen2 capture.csv (9,495 frames / 158.2s)
**Version**: v3 (with period mask fix)

## Command Run

```bash
python scripts/trace_to_midi.py "C:/Users/PC/Documents/Mesen2/capture.csv" \
  -o output/Battletoads_trace_v3/ --game Battletoads \
  --name "Ragnoraks_Canyon" --seg-num 3 --auto-segment
```

## Artifacts Produced

| File | Type | Path |
|------|------|------|
| MIDI (CC+SysEx) | Trace-derived | `output/Battletoads_trace_v3/midi/Battletoads_trace_01_Ragnoraks_Canyon_v1.mid` |
| Console RPP | CC-driven synth | `output/Battletoads_trace_v3/reaper/Battletoads_trace_01_Ragnoraks_Canyon_v1.rpp` |
| APU2 RPP | SysEx register replay | `output/Battletoads_trace_v3/reaper/Battletoads_trace_01_Ragnoraks_Canyon_APU2_v1.rpp` |

## MIDI Content Summary

| Track | Channel | Notes | CC11 (vol) | CC12 (duty) | SysEx |
|-------|---------|-------|------------|-------------|-------|
| 0 | Metadata | 0 | 0 | 0 | 0 |
| 1 | Pulse 1 | 796 | 2,856 | 37 | 0 |
| 2 | Pulse 2 | 923 | 3,768 | 39 | 0 |
| 3 | Triangle | 414 | 414 | 0 | 0 |
| 4 | Noise | 198 | 0 | 0 | 0 |
| 5 | APU Regs | 0 | 0 | 0 | 37,972 |

**SysEx**: 9,493 frames x 4 channels = 37,972 messages. One per channel per frame.

## What Verified Successfully

### 1. Sweep Unit Vibrato Preservation (PASS)

Source capture shows ±4 period oscillation on Pulse 2 (frames 400-460):
```
Frame 403: period 669 → 673 (+4)
Frame 405: period 673 → 669 (-4)
Frame 407: period 669 → 665 (-4)
...pattern continues at 2-frame intervals
```

SysEx track encodes identical oscillation pattern. The APU2 synth will replay this as hardware sweep vibrato — the "fretless bass slide" that defines Battletoads' groove.

**Note**: This oscillation is NOT captured in CC11/CC12. The Console path misses it entirely. Only the APU2/SysEx path preserves sweep.

### 2. Volume Envelope Encoding (PASS)

Pulse 2 CC11 values decode to correct NES volumes:
```
CC11=48 → NES vol 6 (attack)
CC11=40 → NES vol 5 (decay start)
CC11=32 → NES vol 4
CC11=24 → NES vol 3
CC11=16 → NES vol 2
CC11= 8 → NES vol 1 (near-silent)
```

Round-trip encoding: `vol * 8` → `floor(cc11 / 8 + 0.5)` is lossless for all NES volumes 0-15.

### 3. Period Mask Fix (CRITICAL BUG FOUND AND FIXED)

**Bug**: Mesen capture stores `$4006_period` as raw `$4007<<8|$4006`, including length counter bits from $4007[7:3]. The NES period register is only 11 bits (max 2047). Values like 2717 exceed this, causing MIDI notes to map 2 octaves too low.

**Impact before fix**:
- P2: 651 notes, range MIDI 26-81 (D1-A5). D1 is BELOW NES pulse minimum.
- P1: range starts at F1 (MIDI 29). Also below minimum.

**Impact after fix**:
- P2: 923 notes, range MIDI 33-81 (A1-A5). A1 is the NES pulse minimum (~55 Hz).
- P1: range starts at A1 (MIDI 33). Correct.
- 272 additional P2 notes recovered that were being dropped as out-of-range.

**Fix location**: `trace_to_midi.py:mask_period()` — masks raw values with `& 0x7FF`.

### 4. SysEx Register Packing (PASS — was already correct)

The `parse_mesen_registers` function already did `state['p2_period'] & 0xFF` and `>> 8 & 0x07` for packing, which implicitly masks to 11 bits. The APU2 path was producing correct pitches even before the fix. Only the CC/MIDI path was wrong.

### 5. Segment Detection (PASS)

Auto-segmentation detected 1 continuous segment (frames 0-9494). This matches expectations — the capture is pure Level 1 gameplay without silence gaps.

### 6. SFX Filtering (PASS — conservative)

266 frames zeroed as ultrasonic artifacts (period < 20 while sounding). This is the conservative filter — it only catches hardware artifacts, not gameplay SFX. Music-SFX separation needs human judgment.

## What Failed / Remains Unverified

### 1. No Ear-Check Against Game Audio

The MIDI and RPP files exist and are structurally valid, but nobody has opened them in REAPER and listened. Structure verification is not fidelity verification.

**Status**: Verified by structure only. NOT verified by listening.

### 2. Console vs APU2 Path Agreement

Before the period mask fix, these paths disagreed by 2 octaves on Pulse 2. After the fix, the MIDI notes should agree with the SysEx register periods. This needs confirmation by opening both RPPs and comparing.

**Status**: Likely fixed. NOT verified by listening.

### 3. Noise Channel Timbre

The noise channel has 198 hits mapped to 3 drum buckets (kick/snare/hat). The NES has 16 distinct noise periods and a mode bit (long/short sequence). The current mapping loses 13 timbres and ignores mode entirely.

**Status**: Known limitation. Mode bit is in SysEx but not in MIDI CC.

### 4. DPCM Channel

The Mesen capture shows 1 DPCM state change. Battletoads may use DPCM sparingly or the capture didn't trigger it. Currently not extracted to any MIDI track.

**Status**: Not captured. Low priority for Level 1.

### 5. Triangle Period Mask

Triangle periods from `$400A_period` are also masked. Need to verify whether Mesen reports triangle periods the same way (with length counter bits). Triangle range B1-D#4 looks plausible for NES triangle (min period ~2 gives ~27 kHz, max period ~2047 gives ~27 Hz ≈ A0).

**Status**: Probably correct. Not independently verified.

## Is This Good Enough to Scale Up?

**No — not yet.** The critical path is:

1. **Ear-check the v3 output in REAPER.** Open both Console and APU2 RPPs. Compare to the reference MP3 (`output/Battletoads/mp3/`). The period mask fix is mathematically correct but needs human confirmation.

2. **Confirm the APU2 synth actually reads SysEx.** The SysEx data is in the MIDI, but the RPP needs to route it correctly. Open the APU2 RPP, check FX chain, hit play.

3. **Compare one loop cycle** to identify SFX contamination frames. The capture has gameplay SFX mixed in. Compare two full loops of the music pattern — frames that differ are SFX.

## Exact Next Steps (max 3)

1. **Human ear-check**: Open `output/Battletoads_trace_v3/reaper/Battletoads_trace_01_Ragnoraks_Canyon_APU2_v1.rpp` in REAPER. Listen. Compare to game audio or reference MP3. Report: does the bass groove sound right?

2. **Loop comparison**: Identify the loop point in the Level 1 music (should repeat every ~30-40 seconds). Compare frames from cycle 1 vs cycle 2. Frames that differ are SFX to filter.

3. **Confirm period mask doesn't affect other games**: Run `nsf_to_reaper.py` for a known-good game (Castlevania) and verify the output hasn't changed. The mask is in trace_to_midi.py only, so it shouldn't affect the NSF path, but verify.

## Repo Changes Needed

- [x] `trace_to_midi.py`: Add `mask_period()` function, apply to all period reads from CSV
- [ ] Commit v3 output and the fix
- [ ] Push to t3dy/Battletoads
- [ ] Update HANDOVER_BATTLETOADS.md with this validation report findings

## Open Questions (Testable Hypotheses)

1. **H1**: "Triangle `$400A_period` values also include length counter bits from `$400B`." Test: check if any triangle period value > 2047 in the raw capture.

2. **H2**: "The 266 filtered 'artifact' frames include some real SFX the user wants to hear." Test: unfilter, listen, compare. The filter is conservative but may still catch intentional high-frequency effects.

3. **H3**: "The APU2 synth correctly handles the SysEx register format from trace_to_midi.py." Test: open APU2 RPP, monitor the SysEx track, check if the synth decodes register bytes correctly. If sweep vibrato is audible, this confirms the full SysEx round-trip.
