# Web Research: Super Mario Bros. Music Theory

## General Background

Composed by Koji Kondo (b. 1961), Nintendo's first dedicated composer.
Six themes: Overworld (~90s), Underground (~13s), Underwater (~26s),
Castle (~9s), Star/Invincible (~3s loop), Ending (~7s). All double in
speed when the timer drops below 100. Uses 4 of 5 APU channels (no
DPCM). Entire game is 40KB. Added to the American National Recording
Registry in 2023.

Influences: Latin/Caribbean music, T-Square, Deep Purple, Yes, ELP,
Herbie Hancock, Chick Corea, Casiopea, The Beatles. The soundtrack
was composed on a small keyboard and programmed in 6502 assembly.

## NES Channel Assignments (all tracks)

| Channel | Type | Role |
|---------|------|------|
| Pulse 1 | Square wave (variable duty) | Lead melody |
| Pulse 2 | Square wave (variable duty) | Harmony / counterpoint |
| Triangle | Triangle wave (no volume ctrl) | Bass line |
| Noise | White noise | Percussion / rhythm |
| DPCM | Sample playback | Unused in SMB1 |

When a sound effect plays, Pulse 2 drops out. Triangle has no
hardware volume control (only on/off gating). The NES mixes all
channels non-linearly.

## The "Mario Cadence" (cross-cutting harmonic device)

Progression: **bVI - bVII - I** (in C major: Ab - Bb - C)

Both bVI and bVII are borrowed from the parallel minor. Found in
fanfares, level-complete jingles, power-up SFX, and within the
Overworld theme. Described as having roots in late Romantic techniques
(Wagner, Debussy). The bVII functions like a dominant without the
classical leading tone.

## Track 1: Overworld / Ground Theme

**Key:** C major
**Time Signature:** 4/4 (with 2/4 feel)
**Tempo:** ~100 BPM (swing feel on drums)
**Duration:** ~90 seconds (loops)
**Form:** Intro - {A-B-C - A-D-C-D} repeating without intro

### Opening Melody

The iconic notes: **E E E, C E G** (then G an octave lower in bass).
These outline a C major triad (C-E-G).

Intervals: E-E unison, E-C minor 3rd down, C-E major 3rd up,
E-G minor 3rd up.

### Chord Progression

- A section: C - F - C - F - C - G
- B section: C - F - C - F, then C - F - **Ab - Bb - C** (Mario Cadence)
- C section: Ab - C - Ab - C, then Ab - C - D7 - G (bVI alternating
  with I, then secondary dominant of C)
- D section: C - F - G - C
- Intro riff: D7 - G (secondary dominant resolving to G)

### Rhythmic Characteristics

- Drums play a **cha-cha swing feel** while melodic voices play
  **straight rhythms** -- this disjunction creates the "bouncy"
  sensation
- A & B sections: skipping, bouncy drum pattern
- C section: aggressive straight sixteenth notes on drums
- D section: reggaeton-style beat pattern
- 3+3+2 "half-clave" pattern (from Latin music)
- Melody uses triplets, off-beats, heavy syncopation
- Staccato on most notes, strategic legato at phrase endings

### Channel Roles

- Pulse 1: lead melody
- Pulse 2: homorhythmic harmony (same rhythm, different pitches)
- Triangle: bass (third voice in intro, proper bass elsewhere)
- Noise: kick, snare, closed hi-hat simulation

### What Makes It Memorable

Straight melody over swung drums, C major triad arpeggio opening,
modal mixture (bVI-bVII-I), Latin/calypso rhythmic foundation,
syncopation matching Mario's movement. Fast arpeggios and counterpoint
create the illusion of greater complexity than 3 melodic voices.

## Track 2: Underground Theme

**Key:** C Dorian (C-D-Eb-F-G-A-Bb)
**Time Signature:** Odd meter (compared to 6/4)
**Tempo:** Slower than overworld
**Duration:** ~13 seconds (loops)

### Scale/Mode

C Dorian differs from C natural minor by the raised 6th (A natural
instead of Ab). This gives the iv chord (F) a major quality.

### Melodic Characteristics

- Iconic riff is a **chromatic ascending pattern** (half-steps)
- Flatted seventh (Bb) essential to the riff
- Melody carried by the **bass register** (triangle), unlike overworld
- Described as "sparse, bass melody in an odd meter"

### Influence

Very similar to the bassline of "Let's Not Talk About It" from
Lee Ritenour's *Friendship* (1979), nearly note-for-note. That track
is in 6/4 time.

## Track 3: Underwater Theme

**Key:** C major
**Time Signature:** 3/4 (waltz)
**Tempo:** ~100-120 BPM
**Duration:** ~26 seconds (loops)

