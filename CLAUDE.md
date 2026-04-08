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
- **Trace is ground truth** for games with ROM parsers (CV1, Contra, W&W).
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
- **Parser output is hypothesis, not music.** Structural parsing gives
  event structure. Trusted musical output requires execution semantics
  validation against ground truth. See `.claude/rules/architecture.md` Rules 13-17.
- **Noise is a separate semantic domain.** Do not force noise channels
  through melodic assumptions. Noise has different encoding, validation
  criteria, and runtime behavior. Document noise status separately.

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

## Game Extraction Status

| Game | Ladder Rung | Melodic | Noise | Notes |
|------|-------------|---------|-------|-------|
| Castlevania 1 | 4 (trusted) | Validated | Validated | Proven pipeline. 0 pitch mismatches. |
| Contra | 4 (trusted) | Validated | Validated | Proven pipeline. |
| Wizards & Warriors | 2-3 (partial) | Rung 2 all 16 songs (512f), Rung 3 title (2169f) | Rung 1 (structural) + partial Rung 2 (3 active songs) | Strong milestone, not final. See W&W validation record. |
| Battletoads | 1 (parser-aligned) | Structural only | Structural only | Execution semantics validation in progress. |
| Super Mario Bros | NSF only | N/A | N/A | NSF pipeline, no ROM parser. |

Existing MIDI/RPP output for games below Rung 3 is **hypothesis output** —
usable for practical work (listening, arrangement) but not claimable as
verified or trusted.

## NON-NEGOTIABLE RULES

```
NON-NEGOTIABLE: Never skip Frame IR.
Trace-derived exports must follow:
Trace -> canonical frame state -> Frame IR -> MIDI/CC/SysEx/project projection.
Raw register changes are not yet musical events.
Direct period-change-to-note conversion is a known failure mode.
Validation should fail if a trace route bypasses Frame IR.
```

```
NON-NEGOTIABLE: Zero parse errors is NOT musical correctness.
Parse alignment must be followed by EXECUTION SEMANTICS VALIDATION.
Zero parse errors means byte-stream alignment — bytes correctly partitioned.
It does NOT mean pitches, durations, envelopes, or timing are correct.
Parser output is a hypothesis until execution semantics validation passes.
No pitch/rhythm/timbre claims may be promoted to "trusted" without it.
```

```
NON-NEGOTIABLE: Execution Semantics Validation (required phase).
After parser alignment, simulate the driver frame by frame:
  - tempo accumulator, duration counters, control flow
  - pitch modulation (arpeggio, vibrato, sweep)
  - volume envelopes, duty cycle
Compare simulated per-frame state against Mesen trace.
Block promotion to MIDI/REAPER/trusted output until this passes.
Required artifacts: parsed event stream, simulated frame-state trace,
  comparison report, mismatch taxonomy.
See EXECUTIONSEMANTICSVALIDATION.md for full spec.
```

**Different ROMs use different music engines.** Do not hard-code one universal
decoding model. The system must support per-game/per-engine adaptation.

**Three-Layer Architecture (Observed / Intent / Projection):**

All ROM-derived extraction operates across three layers that must
remain distinct in code, artifacts, documentation, and reasoning:

1. **Observed layer** (ground truth): Mesen trace, NSF emulation,
   direct emulator APU state. Authoritative. When other layers
   disagree, this layer wins.
2. **Intent layer** (parser-derived interpretation): parsed event
   stream, simulated driver state, reconciled musical events.
   This is a HYPOTHESIS until validated against Layer 1.
3. **Projection layer** (generated output): MIDI, REAPER, SysEx,
   WAV, MP4, musical claims. PROVISIONAL until Layer 2 passes
   the execution semantics gate against Layer 1.

Execution semantics validation is the gate between Intent and Projection.
If that gate is not passed, Projection outputs are hypothesis output.

**Five pipeline sub-layers (never conflate):**
1. Parsed/interpreted event stream from ROM (structural hypothesis)
2. Simulated frame-level driver state (execution semantics)
3. Canonical observed data (FrameState from trace/NSF — ground truth)
4. Inferred musical interpretation (Frame IR)
5. Downstream DAW/playback projection (MIDI/RPP/synth)

**Three distinct use-cases (never collapse):**
1. Archival/analytical fidelity to ROM behavior
2. Editable REAPER project generation
3. Live MIDI keyboard play through synth plugin

**Pipeline milestone labels (use precisely):**
- **Parser-aligned**: byte-stream alignment confirmed, zero desync. STRUCTURAL milestone only.
- **Semantics-validated**: simulated frame state matches trace within thresholds. SEMANTIC milestone.
- **Trusted / production-ready**: semantics-validated AND ear-checked. May be projected to MIDI/REAPER.
- **Hypothesis output**: parser-derived music before validation. Usable practically, not claimable as verified.

**Validation Ladder** (see `session_protocol.md` for full table):
- Rung 0: Unexamined → Rung 1: Parser-aligned → Rung 2: Internal semantics
- Rung 3: External trace → Rung 4: Trusted projection → Rung 5: Full-game trusted

Read `.claude/rules/session_protocol.md` for gates, ladder, and delivery checklist.
Read `.claude/rules/architecture.md` for the 17 architectural rules.
Read `docs/ARCHITECTURE_SPEC.md` for the full pipeline rebuild specification.

## Key Commands

```bash
# PRIMARY: kitchen_sink.py generates all routes, validates, compares, blocks on failure
python scripts/kitchen_sink.py \
  --capture <trace.csv> --game <Game> --name <Song> -o output/<Game>/

# Legacy single-route (being replaced by kitchen_sink.py):
python scripts/batch_nsf_all.py                                    # batch all games
python scripts/nsf_to_reaper.py <nsf> --all -o output/X/          # single game NSF pipeline
python scripts/trace_to_midi.py <capture.csv> -o output/X/ --auto-segment  # trace pipeline
python scripts/generate_project.py --midi <f> --nes-native -o <out>  # REAPER from MIDI
PYTHONPATH=. python scripts/trace_compare.py --frames 1792         # validate CV1 parser
python scripts/generate_site.py                                     # rebuild website
```
