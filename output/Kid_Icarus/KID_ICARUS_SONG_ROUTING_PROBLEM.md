# Kid Icarus: The Song Routing Problem

## What Is Song Routing?

Song routing is the mechanism that turns "play song N" into actual music data pointers. The game needs to know: when the player enters the overworld, which bytes in ROM contain the notes for Square 1? For Square 2? Triangle? Noise? The answer to that question is different for every game engine we've encountered, and Kid Icarus has the most complicated version yet.

## How Every Other Game Solved It

### Castlevania 1: The Clean Pointer Table

The simplest and cleanest pattern. A flat table at ROM $0825 contains 9-byte entries — one per song. Each entry holds three 16-bit pointers (Sq1, Sq2, Triangle) separated by single-byte spacers.

```
Song N → read 9 bytes at $0825 + (N * 9)
  bytes 0-1: Sq1 data pointer
  byte 2: separator
  bytes 3-4: Sq2 data pointer
  byte 5: separator
  bytes 6-7: Triangle data pointer
  byte 8: separator
```

To extract Song 5, you read offset 45 in the table. Done. No game state, no conditionals, no indirection. The song number IS the table index. This is why Castlevania was our first successful extraction and our template for everything after.

### Contra: Same Pattern, Different Parameters

Same Konami Maezawa driver family, but the pointer table uses a different entry format (3 bytes instead of 9) and the song indices don't start at 0 — music codes run from $26 to $51. The actual pointer extraction is still a direct table lookup, just with an offset: `table_addr + (music_code - 0x26) * entry_size`.

The complication Contra introduced was that the pointer table format differed from CV1 (3-byte entries vs 9-byte). We assumed "same driver = same format" and wasted 3+ prompts before discovering this. But the routing mechanism itself — flat table, direct index — was identical.

### Battletoads: Two-Level Dispatch

Rare's driver added a layer of indirection. The NSF presents songs numbered 1-N, but internally the game uses a different numbering scheme. A lookup table at CPU $8060 maps NSF song indices to internal IDs. The internal ID then indexes into the actual channel pointer table.

```
NSF Song 2 → lookup $8060[2] → internal ID 4 → channel pointers for Level 1
```

This caught us because NSF Song 3 (which we assumed was Level 1 based on numbering) was actually a different song. The mapping isn't sequential — it reflects the order the sound engine was developed, not the order songs appear in the game.

The fix was straightforward once we understood it: read the lookup table at $8060, build the NSF-to-internal mapping, then use the internal ID to find pointers. Two table reads instead of one, but still deterministic.

### Wizards & Warriors: Dynamic Dispatch

W&W took it further. Instead of a static table, the song pointers are **computed at runtime** by the NSF init routine. You can't just read them from ROM — you have to actually execute the init code with the song number in the A register and observe where it stores the pointers (at $0782/$0783).

```
Call $FFC0 with A = song_index
→ init routine computes and stores channel pointers at $0782+
→ read $0782/$0783 to get Sq1 pointer, +4 for Sq2, etc.
```

Our parser solved this by running the init through py65 and capturing the result. The routing is deterministic (same input always produces same output) but you can't short-circuit it — you must run the code.

## Kid Icarus: Everything Wrong at Once

Kid Icarus combines the worst aspects of every pattern above and adds new ones.

### The Three-Layer Routing Stack

**Layer 1: Game State → Song Select ($81E4)**

The game's NMI frame loop calls $81DA, which checks ZP $86. If non-zero, it jumps to $86CC (graphics/PPU update) or falls through to the song select dispatcher at $81E4. The dispatcher reads ZP $81 (a game-state value, NOT a song number) and does an indirect jump through a 10-entry table at $81F5:

```
$81E4: LDA $81        ; game state index (0-9)
$81E6: ASL A           ; multiply by 2
$81E7: TAX
$81E8: LDA $81F5,X    ; pointer lo
$81ED: LDA $81F6,X    ; pointer hi
$81F2: JMP ($0000)     ; indirect jump to state handler
```

Each handler is a game-state-specific routine that may or may not set up music. Song 1's handler ($8365) calls $855A which reads the area index from ZP $3A, does area-based music lookups, checks level progression, and writes configuration data to $0200. This is deeply game-integrated — it's not "play song 1," it's "update the audio state for the current game context."

**Layer 2: Area Table → Channel Config ($855A → $8772)**

$855A reads ZP $3A (current area: 0-3) and indexes into a table at $9370, which has 4 entries pointing to area-specific channel configuration blocks. The selected block gets processed by $8772, which copies structured data into the $0200 working area.

Each area has its own set of patterns, so the same "song" sounds different in Area 1 vs Area 3. This is environmental music — the game doesn't play "Overworld Theme," it plays "whatever music belongs to the area and level the player is currently in."