### Harmonic Analysis

The most harmonically sophisticated track:
- Secondary dominants
- Passing augmented chords
- Diminished chords, fully diminished 7ths
- Seventh chords, borrowed chords, inverted chords
- B major chord interpreted as V/iii (secondary dominant of Em)
- Smooth voice leading throughout
- Ostinato G note provides harmonic anchor

### Melodic Characteristics

- Legato, flowing phrases (swimming motion)
- Wider intervals than staccato overworld
- Andrew Schartmann describes "surprising formal orthodoxy" --
  follows classical waltz conventions closely

### What Makes It Distinctive

The 3/4 waltz meter is unique in the soundtrack. First track Kondo
completed: "a waltz for floating was a no brainer." Most harmonically
rich despite hardware limitations.

## Track 4: Castle / Fortress Theme

**Key:** G minor (only non-C-centric track)
**Time Signature:** 4/4
**Tempo:** Fast
**Duration:** ~9 seconds (loops)

### Harmonic Analysis

- Built on i - iv - v (Gm - Cm - Dm)
- Heavy chromaticism
- Above average complexity in every metric

### Melodic Characteristics

- **Ultra-fast arpeggios** creating claustrophobic, anxious feel
- Triangle functions as independent melodic voice (counterpoint)
- Rapid arpeggiation gives illusion of fuller harmony
- Pulse 1 & 2: rapid arpeggiated figures in upper register
- Noise: minimal or absent (arpeggios provide rhythmic drive)

## Track 5: Star / Invincibility Theme

**Key:** C major (Dm7 - Cmaj7 oscillation, C Lydian / D Dorian area)
**Time Signature:** 4/4
**Tempo:** ~135-150 BPM
**Duration:** ~3 seconds (loops)

### Harmonic Analysis

- Two-chord vamp: **Dm7 - Cmaj7**
- Melody outlines 7th and root of each chord
- Bass outlines root and 5th
- Maximum energy from minimum material

## Track 6: Ending / Victory Theme

**Key:** C major
**Time Signature:** 4/4
**Duration:** ~7 seconds

### Harmonic Analysis

- Inverted chords, diminished chords, seventh chords, borrowed chords
- Features the Mario Cadence (bVI - bVII - I) prominently
- Packs the most harmonic sophistication into the shortest duration

## Cross-Cutting Observations

### Staccato and the "Bouncy" Feel

The NES pulse channels produce short, clipped envelopes. Kondo
exploited this with staccato-dominant melodies, using held notes
strategically for contrast. Staccato + swing drums + syncopation =
signature Mario bounce.

### Tonal Unity

All six tracks are in or closely related to C major (only castle
departs to G minor, the dominant minor). Creates unified tonal
palette despite extreme mood contrasts.

### Duty Cycle

Pulse channels maintain 50% duty cycle throughout (per one analysis),
though our Mesen capture data shows all 4 duty values used
(12.5%, 25%, 50%, 75%).

### Contrast as Design Principle

Maximum contrast in four level themes: bouncy/syncopated (overworld),
sparse/bass-driven (underground), flowing/waltz (underwater),
claustrophobic/arpeggiated (castle). Each recognizable within 1-2
seconds.

## Implications for Our Pipeline

| Finding | Pipeline Impact |
|---------|----------------|
| Key of C major | Can validate note sequences against known scale |
| P1 = melody, P2 = harmony | Channel assignment matches our extraction |
| Triangle = bass (D-E-A pattern) | NSF extraction gets this WRONG (py65 bug) |
| Noise = cha-cha swing | Continuous noise pattern, not vol-gated hits |
| 50% duty (disputed) | Our data shows all 4 duties -- need to check |
| 3/4 waltz for underwater | Different time sig than overworld 4/4 |
| Castle in G minor | Period table must handle sharps/flats |
| ~100 BPM overworld | Our 128.6 BPM is the NES frame-rate mapping |
| Staccato envelopes | CC11 decay shape is musically intentional |
| Mario Cadence (bVI-bVII-I) | Should appear as Ab-Bb-C in extracted notes |

## Sources

- Hooktheory: Overworld, Underground, Castle, Ending analyses
- Video Game Music Shrine: Inside The Score
- Bearded Gentlemen Music: Understanding Super Mario Music
- 8-Bit Analysis: The Mario Cadence
- Wikipedia: Super Mario Bros. Theme, Koji Kondo
- Twenty Thousand Hertz: Super Mario Bros Episode
- Schartmann: Book-length analysis of SMB soundtrack
- NESdev Wiki: APU documentation
- Shmuplations: Koji Kondo 2001 Interview
- Microchop: Underground Theme and 1979 Fusion Record
