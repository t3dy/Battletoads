# Day 4 Update — March 31, 2026

## What Happened Today

### Two Repos Integrated
The NESMusicStudio (extraction pipeline) and ReapNES-Studio (synth/REAPER
tooling) repos were brought together. The Console synth from ReapNES-Studio
replaced the old APU synth in the project generator.

### Projects/ Folder Built
701 REAPER projects across 34 games, organized as self-contained folders:
`Projects/<Game>/midi/*.mid + *.rpp`. Each RPP loads ReapNES_Console.jsfx
with keyboard input configured. `scripts/build_projects.py` rebuilds all.

### RPP Generator Rewritten
`generate_project.py` was rewritten from scratch to match the proven
Console_Test.rpp structure from ReapNES-Studio. Five critical fixes:

1. **Full RPP header** (was 10 lines, now 100+ from working reference)
2. **REC 5088 on ALL tracks** (was 0 on unarmed — broke keyboard routing)
3. **Added 6 missing track fields** (PANLAWFLAGS, SHOWINMIX, etc.)
4. **Keyboard Mode ON** (slider34=1)
5. **Game-specific ADSR presets** (Castlevania, Mega Man, Metroid)

### 14 New Games Added
Dragon Warrior, Final Fantasy, Metal Gear, Ultima (Exodus + Quest of Avatar),
Faxanadu, Gargoyle's Quest II, Goonies II, Kid Icarus, Legendary Wings,
Section Z, Silver Surfer, Strider, Trojan. NSFs extracted and processing.

## What We Learned

### The Critical Gap: Console Synth Ignores CC11/CC12
The biggest discovery. NSF-extracted MIDIs carry per-frame CC11 (volume)
and CC12 (duty cycle) automation — this IS the ground-truth envelope from
the NES sound driver. The old APU synth read these. The Console synth
ignores them, using its own ADSR instead.

This means file playback currently uses generic ADSR curves instead of
the actual per-frame envelopes baked into the MIDI files.

### Every Game Has a Different Envelope Signature
Analyzed 5 games in depth:

| Game | Envelope Type | CC11/note | Note Duration |
|------|-------------|-----------|---------------|
| Mario | Uniform 5-step decay (64>56>48>40>32) | 5.0 | Fixed 7 frames |
| Castlevania | Fast 4-step decay (32>24>16>8) | 4.1 | Variable (50ms-1.4s) |
| Mega Man 2 | Minimal 2-step (64>16) + 1-frame arpeggios | 1.4 | 1.5 frames avg on P2 |
| Metroid | Crescendo-decrescendo (breathes up AND down) | 8.2 | 38 frames avg |
| Contra | Huge attack transient (127>51>42>34>25>17) | 6.1 | Moderate-long |

These are not small differences — they define each game's sonic identity.
Standard ADSR cannot reproduce Metroid's breathing crescendo or Mega Man 2's
1-frame arpeggio texture.

### The Fidelity Hierarchy Is Now Documented
Baked into CLAUDE.md:
1. ROM/Trace (frame-level ground truth)
2. NSF emulation (per-frame CC automation)
3. MIDI file (CC data IS the envelope)
4. ADSR approximation (keyboard only, lowest fidelity)

### Infrastructure Updated
- **CLAUDE.md**: New invariants (CC ground truth, dual-mode synth, zero config)
- **reaper_projects.md**: Rewritten for Console synth + full RPP structure
- **synth_fidelity.md**: New rule file — CC/ADSR dual-mode contract, per-channel
  envelope specs learned from CV1/Contra analysis
- **Memory**: Synth dual-mode gap documented for future sessions

## What's Changed In Our Approach

### Before Today
Synth was a simple register player. MIDI files drove everything through CC.
Projects were minimal RPPs that relied on the user to configure REAPER.

### After Today
Synth is Console with ADSR + keyboard mode. But CC playback is broken.
Projects are full-featured RPPs with zero-config keyboard input.
The generator carries game-specific ADSR presets for keyboard approximation.

### The Plan Going Forward (3 Layers)

**Layer 1 (Critical): Port CC11/CC12 to Console Synth**
~30 lines of code. Port `lp_cc_active[]` from APU to Console. When CC
arrives, bypass ADSR. When no CC (keyboard), use ADSR. This fixes file
playback for all 701 projects without touching any MIDI files.

**Layer 2 (Mechanical): Rebuild Projects**
`python scripts/build_projects.py --force` after Layer 1. One command.

**Layer 3 (Iterative): Game-Specific Tuning**
Ear-check each game's keyboard ADSR preset. This is the only part that
needs LLM/human judgment. CC playback is deterministic — it'll sound
right once the synth reads it.

## Open Questions

1. Should we keep both APU and Console synths available, or consolidate?
2. How many games need individual ADSR tuning vs generic defaults?
3. Should vibrato (rapid period oscillation) be converted to pitch bend?
4. Should we expand the noise drum mapping beyond 3 buckets?
5. Some games (Zelda overworld, Ninja Gaiden opening) produce empty MIDIs
   from the NSF pipeline — likely silent intro tracks or NSF issues.
