# HARDENING.md — Environmental Rebuild

## What This Document Is

This is the record of converting the NES Music Studio pipeline from
a collection of callable skills into a self-regulating execution
system. The input was a detailed prompt specifying 8 parts of
infrastructure hardening. This document contains the complete
response: the orchestrator, the manifest schema, the context
loading rules, the enforcement gates, and the minimal prompt
interface.

---

## PART 1: ORCHESTRATOR STATE MACHINE

### States

```
NEW             — manifest exists, nothing else
CAPTURE_NEEDED  — no trace available
RENDERING       — trace archived, WAV being produced
SEGMENTING      — WAV exists, splitting into tracks
SCANNING        — ROM analysis in progress
POINTER_SEARCH  — looking for sound table (max 2 attempts)
POINTER_STUCK   — 2 attempts failed, debugger recommended
VALIDATING      — one track being parsed and compared to trace
VALIDATION_FAIL — parsed output doesn't match trace
EXTRACTING      — batch extraction in progress
COMPLETE        — all tracks extracted and validated
DEAD_END        — driver unknown, no path forward
```

### Transitions

```
NEW → CAPTURE_NEEDED
  trigger: manifest created, trace_available == false
  action: print "Capture a Mesen APU trace and tell me the path."

CAPTURE_NEEDED → RENDERING
  trigger: user provides capture CSV path
  action: run nes-capture (archive + render WAV)

RENDERING → SEGMENTING
  trigger: WAV file exists with duration > 0
  action: run nes-segment (silence detection + melody comparison)

SEGMENTING → SCANNING
  trigger: segments produced, user has identified at least one track
  action: run nes-scan-rom (header, period table, command signatures)
  parallel: run nes-nesmdb if game is in database

SCANNING → POINTER_SEARCH
  trigger: manifest has mapper, period_table fields populated
  action: run nes-find-pointer-table (attempt 1: exact match)

POINTER_SEARCH → POINTER_SEARCH (attempt 2)
  trigger: attempt 1 returned no results
  action: run nes-find-pointer-table (attempt 2: relaxed structural)
  guard: pointer_search_attempts < 2

POINTER_SEARCH → POINTER_STUCK
  trigger: pointer_search_attempts >= 2, no candidate found
  action: print debugger instructions, set status = POINTER_STUCK
  HARD BLOCK: no further scanning permitted

POINTER_SEARCH → VALIDATING
  trigger: candidate found (verified or candidate status)
  action: run nes-validate

POINTER_STUCK → VALIDATING
  trigger: user provides pointer table address from debugger
  action: update manifest, run nes-validate

VALIDATING → EXTRACTING
  trigger: validation report shows pitch >= 95% AND user says PASS
  action: run nes-batch

VALIDATING → VALIDATION_FAIL
  trigger: pitch < 80% OR user says FAIL
  action: report first mismatch, suggest debugging steps
  next: user fixes issue, returns to VALIDATING

EXTRACTING → COMPLETE
  trigger: all tracks parsed, MIDI + WAV + RPP produced
  action: update manifest status = complete

SCANNING → DEAD_END
  trigger: no Maezawa signatures, no period table, unknown driver
  action: set status = dead_end, recommend deprioritizing
  note: trace renders are still valid and useful
```

### Forbidden Transitions

These transitions are BLOCKED. The orchestrator must refuse them.

```
CAPTURE_NEEDED → SCANNING          (no trace = no ROM analysis)
CAPTURE_NEEDED → POINTER_SEARCH    (no trace = no pointer search)
CAPTURE_NEEDED → VALIDATING        (no trace = no validation)
CAPTURE_NEEDED → EXTRACTING        (no trace = no extraction)
SCANNING → EXTRACTING              (skips validation gate)
POINTER_SEARCH → EXTRACTING        (skips validation gate)
POINTER_STUCK → EXTRACTING         (skips validation gate)
VALIDATION_FAIL → EXTRACTING       (failed validation = no batch)
```

### Skill Visibility

