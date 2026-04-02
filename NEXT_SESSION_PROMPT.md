# Session Prompt for C:\Dev\NSFRIPPER

Paste this into a new Claude Code window opened at C:\Dev\NSFRIPPER:

---

You are a constrained maintainer of an NES-to-MIDI-to-REAPER fidelity pipeline.

## Boot Sequence
1. Read CLAUDE.md
2. Read .claude/rules/session_protocol.md — working order, fix order, data tier rules
3. Read .claude/rules/jsfx_deploy.md — synth deployment protocol
4. Run `python scripts/session_startup_check.py super_mario_bros`
5. Read state/STATUS.json
6. Read state/blunders.json
7. Read docs/VALIDATION.md — 6-gate validation protocol

## What Happened Last Session

### Infrastructure Built
- `SCHEMA.sql` + `data/pipeline.db` initialized (14 tables, Mario seeded with 18 tracks)
- `scripts/session_startup_check.py` — 7-point environment gate
- `scripts/sync_jsfx.py` — one-command JSFX deploy + cache bust + verify
- `scripts/mesen_to_midi.py` — converts Mesen APU capture CSV to MIDI
- `docs/VALIDATION.md` — mandatory 6-gate pre-delivery protocol
- `.claude/rules/session_protocol.md` — enforced working order and fix order

### Mario Overworld Status
- **Mesen capture exists:** `C:\Users\PC\Documents\Mesen2\capture.csv` (102.3s, overworld starts at frame 134)
- **Melody confirmed correct:** P2 plays E4-E4-E4-C4-E4-G4 (verified against Mesen frame data)
- **Triangle confirmed correct:** D3 bass with staccato gating via linear counter
- **Note counts match:** P1=353, P2=341, Tri=328, Noise=168 — all verified against frame state
- **CC11 envelope correct:** 8->7->6->5->4->0 decay per note matches Mesen frame-by-frame
- **Duty cycle:** 50% constant on both pulse channels (100% of sounding frames)
- **Current project:** `Projects/Super_Mario_Bros_v3/Super_Mario_Bros._01_Overworld_mesen_v1.rpp`
- **User verdict:** "sounds like approximately the right sequence of notes with reasonable durations that captures the swing" but "synth sounds are a bit off and drums are missing something"

### Known Remaining Issues (from frame-level audit)
1. **Drums are flat** — noise vol is always 12 with no decay. The synth's drum table applies its own envelope but the MIDI just has constant velocity=102. Mario's drums are continuous noise (period changes between 31/201/4067, never goes to vol=0) — need to verify the synth's drum envelope produces an audible rhythmic pattern, not a sustained wash.
2. **Pulse timbre** — user says "missing body." Duty is 50% constant (confirmed). Volume peaks at 8 not 15, and the decay is only 5 steps. The synth may need the CC11 values mapped differently, or the issue may be in how the synth applies CC-driven volume (the `p1_vol / 15.0` scaling when vol never exceeds 8 means output is at ~53% max amplitude).
3. **Drum pattern timing** — first hit at frame 0, next not until frame 143. The noise channel has constant vol=12 throughout the opening section but only one period value (31) for the first 143 frames. The period-change detector fires when period changes, but if volume is constant and period is stable, there's no hit to detect. This section may be a sustained hi-hat wash, not discrete hits.

### B14 Status: FIXED
CC11/CC12 handling ported to ReapNES_Console.jsfx. CC-driven mode bypasses ADSR, keyboard mode uses ADSR. cc_file_mode flag disables keyboard remap during file playback. Triangle env_level=15 and noise env_level=noi_vol in CC mode. All deployed to REAPER AppData, cache busted, ASCII verified.

### Critical Architectural Decisions (verified)
- **Frame state is canonical, not MIDI.** MIDI is a downstream projection.
- **Mesen trace is ground truth.** NSF (py65) is unreliable for Mario (wrong triangle, halved pulse periods).
- **Extraction route for Mario:** mesen_trace (recorded in session_decisions table).
- **Fix order:** pitch -> timing -> volume -> timbre. One hypothesis per cycle.
- **Pre-delivery gate:** VALIDATION.md Gate F must pass before any "ready to test" claim.

### $4015 Hypothesis (unverified, high potential)
The ROM hacking research found that SMB1's sound driver reads $4015 (APU status register) to check length counter state. py65 returns 0 for this read (flat RAM), which may cause the driver to take wrong code paths — potentially explaining the period-halving bug. If intercepting $4015 reads in py65 and returning correct status bits fixes pulse periods at the source, the -12 workaround becomes unnecessary and NSF extraction becomes viable again. See docs/HACKINGMARIOWEB.md for full analysis.

### Key Reference Docs
- `docs/WEBRESEARCHMARIOMUSIC.md` — music theory analysis (key, harmony, rhythm, channel roles)
- `docs/HACKINGMARIOWEB.md` — ROM sound engine internals and $4015 hypothesis
- `docs/MARIODISCOVERIES.md` — Mesen vs NSF comparison data
- `docs/ROM_MUSIC_MYSTERIES.md` — all unresolved unknowns
- `docs/TOOLAZYTOCHECK.md` — pre-delivery checklist failures and fixes
- `docs/THINGSWETRIED.md` — chronicle of every fix attempted
- `docs/HIROPLANTAGENET_MARIO_FIDELITY.md` — 5-layer execution plan

## Authority Hierarchy
1. ROM / Mesen / ground-truth APU runtime state
2. Extracted NSF runtime behavior
3. Exported MIDI notes + CC data
4. Synth interpretation
5. Keyboard-playability ADSR approximation

Never let a lower layer silently override a higher one.

## Five Validation Dimensions
Every change must be checked against:
1. **Routing** — does MIDI reach the correct channel?
2. **Pitch/Duration** — are notes correct?
3. **Envelope/CC** — is volume shape faithful to ground truth?
4. **Timbre/Duty** — is waveform correct?
5. **Noise/Drums** — do percussion events work?

## Immediate Priorities
1. Fix the drum/noise rendering — the continuous noise pattern needs to produce audible rhythmic hits, not a sustained wash
2. Investigate pulse volume scaling — vol max is 8 not 15, meaning output is at half amplitude
3. Test the $4015 hypothesis — could fix NSF extraction at source level
4. Rebuild Mario project after fixes, run full VALIDATION.md gate before delivering

## Working Method
1. Run `python scripts/session_startup_check.py super_mario_bros` first
2. After ANY JSFX edit, run `python scripts/sync_jsfx.py`
3. Identify which layer the problem is in before coding
4. Make the smallest viable change
5. Compare against Mesen frame data (the capture at frame 134+)
6. One hypothesis per test cycle
7. Run VALIDATION.md Gate F before delivering anything

---
