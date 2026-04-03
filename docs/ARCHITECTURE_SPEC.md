# Pipeline Architecture Specification

This document is the authoritative architectural directive for the NES music
extraction pipeline. It was written by the project owner and must be followed
exactly. All system files, scripts, and session behavior must conform to this
specification.

---

## PRIMARY OBJECTIVE

Eliminate the gap between:

* declared system (docs, rules, invariants, debugging advice)
* actual execution (single-route, CC-default, no validation, rigid assumptions)

Replace it with:

* a deterministic, enforced pipeline that always:

  1. generates all viable representations
  2. validates them automatically
  3. compares them
  4. blocks delivery if fidelity routes fail
  5. preserves enough evidence to diagnose why a route failed
  6. supports game-specific and engine-specific adaptation without collapsing into ad hoc improvisation

## CORE PRINCIPLES

Rules must become code.

Anything currently expressed as:

* "always do X"
* "validate Y"
* "never deliver unless Z"
* "try another interpretation if this route breaks"
* "different ROMs may need different handling"

must be implemented as executable logic, structured state, or explicit extension points in the pipeline.

No reliance on memory, prompts, or manual discipline.

Also: the system must distinguish between:

* canonical observed data
* inferred musical interpretation
* downstream DAW/playback projection

Those are not the same thing and must never be conflated.

## ARCHITECTURAL REQUIREMENT: SUPPORT MULTIPLE MUSIC ENGINES / ENCODING PATTERNS

Assume from the start that ROMs differ in how they encode and schedule music.

The system must support:

* NSF-derived event extraction
* Mesen APU capture / trace-derived frame-state extraction
* hybrid routes that reconcile both
* game-specific engine adapters
* fallback diagnostic routes when neither NSF nor trace alone is sufficient

Do not hard-code one universal decoding model.

Instead, build a framework that can:

* classify or tag a target game/segment by engine traits
* attach route assumptions explicitly
* record which assumptions succeeded or failed
* allow per-engine or per-game heuristics without poisoning the canonical model

## PHASE 1 -- BUILD THE ORCHESTRATION KERNEL

Create:

```text
scripts/kitchen_sink.py
```

This is the single entry point for all pipeline runs.

### Required behavior

When executed, it must:

1. Run preflight checks

   * verify required scripts exist
   * verify JSFX files exist
   * verify output directory
   * load config for NES constraints
   * load game/engine profile if available

2. Ingest sources

   * parse trace/capture into canonical frame state
   * parse NSF if provided
   * normalize into structured data models
   * preserve provenance for every derived artifact

3. Generate all viable routes

   * NSF -> CC MIDI -> Console RPP
   * Trace -> CC MIDI -> Console RPP
   * Trace -> CC+SysEx MIDI -> APU2 RPP (primary fidelity route)
   * Trace -> CC+SysEx MIDI -> Studio RPP (stub if not implemented)
   * Hybrid / diagnostic routes when configured or automatically triggered

4. Run all validations automatically

   * implement as code, not comments
   * collect structured results
   * include route-assumption validation, not just file-structure validation

5. Run cross-route comparison

   * note alignment
   * channel activity
   * parameter retention
   * route divergence
   * confidence and failure reasons

6. Generate report artifacts

   * run_manifest.json
   * validation_results.json
   * comparison_results.json
   * route_assumptions.json
   * report.md

7. Enforce delivery gate

   * if no fidelity route passes, exit with error
   * do not silently fall back to CC output
   * if a route fails because assumptions were wrong, surface that explicitly

## PHASE 2 -- DEFINE CANONICAL DATA MODEL

Create:

```text
scripts/lib/models.py
```

Define structured types such as:

* Run
* SourceAsset
* Segment
* GameProfile
* EngineProfile
* RouteAssumption
* FrameState
* ChannelState
* MusicalEvent
* RouteBuild
* Artifact
* ValidationResult
* ComparisonResult
* LearningRecord

