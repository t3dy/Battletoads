# Finding Track Boundaries

## The Track Mapping Problem

Our NSF has 21 numbered songs. The game has named levels. The Mesen
trace captures gameplay sections without labels. We need to map:
NSF song number ↔ game level ↔ Mesen trace frame range.

## Track Names (from KHInsider and community sources)

| NSF # | Track Name | Game Context |
|-------|-----------|--------------|
| 1 | Title | Title screen |
| 2 | Interlude | Between-level cutscene |
| 3 | Ragnarok's Canyon | Level 1 |
| 4 | Level Complete | Victory jingle |
| 5 | Wookie Hole | Level 2 |
| 6 | Turbo Tunnel | Level 3 (walk section) |
| 7 | Turbo Tunnel Bike Race | Level 3 (bike section) |
| 8 | Arctic Caverns | Level 4 |
| 9 | Surf City & Terra Tubes | Levels 5 & 9 |
| 10 | Karnath's Lair | Level 6 |
| 11 | Volkmire's Inferno | Level 7 |
| 12 | Jet Turbo | Level 7 (jet section) |
| 13 | Intruder Excluder | Level 8 |
| 14 | Rat Race | Level 10 |
| 15 | Clinger-Winger | Level 11 |
| 16 | The Revolution | Level 12 (Dark Queen) |
| 17 | Boss Battle / Ending | Boss fights + ending |
| 18 | Unused | Cut content |
| 19 | Continue & Game Over | Short jingle (54s) |
| 20 | Pause Beat | Pause screen |
| 21 | Unused 2 | Cut content (3.6s) |

## The Critical Discovery: NSF Song 2 ≠ Level 1

The user captured the title screen + Level 1 (Ragnarok's Canyon) in
the Mesen trace. We assumed NSF Song 2 was the level 1 music.

**Wrong.** Song 2 is "Interlude" (the cutscene music). Song 3 is
"Ragnarok's Canyon" — the actual Level 1 music.

The Mesen trace frame ranges:
- Frames 212-5338: Title screen (Song 1)
- Frames 5600-5739: Short transition (likely jingle)
- Frames 5912-5961: Another short transition
- Frames 6085-11367: Level 1 gameplay (Song 3: Ragnarok's Canyon)

We've been comparing Song 2 (Interlude) against Level 1 (Ragnarok's
Canyon) — of course they sound nothing alike.

## How to Triangulate Track Boundaries

### Method 1: MP3 Reference (limited)

The Zophar MP3s are all 180s (3-minute loops) except:
- Track 19: 54.3s (Continue/Game Over — one-shot jingle)
- Track 21: 3.6s (Unused 2 — very short)

Since most tracks loop at exactly 180s, the MP3s don't help establish
loop points. They do confirm the total track count (21).

### Method 2: Online Track Listings

Community sources (KHInsider, VGMRips, Greatest Game Music) provide
track names and game-level mappings. This gives us the definitive
NSF number → level name mapping above.

### Method 3: Mesen Trace Silence Detection

Our `detect_segments()` function finds silence gaps:
```
Segment 1: frames 212-5338  (85.5s) = Title screen
Segment 2: frames 5600-5739 (2.3s)  = Transition jingle
Segment 3: frames 5912-5961 (0.8s)  = Short SFX
Segment 4: frames 6085-11367 (88s)  = Level 1 gameplay
```

### Method 4: Pattern Matching NSF vs Trace

For each Mesen trace segment, compare the opening frames against all
21 NSF songs. The one with the highest pitch/volume correlation is
the match.

### Method 5: Distinctive Feature Matching

The trace shows distinctive musical features we can match:
- Level 1 bass line: E1→G1→B1→A1 on pulse 2 with sweep vibrato
- Level 1 triangle: E2→D2→E2→A2→C4 (two-octave jump)
- Title screen: specific melodic pattern on pulse 1

Compare these pitch sequences against NSF song openings to find
the correct mapping.

## The Bass Run Discovery

The "fretless bass slide" the user hears is the triangle channel
jumping from A2 (MIDI 45) to C4 (MIDI 60) — a leap of 15 semitones
in one frame. Combined with the linear counter creating a rapid
decay envelope, this sounds like a quick upward run.

The pulse 2 bass line shows constant ±4 period oscillation every
frame — this is the NES sweep unit creating natural vibrato that
gives the bass its warmth and groove. Our NSF extraction doesn't
capture this oscillation.

## Track Boundary Verification Protocol

For each game, before extracting:

```
1. Get track listing from community sources (KHInsider, VGMRips)
2. Map NSF song numbers to level names
3. If Mesen trace available:
   a. Run detect_segments() to find boundaries
   b. Match each segment to an NSF song by pitch pattern
   c. Flag any segment that doesn't match any NSF song
4. Verify by listening: play NSF Song N alongside the MP3 Track N
5. Document the mapping in the game manifest JSON
```

Sources:
- [Battletoads NES Soundtrack - KHInsider](https://downloads.khinsider.com/game-soundtracks/album/battletoads-nes-1991)
- [Battletoads Soundtrack Review - Greatest Game Music](https://www.greatestgamemusic.com/soundtracks/battletoads-soundtrack/)
- [Battletoads NSF - Zophar's Domain](https://www.zophar.net/music/nintendo-nes-nsf/battletoads)
- [Battletoads VGM - VGMRips](https://vgmrips.net/packs/pack/battletoads-nes)
