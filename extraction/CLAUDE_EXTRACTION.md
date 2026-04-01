# Extraction Engine

## Core Principle

The NES sound driver is a **stateful frame-based interpreter**, not a data format. Same byte means different things depending on execution context. Canonical time model: **NES frames** (1/60s NTSC). Convert to MIDI only at final export.

## Evidence Hierarchy (never violate)

1. Manually verified reverse-engineering findings (highest)
2. Exact static parser extraction from known format
3. Exact runtime observation from APU trace
4. Reconciled inference (static + dynamic agree)
5. Provisional inference (one source only)
6. Speculative research notes (lowest)

## Terminology

- "period" not "note" for raw APU timer values
- "tempo" only for verified driver timing, not guessed BPM
- "instrument" only if the driver has named instrument definitions

## MIDI Output Contract

Per `docs/REQUIREMENTSFORMIDI.md`: 4 channels (0-3), monophonic per channel, CC11 for volume, CC12 for duty cycle, metadata track with game/song/source/confidence.

## Tools

| Tool | Purpose |
|------|---------|
| `scripts/trace_compare.py` | Frame-level diff vs APU trace |
| `extraction/drivers/konami/frame_ir.py` | Frame-accurate IR with envelope model |
| `extraction/drivers/konami/midi_export.py` | MIDI export from frame IR |
| `extraction/drivers/konami/spec.md` | Command byte format + per-game differences |

## References (don't reinvent)

- **Contra disassembly**: `references/nes-contra-us/docs/Sound Documentation.md`
- **Konami spec**: `extraction/drivers/konami/spec.md` (per-game differences table)

## Path-Specific Rules

When working on drivers: `.claude/rules/new-game-parser.md` loads automatically.
When debugging: `.claude/rules/debugging-protocol.md` loads automatically.
