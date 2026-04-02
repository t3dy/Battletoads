# Leave No Turn Unstoned

A systematic framework for prompting Claude Code to exhaustively check
every music parameter, data range, and encoding pathway when reverse
engineering NES game audio — while staying flexible across different
sound drivers.

## The Core Problem

The NES APU has ~25 individually addressable parameters across 5
channels, updated 60 times per second. Each game's sound driver uses
these parameters differently. A systematic approach must:

1. Check every parameter at every level of the pipeline
2. Not assume any two games work the same way
3. Know when to use deterministic tools vs human judgment
4. Make it impossible to "forget" a parameter

## The Deckard Boundary Map

### DETERMINISTIC (code does this, never LLM)

| Task | Tool | Why Deterministic |
|------|------|-------------------|
| APU register capture | Mesen trace script | Hardware state, no interpretation needed |
| Period → frequency → MIDI note | `period_to_freq()` + `freq_to_midi()` | Pure math: `f = 1789773 / (div * (p+1))` |
| CC11/CC12 encoding | `build_midi()` | Fixed mapping: `vol*8`, `duty*32` |
| Frame-level comparison | `trace_compare.py` | Exact integer comparison per frame |
| RPP generation | `generate_project.py` | Template filling, no judgment |
| Noise period reverse-map | Lookup table (16 entries) | Exact match against known table |
| NSF emulation | py65 6502 CPU | Instruction-level deterministic |
| SysEx APU register packing | 7-bit safe encoding | Byte manipulation |
| WAV rendering | Waveform math | Sample-level deterministic |
| Batch processing | `batch_nsf_all.py` | Loop over files |

### PROBABILISTIC (LLM appropriate)

| Task | Why LLM | Validation |
|------|---------|------------|
| Driver identification from unknown ROM | Pattern recognition in binary | Confirm via disassembly |
| Interpreting disassembly comments | Natural language understanding | Cross-ref with trace data |
| Choosing envelope model for new game | Creative hypothesis | Test against trace frames |
| SFX vs music separation | Contextual judgment | Human ear-check |
| Drum mapping (noise period → GM note) | Musical judgment | Compare to game audio |
| Song boundary detection in traces | Heuristic thresholds | Human confirms segments |
| ADSR preset tuning for keyboard play | Aesthetic judgment | Human plays and adjusts |
| Track naming without M3U | Game knowledge | User verifies |

### BOUNDARY VIOLATIONS TO WATCH FOR

| Violation | Risk | Fix |
|-----------|------|-----|
| LLM guessing byte formats without disassembly | WASTE: 3-5 prompts per guess | Read disassembly FIRST, always |
| Hardcoded envelope model for new game | RISK: wrong model, silent failure | Test against trace before committing |
| LLM writing RPP templates | WASTE: generate_project.py exists | Never write RPP by hand |
| Ear-checking without trace comparison | RISK: subjective, misses subtle errors | trace_compare.py is ground truth |
| Assuming same driver = same parameters | RISK: DX byte count, pointer format differ | Check manifest, read disassembly |

## The Parameter Checklist

Run this checklist for EVERY new game. Each item is a specific parameter
that must be verified against the Mesen trace.

### Pulse Channels (x2)

```
[ ] Period (11-bit, $4002+$4003[2:0])
    - Capture: frame-by-frame period values from trace
    - Convert: period_to_freq() with divisor=16
    - Compare: MIDI note numbers match trace within ±0 semitones
    - Trap: NSF emulation may produce half-periods (see -12 workaround)

[ ] Volume (4-bit, $4000[3:0])
    - Capture: frame-by-frame volume from trace
    - Encode: CC11 = vol * 8 (range 0-120)
    - Decode in synth: floor(cc11 / 8 + 0.5) recovers exact NES vol
    - Trap: old synth used /127*15 which lost 1 level at vol 10-15

[ ] Duty cycle (2-bit, $4000[7:6])
    - Capture: per-frame duty from trace
    - Encode: CC12 = [16, 32, 64, 96] for duty 0-3
    - Decode in synth: floor(cc12 / 32) recovers exact duty
    - Trap: old synth used min(3,cc12) — ALWAYS gave duty 3!

[ ] Constant volume flag ($4000[4])
    - If set: volume register IS the volume (our default assumption)
    - If clear: volume register is envelope divider period
    - Most games use constant volume for music
    - Trap: some games toggle this mid-note for tremolo effects

[ ] Sweep unit ($4001)
    - Enable ($4001[7]), period ($4001[6:4]), negate ($4001[3]), shift ($4001[2:0])
    - NOT captured in MIDI (no standard CC for hardware pitch sweep)
    - Can encode as MIDI pitchbend if sweep parameters are known
    - Alternative: SysEx APU register replay captures this automatically
    - Trap: Battletoads uses sweeps heavily for signature sound

[ ] Length counter ($4003[7:3])
    - Controls automatic note cutoff after N half-frames
    - NOT captured explicitly in MIDI
    - Partially captured via note duration (period change = note boundary)
    - Trap: some games use length counter as a timer, not for cutoff

[ ] Phase reset ($4003 write)
    - Writing to $4003 restarts duty phase and resets length counter
    - Creates subtle "click" at note start on real hardware
    - NOT captured in MIDI
    - Would need per-note phase reset flag in synth
```

