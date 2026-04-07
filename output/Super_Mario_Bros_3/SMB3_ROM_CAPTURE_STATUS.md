# Super Mario Bros. 3: ROM Capture Status

## What We Did

Applied the headless NES emulator approach from Kid Icarus to SMB3.

### Mapper Support Added

Built MMC3 (mapper 4) support for `nes_rom_capture.py`:
- 8KB PRG banking with register-select + data-write protocol
- Two switchable banks (R6 at $8000, R7 at $A000) and two fixed banks ($C000/$E000)
- PRG mode bit controls whether R6 or second-to-last is at $8000

### PPU Stub Improved

Fixed the VBlank handling — the original stub always returned $80 (VBlank set), which caused SMB3 to spin forever waiting for VBlank to clear. New behavior:
- VBlank flag (`$2002` bit 7) sets before each NMI, clears when read
- Sprite-0 hit (`$2002` bit 6) always set
- NMI only fires when enabled (`$2000` bit 7)

### Boot Result

The game boots past the initial PPU wait loops and reaches its NMI-driven main loop. But the title screen curtain animation doesn't complete because it requires PPU state we can't fake (nametable updates, sprite positions, scroll registers).

### Sound Engine Located

- **Music data**: 8KB bank 28 (maps to $A000-$BFFF via R7)
- **Sound engine code**: fixed bank 31 ($E000-$FFFF), with routines at $E2C0-$E900
- **Song request register**: `$07F0` (write non-zero to request song)
- **Song init**: `$E2E1` — sets up DMC, enables channels, but doesn't set channel data pointers
- **Per-frame tick**: `$E2C0` → checks `$07F0`, dispatches to `$E2E1` on new song
- **Channel data pointer**: ZP `$6B/$6C` — never gets set by our init path
- **Song tables**: DMC config at `$E309/$E319/$E329` (indexed by song number)

### What's Missing

The `$E2E1` song init only handles DMC setup (sample rate, address, length) and channel enable. The pulse/triangle/noise channel initialization — including setting `$6B/$6C` to the note data pointer — must happen through the NMI handler's broader frame processing path, not through `$E2C0` alone.

SMB3's sound engine is called from the NMI handler at `$F486` → `$9F40` → `$F499`, which dispatches through a mode-dependent handler chain. The music init happens as a side effect of the game mode transition, not as a standalone "play song" call.

## What Would Fix It

1. **Trace the NMI handler's full dispatch chain** to find where the channel data pointers get set. The mode handler at `$F499` reads `$0100/$0101` and dispatches to the current game state handler. That handler calls the sound engine with the right context.

2. **Find and poke the game mode variable** (equivalent to Kid Icarus's `$A0`). SMB3's `$0100` area likely holds the game state. Setting it to the "overworld map" state would trigger the overworld music init.

3. **Alternatively**, build a more complete NMI simulation that includes the game's task scheduler, not just the sound engine call.

## Why SMB3 Is Harder Than Kid Icarus

| Aspect | Kid Icarus | SMB3 |
|--------|-----------|------|
| Mapper | MMC1 (simple serial) | MMC3 (register select + data) |
| Sound location | One bank (bank 4) + fixed bank | Split: bank 28 (data) + bank 31 (code) |
| Song init | Sets up channel state directly | Goes through multi-stage mode dispatch |
| PPU dependency | Boot only (title screen works) | Ongoing (curtain animation, mode transitions) |
| Music in RAM | Yes ($03B0) — hot-swap works | No — engine runs from fixed bank |
| Mode table | Simple 10-entry table | Complex multi-level dispatch through $0100 |

Kid Icarus's hot-swap technique worked because songs were self-contained code blocks copied to RAM. SMB3's sound engine runs from the fixed bank and reads data from a switchable bank — there's no RAM code to swap.

## Next Steps

The emulator infrastructure is solid. MMC3 mapper works. PPU VBlank toggle works. The remaining challenge is SMB3-specific: finding the game mode dispatch path and the channel data initialization.

For immediate extraction, the existing NSF pipeline for SMB3 should work fine — SMB3's NSF matches the NES cart (same platform, no FDS issue). The ROM emulator approach is most valuable for games where the NSF is wrong or missing.
