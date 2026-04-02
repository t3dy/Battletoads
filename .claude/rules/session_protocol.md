# Session Protocol

## Working Order (mandatory)

1. Environment validity (session_startup_check.py)
2. Source identity and track mapping (DB + track_names)
3. Ground-truth comparison (Mesen vs NSF if both exist)
4. Route choice (nsf / trace / hybrid / apu2_sysex)
5. One-song artifact build
6. Pre-delivery validation (docs/VALIDATION.md Gate F)
7. Batch build (only after one song passes all gates)

Do not skip ahead. Do not change multiple layers at once.

## Fix Order (mandatory)

Always: pitch -> timing -> volume -> timbre.
One hypothesis per test cycle.
Change one thing, rerun comparison.

## Canonical Representation

Dense per-frame APU state is the source of truth.
MIDI is a downstream projection, not the canonical form.
Debug by inspecting frame state, not MIDI events.

## Data Tier Rules

- SQLite (data/pipeline.db): operational truth — games, captures,
  frame states, validation runs, mismatches, decisions
- JSON: human-maintained structured config — track_names, manifests,
  route policies, fidelity reports
- Markdown: reasoning, postmortems, failure analyses, session notes
- Raw files (CSV, ROM, NSF): stay on disk, indexed by DB

## Ground Truth Priority

1. Mesen trace (actual APU hardware state)
2. NSF extraction (6502 emulation — may diverge)
3. MIDI/CC encoding (downstream projection)
4. Synth interpretation (playback approximation)

When Mesen and NSF disagree, Mesen wins.
When MIDI and frame state disagree, frame state wins.

## Delivery Gate

Nothing is "ready to test" unless VALIDATION.md Gate F passes.
Run session_startup_check.py + sync_jsfx.py before every delivery.
