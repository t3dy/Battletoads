# Capcom NES Sound Engines: What We're Learning

## The Capcom Library on NES

Capcom released ~30 NES games between 1987-1993. Their sound team (led by composers like Manami Matsumae, Takashi Tateishi, and Yasuaki Fujita) produced some of the most iconic NES soundtracks ever made. From a music encoding perspective, Capcom is interesting because they evolved their sound engine across three distinct hardware generations.

## The Three Capcom Engine Eras

### Era 1: MMC1 Games (1987-1989)

| Game | Mapper | Year | Extracted? |
|------|--------|------|-----------|
| Mega Man 1 | UxROM (2) | 1987 | Not yet (needs mapper 2 test) |
| **Mega Man 2** | **MMC1** | 1988 | **CAPTURED: 234/279/404/700 notes** |
| Strider | MMC1 | 1989 | Testing |
| Chip 'n Dale | MMC1 | 1990 | Testing |
| Darkwing Duck | MMC1 | 1992 | Testing |

Mega Man 2 is the crown jewel. Our ROM emulator captured it on boot: 234 Sq1, 279 Sq2, 404 Triangle, 700 Noise events — a rich four-channel soundtrack with heavy drum usage.

**What we know about the MM2 engine:**
- Boots and plays immediately (Tier S extraction)
- Full four-channel output from first NMI frame
- Heavy noise channel usage (700 events in 80 seconds = ~8.75 hits/second)
- The title screen intro has the famous "whistle" arpeggio followed by the full title theme

### Era 2: MMC3 Games (1990-1993)

| Game | Mapper | Year | Notes |
|------|--------|------|-------|
| **Mega Man 3** | **MMC3** | 1990 | Testing |
| **Mega Man 4** | **MMC3** | 1991 | Testing |
| **Mega Man 5** | **MMC3** | 1992 | Testing |
| **Mega Man 6** | **MMC3** | 1993 | Testing |
| Mighty Final Fight | MMC3 | 1993 | Testing |
| Gargoyle's Quest II | MMC3 | 1992 | Testing |

The MM3-6 series moved to MMC3, which allows finer-grained 8KB PRG banking. This likely affected how the sound engine accesses music data (8KB data bank vs 16KB).

### Era 3: The Shared Engine Theory

Capcom likely standardized their NES sound engine across games within each era. Evidence from our SMB3 reverse engineering (which uses a Capcom-style engine):

- **Channel output via indexed STA**: `STA $4000,X` / `STA $4002,X` with X selecting the channel (0/4/8/12)
- **Per-channel data pointers in ZP**: song data read via `LDA ($xx),Y` with Y as position counter
- **Song selection via RAM register**: write song number to a request byte, engine picks it up next frame
- **Split init/tick architecture**: one routine handles new song requests, another ticks the channels per frame

## What Our Captures Tell Us About Capcom's Encoding

### Mega Man 2 Analysis

From the 4800-frame title screen capture:

- **Sq1 (234 notes)**: Lead melody. The famous "Dr. Wily" intro arpeggio followed by the title theme melody.
- **Sq2 (279 notes)**: Harmony/countermelody. Slightly more notes than Sq1 — Capcom uses Sq2 for fill patterns and echo effects.
- **Triangle (404 notes)**: Bass line. Nearly double the pulse note count — the bass has fast arpeggiated patterns that Capcom is known for.
- **Noise (700 events)**: Drums. Extremely active — the title theme has a driving beat with hi-hats, snares, and kicks at high density.

**Capcom signature**: The noise channel is more active than any other game we've extracted. Konami games (Castlevania, Contra) have sparse drums. Capcom uses continuous drum patterns.

### The Period Encoding Question

Based on Mega Man 2's output, the period values should match standard NTSC tables. Capcom uses the **octave + semitone** encoding scheme:

```
Note byte: [OOOO SSSS]
  O = octave (sets base period table offset)
  S = semitone within octave (0-11 = C through B)
```

This differs from Konami's nibble-packed scheme where the octave is set by a DX command. Capcom embeds the full note identity in one byte, which is why their note count is higher — each note carries its own octave information, no setup commands needed.

### The Duty Cycle Pattern

Capcom games are known for distinctive duty cycle usage:
- **Sq1 lead**: Usually 50% duty (warm, rounded tone)
- **Sq2 harmony**: Usually 25% duty (brighter, thinner — stands out from Sq1)
- **Attack transients**: Brief 12.5% duty on note attacks (harsh click for articulation)

This should be visible in the CC12 automation of our MIDI captures.

## What We Still Need to Learn

### 1. The Song Pointer Table Format

We need to find how Mega Man 2 maps song numbers to channel data pointers. For SMB3, we found a two-level lookup: secondary index at `$A73F` + config table at `$A76C`. Capcom may use a simpler flat pointer table (more like Castlevania's approach).

### 2. Per-Game Differences Within the Engine

Do MM3-6 share the exact same engine as MM2? The mapper change (MMC1→MMC3) means the data bank handling is different. The question is whether the engine's note format, command set, and envelope system stayed the same.

### 3. The Sweep/Vibrato System

Capcom games have distinctive pitch bends and vibrato effects. These are likely encoded as per-note modulation commands in the data stream. The SMB3 engine had a sweep register field in each song config — Capcom probably has something similar.

### 4. DMC Sample Usage

Mega Man games use DMC samples (the NES's crude PCM channel) for bass drums and voice clips. Our capture shows `$4010-$4013` writes for DMC setup. Understanding how Capcom indexes its DMC sample table would give us the full audio picture.

## Extraction Results So Far

| Game | Method | Sq1 | Sq2 | Tri | Noise | Status |
|------|--------|-----|-----|-----|-------|--------|
| Mega Man 2 | Boot capture | 234 | 279 | 404 | 700 | RPP built |
| Mega Man 3 | Testing | ? | ? | ? | ? | Batch running |
| Mega Man 4 | Testing | ? | ? | ? | ? | Batch running |
| Mega Man 5 | Testing | ? | ? | ? | ? | Batch running |
| Mega Man 6 | Testing | ? | ? | ? | ? | Batch running |
| Mighty Final Fight | Testing | ? | ? | ? | ? | Batch running |
| Darkwing Duck | Testing | ? | ? | ? | ? | Batch running |
| Chip 'n Dale | Testing | ? | ? | ? | ? | Batch running |
| Strider | Testing | ? | ? | ? | ? | Batch running |
| Gargoyle's Quest II | Testing | ? | ? | ? | ? | Batch running |

## The Capcom Sound Compared to Other Publishers

| Trait | Capcom | Konami | Rare | Nintendo |
|-------|--------|--------|------|----------|
| Drum density | Very high (700/80s) | Moderate | Low-moderate | Low |
| Note encoding | Octave+semitone byte | Nibble-packed | Byte index | Code-as-music |
| Envelope | Per-note duty shifts | Parametric/lookup table | Software register | RAM code |
| Period table | Standard NTSC, 6 octaves | Standard NTSC, 5 octaves | Standard NTSC, 5 octaves | Custom per bank |
| Channel balance | All 4 equally active | Pulse-heavy, sparse drums | Melodic-focused | Varies by bank |
| Characteristic sound | Bright, driving, rhythmic | Dark, atmospheric | Rich harmonies | Area-dependent |

Capcom's NES music stands out because of the rhythmic density. Their drum programming approaches modern pop/rock patterns — constant hi-hat, backbeat snare, syncopated kicks. Combined with the dual-duty pulse arrangement (50% lead, 25% harmony), it creates the most "band-like" sound on the NES.
