# NES Tone Database — Website Style Guide & Content Templates

## Audience

Two primary audiences with overlapping interests:

1. **Chiptune Musicians**: Want to understand HOW NES sounds are made so they can recreate or riff on them. Care about timbre, waveform character, envelope shaping, and what makes one game's pulse lead sound different from another's.

2. **ROM Hackers**: Want technical details about how music data is encoded in specific games so they can modify it. Care about driver architecture, data formats, pointer tables, and how the software transforms bytes into register writes.

Both audiences benefit from understanding the hardware layer (what the RP2A03 physically does) and how it maps to modern tools (MIDI, DAW, synthesizers).

## Content Principles

### 1. Explain the WHY, not just the WHAT
BAD: "Duty cycle: 50%"
GOOD: "50% duty cycle — a pure square wave. This is the warmest, fullest pulse tone the NES can produce. It has strong odd harmonics (3rd, 5th, 7th) that give it a hollow, clarinet-like quality. Most games use this for the lead melody because it cuts through the mix without being harsh."

### 2. Always give the two-column comparison
Every sonic property should be explained in two contexts:
- **NES Hardware**: What the RP2A03 chip physically does (register values, waveform generation, timing)
- **Modern Synth**: How to recreate it with ADSR envelopes, waveform selection, and MIDI CC automation in REAPER/ReapNES

### 3. Use concrete sonic analogies
Describe what things SOUND like, not just what they ARE:
- 12.5% duty = "thin and nasal, like a kazoo or a muted trumpet"
- 50% duty = "warm and hollow, like a clarinet or recorder"
- Triangle wave = "pure, dark bass — like a low flute or a sub-bass synth with the filter wide open"
- Short LFSR noise = "metallic, pitched — like hitting a trash can lid"
- Long LFSR noise = "white noise hiss — like radio static or wind"

### 4. Explain harmonic content
Musicians think in harmonics. Every waveform explanation should include:
- Which harmonics are present and how strong they are
- How this compares to familiar instruments or synth waveforms
- Why changing the duty cycle or waveform type changes the timbre

### 5. Show the extraction pipeline
For ROM hackers, always show the path from ROM bytes to audible sound:
```
ROM data → driver code → APU register writes → waveform generation → speaker
```
And our reverse path:
```
ROM → headless emulator → APU capture → Mesen CSV → MIDI → REAPER project
```

## Page Templates

### Game Page Template

```
[Breadcrumb: NES Tone Database > Game Name]

# Game Name
[Publisher] · [Year] · [Mapper] · [Driver Family]

## Sound Architecture
[2-3 paragraphs explaining HOW this game's music works. Not just "it uses 
a data-driven player" but WHAT that means for the sound — how notes get from 
ROM bytes to the speaker, what makes this game's sound distinctive.]

## Encoding Format
[Code block showing the actual byte format with annotations]
[Explain what a chiptune musician or ROM hacker would need to know to 
understand or modify this game's music data]

## Instruments

### Square 1 — Lead Melody
[Two-column table]

| NES Hardware (RP2A03) | Modern Synth (ReapNES/REAPER) |
|----------------------|-------------------------------|
| [How the hardware generates this specific sound — register values, 
waveform generation, envelope behavior] | [How to recreate it — 
which CC values, ADSR settings, duty cycle, and why these settings 
produce a similar result] |

**Harmonic Character**: [Detailed explanation of why this sounds the 
way it does — which harmonics are present, what acoustic instrument 
it resembles, how the envelope shapes the perception]

**Envelope Analysis**: [SVG sparkline + ADSR values + explanation of 
what the envelope DOES to the sound over time]

[Repeat for each channel: Square 2, Triangle, Noise]

## Tracks
[List of all extracted tracks with note counts and links to REAPER projects]
```

### How It Works Tab Template

```
## The NES Sound Chip (RP2A03)
[Deep dive into each channel with waveform diagrams, harmonic analysis,
and concrete sonic analogies]

## How We Extract the Music
[Step-by-step pipeline with diagrams:
ROM → Emulator → APU Capture → MIDI → REAPER]

## The ReapNES Synthesizer
[How the JSFX plugin recreates NES sounds:
Three-priority cascade, CC11/CC12 mapping, SysEx mode]

## Building REAPER Projects
[How generate_project.py creates playable DAW sessions:
Track layout, synth configuration, MIDI routing]
```

## Visual Design Rules

- Dark background (#0a0a0a), light text (#d0d0d0)
- Channel colors: Sq1=#ff6b6b, Sq2=#ffa94d, Tri=#51cf66, Noise=#748ffc
- Accent: #00ff88 (green) for headings, #00ccff (cyan) for links
- Monospace for code/data, system-ui for prose
- Expandable sections (details/summary) for deep dives
- SVG sparklines for envelope visualization
- ASCII waveform diagrams for duty cycles
