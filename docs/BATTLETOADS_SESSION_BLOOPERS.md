# Battletoads Session Bloopers: A Comedy of Errors

## Act I: "The Sweep Hold Triumph That Fixed Nothing"

**The Scene:** Claude discovers that period 231 snaps to B4 instead of A#4 due
to sweep vibrato. Spends considerable effort building an elegant "sweep hold"
mechanism with tolerance windows.

**The Punchline:** The A#4 note was never supposed to BE A#4. It should have
been G2. We built a precision instrument to hold the wrong note steady.

**Lesson:** Don't polish a turd. If the base note is wrong, stabilizing it
just produces a very stable wrong note.

---

## Act II: "The SFX Contamination Theory That Wasn't"

**The Scene:** Fan MIDI says E2-D2-G2. Trace says E3-A2-A#4. Claude theorizes
that sound effects during gameplay are overwriting the pulse channel registers,
contaminating the music data.

**The User:** Records a clean capture with zero SFX.

**The Result:** Exact same notes. E3-A2-A#4. No contamination. The hardware
really plays these periods.

**The Punchline:** Claude spent a full analysis cycle on a theory that was
disproved by a 6-minute recording.

**Lesson:** When in doubt, get more data. Don't theorize when you can test.

---

## Act III: "Five Loops Don't Lie"

**The Win:** Found the 4029-frame (67.1s) loop in the clean capture, confirmed
by 5 clean repetitions. The loop length matches the fan MIDI total duration
to within 0.1 seconds.

**But Then:** Started the extraction at the loop BOUNDARY (the bridge section
with B1/A1 notes) instead of where the riff actually begins.

**The User:** "You are still starting a few beats late."

**Lesson:** Finding the loop length ≠ finding the loop start. The bridge is
not the opening.

---

## Act IV: "The Octave That Wasn't An Octave"

**The Scene:** Fan MIDI has E2, trace has E3. "Oh, it's just an octave offset,
the NSF applies -12 to pulse notes." Case closed.

**The Problem:** Fan has D2, trace has A2. That's +7 semitones, not +12.
Fan has G2, trace has A#4. That's +27 semitones, not +12. These are not
octave errors. These are completely different notes.

**What Took 6 Rounds To Figure Out:** The Rare driver has a TRANSPOSITION
REGISTER at $0354,X (set by CMD 0x12, modified by CMD 0x13) that shifts
note indices before the period table lookup. The trace captures the SHIFTED
period, not the intended note.

**Lesson:** When three sources agree (fan MIDI, NSF, ROM data) and one
disagrees (trace), the trace interpretation is wrong — even if the raw
trace data is technically correct.

---

## Act V: "The ROM Was Trying To Tell Us"

**The Win:** Finally cracked it open. Read the actual bytes at $A2CF. Found
0x88 (G2) and 0x83 (D2) in the song data. These ARE the correct riff notes.

**But Also Found:** The first 97 bytes of P2 data are initialization commands
and complex arpeggio patterns with rapid transposition changes — NOT the
opening riff. The riff is stored in subroutine patterns called via CMD 0x1E.

**The Discovery Path:**
1. Found CMD 0x12 handler at $8DCD writes to $0354,X
2. Found the ADC $0354,X at $88DE in the note handler
3. Confirmed: note_byte + transposition → table_index → period
4. The trace captures the FINAL period, after transposition

**Lesson:** The 6502 disassembly doesn't lie. When the math doesn't work out,
read the code.

---

## Act VI: "ANXIETY.md — The File That Should Have Been Written First"

**The Realization:** After 8 versions of trace-derived MIDI, the user says:
"I'm afraid that in the future you will get married to a note sequence
you'd worked out when you could be figuring out the locations of all the
note pitch and duration and envelope values from figuring out how they are
placed in the data."

**Translation:** Stop polishing trace output. Go read the ROM.

**The Result:** ANXIETY.md + 7 finder skills + a complete Rare driver
command reference. The foundation for doing it right.

---

## The Scoreboard

| Version | What Happened | Quality |
|---------|--------------|---------|
| v3 | Raw trace, closest yet per user | Trills everywhere |
| v4 | Over-filtered, lost real notes | Worse |
| v5 | APU2 SysEx, but SysEx was broken | No sound |
| v6 | Smart note detection, 3-frame stability | 2 beats late, dee too high |
| v7 | ROM table snapping + sweep hold | Same wrong notes, just held steadier |
| v8 | Clean capture, wrong start point | All over the place |
| v8b | Different start point, still wrong | Still wrong notes |
| **v9** | **Fan MIDI pitches + trace timing** | **First time riff sounds right** |

## Key Realization Timeline

1. **Hour 1:** "Let me snap to the ROM period table" → wrong approach (trace periods ARE table entries, just the wrong ones)
2. **Hour 2:** "SFX must be contaminating the trace" → disproved by clean capture
3. **Hour 3:** "The NSF diverges, trace is ground truth" → technically true but misleading
4. **Hour 4:** "Wait, the fan MIDI matches the NSF AND the ROM data" → the trace interpretation was the outlier
5. **Hour 5:** "CMD 0x12 sets transposition at $0354" → ROOT CAUSE FOUND
6. **Hour 5.5:** "Build finder skills, not more trace interpretations" → paradigm shift
