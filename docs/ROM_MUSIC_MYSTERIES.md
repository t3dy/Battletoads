# ROM Music Mysteries — Unresolved Unknowns

Status: Living document. Updated as mysteries are resolved or new ones discovered.
Last updated: 2026-04-01

## Category A: Pitch / Runtime State

### A1. Pulse Period Halving Under NSF Emulation [WORKAROUND APPLIED]

**Symptom:** NSF extraction produces pulse periods exactly half of Mesen
ground truth, shifting all pulse notes +12 semitones (1 octave too high).

**Evidence:**
- 12/12 Pulse 2 notes compared: ratio consistently ~2.005
- 10/10 Pulse 1 notes compared: ratio consistently ~2.003
- Triangle periods: IDENTICAL between NSF and Mesen (0 of 10 differ)
- Period lookup table: byte-identical between NSF ROM and World ROM
- All writes traced via APU hook: values are genuinely halved, not
  mis-assembled from lo/hi bytes

**Current hypothesis:** The SMB sound driver uses a variable (likely
zero-page) to select the octave offset into the period table. In the
ROM, the game engine initializes this before starting music. In the
NSF, only INIT and PLAY run — the game engine variable is never set,
defaulting to 0, which maps to a higher octave in the table.

**What is proven:**
- The bug is pulse-only (triangle unaffected)
- The period table data is correct
- The 6502 code runs and produces correct note intervals
- The absolute period values are exactly halved

**What is still uncertain:**
- Which zero-page variable controls the octave offset
- Whether this is SMB-specific or affects other NSFs
- Whether the NSF file itself is defective (missing initialization)

**Workaround:** `period_to_midi()` subtracts 12 from pulse notes.
Marked as WORKAROUND in code. See `nsf_to_reaper.py:240`.

**Next test:** Extract Castlevania (different sound driver) and compare
against its existing Mesen trace to see if the same halving occurs.

### A2. Is the Octave Bug SMB-Specific or Universal?

**Symptom:** Unknown whether other games have the same period halving.

**Evidence so far:** Only Mario tested. Castlevania, Contra, Mega Man
traces exist but haven't been compared against NSF extraction with
this specific question in mind.

**Risk:** If the -12 correction is applied globally but some games
DON'T have the bug, those games would be 1 octave too LOW.

**Next test:** Run comparison on Castlevania (trace exists at
`extraction/traces/castlevania/stage1.csv`). If CV1 pulse periods
match without correction, the bug is SMB-specific and the workaround
needs to be game-conditional.

### A3. Triangle Octave Relationship

**Symptom:** Triangle uses divisor 32 (vs pulse 16), producing notes
1 octave lower for the same period. Currently handled by
`period_to_midi(period, is_tri=True)`. Confirmed correct by Mesen.

**Status:** RESOLVED. Triangle periods match between NSF and Mesen.
No correction needed.

## Category B: Note Boundaries

### B1. Vibrato Fragmentation

**Symptom:** Games using software vibrato (rapid period oscillation
+/- 1-2 semitones within 4 frames) produce a stream of very short
notes instead of a sustained note with pitch modulation.

**Affected games:** Unknown — needs systematic check.

**Current behavior:** Each period change creates a note boundary.
A vibrato of 2 semitones at 15 Hz produces ~4 notes per vibrato
cycle, or ~60 note events per second.

**Impact:** Notes sound choppy on synths with attack time. The ADSR
attack phase cuts into each micro-note, destroying the legato effect.

**Possible fix:** Detect rapid period oscillation (same note +/- 1-2
semitones within N frames) and convert to MIDI pitch bend events
instead of note boundaries.

**Next test:** Find a game with known vibrato (check if Metroid or
Castlevania uses software vibrato) and quantify the fragmentation.

### B2. Same-Pitch Retrigger Collapsing

**Symptom:** When a note ends and the same pitch immediately restarts
(common in staccato passages), the extraction may collapse them into
one sustained note if the period doesn't change between them.

**Evidence:** Mario Overworld has 314 Pulse 1 notes, all 112 ticks
(7 frames). The volume decays to 0 within the note, then a new CC11
value arrives for the next note. If the period stays the same, no
note boundary is created — the extraction sees it as one long note
with volume automation.

**Current behavior:** Note boundary is period-change-driven. Same
period + volume drop to 0 + volume rise = still the same note.

**Impact:** The MIDI file may have fewer notes than the game actually
plays. CC11 handles the volume shape correctly, but the synth's
note-on behavior (ADSR trigger) doesn't fire for the retrigger.

**Next test:** Compare Mario note count (314 on P1) against Mesen
period changes to see if any retriggered notes are being collapsed.

### B3. Volume-Zero Gaps Within Notes

**Symptom:** A note can have vol=0 for several frames in the middle
(between envelope decay and next note) while the period stays the
same. This is correct NES behavior — the note is technically still
"on" but silent.

**Current handling:** Correct. The spec says "Duration is determined
by period changes, not volume reaching zero." CC11 drops to 0 and
the synth goes silent, which is faithful.

**Status:** RESOLVED by design. No fix needed.

## Category C: Noise / Drums

### C1. Crude 3-Bucket Drum Mapping

**Symptom:** The extraction maps 16 possible noise period indices to
only 3 GM drum notes: kick (36), snare (38), hi-hat (42).

**Evidence from Mario Mesen capture:**
- Noise period values seen: 3, 31, 63, 761
- These are Mesen's decoded timer periods, not the 4-bit indices
- NSF extracts period_idx=3 consistently (maps to hi-hat bucket)
- Mesen shows 68 drum hits, NSF shows 67 (close match)

**Impact:** Games with varied percussion lose variety. The synth has
23 GM drum mappings but the extraction only produces 3.

