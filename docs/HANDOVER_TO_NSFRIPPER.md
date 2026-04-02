# Handover: NESMusicStudio -> NSFRIPPER

## What This Repo Is

NSF-rip-to-REAPER (NSFRIPPER) is a clean extraction from NESMusicStudio.
It contains only what's needed to run the NES-to-MIDI-to-REAPER pipeline
and iteratively improve fidelity. All narrative history and bulk generated
data was left behind.

GitHub target: https://github.com/t3dy/NSF-rip-to-REAPER

## What's Here (56MB)

### Infrastructure (always loaded)
- `CLAUDE.md` — invariants, fidelity hierarchy, pipeline commands
- `.claude/rules/` — 6 scoped rule files (synth, projects, architecture, debugging, parser, versioning)

### Machine-Readable Specs
- `specs/console_sliders.json` — 38-slider map for ReapNES_Console.jsfx
- `specs/cc_mapping.json` — CC11/CC12 semantics and conversion formulas
- `specs/rpp_fields.json` — required RPP tokens, forbidden tokens, REC format
- `specs/note_boundary_rules.json` — how note starts/ends are detected from APU registers
- `specs/noise_channel_rules.json` — noise period table, LFSR, drum mapping
- `specs/game_registry.json` — 50 games with track counts and status
- `specs/game_adsr.json` — per-game keyboard ADSR presets (approximation only)
- `specs/game_signatures.json` — envelope/duration/timbre characterization for 5 reference games

### State
- `state/STATUS.json` — current pipeline status, critical blocker, priorities
- `state/blunders.json` — 16 structured blunders with symptom/cause/fix
- `state/wins.json` — proven successes and patterns
- `state/wishes.json` — user desires and future goals

### Templates
- `templates/rpp/known_good_header.txt` — Console_Test.rpp header (known working)
- `templates/reports/PROJECT_TEMPLATE.md` — per-game analysis log template
- `templates/json/game_signature_template.json` — game characterization schema

### Pipeline Code
- `scripts/nsf_to_reaper.py` — NSF extraction (6502 emulation -> MIDI + RPP)
- `scripts/generate_project.py` — RPP generator (Console synth, full header, keyboard)
- `scripts/build_projects.py` — batch rebuild all Projects/
- `scripts/analyze_midi_for_log.py` — MIDI analysis for project logs
- `scripts/validate.py` — lint JSFX/RPP/MIDI
- `scripts/validate_project.py` — 5-dimension fidelity validation scaffold
- 15 other pipeline/utility scripts

### Synth Plugins
- `studio/jsfx/ReapNES_APU.jsfx` — old synth (reads CC11/CC12, no keyboard ADSR)
- `studio/jsfx/ReapNES_Console.jsfx` — MISSING (lives in ReapNES-Studio repo)
- `studio/jsfx/ReapNES_Full.jsfx`, `ReapNES_Instrument.jsfx`, `ReapNES_Pulse.jsfx`
- `studio/jsfx/lib/` — shared JSFX libraries

### Data
- `output/*/nsf/` — NSF source files for ~50 games (1.2MB)
- `output/*/midi/` — 1099 extracted MIDIs (~30MB)
- `Projects/` — 1099 generated REAPER projects (23MB)
- `extraction/` — Konami driver parsers, manifests, nesml library

### Active Docs
- `docs/NESMUSICTRANSLATEDTOMIDI.md` — how the translation works
- `docs/PROJECTMARIO1.md` through `PROJECTCONTRA.md` — 5 reference game analyses
- `docs/REFINEMENT_PLAN.md` — layer-by-layer improvement plan
- `docs/331CONTEXTENGINEERINGAPPROACH.md` — context engineering architecture
- Plus infrastructure docs: INVARIANTS, CHECKLIST, FAILURE_MODES, etc.

## What's NOT Here

- WAV renders (8.4GB) — regenerate with `scripts/render_batch.py`
- Old REAPER projects in `studio/reaper_projects/` (522MB) — regenerate with `build_projects.py`
- Preset corpus (149MB) — lives in NESMusicStudio if needed
- AllNESRoms/ (621MB) — stay in NESMusicStudio
- ~50 narrative history docs — stay in NESMusicStudio/docs/
- .zophar.zip archives (66MB) — stay in NESMusicStudio root
- ReapNES_Console.jsfx — lives at C:\Dev\ReapNES-Studio\jsfx\ and is installed
  to REAPER Effects dir. Copy it to studio/jsfx/ if needed.

## Critical Blocker

**B14: Console synth ignores CC11/CC12.** This is THE priority.
The old APU synth reads CC automation (volume + duty per frame) from
MIDI files. The Console synth (which has keyboard support) ignores
CC automation and uses ADSR instead. This means file playback is
wrong for all 1099 projects.

**Fix:** Port ~30 lines of `lp_cc_active[]` code from ReapNES_APU.jsfx
`@block` section into ReapNES_Console.jsfx. When CC11/CC12 arrives,
bypass ADSR and let CC data drive volume/duty directly.

## Fidelity Hierarchy

1. ROM/Trace (Mesen APU dumps) — frame-level ground truth
2. NSF emulation (py65 6502 -> CC11/CC12 per frame)
3. MIDI file (CC automation IS the envelope)
4. ADSR approximation (keyboard only, lowest fidelity)

Never let a lower layer override a higher one.

## Key Commands

```bash
python scripts/nsf_to_reaper.py <nsf> --all 180 -o output/X/   # single game
python scripts/batch_nsf_all.py                                  # all games
python scripts/generate_project.py --midi <f> --nes-native -o <out>  # RPP from MIDI
python scripts/build_projects.py --force                         # rebuild all Projects
python scripts/validate_project.py Projects/Super_Mario_Bros/*.rpp  # validate
python scripts/analyze_midi_for_log.py output/X/midi/track.mid   # analyze MIDI
```

## Session Boot Sequence

1. Read `CLAUDE.md` (auto-loaded, ~100 lines)
2. Read `state/STATUS.json` (current state, blocker, priorities)
3. Read `state/blunders.json` (what NOT to repeat)
4. Read the relevant rule file for your task
5. If refining a game: read its `docs/PROJECT*.md` and run `analyze_midi_for_log.py`
