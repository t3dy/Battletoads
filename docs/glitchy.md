# How Vampire Killer Became Glitch Art

## The Bug

One line of JSFX code turned Castlevania into an unrecognizable mess:

```jsfx
kb_mode && ch_mode < 4 ? ( ch = ch_mode; );
```

This is the **Keyboard Mode** remap. It's designed for live keyboard play:
when you press a key on your MIDI keyboard, whatever channel it sends on
gets remapped to the track's NES channel. So if your keyboard sends on
ch 0 but you're on the Triangle track (ch_mode=2), the note gets
remapped to ch 2. Useful feature.

**The problem:** each REAPER track loads the SAME multi-track MIDI file.
That file has events on channels 0, 1, 2, and 3. When Keyboard Mode is
ON, **every event from every channel** gets remapped to the track's own
channel. The channel filter (`ch != ch_mode ? use_msg = 0`) never fires
because `ch` was already overwritten to match `ch_mode`.

## What Each Track's Synth Actually Heard

### Track 1 (Pulse 1, ch_mode=0)

**Should have heard:** 206 notes, 840 CC11 updates (Pulse 1 melody)

**Actually heard:** 814 notes, 1,959 CC11 updates — the entire game
playing on a single pulse oscillator simultaneously:

- Pulse 1 melody (206 notes, ch=0) ← correct
- Pulse 2 harmony (211 notes, ch=1 → remapped to ch=0) ← WRONG
- Triangle bass (85 notes, ch=2 → remapped to ch=0) ← WRONG
- Noise drums (312 notes, ch=3 → remapped to ch=0) ← WRONG

All four channels fighting over one oscillator. Every 16 ticks,
CC11 from one channel overwrites the volume set by another.

### The Cascade

At tick 0, Pulse 1 gets CC11=32 (vol=4). Correct. But then at the
same tick, Triangle sends CC11=127 (vol=15) — also remapped to ch=0.
Volume jumps to 15. Then Pulse 2 sends CC11=40 — vol drops to 5.

This happens every frame (60Hz). The volume is a seizure-inducing
random walk as four independent envelope streams clobber each other
at 16-tick intervals.

Meanwhile, notes from all four channels trigger on the same pulse
oscillator. The pitch jumps between melody, harmony, bass, and drum
mappings. Drum notes (GM 36/38/42) get interpreted as melodic notes
on the pulse channel, producing pitches that don't exist in the
original composition.

Multiply this by 4 tracks (each one doing the same remapping), and
you get four copies of this chaos layered on top of each other.

## The Fix

Keyboard Mode should only remap when the event comes from a keyboard
(live input), not from file playback. The simplest fix: disable the
keyboard remap for CC-driven channels (where CC11/CC12 have been
received), since those are always from file data. For events from
the file, let the original MIDI channel stand — the channel filter
will naturally accept matching events and reject the rest.

```jsfx
// BEFORE (broken):
kb_mode && ch_mode < 4 ? ( ch = ch_mode; );

// AFTER (fixed):
// Only remap for keyboard input, not file playback.
// If this channel already has CC data, it's from a file.
kb_mode && ch_mode < 4 && !cc[ch_mode * 4] ? ( ch = ch_mode; );
```

Actually, the real fix is even simpler: don't remap at all when CC11
data is present for this track. The channel filter does the right
thing on its own. The keyboard remap is only needed when a human
presses keys on a MIDI controller that might send on the wrong channel.
