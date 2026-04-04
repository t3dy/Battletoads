# Parser Aligned: From Command Discovery to Working Parser

## What Happened

### Step 1: Disassembled All 31 Command Handlers

Read the 6502 machine code for every handler in the Rare driver's dispatch
table at $8B7B. For each handler, counted INY instructions (each INY = 1
byte consumed from the song data stream) and identified what RAM locations
each handler writes to.

Initial result: a table of 31 commands (0x00-0x1E) with parameter counts
and effects. Most matched the handover's notes, but several were unknown.

### Step 2: Discovered Subroutine Parameter Counts Were Wrong

Three commands call 6502 subroutines before returning:
- CMD 0x08 calls $8CC4 (reads 3 bytes internally) = 3 params total
- CMD 0x17 calls $8CC4 (3 bytes) + reads 1 more byte = 4 params total
- CMD 0x0A/0x0B call $8D08 (reads 4 bytes) + 1 more = 5 params total

The handover had CMD 0x17 as 1 param and CMD 0x08 as unknown. These wrong
counts would desynchronize the entire data stream — every byte after the
error gets misinterpreted.

### Step 3: Critical Discovery in the Note Handler

Reading the note handler code at $88D9-$8938 revealed a **dual-mode
duration system**:

```
$892D: LDA $0351,X      ; check persistent duration register
$8930: BNE $8935        ; if non-zero, use it (skip inline read)
$8932: INY              ; else advance to duration byte
$8933: LDA ($37),Y      ; read inline duration from stream
$8935: STA $0302,X      ; store to duration counter
```

- CMD 0x06 (1 param) sets persistent duration — all subsequent notes use
  this value, no inline byte consumed
- CMD 0x07 (0 params) clears it — each note is followed by an inline
  duration byte

This means the byte pattern `88 02 88 02 88 06` with persistent_duration=0
is: G2(dur=2) G2(dur=2) G2(dur=6). But with persistent_duration=2, the
pattern `83 22 83 04` is: D2(no dur byte) CMD_0x22 D2(no dur byte) envelope_04.

### Step 4: Built Parser v1, Got 335 Errors

First test run produced "Unknown byte 0x1F", "Unknown byte 0x22", etc.
The problem: MAX_CMD was 0x1E but the dispatch table extends further.

### Step 5: Discovered 8 More Commands (0x1F-0x26)

Read the dispatch table beyond entry 0x1E. Found valid handler addresses
for CMD 0x1F through 0x26. CMD 0x27 pointed to $00A9 (zero page = garbage),
confirming the table ends at 0x26.

Key new commands:
- CMD 0x1F (2 params): sets the envelope override flag ($03A2,X)
- CMD 0x22 (0 params): enables per-note envelope override byte
- CMD 0x21 (0 params): clears both persistent duration and envelope override
- CMD 0x23 (2 params): another subroutine call mechanism

### Step 6: Parser v2 — Zero Errors

Updated MAX_CMD to 0x26, added all parameter counts, fixed CMD 0x1E/0x05
subroutine handling. Result: 0 errors, 821 notes, 1163 commands. But the
jump at the end went to $0283 (RAM address = parse desynchronized late).

### Step 7: Discovered Per-Note Envelope Override Byte

The note handler at $890D-$8920 reads an EXTRA byte from the stream when
$03A2,X has bit 7 set:

```
$890D: LDA $03A2,X      ; check flag
$8910: BPL skip         ; if bit 7 clear, no extra byte
$8914: INY              ; advance
$8917: LDA ($37),Y      ; read envelope override byte
```

CMD 0x22 sets $03A2,X = $80 (bit 7 set). This means each note between
CMD 0x22 and CMD 0x21 consumes an EXTRA byte. Without tracking this, the
parser desynchronizes at the D2 riff section where envelope overrides are used.

### Step 8: Found CMD 0x1F Has 2 Params, Not 3

The handler has 3 INY but also a DEY:
```
$8D37: INY (param1)    ; +1
$8D3D: INY (param2)    ; +1
$8D45: DEY             ; -1
; falls into CMD 0x0C which does INY (+1)
```

Net advance: 2. The DEY re-reads param2 for different processing. My
disassembler counted raw INY without accounting for DEY, giving the wrong 3.

### Step 9: Parser v3 — Zero Parse Errors, 955 Notes, Clean Loop

With all fixes:
- 39 commands (0x00-0x26) with verified parameter counts
- Dual-mode duration tracking (persistent vs inline)
- Per-note envelope override byte tracking
- Subroutine call/return/loop mechanism (CMD 0x1E/0x05)
- Loop detection (CMD 0x01 jump to earlier address)

**Result: 0 parse errors, 955 notes, 1 rest, 520 commands, clean loop to $A2D6**

> **IMPORTANT: This is a STRUCTURAL milestone, not a SEMANTIC one.**
> Zero parse errors means byte-stream alignment is confirmed — every
> command boundary, parameter count, and variable-width event is correctly
> partitioned. It does NOT mean pitches, durations, envelopes, or timing
> are musically correct.
>
> Known remaining gaps at this point:
> - Duration accounting off by 1.52x (2048 ticks vs ~1343 expected)
> - Arpeggio system (CMD 0x0D/0x0E) not yet simulated
> - Envelope shapes not yet validated against trace
> - Base notes (e.g., G6) may never actually sound as parsed due to
>   arpeggio offsets transposing them by several octaves
>
> **Parser output is a hypothesis.** Execution semantics validation
> (simulating the driver frame-by-frame and comparing against Mesen
> trace) is the NEXT required phase. See EXECUTIONSEMANTICSVALIDATION.md.

## Key Insight: The Same Subroutine, Different Transpositions

The riff doesn't exist as a sequential E2-D2-G2 pattern in ROM. Instead:

1. A subroutine at $A2B1 contains a chord pattern using raw bytes 0x8F, 0x8A, 0x88
2. The main sequence calls this subroutine with different transpositions:
   - transpo=-3: B2 / F#2 / E2 (the low arpeggio intro)
   - transpo=12: D4 / A3 / G3 (the high octave section)
3. Another subroutine at $A34C contains the D2 riff (raw byte 0x83)
4. The riff is ASSEMBLED from these reusable patterns called at different transpositions

## Files Changed

- `extraction/drivers/rare/parser.py` — New Rare driver parser
- `extraction/drivers/rare/__init__.py` — Package init
- `extraction/manifests/battletoads.json` — Game manifest with all findings