| Skill | User-callable | Orchestrator-internal | Requires state |
|-------|--------------|----------------------|----------------|
| nes-capture | YES | YES | any |
| nes-segment | YES | YES | trace exists |
| nes-scan-rom | YES | YES | any (but trace recommended) |
| nes-nesmdb | YES | YES | any |
| nes-find-pointer-table | NO | YES | SCANNING complete |
| nes-validate | NO | YES | pointer candidate + trace |
| nes-batch | NO | YES | validation PASSED |
| nes-separate-sfx | YES | NO | trace exists |
| nes-rip (orchestrator) | YES | — | entry point |

Skills marked "NO" for user-callable can only run through the
orchestrator. Direct invocation must check the manifest state and
refuse if preconditions aren't met.

---

## PART 2: MANIFEST AS CONTROL SURFACE

### Schema

```json
{
  "game": "super_c",
  "rom_file": "extraction/roms/super_c.nes",

  "pipeline_stage": "SCANNING",

  "header": {
    "mapper": {"value": 2, "status": "verified", "evidence": "rom_header"},
    "prg_banks": {"value": 8, "status": "verified", "evidence": "rom_header"},
    "chr_banks": {"value": 0, "status": "verified", "evidence": "rom_header"}
  },

  "driver": {
    "family": {"value": "contra_variant", "status": "high", "evidence": "command_signatures"},
    "vibrato_active": {"value": true, "status": "verified", "evidence": "trace"}
  },

  "period_table": {
    "address": {"value": "NOT_FOUND", "status": "not_found", "evidence": "rom_scan"},
    "format": {"value": "unknown", "status": "unknown"},
    "tuning": {"value": "contra_variant", "status": "verified", "evidence": "trace"}
  },

  "pointer_table": {
    "address": {"value": "UNKNOWN", "status": "unknown"},
    "format": {"value": "unknown", "status": "unknown"},
    "bank": {"value": null, "status": "unknown"},
    "search_attempts": 2
  },

  "traces": [
    {
      "file": "extraction/traces/super_c/capture1.csv",
      "frames": 4076,
      "duration_sec": 67.9,
      "track_identified": "Thunder Landing (Stage 1)",
      "identified_by": "user"
    }
  ],

  "segments": [
    {"id": 1, "frames": "0-442", "duration": 7.4, "name": "intro SFX"},
    {"id": 2, "frames": "442-4076", "duration": 60.6, "name": "Thunder Landing"}
  ],

  "validation": {
    "status": "not_attempted",
    "track": null,
    "pitch_match_pct": null,
    "user_verdict": null
  },

  "tracks_extracted": [],

  "output_version": 1,
  "status": "scanning",
  "notes": "Period table not found as contiguous block. Pointer table search exhausted 2 attempts. Debugger recommended."
}
```

### Field Rules

**Status values:** `verified` > `candidate` > `high` > `medium` > `low` > `unknown` > `not_found`

**Evidence values:** `rom_header` | `rom_scan` | `trace` | `disassembly` | `user` | `nesmdb_match` | `hypothesis`

**Write rules:**
- A field with status `verified` can NEVER be overwritten by `candidate` or lower
- `pipeline_stage` is set ONLY by the orchestrator
- `validation.status` is set ONLY by nes-validate
- `output_version` increments on every batch extraction, never decrements
- `pointer_table.search_attempts` increments on each search, triggers HARD STOP at 2