**Layer 3: Song Config Index → Data Pointers ($A896)**

Finally, a separate routine at $A896 reads $0350 (set by the game engine during the Layer 1/2 processing) and uses it to index a lookup at $ABAB, which gives an offset into a config table at $AC88. That config table contains the actual 13-byte channel blocks with data pointers.

```
$0350 → $ABAB[$0350] → offset → $AC88[offset] → 13 bytes:
  [0]    transpose
  [1]    flags
  [2]    unknown
  [3-4]  envelope IDs
  [5-6]  Sq1 data pointer
  [7-8]  Sq2 data pointer
  [9-10] Triangle data pointer
  [11-12] Noise data pointer
```

12 valid entries exist (indices 0-11). But $0350 isn't set by Layer 3 — it's set as a side effect of the game logic in Layers 1 and 2. The mapping from "what the player experiences as Song 1" to "$0350 = ?" is buried in the game's state machine.

### Why This Is Hard

| Game | Routing depth | Game state needed? | Static table? |
|------|-------------|-------------------|---------------|
| Castlevania | 1 level | No | Yes |
| Contra | 1 level | No | Yes (with offset) |
| Battletoads | 2 levels | No | Yes (two tables) |
| Wizards & Warriors | 1 level | No | No (computed) |
| **Kid Icarus** | **3 levels** | **Yes** | **Partially** |

Every other game's routing is **stateless** — given a song number, the pointers are deterministic regardless of what's happening in the game. Kid Icarus's routing is **stateful** — the same song number might produce different music depending on the area, level, and game progression. The music IS the game state.

## What We're Going to Try

### Approach 1: Brute-Force Config Enumeration (Fastest)

We have 12 valid configs in the $AC88 table. That's a small enough number to just play all of them through the harness and identify them by ear or by comparing against known game audio:

```python
for song_idx in range(12):
    cpu.memory[0x0350] = song_idx
    call(0xA896)           # load channel config
    for frame in range(300):  # play 5 seconds
        call(0xA9AF)       # per-frame update
        capture_apu_writes()
    export_to_wav_or_midi()
```

We don't need to understand the game's state machine. We just need to know which of 12 configs produces which music. Play them, name them, extract them. This bypasses Layers 1 and 2 entirely.

The downside: if any two configs produce different music depending on state that Layer 3 doesn't capture (like a variable we're not setting), we'd miss it. But the 13-byte config block looks self-contained — it has everything the play routine reads.

### Approach 2: Mesen $0350 Sniffing (Most Reliable)

Add a watchpoint on $0350 in Mesen. Play through the game, triggering each song. Record which $0350 value is active during each song. This gives us the definitive mapping without reverse-engineering the game logic.

```
Mesen watchpoint: Write to $0350
Play game → enter Underworld → $0350 changes to 7 → that's the Underworld song
           → enter Overworld  → $0350 changes to 2 → that's the Overworld song
           → boss fight       → $0350 changes to 4 → that's the Boss song
```

This is how we'd validate Approach 1's results. It requires human gameplay but only one playthrough.

### Approach 3: Trace-Match (Automated but Slow)

We already have a Mesen trace of Song 1. For each of the 12 configs, run 100 frames through the harness and compare the Sq1 period sequence against the trace. The config that matches is Song 1.

We tried this already and got no match — but that's because there may be additional state (transpose, tempo, or initial counter values) that differs between a cold harness start and the game's actual init. The trace shows period 105 as the first note; the harness with config 0 shows period 178. The difference could be a transpose offset or a different config index.

What we'll do: for each config, try multiple transpose values ($032B = 0, $0C, $18, $24) and check if any combination produces the trace's period sequence. This is computationally cheap — 12 configs × 4 transposes = 48 tests, each running 100 frames.

### Approach 4: Static Analysis of Game State (Deepest)

Trace the game code from $81E4 forward, mapping every conditional branch to determine which values of $81, $3A, $3E, $3F, $14, $15 lead to which $0350 output. Build a complete state→song routing table.

This is the most thorough approach but also the most time-consuming. We'd only do this if the simpler approaches fail — and with only 12 configs, they probably won't.

## The Plan

1. **Immediate**: Run all 12 configs through the harness, export 10 seconds of APU state each, convert to audio-comparable format
2. **Compare**: Match the Song 1 harness output against the Mesen trace by trying different init parameters
3. **Validate**: Once Song 1's config is identified, confirm 100% period match against the trace
4. **Map the rest**: Either by ear (play each config, listen) or by capturing more Mesen traces for 2-3 additional songs and cross-matching
5. **Extract all**: Once the config→song mapping is known, batch-extract all 12 songs through the harness → mesen_to_midi.py → REAPER projects

The goal is a complete set of ground-truth REAPER projects for the NES cartridge version of Kid Icarus, replacing the incorrect FDS NSF extraction.
