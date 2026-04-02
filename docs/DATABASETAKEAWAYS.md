# Database Takeaways: What an Agentic ROM Music System Needs to Know

Observations from five days of NES music reverse engineering, organized
as a data-problem specification for building a queryable database that
an agentic coding system can use to drive the pipeline autonomously.

---

## 1. The Core Ontology: Six Layers, Each a Table Family

The pipeline has six distinct information layers. Each requires its
own schema because the data shapes, update frequencies, and truth
sources are fundamentally different.

### Layer 1: Hardware Facts (static, write-once)

```
Table: nes_apu_registers
  register_addr:  hex          -- $4000, $4001, ..., $4015
  bit_fields:     json         -- [{name, bits, values}]
  channel:        enum         -- pulse1, pulse2, triangle, noise, dpcm
  behavior:       text         -- what this register controls

Table: nes_apu_formulas
  name:           text         -- "pulse_freq", "tri_freq", "noise_timer"
  formula:        text         -- "1789773 / (16 * (period + 1))"
  domain:         text         -- "period: 8-2047 (pulse), 2-2047 (triangle)"
  gotchas:        text[]       -- ["triangle divider is 32, not 16", ...]
```

These never change. They encode NES hardware facts. Every downstream
computation depends on getting these right. The database should serve
these as immutable reference data.

**Agentic use**: Before computing any pitch or frequency, the agent
queries the formula table for the correct divisor and valid range.
Prevents the "triangle is 1 octave lower" bug that hit every session.

### Layer 2: Game Identity (slow-changing, per-game)

```
Table: games
  slug:           text PK      -- "battletoads", "castlevania"
  developer:      text         -- "Rare", "Konami"
  year:           int
  mapper:         int          -- iNES mapper number
  sound_driver:   text         -- "rare_custom", "maezawa_v2"
  nsf_track_count: int
  trace_available: bool
  fidelity_route: enum         -- "nsf_sufficient", "trace_required", "unknown"

Table: track_listing
  game_slug:      text FK
  nsf_number:     int
  track_name:     text         -- "Ragnarok's Canyon"
  game_context:   text         -- "Level 1"
  source:         text         -- "KHInsider", "VGMRips"

Table: game_manifests
  game_slug:      text FK
  driver_family:  text
  pointer_table:  hex
  command_format: json         -- per-opcode byte counts
  period_table:   int[]        -- 12-note lookup
  envelope_model: enum         -- "parametric", "lookup_table", "unknown"
  percussion:     enum         -- "inline", "separate_channel", "none"
  known_facts:    text[]
  hypotheses:     text[]       -- EXPLICITLY separated from facts
```

**Agentic use**: Before writing any parser code, the agent queries the
manifest. If `hypotheses` is non-empty and `known_facts` is sparse,
the agent should flag "insufficient information — read disassembly first."

**Critical lesson**: The `fidelity_route` field prevents the single
most expensive mistake. Battletoads burned 15+ prompts because the
agent assumed NSF was sufficient. A pre-computed fidelity score
(from trace comparison) would have routed to the trace pipeline
immediately.

### Layer 3: Extraction State (per-run, mutable)

```
Table: extraction_runs
  id:             serial PK
  game_slug:      text FK
  track_number:   int
  pipeline:       enum         -- "nsf", "trace", "rom_parser"
  source_path:    text         -- path to NSF/CSV/ROM
  timestamp:      timestamp
  status:         enum         -- "running", "completed", "failed"

Table: extraction_outputs
  run_id:         int FK
  artifact_type:  enum         -- "midi", "rpp_console", "rpp_apu2", "wav", "sysex"
  path:           text
  version:        int          -- v1, v2, v3...
  notes_p1:       int          -- note count per channel
  notes_p2:       int
  notes_tri:      int
  notes_noise:    int
  cc_count:       int          -- total CC messages
  sysex_count:    int          -- total SysEx messages
  midi_range_min: int          -- lowest MIDI note
  midi_range_max: int          -- highest MIDI note
  verified_by:    enum         -- "structure", "listening", "trace_compare", "none"
```

**Agentic use**: The agent can query "what artifacts exist for this
game/track?" and "what verification level have they reached?" before
deciding whether to re-extract or build on existing output.

**Critical lesson**: The `verified_by` field is the most important
column. Our pipeline produced dozens of "completed" artifacts that
were structurally valid but audibly wrong. The database must distinguish
"file exists" from "file verified."

### Layer 4: Fidelity Measurements (per-comparison)

