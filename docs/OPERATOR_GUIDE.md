# NES Music Lab — Operator Guide

You (the human) do the emulator work. Claude does the data analysis. This document tells you exactly what to do at each step, what to bring back, and what format Claude needs it in.

---

## Setup

### Step 0: Install Mesen 2 to a Permanent Location

Your Mesen 2.1.1 was extracted to a temp RAR folder that got cleaned up. Fix this:

1. Locate `C:\Users\PC\Downloads\Mesen_2.1.1_Windows.zip`
2. Extract it to a permanent folder: `C:\Tools\Mesen\` (or wherever you like)
3. Run `Mesen.exe` from that folder — it will find your existing settings in `Documents\Mesen2\`
4. **Optional:** Pin it to taskbar or create a shortcut

Your existing settings, save states, and debugger labels (including the Castlevania III PPU labels) will carry over automatically.

### Step 1: Copy Lua Scripts

Two scripts are in `docs/scripts/`. You don't need to move them — Mesen can open them from anywhere — but for convenience:

```
docs/scripts/mesen_apu_capture.lua    ← APU trace recording
docs/scripts/mesen_memory_dump.lua    ← ROM inspection tools
```

### Step 2: Create Trace Output Directories

These already exist, but make sure the per-ROM folders are ready:

```
mkdir traces\castlevania
mkdir traces\darkwing_duck
mkdir traces\bionic_commando
```

(Or whatever ROM you're working with.)

---

## Task 1: Capture an APU Trace

This is the **most important task**. It captures exactly what the NES sound hardware does during music playback.

### What You're Doing

Recording every value the game writes to APU registers ($4000–$4017) with frame-accurate timing. This is the "ground truth" of what the music sounds like at the hardware level.

### Steps

1. **Open Mesen 2.** Load `Castlevania (U) (V1.0) [!].nes`.

2. **Open the Script Window.** Menu: `Debug → Script Window`
   - If you don't see this menu, make sure you're on Mesen 2 (not Mesen 1).

3. **Load the capture script.** In the Script Window:
   - Click the folder icon (Open) or paste the contents of:
     `C:\Dev\NESMusicLab\docs\scripts\mesen_apu_capture.lua`
   - Click the **Run** button (play icon ▶).
   - You should see the "NES Music Lab — APU Capture Script Loaded" message in the output pane.

4. **Get to the music you want.** For Castlevania:
   - **Title screen music:** Just let the title screen play.
   - **Stage 1 ("Vampire Killer"):** Start a new game — music begins immediately.
   - **Boss music:** Get to the first boss (or use save states if you have them).

5. **Start capture.** In the script console (text input at the bottom of the Script Window), type:
   ```
   startCapture()
   ```
   Press Enter. You'll see "APU CAPTURE STARTED."

6. **Let it play.** Don't press pause. Don't open menus. Let the game run for **30–90 seconds** — enough for the song to loop at least twice. You'll hear the music loop; that's what we want.

   - **Important:** Avoid triggering sound effects if possible. For Stage 1, don't move Belmont — just let the game idle. If the game doesn't idle nicely, that's okay, we'll filter SFX later.
   - **For title screen:** Perfect — no SFX, just music.

7. **Stop capture.** Type:
   ```
   stopCapture()
   ```
   It will tell you how many writes were captured and the duration.

8. **Save the file.** Type:
   ```
   saveCapture('C:/Dev/NESMusicLab/traces/castlevania/title')
   ```
   or for Stage 1:
   ```
   saveCapture('C:/Dev/NESMusicLab/traces/castlevania/stage1')
   ```

   This saves a CSV file at that path.

9. **Verify.** Check that the file exists and has content:
   - File should be in `traces/castlevania/title.csv` (or `stage1.csv`)
   - Open it — you should see rows like `0,$4000,191`
   - Size should be at least 50KB for a 30-second capture

### What to Capture (Priority Order)

For Castlevania, capture these in order:

| Song | How to Get There | Filename |
|------|-----------------|----------|
| Title screen | Just load the ROM | `traces/castlevania/title` |
| Stage 1 "Vampire Killer" | Start new game, don't move | `traces/castlevania/stage1` |
| Stage 2 "Stalker" | Get to Stage 2 (or save state) | `traces/castlevania/stage2` |
| Boss battle | Reach a boss | `traces/castlevania/boss` |

The title screen is the safest first capture — no SFX contamination.

### Troubleshooting

- **"Could not open file" error:** Use forward slashes in the path, not backslashes. `C:/Dev/NESMusicLab/traces/...` not `C:\Dev\...`
- **Very few writes (<1000):** The game might be paused or the music isn't playing. Make sure the game is running and you can hear sound.
- **Script console not visible:** The input box is at the very bottom of the Script Window. Resize the window if needed.
- **Script errors on load:** Make sure you're using Mesen 2, not Mesen 1. The Lua API is different.

---

## Task 2: Read the NMI Vector (Static Analysis Starting Point)

This tells us where the game's main interrupt handler is — the entry point for finding the music engine.

### Steps

1. **Load Castlevania** in Mesen 2 (if not already loaded).

2. **Open the Script Window** and load:
   `C:\Dev\NESMusicLab\docs\scripts\mesen_memory_dump.lua`

3. **Run the script**, then type in the console:
   ```
   findNMI()
   ```

4. **Copy the output** and paste it here. It will look something like:
   ```
   NMI vector: $C04A
   Dumping first 32 bytes of NMI handler:
   $C04A: 48 8A 48 98 48 ...
   ```

5. **Also run:**
   ```
   findReset()
   ```

### What Claude Does With This

The NMI vector tells us where the game's vertical blank interrupt starts. NES games almost always update music in the NMI handler or in a subroutine called from it. From the NMI address, we trace the call chain to find the music update routine.

---

## Task 3: Find APU Status Writes (Music Engine Fingerprint)

Every NES music engine writes to $4015 (APU status register) to enable/disable channels. Finding these writes helps locate the music init and play routines.

### Steps

1. With the memory dump script loaded, type:
   ```
   searchBytes(0x8000, 0xFFFF, {0x8D, 0x15, 0x40})
   ```
   This searches for `STA $4015` instructions in the ROM.

2. **Copy all results** and paste them here. There will probably be 2–10 matches.

3. **Also search for JSR patterns** near the NMI:
   If the NMI was at (for example) $C04A, check what it calls:
   ```
   dumpHex(0xC04A, 64)
   ```
   Copy the hex dump.

---

## Task 4: Dump a Suspected Song Table Region

Once Claude identifies a likely song table location from the static analysis, you'll dump that region.

### Steps (Claude will give you the exact addresses)

Claude will say something like: "Dump 256 bytes starting at $8200."

You type:
```
dumpHex(0x8200, 256)
```

Or to save to a file:
```
dumpRegion(0x8200, 256, 'C:/Dev/NESMusicLab/traces/castlevania/song_table.bin')
```

And to read a pointer table:
```
readPointerTable(0x8200, 16)
```
This reads 16 consecutive 16-bit pointers and shows where each one points.

---

## Task 5: Use the Mesen Debugger (Advanced)

You've used it before (CDL files exist for several ROMs). For music engine tracing:

### Set a Write Breakpoint on $4000

1. **Open Debugger:** `Debug → Debugger` (or Ctrl+D)
2. In the Breakpoints panel, click **Add**.
3. Set:
   - **Type:** Write
   - **Address:** $4000
   - **Memory Type:** CPU
4. Click OK.
5. **Resume execution** — the debugger will break the next time the game writes to $4000 (Pulse 1 register 0).
6. **Look at the call stack** in the debugger — this shows you exactly which subroutine is writing to the APU. The top of the call stack is the music engine's channel update routine.
7. **Copy the call stack** and the current instruction/surrounding code and paste it here.

### Set a Breakpoint on the NMI

1. Add breakpoint: **Type:** Execute, **Address:** (the NMI address from Task 2)
2. Step through with F10 (step over) or F11 (step into) to see what the NMI calls.
3. Look for JSR instructions — one of them calls the music update.

---

## Task 6: Use Mesen's Trace Logger (Alternative to Lua Script)

If the Lua script doesn't work for any reason, Mesen has a built-in trace logger.

1. `Debug → Trace Logger`
2. Set up:
   - **Log to file:** Check this, set path to `C:\Dev\NESMusicLab\traces\castlevania\trace_log.txt`
   - **Format:** Default is fine
3. Start logging, let music play for 30 seconds, stop logging.
4. The output will be a full CPU trace (huge file). Give it to Claude — we'll filter for APU writes.

---

## What to Bring Back to Claude

After each task, paste the output directly into the chat. Claude needs:

| Task | What to Paste |
|------|--------------|
| APU Capture | Just tell Claude the file path — the pipeline reads the CSV directly |
| NMI Vector | The console output from `findNMI()` and `findReset()` |
| APU Status Writes | The console output from `searchBytes(...)` |
| Hex Dumps | The full console output from `dumpHex(...)` or `readPointerTable(...)` |
| Debugger Info | Screenshot or text copy of the call stack and surrounding assembly |

### Format for Hex Dumps

When pasting hex from Mesen, keep the address prefix. Like this:
```
$C04A: 48 8A 48 98 48 A9 01 8D 00 20 ...
```

Claude can parse this directly.

---

## Recommended First Session

Do Tasks 1–3 in one sitting. This gives Claude:
1. A real APU trace to analyze (Task 1)
2. The NMI entry point for static analysis (Task 2)
3. APU write locations for music engine identification (Task 3)

That's enough to start cracking the Konami driver. Everything after that, Claude will give you specific addresses and instructions.

**Start with the title screen trace** — it's the cleanest (no SFX) and the easiest to capture.