### Triangle Channel

```
[ ] Period (11-bit, $400A+$400B[2:0])
    - Same as pulse but divisor=32 (one octave lower for same period)
    - Trap: triangle has no -12 workaround in NSF mode

[ ] Linear counter ($4008[6:0])
    - Acts as gate: >0 = sounding, =0 = silent
    - Duration = (reload_value + 3) / 4 frames (quarter-frame clocking)
    - CC11 always 127 when sounding (triangle has no volume control)
    - Trap: linear counter doesn't align exactly to 60fps frame boundaries

[ ] Length counter ($400B[7:3])
    - Same as pulse, automatic cutoff
    - Interacts with linear counter (both must be active)
```

### Noise Channel

```
[ ] Volume (4-bit, $400C[3:0])
    - Drum hits: velocity = vol * 8
    - Decay tracking: end note when vol drops to <25% of hit or after 12 frames
    - Trap: old code waited for vol=0, causing 500ms+ drum smear

[ ] Period index (4-bit, $400E[3:0])
    - Maps to timer via 16-entry lookup table
    - Determines pitch/timbre of noise
    - Current: 3 buckets (kick/snare/hat) — loses 13 distinct timbres
    - Better: map to 16 distinct GM drum notes

[ ] Mode bit ($400E[7])
    - 0 = long sequence (hiss/white noise)
    - 1 = short sequence (metallic/tonal)
    - NOT captured in MIDI
    - Critical for hi-hat realism (short mode = metallic hat)
    - Synth has noi_mode but MIDI doesn't set it

[ ] Length counter ($400F[7:3])
    - Auto-cutoff for noise, same as pulse
```

### DPCM Channel

```
[ ] DAC direct write ($4011[6:0])
    - 7-bit DAC value, written directly
    - Used for bass drums, voice samples, sound effects
    - NOT captured in 4-channel MIDI at all
    - Mesen trace captures $4011_dac changes
    - Could add as 5th MIDI track with velocity = DAC value

[ ] Sample address ($4012)
    - Points to DPCM sample data in ROM
    - Would need sample extraction for accurate playback

[ ] Sample length ($4013)
    - Length of DPCM sample

[ ] Rate ($4010[3:0])
    - Playback rate index (16 possible rates)
```

## The Two-Layer Synth Strategy

### Layer 1: CC-Driven (Console synth, current approach)

Captures ~70% of NES audio through standard MIDI:
- Notes (period changes)
- Volume envelope (CC11 per frame)
- Duty cycle (CC12 per frame)
- Drum hits (velocity + note mapping)

Missing: sweep, DPCM, noise mode, phase reset, length counter.

### Layer 2: SysEx Register Replay (APU2 synth)

Captures ~95% of NES audio through raw register replay:
- Every APU register write, every frame, every channel
- Sweep unit, noise mode, DPCM DAC — all included
- Only missing: DPCM sample ROM data (DAC writes captured, not sample playback)

The SysEx track (Track 5) already exists in every NSF-extracted MIDI.
Switch from Console to APU2 synth for file playback to get near-perfect
reproduction.

### When to Use Which

| Scenario | Synth | Why |
|----------|-------|-----|
| File playback (listening) | APU2 | Maximum fidelity from SysEx |
| Keyboard play (performing) | Console | ADSR envelopes for live input |
| A/B testing extraction | Both | Compare CC path vs register path |
| YouTube renders | APU2 | Closest to original game audio |
| Live performance + backing | Console (keyboard) + APU2 (backing) | Best of both |

