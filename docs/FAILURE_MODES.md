# NES Music Studio — Failure Modes and Anti-Patterns

Catalog of failure modes encountered during CV1 and Contra extraction,
plus hypothetical scenarios for future ROMs. Every entry is grounded
in real incidents or derived from documented project lessons.

---

## 1. Assumption Transfer Failures

Treating knowledge from one game as universal truth for another.

### 1.1 Same Period Table Implies Same Driver

**Description**: The NES period table (12 entries mapping semitones to
timer values) is standard NTSC tuning, not a driver fingerprint.
Seeing identical period values in two ROMs proves they target the same
hardware, nothing more.

**Real example**: CV2 (Simon's Quest) has the same period table values
as CV1 and Contra. We spent 4 prompts scanning CV2 for the Maezawa
pointer table before discovering CV2 uses the Fujio variant -- a
completely different sound engine with no compatible command format.

**Detection**: Search for command signatures (E8, DX+instrument bytes,
FE+count+address) rather than period table matches. No signature
hits means not Maezawa.

**Prevention**: Step 3 of the parser checklist: scan for
E8+DX and FE+count+addr patterns. No hits = STOP.

**Cost if missed**: 3-4 prompts wasted on dead-end scanning. No data
quality impact (the parser simply fails to produce output).

### 1.2 Same Publisher Implies Same Driver

**Description**: Konami published dozens of NES titles across multiple
development teams. Driver choice varied by team, era, and mapper.

**Real example**: CV1 (Maezawa, 1986) and CV2 (Fujio variant, 1987)
are both Konami Castlevania titles. CV2 uses a different driver
despite being a direct sequel. CV3 uses MMC5 expansion audio with
yet another engine.

**Detection**: Run rom_identify.py to check mapper and scan for driver
command signatures before assuming compatibility.

**Prevention**: Manifest-first workflow. Create the manifest JSON
and record driver identity as verified or hypothesis before writing
any parser code.

**Cost if missed**: 3+ prompts if a parser is written for the wrong
driver. The parser may appear to partially work on random data,
wasting additional prompts debugging phantom issues.

### 1.3 DX Byte Count Assumed from CV1

**Description**: The DX (tempo+instrument) command reads a variable
number of extra bytes depending on the game. CV1 reads 2 bytes after
DX for pulse (instrument + fade). Contra reads 3 for pulse
(config + vol_env + decrescendo) and 1 for triangle.

**Real example**: Contra v2 used the CV1 parser unmodified. After
every DX command, the parser consumed the wrong number of bytes,
shifting the data pointer. All subsequent bytes were misinterpreted.
Result: missing melodies, nonsense notes, and corrupted output for
9 of 11 tracks.

**Detection**: After parsing, check that all channels reach the same
total frame count. Byte count mismatches cause channels to desync
and produce wildly different durations.

**Prevention**: Step 5 of the parser checklist: determine DX byte
count from the disassembly before writing any code.

**Cost if missed**: 2-3 prompts. Output is obviously broken (nonsense
notes, missing sections), so it does not produce silently wrong data.

### 1.4 E8 Gate Semantics Assumed Universal

**Description**: The E8 (EnvelopeEnable) command was initially treated
as a gate that controls whether volume fading is applied. Sq1 had an
E8 command; Sq2 did not. The assumption that E8 gates fading caused
1518 volume mismatches on Sq2 alone.

**Real example**: Sq2 in Vampire Killer has zero E8 commands in its
data stream, yet the APU trace shows clear volume decay on every note.
E8 does not gate the fade system. Fading is always active when
fade_start > 0.

**Detection**: Compare volume mismatch counts per channel. If one
channel has dramatically more mismatches and also has fewer E8
commands, the gate logic is wrong.

**Prevention**: Check assumptions against ALL channels, not just the
first one tested. Cross-channel verification is mandatory.

**Cost if missed**: 2 prompts. Volume accuracy drops significantly on
affected channels.

---

## 2. Static Parsing Without State

Treating the byte stream as a flat sequence instead of a stateful
virtual machine with execution context.

### 2.1 Missing Loop Context

**Description**: The FE (repeat) command uses a per-channel counter.
The parser must track repeat state to know when a section has been
played the correct number of times. Without state, repeats produce
wrong iteration counts.

**Real example**: The FE repeat count bug in CV1 v4. FE 02 was
interpreted as "repeat 2 more times" (3 total passes) instead of
"2 total passes." This shifted the data pointer so section B started
at the wrong byte offset, corrupting every note from frame 896 onward.

**Detection**: Compare parsed output against trace at section
boundaries. If notes are correct for the first section but wrong
afterward, a control flow command likely shifted the pointer.

**Prevention**: Verify FE semantics against the disassembly. The
driver increments the counter before comparing, so count=2 means
2 passes, not 3.

**Cost if missed**: 3 prompts. All notes after the first repeat are
wrong. Structural errors cascade -- one bad count corrupts everything
downstream.

### 2.2 Missing Bank Switch State

**Description**: Mapper 2+ ROMs have bank-switched address spaces.
A CPU address like $9428 maps to different ROM offsets depending on
which bank is currently selected. Without tracking the active bank,
pointer lookups read from the wrong ROM location.

**Real example**: Contra's sound data lives entirely in bank 1 (ROM
$4010-$8010). Using the CV1 linear address formula
(addr - $8000 + 16) returned garbage because it assumed mapper 0.

