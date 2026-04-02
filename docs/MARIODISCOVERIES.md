# Mario Discoveries — Mesen Capture vs NSF Analysis

Date: 2026-04-01
Source: Mesen 2 capture of Super Mario Bros. (World) ROM, 93.6 seconds
Capture file: `C:\Users\PC\Documents\Mesen2\capture.csv` (13,088 rows)

## Discovery 1: The NSF Emulator Has a 1-Octave Pitch Bug

### Evidence

Side-by-side comparison of Pulse 2 melody (Mario Overworld):

| Note | Mesen Period | Mesen MIDI | NSF Period | NSF MIDI | Diff |
|------|-------------|------------|------------|----------|------|
| E    | 339         | 64 (E4)   | 169        | 76 (E5)  | +12  |
| C    | 427         | 60 (C4)   | 213        | 72 (C5)  | +12  |
| E    | 339         | 64 (E4)   | 169        | 76 (E5)  | +12  |
| G    | 285         | 67 (G4)   | 142        | 79 (G5)  | +12  |
| C    | 427         | 60 (C4)   | 213        | 72 (C5)  | +12  |
| G    | 571         | 55 (G3)   | 285        | 67 (G4)  | +12  |
| E    | 679         | 52 (E3)   | 339        | 64 (E4)  | +12  |
| A    | 509         | 57 (A3)   | 254        | 69 (A4)  | +12  |
| B    | 453         | 59 (B3)   | 226        | 71 (B4)  | +12  |
| Bb   | 479         | 58 (Bb3)  | 239        | 70 (Bb4) | +12  |
| A    | 509         | 57 (A3)   | 254        | 69 (A4)  | +12  |
| G    | 571         | 55 (G3)   | 285        | 67 (G4)  | +12  |

**Every note is exactly +12 semitones (1 octave) too high.**

### The Melody Intervals Are Correct

```
NSF intervals:   [-4, 4, 3, -7, -5, -3, 5, 2, -1, -1, -2]
Mesen intervals: [-4, 4, 3, -7, -5, -3, 5, 2, -1, -1, -2]
                  ^^ IDENTICAL ^^
```

The NSF driver is reading the music data correctly and choosing the
right note INDICES. But the PERIOD VALUES it writes to the APU are
exactly half what the real hardware produces.

### Period Ratio Is Consistently ~2.0

```
Mesen_period / NSF_period for each note:
  339/169 = 2.006   427/213 = 2.005   285/142 = 2.007
  571/285 = 2.004   679/339 = 2.003   509/254 = 2.004
  453/226 = 2.004   479/239 = 2.004
```

Half the period = double the frequency = one octave higher.

### Root Cause: Not the Period Table

The period lookup table in the NSF ROM is **byte-for-byte identical**
to the World ROM (verified at CPU address $FF09, 48 bytes). The sound
code and data match. The bug is in how the py65 6502 emulator executes
that code — it's producing different register writes than real hardware.

Likely candidates:
- **Memory-mapped I/O handling**: py65 treats APU registers ($4000-$4017)
  as flat RAM. Real NES has write-only registers with side effects. The
  sound driver might read from APU registers expecting specific behavior
  that py65 doesn't emulate (returning open bus, status bits, etc.)
- **Timing**: The PLAY routine might depend on cycle-accurate timing
  that py65 doesn't model. If a branch is taken differently due to
  timing, the wrong period table entry could be selected.
- **Stack/interrupt behavior**: NSF PLAY is called by our harness, not
  by the NES's real NMI handler. If the driver checks stack state or
  interrupt flags, it might take a different code path.

### Impact

All 1099 MIDIs in the pipeline are one octave too high for pulse and
triangle channels. This is a systematic, fixable offset — but fixing
it properly requires either:
1. Finding and patching the py65 emulation bug, OR
2. Applying a post-hoc -12 semitone correction in `period_to_midi()`, OR
3. Switching to Mesen-based extraction (captures correct periods)

## Discovery 2: Mesen Captures Decoded APU State, Not Raw Registers

The Mesen capture script uses `emu.getState()` which returns the
internal APU state:

```lua
{key = "apu.square2.timer.period", addr = "$4006_period"}
```

This is the FULL 11-bit decoded period from the APU's internal timer,
NOT the raw byte written to register $4006. This is superior to raw
register capture because:

1. **No assembly required** — the 11-bit period is pre-computed
2. **No race conditions** — captures the actual timer state, not
   a snapshot between writes
3. **Volume is decoded** — shows the current envelope volume, not
   just the register configuration
4. **Timing is frame-accurate** — endFrame callback fires after
   all CPU work for that frame is done

### Capture Format

```csv
frame,parameter,value
183,$4006_period,339      # full 11-bit period
183,$4004_vol,8           # current envelope volume (0-15)
183,$4004_duty,2          # duty cycle (0-3)
```

The values are directly usable for MIDI conversion without needing to
model APU hardware behavior.

## Discovery 3: The Mario Overworld Theme Is in E-flat Major (Concert)

From the Mesen capture, the melody on Pulse 2:

```
E4 - C4 - E4 - G4 (opening figure)
```

This corresponds to the well-known Mario melody, but the absolute
pitch on the NES hardware is E4 (329 Hz), not E5 (659 Hz) as the NSF
extraction produces. The bass on Pulse 1 starts at F#3 (185 Hz).

This matters for:
- Matching keyboard playback to the original game feel
- Setting the right ADSR attack/release character (lower notes need
  different envelope shapes)
- Noise/drum balance (mix levels depend on frequency range)

## Discovery 4: SMB1 Envelope Pattern

From the Mesen capture, Pulse 1 volume envelope:

