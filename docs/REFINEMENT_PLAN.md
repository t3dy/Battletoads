# Refinement Plan: Iterative Fidelity Improvement

## The Mario Regression — Diagnosis

The Mario project got worse because we switched from ReapNES_APU.jsfx
(which reads CC11/CC12) to ReapNES_Console.jsfx (which ignores them).

**Before (APU synth):** MIDI file's CC11 data (64>56>48>40>32 per note)
drove the volume directly. Notes had the correct staccato decay. Close
to game audio. Problem was note durations.

**After (Console synth):** CC11 ignored. ADSR envelope plays instead.
Generic sustain replaces the precise 5-step decay. Notes that should
fade out don't. Notes that should be punchy sustain. Drums may not
trigger correctly because the Console handles noise differently.

**Root cause:** Layer violation. A lower-authority system (ADSR) silently
overrode a higher-authority system (CC11 ground truth data).

**Fix:** Port CC11/CC12 handling from APU to Console. This is the single
highest-leverage change. It fixes playback fidelity for ALL 1099 projects
at once.

## The Broader Problem: Refinement Is Iterative

Every game's music has a unique sound driver with different envelope
shapes, duration patterns, and timbre behavior. The first pipeline pass
captures pitch and timing correctly but may lose subtleties in volume
envelope, duty cycle variation, noise behavior, and note boundary
detection.

Getting from "recognizable" to "faithful" requires iterative comparison
between our output and the original game audio. Each iteration teaches
us something about the sound driver that we can encode into the pipeline.

## Context Engineering for Agentic Refinement

### The Problem
An LLM working on fidelity refinement needs to hold multiple concerns
simultaneously:
- NES APU hardware behavior (register semantics)
- NSF extraction mechanics (how MIDI gets generated)
- MIDI format specifics (CC mapping, tick timing, channel routing)
- JSFX synth behavior (how the plugin interprets MIDI)
- RPP structure (how REAPER loads and routes everything)
- Per-game driver quirks (envelope shapes, duration patterns)
- The blunder history (16 documented failure modes to avoid)

This is too much to dump into context all at once. It needs progressive
revelation.

### Progressive Context Architecture

```
LAYER 0: Always Loaded (CLAUDE.md + rules/)
  ~400 lines. Invariants, fidelity hierarchy, Deckard boundary,
  pipeline commands. Enough to avoid blunders and make safe changes.

LAYER 1: Task-Specific Rules (triggered by file globs)
  synth_fidelity.md    — when touching jsfx/ or generate_project.py
  reaper_projects.md   — when touching Projects/ or RPP generation
  architecture.md      — when touching extraction/ or scripts/
  ~300 lines each, loaded only when relevant.

LAYER 2: Machine-Readable Specs (read on demand)
  specs/console_sliders.json  — full 38-slider map
  specs/cc_mapping.json       — CC11/CC12 value tables
  specs/rpp_fields.json       — required RPP tokens
  specs/game_adsr.json        — per-game ADSR presets
  specs/game_registry.json    — all games, status, track counts

LAYER 3: Reference Cases (read when refining a specific game)
  docs/PROJECTMARIO1.md       — Mario envelope analysis
  docs/PROJECTCASTLEVANIA.md  — Castlevania envelope analysis
  docs/PROJECTMEGAMAN2.md     — Mega Man 2 arpeggio analysis
  docs/PROJECTMETROID.md      — Metroid crescendo analysis
  docs/PROJECTCONTRA.md       — Contra attack transient analysis

LAYER 4: Deep Technical (read only when debugging specific failures)
  docs/NESMUSICTRANSLATEDTOMIDI.md  — full pipeline explanation
  docs/BLOOPERS.md (ReapNES-Studio) — 16 blunder histories
  extraction/drivers/konami/spec.md — per-game command format
```

### How to Use This in Practice

**Starting a refinement session:**
1. Read CLAUDE.md (Layer 0) — 100 lines
2. Read the relevant rule file (Layer 1) — 96 lines
3. Read the PROJECT*.md log for the target game (Layer 3) — 100 lines
4. Read the actual MIDI file analysis (run analyze_midi_for_log.py)
5. Compare to reference audio (user provides ear-check feedback)

**Iterating on a single game:**
1. Run analysis script on the MIDI
2. Compare CC11 envelope shape to expected game character
3. Check note durations against known driver behavior
4. Listen in REAPER, note specific symptoms
5. Trace symptom to layer (extraction? synth? project?)
6. Make smallest change, re-test
7. Update PROJECT*.md log with findings