**Detection**: Parser produces obviously wrong data (random notes,
immediate crashes, division-by-zero on invalid tempo bytes).

**Prevention**: Step 1 of the parser checklist: read rom[6] for
mapper type. Configure the address resolver before parsing.

**Cost if missed**: 2 prompts. Output is non-functional, so it fails
fast rather than producing subtly wrong data.

### 2.3 Missing Tempo Accumulator State

**Description**: The NES driver's duration counter is frame-based.
Each DX command sets a tempo multiplier. If the parser fails to track
tempo changes mid-stream, all subsequent note durations are wrong.

**Hypothetical scenario**: A track changes tempo from D7 (7 frames
per unit) to D5 (5 frames per unit) midway through. If the parser
ignores the second DX and keeps using tempo 7, every note after the
change is 40% too long.

**Detection**: Channel durations diverge. If one channel parses to
3072 frames and another to 2800, a tempo change was missed.

**Prevention**: The parser must update its tempo state variable on
every DX command encounter, not just the first.

**Cost if missed**: 2 prompts. Timing drift accumulates, making later
sections obviously wrong.

---

## 3. Mapper/Address Failures

Wrong ROM-to-CPU or CPU-to-ROM address translation.

### 3.1 Hardcoded Offsets Instead of Resolved Addresses

**Description**: Using a fixed formula like `addr - 0x8000 + 16`
works for mapper 0 (NROM, 32KB PRG) but fails for any bank-switched
mapper. Each mapper type has its own address resolution scheme.

**Real example**: CV1 (mapper 0) uses linear addressing. Contra
(mapper 2, UNROM) requires bank-aware resolution:
`16 + bank * 16384 + (cpu_addr - 0x8000)`. Using CV1's formula
on Contra reads from the wrong ROM location.

**Detection**: Parsed data is garbage. Pointer table reads produce
addresses outside valid ROM range or point to non-music data.

**Prevention**: The manifest must declare `resolver_method` (linear
vs bank-switched). The parser must use the manifest's resolver, never
a hardcoded formula.

**Cost if missed**: 1-2 prompts. Fails obviously.

### 3.2 Wrong Bank Assumption

**Description**: Even with the correct mapper type, choosing the wrong
bank number reads valid-looking but incorrect data. Unlike wrong
mapper type (which produces garbage), wrong bank can produce
plausible-looking but musically wrong output.

