---
layout: default
title: "Musical Parameter Checklist"
---

# Musical Parameter Checklist

Every parameter that shapes how NES music sounds, whether we model
it, and how to check.

## How to Check Any Parameter

There are three methods, in order of reliability:

1. **Trace comparison** — capture a Mesen APU trace, compare
   frame-by-frame against our extraction. This is definitive.
   The trace shows what the hardware actually produced.

2. **Disassembly reading** — find the code that writes to the
   relevant APU register. Follow the data path from music command
   to register write. This explains *why* a value is what it is.

3. **Ear comparison** — play our render alongside the game in
   Mesen. Useful for catching gross errors but unreliable for
   subtle differences (systematic pitch offsets, envelope timing).

## The Checklist

### PITCH

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Period table | Maps pitch index to NES timer period | Verified (same across Konami games) | Compare `PERIOD_TABLE` against ROM bytes at known address |
| Octave shifts | Period >> N for higher octaves | Verified | Trace: `$4002_period` values match `pitch_octave_to_period()` |
| EC pitch adjust | Shifts all notes by N semitones | Verified (Contra) | Parse EC byte, compare extraction MIDI vs trace MIDI |
| Vibrato (EB) | Per-frame pitch modulation (LFO) | **NOT IMPLEMENTED** | Trace: look for `$4002_period` oscillating within a single note. Disassembly says "not used in Contra" but may be in other games |
| Sweep unit ($4001) | Hardware pitch slide | Not used (Contra/CV1) | Trace: check if `$4001_sweep` ever becomes 1 |
| Pitch adjustment ($EC param) | Fine-tune period table offset | Implemented | Check all tracks for EC commands, verify param values |

**How to check pitch overall**: Run trace comparison. Filter for
frames where both sides are sounding. Any remaining mismatches
after aligning are real pitch errors.

### VOLUME ENVELOPE

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Lookup tables | Per-frame volume from `pulse_volume_ptr_tbl` | Verified (54 tables extracted) | Compare extraction `$4000_vol` vs trace frame-by-frame in aligned section |
| Auto decrescendo | Bit 7 mode: decay for vol_duration frames, pause, resume at tail | Fixed (was broken — decayed to 0 instead of pausing) | Check trace volume for notes using auto mode. Should hold > 0 |
| Vol duration | Low nibble of vol_env byte: limits auto-decay frames | Implemented | Trace: count how many frames volume decrements before holding |
| Decrescendo end pause | `(mul * dur) >> 4`: when to resume tail decay | Provisional | Trace: find frame where held volume starts dropping again. Compare to formula |
| Constant volume flag | $4000 bit 4: hardware vs software envelope | Always 1 in Contra | Trace: verify `$4000_const` is always 1 |

**How to check envelopes**: For a specific note, print our per-frame
volume array and the trace's `$4000_vol` for the same frames. The
first divergence points to the model error.

### DUTY CYCLE / TIMBRE

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Duty cycle | Waveform shape (12.5%, 25%, 50%, 75%) | Applied per instrument change | Trace: check `$4000_duty` changes. Look for mid-note changes |
| Mid-note duty changes | Some instruments switch duty within a note | **NOT MODELED** | Trace shows 2 mid-note duty changes in Jungle (frames 1979, 2075). Rare but audible |
| Mixer nonlinearity | NES DAC has nonlinear mixing curve | **NOT MODELED** (affects tone) | Compare our linear mix against the NES nonlinear formula: `pulse_out = 95.88 / (8128/p1+p2 + 100)` |
| Channel crosstalk | NES channels share a nonlinear mixer | **NOT MODELED** | Audible as subtle tonal coloring. Only matters for production quality |

**How to check duty**: Grep trace for `$4000_duty` and `$4004_duty`
changes. Map each change to the corresponding note boundary. Any
change that falls mid-note is unmodeled behavior.

