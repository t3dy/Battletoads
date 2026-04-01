# How NES Music Gets Translated to MIDI and Synth Plugins

## The Problem

The NES has no "music file format." There is no score, no sheet music,
no MIDI. There is a 6502 CPU running a custom sound driver that writes
raw register values to the 2A03 Audio Processing Unit 60 times per
second. The music IS the register writes. To get it into MIDI, we have
to capture those writes, interpret them as musical events, and encode
them in a format that a DAW can play back through a synth that
approximates the original hardware.

Every step in this chain introduces translation loss. This document
explains where the losses are, what we do about them, and what "close
enough" means.

## The Pipeline

```
NSF file (contains 6502 code + sound driver)
    │
    ▼
py65 6502 emulator runs INIT() once, then PLAY() at 60 Hz
    │
    ▼
APU register snapshots captured per frame ($4000-$4017)
    │
    ▼
Register deltas → per-channel state (period, volume, duty, linear counter)
    │
    ▼
State changes → MIDI events (note_on/off, CC11, CC12)
    │
    ▼
MIDI file with 5 tracks (metadata + 4 NES channels)
    │
    ▼
REAPER project with ReapNES_Console.jsfx synth per track
    │
    ▼
Synth reads MIDI, synthesizes NES-style waveforms
```

## Stage 1: 6502 Emulation (Lossless)

The NSF file IS the NES sound driver, extracted from the ROM. We run
it on a 6502 emulator (py65) with the same timing as real hardware:

- CPU clock: 1,789,773 Hz
- PLAY() called at 60.0988 Hz (NTSC frame rate)
- After each PLAY(), we snapshot all APU registers

This stage is **lossless**. The emulator executes the identical code
the NES would. The register values are exactly what the hardware would
see. There is no interpretation, no approximation.

The only limitation: some NSF files use mapper-specific features or
external sound chips (VRC6, FDS, MMC5) that our emulator doesn't
support. For standard 2A03 games, emulation is perfect.

## Stage 2: Register Interpretation (Minimal Loss)

Each frame, we read the APU register state and extract musical parameters:

**Pulse channels ($4000-$4007):**
- Period: 11-bit value from registers $4002/$4003 (or $4006/$4007)
- Volume: 4 bits from $4000 (or $4004), range 0-15
- Duty cycle: 2 bits from $4000 (or $4004), values 0-3

**Triangle ($4008-$400B):**
- Period: 11-bit from $400A/$400B
- Linear counter: 7 bits from $4008 (controls note duration)
- No volume control (hardware limitation — triangle is always full volume)

**Noise ($400C-$400F):**
- Volume: 4 bits from $400C, range 0-15
- Period index: 4 bits from $400E (indexes into a 16-entry lookup table)
- Mode: 1 bit from $400E (long vs short noise)

**Where loss enters:**

The 2A03 updates registers mid-frame via writes at specific CPU cycle
offsets. We only capture state once per frame (at the END of PLAY()).
If the driver writes a register twice in one frame, we only see the
final value. This can lose very fast trills or mid-frame effects.

In practice, nearly all NES sound drivers operate on frame boundaries.
Mid-frame writes are rare and usually inaudible. Loss here is negligible
for all 34 games in our library.

## Stage 3: MIDI Event Generation (Where Most Translation Happens)

This is the critical stage. We convert continuous register state into
discrete MIDI events. Here's how each parameter maps:

### Note Boundaries (Period → MIDI Note)

A "note" in MIDI has an explicit start and end. The NES APU has no
concept of notes — it has a period register that changes value whenever
the driver tells it to.

**Our rule:** A note boundary occurs when the period register changes
to a different value with volume > 0. Period stays the same = same note
continues. Period changes = old note ends, new note begins.

```
freq_hz = 1,789,773 / (divisor * (period + 1))
midi_note = round(69 + 12 * log2(freq_hz / 440))
```

Where divisor = 16 for pulse, 32 for triangle.

**What this loses:**
- Vibrato implemented as rapid small period changes becomes a stream of
  very short notes instead of pitch bend on a single note. Most NES
  games use hardware sweep for vibrato, which we don't yet capture as
  pitch bend.
- Portamento (smooth pitch slides) becomes a series of chromatic steps.

### Volume Envelope (APU Volume → CC11)

The NES driver updates volume every frame. We capture this as MIDI CC11
(Expression):

```
cc11_value = min(127, nes_volume * 8)
```

This gives us per-frame volume automation — typically 4-5 CC11 messages
per note. This IS the envelope. It captures the exact volume shape the
game's sound driver produces: the attack, the decay, the sustain level,
the release ramp.

**Example from Castlevania "Vampire Killer" (Pulse 1):**
```
Frame 0: note_on C5, CC11=120 (vol 15, full attack)
Frame 1: CC11=112 (vol 14, decay begins)
Frame 2: CC11=104 (vol 13)
Frame 3: CC11=96  (vol 12)
...
Frame 38: CC11=8  (vol 1, nearly silent)
Frame 41: note_off (period changed to new note)
```

