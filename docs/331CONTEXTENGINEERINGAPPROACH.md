# Context Engineering Approach for NES Fidelity Pipeline

## The Core Problem

This project requires an LLM to hold simultaneous knowledge of:
- NES APU hardware registers (4 channels, 17 registers, frame-rate updates)
- 6502 emulation mechanics (NSF driver execution, register capture)
- MIDI specification (CC mapping, note boundaries, tick resolution)
- JSFX plugin language (operator quirks, pin declarations, cache behavior)
- REAPER RPP format (undocumented, reverse-engineered, version-specific)
- 16 documented blunders (silent failures, cache demons, format tribal knowledge)
- Per-game sound driver characteristics (envelope shapes, arpeggio patterns)
- The fidelity hierarchy (what overrides what)

Dumping all of this into context at once wastes tokens and dilutes
attention. Not loading enough causes blunder repetition and layer
violations. The solution is progressive context revelation tied to
the specific task at hand.

## Architecture: What Lives Where

### Tier 1: Always Loaded (CLAUDE.md + .claude/rules/)

These files are read by the Claude Code harness at session start.
They must be compact, actionable, and contain the invariants that
prevent the most expensive mistakes.

**CLAUDE.md** (~100 lines)
- Pipeline layer commands (bash one-liners)
- Hard invariants (CC ground truth, dual-mode synth, zero config)
- Fidelity hierarchy (ROM > NSF > MIDI CC > ADSR)
- Deckard boundary (deterministic vs LLM split)
- Key commands for common operations

**Rules files** (loaded by file glob, ~96 lines each)
- `synth_fidelity.md` — CC/ADSR dual-mode contract, envelope specs
- `reaper_projects.md` — RPP structure, Console synth, REC 5088 rule
- `architecture.md` — parser/IR separation, trace validation
- `debugging-protocol.md` — symptom-first investigation order
- `new-game-parser.md` — 8-step checklist before writing driver code
- `output-versioning.md` — never overwrite tested files

**Design principle:** These files answer "what must I NOT do?" before
the session starts. They are guard rails, not instruction manuals.

### Tier 2: Machine-Readable Specs (specs/*.json)

These files contain structured data that code and prompts can reference.
They are the single source of truth for parameter values, mappings,
and configuration. They replace prose descriptions with queryable data.

- `specs/console_sliders.json` — all 38 Console synth slider definitions
- `specs/cc_mapping.json` — CC11/CC12 value ranges and conversion formulas
- `specs/rpp_fields.json` — required RPP tokens, forbidden tokens, REC format
- `specs/game_adsr.json` — per-game ADSR presets (labeled as APPROXIMATION)
- `specs/game_registry.json` — all games with track counts and status

**Design principle:** Facts belong in JSON. If a value appears in both
prose and code, the JSON is authoritative. Generate code from specs,
not the other way around.

### Tier 3: Per-Game Analysis Logs (docs/PROJECT*.md)

These files capture what we learned about each game's specific musical
characteristics. They are written during refinement and read when
returning to that game.

Each log contains:
- What was wrong (symptoms)
- Where the musical information lives in the MIDI file
- What changed (fixes applied)
- What remains approximate
- What still needs validation

**Design principle:** One game, one file. Load only the game you're
working on. Cross-game patterns get promoted to Tier 1 or Tier 2.

### Tier 4: Deep Technical Reference (read on demand)

- `docs/NESMUSICTRANSLATEDTOMIDI.md` — full pipeline explanation
- `docs/BLOOPERS.md` (ReapNES-Studio) — 16 blunder histories with context
- `extraction/drivers/konami/spec.md` — per-game command format table
- `docs/HANDOVER.md` — session handover document

**Design principle:** Only load these when the task specifically requires
deep understanding of WHY something works the way it does. For most
tasks, the invariants in Tier 1 are sufficient.

## How Context Flows During a Session

### Session Start (automatic)
```
CLAUDE.md loaded                      → ~100 lines
Relevant rules/ files loaded by glob  → ~96 lines each
Memory files loaded                   → ~30 lines
                                         Total: ~320 lines
```

### Task Identification
The LLM reads the user's request and classifies which layer it affects:
1. Extraction (NSF/MIDI generation)
2. Synth (JSFX plugin behavior)
3. Project (RPP generation/routing)
4. Documentation/infrastructure

### Context Loading (manual, based on task)
```
If touching synth:    read specs/console_sliders.json, specs/cc_mapping.json
If touching projects: read specs/rpp_fields.json
If refining a game:   read docs/PROJECT<game>.md, run analyze_midi_for_log.py
If debugging:         read the relevant blunder from docs/BLOOPERS.md
```

### Work Loop
```
1. Restate invariants being enforced
2. Identify the specific target
3. Inspect deterministically (read files, run analysis)
4. Make smallest viable change
5. Validate against 5 dimensions:
   - routing (does MIDI reach the correct channel?)
   - pitch/duration (are notes correct?)
   - envelope/CC (is volume shape faithful?)
   - timbre/duty (is waveform correct?)
   - noise/drums (do percussion events work?)
6. Update PROJECT*.md log
7. If finding generalizes: update specs/ or rules/
```