```
Table: fidelity_comparisons
  id:             serial PK
  game_slug:      text FK
  track_number:   int
  source_a:       text         -- "nsf_extraction"
  source_b:       text         -- "mesen_trace"
  frames_compared: int

Table: fidelity_per_channel
  comparison_id:  int FK
  channel:        enum
  pitch_mismatches:   int
  volume_mismatches:  int
  duty_mismatches:    int
  timing_mismatches:  int
  first_mismatch_frame: int
  overall_score:  float        -- 0.0 to 1.0

Table: fidelity_decisions
  game_slug:      text FK
  decided_route:  enum         -- "nsf", "trace", "hybrid"
  reason:         text
  decided_at:     timestamp
  decided_by:     text         -- "automated_threshold" or "human_earcheck"
```

**Agentic use**: When the fidelity score drops below 80%, the system
automatically routes to the trace pipeline. When a human ear-check
overrides the automated decision, that's recorded as a higher-truth
decision.

**Critical lesson**: The `first_mismatch_frame` field is the single
most useful debugging datum. When something sounds wrong, you don't
need to know how MANY mismatches there are — you need to know WHERE
the first one is.

### Layer 5: Bug and Fix History (append-only)

```
Table: blunders
  id:             serial PK
  game_slug:      text FK      -- NULL if cross-game
  symptom:        text         -- "no sound from REAPER projects"
  root_cause:     text         -- "JSFX empty else branch syntax error"
  fix:            text         -- "add 0; no-op to empty else branches"
  prompts_wasted: int          -- cost in LLM prompts
  category:       enum         -- "synth", "encoding", "project_gen", "mapping", "methodology"
  prevention:     text         -- "check FX window for error banner"
  timestamp:      timestamp

Table: fix_patterns
  pattern_name:   text PK      -- "check_synth_first"
  trigger:        text         -- "before any RPP debugging"
  action:         text         -- "open FX window, verify no error banner"
  cost_if_skipped: text        -- "15+ prompts debugging wrong layer"
  derived_from:   int[] FK     -- blunder IDs that produced this pattern
```

**Agentic use**: Before starting any debugging task, the agent queries
fix_patterns for applicable triggers. The database serves as a
"don't repeat this" oracle.

**Critical lesson for LLM context engineering**: The blunders table
is the most valuable training signal for future sessions. Each row
encodes a specific failure mode with its cost. An agent that reads
these before starting work avoids the most expensive mistakes. The
`prompts_wasted` column is the loss function — optimize to minimize it.

### Layer 6: LLM Session State (per-conversation)

```
Table: session_log
  session_id:     uuid PK
  started_at:     timestamp
  game_slug:      text FK
  phase:          enum         -- "rehydrate", "environment", "extraction", "validation", "reporting"

Table: session_decisions
  session_id:     uuid FK
  timestamp:      timestamp
  decision:       text         -- "route via trace pipeline"
  reasoning:      text         -- "NSF fidelity score 54%"
  evidence:       text         -- "trace_compare output"
  outcome:        enum         -- "correct", "incorrect", "unknown"

Table: session_hypotheses
  session_id:     uuid FK
  hypothesis:     text         -- "period values include length counter bits"
  status:         enum         -- "proposed", "testing", "confirmed", "rejected"
  test_method:    text         -- "check if any period > 2047"
  evidence:       text         -- "P2 period 2717 > 2047 max"
  prompt_cost:    int          -- how many prompts to resolve
```

**Agentic use**: At session start, the agent loads the most recent
session log for this game and resumes from the last known phase.
The hypotheses table prevents re-testing already-confirmed or
already-rejected ideas.

