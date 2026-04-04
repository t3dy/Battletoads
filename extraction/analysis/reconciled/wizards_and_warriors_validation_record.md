# Wizards & Warriors — Validation Status

**Last updated:** 2026-04-03
**Parser:** `extraction/drivers/other/wizards_and_warriors_parser.py`
**Simulator:** `extraction/drivers/other/wizards_and_warriors_simulator.py`
**Manifest:** `extraction/manifests/wizards_and_warriors.json`

---

## Ground Truth Sources

| Source | Path | Status |
|--------|------|--------|
| ROM | `extraction/roms/Wizards & Warriors (U) (V1.0) [!].nes` | 129 KB, mapper 7 (AxROM) |
| NSF | `state/ww_ref/Wizards & Warriors [...].nsf` | 16 songs, verified entry points |
| Mesen trace | `extraction/traces/wizards_and_warriors/title_capture.csv` | Song 1 only, 4889 frames (clean ref span 2721-4889) |
| Fan MIDI | N/A | Not available |

---

## Validation Ladder Status

### Per-Channel, Per-Song

| Song | Pulse 1 | Pulse 2 | Triangle | Noise | Best Rung |
|------|---------|---------|----------|-------|-----------|
| 01 - Title | Rung 3 (2169f trace) | Rung 3 (2169f trace) | Rung 3 (2169f trace) | Rung 0 (inactive) | 3 |
| 02 - Forest of Elrond | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 partial (512f, simple gated) | 2 |
| 03 - Tree | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 04 - Ice Cave | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 05 - Low on Energy | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 06 - Initial Registration | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 partial (512f, fixed-period) | 2 |
| 07 - Got an Item | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 08 - Outside Castle | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 09 - Castle Ironspire | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 10 - Entering a Door | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 11 - Map | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 12 - Potion | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 13 - Fire Cavern | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 14 - Inside Big Tree | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 15 - Boss | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 0 (inactive) | 2 |
| 16 - Forest (alt) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 (512f NSF) | Rung 2 partial (512f, richest case) | 2 |

---

## Verified Findings

What has passed execution semantics validation with evidence:

- [x] Song/channel pointer recovery for all 16 songs (deterministic via py65 emulation)
- [x] Title pulse 1: 2169/2169 exact scaled-period match vs Mesen trace (frames 2721-4889)
- [x] Title pulse 2: 2169/2169 exact scaled-period match vs Mesen trace
- [x] Title triangle: 2169/2169 exact period match vs Mesen trace, gate behavior exact
- [x] All 16 melodic channels (48/48): 512/512 period agreement vs NSF emulation
- [x] Period table recovery: 0xEFD9 (table-notes LE), 0xF000 (direct BE)
- [x] Command dispatch at 0xEEEE, 11 commands (0x00-0x0A)
- [x] Loop handling operational (commands 0x05/0x06, validated on title opening rest loop)
- [x] Duration mode switching (command 0x07, inline vs persistent)
- [x] Song-level duration scaling via command 0x09 (Ice Cave 3x, Initial Registration 2x)

---

## Approximate Results

What matches within tolerances but has known edge cases:

- [ ] Title triangle linear-counter values on final 3 release frames (approximate, not exact)
- [ ] Title pulse sounding state: 2168/2169 frames (1 frame final-volume drop — capture boundary)
- [ ] Command 0x09 duration scaling: confirmed for songs 4 and 6, generalization to other songs plausible but not individually verified

---

## Hypotheses (Unvalidated Parser Output)

What the parser produces but has not been compared against ground truth:

- [ ] Full-song melodic behavior beyond 512-frame window (parser extracts full songs but only first 512 frames compared)
- [ ] Command 0x03 semantics (appears in streams but effect not fully characterized)
- [ ] Command 0x08 semantics (rare, effect unknown)
- [ ] Command 0x0A semantics (rare, effect unknown)
- [ ] Duration values for songs not individually ear-checked

---

## Unvalidated Areas

What has not been attempted:

- [ ] External Mesen trace captures for songs 2-16 (only title captured)
- [ ] Full-song duration validation beyond 512-frame window for any song
- [ ] Noise channel full byte-to-register mapping generalization
- [ ] Complete command semantics for commands 0x03, 0x08, 0x0A
- [ ] Ear-check of all 16 songs against game audio (partial at best)

---

## Artifact Trust Levels

| Artifact | Path | Trust Level | Scope |
|----------|------|-------------|-------|
| MIDI (full game, 16 songs) | `output/Wizards_and_Warriors/midi/` | **Hypothesis output** | Rung 2 melodic, practical working artifacts |
| MIDI (trace title) | `output/Wizards_and_Warriors_trace/midi/` | **Trusted (title melodic)** | Rung 3, title pulse+tri 2169 frames |
| REAPER (full game, 16 songs) | `output/Wizards_and_Warriors/reaper/` | **Hypothesis output** | Working drafts, not semantics-validated |
| REAPER (trace title) | `output/Wizards_and_Warriors_trace/reaper/` | **Trusted (title melodic)** | Rung 3 scope |
| WAV renders | `output/Wizards_and_Warriors/wav/` | **Preview** | Unvalidated placeholders |

**Practical use:** All 16 full-game MIDI/RPP files are usable for listening,
arrangement, and DAW work. They are strong working artifacts based on Rung 2
internal validation. They are NOT claimable as fully validated or archival-quality.

---

## Noise Channel Notes

Noise is a separate semantic domain — documented here, not mixed with melodic.

- **Encoding:** noise bytes use the same command dispatch but different period/volume semantics
- **Active songs:** 3 of 16 (songs 2, 6, 16) have active noise events
- **Inactive songs:** 11 songs emit sentinel stream 0xF1E0 (inactive), 2 are muted-but-primed
- **Song 2 (Forest of Elrond):** Simple gated percussion, volume toggles only. Exact NSF register match 512 frames.
- **Song 6 (Initial Registration):** Fixed-period percussion with instrument variation. Exact NSF match 512 frames.
- **Song 16 (Forest alt):** Richest active case, partial raw-byte-to-register mappings exist. Exact NSF match 512 frames.
- **Validation state:** Rung 2 partial for active songs (NSF match on 512-frame window). Full generalization pending.
- **Known gaps:** No Mesen trace capture for noise-active songs. Byte-to-register mapping not generalized.

---

## Next Validation Targets

Priority order for further validation work:

1. External Mesen trace captures for songs 2, 4, 6 (noise-active and duration-scaled songs)
2. Full-song melodic validation beyond 512-frame window (at least one representative song)
3. Noise channel byte-to-register generalization from song 16 partial mappings
4. Command 0x03/0x08/0x0A semantics investigation
5. Ear-check of at least songs 1-5 against game audio for Rung 4 promotion

---

## Driver-Specific Notes

- **Driver family:** Custom W&W driver (Rare, not Konami or Battletoads variant)
- **Command set:** 11 commands (0x00-0x0A) via dispatch table at 0xEEEE
- **Tempo model:** Counter-based playback, per-frame duration countdown
- **Duration model:** Dual-mode — inline (negative $07E0,X) and persistent (non-negative)
- **Duration scaling:** Command 0x09 provides song-level multiplier (Ice Cave 3x, Init Reg 2x)
- **Modulation:** Not observed in current analysis (no arpeggio/vibrato commands found)
- **Envelope:** Command 0x03 present but not fully characterized
- **Mixed note encoding:** Table-notes (bit 7 set, period from 0xEFD9) and direct-notes (0x10-0x7F, period from 0xF000 + volume nibble)
