# NES Music Studio — Skills Manual

## What Are Skills?

Skills are reusable Claude Code slash commands. Type `/skill-name` and Claude
executes a structured prompt with domain knowledge baked in. They prevent
wheel-reinvention across sessions and enforce hard-won lessons.

This project uses two skill systems:

1. **PKD Planning Skills** — 33 general-purpose engineering skills (shared across all projects under `C:\Dev`)
2. **NES Music Finder Skills** — 8 domain-specific skills for ROM music extraction (this project only)

---

## Part 1: PKD Planning Skills

Named after Philip K. Dick characters. Each character's situation in the novel
mirrors the skill's function. Organized into two namespaces.

### The 5 Essential Skills (Use Every Session)

| Skill | Character | What It Does | When to Run |
|-------|-----------|-------------|-------------|
| `/plan-joe-chip-scope` | Joe Chip (Ubik) | **Freezes scope.** Forces you to define what you're building and what you're NOT. | FIRST, before any code |
| `/plan-runciter-slice` | Glen Runciter (Ubik) | **Designs vertical slices.** Slice 1 proves the foundation before you touch the fun parts. | SECOND, after scope |
| `/plan-deckard-boundary` | Rick Deckard (Do Androids Dream) | **Maps deterministic vs LLM boundaries.** Prevents using AI where a regex would do. | When designing AI systems |
| `/plan-abendsen-parking` | Hawthorne Abendsen (Man in the High Castle) | **Parks ideas without scope creep.** Ideas aren't rejected, they're stored. | When you think "let me also add..." |
| `/plan-steiner-gate` | Manfred Steiner (Martian Time-Slip) | **Phase gate check.** Verifies current slice passes before you start the next one. | Between phases/slices |

### Full PLAN Skill Reference (26 Skills)

#### Core Infrastructure & Scope Control

| Skill | Purpose |
|-------|---------|
| `/plan-joe-chip-scope` | Scope Freezer — prevent runaway expansion |
| `/plan-runciter-slice` | Vertical Slice Designer — force MVP-first architecture |
| `/plan-deckard-boundary` | Deterministic vs LLM Boundary Mapper |
| `/plan-steiner-gate` | Phase Gate Verifier — enforce phase discipline |
| `/plan-mayerson-prereq` | Environment Prerequisites Checker |

#### Prompt & Token Engineering

| Skill | Purpose |
|-------|---------|
| `/plan-isidore-tokens` | Token Economy Optimizer — reduce prompt waste |
| `/plan-fat-compress` | Concept Compression — distill ideas into prompts |
| `/plan-kevin-pipeline` | Prompt Pipeline Builder — break giant prompts into stages |
| `/plan-buckman-critic` | Prompt Critic — evaluate prompts on 8 dimensions before execution |

#### Architecture & Execution

| Skill | Purpose |
|-------|---------|
| `/plan-eldritch-swarm` | Agent Swarm Architect — define multi-agent roles |
| `/plan-buckman-execute` | Execution Planner — translate plans into repo task lists |
| `/plan-rosen-artifact` | Artifact Generator — force structured outputs |
| `/plan-bulero-refactor` | Architecture Refactorer — simplify sprawling systems |
| `/plan-regan-simplify` | Code Simplification Reviewer |

#### Research & Knowledge Systems

| Skill | Purpose |
|-------|---------|
| `/plan-lampton-corpus` | Research Corpus Analyzer — process document collections |
| `/plan-brady-graph` | Knowledge Graph Builder — structure scholarly material |
| `/plan-taverner-curriculum` | Curriculum Generator — convert research into teaching |
| `/plan-pris-pedagogy` | Difficult Games Pedagogy Mapper |

#### Analysis & Reflection

| Skill | Purpose |
|-------|---------|
| `/plan-runciter-audit` | Failure Mode Analyzer — anticipate breakdowns |
| `/plan-arctor-retro` | Project Retrospective — learn from past mistakes |
| `/plan-fatmode-growth` | Personal Learning Curve Advisor |
| `/plan-abendsen-parking` | Idea Parking Lot — store ideas without scope creep |

#### Context & Framing

| Skill | Purpose |
|-------|---------|
| `/plan-bohlen-constraint` | Constraint Articulator — bound vague requests |
| `/plan-mercer-reframe` | Mental Model Challenger — question assumptions |
| `/plan-tagomi-briefing` | Project Briefing Generator for handover |
| `/plan-freck-narrative` | Narrative Synthesizer — technical to compelling explanation |

### Full WRITE Skill Reference (7 Skills)

