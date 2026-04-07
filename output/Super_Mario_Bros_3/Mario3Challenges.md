# Super Mario Bros. 3: What the ROM Emulator Taught Us

## The Setup

After cracking Kid Icarus with the headless NES emulator, we applied the same method to SMB3 — mapper 4 (MMC3), 256KB PRG, the most popular NES game ever made. It didn't go as smoothly.

## What We Built

### MMC3 Mapper Support

MMC3 uses a register-select + data-write protocol instead of MMC1's serial register:

```
Write to $8000 (even): select which internal register (0-7)
Write to $8001 (odd): set the selected register's value
```

PRG banking is 8KB granularity (vs MMC1's 16KB):
- **R6**: selects one switchable 8KB bank
- **R7**: selects another switchable 8KB bank
- **Bit 6** of the bank select register swaps which slots R6/R7 control
- Two banks are always fixed: second-to-last at $C000, last at $E000

This was ~40 lines of code in `nes_rom_capture.py` and required updating `_resolve_prg` to handle 4 × 8KB slots instead of 2 × 16KB.

### PPU VBlank Fix

The original emulator always returned `$80` from `$2002` (PPU status), simulating permanent VBlank. This worked for Kid Icarus but broke SMB3.

**The problem:** SMB3's boot code waits for VBlank to END:
```
$A930: LDA $2002     ; read PPU status
$A933: AND #$80      ; check VBlank flag
$A935: BNE $A930     ; loop until VBlank CLEARS
```

With VBlank permanently set, this loops forever.

**The fix:** Toggle VBlank on read (matching real NES behavior):
```python
if key == 0x2002:
    val = (0x80 if self._ppu_vblank else 0x00) | 0x40  # + sprite-0
    self._ppu_vblank = False  # cleared after read
    return val
```

VBlank gets set before each NMI via `trigger_nmi()`. This lets the game's PPU wait loops pass while maintaining the frame-based timing that the game expects.

### NMI Enable Tracking

On real hardware, NMI only fires when the game enables it by writing bit 7 to `$2000`. Our original emulator fired NMI unconditionally, which caused SMB3 to crash (NMI firing during boot before the game was ready).

**The fix:** Track `$2000` writes and only fire NMI when `_nmi_enabled` is True.

## What We Found in SMB3

### Sound Engine Architecture

SMB3's sound engine is split across two locations:

| Location | Bank | Content |
|----------|------|---------|
| $E2C0-$E900 | 31 (fixed) | Sound engine code: init, per-frame tick, channel processing |
| $A73F-$B547 | 28 (switchable at $A000) | Lookup tables: period tables, song data, envelope shapes |

The fixed bank contains the executable code. The switchable bank contains the data. This is the opposite of Kid Icarus, where the executable code was in a switchable bank and got copied to RAM.

### Song Request Protocol

```
$07F0 = song request register
$07F1 = current playing song
$07F5 = SFX request
$07F8 = volume/fade
```

To request a song: write the song number to `$07F0`. The per-frame tick at `$E2C0` reads `$07F0` and dispatches:
- `$07F0 == $7E`: special case (silence/reset)
- `$07F0 != 0`: new song → jump to `$E2E1` (song init)
- `$07F0 == 0`: no new request → continue playing current song

### The Init Problem

`$E2E1` (song init) only handles DMC setup:
```
STA $07F1      ; save as current song
TAY
LDA $E329,Y    ; DMC rate table
STA $4010
LDA $E309,Y    ; DMC sample address table  
STA $4012
LDA $E319,Y    ; DMC sample length table
STA $4013
STA $4015      ; enable all channels
RTS
```

This sets up the DMC channel but **does not** set up pulse, triangle, or noise channels. The channel data pointer at ZP `$6B/$6C` (used by `LDA ($6B),Y` throughout the engine) is never set by this code path.

### Where Channel Init Actually Happens

The NMI handler at `$F486` does:
1. Push registers
2. `JMP $9F40` (in bank 30, second-to-last)
3. `$9F40`: `STA $0378; LDA $03F1; JMP $F499`
4. `$F499`: Check `$03F1`, dispatch through a mode handler table

The mode handler table at `$F480/$F483` maps game states to frame handlers. Each game state (title screen, world map, level, etc.) has its own handler that calls the sound engine with the right parameters.

The channel data pointer `$6B/$6C` gets set by the **game state handler**, not by the sound engine. When the game transitions to a new state (e.g., entering a level), the state handler:
1. Loads the song number for that state
2. Writes it to `$07F0`
3. Sets up `$6B/$6C` to point to the song's note data in bank 28
4. Calls `$E2C0` which processes the request and starts playback

We can call `$E2C0` directly, but without the game state handler setting up `$6B/$6C`, the engine has no data to play.

## Why the Kid Icarus Techniques Failed

### Hot-Swap: Not Applicable

Kid Icarus copies song-specific 6502 code to RAM at `$03B0`. Swapping banks for one frame copies different code → different song. SMB3 doesn't do this. Its sound engine runs entirely from the fixed bank ($E000-$FFFF). There's no RAM code to swap.

### Direct Init: Incomplete

Kid Icarus's `$AC88` config system has self-contained channel configs: data pointers, envelope IDs, transpose values — everything needed to start a song. Setting `$0350` and calling `$A896` gave the engine everything it needed.

SMB3's `$E2E1` song init only handles DMC. The pulse/triangle/noise setup requires the game state handler's context. There's no single "play song N" entry point that sets up all channels.

### Mode Table Poke: Not Sufficient

Kid Icarus's ZP `$A0` mode poke worked because different banks had independent music engines that auto-initialized. SMB3's sound engine is in the fixed bank — changing the game mode changes which state handler runs, but the state handler needs PPU interaction (nametable updates, scroll position, sprite state) to function properly.

## What Would Actually Crack It

### Option 1: Find the Song Data Pointer Table

Somewhere in bank 28 (or the fixed bank) there must be a table mapping song numbers to data pointer values. If we find it, we can manually set `$6B/$6C` to the right pointer for each song, bypassing the game state handler entirely.

The sound engine reads `($6B),Y` extensively. The pointer `$6B/$6C` must be set to an address in the $A000-$BFFF range (bank 28) for each song. Finding the table that maps song number → data address would let us init any song directly.

### Option 2: Trace the NMI Handler Deeper

Follow the dispatch chain from `$F499` through all possible game states. One of them calls the sound engine with proper `$6B/$6C` setup. Finding that code path tells us exactly how to init a song.

### Option 3: Poke $6B/$6C Directly

If we find even one valid song data pointer (e.g., by trial-and-error or by looking at what Mesen shows), we can poke `$6B/$6C` directly and call `$E2C0`. The engine should play whatever the pointer points to.

### Option 4: Richer NMI Simulation

Run the full NMI handler (not just the sound engine call) with enough game state faked to progress past the title screen. This requires more PPU stub sophistication — returning plausible scroll values, handling `$2007` reads, simulating the IRQ scanline counter.

## What This Teaches About the ROM Emulator Approach

### Games Where It Works Well

- **Self-contained music engines** (Kid Icarus bank 1): music code in RAM, init is independent of game state
- **Config-table engines** (Kid Icarus bank 4 $AC88): song selection through a simple config system
- **Games with simple boot** (any game that plays music immediately after RESET)

### Games Where It Needs More Work

- **Fixed-bank engines** (SMB3): sound code in fixed bank, data pointers set by game state handlers
- **PPU-dependent init** (SMB3, most complex games): game state transitions require PPU interaction
- **Multi-stage boot** (SMB3): title screen has animation sequences that must complete before music

### The Continuum

```
Easy ←────────────────────────────────────────→ Hard

Boot-and-capture    Hot-swap     Config poke    State handler    Full PPU sim
(plays on boot)     (RAM code)   ($AC88)        (needs ZP setup) (needs graphics)

Kid Icarus title    KI bank 3    KI bank 4      SMB3             ??? 
```

The emulator handles everything left of SMB3. Cracking SMB3 requires moving one step right — finding how the state handler sets up `$6B/$6C` and replicating that without PPU.

## SMB3 NSF Note

Unlike Kid Icarus, SMB3's NSF file IS from the NES cartridge (same platform, no FDS issue). The existing NSF extraction pipeline should produce correct output for SMB3. The ROM emulator approach is most valuable for games where the NSF is wrong, missing, or unavailable.

That said, cracking SMB3 via ROM emulation would validate the approach on the most important NES game and prove it works for MMC3 mapper games — a much larger library than Kid Icarus's MMC1.