### Session End
- Any durable finding written to specs/ or rules/
- PROJECT*.md updated for games touched
- state/STATUS.json updated if game status changed

## What Makes This Different from Standard Context Engineering

### Problem: Format Tribal Knowledge
The RPP format has no official specification. The JSFX language has
undocumented operator differences from C. The NES APU has hardware
quirks that aren't in any manual.

**Solution:** Machine-readable spec files that codify our reverse-
engineered knowledge. Future sessions don't need to re-discover that
`^` means power in JSFX or that `REC 0 0` breaks keyboard routing.
They read the spec and the blunder ID.

### Problem: Silent Failures
REAPER produces no error messages for most misconfiguration. Wrong
tags, missing pins, bad tokens — all silently produce no sound.

**Solution:** The blunder registry maps symptoms to root causes. When
a session encounters "no sound in REAPER," it checks the registry
before investigating. The debugging protocol (Tier 1 rule) enforces
symptom-first diagnosis.

### Problem: Cross-Game Variation
Every game's sound driver has different envelope behavior. A fix that
works for Castlevania may break Mario.

**Solution:** Per-game PROJECT logs capture the specific characteristics.
The GAME_ADSR spec separates per-game parameters from the shared synth
code. Validation runs against representative cases from multiple games.

### Problem: Layer Violations
A change to the synth (Layer 3) can silently override ground-truth
MIDI data (Layer 2). This is what caused the Mario regression.

**Solution:** The fidelity hierarchy is encoded in CLAUDE.md as a
hard invariant. Every change must identify which layer it affects and
confirm it doesn't override a higher layer. The dual-mode contract
(CC-driven vs ADSR) makes the boundary explicit in code.

## Infrastructure File Map

```
NESMusicStudio/
  CLAUDE.md                          ← Tier 1: always loaded
  .claude/rules/
    synth_fidelity.md                ← Tier 1: loaded by glob
    reaper_projects.md               ← Tier 1: loaded by glob
    architecture.md                  ← Tier 1: loaded by glob
    debugging-protocol.md            ← Tier 1: loaded by glob
    new-game-parser.md               ← Tier 1: loaded by glob
    output-versioning.md             ← Tier 1: loaded by glob
  specs/
    console_sliders.json             ← Tier 2: structured spec
    cc_mapping.json                  ← Tier 2: structured spec
    rpp_fields.json                  ← Tier 2: structured spec
    game_adsr.json                   ← Tier 2: per-game presets
    game_registry.json               ← Tier 2: all games inventory
  docs/
    PROJECTMARIO1.md                 ← Tier 3: per-game log
    PROJECTCASTLEVANIA.md            ← Tier 3: per-game log
    PROJECTMEGAMAN2.md               ← Tier 3: per-game log
    PROJECTMETROID.md                ← Tier 3: per-game log
    PROJECTCONTRA.md                 ← Tier 3: per-game log
    NESMUSICTRANSLATEDTOMIDI.md      ← Tier 4: deep reference
    REFINEMENT_PLAN.md               ← Tier 4: process reference
    331UPDATE.md                     ← status snapshot
    HANDOVER.md                      ← session handover
    MISTAKEBAKED.md                  ← blunder index
  scripts/
    generate_project.py              ← RPP generator (reads specs)
    build_projects.py                ← batch builder
    nsf_to_reaper.py                 ← NSF extraction pipeline
    analyze_midi_for_log.py          ← MIDI analysis tool
    validate.py                      ← lint JSFX/RPP/MIDI
```

## What Still Needs Building

### state/STATUS.json
Machine-readable current state: what's working, what's broken, what
the next priority is. Read at session start to orient immediately.

### state/blunders.json
The 16 blunders from both repos as structured data:
`{id, symptom, root_cause, fix, prevention_rule, layer_affected}`
Queryable by symptom or layer.

### Validation Gate Script
A single command that checks all 5 fidelity dimensions for a given
game project:
```bash
python scripts/validate_project.py Projects/<Game>/<track>.rpp
```
Checks: RPP structure, MIDI content, synth config, channel routing,
CC data presence.

### Reference Audio Comparison
Semi-automated spectral comparison between our WAV output and reference
recordings (MP3 from NSF player). Flags divergent frames for human
ear-check.

## The Efficiency Argument

Without this infrastructure, every session starts by:
1. Reading 2000+ lines of narrative docs to understand what happened
2. Re-discovering format quirks through trial and error
3. Making changes that violate invariants from previous sessions
4. Debugging silent failures with no diagnostic framework

With this infrastructure, every session starts by:
1. Reading ~320 lines of always-loaded rules (automatic)
2. Loading ~200 lines of task-specific specs (one read command)
3. Making changes within documented constraints
4. Validating against structured checklists

The difference is ~30 minutes of orientation vs ~5 minutes. Over
dozens of iterative refinement sessions, this compounds.