### Critical rule

FrameState is the single source of truth for observed hardware behavior.

All routes must derive from it or explicitly document why they are instead using NSF/event-layer data.

Never debug MIDI before confirming FrameState.

Also: inferred note objects, durations, articulations, and keyboard-playable abstractions are downstream interpretations, not source truth.

## PHASE 3 -- INTRODUCE ENGINE / GAME PROFILE SUPPORT

Create:

```text
scripts/lib/profiles/
```

Support configuration objects or modules for:

* known game-specific quirks
* engine-specific decoding assumptions
* timing expectations
* arpeggio conventions
* sweep usage patterns
* noise channel interpretation rules
* live-play compromises for keyboard mode
* known mismatch patterns between rip fidelity and playable synth abstractions

The system must work even when no profile exists, but when a profile does exist it should guide:

* route selection
* validation thresholds
* comparison expectations
* debugging hints

Profiles must be advisory inputs to route logic, not replacements for raw evidence.

## PHASE 4 -- ROUTE BUILDERS

Create modular route builders:

```text
scripts/lib/route_builders/
  nsf_cc_console.py
  trace_cc_console.py
  trace_sysex_apu2.py
  trace_sysex_studio.py
  hybrid_trace_nsf.py
  diagnostic_parameter_dump.py
```

Each builder must:

* accept FrameState and/or NSF/event-layer equivalents
* declare assumptions explicitly
* return a structured RouteBuild object
* emit artifacts such as MIDI, RPP, dumps, route summaries
* never return only print statements or narrative prose

### Required classification

Each route must declare:

* route_id
* route_class: baseline | fidelity | target | diagnostic | hybrid
* source_basis: trace | nsf | hybrid
* intended_use: playback | analysis | live_input | debugging
* assumptions: explicit list

Fidelity routes must include:

* trace_sysex_apu2
* trace_sysex_studio (even if stub)

Diagnostic routes must exist for cases where musical interpretation is uncertain but raw parameter replay is still possible.

## PHASE 5 -- VALIDATION SYSTEM (MANDATORY)

Create:

```text
scripts/lib/validators/
```

Implement validators as structured functions.

### Required validator groups

1. Frame / source integrity
2. MIDI integrity
3. SysEx integrity
4. RPP structure
5. Platform constraints
6. Assumption validity
7. Route suitability by use-case

### Examples that must be implemented

* note range within NES limits
* no illegal period values
* CC round-trip integrity
* SysEx message count correct
* RPP contains FXCHAIN and HASDATA
* channel activity non-zero
* no invalid 1-frame artifacts (flag, not always fail)
* route assumptions consistent with observed data
* live-input route exposes usable playable controls
* playback route preserves enough fidelity for ear-checking

### Enforcement rule

Inside kitchen_sink.py:

```python
if no_fidelity_route_passes_blocking_checks:
    exit(1)
```

No exceptions.

Also:

* a route may pass file-structure validation and still fail interpretation validation
* the report must distinguish those cases

## PHASE 6 -- CROSS-ROUTE COMPARISON

Create:

```text
scripts/lib/compare.py
```

Must compute:

* note alignment across routes
* channel activity percentages
* pitch divergence
* duration divergence
* parameter coverage matrix
* what each route loses vs retains
* which assumptions changed the output
* which route is best for fidelity, editability, and live keyboard play

The system must not assume that the best route for faithful playback is the best route for live MIDI keyboard input.

Those are separate targets and should be scored separately.

## PHASE 7 -- LEARNING FROM PAST ATTEMPTS

Create:

```text
state/route_learnings.json
state/blunders.json
state/game_profiles/
```

and supporting code to read/write them.

The pipeline should record:

* which routes were attempted
* which validators failed
* what assumptions were active
* what was learned about a given game/engine
* recurring failure patterns
* known bad transformations to avoid repeating

This is not free-form memory. It is structured operational memory.

Examples:

* "for Game X, NSF note extraction misses vibrato encoded as rapid period changes"
* "for Game Y, trace-derived 1-frame notes are often intentional arpeggio cycling, do not blanket-filter"
* "for live keyboard mode, Console route is acceptable but must expose timbre controls and not masquerade as archival playback fidelity"

Do not let this become a garbage heap of prose. Keep it structured and queryable.

## PHASE 8 -- SEPARATE USE-CASES EXPLICITLY

The pipeline currently mixes at least three goals:

1. archival / analytical fidelity to ROM behavior
2. editable REAPER project generation
3. live MIDI keyboard play through a synth plugin

These are related but not identical.

The architecture must explicitly model them.

For every route, declare suitability for:

* archival playback fidelity
* analytical inspection
* DAW editing
* live input performance

Do not pretend one projection solves every use-case equally well.

The system should prefer:

* SysEx / register replay for fidelity and debugging
* CC / simplified control abstractions for live keyboard play and editability
* hybrid or unified synth approaches for bridging the two

## PHASE 9 -- CHANGE DEFAULT BEHAVIOR

Modify existing scripts:

### generate_project.py

* remove default CC-only output
* or mark as deprecated
* or make it call kitchen_sink.py internally

### trace_to_midi.py

* ensure SysEx path is first-class
* ensure it returns structured data, not just files
* ensure it can emit diagnostic dumps and route summaries

### any existing single-path project builders

* either retire them
* or reframe them as subroutines invoked by kitchen_sink.py

## PHASE 10 -- DEBUGGING PROTOCOL ENFORCEMENT

Hard-code this order into docs, comments, and report output:

1. check SysEx playback first
2. if SysEx sounds correct, the problem is in CC encoding / projection / live-input abstraction
3. if SysEx sounds wrong, the problem is in source extraction, route assumptions, or synth interpretation
4. never debug MIDI first when the underlying frame-state or register replay has not been confirmed

Also:

* automatically generate frame dump artifacts
* attach them to each route build
* emit route assumption summaries for failed routes
* surface "what changed" between route outputs

## PHASE 11 -- SYNTH ARCHITECTURE (PREP FOR UNIFIED SYSTEM)

Prepare for:

ReapNES Studio (single JSFX or unified plugin architecture)

Do not implement fully yet, but ensure the pipeline supports:

* SysEx/register replay as the fidelity path
* CC/control abstraction as the playable/editable path
* eventual unified UI that lets the user inspect and perform sounds
* live MIDI keyboard behavior that does not collapse all timbres into a generic fallback pulse sound

The architecture must acknowledge that "faithful playback from ripped data" and "responsive live keyboard instrument behavior" are partially different problems.

## PHASE 12 -- SYSTEM FILE UPDATES

Update:

### CLAUDE.md

Add kitchen_sink.py as the primary command and declare that all artifact generation goes through it.

### session_protocol.md

Replace "build one artifact" with "run kitchen_sink.py, inspect report, test fidelity route first, then investigate route-specific problems."

### VALIDATION.md

Convert it into a validator reference and note that enforcement now lives in code.

### any init / plan / environment files

Ensure they instruct future sessions to:

* treat frame-state as canonical
* generate multiple routes
* preserve provenance
* record learnings
* distinguish fidelity vs editability vs live-play goals
* avoid assuming all ROMs encode music the same way

## HARD CONSTRAINTS

* no single-route execution paths
* no delivery without validation
* no CC-default behavior masquerading as best output
* no silent fallback to inferior outputs
* no debugging at MIDI layer before SysEx check
* no assumption that one music engine model fits all ROMs
* no collapse of archival fidelity and live keyboard usability into one unexamined output

## SUCCESS CRITERIA

A run is successful only if:

* multiple routes are generated
* at least one fidelity route passes all blocking validations
* report artifacts are produced
* route assumptions are made explicit
* the system records what it learned
* SysEx/APU2 route is the default listening target for fidelity evaluation
* live-input/playable routes are evaluated as a distinct target, not confused with archival fidelity