**Read rules:**
- The orchestrator reads `pipeline_stage` to determine next action
- Every skill reads its precondition fields before executing
- No skill reads fields outside its scope (nes-segment doesn't read pointer_table)

---

## PART 3: CONTEXT LOADING RULES

### Layer 0 — Always (loaded every session, <200 tokens)

```
Project: NES Music Studio — ROM → parser → frame IR → MIDI → REAPER/WAV
Rule: trace is ground truth
Rule: one track validated before batch
Rule: version all outputs, never overwrite
Rule: 2 pointer search attempts max, then debugger
Current game: read from manifest pipeline_stage
```

This replaces the current CLAUDE.md workflow section.

### Layer 1 — Manifest (loaded when game is specified)

Read `extraction/manifests/{game}.json`. This tells the session:
- What pipeline stage we're at
- What's verified vs unknown
- What traces exist
- Whether validation has passed

No other game-specific context is needed at session start.

### Layer 2 — Driver spec (loaded when driver.family.status != "unknown")

| driver.family.value | Load |
|---------------------|------|
| maezawa | extraction/drivers/konami/spec.md (note encoding, octave commands) |
| contra_variant | spec.md + Contra-specific sections (DX 3-byte, lookup envelopes, vibrato) |
| fujio | CV2-specific encoding notes |
| unknown | NOTHING about any driver. Start fresh. |

### Layer 3 — Task-specific (loaded based on pipeline_stage)

| pipeline_stage | Load |
|---------------|------|
| CAPTURE_NEEDED | Nothing extra — just ask for trace |
| RENDERING | Trace renderer parameters |
| SEGMENTING | Silence detection thresholds |
| SCANNING | Period table byte patterns, command signature ranges |
| POINTER_SEARCH | Reference disassembly format (if available), 2-attempt rule |
| VALIDATING | trace_compare.py usage, pitch match thresholds |
| EXTRACTING | Parser invocation, output naming conventions |

### Layer 4 — Mistake triggers (loaded ONLY when conditions match)

| Condition | Load |
|-----------|------|
| pointer_table.search_attempts == 1 and status == unknown | PATTERNMATCHING.md rules 1-5 |
| pointer_table.search_attempts == 2 | GRINDINGONTHEPOINTERTABLE.md "2 attempts max" rule |
| driver.family.status == "unknown" | Gradius lesson: "not all Konami games are Maezawa" |
| pipeline_stage == VALIDATION_FAIL | Debugging protocol: dump trace first, one hypothesis |
| user says "let me also add..." | ABENDSEN parking lot (scope creep) |

**Never preload Layer 4.** It fires only when the specific condition is met.

---

## PART 4: ENFORCEMENT GATES

### Hard blocks (produce immediate STOP)

```
BLOCK: nes-validate
  IF manifest.traces is empty
  MESSAGE: "Cannot validate without a trace. Capture one in Mesen first."

BLOCK: nes-batch
  IF manifest.validation.status != "PASS"
  MESSAGE: "Batch extraction blocked. Run /nes-validate and get a PASS first."

BLOCK: nes-find-pointer-table (attempt 3+)
  IF manifest.pointer_table.search_attempts >= 2
  MESSAGE: "Pointer search exhausted (2 attempts). Use Mesen debugger:
    1. Set breakpoint on $4002 write
    2. Play until music starts
    3. Note the calling code address
    4. The table address is in the code"

BLOCK: hypothesis generation
  IF manifest.header.mapper.status != "verified"
  MESSAGE: "ROM not scanned yet. Run /nes-scan-rom before writing hypotheses."

BLOCK: driver family assertion
  IF evidence == "hypothesis"
  MESSAGE: "Driver family is a hypothesis, not verified. Do not treat as fact."
```

### Required transitions (state machine enforced)

```
CAPTURE_NEEDED is the MANDATORY first state for any new game.
No path exists from NEW to SCANNING that bypasses CAPTURE_NEEDED.

VALIDATING is the MANDATORY gate before EXTRACTING.
No path exists from any state to EXTRACTING that bypasses VALIDATING.

POINTER_STUCK requires USER INPUT (debugger address) to proceed.
No automated path exists from POINTER_STUCK to VALIDATING.
```

### Soft warnings (produce WARNING, don't block)

```
WARN: nes-nesmdb
  IF median pulse pitch > MIDI 80
  MESSAGE: "Pitch seems high. Check against trace — may need octave correction."

WARN: nes-segment
  IF no silence gaps found
  MESSAGE: "No track boundaries detected. This capture may be a single track."

WARN: nes-scan-rom
  IF driver.family matches publisher assumption but not ROM evidence
  MESSAGE: "Driver family based on publisher, not ROM signatures. Verify."
```

---

## PART 5: POINTER TABLE STRATEGY

### Tiered discovery (enforced order)

```
Tier 1: Reference disassembly
  Check references/ for annotated source of this game or same-engine game.
  If found: read the sound table format directly.
  Result: VERIFIED address with zero search.

Tier 2: Exact format match
  If driver family is known: search for the EXACT control byte pattern.
  Contra: 0x18 0x01 0x02 0x03 with valid addresses.
  CV1: grouped 9-byte records with 3 valid pointers.
  Budget: 1 attempt.

Tier 3: Trace-guided structural search
  Use trace period values to identify the sound bank.
  Search that bank ONLY for ascending unique pointers
  whose targets contain E0-E4 within 16 bytes.
  Validate top candidate by parsing one channel and
  comparing pitch sequence to trace.
  Budget: 1 attempt.

Tier 4: HARD STOP
  IF Tiers 1-3 all fail:
  Set pointer_table.status = "unknown"
  Set pipeline_stage = "POINTER_STUCK"
  Print Mesen debugger instructions.
  DO NOT attempt Tier 5, 6, 7, or any further scanning.
```

### What is explicitly forbidden

- Relaxation spirals (each search more permissive than the last)
- Heuristic scoring without trace validation
- Searching all banks when trace data narrows to one bank
- More than 2 automated search attempts total

---

## PART 6: TRACE AS PRIMARY SYSTEM

### Priority order

```
1. TRACE (hardware register ground truth)
2. ROM SCAN (byte-level facts)
3. DISASSEMBLY (code-level understanding)
4. NESMDB (reference audio, may have artifacts)
5. HYPOTHESIS (training knowledge, often wrong)
```

### Encoding in the state machine

```
manifest.traces is empty → pipeline_stage MUST be CAPTURE_NEEDED
manifest.traces is empty → nes-scan-rom MAY run but CANNOT lead to VALIDATING
manifest.traces is empty → nes-find-pointer-table SHOULD NOT run
  (searching without trace validation data is wasteful)
```

### What trace enables

- WAV render (immediate, game-agnostic)
- Track identification (user ear)
- Period value extraction (guides ROM scan to correct bank)
- Validation reference (parsed output compared frame-by-frame)
- Vibrato detection (period wobble analysis)
- SFX separation (pitch-jump heuristic)

Without a trace, the only useful operation is nes-scan-rom for
basic ROM facts. Everything else is blocked or degraded.

---

## PART 7: OUTPUT DISCIPLINE

### Versioning

```
output/{Game}/wav/{file}_v{N}.wav
output/{Game}/midi/{file}_v{N}.mid
output/{Game}/reaper/{file}_v{N}.rpp
```

**Rule:** before writing any output file, check if v{N} exists.
If yes, increment N. Never overwrite. Never delete.

### Manifest linkage

Every output file must be recorded in the manifest:
```json
"tracks_extracted": [
  {
    "number": 1,
    "name": "Thunder Landing",
    "midi": "output/Super_C/midi/super_c_track_01_thunder_landing_v1.mid",
    "wav": "output/Super_C/wav/super_c_track_01_thunder_landing_v1.wav",
    "rpp": "output/Super_C/reaper/super_c_track_01_thunder_landing_v1.rpp",
    "validated_against_trace": true,
    "pitch_match_pct": 97.2,
    "version": 1
  }
]
```

### Validation reports

Stored in the manifest under `validation`, not as separate files.
The manifest IS the project memory.

---

## PART 8: MINIMAL PROMPT INTERFACE

### What the user types

| User input | System response |
|-----------|----------------|
| "process super c" | Read manifest → determine stage → execute next step |
| "SAVED: capture.csv" | Archive trace → render WAV → segment → ask for track ID |
| "that's Thunder Landing" | Update manifest → advance to SCANNING |
| "find the pointer table" | Check attempts < 2 → run search → report result or STOP |
| "validate" | Check trace + pointer table exist → parse → compare → report |
| "extract all" | Check validation passed → batch extract → report |
| "separate sfx" | Check trace exists → render 6 WAVs |
| "status" | Print manifest pipeline_stage + what's needed next |

### What the user never types

- Driver family predictions
- Period table addresses
- Pointer table search parameters
- Parsing commands
- Output file paths
- Context loading instructions

The system handles all of this from the manifest.

### Session startup

```
1. User says game name (or system reads from manifest)
2. System loads Layer 0 (invariants) + Layer 1 (manifest)
3. System reports: "Super C is at stage POINTER_STUCK.
   The pointer table wasn't found after 2 search attempts.
   Next step: provide the address from Mesen debugger, or
   capture another trace for a different track."
4. User provides input
5. System advances state machine
```

No context about CV1 envelopes. No Maezawa command format.
No hypothesis documents. Just: what stage, what's next.
