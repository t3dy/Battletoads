# What Worked with Contra and Castlevania

How we got from broken extractions to 0-mismatch fidelity, and what
prompting patterns and engineering decisions made it happen.

## The Short Version

CV1 Vampire Killer reached **0 pitch and 0 volume mismatches** across
1792 frames on both pulse channels. Contra Jungle reached **0 actual
pitch mismatches** across 2976 frames. The path from broken to working
was not algorithmic — it was methodological. The key moves:

1. Build `trace_compare.py` BEFORE debugging (ground truth first)
2. Separate parser (full-duration events) from frame IR (envelope shaping)
3. Export MIDI from frame IR, not from parser events
4. Test envelope strategies as isolated functions
5. Use Contra bugs to find CV1 bugs (cross-game validation)

## Timeline of Breakthroughs

### Phase 1: Notes Wrong (CV1 v1-v3)

**Problem**: Every note one octave too high.
**Root cause**: BASE_MIDI_OCTAVE4 was 36 (C2) instead of 24 (C1).
**How found**: Mesen trace showed period 511 = A3 on hardware. Our
parser said A4. Simple arithmetic check against the period table.
**Cost**: 2 prompts (should have been 0 — check the period table first).

**Problem**: B section of Vampire Killer never played.
**Root cause**: FE repeat count — driver increments counter BEFORE
comparing, so `$FE 02` means 2 total passes, not 3.
**How found**: Disassembly showed the increment-then-compare pattern.
Trace confirmed B section started at the right address when fixed.
**Cost**: 4 prompts (guessed before reading the disassembly).

### Phase 2: Volume Wrong (CV1 v4-v5)

**Problem**: Notes played at constant volume instead of decaying.
**Root cause**: Envelope model completely misunderstood. `fade_start`
is not "frames to delay" but "number of volume decrements starting
at frame 1."
**How found**: Trace dump of frames 0-20 for pulse 1 showed volume
decaying from 15 to 11 over 4 frames. Our parser held at 15.
**Cost**: 5 prompts (guessed 3 envelope hypotheses before dumping trace).

**Problem**: 45 volume mismatches on pulse 1, couldn't find the cause.
**Root cause**: `phase2_start = duration - fade_step` went negative
when fade_step > duration (9 notes). Negative phase2_start triggered
release decay on frame 0.
**How found**: Only discovered during Contra work. Contra's different
envelope model forced re-examination of the shared Maezawa driver code.
**Fix**: One line: `phase2_start = max(1, duration - fade_step)`.
**Cost**: 3 prompts on CV1 alone (never found it). 0 additional prompts
once Contra work exposed the shared driver logic.

### Phase 3: Contra's Different World (v1-v8)

**Problem**: Ran CV1 parser on Contra, got garbage.
**Root cause**: Same driver family, completely different parameters.
DX reads 3 bytes in Contra vs 2 in CV1. Volume uses lookup tables
instead of parametric decay. Percussion is separate channel with DMC.
**How found**: Reading the Contra disassembly (should have been step 1).
**Cost**: 3 prompts (assumed same format without checking).

**Key differences that required new code**:
- Volume model: 54 pre-built envelope lookup tables from ROM
- EC pitch adjustment: +1 semitone per track (every note was flat)
- Resume-decrescendo: bounce-at-1 logic in release phase
- Percussion: compound hits (DMC snare + noise kick simultaneously)

**Result**: Contra Jungle v8 = 0 pitch mismatches, 96.6% volume match.

## The Prompting Patterns That Actually Worked

### 1. "Dump trace before modeling"

The single most valuable pattern. Instead of:
> "I think the envelope decays linearly over 8 frames"

Do:
> "Extract frames 0-20 from Mesen trace for pulse 1. Show me the
> actual vol register values."

Then the data speaks: `vol: 15, 14, 13, 12, 11, 11, 11, 11...`
Now you KNOW it's a 4-frame linear decay to sustain at 11.

**Prompt template**:
```
Before writing any code, dump the APU trace data for [channel]
frames [N-M]. Show me period, volume, and duty per frame.
What does the actual hardware do?
```

### 2. "Fix in priority order: Pitch > Timing > Volume > Timbre"