### NOISE / PERCUSSION

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Drum type mapping | Nibble → percussion_tbl → sound code | Fixed (was wrong — kicks labeled as snares) | Compare nibble distribution against disassembly `percussion_tbl` |
| Noise period ($400E) | Controls drum pitch/timbre | **NOT MODELED** (we use fixed synth) | Trace: extract `$400E_period` per drum hit. Only 2 values in Jungle (7 and 31) |
| Noise mode ($400E bit 7) | Long (hiss) vs short (metallic) | **NOT MODELED** | Trace: check `$400E_mode`. Always 0 in Jungle |
| DMC samples ($4011) | DPCM sample playback for snare/cymbal | **NOT MODELED** (we synthesize) | Trace: `$4011_dac` changes rapidly during sample playback. 283 changes in first 1000 frames |
| DMC sample addresses | Which ROM sample plays for each drum | Known from disassembly, not extracted | Read `$4012_addr` and `$4013_len` from trace, decode sample data from ROM |
| Kick/bass sync | Noise hits aligned with triangle notes | Implemented (percussion_tbl compound hits) | Compare noise and triangle event timelines — should start on same frame |

**How to check percussion**: Look at trace `$400C_vol` (noise volume)
and `$4011_dac` (DMC output) together. Noise spikes = kick drums.
DAC fluctuations = sample playback. Compare timing against our
drum events.

### TRIANGLE

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Linear counter ($4008) | Gates triangle on/off | Implemented (formula: (reload+3)//4 frames) | Trace: compare `$4008_linear` countdown against our sounding_frames calculation |
| Length counter ($400B) | Second gate mechanism | Not tracked (const vol mode makes it irrelevant) | Trace: verify `$400B_length` doesn't cut notes short |
| Phase reset | Waveform restarts on new note (creates attack transient) | Implemented in render_wav.py | Ear comparison — the "punch" on bass note attacks |
| Triangle pop | Silencing triangle mid-waveform causes audible click | **NOT MODELED** | Audible in game as bass "pop." Our renderer fades cleanly |

**How to check triangle**: Compare `$4008_linear` trace values
against our `sounding_frames` for each note. Any note where we
predict N sounding frames but the trace shows N±1 is a linear
counter model error.

### TIMING

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Tempo (DX low nibble) | Frames per duration unit | Implemented | Trace: measure actual note durations (period-change to period-change) |
| Note duration | `tempo * (nibble + 1)` | Verified (0 drift over 24 notes in Jungle) | Note-by-note comparison against trace |
| Rest duration | `tempo * (nibble + 1)` for $C0 commands | Implemented | Trace: measure silence gaps between notes |
| Repeat counts (FE) | Loop sections N times | Implemented | Compare total song duration against trace |
| Song loop point | Where infinite repeat jumps | Implemented (FE $FF) | Trace: find where note sequence repeats |

**How to check timing**: Run note-boundary comparison (extract note
start frames from both extraction and trace). Any accumulating
drift means a duration calculation is wrong somewhere.

### PLAYBACK / RENDERING

| Parameter | What It Does | Our Status | How to Check |
|-----------|-------------|------------|--------------|
| Python synth (`render_wav.py`) | Quick preview audio | Simple approximation | Compare against REAPER render or game audio |
| REAPER JSFX plugin | Production NES audio | Better approximation | Compare against Mesen audio output |
| Mesen audio | Cycle-accurate APU emulation | Ground truth | This IS the reference |
| MIDI CC11 automation | Volume envelope in MIDI | Implemented | Load MIDI in DAW, verify automation curves match expected envelopes |
| MIDI note mapping | Which MIDI note = which pitch | Verified (0 real mismatches in trace comparison) | Play MIDI alongside game, check key signature |

**The tone difference you hear** between our WAV and the game is
primarily the renderer, not the extraction. The data (notes, timing,
volumes) is verified correct. The sound synthesis is approximate.
For best results, render in REAPER with the JSFX NES plugin.

## Priority Order for Improving Fidelity

1. ~~EC pitch adjustment~~ — DONE (was off by 1 semitone)
2. ~~Volume envelope tables~~ — DONE (54 tables extracted)
3. ~~Auto-decrescendo vol_duration~~ — DONE (Base track fix)
4. **Noise period values** — extract $400E values per drum type
   from trace, apply in renderer for accurate kick/snare tuning
5. **DMC sample extraction** — decode DPCM samples from ROM for
   authentic percussion
6. **Mid-note duty changes** — rare (2 in Jungle) but audible
7. **NES mixer nonlinearity** — improves overall tone accuracy
8. **Vibrato (EB)** — not used in Contra, check other games