## IMPLEMENTATION STRATEGY

1. build a minimal working kitchen_sink.py
2. define the canonical models and route interfaces
3. stub route builders where necessary
4. wire validation and blocking early
5. add engine/game profile support
6. add structured learning/state capture
7. iterate until one command produces full comparison, validated outputs, and explicit route recommendations for both fidelity playback and live-play use

## FINAL NOTE

The system already contains many of the right ideas:

* SysEx fidelity path
* validation gates
* frame-state ontology
* debugging discipline
* awareness that downstream MIDI abstractions can distort source behavior

Your task is to force the system to use those ideas while also recognizing that different ROMs and music engines require adaptable interpretation layers.

Do not add vague conceptual complexity.

Build a flexible but disciplined framework that:

* preserves canonical evidence
* tries multiple interpretations
* learns from failures
* separates fidelity from playability
* turns system rules into enforced execution.

---

## NON-NEGOTIABLE DIRECTIVE -- DO NOT SKIP THE FRAME IR STEP

Do not attempt to translate raw Mesen/APU register writes directly into final musical notes or DAW-ready playback without first passing through a **frame IR (intermediate representation)** layer.

This is a hard architectural rule.

### Why this exists

The CV1/Contra work established the proven pattern:

**Trace -> Frame IR -> MIDI/CC projection -> Console synth**

Those rips worked because the frame IR interpreted hardware behavior into stable musical events before MIDI encoding.

Raw register replay is not equivalent to musical interpretation, and it is not automatically equivalent to what a software synth should do. Directly splitting notes on every period change creates false musical structure, especially in cases like:

* sweep effects
* vibrato-like oscillation
* rapid period modulation
* arpeggio cycling
* transient register churn
* triangle channel state changes that do not map 1:1 to naive note starts

### Architectural rule

Every trace-based route must explicitly pass through these layers:

1. **Observed hardware state**

   * raw register writes
   * per-frame channel state
   * counters, flags, period values, volume, sweep, linear counter, etc.

2. **Frame IR**

   * interpreted per-frame musical state
   * stable event candidates
   * channel activity classification
   * note continuity vs modulation
   * inferred note boundaries
   * explicit uncertainty markers where interpretation is ambiguous

3. **Projection layer**

   * MIDI notes
   * CC11/CC12 or other control data
   * SysEx only when justified for specific fidelity/debugging purposes
   * REAPER project generation
   * live-play abstractions

Do not collapse layers 1 and 3 together.

### Mandatory infrastructure changes

Bake this into the infrastructure so it cannot be casually skipped:

* Add a system-level rule: **No trace -> MIDI conversion without Frame IR generation**
* Require `kitchen_sink.py` and any trace conversion path to emit a Frame IR artifact first
* Require validation to fail if a trace-based route bypasses Frame IR
* Update docs to state that MIDI notes are derived from interpreted frame events, not raw period changes
* Treat "new note on every period change" as a known anti-pattern unless explicitly justified by the engine/profile
* Store Frame IR artifacts as first-class outputs for debugging and comparison

### Required artifact

For every trace-based build, produce something like:

```text
output/<game>/<segment>/frame_ir.json
```

or equivalent structured artifact containing:

* frame index
* channel state
* interpreted note/event state
* continuity decisions
* modulation annotations
* uncertainty flags
* provenance back to source trace data

### Debugging rule

If the output sounds wrong:

1. inspect raw frame state
2. inspect Frame IR decisions
3. inspect MIDI projection
4. inspect synth/project behavior

Do not jump from raw trace straight to MIDI debugging.

### Battletoads-specific implication

For Battletoads, rapid period changes must not automatically become rapid note retriggers. The pipeline must first determine whether observed changes represent:

* a single sustained musical event with modulation
* a true sequence of discrete notes
* engine-driven sweep behavior
* arpeggio cycling
* malformed interpretation