Pitch errors make everything downstream wrong. If notes are an octave
off, volume debugging is meaningless. If timing is wrong, envelope
alignment is impossible.

**Prompt template**:
```
Run trace_compare.py. What is the FIRST mismatch? Which channel,
which frame, which parameter (pitch/volume/duty)? Fix that one
thing before looking at anything else.
```

### 3. "One hypothesis, one test"

Contra v1-v4 wasted prompts trying multiple fixes simultaneously.
Can't tell which one helped.

**Prompt template**:
```
Form ONE hypothesis about why frame [N] has volume [X] instead
of [Y]. Change ONE thing. Rerun trace_compare. Did the first
mismatch move to a later frame? If yes, hypothesis confirmed.
If no, revert and try a different hypothesis.
```

### 4. "Read the disassembly before guessing"

Every time we guessed a byte format without reading the disassembly,
we wasted 2-4 prompts. Every time we read the disassembly first, the
code was right on the first try.

**Prompt template**:
```
Before writing the parser for [game], find and read the disassembly
in references/. Specifically look for:
1. How many bytes does DX read?
2. What does $C0-$CF mean (rest or mute)?
3. Where is the pointer table?
4. What is the volume model (parametric or table)?
```

### 5. "Cross-game validation"

The CV1 phase2_start bug was invisible in CV1 alone (only 9 notes
affected, 1 volume step each). Contra's different parameter ranges
made the same infrastructure code produce obviously wrong output.

**Prompt template**:
```
After fixing [Game B], go back and rerun trace_compare on [Game A].
Did any previously-passing tests now fail? Did any mismatches
improve? Cross-game changes expose shared infrastructure bugs.
```

### 6. "Parsers emit full-duration events, IR shapes them"

The architectural decision that made everything else possible. Parsers
don't know about staccato or envelope decay — they just emit notes
with their full notated duration. The frame IR applies the driver's
volume model frame by frame.

This means:
- Parser bugs are about note boundaries (pitch, timing)
- IR bugs are about envelope shape (volume, duty)
- They can be debugged independently
- New volume models don't require parser changes

### 7. "Export MIDI from frame IR, not from parser"

Early versions exported MIDI directly from parser events. This lost
all envelope information — notes played at constant volume for their
full duration. Exporting from the frame IR produces:
- Shortened notes (staccato matching the envelope decay)
- Per-frame CC11 automation (exact volume curve)
- Per-frame CC12 automation (exact duty cycle)

## The Architecture That Enables Fidelity

```
ROM Disassembly → Parser → Full-Duration Events
                              ↓
                         Frame IR → Per-Frame State (period, vol, duty)
                              ↓
                         MIDI Export (note_on/off + CC11 + CC12)
                              ↓
                         Trace Compare ← Mesen APU Trace (ground truth)
```

Each layer is independently testable:
- Parser correctness: do note boundaries match the score?
- IR correctness: does per-frame volume match the trace?
- MIDI correctness: does playback sound like the game?

## What This Means for Battletoads

Battletoads doesn't use the Konami/Maezawa driver. It's by Rare, with
a completely different sound engine. But the METHOD is the same:

1. Get the Mesen trace (DONE — 11,368 frames captured)
2. Extract per-frame APU state (DONE — trace_to_midi.py)
3. Compare NSF extraction against trace (TODO)
4. Fix mismatches one at a time, pitch first
5. Find or write the disassembly for Rare's sound driver
6. Build a Battletoads-specific frame IR if needed

The NSF pipeline already gets us ~70% fidelity through direct APU
register capture. The remaining 30% (sweep, DPCM, noise mode) requires
either game-specific driver knowledge or the APU2 SysEx replay path.

## Files That Document This History

- `docs/MISTAKEBAKED.md` — 8 rules from blunders, with costs
- `extraction/CLAUDE_EXTRACTION.md` — evidence hierarchy + checklists
- `extraction/drivers/konami/spec.md` — CV1 vs Contra parameter table
- `.claude/rules/debugging-protocol.md` — 5-step order of operations
- `.claude/rules/new-game-parser.md` — 8-step mandatory checklist
- `.claude/rules/architecture.md` — parser/IR separation invariant