**Hypothetical scenario**: A game stores music in bank 3 but we
assume bank 1 (following Contra's layout). The parser reads data
from bank 1 that happens to contain valid-looking command bytes,
producing a track that parses without errors but plays wrong notes.

**Detection**: Compare parsed output to the game audio by ear. Wrong
bank produces internally consistent but musically incorrect output.

**Prevention**: Find the bank number from the disassembly or by
tracing the bank-switch register writes in Mesen's debugger.

**Cost if missed**: 3-5 prompts. Subtle -- the parser succeeds and
the output sounds like plausible NES music, just wrong music.

### 3.3 Ignoring Mapper Type

**Description**: Proceeding without checking the iNES header for
mapper information. Mapper type determines the entire address space
layout.

**Real example**: rom_identify.py was built specifically to prevent
this. Before it existed, the Contra extraction started by assuming
mapper 0 (CV1's type), wasting the first attempt entirely.

**Detection**: rom_identify.py reports mapper type as its first output.

**Prevention**: Step 1 of the workflow: run rom_identify.py. Step 1
of the parser checklist: read rom[6-7] for mapper type.

**Cost if missed**: 1-2 prompts.

---

## 4. Validation Failures

Trusting automated output without human verification.

### 4.1 Zero Trace Mismatches but Wrong Octave

**Description**: The trace comparison tool checks internal consistency
between the parser's output and the emulator's APU state. If both use
the same incorrect octave mapping, they agree perfectly while both
being wrong by exactly 12 semitones.

**Real example**: After setting BASE_MIDI_OCTAVE4 = 24 to match the
trace's frequency-to-MIDI conversion, the trace comparison showed
zero pitch mismatches on all channels. But playback in REAPER was one
octave too low. The trace comparison's freq_to_midi function used the
same wrong constant, creating a closed loop of consistent error.

**Detection**: A human must compare the REAPER/MIDI output against the
actual game running in an emulator. Automated comparison cannot catch
systematic offsets.

**Prevention**: After any pitch or octave mapping change, the user
must listen to both the extraction and the game side by side. Add a
gate step: "user confirms pitch matches game" before proceeding.

**Cost if missed**: 3 prompts. Subtle because every automated test
passes. Only caught by ear.

### 4.2 Automated Tests Pass but Music Sounds Wrong

**Description**: The trace comparison validates pitch, volume, and
sounding state at frame resolution. But it cannot evaluate musical
correctness -- whether the notes form the right melody, whether the
rhythm feels right, whether articulation matches the game's feel.

**Real example**: CV1 v3 had zero pitch mismatches but played too
legato because the MIDI export used raw parser events instead of
the frame IR's envelope-shortened notes. The trace comparison only
checks per-frame state, not MIDI export behavior.

**Detection**: Listen to the output. Compare rhythm and articulation
to the game, not just pitch.

**Prevention**: The workflow mandates listening after every change.
Parse ONE track and listen before batch-extracting.

**Cost if missed**: 2-3 prompts spent investigating why output sounds
wrong despite passing all automated tests.

### 4.3 Testing One Channel, Assuming Others Work

**Description**: Verifying output on pulse 1 and assuming pulse 2 and
triangle behave identically. Each channel may have different command
sequences, different instrument parameters, and different edge cases.

**Real example**: The E8 gate bug was invisible on Sq1 (which had an
E8 command) but caused 1518 mismatches on Sq2 (which had none). If
only Sq1 had been checked, the bug would have shipped.

**Detection**: Always run trace comparison on ALL channels. Check
mismatch counts per channel, not just the aggregate.

**Prevention**: trace_compare.py reports per-channel results. Review
all channels before declaring success.

**Cost if missed**: 2 prompts. Can produce systematically wrong volume
on entire channels.

---

## 5. Envelope Model Failures

Applying the wrong volume shaping model to a game's audio.

### 5.1 Parametric Model on Lookup-Table Driver

**Description**: CV1 uses a two-phase parametric envelope (fade_start
decrements + hold + fade_step release). Contra uses volume envelope
lookup tables indexed by instrument ID. Applying CV1's parametric
model to Contra produces flat or incorrectly shaped dynamics.

**Real example**: Contra v3-v4 used the CV1 fade_start/fade_step
model. The result was flat volume on most notes because Contra's
DX bytes encode table indices, not parametric decay values.

**Detection**: Volume sounds flat or wrong compared to the game.
The DX extra bytes parse to implausible fade values (e.g., fade_start
of 0 for instruments that clearly decay).

**Prevention**: DriverCapability dispatches envelope strategy. Check
volume_model in the manifest before applying any envelope logic.

**Cost if missed**: 3+ prompts. Volume is wrong on every note but
pitches are correct, making it tempting to ship and fix later.

### 5.2 Ignoring Triangle Linear Counter

**Description**: Triangle volume is not controlled by the APU volume
register. Triangle notes are gated by the $4008 linear counter. The
instrument byte for triangle IS the $4008 register value, not a
volume/duty setting.

**Real example**: CV1 triangle had 518 sounding-state mismatches
because the frame IR treated triangle like pulse (volume-based
gating). The fix was modeling linear counter decay:
`(reload + 3) // 4` sounding frames.

**Detection**: Triangle notes sustain for their full duration instead
of cutting off early. Sounding-state mismatches are high while pitch
mismatches are zero.

**Prevention**: Triangle always requires special handling. The
instrument byte must be decoded as $4008 (control bit + reload value),
not as DDLCVVVV.

**Cost if missed**: 2 prompts. Triangle articulation is wrong (too
legato) but pitches are correct.

### 5.3 Missing Duty Cycle Envelope

**Description**: Some drivers change duty cycle over the course of a
note (e.g., starting at 50% and shifting to 25% for a "twang" effect).
If the parser only captures the initial duty setting, timbral
evolution within notes is lost.

**Hypothetical scenario**: A driver's volume envelope table includes
duty cycle changes alongside volume changes. The extraction captures
volume but ignores the duty column, producing notes with static timbre.

**Detection**: Compare the APU trace's duty cycle register writes
against the extraction. If the trace shows mid-note duty changes that
the extraction misses, this failure is present.

**Prevention**: When extracting envelope tables, check whether they
contain duty cycle data in addition to volume data.

**Cost if missed**: Low impact on note accuracy. Affects timbral
authenticity only.

---

## 6. Silent Invariant Violations

Conditions that produce wrong output without raising errors.

### 6.1 Duration Overflow from Clamping Errors

**Description**: Computed timing values can go negative or overflow
if intermediate calculations are not clamped. Negative durations
wrap to large positive values in unsigned arithmetic.

**Real example**: The phase2_start calculation
`duration - fade_step` produced negative values when fade_step
exceeded the note duration. The fix was
`phase2_start = max(1, duration - fade_step)`.

**Detection**: Notes with anomalously long durations or gaps. Frame
IR output with duration values that exceed the note's allocated time.

**Prevention**: All derived timing values must use explicit
`max()` / `min()` clamping. The architecture rule is: "Derived
Timing Must Be Clamped."

**Cost if missed**: 2 prompts. Produces subtly wrong articulation
on short notes.

### 6.2 Negative Timing Values

**Description**: Subtracting envelope parameters from note duration
can produce negative frame counts. Python handles negative integers
gracefully (no crash), so the error is silent.

**Hypothetical scenario**: A note with duration 3 and fade_step 5
produces phase2_start = -2. The envelope code iterates with a
negative start index, skipping the hold phase entirely and applying
release from the wrong frame.

**Detection**: Dump frame IR for short notes and verify that envelope
phases start and end at correct frame indices.

**Prevention**: Clamp all subtraction results to minimum 1.

**Cost if missed**: 1-2 prompts. Affects only short notes with large
envelope parameters.

### 6.3 Parser Emitting Shaped Durations

**Description**: The parser must emit full-duration note events.
Staccato truncation, envelope-based shortening, and articulation
shaping are the frame IR's responsibility. If the parser pre-shapes
durations, the frame IR cannot apply correct envelopes.

**Real example**: Contra v1-v4 had incorrect note splitting in the
parser (DECRESCENDO_END_PAUSE was splitting notes into sounding +
silent portions at parse time). This prevented the frame IR from
applying correct envelope shaping because the notes were already
truncated.

**Detection**: `ParsedSong.validate_full_duration()` must return
empty. Any note where `duration_frames != tempo * (nibble + 1)` is
a parser violation.

**Prevention**: Architecture rule: parsers emit full-duration events.
The validation function enforces this at parse time.

**Cost if missed**: 3+ prompts. The frame IR produces wrong envelopes
on pre-truncated notes, and the root cause is non-obvious because the
IR code looks correct.

---

## 7. Process Failures

Workflow mistakes that waste prompts or destroy work.

### 7.1 Batch Extracting Before Single Track Validates

**Description**: Extracting all tracks from a ROM before confirming
that one reference track sounds correct. If the parser has a
systematic error, batch extraction produces many wrong files that
all need to be regenerated.

**Real example**: Contra v1 ran the CV1 parser on all tracks. 13/15
failed. The 2 that "worked" were accidents from random data aligning
with valid command bytes.

**Detection**: If more than 1-2 tracks fail on first extraction, the
parser likely has a fundamental error.

**Prevention**: Step 6 of the workflow: parse ONE track and listen
before batch-extracting.

**Cost if missed**: 2-3 prompts regenerating batch output. Also
creates confusing state with many broken files.

### 7.2 Overwriting Output Files Without Versioning

**Description**: Saving new extraction results over previous files.
The user cannot A/B compare versions, and there is no rollback if the
new version is worse.

**Real example**: Contra MIDI and RPP files were overwritten between
versions. The user could not compare v3 articulation against v4 to
decide which sounded better.

**Detection**: User asks to compare versions and the old file is gone.

**Prevention**: Always version output files (v1, v2, etc.). Never
overwrite a file that has been tested or delivered to the user.

**Cost if missed**: 2 prompts to regenerate the old version. Also
erodes user trust.

### 7.3 Guessing Before Dumping Trace Data

**Description**: Forming hypotheses about driver behavior from byte
values alone instead of extracting actual APU trace frames first.
The trace shows what the hardware does; bytes show what we think it
should do.

**Real example**: Three different envelope hypotheses were tested for
CV1 before anyone looked at actual frame data. When the trace was
finally dumped, the correct model was obvious from 20 frames of
volume values.

**Detection**: If you are on your second hypothesis without having
looked at trace data, you are in this failure mode.

**Prevention**: Dump 20 frames of trace data BEFORE modeling. The
trace is ground truth.

**Cost if missed**: 5 prompts. The worst single time-waster in the
project's history.

### 7.4 Trying Multiple Hypotheses Simultaneously

**Description**: Changing multiple things at once to "save time."
When the output changes, it is impossible to know which change
caused the improvement (or regression).

**Real example**: The fade_step investigation tried "continued decay
rate" and "force vol=0 on last frame" before isolating the correct
model. Each failed hypothesis required reverting changes and
re-running the trace comparison.

**Detection**: If you changed 2+ things and the result improved, you
do not know which change helped. If it got worse, you do not know
which change hurt.

**Prevention**: Debugging protocol step 4: form ONE hypothesis and
test it. Do not try 3 at once.

**Cost if missed**: 2-3 prompts per extra hypothesis.

### 7.5 Reasoning About Bytes Instead of Reading the Disassembly

**Description**: Attempting to reverse-engineer command semantics by
staring at hex dumps when an annotated disassembly exists and
documents the exact behavior.

**Real example**: The DX byte count for Contra was assumed to be 2
(matching CV1) instead of reading the Contra disassembly which
clearly documents 3 bytes for pulse and 1 for triangle.

**Detection**: If you are guessing about a command format and a
disassembly exists in references/, you are in this failure mode.

**Prevention**: Step 2 of the workflow: check references/ for
annotated source. If it exists, read it. 10 minutes reading saves
hours guessing.

**Cost if missed**: 3 prompts per wrong assumption about command
format.

---

## Implications for Our Pipeline

The failure modes above require these safeguards:

1. **rom_identify.py as mandatory first step**: Reports mapper type,
   period table presence, and driver signature before any parsing
   begins. Prevents mapper/address failures and assumption transfer.

2. **Manifest-first architecture**: Every game gets a JSON manifest
   declaring ROM layout, command format, and known facts vs hypotheses
   BEFORE any parser code is written. Prevents assumption baking.

3. **DriverCapability dispatch**: The frame IR selects envelope
   strategy via DriverCapability, not isinstance checks. Prevents
   envelope model failures when adding new games.

4. **ParsedSong.validate_full_duration()**: Enforces the parser/IR
   contract. Parsers emit full durations; the IR handles shaping.
   Prevents silent invariant violations.

5. **Per-channel trace comparison**: trace_compare.py reports
   per-channel mismatch counts. Prevents single-channel testing bias.

6. **Human listening gate**: No extraction is complete until a human
   compares the output to the game. Automated tests verify internal
   consistency, not absolute correctness.

7. **Versioned output files**: Every extraction iteration gets a
   version suffix. Previous versions are never overwritten.

---

## Pre-Flight Checklist: Before Starting Any New ROM

Run these checks in order. Do not skip steps. Do not write parser
code until step 7 passes.

- [ ] **1. rom_identify.py** -- run `PYTHONPATH=. python scripts/rom_identify.py <rom>`.
      Record mapper type, PRG size, period table presence, driver signature hits.

- [ ] **2. Check manifest** -- look in `extraction/manifests/` for existing JSON.
      If found, read it for known facts and hypotheses.

- [ ] **3. Find disassembly** -- check `references/` for annotated source.
      If one exists, read the sound engine code. Record pointer table address,
      DX byte count, percussion format, and bank mapping.

- [ ] **4. Driver identity** -- scan for E8+DX and FE+count+addr patterns.
      No hits = not Maezawa. STOP and investigate the actual driver.

- [ ] **5. Create manifest** -- write `extraction/manifests/<game>.json` with:
      mapper, resolver_method, pointer_table_addr, dx_byte_count,
      percussion_type, volume_model. Mark each field as verified or hypothesis.

- [ ] **6. Configure address resolver** -- mapper 0 = linear,
      mapper 2 = bank-switched. Use the manifest's resolver_method.

- [ ] **7. Parse ONE track** -- extract a single well-known track.
      Listen and compare to game. Fix issues before proceeding.

- [ ] **8. Trace comparison** -- if a Mesen APU trace is available,
      run trace_compare.py against the reference track. Verify zero
      pitch mismatches.

- [ ] **9. Cross-channel check** -- verify all channels (pulse 1,
      pulse 2, triangle, noise) individually. Do not assume one
      channel's success implies the others work.

- [ ] **10. Batch extract** -- only after steps 7-9 pass. Version
      all output files.

---

## Summary Table

| # | Failure Mode | Category | Cost (prompts) | Detection Difficulty |
|---|-------------|----------|----------------|---------------------|
| 1.1 | Period table = driver | Assumption | 3-4 | Easy (signature scan) |
| 1.2 | Publisher = driver | Assumption | 3+ | Easy (rom_identify) |
| 1.3 | DX byte count assumed | Assumption | 2-3 | Medium (output is broken) |
| 1.4 | E8 gate assumed | Assumption | 2 | Medium (per-channel comparison) |
| 2.1 | Missing loop context | Stateless | 3 | Hard (cascading corruption) |
| 2.2 | Missing bank switch | Stateless | 2 | Easy (garbage output) |
| 2.3 | Missing tempo state | Stateless | 2 | Medium (duration drift) |
| 3.1 | Hardcoded offsets | Address | 1-2 | Easy (garbage output) |
| 3.2 | Wrong bank | Address | 3-5 | Hard (plausible wrong output) |
| 3.3 | Ignoring mapper | Address | 1-2 | Easy (rom_identify) |
| 4.1 | Zero mismatches, wrong octave | Validation | 3 | Hard (requires human ear) |
| 4.2 | Tests pass, sounds wrong | Validation | 2-3 | Hard (requires listening) |
| 4.3 | One channel tested | Validation | 2 | Medium (per-channel report) |
| 5.1 | Wrong envelope model | Envelope | 3+ | Medium (flat volume) |
| 5.2 | Ignoring triangle counter | Envelope | 2 | Medium (sustain mismatches) |
| 5.3 | Missing duty envelope | Envelope | Low | Hard (timbral only) |
| 6.1 | Duration overflow | Silent | 2 | Hard (short notes only) |
| 6.2 | Negative timing | Silent | 1-2 | Hard (no crash in Python) |
| 6.3 | Parser shapes durations | Silent | 3+ | Medium (validation function) |
| 7.1 | Batch before validate | Process | 2-3 | Easy (many failures) |
| 7.2 | No versioning | Process | 2 | Easy (file missing) |
| 7.3 | Guess before trace | Process | 5 | Easy (self-awareness) |
| 7.4 | Multiple hypotheses | Process | 2-3 | Easy (self-awareness) |
| 7.5 | Skip disassembly | Process | 3 | Easy (check references/) |