This decision belongs in Frame IR, not in the final MIDI builder.

### Enforcement language for docs

> Frame IR is mandatory for all trace-derived musical exports. Raw register data is canonical observational evidence, but it is not itself a musical event model. No trace-derived MIDI or REAPER artifact should be considered valid unless it is produced from an explicit Frame IR stage.

### Specific anti-regression policy

Any future script or refactor that:

* converts trace directly to note events
* opens a new MIDI note on every raw period change
* bypasses Frame IR because it is "faster"
* treats raw hardware churn as already-musical structure

should be treated as a regression against the proven CV1/Contra approach.

Compact version for CLAUDE.md or session_protocol.md:

```text
NON-NEGOTIABLE: Never skip Frame IR.
Trace-derived exports must follow:
Trace -> canonical frame state -> Frame IR -> MIDI/CC/SysEx/project projection.
Raw register changes are not yet musical events.
Direct period-change-to-note conversion is a known failure mode.
Validation should fail if a trace route bypasses Frame IR.
```

Implementation task:

```text
Create or restore a first-class Frame IR layer for trace-based routes and refactor
trace_to_midi.py so MIDI note generation consumes Frame IR decisions rather than
opening notes directly on raw period changes.
```

---

## INFRASTRUCTURE REBAKE DIRECTIVE -- TEMPORAL INTERPRETATION LAYER AS FIRST-CLASS SYSTEM BOUNDARY

Rework the infrastructure so that temporal interpretation is treated as a formal boundary in the pipeline, not an incidental heuristic hidden inside a conversion script.

### What must change

The codebase must explicitly separate:

* observational state capture
* temporal interpretation
* export/render generation

This boundary must be visible in:

* directory structure
* script responsibilities
* artifact outputs
* validation rules
* session docs
* route orchestration

### Required infrastructure outcomes

1. Introduce a dedicated interpretation-stage artifact for every trace-backed run.

   * It must be saved to disk
   * It must be inspectable independently of MIDI
   * It must support debugging, comparison, and regression testing

2. Refactor script boundaries so that export builders consume interpreted event/state objects rather than raw frame deltas.

   * Any script that currently turns per-frame changes directly into note boundaries must be reworked
   * Builders should accept structured interpreted spans/events, not infer them ad hoc during export

3. Add infrastructure-level anti-regression checks.

   * Detect suspicious note explosion
   * Detect excessive retrigger density
   * Detect direct raw-change-to-note logic
   * Fail validation when export logic bypasses the interpretation layer

4. Encode temporal reasoning as configurable policy.

   * Thresholds, continuity rules, modulation handling, and channel-specific behaviors must live in a dedicated policy/config layer
   * These policies must be testable and overridable per game/engine profile
   * Do not bury them as magic numbers inside a monolithic build function

5. Make interpretation outputs comparable across versions.

   * Emit versioned artifacts
   * Support A/B comparison of interpretation strategies
   * Preserve provenance so we know which logic produced which musical segmentation

### Required doc and system-file revisions

Update the system so it states clearly that:

* export generation is downstream of interpreted temporal structure
* playback artifacts are projections, not ground truth
* debugging should focus on segmentation and continuity decisions before render-layer details
* improvement work should target the interpretation boundary whenever note structure sounds implausible

### Required implementation tasks

* Create a dedicated module for temporal interpretation logic
* Define stable interfaces for interpreted spans/events
* Move heuristics out of export code into reusable interpretation policies
* Add validation hooks that inspect interpreted output before project generation
* Add regression fixtures using known difficult passages so future edits cannot silently reintroduce fragmentation

### Enforcement statement

No trace-backed production artifact should be considered valid unless it can be traced through:

1. captured state
2. explicit temporal interpretation output
3. downstream projection/render

If the pipeline cannot show those three stages distinctly, the run should be treated as architecturally incomplete.