| Skill | Purpose |
|-------|---------|
| `/write-dominic-template` | Writing Template Builder |
| `/write-archer-evaluate` | Writing Performance Evaluator — score writing quality |
| `/write-isidore-critique` | Writing Critique Engine — deep structural critique |
| `/write-dekany-style` | Style Consistency Checker |
| `/write-runciter-ux` | Website UX & Design Auditor — paired functional + aesthetic audit |
| `/write-chip-copy` | Microcopy & UI Text Reviewer |
| `/write-rachael-aesthetic` | Visual Design Logic Auditor |

### Trigger Phrases (Build These Habits)

| When you think... | Run this |
|-------------------|----------|
| "Let me also add..." | `/plan-abendsen-parking` |
| "This prompt should handle everything" | `/plan-kevin-pipeline` |
| "I'll just start coding" | `/plan-joe-chip-scope` first |
| "I'll clean this up later" | `/plan-runciter-slice` |
| "The AI should figure this out" | `/plan-deckard-boundary` |
| "I'll skip to the fun part" | `/plan-steiner-gate` |
| "This is getting complicated" | `/plan-bulero-refactor` |
| "Why isn't this working?" | `/plan-runciter-audit` |

### The Optimal Workflow Sequence

```
PHASE 1: INTAKE
  /plan-tagomi-briefing      generate project context
  /plan-mercer-reframe       verify mental model
  /plan-bohlen-constraint    articulate constraints

PHASE 2: SCOPE
  /plan-joe-chip-scope       FREEZE scope (most important step)
  /plan-abendsen-parking     park non-v1 ideas

PHASE 3: ARCHITECTURE
  /plan-deckard-boundary     map deterministic vs LLM
  /plan-runciter-slice       design vertical slices
  /plan-runciter-audit       failure mode analysis

PHASE 4: PROMPT DESIGN (if applicable)
  /plan-fat-compress         compress concepts
  /plan-kevin-pipeline       stage the pipeline
  /plan-isidore-tokens       optimize tokens
  /plan-buckman-critic       critique prompts

PHASE 5: EXECUTION
  /plan-buckman-execute      generate task list
  /plan-mayerson-prereq      check environment
  Build Slice 1...
  /plan-steiner-gate         verify before Slice 2
  Build Slice 2...

PHASE 6: QUALITY
  /plan-regan-simplify       review code
  /write-runciter-ux         audit UX (web projects)
  /write-chip-copy           audit microcopy

PHASE 7: RETROSPECTIVE
  /plan-arctor-retro         what worked, what didn't
  /plan-tagomi-briefing      generate briefing for next session
```

---

## Part 2: NES Music Finder Skills

Eight domain-specific skills for reverse engineering NES music drivers and
extracting musical data from ROMs. These live in `.claude/skills/` within
the NSFRIPPER project.

### The Orchestrator

**MUSICFINDER_ORCHESTRATOR** coordinates all six finder skills through a
five-phase pipeline:

```
Phase 1: DISCOVERY
  LOOKUPTABLEFINDER   find period tables, envelope tables, arpeggio tables
  COMMANDFINDER       decode the full command dispatch table
  SEQUENCEFINDER      find song table, channel pointers, loop structure

Phase 2: PARSING (structural alignment only)
  PITCHFINDER         note bytes + transposition = base note indices
  RHYTHMFINDER        duration encoding = raw duration values
  ENVELOPEFINDER      envelope IDs = envelope table references
  ★ "Zero parse errors" here = byte-stream alignment. NOT musical truth.
    Parser output is a HYPOTHESIS until Phase 3 passes.

Phase 3: EXECUTION SEMANTICS VALIDATION (mandatory before assembly)
  Build frame-level simulator from parsed events + driver model
  Simulate tempo accumulator, duration, pitch modulation, envelopes
  Compare simulated per-frame state against Mesen trace
  Classify mismatches by cause (tempo/duration/arpeggio/envelope)
  Block assembly until sim matches trace within thresholds
  ★ Only after this passes are events "semantics-validated."

Phase 4: ASSEMBLY (only after Phase 3 passes)
  Combine validated pitch + rhythm + envelope into Frame IR
  Project Frame IR to MIDI events
  Generate REAPER project via generate_project.py

Phase 5: VALIDATION
  Compare ROM-derived pitches against fan MIDI (should match)
  Compare ROM-derived timing against trace (should match)
  Ear-check in REAPER (user confirms)
  ★ Only after ear-check: label output "trusted" / "production-ready"
```

### Finder Skill Reference

#### PITCHFINDER

**What it finds:** How a note byte in ROM becomes an APU period value.

- Period table location and contents
- Note byte encoding (what range = notes, what = rests, what = commands)
- Transposition mechanism (per-channel register, absolute/relative set commands)
- Arpeggio/vibrato tables that modify pitch per-frame

