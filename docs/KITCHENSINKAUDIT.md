# Kitchen Sink Audit: What We Know But Don't Use

An honest accounting of every approach, tool, and data path this
project has documented but fails to actually run when producing output.

---

## The Indictment

We have 1,425 lines of context loaded into every session. We have
15 system files, 10 invariants, 6 validation gates, 2 automated
gatekeepers, and 8 architecture rules. We have docs explaining the
sweep problem, the fake trill problem, the period mask problem,
the SysEx solution, and the three-priority cascade.

**And we're still generating MIDI files that only use Priority 2
(CC11/CC12) when we have working code for Priority 1 (SysEx register
replay).**

The trace_to_midi.py script already generates SysEx data. It already
creates APU2 RPPs. The APU2 synth already reads SysEx. The MIDI files
already contain Track 5 with raw register state. But when the user
opens the output and hits play, they get the Console synth reading
CC data — because that's what generate_project.py defaults to.

We documented the solution, then delivered the inferior path.

---

## What the System Files Say vs What Actually Happens

### Gap 1: "Try everything" vs "try one thing"

**The rules say**: Session protocol step 4 is "Route choice
(nsf/trace/hybrid/apu2_sysex)." VALIDATION.md Gate C says compare
fidelity and make a route decision.

**What actually happens**: The session picks one route (usually NSF
or trace+Console) and runs it. It never generates outputs from
multiple routes for comparison. It never creates side-by-side A/B
test RPPs.

**What should happen**: For every new game segment, generate ALL
available representations:
1. NSF → CC MIDI → Console RPP (baseline)
2. Trace → CC MIDI → Console RPP (better notes)
3. Trace → CC+SysEx MIDI → APU2 RPP (best fidelity)
4. Trace → CC+SysEx MIDI → unified Studio RPP (target)

Then compare. Let the ear-check determine which route to scale.

### Gap 2: "SysEx is the fidelity path" vs never using it

**The docs say**: SOLVINGTHECHIPTUNEVSMIDIPROBLEM.md explains exactly
how SysEx register replay solves the sweep trill problem, the 1-frame
arpeggio problem, the noise timbre problem, and the phase reset problem.

**What actually happens**: We spend rounds debugging the CC/MIDI path
(trying hysteresis, trying period smoothing, analyzing fake trills)
when the SysEx path already encodes the correct data.

**What should happen**: The default output should include the APU2 RPP.
When the user opens a project, the SysEx path should be the first thing
they hear. CC/Console path is for keyboard play and editing.

### Gap 3: "Validate at every gate" vs "deliver and hope"

**The rules say**: VALIDATION.md has 6 gates (A through F). Gate F
has 9 specific checks before delivery. The session protocol says
"nothing is ready unless Gate F passes."

**What actually happens**: The pipeline runs trace_to_midi.py,
generates files, and reports file counts. Nobody runs the validation
gates. The session_startup_check.py exists but the Battletoads session
didn't run it before generating output.

**What should happen**: After every generation run, automatically
execute a validation script that checks:
- [ ] MIDI has notes on all expected channels
- [ ] CC11/CC12 values decode round-trip correctly
- [ ] SysEx track has 4 × frame_count messages
- [ ] RPP has FXCHAIN and HASDATA
- [ ] Note range is within NES hardware limits (A1-A5 for pulse)
- [ ] No 1-frame notes in non-arpeggio context
- [ ] Noise has > N hits (not just 1)

### Gap 4: "Frame state is canonical" vs debugging MIDI

**The rules say**: session_protocol.md says "Dense per-frame APU state
is the source of truth. MIDI is a downstream projection. Debug by
inspecting frame state, not MIDI events."

**What actually happens**: When the output sounds wrong, we analyze
MIDI note sequences, count note events, compare MIDI tracks. We
diagnose "fake trills" in the MIDI when the underlying frame data is
correct — the trill is a MIDI encoding artifact that doesn't exist
in the frame data.

**What should happen**: When something sounds wrong:
1. Check the SysEx path first (it bypasses all MIDI encoding)
2. If SysEx sounds right → the problem is CC encoding, fix that
3. If SysEx sounds wrong → the problem is in the source data or synth
4. Never debug CC encoding until confirming SysEx is correct

### Gap 5: "Dump trace before modeling" vs speculating

**The rules say**: debugging-protocol.md says "Extract trace data for
the exact frames. Don't reason abstractly."

**What actually happens**: We build hypotheses about what the data
might look like ("the sweep oscillation is ±4") and write code to
handle it, then discover the actual data is different (periods include
length counter bits, oscillation crosses semitone boundaries but half
the crossings are real notes).

**What should happen**: Before any code change, produce a concrete
data dump:
```bash
python -c "
# Dump frames N-M, channel X, show every register parameter
# Compare to what our MIDI encodes for the same frames
"
```

### Gap 6: "One synth not many" vs 6 separate JSFX files

**The user said**: One unified synth with a visual console UI.

**What exists**: 6 separate JSFX files totaling 3,129 lines, each
with different subsets of features. No single file has everything.
The Console synth has no SysEx. The APU2 has no UI. The merge plan
exists (SYNTHMERGE.md) but hasn't been executed.

**What should happen**: Build the unified synth. This is the product.
Everything else is infrastructure.

---

## The Context Loading Problem

### What Loads Automatically

Claude Code loads these on every session start:
- `CLAUDE.md` (123 lines) — always
- `.claude/rules/*.md` (6 files, ~320 lines) — when relevant files are touched
- Memory files (7 entries) — always

### What Should Load But Doesn't