**Critical lesson**: The `outcome` field on decisions is the
feedback loop. When a session makes a decision (e.g., "use NSF
path") and the outcome is later judged "incorrect" (e.g., "NSF
fidelity too low"), future sessions can query this and avoid the
same decision for similar games.

---

## 2. The Prompt/Context Engineering Data Problem

LLM behavior in this project is itself a data problem with
measurable costs and queryable patterns.

### What the Database Should Track About LLM Behavior

```
Table: prompt_patterns
  pattern_id:     serial PK
  name:           text         -- "dump_trace_before_modeling"
  description:    text         -- "extract actual frame data before hypothesizing"
  trigger:        text         -- "agent is about to guess envelope shape"
  template:       text         -- "Before writing code, dump frames N-M for channel X..."
  avg_prompts_saved: float     -- estimated savings when applied

Table: prompt_failures
  id:             serial PK
  session_id:     uuid FK
  failure_type:   enum         -- "wrong_assumption", "skipped_check", "wrong_layer",
                                  "multiple_variables", "no_disassembly", "wrong_song"
  description:    text
  prompts_wasted: int
  prevention:     text FK      -- references prompt_patterns.pattern_id

Table: context_costs
  game_slug:      text FK
  doc_name:       text         -- "CLAUDE.md", "HANDOVER_BATTLETOADS.md"
  token_count:    int
  load_priority:  int          -- 1=always, 2=if working on this game, 3=on demand
  staleness_days: int          -- how many days before this doc may be outdated

Table: vocabulary_bridges
  user_term:      text         -- "fretless bass slide"
  technical_term: text         -- "sweep unit pitch modulation"
  nes_parameter:  text         -- "$4001 sweep enable/period/negate/shift"
  explanation:    text         -- "hardware pitch bend via period register auto-increment"
```

### Prompt Failure Taxonomy (from this project)

| Failure Type | Frequency | Avg Cost | Prevention Pattern |
|-------------|-----------|----------|-------------------|
| Wrong assumption (byte format, song mapping) | 5 | 3.4 prompts | Read disassembly / track listing first |
| Skipped pre-flight check (synth, environment) | 3 | 5.0 prompts | Run session_startup_check.py |
| Debugging wrong layer (data vs synth vs project) | 4 | 3.8 prompts | Isolate layer: play test RPP first |
| Multiple variables changed simultaneously | 3 | 4.0 prompts | One hypothesis, one test, one change |
| Hypothesized without data | 3 | 5.0 prompts | Dump trace frames before modeling |
| Cross-game assumption (same driver = same format) | 2 | 3.0 prompts | Check manifest, read disassembly |

**Total measurable waste**: ~50 prompts across 5 days. At ~2 minutes
per prompt cycle, that's ~100 minutes of wasted compute. A database
that serves the right prevention pattern at the right trigger point
could have saved most of this.

### The Context Loading Strategy

Not all context is equally valuable. The database should serve context
based on what the agent is about to do:

```
Phase: STARTING NEW GAME
  Load: game manifest, track listing, blunders for this developer
  Skip: detailed extraction docs for other games

Phase: DEBUGGING EXTRACTION
  Load: fix_patterns matching symptom, trace comparison data, disassembly
  Skip: project generation docs, synth configuration

Phase: GENERATING OUTPUT
  Load: RPP rules, synth slider spec, pre-delivery checklist
  Skip: ROM analysis docs, driver identification

Phase: VALIDATING FIDELITY
  Load: fidelity thresholds, fix_order protocol, trace data
  Skip: everything else
```

**Key insight**: Context is a scarce resource (token budget). Loading
irrelevant docs dilutes the signal. The database should implement a
relevance ranking that matches the current phase.

---

## 3. Cross-Cutting Ontological Observations

### 3.1 The Known/Unknown Boundary Is the Most Important Datum

Every game manifest should have two explicitly separated lists:
`known_facts` and `hypotheses`. When these are conflated (as they
were in early Battletoads work), the agent treats guesses as facts
and builds on unstable ground.

**Database enforcement**: The `hypotheses` table requires a `test_method`
field. A hypothesis without a test method is not a hypothesis — it's
a wish. Reject it at insert time.

### 3.2 Version Chains Are Non-Negotiable

Every output artifact must have a version number. The database should
enforce monotonic versioning per (game, track, artifact_type) tuple.
Never overwrite — always increment.

```
Table: artifact_versions
  game_slug + track + type:  composite PK
  version:                   int
  path:                      text
  parent_version:            int NULL  -- what this was derived from
  changes_from_parent:       text      -- what changed
  verified:                  bool
```

**Why**: In this project, we overwrote Battletoads MIDI files and
couldn't compare old vs new. The period mask fix (v2→v3) was only
catchable because we output to different directories.

### 3.3 The Fix Order Is a DAG, Not a List

The documented fix order (pitch → timing → volume → timbre) is
actually a dependency graph. Pitch errors make timing measurement
meaningless. Timing errors make volume alignment impossible. This
should be encoded as a DAG:

```
Table: debug_dependencies
  parameter:      text         -- "pitch", "timing", "volume", "timbre"
  depends_on:     text[]       -- e.g., volume depends_on ["pitch", "timing"]
  check_method:   text         -- "trace_compare.py --channel X"
  fix_before:     text[]       -- what can't be fixed until this is right
```

### 3.4 Ground Truth Is Not One Thing

There are at least 4 levels of "truth" in this project, and they
don't always agree:

```
Table: truth_hierarchy
  level:          int          -- 1 = highest
  source:         text         -- "mesen_trace", "nsf_emulation", "midi_cc", "adsr_approx"
  description:    text
  captures:       text[]       -- what parameters this source faithfully represents
  misses:         text[]       -- what parameters this source cannot capture
  when_to_use:    text         -- "always prefer higher level when available"

Table: truth_conflicts
  game_slug:      text FK
  parameter:      text         -- "pulse2_period"
  source_a:       text
  source_b:       text
  source_a_value: text
  source_b_value: text
  resolution:     text         -- "source_a wins (higher truth level)"
  frame:          int          -- where the conflict was observed
```

### 3.5 The Synth Is a Data Consumer, Not Just a Plugin

The JSFX synth's behavior is deterministic given its input data. Its
bugs are data bugs — wrong decoding of CC values, missing handling
of SysEx messages, empty code branches. The database should treat
the synth as a function with a known input/output contract:

```
Table: synth_contracts
  synth:          text         -- "console", "apu2"
  input_type:     text         -- "cc11", "cc12", "sysex_apu_frame", "note_on"
  encoding:       text         -- "vol * 8", "duty * 32", "7-bit safe register pack"
  decoding:       text         -- "floor(cc11 / 8 + 0.5)", "floor(cc12 / 32)"
  lossless:       bool         -- true if encode→decode recovers exact value
  known_bugs:     text[]       -- historical bugs in this contract
```

### 3.6 Every Mesen Parameter Name Is a Potential Encoding Trap

The `$4006_period` field turned out to store `$4007<<8|$4006` (raw
register concatenation including length counter bits), not the 11-bit
period. This cost 272 dropped notes and 2 octaves of pitch error.

```
Table: capture_field_semantics
  parameter_name: text PK      -- "$4006_period"
  actual_meaning: text         -- "raw $4007<<8|$4006, includes length counter"
  expected_meaning: text       -- "11-bit timer period"
  transform:      text         -- "value & 0x7FF"
  discovered_by:  text         -- "period value 2717 exceeds 11-bit max 2047"
  games_affected: text[]       -- all games using Mesen trace path
```

**This table saves future sessions from the exact bug we found today.**

---

## 4. What the Agentic System Should Do Differently

### 4.1 Pre-Flight as Mandatory Query

Before any extraction, the agent should execute:

```sql
SELECT prevention FROM fix_patterns
WHERE trigger IN (
  'before_new_game',
  'before_extraction',
  'before_project_generation'
)
ORDER BY cost_if_skipped DESC;
```

This surfaces the highest-cost prevention steps first.

### 4.2 Route Selection as Data Query

```sql
SELECT fidelity_route FROM games WHERE slug = ?;
-- If 'unknown':
SELECT overall_score FROM fidelity_per_channel
WHERE game_slug = ? AND source_a = 'nsf' AND source_b = 'trace';
-- If score < 0.8: route = 'trace_required'
```

No LLM judgment needed for route selection. It's a threshold check
on measured data.

### 4.3 Hypothesis Management

```sql
-- Before proposing a new hypothesis:
SELECT * FROM session_hypotheses
WHERE game_slug = ? AND status = 'rejected';
-- Don't re-propose rejected hypotheses without new evidence.

-- After testing:
UPDATE session_hypotheses SET status = 'confirmed', evidence = ?
WHERE hypothesis = ?;
```

### 4.4 Context Budget Optimization

```sql
SELECT doc_name, token_count, load_priority
FROM context_costs
WHERE (game_slug = ? OR game_slug IS NULL)
  AND load_priority <= ?  -- 1=always, 2=game-specific, 3=on-demand
ORDER BY load_priority, token_count;
```

Load the minimum context needed for the current phase. Don't burn
tokens on docs about project generation when you're debugging pitch.

---

## 5. Schema Summary

```
-- Static reference
nes_apu_registers, nes_apu_formulas

-- Per-game identity
games, track_listing, game_manifests

-- Per-run extraction state
extraction_runs, extraction_outputs

-- Fidelity measurements
fidelity_comparisons, fidelity_per_channel, fidelity_decisions

-- Bug/fix history
blunders, fix_patterns

-- LLM session management
session_log, session_decisions, session_hypotheses

-- Prompt/context engineering
prompt_patterns, prompt_failures, context_costs, vocabulary_bridges

-- Cross-cutting
truth_hierarchy, truth_conflicts, synth_contracts,
capture_field_semantics, artifact_versions, debug_dependencies
```

Total: ~25 tables. Each serves a specific query pattern that an
agentic system needs to make correct decisions without human
intervention.

---

## 6. The Meta-Lesson

The most expensive bugs in this project were NOT technical. They
were information-routing failures:

- The right rule existed but wasn't consulted (JSFX check)
- The right data existed but wasn't queried (track listing)
- The right hypothesis was rejected prematurely (NSF inadequacy)
- The right fix pattern was known but not applied (one variable at a time)

A database doesn't just store information — it makes information
**findable at the moment it's needed**. The schema above is designed
so that the right prevention pattern surfaces exactly when the agent
is about to make the mistake it prevents.