**Applying cross-game insights:**
When a fix for one game reveals a general pattern (e.g., "all Konami
games use DX commands for tempo"), encode it in:
- The relevant spec JSON (machine-readable)
- The relevant rule file (for future sessions)
- The PROJECT*.md log (for the specific game)

## The Refinement Workflow (Per Game)

### Phase 1: Automated Analysis
```bash
python scripts/analyze_midi_for_log.py output/<Game>/midi/<track>.mid
```
This gives: note counts, duration stats, CC11/CC12 patterns, envelope
shapes, velocity distribution. Pure data, no judgment needed.

### Phase 2: Ear-Check Against Reference
User listens to:
1. The REAPER project output
2. The original game (via NSF player or YouTube)
3. Notes specific discrepancies: "drums missing," "melody too sustained,"
   "wrong pitch in bar 12," etc.

### Phase 3: Diagnosis
Map each discrepancy to a layer:

| Symptom | Likely Layer | Investigation |
|---------|-------------|---------------|
| Wrong notes/pitch | Extraction | Check period_to_midi conversion |
| Notes too long/short | Extraction | Check note boundary detection |
| Volume envelope wrong | Synth | Check CC11 handling |
| Duty/timbre wrong | Synth | Check CC12 handling |
| Drums missing/wrong | Extraction + Synth | Check noise channel + drum mapping |
| Keyboard doesn't work | RPP generation | Check REC field, slider config |
| No sound at all | RPP + Synth | Check RPP structure, JSFX loading |

### Phase 4: Fix
1. Make the smallest change at the correct layer
2. Re-run analysis to verify the change
3. User ear-checks again
4. Update PROJECT*.md log

### Phase 5: Generalize
If the fix applies to other games:
1. Update the relevant spec JSON
2. Update the relevant rule file
3. Re-run pipeline for affected games

## Highest-Leverage Changes (Priority Order)

### 1. Port CC11/CC12 to Console Synth (fixes ALL games)
~30 lines of JSFX code. Port lp_cc_active[] from APU. When CC data
arrives, bypass ADSR. This single change fixes file playback for all
1099 projects.

### 2. Validate Drum/Noise Handling in Console Synth
The Console synth may handle noise differently from APU. Compare:
- APU drum mapping table (35 entries, period/mode/vol/decay)
- Console drum handling (check @block section)
If Console lacks the drum mapping, port it.

### 3. Build Reference Audio Comparison Tool
A script that:
- Renders our MIDI through the synth (WAV)
- Loads reference MP3/WAV from the NSF player
- Computes spectral difference per-channel
- Flags frames where volume or pitch diverge by >threshold

This makes ear-checking semi-automated.

### 4. Expand Game ADSR Presets
For each game the user ear-checks, derive ADSR parameters from the
CC11 analysis data and add to specs/game_adsr.json. This improves
keyboard play fidelity without touching the CC-driven file playback.

### 5. Improve Note Boundary Detection
Some games use vibrato (rapid period oscillation) that creates spurious
note boundaries. Detect and convert to pitch bend. This requires
per-game analysis of which period changes are "real" note changes vs
ornamental.

## Infrastructure Improvements for Future Sessions

### What to Bake Into System Files
- Every blunder from both repos, as machine-readable checklist items
- The complete slider map, CC map, and RPP field spec as JSON
- Per-game analysis results as structured data (not just prose logs)
- Build/validate commands as a single entry point

### What to Keep as Progressive Context
- Deep technical explanations (NESMUSICTRANSLATEDTOMIDI.md)
- Per-game PROJECT*.md logs (only load for the game being worked on)
- Blunder narratives (only load when debugging a specific failure mode)
- Driver specs (only load when working on extraction)

### The Key Insight from the Blooper History
16 blunders across both repos. The pattern:
1. **Silent failures** (JSFX compiles but produces no sound)
2. **Cache invalidation** (REAPER serves old compiled code)
3. **Format tribal knowledge** (no official RPP spec)
4. **Skipped verification** (built infrastructure before testing one note)

Every future session should start with: "Does the simplest case still
work?" before making changes. The verification order:
1. Manual JSFX test in REAPER UI
2. Minimal RPP with defaults
3. Multi-track with per-channel routing
4. MIDI file playback with CC automation
5. Full project with all features
