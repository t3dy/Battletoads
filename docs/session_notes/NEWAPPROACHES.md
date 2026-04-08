# New Approaches — Session 3 (2026-04-02)

## Context

This session picked up from the Session 2 handover. Session 2 ended with a
paradigm shift: stop generating MIDI from trace periods and instead parse ROM
song data directly, using the fan MIDI as a Rosetta Stone to locate data in
the ROM (not as a replacement data source).

## New Approaches Taken This Session

### 1. Skills Manual as Project Documentation

Created `SKILLSMANUAL.md` — a unified reference for all skills across three
systems: PKD planning skills (33), NES music finder skills (7), and sibling
project skills (NESMusicStudio, NESMusicLab). This is the first time the full
skill ecosystem has been documented in one place, including how skills interact
across projects.

**Why this matters:** Future sessions can read one document to understand what
tools are available instead of rediscovering them from scattered skill files.

### 2. ROMPARSER Skill — Driver-Agnostic ROM Extraction

Created `.claude/skills/ROMPARSER.md` — a new orchestrator skill that doesn't
assume any specific driver format. Previous work was either Konami-specific
(CV1/Contra parsers) or Rare-specific (Battletoads finder skills). ROMPARSER
is the first driver-agnostic extraction methodology.

**Key innovations in this skill:**

- **Evidence triangulation:** Uses multiple sources (ROM data, Mesen trace,
  NSF emulation, fan MIDI, fan recordings) rated by trust level per parameter
  type. Fan MIDIs are trusted for pitch but explicitly NOT trusted for rhythm.

- **Hypothesis-driven discovery:** Every manifest field starts as "unknown"
  and gets promoted through "hypothesis" to "verified" with explicit evidence.
  No field jumps straight to verified.

- **Six triangulation strategies:** Known-pitch search, duration bracketing,
  command boundary detection, cross-channel correlation, envelope shape
  fingerprinting, and NSF A/B comparison. Each is a concrete technique for
  resolving a specific class of ambiguity.

- **Fan MIDI as search target, not data source:** The Battletoads lesson
  formalized. When a fan pitch is confirmed correct, use it to locate WHERE
  that byte lives in ROM data and HOW the driver gets from byte to register.
  Work backwards from known-correct pitches to find addressing schemes.

### 3. CV1/Contra Best Practices Audit

Studied the successful Castlevania 1 and Contra extractions to extract proven
patterns and fold them into the ROMPARSER skill:

- **Parser emits full-duration events** (no staccato in parser, all shaping in Frame IR)
- **Frame IR is the canonical layer** (debug here, not at MIDI level)
- **DriverCapability dispatches envelope strategy** (not isinstance checks)
- **One hypothesis per test cycle** (change one thing, rerun comparison)
- **Cross-game regression testing** (fixing Contra exposed a CV1 bug in shared code)
- **6-gate validation protocol** (environment, source integrity, ground truth,
  parameter coverage, artifact build, pre-delivery)

### 4. ROM Data Analysis Began

Read and analyzed the actual ROM bytes at key addresses:
- Period table at $8E22 confirmed (60 entries, C2-B6, standard NTSC)
- Dispatch table at $8B7B confirmed (31 command handlers)
- P2 song data at $A2CF dumped and partially decoded
- Note handler at $88D9 read (shows transposition mechanism)
- Multiple command handlers read to determine parameter counts

**Key finding from this session's analysis:** The byte after each note in
the Rare driver appears to be a duration value (Scheme A in ROMPARSER
terminology). The G2 riff section shows clear note+duration pairs:
`88 02 88 02 88 02 88 06` = G2(dur=2) G2(2) G2(2) G2(6).

This still needs formal verification via trace frame gap comparison, but
it's a strong hypothesis.

---

## Documents Written This Session (10)

| # | File | Type | Purpose |
|---|------|------|---------|
| 1 | `SKILLSMANUAL.md` | Manual | Unified reference for all 40+ skills across PKD planning, NES finder, and sibling projects |
| 2 | `.claude/skills/ROMPARSER.md` | Skill | Driver-agnostic ROM music extraction with evidence triangulation |
| 3 | `NEWAPPROACHES.md` | Summary | This document — session approaches and document inventory |

### Documents Written Last Session (Session 2) Referenced by Handover

| # | File | Type | Purpose |
|---|------|------|---------|
| 4 | `NEXT_SESSION_PROMPT.md` | Handover | Complete state transfer with ROM analysis, decoded commands, song pointers |
| 5 | `docs/BATTLETOADS_SESSION_BLOOPERS.md` | Narrative | Comedy of errors from v3-v9, lessons as stories |
| 6 | `docs/ANXIETY.md` | Anti-regression | Why trace periods are not intended notes, correct pipeline diagram |
| 7 | `.claude/skills/PITCHFINDER.md` | Skill | Period table, note encoding, transposition mechanism |
| 8 | `.claude/skills/RHYTHMFINDER.md` | Skill | Tempo accumulator, duration encoding |
| 9 | `.claude/skills/ENVELOPEFINDER.md` | Skill | Volume envelopes, duty cycle control |
| 10 | `.claude/skills/SEQUENCEFINDER.md` | Skill | Song tables, channel pointers, loop structure |
| 11 | `.claude/skills/COMMANDFINDER.md` | Skill | Full 30-command dispatch reference |
| 12 | `.claude/skills/LOOKUPTABLEFINDER.md` | Skill | Period/envelope/arpeggio table location |
| 13 | `.claude/skills/MUSICFINDER_ORCHESTRATOR.md` | Skill | Coordinates all finders through 4-phase pipeline |

---

## What's Changed Since the Handover

| Before (Session 2 end) | After (Session 3) |
|-------------------------|---------------------|
| 7 finder skills, no overarching method | ROMPARSER skill wraps finders into a driver-agnostic methodology |
| Skills documented individually | SKILLSMANUAL.md unifies all 40+ skills |
| CV1/Contra best practices implicit in code | Best practices audited and codified into ROMPARSER |
| "Fan MIDI as Rosetta Stone" was a verbal insight | Formalized as Triangulation Strategy 1 (Known-Pitch Search) |
| ROM data read but not systematically analyzed | P2 data partially decoded, duration hypothesis formed |
| Manifest format used only for Konami | Manifest format extended with per-field status tracking |

## Next Steps (Not Started)

1. **Verify duration encoding** — confirm Scheme A (note+duration byte pairs)
   by comparing parsed durations against Mesen trace frame gaps
2. **Finish decoding all 31 commands** — especially CMD 0x05, 0x06, 0x1E
   parameter counts and effects
3. **Build the Rare driver parser** — using ROMPARSER methodology
4. **Parse P2 channel completely** — follow subroutine calls, track transposition
5. **Validate against fan MIDI** — first 30 pitches should match E2-D2-G2 riff
