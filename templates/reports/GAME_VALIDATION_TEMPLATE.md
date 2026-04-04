# [Game Name] — Validation Status

**Last updated:** [date]
**Parser:** [path to parser file]
**Simulator:** [path to simulator file]
**Manifest:** [path to manifest JSON]

---

## Ground Truth Sources

| Source | Path | Status |
|--------|------|--------|
| ROM | | |
| NSF | | |
| Mesen trace | | [which songs captured, frame counts] |
| Fan MIDI | | [if available, used for pitch cross-check only] |

---

## Validation Ladder Status

### Per-Channel, Per-Song

| Song | Pulse 1 | Pulse 2 | Triangle | Noise | Rung |
|------|---------|---------|----------|-------|------|
| 01 - [name] | | | | | |
| 02 - [name] | | | | | |
| ... | | | | | |

Rung values: 0=unexamined, 1=parser-aligned, 2=internal-semantics,
3=external-trace, 4=trusted-projection, 5=full-game-trusted

For each cell, note the validation scope:
- Frame range validated (e.g., "512 frames" or "full song")
- Match percentage if measured (e.g., "512/512 period match")
- Known limitations or edge cases

---

## Verified Findings

What has passed execution semantics validation with evidence:

- [ ] [Finding with frame range, channel, comparison metric]
- [ ] ...

---

## Approximate Results

What matches within tolerances but has known edge cases:

- [ ] [Result with known limitation]
- [ ] ...

---

## Hypotheses (Unvalidated Parser Output)

What the parser produces but has not been compared against ground truth:

- [ ] [Hypothesis with rationale for why it's plausible]
- [ ] ...

---

## Unvalidated Areas

What has not been attempted:

- [ ] [Area and what would be needed to validate it]
- [ ] ...

---

## Artifact Trust Levels

| Artifact | Path | Trust Level | Scope |
|----------|------|-------------|-------|
| MIDI (full game) | | [hypothesis/trusted] | [validated scope] |
| MIDI (trace) | | [hypothesis/trusted] | [validated scope] |
| REAPER projects | | [working draft/production] | [validated scope] |
| WAV renders | | [preview/reference] | [validated scope] |

---

## Noise Channel Notes

Noise is a separate semantic domain. Document separately:

- Encoding scheme: [how noise bytes map to registers]
- Active songs: [which songs have noise events]
- Validation state: [structural only / partial semantics / validated]
- Known gaps: [what remains unmodeled]

---

## Next Validation Targets

Priority order for further validation work:

1. [Target with rationale]
2. [Target with rationale]
3. ...

---

## Driver-Specific Notes

- Command set: [reference to manifest or command doc]
- Tempo model: [accumulator type, known values]
- Duration model: [inline/persistent, known quirks]
- Modulation: [arpeggio, vibrato, sweep — what is modeled]
- Envelope: [model type, what is validated]
