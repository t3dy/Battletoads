# Building the Environment to Avoid Our Foibles

Concrete recommendations for restructuring the project environment
so the problems from the Battletoads session can't happen again.

## Problem 1: Broken Synth Not Detected

### What Happened
JSFX had a syntax error (empty else branches). No automated check
caught it. Hours spent debugging RPP structure when the synth was
the problem.

### Fix: Synth Validation Script + Hook

Create `scripts/validate_synth.py`:
```python
"""Validate JSFX synth files for common errors."""
# 1. Check for empty branches: ) : (\n  // comment\n);
# 2. Check CC11 decoder uses /8 not /127
# 3. Check CC12 decoder uses floor(x/32) not min(3,x)
# 4. Check @sample section exists and has output assignments
```

Add as a Claude Code hook that runs before any RPP generation:
```json
{
  "hooks": {
    "pre_generate_project": {
      "command": "python scripts/validate_synth.py",
      "fail_on_error": true
    }
  }
}
```

### Fix: Test RPP as Canary

`output/test_inline_midi.rpp` should be the first thing tested every
session. Add to session startup checklist.

## Problem 2: Wrong Song Mapping

### What Happened
NSF Song 2 was treated as Level 1 music. It's actually "Interlude."
Level 1 is Song 3. No web search was done to check.

### Fix: Track Manifest With Names

Every game in the pipeline should have a `track_names.json`:
```json
{
  "game": "Battletoads",
  "source": "https://downloads.khinsider.com/...",
  "tracks": {
    "1": "Title",
    "2": "Interlude",
    "3": "Ragnarok's Canyon",
    ...
  }
}
```

Create this file AS THE FIRST STEP for every new game, populated
from a web search. It takes 2 minutes and prevents hour-long
wrong-song debugging.

### Fix: Naming Convention

Output files should use track names, not just numbers:
```
Battletoads_03_Ragnoraks_Canyon_v1.mid   (not Song_3)
Battletoads_07_Turbo_Tunnel_Bike_Race_v1.mid
```

This makes it impossible to accidentally test the wrong song.

## Problem 3: No NSF vs Trace Comparison

### What Happened
NSF extraction was treated as ground truth. Nobody compared it
against the Mesen trace until the user said "something is radically
missing." The comparison would have shown a 42% period match and
completely different timing.

### Fix: Automatic Trace Comparison

When a Mesen trace exists, the pipeline should AUTOMATICALLY compare
it against the NSF extraction and report a fidelity score:

```python
# In batch_nsf_all.py or trace_to_midi.py:
if trace_exists(game):
    score = compare_nsf_vs_trace(nsf_frames, trace_frames)
    if score.period_match < 80:
        print(f"WARNING: NSF only {score.period_match}% period match")
        print(f"RECOMMENDATION: Use trace pipeline for {game}")
```

Games scoring below 80% should automatically route to the trace
pipeline.

### Fix: Fidelity Dashboard

After extraction, print a dashboard:
```
=== FIDELITY REPORT: Battletoads Song 3 ===
Period match vs trace:  42% *** USE TRACE ***
Volume match vs trace:  68%
Timing match vs trace:  12%
Channels with data:     P1=540 P2=301 Tri=22 Noise=1
Expected (from trace):  P1=~400 P2=~350 Tri=~200 Noise=~100
Triangle suspiciously low: 22 vs expected ~200
```

The triangle having 22 notes when the trace shows ~200 is a red flag
that should be caught automatically.

## Problem 4: Delivering Before Validating

### What Happened
Two rounds of "ready to test" were delivered without confirming
sound output. The user had to discover silence both times.

### Fix: Pre-Delivery Checklist Gate

Before saying "ready to test," Claude MUST verify:
1. RPP has HASDATA (automated: grep for HASDATA in file)
2. MIDI has notes on expected channels (automated: mido parse)
3. WAV preview is non-silent (automated: check max amplitude > 0)
4. JSFX has no syntax errors (automated: validate_synth.py)

If ANY check fails, fix it before delivering.

### Fix: WAV Preview As Smoke Test

`nsf_to_reaper.py` already renders a WAV preview. If the WAV is
silent or sounds obviously wrong (all same pitch, no rhythm), that's
a pipeline failure. Add an automated check:

```python
# After render_wav():
import numpy as np
audio = np.frombuffer(wav_data, dtype=np.int16)
if np.max(np.abs(audio)) < 100:
    raise RuntimeError("WAV preview is silent — pipeline broken")
```

## Problem 5: Session Context Overload

### What Happened
The session tried to do everything at once: fix RPP generation,
build trace_to_midi.py, fix 3 synth bugs, regenerate all files,
write docs, and debug no-sound issues. Variables interacted.

### Fix: One Thing At A Time Protocol

For each new game:

**Phase 1: Validate Environment (5 min)**
- Test synth compiles
- Test RPP plays sound
- Web search for track names

**Phase 2: Extract (10 min)**
- Run NSF pipeline
- Compare against trace (if available)
- Choose pipeline: NSF or trace

**Phase 3: One Song Test (5 min)**
- Pick the most recognizable song
- Generate RPP
- User listens, gives feedback
- Fix issues ONE AT A TIME

**Phase 4: Batch (10 min)**
- Apply fixes to all songs
- Generate all RPPs
- User spot-checks 2-3 songs

### Fix: Gate Between Phases

Don't start Phase 2 until Phase 1 passes. Don't start Phase 3
until Phase 2 confirms data quality. Each phase has explicit
pass/fail criteria.

## Problem 6: Synth Bug Accumulation

### What Happened
Three separate bugs in ReapNES_Console.jsfx (syntax error, CC11
decoding, CC12 decoding) were all present simultaneously. They
were introduced at different times but never caught because there's
no test suite for the synth.

### Fix: JSFX Test Harness

Create `scripts/test_synth.py` that:
1. Generates a known test MIDI (C major scale, all duties, all volumes)
2. Builds an RPP with the synth loaded
3. Validates the JSFX source for known bug patterns
4. Reports: "Synth OK" or "Synth has N issues"

Run this after any JSFX edit and before any game extraction session.

### Fix: Synth Version Control

The JSFX lives in two places:
- `studio/jsfx/ReapNES_Console.jsfx` (repo)
- `C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio/` (REAPER)

These can drift. Add a sync check to session startup:
```python
if hash(repo_jsfx) != hash(reaper_jsfx):
    print("WARNING: JSFX out of sync — copy repo version to REAPER")
```

## Implementation Priority

1. **Session startup checklist** — add to CLAUDE.md as mandatory
   first step. Zero code required, prevents 80% of issues.
2. **validate_synth.py** — catches synth bugs before they reach the user.
   ~50 lines of Python.
3. **Track names manifest** — web search on first session. Prevents
   wrong-song mapping. ~5 min per game.
4. **NSF vs trace comparison** — automatic fidelity scoring. Routes
   games to the right pipeline. ~100 lines of Python.
5. **Pre-delivery checklist** — automated checks before "ready to test."
   Prevents silent RPP delivery. ~30 lines of Python.

Total investment: ~200 lines of Python + a mandatory startup checklist.
Expected savings: 2-4 hours per game session.
