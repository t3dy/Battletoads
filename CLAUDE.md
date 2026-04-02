# NES Music Studio

NSF/ROM → MIDI → REAPER/WAV/MP4 → YouTube.

## The Product

**ReapNES Studio** is a single unified JSFX synthesizer plugin for REAPER that:
1. Plays NES game music from MIDI files at ROM-level accuracy (via SysEx register replay)
2. Works with a MIDI keyboard for modern composers (via ADSR envelopes)
3. Has a vintage analog synth console UI — knobs, sliders, oscilloscope
4. Shows parameter changes in real time for video recording (YouTube)
5. Makes game-to-game timbral differences visible through knob positions

**One synth, not many.** All functionality lives in one plugin. The synth
auto-detects its input: SysEx → hardware replay, CC11/CC12 → envelope
playback, keyboard only → ADSR mode. See `docs/SYNTHMERGE.md` for the
full design and `docs/SOLVINGTHECHIPTUNEVSMIDIPROBLEM.md` for the
architecture.

## Priority: Production Pipeline

The primary goal is producing REAPER projects and YouTube videos for all
games in the library. Maximize deterministic scripting; minimize LLM involvement.

### Layer 1: Batch Production (DETERMINISTIC — no LLM)

For games with NSF files, the entire pipeline is automated:

```bash
python scripts/batch_nsf_all.py                           # all unprocessed games
python scripts/nsf_to_reaper.py <nsf> --all -o output/X/  # single game
python scripts/generate_project.py --midi <f> --nes-native -o <out>  # REAPER from MIDI
```

Output per game: `output/<Game>/midi/`, `output/<Game>/reaper/`, `output/<Game>/wav/`

### Layer 2: Quality Validation (HUMAN — ear-check)

After batch production, user listens to output and flags issues.
Not every game needs trace-level validation. NSF emulation is ground truth.

### Layer 3: ROM Reverse Engineering (LLM-ASSISTED — only when needed)

For games where NSF output is inadequate or deeper fidelity is required:

1. **Identify** — `PYTHONPATH=. python scripts/rom_identify.py <rom>`
2. **Check manifest** — `extraction/manifests/*.json`
3. **Find disassembly** — check `references/`
4. **Parse one track, listen** — gate before batch
5. **Iterate on fidelity** — trace_compare.py

### Layer 4: Website & Distribution (DETERMINISTIC)

```bash
python scripts/generate_site.py          # regenerate per-game pages from output/
```

Site: https://t3dy.github.io/ReapNES/

## Hard Invariants

- **NSF emulation is ground truth** for games without custom ROM parsers.
- **Trace is ground truth** for games with ROM parsers (CV1, Contra).
- **CC11/CC12 in MIDI files is ground truth for volume/duty envelopes.**
  NSF extraction captures per-frame APU register state as CC automation.
  The synth MUST play these back faithfully, not override with ADSR.
- **Triangle is 1 octave lower than pulse** (hardware fact).
- **Version output files** (v1, v2...). Never overwrite a tested file.
- **Same opcode ≠ same semantics** across drivers. Check manifest.
- **generate_project.py is the only way to make RPP files.** Never write RPP by hand.
- **One synth plugin (ReapNES Studio).** Not multiple JSFX files.
  All playback modes live in one plugin with a three-priority input cascade:
  Priority 1: SysEx register replay (hardware-exact).
  Priority 2: CC11/CC12 automation (file playback).
  Priority 3: ADSR keyboard (live composing).
  Auto-detects from incoming data. See docs/SYNTHMERGE.md.
- **Projects must work with zero manual REAPER configuration.** Keyboard,
  MIDI routing, synth settings — everything baked into the RPP file.

## Fidelity Hierarchy

Truth flows downhill. Never let a lower layer override a higher one.

1. **Mesen Trace** — APU register dumps from real gameplay. Frame-level ground truth.
   NSF may diverge from actual game audio (proven: Battletoads, Mario).
   When Mesen trace and NSF disagree, Mesen wins.
2. **SysEx in MIDI** — Lossless register state encoding. Synth replays hardware.
3. **NSF emulation** — 6502 CPU runs the sound driver. Per-frame CC11/CC12.
   Convenient but not always faithful to in-game audio.
4. **CC11/CC12 in MIDI** — Volume + duty envelope. Loses sweep, noise mode, phase.
5. **ADSR approximation** — Only for live keyboard when no file data exists.

Per-game route decision: if NSF fidelity score (via trace_compare) < 80%,
use trace pipeline. Battletoads and Mario are confirmed trace-required games.

## Deckard Boundary (deterministic vs LLM)

| Deterministic (code) | LLM-appropriate |
|----------------------|-----------------|
| NSF emulation, MIDI export, RPP generation | Driver identification from unknown ROMs |
| WAV rendering, MP4 creation, site generation | Command format reverse engineering |
| Trace validation, batch processing | Manifest hypothesis authoring |
| CC11/CC12 playback in synth (frame-accurate) | Game-specific ADSR tuning for keyboard |
| Channel auto-mapping, Bach mashup matrix | Track naming for games without M3U |

## State

- Per-game output: `output/<Game>/` — midi, reaper, wav, nsf
- Manifests: `extraction/manifests/*.json`
- Priorities: this file
- Mistake narratives: @docs/MISTAKEBAKED.md
- Handover (legacy): @docs/HANDOVER.md

## Key Commands

```bash
python scripts/batch_nsf_all.py                                    # batch all games
python scripts/nsf_to_reaper.py <nsf> --all -o output/X/          # single game NSF pipeline
python scripts/generate_project.py --midi <f> --nes-native -o <out>  # REAPER from MIDI
PYTHONPATH=. python scripts/full_pipeline.py <rom> --game-name X   # ROM pipeline (Konami)
PYTHONPATH=. python scripts/trace_compare.py --frames 1792         # validate CV1 parser
python scripts/generate_site.py                                     # rebuild website
```
