# Prompt & Context Engineering Critique

An honest assessment of what went wrong in the Battletoads session
and what it reveals about the prompt/context setup.

## What Worked

### 1. The CLAUDE.md Rule System

The rules in `.claude/rules/` caught several issues:
- `reaper_projects.md` explicitly said "generate_project.py is the
  only way to make RPP files" — when violated, the rule was there
  to point at.
- `synth_fidelity.md` documented the CC11/CC12 encoding contract.
- `architecture.md` defined the parser/IR separation.

These rules EXISTED. The problem was that the agent didn't read and
apply them before building.

### 2. The Mistake Documentation Culture

MISTAKEBAKED.md, the debugging protocol, the new-game checklist —
all of these encode hard-won lessons. The culture of writing mistake
docs is excellent and should continue.

### 3. Progressive Escalation

Ted's feedback escalated naturally: "somewhat like Battletoads" →
"tones are off" → "something is radically missing." This is good
prompt engineering — each round gives the agent a tighter signal.

## What Went Wrong

### 1. No Pre-Flight Check on the Synth

The JSFX syntax error was the entire session blocker. It was visible
in the FX window as a red banner. Nobody checked it because:
- The rules don't mention "verify JSFX compiles" as a pre-flight step
- The pipeline assumes the synth works if it was working last time
- Claude can't open REAPER, so it relied on structural analysis of
  the RPP file to diagnose "no sound"

**Root cause**: No automated synth validation in the pipeline. The
JSFX is a text file — we could grep for syntax patterns that cause
JSFX compilation errors (empty branches, unmatched parens, etc.).

### 2. Wrong Song Mapping

We built and tested Song 2 (Interlude) thinking it was Level 1
(Ragnarok's Canyon = Song 3). This wasted every frame-level
comparison and A/B test.

**Root cause**: No track listing was consulted. The NSF has generic
names ("Song 1", "Song 2"...) and we assumed sequential mapping.
A 30-second web search would have given us the correct names.

### 3. Too Many Variables Changed At Once

In one session we:
- Changed RPP generation (build_rpp → generate_project.py)
- Changed MIDI embedding (FILE → HASDATA)
- Changed MIDI encoding (period_fn, source_text)
- Fixed 3 synth bugs (syntax error, CC11, CC12)
- Built a new trace_to_midi.py script
- Regenerated files multiple times

When the user reported "still no sound," it was impossible to know
which change broke things because everything changed.

### 4. Delivered Before Validating

"Wait to give me something to test until you are confident" — this
was an explicit user instruction. It was violated twice:
- First delivery: bare-bones RPPs from build_rpp() (no synth loaded)
- Second delivery: HASDATA RPPs with broken JSFX (syntax error)

Neither delivery was tested beyond "the file has the right structure."

### 5. No Ground Truth Comparison From The Start

The Mesen trace existed from the beginning of the session. We should
have compared NSF extraction against it in the FIRST step, not after
hours of debugging synth issues. This would have revealed:
- The NSF produces different data than the game
- Song 2 ≠ Level 1
- Sweep vibrato missing from NSF

### 6. The CLAUDE.md Was Too Dense

The CLAUDE.md file is well-organized but loads a lot of context
upfront. The agent read it but didn't internalize the hierarchy:
- "generate_project.py is the only way to make RPP files" was buried
  among other rules
- The synth fidelity contract (CC11/CC12 encoding) was in a separate
  rules file that wasn't consulted during synth debugging

## The Context Architecture Gap

### What's Missing: A Pre-Game Checklist Gate

There's a "New Game Parser Checklist" for ROM reverse engineering,
but no equivalent for the simpler NSF pipeline:

```
Before delivering ANY game's REAPER project:
1. [ ] Verify JSFX synth compiles (grep for empty branches, test RPP)
2. [ ] Confirm NSF song ↔ game level mapping (web search)
3. [ ] Compare NSF frame data against Mesen trace (if available)
4. [ ] Verify MIDI has notes on all expected channels
5. [ ] Verify RPP has HASDATA (not FILE reference)
6. [ ] Play WAV preview — is it non-silent?
7. [ ] If mismatch > 20%: use trace pipeline, not NSF
```

### What's Missing: Tool Validation Tests

The synth had 3 bugs. The RPP generator had 2 bugs. None of these
were caught by any automated check. We need:

```python
# scripts/validate_synth.py
# Parse JSFX file, check for:
# - Empty branches: ") : (\n  //.*\n);" pattern
# - CC11 decoder: should use /8, not /127*15
# - CC12 decoder: should use floor(x/32), not min(3,x)
# - @sample section compiles (no syntax errors)

# scripts/validate_rpp.py
# Parse RPP file, check for:
# - HASDATA present (not just FILE reference)
# - FXCHAIN present with ReapNES plugin
# - MIDI events present (E lines after HASDATA)
# - Duration > 0
```

### What's Missing: Session Startup Protocol

The first thing every session should do:

```
1. Read CLAUDE.md + rules/
2. Check: what game are we working on?
3. Web search: get track listing and names
4. Check: does JSFX synth compile?
5. Check: does test_inline_midi.rpp play sound?
6. THEN start working
```

This adds 2 minutes to session startup and would have prevented the
entire Battletoads disaster.