**Known fix path:** Map all 16 period indices to distinct MIDI notes
instead of 3 buckets. The synth drum table already supports this.

### C2. Noise Mode Bit Lost in MIDI

**Symptom:** The noise mode bit (long=0, short=1) is captured in
frame data but NOT encoded in the MIDI output. The synth assigns
mode per drum type from its table, which may not match the game.

**Evidence:** Mario uses both modes (0 and 1) for different drum
sounds. The extraction sees both but the MIDI only carries the
note number, not the mode.

**Fix:** Encode mode in the MIDI note mapping (e.g., mode 0 drums
at notes 36-50, mode 1 drums at notes 51-65) or use CC to switch.

### C3. Noise Volume Envelope Not in MIDI

**Symptom:** NSF extraction captures per-frame noise volume but does
NOT emit CC11 for noise. The synth uses its own decay envelopes from
the drum table. The game's actual volume shape may differ.

**Evidence:** Mario noise vol is binary (0 or 12, constant mode).
No decay captured because SMB uses const=1 (hardware envelope off).
Other games may use the hardware envelope for noise, producing
actual decay curves that we're not capturing.

### C4. Noise Period Representation Mismatch

**Symptom:** NSF extraction captures the 4-bit period INDEX (0-15),
but Mesen reports the decoded timer PERIOD value from the hardware
lookup table. These are different numbers for the same sound.

**Evidence:** NSF period_idx=3, Mesen period=31. The noise period
table maps index 3 → 32 CPU cycles. Mesen reports 31 (off by 1,
likely 0-indexed in hardware).

**Impact:** Comparison scripts must map between representations.

## Category D: Hardware Semantics

### D1. APU Registers Are Write-Only (Flat RAM Mismatch)

**Symptom:** py65 treats $4000-$4017 as flat RAM. Real NES APU
registers are write-only with side effects (timer reload, phase
restart, length counter set).

**Impact on extraction:** The extraction reads cpu.memory[$4002]
after each frame, which gives the last byte written. This is
correct for the value but misses:
- Multiple writes per frame (only last value captured)
- Write ordering effects (e.g., $4003 before vs after $4002)
- Timer reload side effects (hardware latches period on $4003 write)

**Evidence:** The APU write tracer confirmed that for Mario, the
driver writes period registers at most once per frame for each
channel. No multi-write issues detected for this game.

**Risk:** Games with mid-frame register manipulation (fast trills,
DMA interference) would be affected.

### D2. Length Counter Not Modeled

**Symptom:** The extraction ignores the length counter ($4003/$4007
bits 3-7). On real hardware, the length counter can silence a channel
after N frames regardless of what the driver does.

**Evidence:** Mario triangle $400B_length has 5,442 changes — it's
actively being used. But since the driver continuously refreshes the
length counter (writing $400B every frame), the auto-silence never
triggers, and our extraction correctly captures the triangle as
continuously active.

**Impact:** For games where the driver DOESN'T refresh the length
counter, notes would end earlier on real hardware than in extraction.
Likely edge case.

### D3. DMC Channel Not Extracted

**Symptom:** The DPCM (delta modulation channel, $4010-$4013) is not
captured in MIDI extraction.

**Evidence from Mario Mesen capture:** 49 DMC DAC changes, linear
ramp 0→48 over 49 frames. This is the "coin/powerup" sound effect,
not musical content for the Overworld theme.

**Impact for Mario:** Zero. DMC is not used for music.

**Impact for other games:** HIGH. Mega Man 2 uses DPCM for drums.
Castlevania III uses it for bass. Games using the VRC6 or other
expansion audio also use sample-based channels.

## Category E: Representation Limits

### E1. CC11 Volume Quantization

**Symptom:** NES volume (0-15) mapped to CC11 (0-127) via `vol * 8`.
This means CC11 values are always multiples of 8: 0, 8, 16, 24...120.
Only 16 of 128 possible values are used.

**Impact:** Minimal. The synth reverse-maps CC11 back to 0-15 via
`floor(msg3 * 15 / 127)`. The round-trip is lossy only at the
boundaries (e.g., CC=120 → NES vol=14, but original was vol=15
mapped to CC=120). This is a known 1-bit loss at the top of range.

### E2. MIDI Note Resolution for NES Periods

**Symptom:** NES periods don't map exactly to MIDI semitones. The
`round()` in period_to_midi can be off by up to 50 cents.

**Impact:** Minimal for most games. NES games are tuned to their
own period tables, which are approximately but not exactly equal
temperament. The rounding error is inaudible in context.

### E3. Tempo Mapping Precision

**Symptom:** 128.6 BPM chosen so that 16 ticks = 1 NES frame.
The actual NES frame rate is 60.0988 Hz (NTSC), which maps to
128.57 BPM. The 128.6 approximation introduces ~0.02% drift.

**Impact:** Negligible. Over 90 seconds, drift is ~18ms (less than
1 frame).

## Priority Ranking

| ID | Mystery | Impact | Effort | Priority |
|----|---------|--------|--------|----------|
| A1 | Pulse period halving | HIGH | DONE (workaround) | Source fix later |
| A2 | Is bug universal? | HIGH | LOW (test 1 game) | NEXT |
| C1 | 3-bucket drums | MEDIUM | LOW | After A2 |
| C2 | Mode bit lost | MEDIUM | LOW | After C1 |
| B1 | Vibrato fragmentation | MEDIUM | MEDIUM | Needs anchor game |
| B2 | Same-pitch retrigger | LOW-MED | LOW | Test on Mario |
| D3 | DMC not extracted | HIGH for some games | HIGH | Per-game basis |
| C3 | Noise envelope | LOW | LOW | After C1/C2 |
| D1 | Write-only registers | LOW | N/A | Monitor |
| D2 | Length counter | LOW | LOW | Edge case |