## Systematic Prompting Protocol

### For Each New Game

```
Step 1: CAPTURE
  "Run the NSF for [game] song [N] for [seconds]s.
   Also load the Mesen trace if available.
   Show me: total frames, notes per channel, CC density."

Step 2: PARAMETER SCAN
  "For each channel (pulse1, pulse2, triangle, noise, dpcm),
   show me the first 30 frames of APU register state.
   Flag any parameter that changes but is NOT captured in our MIDI."

Step 3: COMPARE
  "Run trace_compare against the NSF extraction.
   Report the FIRST mismatch per channel.
   Is it pitch, volume, duty, or timing?"

Step 4: FIX (one at a time)
  "The first mismatch is [X] on [channel] at frame [N].
   Form ONE hypothesis. Change ONE thing. Rerun comparison.
   Did the first mismatch move to a later frame?"

Step 5: VALIDATE
  "After all mismatches are resolved (or explained),
   generate the RPP and WAV. User ear-checks.
   Document any remaining gaps in the game manifest."
```

### For Checking Parameters You Might Have Missed

```
"List every APU register parameter that changes in the Mesen trace
 for [game]. For each one, tell me:
 1. Is it captured in our MIDI? (CC11, CC12, note, velocity, or not at all)
 2. Is the synth using it? (check the @block MIDI handler)
 3. Is the encoding/decoding round-trip lossless?
 Show me any parameter where the answer to 1, 2, or 3 is 'no'."
```

### For Cross-Game Validation

```
"After fixing [Game B]'s extraction, rerun trace_compare on [Game A].
 Did any previously-zero-mismatch channels regress?
 Did any previously-mismatched channels improve?
 What does this tell us about shared infrastructure assumptions?"
```

## The Manifest System

Every game should have a manifest JSON in `extraction/manifests/` that
records what we know and don't know:

```json
{
  "game": "Battletoads",
  "developer": "Rare",
  "year": 1991,
  "mapper": 7,
  "sound_driver": "unknown",
  "channels_used": ["pulse1", "pulse2", "triangle", "noise", "dpcm"],
  "parameters_captured": {
    "period": "yes - note events",
    "volume": "yes - CC11",
    "duty": "yes - CC12",
    "sweep": "no - not in MIDI, in SysEx only",
    "noise_mode": "no - not captured",
    "dpcm": "no - not in 4-channel MIDI",
    "length_counter": "no - implicit in note duration"
  },
  "fidelity_status": {
    "nsf_extraction": "70% - missing sweep, DPCM, noise mode",
    "trace_extraction": "75% - same gaps but real hardware periods",
    "apu2_sysex": "95% - only missing DPCM sample ROM data"
  },
  "known_issues": [
    "Sweep unit creates signature pitch slides not captured in MIDI",
    "DPCM bass drum layer entirely absent from 4-channel output",
    "Noise mode bit not transmitted — all noise is long-sequence"
  ],
  "tracks": 21,
  "trace_available": true,
  "disassembly_available": false
}
```

## How to Avoid the Battletoads Disaster

The Battletoads session burned 15+ prompts on problems that weren't
in the music data at all (JSFX syntax error, RPP format, HASDATA).
To prevent this:

### Pre-Flight Checklist (Before ANY Game)

```
[ ] JSFX synth compiles without errors (open FX window, check banner)
[ ] Test RPP plays sound (use test_inline_midi.rpp)
[ ] MIDI has notes in all expected channels (python -c "import mido...")
[ ] CC11/CC12 values decode correctly (verify round-trip)
[ ] RPP has HASDATA (not FILE reference)
[ ] WAV preview renders non-silent audio
```

### The "Stoned Checklist" — Exhaustive Parameter Verification

For each channel, for the first 100 frames:

```
[ ] Period values match between NSF and Mesen trace
[ ] Volume values match (after CC11 encoding/decoding round-trip)
[ ] Duty values match (after CC12 encoding/decoding round-trip)
[ ] Note boundaries align (same frame for note_on/note_off)
[ ] No parameter changes in trace that are absent from MIDI
[ ] Synth FX window shows no errors
[ ] Hit play — audio output appears on meters
[ ] Human ear-check: does it sound like the game?
```

If ANY check fails, fix it before moving to the next game. Don't
accumulate debt across games — it compounds.