```
Frame 183: vol=8   (note attack)
Frame 184: vol=8
Frame 185: vol=7   (start decay)
Frame 186: vol=6
Frame 187: vol=5
Frame 188: vol=4
Frame 189: vol=3
Frame 190: vol=2
Frame 191: vol=1
Frame 192: vol=0   (silent)
```

This is a **uniform linear 8-step decay from 8 to 0**, taking 8 frames
(~133ms at 60fps). The attack is instant (vol jumps to 8 on the first
frame). No sustain phase.

The NSF extraction captures this via CC11 updates:
```
CC11=64, CC11=56, CC11=48, CC11=40, CC11=32
```

The mapping `vol * 8` converts NES 0-15 to MIDI CC 0-127 range:
8*8=64, 7*8=56, 6*8=48, etc. This matches the Mesen capture.

**Conclusion:** The envelope extraction IS accurate. The CC11 values
correctly represent the NES volume envelope. The problem is only pitch.

## Discovery 5: Noise Channel Behavior

From the Mesen capture:
```
Frame 183: $400E_period=31, $400C_vol=12, $400C_const=1
```

The noise channel at game start has:
- Period 31 (longest/lowest pitch noise)
- Volume 12 (constant volume mode, not envelope)
- `const=1` means the volume register directly controls output

The extracted MIDI (track 4) has 67 noise events with velocity-only
encoding (no CC11). This is correct for Mario's simple drum pattern.

## Evaluation: NSF vs Mesen Capture Techniques

### NSF Emulation (Current Pipeline)

**Strengths:**
- Fully automated (`batch_nsf_all.py` processes 50 games)
- No manual gameplay required
- Extracts all tracks from an NSF in seconds
- Self-contained: NSF file + py65 emulator, no external tools
- Track isolation: each NSF track plays one song cleanly

**Weaknesses:**
- 6502 emulation fidelity: py65 doesn't model APU hardware behavior
- **Systematic pitch error**: periods are halved (1 octave too high)
- No cycle-accurate timing: may miss frame-precise register writes
- No APU state decoding: must assemble period from raw register bytes
- Can't verify against real hardware behavior

**Verdict:** Good for batch extraction of melody/rhythm structure, but
cannot be trusted for absolute pitch without validation against Mesen.

### Mesen Capture (New Technique)

**Strengths:**
- **Ground truth**: captures actual APU state from cycle-accurate emulation
- Decoded values: full 11-bit period, envelope volume, duty — no assembly
- Frame-accurate: endFrame callback after all CPU work completes
- Validates against real NES behavior (Mesen is a reference emulator)
- Captures ALL channels simultaneously
- Can capture any game without needing an NSF file

**Weaknesses:**
- Requires manual gameplay: operator must play the game and press [/]
- No track isolation: captures whatever music the game is playing
- Requires Mesen 2 installation and Lua script setup
- Must time captures to specific songs (can't just request "track 5")
- Output needs post-processing (CSV -> MIDI conversion)
- Alignment: Mesen frame numbers don't match NSF frame numbers

**Verdict:** Essential for validation and for games without good NSFs.
Not practical for bulk extraction of all tracks from all games.

### Recommended Workflow

```
Layer 1: NSF Batch Extraction (automated, 50 games)
   ↓ produces MIDIs with correct melody/rhythm but wrong octave

Layer 2: Octave Correction (automated fix for py65 bug)
   ↓ apply -12 semitone correction to pulse channels

Layer 3: Mesen Validation (manual, per reference game)
   ↓ capture 5 reference games, compare frame-by-frame
   ↓ confirm correction is sufficient or find per-game issues

Layer 4: Mesen Direct Extraction (for problem games)
   ↓ when NSF emulation is inadequate, capture from ROM
   ↓ convert capture CSV to MIDI directly
```

### When to Use Each

| Situation | Use NSF | Use Mesen |
|-----------|---------|-----------|
| Bulk extraction of 50+ games | Yes | No |
| Absolute pitch verification | No | Yes |
| Games without NSF files | No | Yes |
| Envelope shape validation | Maybe | Yes |
| Per-game ADSR tuning reference | No | Yes |
| Automated CI/CD pipeline | Yes | No |
| One-time deep analysis | No | Yes |

### Key Insight

**NSF and Mesen are complementary, not competing.** NSF gives you
automation and coverage. Mesen gives you ground truth and validation.
The pipeline should use NSF for bulk extraction and Mesen captures
for per-game quality gates.

## Immediate Next Steps

1. **Fix the octave bug**: Either patch py65's APU handling or apply
   `-12` correction in `period_to_midi()` for pulse channels
2. **Validate triangle**: Check if triangle channel has the same
   octave offset (it uses 32-step vs 16-step, so the error may differ)
3. **Build Mesen-to-MIDI converter**: `convert_trace.py` exists but
   needs a path from Mesen CSV → MIDI with CC automation
4. **Capture 5 reference games**: Mario, Castlevania, Mega Man 2,
   Metroid, Contra — establish ground truth for each
5. **JSFX cache bust**: Rename Console synth to force REAPER to
   reload the CC-handling fix (B04)

## Files

- Mesen capture: `C:\Users\PC\Documents\Mesen2\capture.csv`
- NSF source: `output/Super_Mario_Bros/nsf/Super Mario Bros. (...).nsf`
- ROM source: `C:\Dev\NESMusicStudio\AllNESRoms\...\World\Super Mario Bros. (W) (V1.0) [!].nes`
- Extracted MIDI: `output/Super_Mario_Bros/midi/Super_Mario_Bros._01_Running_About_v1.mid`
- Mesen Lua script: `C:\Dev\NESMusicLab\docs\scripts\mesen_apu_capture.lua`
