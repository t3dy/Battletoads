# Kid Icarus: Why This Is Hard (And What Would Actually Work)

## The Question

For Castlevania and Contra, we found the song data quickly: pointer table in ROM, follow the pointers, decode the note stream, done. Why can't we do the same thing here?

## The Honest Answer

The approach that worked for Castlevania DOES apply — but I've been overcomplicating it by trying to trace the game's init logic instead of doing what we actually did for CV1 and Contra.

### What We Actually Did for Castlevania

We didn't reverse-engineer the Castlevania music driver from scratch. We:

1. **Used the NSF file** — which wraps the game's driver with clean init/play entry points
2. Called init(song_number), called play() per frame, captured APU writes
3. The NSF IS a working harness — someone already extracted the driver

### What's Different About Kid Icarus

The NSF is from the **wrong platform** (FDS vs NES cart). The music is different. So we can't use the existing NSF.

But the NES cartridge ROM has the same kind of driver code. The per-frame play routine is at $A210, called from $A2E4. The channel processing runs through $A36E (note writing), $A3C3 (timing checks), and the $A4xx-$A8xx song routines. The APU output happens at $400x register writes through $A36E.

### Where I Went Wrong

Instead of finding the init and play entry points (like the NSF gives us for CV1), I got pulled into reverse-engineering the game's state machine — the area tables, the task scheduler, the $0200 dispatch records, the multi-layer routing. That's the game logic, not the music driver.

The music driver has a simple interface:
- **Init**: set state variables in $0380/$0388/$0381/$0389 to a bitmask value, which activates channel handlers
- **Play**: call $A210 once per frame

The problem is I don't know what bitmask values correspond to which songs, and the init path that sets them is deeply integrated with game state.

## What Would Actually Work (The CV1 Method Applied)

### Option 1: Mesen Memory Watch

Set a write watchpoint on $0380 in Mesen. Play the game. When a new song starts, $0380 changes. Record the value and which song was playing. Do this for each area/song in the game. Takes one playthrough (~30 minutes of gameplay).

This is the equivalent of what the NSF does for us automatically — it maps song numbers to state values. We just need to build that mapping manually.

### Option 2: Build a Minimal NSF From the NES Cart

This is what SHOULD have been done from the start. An NSF is just:
- Header (song count, init address, play address)  
- The music driver code
- The music data

For Kid Icarus NES cart:
- Music code: bank 4 ($8000-$BFFF = 16KB)
- Init: a routine that sets $0380 = song_bitmask and calls any necessary setup
- Play: $A210

We could build a custom NSF by:
1. Extracting bank 4
2. Writing a small init stub that takes A = song_number and sets the right $0380 value
3. Using $A210 as the play address

The only missing piece is the $0380 mapping — which Option 1 gives us.

### Option 3: Brute Force the State Space

$0380 is a bitmask byte (8 possible bit positions × 4 state variables = 32 combinations). But the engine only uses a subset. Try all 256 possible $0380 values, run 50 frames of $A210 for each, and check which ones produce APU writes with valid periods.

This is the "jukebox" approach — play every slot, listen to what comes out.

### Option 4: Just Capture Traces

We already proved that Mesen captures → mesen_to_midi.py works perfectly for Song 1. The entire game has maybe 10 distinct songs. Capturing 10 Mesen traces (~2 minutes each) gives us ground-truth MIDI for everything. No reverse engineering needed.

This is the slowest approach but has zero risk of getting the wrong notes. And we already have the tooling.

## The Lesson

For CV1/Contra, the NSF abstracted away the song routing problem. The NSF format says "here's init, here's play, song number goes in A register." We never had to figure out how the game selects songs because the NSF already solved that.

For Kid Icarus, we're doing the work the NSF ripper already did for other games — mapping game state to music state. The core problem isn't that the music engine is fundamentally different (it has notes, periods, envelopes, and per-frame updates just like every other NES game). The problem is that no one has built an NSF for the NES cart version, so we're building that mapping from scratch.

The fastest path: Option 3 (brute-force $0380) to find which values produce music, combined with Option 4 (traces) to validate. This gets us all the songs without understanding the game logic.