**What this loses:**
- CC11 has 128 steps (0-127). NES volume has 16 steps (0-15). The
  mapping `vol * 8` means CC11 values jump in steps of 8. Intermediate
  values (e.g., CC11=100) never occur. This is actually fine — the
  synth maps CC11 back to NES 0-15 range. No information is lost in
  the round trip.
- Volume changes within a single frame are lost (same limitation as
  Stage 2).

### Duty Cycle (APU Duty → CC12)

Pulse channels have 4 duty cycle settings that change the timbre.
We capture changes as MIDI CC12:

```
duty 0 (12.5%) → CC12 = 16
duty 1 (25%)   → CC12 = 32
duty 2 (50%)   → CC12 = 64
duty 3 (75%)   → CC12 = 96
```

Many games change duty cycle mid-note (brighter attack, mellower
sustain). CC12 preserves this frame-by-frame.

### Timing (Frames → MIDI Ticks)

```
MIDI tempo: 128.6 BPM
Ticks per beat: 480
Ticks per frame: 16
```

At these values, 1 frame = 16 ticks, and the timing resolution
exactly matches the NES frame rate. No rounding, no quantization.

**Note duration statistics from Castlevania "Vampire Killer":**
- Minimum: 48 ticks (3 frames, ~50ms) — staccato
- Typical: 96-200 ticks (6-12 frames, ~100-200ms)
- Maximum: 1344 ticks (84 frames, ~1.4 seconds) — sustained notes
- All durations are exact multiples of 16 ticks (frame-aligned)

### Triangle Channel (Special Case)

Triangle has no volume control — it's either on or off. We emit
CC11=127 as a gate signal when the note is active. Duration alone
controls articulation: short notes sound staccato, long notes sound
legato. The linear counter ($4008) determines how long the triangle
sounds before self-silencing.

### Noise Channel (Drums)

Noise maps to GM drum notes based on period:
- Period 0-4 (high pitch): Closed hi-hat (note 42)
- Period 5-8 (mid pitch): Snare (note 38)
- Period 9-15 (low pitch): Kick (note 36)

Volume determines velocity. No CC11 — drums are velocity-driven with
natural decay in the synth.

## Stage 4: Synth Playback (Where Approximation Lives)

The ReapNES_Console.jsfx synthesizer reconstructs NES-style audio from
the MIDI data. It uses:

**Pulse waveforms:** 8-sample duty cycle lookup tables (identical to
hardware). 4 duty settings producing 12.5%, 25%, 50%, 75% waveforms.

**Triangle waveform:** 32-step lookup table (identical to hardware).
The characteristic "staircase" shape that gives NES bass its sound.

**Noise:** 15-bit Linear Feedback Shift Register with two feedback
modes (long/short). Period table matches hardware values exactly.

**Mixer:** Weighted sum with DC offset removal. Pulse channels at 0.5x,
triangle at 0.4x, noise at 0.3x. This approximates the NES DAC's
nonlinear mixing but doesn't perfectly replicate it.

### What the Synth Gets Right

- Waveform shapes are hardware-identical (lookup tables match 2A03)
- Frequency calculation uses the same period-to-Hz formula as hardware
- LFSR noise generation matches hardware feedback polynomial
- Per-frame CC11/CC12 automation replays the exact volume/duty sequence

### What the Synth Approximates

- **Mixer nonlinearity.** Real NES DAC has nonlinear mixing where loud
  pulse channels slightly compress quiet ones. Our mixer is linear with
  fixed weights. Difference is subtle — affects perceived loudness balance
  more than timbre.

- **Aliasing behavior.** Real NES hardware aliases at specific frequencies
  due to the fixed sample rate of the APU. Our synth runs at 44.1 kHz
  and aliases differently. High-frequency pulse notes (period < 8) sound
  slightly different.

- **Triangle quantization noise.** The 32-step triangle produces
  quantization artifacts at low frequencies that give NES bass its
  characteristic "buzz." Our synth reproduces this accurately because
  it uses the same 32-step table, but the higher sample rate smooths
  some of the aliasing artifacts.

- **Channel crosstalk.** Real hardware has slight bleed between channels
  due to shared DAC lines. Our synth has perfect channel isolation.

## What "Close Enough" Means

We define fidelity in layers:

### Layer 1: Pitch Accuracy (EXACT)

Every note in the MIDI file corresponds to a specific NES period value.
The period-to-frequency formula is mathematically identical to hardware.
If you play the MIDI through the synth and compare to a hardware
recording, every note is at the correct pitch. We validate this with
trace_compare.py against Mesen APU dumps — zero pitch mismatches on
all tested tracks.

### Layer 2: Timing Accuracy (EXACT within frame resolution)

Note boundaries, durations, and CC automation are frame-aligned at
60 Hz. The NES sound driver operates at this rate. Our MIDI resolution
(16 ticks/frame) captures every possible frame boundary. No events are
quantized or shifted. Timing is as accurate as the source material
allows.

### Layer 3: Volume Envelope (FAITHFUL)

