# NES Music Studio

NSF/ROM → MIDI → REAPER/WAV/MP4 → YouTube.

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
- **Synth must be dual-mode**: CC-driven for file playback, ADSR for keyboard.
  When CC11 or CC12 arrives on a channel, bypass ADSR and let CC data drive.
  When no CC data (keyboard play), use ADSR envelopes for NES-like feel.
- **Projects must work with zero manual REAPER configuration.** Keyboard,
  MIDI routing, synth settings — everything baked into the RPP file.

## Fidelity Hierarchy

Truth flows downhill. Never let a lower layer override a higher one.

1. **ROM/Trace** — APU register dumps from Mesen. Frame-level ground truth.
2. **NSF emulation** — 6502 CPU runs the sound driver. Per-frame CC11/CC12.
3. **MIDI file** — CC automation IS the envelope. Synth plays it back verbatim.
4. **ADSR approximation** — Only for live keyboard when no CC data exists.

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
