# ANXIETY: Getting Married to Derived Data

## The Concern

When working with trace-derived note sequences, there is a persistent failure mode:
the system (and the operator) can become "married to" a note sequence produced by
one interpretation layer, continuing to polish and adjust it even when the underlying
interpretation is fundamentally wrong.

This happened during the Battletoads Level 1 extraction across v3-v8:

1. The trace captures raw APU period values (669, 1001, 235)
2. These were mapped to notes (E3, A2, A#4) via period table lookup
3. Multiple sessions were spent adjusting sweep hold, stability filtering,
   and start offsets to make these notes sound right
4. They never sounded right because **the notes themselves were wrong**
5. The ROM data and fan MIDI both confirm the intended notes are E2, D2, G2
6. The driver applies a transposition register ($0354,X) that shifts note
   indices before period table lookup -- the trace captures the SHIFTED result,
   not the intended note

## The Root Cause

The trace captures **output** (what the APU register contains after the driver
processes the note). The MIDI should be generated from **intent** (what note
the driver was told to play by the ROM song data).

The gap between output and intent is the transposition register. CMD 0x12
sets it absolutely, CMD 0x13 adds to it relatively. The driver does:

```
note_byte = song_data[ptr]        ; e.g., $85 = E2 (table index 4)
transposition = mem[$0354 + X]    ; e.g., 12
period_index = note_byte + transposition  ; 4 + 12 = 16 = E3
period = period_table[period_index]       ; 678
write APU register with period            ; Mesen captures 678
```

The trace sees 678. We mapped it to E3. But the song data says E2. The
transposition is invisible in the trace.

## Anti-Regression Rules

1. **Never generate MIDI from trace periods alone.** The trace period is the
   FINAL output after all driver transformations. It is not the musical intent.

2. **ROM song data is the authority for note values.** Parse the actual note
   bytes from the ROM, apply the known command semantics, and generate MIDI
   from that.

3. **Trace data is authority for TIMING and ENVELOPE only.** CC11 volume
   envelopes, note durations (attack-to-attack gaps), and drum hits are
   reliable from the trace because they don't get transposed.

4. **When a derived sequence doesn't match a known reference, suspect the
   derivation, not the reference.** The fan MIDI matched the NSF extraction
   matched the ROM data. The trace was the outlier. Three sources agreeing
   outweighs one.

5. **Don't polish the wrong thing.** Sweep hold, stability filtering, and
   period table snapping are all correct techniques -- but they're refinements
   to an incorrect base. Applying them to transposed periods produces
   precisely-wrong notes.

## What We Now Know About the Rare Driver

- **Period table**: 60 entries at ROM $8E22, standard NTSC, C2-B6
- **Note encoding**: byte >= $81 means note; index = byte - $81 + transposition
- **Transposition register**: $0354,X (per-channel, set by CMD 0x12, modified by CMD 0x13)
- **Rest**: byte $80
- **Commands**: byte < $80, dispatched through jump table at $8B7B
- **Key commands found**:
  - CMD 0x12 nn: set transposition = nn (absolute)
  - CMD 0x13 nn: transposition += nn (relative/signed)
  - CMD 0x04: set data pointer (subroutine call?)
  - CMD 0x17 nn: set value at $0364,X
  - CMD 0x1E: loop/jump construct
  - CMD 0x03: set envelope/volume parameters
  - CMD 0x00: channel off

## The Correct Pipeline for Battletoads

```
ROM song data ($A2CF for P2)
  |
  v
Parse command stream (CMD bytes < $80 with parameters)
Track transposition register (CMD 0x12, 0x13)
Extract note bytes (>= $81)
  |
  v
Apply transposition: note_index = (byte - $81) + current_transposition
Look up period_table[note_index]
  |
  v
Convert to MIDI note (standard period-to-MIDI math)
  |
  v
Combine with trace-derived timing and CC11 envelopes
  |
  v
Output MIDI
```

## Session Discipline

Before generating ANY MIDI from a new game:
1. Identify the music driver (done: Rare custom engine)
2. Find the period table (done: $8E22)
3. Find the note encoding (done: $81+N with transposition)
4. Find the transposition mechanism (done: $0354, CMD 0x12/0x13)
5. Parse a test phrase from ROM and verify against known-good reference
6. ONLY THEN generate MIDI

Do not skip to step 6 because "the trace is ground truth." The trace is
ground truth for register state, not for musical intent.