**Key lesson:** The Mesen trace captures periods AFTER transposition. Converting
trace periods back to notes gives the TRANSPOSED note, not the intended note.
Always parse ROM data for pitch.

#### RHYTHMFINDER

**What it finds:** How the driver controls note timing.

- Tempo system (frame accumulator, speed register, overflow-triggers-music pattern)
- Duration encoding (inline byte after note? current-duration command? lookup table?)
- Duration counter RAM location
- Rest/silence encoding

**Key output:** Duration values that can be validated against trace frame gaps
between note attacks.

#### ENVELOPEFINDER

**What it finds:** How the driver shapes volume and timbre over time.

- Envelope table location and format (per-frame volume values 0-15)
- Envelope commands in song data (which command sets the envelope ID)
- Duty cycle control (per-frame, per-note, or per-section)
- Constant volume flag usage

**Key output:** Per-frame volume shapes that should match trace CC11 data exactly.

#### SEQUENCEFINDER

**What it finds:** High-level song structure.

- Song table (NSF song number to internal ID mapping)
- Channel pointers (where each channel's data begins for a given song)
- Pattern/subroutine system (call/return commands, shared patterns)
- Loop structure (loop point, loop count, infinite loop at song end)

**Key output:** The address map for parsing any song in the ROM.

#### COMMANDFINDER

**What it finds:** The complete command vocabulary of the music driver.

- Dispatch/jump table location and all handler addresses
- Parameter count for each command (counted from INY instructions in handler code)
- Effect of each command (what RAM locations it writes to)
- Categories: pitch, timing, envelope, flow control, channel control

**Key output:** A reference table like the Battletoads 30-command table.

#### LOOKUPTABLEFINDER

**What it finds:** All lookup tables used by the driver.

- Period table (note index to 11-bit APU timer period)
- Envelope tables (volume shapes)
- Arpeggio tables (semitone offset sequences for chord effects)
- Noise period map (drum note to noise channel period)
- Duty cycle table

**Method:** Scan PRG ROM for sequences of decreasing 16-bit values following
the 2^(1/12) ratio. Cross-reference with driver code that indexes into these tables.

### How the Finders Work Together

```
COMMANDFINDER says: "CMD 0x12 takes 1 param and writes to $0354,X"
PITCHFINDER says:   "The note handler does ADC $0354,X before table lookup"
SEQUENCEFINDER says: "Song 4 P2 data starts at $A2CF"

Combined: "At $A2CF, when we see 0x12 0x0C, it means transposition = 12.
The next note byte 0x85 becomes index (4 + 12) = 16 = E3. But the ROM
intent is E2 (index 4). The MIDI should say E2."
```

#### ROMEMULATOR

**What it does:** Extracts NES music by booting the ROM in a headless 6502
emulator — no NSF, no manual gameplay, no music format reverse-engineering.

- Boots from RESET vector, fires NMI at 60Hz, captures APU register writes
- MMC1 mapper emulation (bank switching via serial register protocol)
- Controller simulation (scripted button presses per frame)
- Hot-swap technique: switch banks for one NMI to copy song code to RAM,
  switch back to tick the new song from the original bank's NMI handler
- Combined extraction: data-driven pulse player + code-as-music noise/triangle
- Outputs Mesen-compatible CSV that feeds directly into mesen_to_midi.py

**When to use:**
- NSF doesn't match the target ROM (FDS vs NES, JP vs US)
- Music engine is too complex to parse (code-as-music, game-state-dependent)
- You want fully automated extraction for ALL songs
- You've been going in circles reverse-engineering the music format

**Key lesson from Kid Icarus:** Don't parse the music data — run the game's
own code. The CPU writes to APU registers to make sound. Capture those writes.
The game's code is the best parser of its own music format.

**Tool:** `scripts/nes_rom_capture.py`

### Anti-Patterns (From ANXIETY.md + EXECUTIONSEMANTICSVALIDATION.md + Kid Icarus)

1. **Don't polish trace-derived pitches** — fix the source (ROM parsing)
2. **Don't assume one game's encoding works for another** — even same driver family differs
3. **Don't skip validation against a known reference** — fan MIDI, NSF, or ear-check
4. **Don't generate MIDI before understanding the full command set**
5. **When stuck, read the 6502 disassembly** — the code is the ultimate truth
6. **Don't treat zero parse errors as musical correctness** — byte-stream alignment ≠ correct pitches/durations/envelopes
7. **Don't skip execution semantics validation** — simulate driver frame-by-frame and compare against trace before assembly
8. **Don't promote parser output to MIDI without simulation** — parser output is a hypothesis, not ground truth
9. **Don't reverse-engineer the music format when you can run the code** — if you've spent 30+ minutes parsing data tables, try the ROM emulator instead
10. **Don't assume the NSF matches the ROM** — FDS/NES, PAL/NTSC, JP/US platform variants can have completely different music

---

## Part 3: Related Project Skills

Two sibling projects have their own skill sets:

### NESMusicStudio (`C:\Dev\NESMusicStudio\.claude\skills\`)

Operational pipeline skills for the production workflow:

| Skill | Purpose |
|-------|---------|
| `nes-rip` | Full NSF-to-MIDI extraction pipeline |
| `nes-batch` | Batch process all unprocessed games |
| `nes-capture` | Mesen trace capture workflow |
| `nes-segment` | Segment long traces into individual songs |
| `nes-separate-sfx` | Separate music from sound effects |
| `nes-validate` | Validate extraction against ground truth |
| `nes-scan-rom` | Scan ROM for music driver signatures |
| `nes-find-pointer-table` | Locate music pointer tables in ROM |
| `nes-nesmdb` | Cross-reference with NES Music Database |

### NESMusicLab (`C:\Dev\NESMusicLab\.claude\skills\`)

Research and analysis skills for deep driver investigation:

| Skill | Purpose |
|-------|---------|
| `nes-driver-recon` | Reconnaissance on unknown music drivers |
| `apu-trace-analysis` | Deep analysis of APU trace data |
| `sequence-reconstruction` | Reconstruct song sequences from ROM data |
| `instrument-reconstruction` | Reconstruct instrument/envelope definitions |
| `trace-static-reconciliation` | Compare trace (dynamic) vs ROM (static) analysis |
| `midi-export-audit` | Audit MIDI export quality |
| `reaper-export` | REAPER project generation and validation |
| `research-audit` | Audit research findings for completeness |

---

## Part 4: How Skills Interact Across Projects

```
NESMusicLab (research)     NSFRIPPER (extraction)     NESMusicStudio (production)
  driver-recon          -->  COMMANDFINDER          -->  nes-rip
  apu-trace-analysis    -->  PITCHFINDER            -->  nes-batch
  sequence-recon        -->  SEQUENCEFINDER          -->  nes-validate
  instrument-recon      -->  ENVELOPEFINDER          -->  nes-capture
  trace-static-recon    -->  MUSICFINDER_ORCHESTRATOR-->  nes-segment

                            PKD Skills (all projects)
                            /plan-joe-chip-scope
                            /plan-runciter-slice
                            /plan-deckard-boundary
                            /plan-steiner-gate
                            /plan-abendsen-parking
```

The research skills (Lab) produce knowledge. The finder skills (NSFRIPPER) use
that knowledge to build parsers. The production skills (Studio) use those
parsers to batch-process games.

PKD planning skills govern the workflow at every stage.

---

## Part 5: The Ground Truth Hierarchy

Every skill operates within this hierarchy. Higher layers override lower ones:

```
1. Mesen Trace     — APU register dumps from actual gameplay (frame-level truth)
2. ROM Song Data   — the composer's intended notes, parsed by finder skills
3. NSF Emulation   — 6502 CPU runs the sound driver (convenient, not always faithful)
4. Fan MIDI        — human transcription (good pitch, unreliable rhythm)
5. MIDI Export      — downstream projection from any of the above
```

When sources disagree:
- Trace vs NSF: trace wins (proven by Mario, Battletoads)
- ROM data vs trace: ROM for pitch, trace for timing/envelope
- Fan MIDI vs anything: use fan MIDI as a search target, not a replacement source

---

## Quick Reference Card

```
STARTING A NEW PROJECT:
  /plan-joe-chip-scope    freeze scope
  /plan-runciter-slice    design slices
  /plan-deckard-boundary  map AI boundaries

STARTING A NEW GAME EXTRACTION:
  COMMANDFINDER           decode driver commands
  LOOKUPTABLEFINDER       find period/envelope tables
  SEQUENCEFINDER          find song structure
  PITCHFINDER             decode note encoding + transposition
  RHYTHMFINDER            decode duration encoding
  ENVELOPEFINDER          decode volume envelopes
  MUSICFINDER_ORCHESTRATOR coordinate all of the above
  ★ After parsing: run EXECUTION SEMANTICS VALIDATION
    (simulate driver, compare against trace, THEN assemble MIDI)

DURING BUILD:
  /plan-abendsen-parking  park new ideas
  /plan-steiner-gate      gate between phases

AFTER BUILD:
  /plan-arctor-retro      honest retrospective
  /plan-tagomi-briefing   handover doc for next session
```