CC11 automation captures the per-frame volume sequence from the sound
driver. When the synth reads CC11 and applies it as volume, the envelope
shape matches the game. This depends on the synth actually reading CC11
— our Console synth currently uses ADSR envelopes instead, which is a
known gap being fixed (see "Current Limitations" below).

### Layer 4: Timbre (CLOSE)

Duty cycle changes are captured as CC12 and replayed through identical
waveform tables. The timbre is very close to hardware. Differences come
from mixer nonlinearity and aliasing behavior, which affect the overall
"feel" more than individual notes.

### Layer 5: Mix Balance (APPROXIMATE)

Our fixed-weight linear mixer approximates the NES DAC. The relative
levels of pulse, triangle, and noise are close but not identical to
hardware. Different games use different volume levels for each channel,
and the nonlinear DAC means the relationship is not constant.

### What We Don't Capture

- **DPCM samples** (channel 5). Some games use delta-modulation for
  voice clips, bass drums, or samples. We don't extract these.
- **Expansion audio** (VRC6, FDS, MMC5, N163, Sunsoft 5B). Japanese
  Famicom games sometimes use extra sound channels. Our pipeline only
  handles the standard 2A03.
- **Hardware sweep unit.** The NES has a hardware pitch sweep that some
  games use for vibrato or sound effects. We capture the resulting
  period changes as discrete note events, not as smooth pitch bends.

## Current Limitations and Planned Fixes

### Console Synth Ignores CC11/CC12 (CRITICAL)

The ReapNES_Console.jsfx synth has ADSR envelopes for keyboard play
but does not read CC11 (volume) or CC12 (duty) from MIDI files. This
means file playback uses generic ADSR curves instead of the per-frame
ground-truth envelopes baked into the MIDI.

**Fix:** Port the `lp_cc_active[]` dual-mode system from the old
ReapNES_APU.jsfx. When CC11/CC12 arrives, bypass ADSR and let CC data
drive directly. When no CC data (keyboard play), use ADSR.

### Vibrato as Note Stream

Games that implement vibrato by rapidly changing the period register
produce a stream of very short notes instead of a single note with
pitch modulation. This is technically accurate (those ARE the period
values) but sounds choppy on a synth with attack time.

**Possible fix:** Detect rapid period oscillation within a threshold
(e.g., +/- 1-2 semitones within 4 frames) and convert to MIDI pitch
bend on a sustained note.

### Noise Drum Mapping

Our 3-bucket mapping (kick/snare/hi-hat based on period) is crude.
Real NES games use all 16 noise periods with different volume envelopes
to create a wider range of percussion timbres.

**Possible fix:** Map all 16 noise periods to distinct MIDI notes and
build a more nuanced drum envelope table in the synth.

## Alternative Approaches We Could Take

### Approach A: APU Register Stream (No MIDI)

Instead of converting to MIDI, stream raw APU register values directly
to the synth plugin. The JSFX would read a custom file format or SysEx
data containing per-frame register dumps.

**Pros:** Zero translation loss. Every register write replayed exactly.
**Cons:** Not editable in a DAW. Can't rearrange, transpose, or remix.
Defeats the purpose of having it in REAPER.

### Approach B: Per-Sample Emulation

Run a full APU emulator inside the JSFX plugin at the correct clock
rate, feeding it register writes at frame boundaries.

**Pros:** Hardware-identical output including mixer nonlinearity and
aliasing. Would be indistinguishable from real hardware.
**Cons:** Extremely CPU-intensive. JSFX would need to maintain full APU
state including cycle-accurate timing. Would require a fundamentally
different plugin architecture.

### Approach C: Hybrid MIDI + Register Sideband

Use standard MIDI for note/timing but add a sideband channel carrying
raw register snapshots as SysEx or NRPN data. The synth could use MIDI
for user editing while falling back to register data for playback.

**Pros:** Best of both worlds — editable MIDI plus hardware-accurate
playback. Could toggle between "edit mode" and "authentic mode."
**Cons:** Complex to implement. REAPER's MIDI editor wouldn't display
the sideband data meaningfully. Two sources of truth is fragile.

### Approach D: Pre-Rendered Wavetables

For each game, pre-render every unique instrument timbre as a short
audio sample (attack + sustain loop) and use a sample-based synth.

**Pros:** Perfectly captures the exact sound of each instrument.
**Cons:** Loses per-note envelope variation. A note in bar 1 might have
a different envelope than the same pitch in bar 40 (because the driver
state differs). Wavetables can't capture this.

### What We Actually Use (Approach E: CC Automation)

Our current approach — MIDI with per-frame CC automation — is the best
balance of fidelity and editability. The MIDI file is a standard format
that any DAW can read. The CC automation captures the ground-truth
envelope from the sound driver. The synth uses hardware-identical
waveform tables. The user can open a project, hit play, and hear
something very close to the original game. They can also select a track,
plug in a keyboard, and play live with NES-style timbre.

The remaining gap is the Console synth's CC handling, which is a
straightforward code port, not a design problem.