These are referenced by the rules but the LLM has to be told to read them:
- `docs/VALIDATION.md` (107 lines) — the actual gate protocol
- `docs/INVARIANTS.md` (255 lines) — the mechanical checks
- `docs/LEAVENOTURNUNSTONED.md` — the exhaustive parameter checklist
- `state/STATUS.json` — current game/track state
- `state/blunders.json` — what NOT to repeat

### What Should Exist But Doesn't

There is no single script that runs the "kitchen sink" approach. No:
- `scripts/try_everything.py <capture.csv> <game> <name>`
  that generates ALL representations and runs ALL validations
- `scripts/validate_output.py <output_dir>`
  that checks all Gate F conditions automatically
- `scripts/compare_routes.py <trace> <nsf> <song>`
  that generates side-by-side output from every available path

---

## The Fix: A Kitchen Sink Pipeline Script

### What It Should Do

```bash
python scripts/kitchen_sink.py \
  --capture "C:/Users/PC/Documents/Mesen2/capture.csv" \
  --nsf output/Battletoads/nsf/Battletoads.nsf \
  --song 3 --game Battletoads --name "Ragnoraks_Canyon" \
  -o output/Battletoads_kitchen/
```

This single command should:

1. **Generate ALL representations**:
   - NSF → CC MIDI → Console RPP
   - Trace → CC MIDI → Console RPP
   - Trace → CC+SysEx MIDI → APU2 RPP (this is the main deliverable)
   - Raw parameter dump for first 100 frames per channel

2. **Run ALL validations automatically**:
   - Note counts per channel (with expected ranges)
   - CC11/CC12 round-trip check (encode→decode→compare)
   - SysEx message count (must = 4 × frame_count)
   - Note range within NES limits
   - Period values within 11-bit range (0-2047)
   - No notes below A1 on pulse (period ≤ 2037)
   - RPP structural checks (FXCHAIN, HASDATA, REC=5088)

3. **Produce comparison data**:
   - NSF vs trace note alignment (which NSF song matches which trace segment?)
   - Per-channel activity profile (% frames active)
   - Parameter coverage matrix (what's captured, what's lost)
   - First 20 notes per channel per route (side-by-side)

4. **Produce a validation report** (markdown):
   - What was generated
   - What passed / what failed
   - Per-channel fidelity metrics
   - Specific recommendation: which output to test first

5. **NOT batch-process**:
   - One song/segment only
   - The user ear-checks before any scaling

### What the System Files Need to Change

**CLAUDE.md**: Add `kitchen_sink.py` to Key Commands.

**session_protocol.md**: Change step 5 from "One-song artifact build"
to "One-song kitchen sink build (all routes, all validations)."

**jsfx_deploy.md**: Add sync_jsfx.py to the kitchen_sink.py pipeline
so it runs automatically.

**NEXT_SESSION_PROMPT.md**: Needs a complete rewrite. The boot
sequence should be:
1. Read CLAUDE.md (auto)
2. Read system files (auto)
3. Run kitchen_sink.py for the target game/song
4. Read the generated validation report
5. Ask the user to ear-check the APU2 output first
6. Debug based on ear-check feedback, not speculation

---

## The Meta-Problem: Context That Warns vs Context That Acts

The current system has 1,425 lines of WARNING context: "don't do this,"
"always do that," "check this before that." Warnings are read once and
then forgotten as the session focuses on the immediate task.

What works better: AUTOMATED ENFORCEMENT. The session_startup_check.py
and sync_jsfx.py work because they're scripts that block progress. You
can't ignore them.

**The kitchen_sink.py script should be the enforcement mechanism for
all the rules.** Instead of 8 files saying "validate before delivery,"
one script that validates and blocks delivery if checks fail.

### Rules That Should Become Code

| Rule (currently text) | Script (should be code) |
|---|---|
| "Generate all routes" | kitchen_sink.py generates NSF + trace + APU2 |
| "Check note range" | validate_output.py asserts MIDI range A1-A5 |
| "SysEx count = 4 × frames" | validate_output.py counts SysEx messages |
| "CC11 round-trip lossless" | validate_output.py encodes + decodes + compares |
| "RPP has FXCHAIN" | validate_output.py greps for FXCHAIN in RPP |
| "Version files" | kitchen_sink.py auto-increments version suffix |
| "Run trace_compare" | kitchen_sink.py runs comparison if trace available |
| "Period ≤ 2047" | validate_output.py checks all MIDI notes map to valid periods |
| "No delivery without Gate F" | kitchen_sink.py returns exit code 1 if any check fails |

### Rules That Must Stay Advisory

| Rule | Why it can't be automated |
|---|---|
| "Does it sound like the game?" | Requires human ears |
| "Which envelope model?" | Requires game-specific knowledge |
| "Is this SFX or music?" | Requires context |
| "Which NSF song matches this trace segment?" | Requires pattern matching judgment |

---

## Summary: What's Broken

1. **We document solutions and don't use them.** SysEx replay exists
   but the default output uses CC mode.

2. **We try one approach at a time.** The kitchen sink approach
   (try everything, compare) is described in LEAVENOTURNUNSTONED.md
   but never implemented as a runnable script.

3. **We warn but don't enforce.** 1,425 lines of context rules that
   the LLM can ignore because they're text, not code.

4. **We debug downstream when the upstream is correct.** Hours spent
   on CC/MIDI encoding artifacts when the SysEx data was right all along.

5. **We deliver single-route output and ear-check.** Should deliver
   multi-route output so the user can A/B test immediately.

## What To Build Next

1. **kitchen_sink.py** — one script that runs every approach,
   validates everything, produces a comparison report.

2. **validate_output.py** — automated Gate F checks, returns exit
   code so it blocks delivery.

3. **ReapNES Studio** — the unified synth. This is the product.
   Everything else is infrastructure to feed it data.
