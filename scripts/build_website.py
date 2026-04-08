#!/usr/bin/env python3
"""Build the complete NES Tone Database website.

Generates:
- index.html — main page with Tones, Games, How It Works, Documents tabs
- games/<slug>.html — per-game pages with instrument analysis
- how-it-works.html — extraction pipeline and synth architecture

Usage:
    python scripts/build_website.py -o output/tone_database/
"""

import json
import os
import argparse
import math
import glob

# ═══════════════════════════════════════════════════════════════════════
# SHARED CSS
# ═══════════════════════════════════════════════════════════════════════

SHARED_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #d0d0d0; line-height: 1.7; }
a { color: #00ccff; text-decoration: none; }
a:hover { text-decoration: underline; color: #66ddff; }

/* Navigation */
.site-header { background: #0d0d14; border-bottom: 2px solid #1a1a2e; padding: 0 20px; position: sticky; top: 0; z-index: 100; }
.site-header nav { max-width: 1100px; margin: 0 auto; display: flex; align-items: center; gap: 0; }
.site-title { color: #00ff88; font-size: 16px; font-weight: bold; padding: 14px 20px 14px 0; margin-right: 10px; border-right: 1px solid #222; white-space: nowrap; }
.nav-link { padding: 14px 18px; color: #888; font-size: 14px; border-bottom: 2px solid transparent; transition: all 0.2s; }
.nav-link:hover { color: #fff; text-decoration: none; border-bottom-color: #444; }
.nav-link.active { color: #00ff88; border-bottom-color: #00ff88; }

/* Layout */
.container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }
h1 { color: #00ff88; font-size: 28px; margin-bottom: 8px; }
h2 { color: #00ccff; font-size: 22px; margin: 35px 0 15px; border-bottom: 1px solid #1a1a2e; padding-bottom: 8px; }
h3 { color: #e0e0e0; font-size: 17px; margin: 20px 0 10px; }
h4 { color: #00ff88; font-size: 14px; margin: 15px 0 8px; }
.subtitle { color: #666; font-size: 14px; margin-bottom: 20px; }
p { margin-bottom: 12px; font-size: 15px; }

/* Cards */
.card { background: #111; border: 1px solid #1a1a2e; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.card:hover { border-color: #333; }

/* Stats */
.stats { display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 25px; }
.stat { background: #111; padding: 12px 18px; border-radius: 8px; border: 1px solid #1a1a2e; }
.stat-num { color: #00ff88; font-size: 28px; font-weight: bold; line-height: 1; }
.stat-label { color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }

/* Search */
.search-box { width: 100%; padding: 12px 16px; margin-bottom: 20px; background: #0d0d14; border: 1px solid #222; color: #fff; font-family: inherit; font-size: 14px; border-radius: 8px; }
.search-box:focus { outline: none; border-color: #00ff88; }

/* Tables */
table { width: 100%; border-collapse: collapse; margin: 15px 0; }
th { text-align: left; padding: 10px 14px; background: #0d0d14; color: #00ff88; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #1a1a2e; }
td { padding: 12px 14px; border-bottom: 1px solid #111; font-size: 14px; vertical-align: top; }
tr:hover td { background: #0d0d14; }

/* Two-column comparison */
.comparison-table td:first-child { border-right: 1px solid #1a1a2e; width: 50%; }
.comparison-table th:first-child { border-right: 1px solid #1a1a2e; }

/* Code blocks */
.code-block { background: #0d0d14; padding: 14px 18px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 13px; color: #ccc; border-left: 3px solid #00ff88; margin: 12px 0; overflow-x: auto; white-space: pre-wrap; }

/* Expandable sections */
details { margin: 10px 0; }
details summary { cursor: pointer; font-size: 14px; color: #00ccff; padding: 8px 0; }
details summary:hover { color: #66ddff; }
details[open] summary { margin-bottom: 8px; }
details > div, details > p { padding-left: 12px; border-left: 2px solid #1a1a2e; margin-left: 4px; }

/* Tags */
.tag { display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 11px; margin-right: 6px; background: #1a1a2e; color: #888; }
.tag-green { background: #0d1f0d; color: #00ff88; }
.tag-cyan { background: #0d1520; color: #00ccff; }

/* Sparklines */
.sparkline { background: #080812; border-radius: 4px; }

/* Game cards grid */
.game-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.game-card { background: #111; border: 1px solid #1a1a2e; border-radius: 8px; padding: 16px; display: block; color: inherit; transition: all 0.2s; }
.game-card:hover { border-color: #00ff88; text-decoration: none; transform: translateY(-2px); }
.game-card-title { color: #00ccff; font-size: 16px; font-weight: bold; margin-bottom: 6px; }
.game-card-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.game-card-notes { color: #666; font-size: 12px; }

/* Channel colors */
.ch-sq1 { color: #ff6b6b; }
.ch-sq2 { color: #ffa94d; }
.ch-tri { color: #51cf66; }
.ch-noi { color: #748ffc; }

/* Instrument cards on game pages */
.instrument { background: #111; border: 1px solid #1a1a2e; border-radius: 8px; margin-bottom: 24px; overflow: hidden; }
.instrument-header { padding: 16px 20px; border-bottom: 1px solid #1a1a2e; display: flex; justify-content: space-between; align-items: center; }
.instrument-body { padding: 20px; }
.envelope-row { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 15px; }
.adsr-pills { display: flex; gap: 8px; flex-wrap: wrap; }
.adsr-pill { background: #0d0d14; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
.duty-viz { font-family: monospace; font-size: 28px; letter-spacing: 3px; color: #00ccff; margin: 8px 0; }
.harmonic-text { font-size: 14px; color: #bbb; line-height: 1.7; margin-top: 12px; }

/* Waveform diagrams */
.waveform-label { font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }

footer { max-width: 1100px; margin: 40px auto 20px; padding: 15px 20px; border-top: 1px solid #1a1a2e; color: #444; font-size: 11px; text-align: center; }
"""

# ═══════════════════════════════════════════════════════════════════════
# NAV BAR
# ═══════════════════════════════════════════════════════════════════════

def nav_bar(active=""):
    links = [
        ("index.html", "Games", "games"),
        ("tones.html", "Tones", "tones"),
        ("how-it-works.html", "How It Works", "how"),
        ("docs.html", "Documents", "docs"),
    ]
    items = []
    for href, label, key in links:
        cls = "nav-link active" if key == active else "nav-link"
        items.append(f'<a href="{href}" class="{cls}">{label}</a>')
    return f"""<header class="site-header"><nav>
        <span class="site-title">NES Tone Database</span>
        {''.join(items)}
    </nav></header>"""


# ═══════════════════════════════════════════════════════════════════════
# HARMONIC / TIMBRAL DESCRIPTIONS
# ═══════════════════════════════════════════════════════════════════════

DUTY_DEEP = {
    0: {
        "name": "12.5%",
        "viz": "▁▁▁▁▁▁▁█",
        "nes": "The narrowest pulse width. The APU generates a waveform that is HIGH for 1/8 of the cycle and LOW for 7/8. Written to $4000/$4004 bits 6-7 as value 0.",
        "modern": "In ReapNES Console, set CC12 to 0-31 (maps to duty 0). In a modern synth like Serum or Vital, use a pulse/square oscillator and set pulse width to 12.5%. In subtractive synthesis, this is the extreme narrow end of the PWM range.",
        "harmonics": "Contains ALL harmonics (odd and even) but with a distinctive spectral tilt. The narrow pulse emphasizes high-frequency content, making it thin and buzzy. The 8th, 16th, and 24th harmonics are absent (nulls at multiples of 8). Think of a muted trumpet, a kazoo, or the 'sting' sound in classic chiptune. Used sparingly by most composers — often for attack transients or special effects rather than sustained melody.",
    },
    1: {
        "name": "25%",
        "viz": "▁▁▁▁▁▁██",
        "nes": "Quarter-width pulse. HIGH for 2/8, LOW for 6/8. Written as duty value 1 ($40 in register). This is the default 'chiptune' sound — the one most people associate with NES music.",
        "modern": "CC12 = 32-63 in ReapNES. In modern synths, set pulse width to 25%. This is the sweet spot between brightness and body. Many VST 'chiptune' presets default to this duty cycle.",
        "harmonics": "Contains all harmonics except every 4th (4th, 8th, 12th are absent). This creates a hollow, reedy quality — like a clarinet or oboe. The missing harmonics give it a 'nasal' character that cuts through a mix without being harsh. Capcom uses this extensively for harmony parts (Sq2) to contrast with the warmer 50% lead.",
    },
    2: {
        "name": "50%",
        "viz": "▁▁▁▁████",
        "nes": "True square wave — symmetrical, HIGH and LOW for equal time. Duty value 2 ($80 in register). The richest harmonic content of any NES duty cycle.",
        "modern": "CC12 = 64-95 in ReapNES. In any synth, this is the standard square wave. The foundation of chiptune sound. Most lead melody patches start here.",
        "harmonics": "Contains ONLY odd harmonics (1st, 3rd, 5th, 7th, 9th...) with amplitudes falling off as 1/n. This is what gives the square wave its warm, hollow, 'woody' quality. It sounds like a clarinet in its low register or a recorder. The absence of even harmonics distinguishes it sharply from a sawtooth wave. This is the most commonly used duty cycle for lead melodies across all NES games because it has the fullest body without brightness.",
    },
    3: {
        "name": "75%",
        "viz": "▁▁██████",
        "nes": "Wide pulse — inverse of 25%. HIGH for 6/8, LOW for 2/8. Duty value 3 ($C0). Acoustically identical to 25% because the human ear cannot distinguish a waveform from its inversion.",
        "modern": "CC12 = 96-127 in ReapNES. Sounds identical to 25% duty. Some NES drivers alternate between 25% and 75% rapidly to create a subtle chorus/phasing effect — this is because the phase relationship between the two inversions creates interference when mixed.",
        "harmonics": "Same harmonic content as 25% (missing every 4th harmonic). The only difference is the DC offset, which is inaudible. Some composers exploit the phase difference between 25% and 75% by switching between them for timbral animation.",
    },
}

TRIANGLE_DEEP = {
    "nes": "The triangle channel generates a 32-step staircase approximation of a triangle wave. Unlike the pulse channels, it has NO volume control — only an on/off gate via the linear counter ($4008). The period register works the same as pulse, but the frequency is ONE OCTAVE LOWER for the same period value because the sequencer has 32 steps instead of 16.",
    "modern": "In ReapNES Console, set Channel Mode to 2 (Triangle). CC11 is always 127 (gate only — full volume or silence). No CC12 needed (no duty cycle). For MIDI keyboard playing, the triangle channel uses note duration for all articulation — staccato = short notes, legato = long notes. In modern synths, use a triangle oscillator with no filter and no amplitude envelope (just a gate).",
    "harmonics": "A perfect triangle wave contains only odd harmonics like a square wave, but they fall off as 1/n² instead of 1/n — much faster. This means the triangle is much darker and smoother than a square wave. The NES triangle is not mathematically perfect (it's a 32-step staircase), which adds slight high-frequency 'grittiness' — especially audible at high pitches. At low pitches (where it's typically used as bass), it sounds clean, dark, and full — similar to a low flute, a sub-bass synth with a wide-open filter, or the fundamental tone of a bass guitar with no harmonics.",
}

NOISE_DEEP = {
    "nes": "The noise channel uses a 15-bit Linear Feedback Shift Register (LFSR) to generate pseudo-random noise. The period register ($400E bits 0-3) selects one of 16 timer values that control how fast the LFSR shifts — lower periods = faster shifts = higher-pitched noise. Bit 7 of $400E selects the feedback mode: 0 = long sequence (32767 steps, sounds like white noise), 1 = short sequence (93 steps, sounds metallic/tonal).",
    "modern": "In ReapNES Console, set Channel Mode to 3 (Noise). MIDI note numbers map to drum sounds: 36=kick, 38=snare, 42=closed hi-hat, 46=open hi-hat. Velocity controls initial volume. The ADSR envelope shapes the hit. In modern synths, use a noise oscillator with a short amplitude envelope for percussion. For the 'short mode' metallic sound, use a very short noise burst with high resonance — similar to the '808 cowbell' technique.",
    "harmonics": "In long mode, the noise has a flat (white) spectrum — equal energy at all frequencies, filtered by the period setting which acts as a crude lowpass. In short mode, the 93-step cycle creates a pitched, metallic tone with a distinctive 'ring' — this is because the short cycle creates a quasi-periodic waveform with identifiable pitch. The short mode noise is what gives NES snare drums their distinctive 'metallic crack' — it's a sound unique to the NES that you can't easily recreate with simple white noise.",
}

SHAPE_DEEP = {
    "percussive": {
        "description": "Sharp attack, rapid decay — the note hits hard and fades quickly within a few frames.",
        "character": "Creates punchy, rhythmic melodies where each note stands out as a distinct event. This is the signature envelope of action game music — Castlevania, Mega Man, and Contra all use percussive pulse envelopes to give their melodies a driving, energetic feel. The rapid decay prevents notes from bleeding into each other, keeping the texture clean even at fast tempos.",
        "adsr": "Attack: 0ms (instant), Decay: 15-50ms, Sustain: 0-30%, Release: 0ms",
        "synth_tip": "In a modern synth, set attack to 0, decay to 15-50ms, sustain to near zero. Add a slight volume boost at the very start (initial level = max) for the 'pluck' transient.",
    },
    "sustained": {
        "description": "Consistent volume throughout the note with minimal decay.",
        "character": "Creates smooth, flowing melodies. Common in RPG town themes, love themes, and any passage that needs a lyrical quality. The constant volume makes the melody feel like a voice singing rather than an instrument plucking. Final Fantasy and Dragon Quest use this extensively.",
        "adsr": "Attack: 0ms, Decay: 0ms, Sustain: 80-100%, Release: varies",
        "synth_tip": "Set sustain to maximum. The NES achieves this by writing the same volume value every frame — in MIDI terms, CC11 stays constant throughout the note.",
    },
    "decaying": {
        "description": "Natural fade from peak volume — like a plucked string or a bell strike.",
        "character": "The most natural-sounding envelope on NES. Gives notes a realistic, organic quality. The decay rate varies by game: Castlevania uses fast 4-step decays (32→24→16→8) for its gothic harpsichord feel, while Kirby uses slower, gentler decays for its playful sound.",
        "adsr": "Attack: 0ms, Decay: 30-200ms, Sustain: 20-60%, Release: 0-30ms",
        "synth_tip": "The key parameter is the decay time and sustain level. Faster decay + lower sustain = more percussive feel. Slower decay + higher sustain = more legato feel.",
    },
    "swell": {
        "description": "Volume increases over the note duration — a crescendo effect.",
        "character": "Rare on NES because it requires the driver to increase volume each frame (computationally expensive). Used for dramatic passages, transitions, or to create a 'breathing' quality. Creates tension and anticipation.",
        "adsr": "Attack: 50-200ms, Decay: 0ms, Sustain: 100%, Release: varies",
        "synth_tip": "Set a slow attack time. On NES, this is achieved by writing incrementing volume values to CC11 over several frames.",
    },
}

# ═══════════════════════════════════════════════════════════════════════
# DRIVER INFO (expanded from earlier)
# ═══════════════════════════════════════════════════════════════════════

DRIVERS = {
    "Konami Maezawa": {
        "keywords": ["Castlevania", "Contra", "Gradius", "Life_Force"],
        "summary": "Konami's workhorse NES driver used across dozens of titles from 1986-1992.",
        "architecture": "Data-driven flat byte stream. Notes are nibble-packed: high 4 bits = pitch (C through B within the current octave), low 4 bits = duration index. Duration in frames = tempo_register × (duration_nibble + 1). Octave set by DX commands. Envelopes are parametric two-phase: a fast attack phase followed by a decay phase controlled by two parameters (fade_start, fade_step).",
        "sound_character": "Dark, atmospheric, cinematic. The parametric envelope creates a distinctive 'gothic harpsichord' attack — sharp onset followed by controlled decay. Sparse but effective drum patterns give the music space to breathe. Castlevania's 'Vampire Killer' is the definitive example.",
    },
    "Capcom": {
        "keywords": ["Mega_Man", "Darkwing", "Chip_n_Dale", "Duck_Tales", "Strider", "Mighty_Final", "Gargoyles", "Little_Nemo", "Ghosts_n_Goblins", "Bionic_Commando"],
        "summary": "Capcom's internal NES sound engine, evolved across the Mega Man series and Disney licensed titles (1987-1993).",
        "architecture": "Octave + semitone byte encoding — full note identity in one byte with no separate octave command. Variable-width command dispatch. Heavy use of per-frame duty cycle switching for timbral animation. 54 pre-built envelope lookup tables in Contra variant.",
        "sound_character": "Bright, driving, rhythmic — the most 'band-like' sound on NES. Characterized by extremely dense drum programming (700+ noise events per 80 seconds is typical), dual-duty pulse arrangement (50% lead, 25% harmony for timbral contrast), and fast arpeggiated bass lines on triangle. The Mega Man series defines the Capcom NES sound.",
    },
    "Square": {
        "keywords": ["Final_Fantasy"],
        "summary": "Square's NES sound engine for the Final Fantasy series. MIDI-based composition workflow.",
        "architecture": "Digit-encoded notes: first hex digit (0-B) = pitch (C through B), second digit (0-9) = duration. $D8-$DB = octave shift commands. $F prefix = Musical Control String (tempo, instrument configuration). $D0/$D1 = loop/repeat with pointer addresses. Master Music Table at ROM $34010 contains 23 songs × 6 bytes (3 channel pointers).",
        "sound_character": "Classical, arpeggiated, orchestral. The Prelude's ascending arpeggio across two pulse channels is the most recognizable NES musical motif. Minimal percussion — rhythm comes from pulse interplay and triangle bass patterns. Town and castle themes have a stately, medieval quality. Battle music uses faster tempos but maintains the classical voice-leading.",
    },
    "Nintendo": {
        "keywords": ["Kid_Icarus", "Kirby", "Metroid", "Ice_Climber", "Donkey_Kong", "Excitebike", "Dr_Mario", "Tetris"],
        "summary": "Nintendo's first-party sound engines vary significantly per game and era.",
        "architecture": "No standardized driver. Kid Icarus uses three simultaneous engines: code-as-music (songs as 6502 subroutines), RAM-resident code (copied during bank switches), and a data-driven config table system. Kirby uses standard data-driven with MMC3 banking. Early titles (Ice Climber, DK) use simple NROM drivers.",
        "sound_character": "Unpredictable and game-specific. Ranges from Kirby's lush four-channel pop arrangements (1075 drum hits!) to Metroid's sparse, atmospheric drones (17 noise events). Kid Icarus changes character between banks. Dr. Mario and Tetris have infectiously catchy melodies with simple but effective arrangements.",
    },
    "Warhol": {
        "keywords": ["Dick_Tracy", "Maniac_Mansion", "Rocketeer", "Caesars_Palace", "Total_Recall", "Rad_Gravity"],
        "summary": "David Warhol's driver for Realtime Associates (1990-1992). Unique MIDI-based workflow.",
        "architecture": "Composers (George Sanger, David Hayes) created MIDI files in Cakewalk/Performer, which Warhol arranged and converted to a text format for NES. Entry points: $8029 = play_song(X register), $80A0 = per-frame tick. Standard NTSC period table spanning 7 octaves. Never uses DPCM (Warhol couldn't figure out how).",
        "sound_character": "Distinctive 'echo' instrument created by hardware sweep every 13 frames, giving a reverb-like decay unique among NES games. Duty cycle basses. Square channel drums (pulse waves used as percussion in Defenders of Dynatron City). The MIDI workflow gives the music a slightly different feel from hand-coded NES drivers — more 'composed' and less 'programmed'.",
    },
    "Sunsoft": {
        "keywords": ["Batman", "Journey_to_Silius", "Blaster_Master"],
        "summary": "Sunsoft's NES sound engine, famous for pushing the hardware to its absolute limits.",
        "architecture": "Data-driven with aggressive timbral techniques. Rapid duty cycle switching for bass tones (alternating between duty cycles creates a phaser-like effect). Fast arpeggios across notes for pseudo-polyphony (playing chord tones in rapid succession to simulate chords on a monophonic channel).",
        "sound_character": "Punchy, bass-heavy, funk-influenced. Blaster Master's 1063 triangle notes in 80 seconds is the densest bass line in our collection. Journey to Silius has a driving, almost techno-like quality. Batman (Sunsoft) has deep grooves with sophisticated bass patterns. The bass presence is what sets Sunsoft apart — their triangle channel work is unmatched.",
    },
    "Enix": {
        "keywords": ["Dragon_Warrior"],
        "summary": "Enix's RPG sound engine for the Dragon Quest/Dragon Warrior series.",
        "architecture": "Standard data-driven player with period table lookup. Orchestral-influenced composition by Koichi Sugiyama (one of the first major classical composers to write for video games).",
        "sound_character": "Orchestral, stately, dignified. Three-channel focus (Sq1/Sq2/Triangle) with minimal or no percussion. The Overworld theme treats the NES as a chamber ensemble — two melody voices over a bass line, with careful voice-leading that would be at home in a Bach invention. This approach respects the limitations of the hardware by not trying to make it sound like a rock band.",
    },
    "Rare": {
        "keywords": ["Battletoads", "Wizards"],
        "summary": "Rare's custom NES drivers — each game has its own engine (not standardized).",
        "architecture": "Battletoads: byte-index notes (≥$81), persistent duration via command, software volume register ($0352,X) with ramp/oscillate modes, ~20 command opcodes. Wizards & Warriors: simpler 10-command format with two period tables.",
        "sound_character": "Rich harmonies and moderate percussion. Battletoads has the most complex command set we've analyzed with features like transposition, sweep, vibrato, and volume oscillation all controllable per-channel. The music has a progressive rock quality with sophisticated arrangements that push the NES hardware.",
    },
    "Technos": {
        "keywords": ["Double_Dragon", "River_City"],
        "summary": "Technos Japan's beat-em-up sound engine.",
        "architecture": "Standard data-driven player with full four-channel arrangements.",
        "sound_character": "Action-oriented with balanced four-channel usage. Double Dragon's 1303 total notes across 80 seconds shows even distribution between melody, harmony, bass, and drums — every channel pulling its weight.",
    },
    "Unknown": {
        "keywords": [],
        "summary": "Driver not yet identified for this game.",
        "architecture": "Standard NES APU data-driven player. Technical details pending analysis.",
        "sound_character": "Varies.",
    },
}


def identify_driver(game_name):
    gn = game_name.lower().replace('_', ' ')
    for name, info in DRIVERS.items():
        if any(kw.lower().replace('_', ' ') in gn for kw in info["keywords"]):
            return name, info
    return "Unknown", DRIVERS["Unknown"]


def sparkline_svg(curve, color, width=200, height=60):
    if not curve or max(curve) == 0:
        return f'<svg width="{width}" height="{height}" class="sparkline"><text x="30" y="35" fill="#333" font-size="11">no envelope data</text></svg>'
    mx = max(curve)
    n = max(len(curve) - 1, 1)
    pts = " ".join(f"{i*(width/n):.0f},{height-4-(v/mx*(height-8)):.0f}" for i, v in enumerate(curve))
    return f'<svg width="{width}" height="{height}" class="sparkline"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'


CH_COLORS = {0: '#ff6b6b', 1: '#ffa94d', 2: '#51cf66', 3: '#748ffc'}
CH_CSS = {0: 'ch-sq1', 1: 'ch-sq2', 2: 'ch-tri', 3: 'ch-noi'}


def describe_instrument(inst, all_instruments, game_name, driver_name):
    """Generate game-specific, data-driven prose for one instrument channel.

    Reads the actual ADSR values, duty distributions, shape distributions,
    note counts, and durations and writes prose that describes what THIS
    channel sounds like in THIS game, and how it differs from the other channels.
    """
    ch = inst['channel']
    ch_name = inst['channel_name']
    adsr = inst['adsr']
    shape = inst.get('dominant_shape', 'unknown')
    notes = inst['note_count']
    avg_dur = inst.get('avg_duration_ms', 0)
    peak = inst.get('peak_volume', 0)
    curve = inst.get('envelope_curve', [])
    shape_dist = inst.get('shape_distribution', {})
    duty_dist = inst.get('duty_distribution', {})
    duty = inst.get('dominant_duty', 2)
    display_name = game_name.replace('_', ' ')

    # Compute derived characteristics
    articulation = 'rapid staccato' if avg_dur < 80 else 'staccato' if avg_dur < 150 else 'moderate' if avg_dur < 300 else 'legato' if avg_dur < 600 else 'very long sustained'
    density = 'extremely dense' if notes > 500 else 'dense' if notes > 200 else 'moderate' if notes > 50 else 'sparse'
    volume_character = 'full volume' if peak > 100 else 'moderate volume' if peak > 50 else 'quiet' if peak > 20 else 'very quiet'

    # Check for timbral variety (duty switching)
    num_duties = len([k for k, v in duty_dist.items() if int(v) > 3])
    duty_varies = num_duties > 1

    # Check for envelope variety (shape mixing)
    num_shapes = len([k for k, v in shape_dist.items() if int(v) > 3])
    shape_varies = num_shapes > 1

    # Envelope curve character
    if curve and len(curve) > 3 and max(curve) > 0:
        mx = max(curve)
        start_ratio = curve[0] / mx
        mid_ratio = curve[len(curve)//2] / mx if len(curve) > 2 else 0
        end_ratio = curve[-1] / mx if curve[-1] > 0 else 0
        if start_ratio < 0.5 and mid_ratio > 0.8:
            env_character = "fades in (swell) — unusual for NES, creates an expressive, breath-like quality"
        elif start_ratio > 0.8 and mid_ratio < 0.4:
            env_character = "sharp attack then quick fade — a plucked, percussive quality where each note pops out distinctly"
        elif start_ratio > 0.8 and mid_ratio > 0.7:
            env_character = "sustained at near-constant volume — a smooth, organ-like tone where notes flow into each other"
        elif mid_ratio > start_ratio:
            env_character = "builds after the initial attack — creates a delayed swell effect"
        else:
            env_character = "gradual natural decay — like a plucked string fading"
    else:
        env_character = "minimal envelope shaping"

    # Find other channels for comparison
    other_pulse = [i for i in all_instruments if i['channel'] < 2 and i['channel'] != ch]

    # Build the prose
    duty_names = {0: '12.5%', 1: '25%', 2: '50%', 3: '75%'}

    if ch < 2:  # Pulse channels
        # Duty cycle description
        dn = duty_names.get(duty, '50%')
        if duty_varies:
            duty_list = ', '.join(f"{duty_names.get(int(k), k)} ({v}×)" for k, v in sorted(duty_dist.items(), key=lambda x: -int(x[1])) if int(v) > 3)
            duty_prose = f"switches between multiple duty cycles ({duty_list}), creating timbral animation — the tone color shifts throughout the melody like a singer changing vowels"
        else:
            sonic_qual = {
                0: "thin, nasal, and buzzy — like a kazoo or muted trumpet, all high-frequency bite",
                1: "bright and hollow — like a clarinet or oboe, clear without being harsh",
                2: "warm, full, and round — a pure square wave with that classic NES lead character, like a low recorder",
                3: "same harmonic content as 25% (inverted phase), bright and hollow",
            }
            duty_prose = f"uses {dn} duty cycle consistently — {sonic_qual.get(duty, 'standard pulse tone')}"

        # Envelope description with game-specific detail
        if shape_varies:
            shape_list = ', '.join(f"{k} ({v}×)" for k, v in sorted(shape_dist.items(), key=lambda x: -int(x[1])) if int(v) > 3)
            env_prose = f"The envelope is dynamic — notes use a mix of shapes ({shape_list}), meaning {display_name} varies the attack character throughout the song. Some notes punch hard (percussive), others ring out (sustained), creating rhythmic interest beyond just the melody."
        else:
            env_prose = f"The envelope is consistently {shape}: {env_character}."

        # Role and comparison
        if ch == 0:
            role = "lead melody"
            if other_pulse:
                op = other_pulse[0]
                if op['note_count'] > notes * 1.5:
                    role_prose = f"Carries the {role}, though Square 2 is actually busier ({op['note_count']} vs {notes} notes) — this channel provides the main theme while Sq2 fills in the texture."
                elif notes > op['note_count'] * 1.5:
                    role_prose = f"Dominates as the {role} with {notes} notes (vs Sq2's {op['note_count']}) — this is clearly the star of {display_name}'s arrangement."
                else:
                    role_prose = f"Shares melodic duties with Square 2 ({notes} vs {op['note_count']} notes) — the two pulse channels trade phrases and harmonize."
            else:
                role_prose = f"Carries the {role} with {notes} notes."
        else:
            role = "harmony / countermelody"
            if other_pulse:
                op = other_pulse[0]
                vol_diff = peak - op.get('peak_volume', 0)
                if vol_diff < -20:
                    role_prose = f"Plays {role} at noticeably lower volume (peak {peak} vs Sq1's {op.get('peak_volume', 0)}) — sits behind the lead, adding depth without competing."
                elif avg_dur > op.get('avg_duration_ms', 0) * 2:
                    role_prose = f"Plays long sustained notes ({avg_dur}ms avg vs Sq1's {op.get('avg_duration_ms', 0)}ms) — functions as a pad/chord channel underneath the lead melody."
                else:
                    role_prose = f"Provides {role} alongside Square 1 — the two channels create {display_name}'s characteristic pulse texture."
            else:
                role_prose = f"Provides {role}."

        # Harmonic content
        harmonic_map = {
            0: "Contains all harmonics but with a steep spectral tilt — the narrow pulse emphasizes high frequencies, producing a thin, nasal buzz. Missing every 8th harmonic (8th, 16th, 24th).",
            1: "Missing every 4th harmonic (4th, 8th, 12th, 16th...), creating a hollow, reedy quality. The gaps in the spectrum give it a nasal 'chiptune' character that cuts through a mix.",
            2: "Contains only odd harmonics (1st, 3rd, 5th, 7th...) falling off as 1/n. This gives the square wave its warm, hollow, woody quality — the richest pulse tone the NES can produce.",
            3: "Identical harmonic content to 25% duty (phase-inverted). Some drivers alternate between 25% and 75% for a subtle phasing effect.",
        }
        harmonics = harmonic_map.get(duty, "Standard pulse harmonic content.")

        description = f"""
        <p>In {display_name}, {ch_name} {duty_prose}. At {volume_character} (peak {peak}/127), it plays {density} {articulation} phrases averaging {avg_dur}ms per note.</p>
        <p>{env_prose}</p>
        <p>{role_prose}</p>
        """

    elif ch == 2:  # Triangle
        staccato_pct = int(shape_dist.get('percussive', 0)) / max(notes, 1) * 100
        if staccato_pct > 60:
            bass_style = f"predominantly staccato — short, punchy bass hits that give {display_name} a rhythmic, bouncy feel. The quick on/off gating creates percussive bass that almost functions as a second drum channel."
        elif staccato_pct < 20:
            bass_style = f"predominantly legato — long, sustained bass notes that provide a smooth harmonic foundation under the melody. The sustained gating creates a warm, continuous low end."
        else:
            bass_style = f"a mix of staccato and legato — alternating between punchy hits and sustained lines, giving the bass both rhythmic drive and harmonic support."

        description = f"""
        <p>{display_name}'s bass uses the triangle wave — the NES's only sub-bass channel. With no volume control (only on/off gating), all expression comes from note duration: {bass_style}</p>
        <p>At {notes} notes and {avg_dur}ms average duration, the bass is {density}. The triangle wave produces only odd harmonics falling off as 1/n² (much faster than the square wave's 1/n), making it the darkest, smoothest tone the NES can generate — like a low flute or a sub-bass synth with the filter wide open.</p>
        <p>Because the triangle is one octave lower than the pulse channels for the same period value (32-step sequencer vs 16-step), it naturally sits below the melody without competing for frequency space.</p>
        """
        harmonics = "Only odd harmonics (like square wave) but falling off as 1/n² — much darker and smoother. The 32-step staircase approximation adds slight high-frequency grit at high pitches, but in the bass register where it's typically used, the tone is clean and pure."

    else:  # Noise
        if notes > 500:
            drum_character = f"an extremely dense drum pattern — {notes} hits in the capture ({notes/80:.0f} per second). This is a driving, relentless beat that propels the music forward, more like a drum machine than acoustic percussion."
        elif notes > 200:
            drum_character = f"a steady, active drum pattern with {notes} hits. Consistent rhythmic backbone with regular kick-snare-hat patterns."
        elif notes > 50:
            drum_character = f"moderate percussion with {notes} hits — enough to establish rhythm without dominating the mix."
        elif notes > 10:
            drum_character = f"sparse accents — only {notes} hits, used for emphasis on key beats rather than continuous rhythm."
        else:
            drum_character = f"minimal percussion — just {notes} hits, the music relies on melodic rhythm rather than drums."

        description = f"""
        <p>{display_name}'s percussion channel produces {drum_character}</p>
        <p>Every NES drum is synthesized from the noise channel's linear-feedback shift register (LFSR) — there are no audio samples. The 'kick' is a low-period noise burst, the 'snare' is a mid-period hit (often using the short LFSR mode for a metallic crack), and 'hi-hats' are high-period filtered noise. The average hit duration of {avg_dur}ms tells us these are {'tight, punchy hits' if avg_dur < 50 else 'medium-length hits' if avg_dur < 150 else 'longer, sustained noise bursts'}.</p>
        """
        harmonics = "In long LFSR mode: flat (white) spectrum filtered by the period setting. In short LFSR mode (93-step cycle): quasi-periodic metallic tone with identifiable pitch — this is what gives NES snare drums their distinctive 'crack'."

    return description, harmonics


def build_game_page(game_data, output_dir):
    g = game_data
    driver_name, driver_info = identify_driver(g['game'])

    all_instruments = g.get('instruments', [])
    instruments_html = []
    for inst in all_instruments:
        ch = inst['channel']
        ch_name = inst['channel_name']
        color = CH_COLORS.get(ch, '#888')
        adsr = inst['adsr']
        shape = inst.get('dominant_shape', 'unknown')

        # Generate game-specific description
        description_html, harmonics_text = describe_instrument(
            inst, all_instruments, g['game'], driver_name
        )

        # Envelope sparkline
        svg = sparkline_svg(inst.get('envelope_curve', []), color)

        # Build the two-column comparison table with game-specific REAPER settings
        if ch < 2:  # Pulse
            duty = inst.get('dominant_duty', 2)
            d = DUTY_DEEP.get(duty, DUTY_DEEP[2])
            # Game-specific REAPER settings
            reaper_specific = f"""{d['modern']}
            <p style="margin-top:10px"><strong>For {g['display_name']} specifically:</strong>
            Set attack to {adsr['attack_ms']}ms, decay to {adsr['decay_ms']}ms,
            sustain to {round(adsr['sustain_ratio']*100)}%.
            {'The sustained envelope means CC11 stays near-constant — let the automation drive the volume, dont add ADSR shaping.' if shape == 'sustained' else
             'The percussive envelope means CC11 drops quickly — the captured automation already contains the pluck/decay, no additional ADSR needed.' if shape == 'percussive' else
             'The decaying envelope means CC11 gradually fades — this natural decay is captured in the automation data.' if shape == 'decaying' else
             'The swell means CC11 increases over time — a slow attack is baked into the automation.'}</p>"""
            comparison = f"""
            <table class="comparison-table">
                <tr><th>NES Hardware (RP2A03)</th><th>Recreating in REAPER (ReapNES Console)</th></tr>
                <tr>
                    <td>{d['nes']}</td>
                    <td>{reaper_specific}</td>
                </tr>
            </table>
            <div class="harmonic-text">
                <h4>Harmonic Character — {d['name']} Duty Cycle</h4>
                <div class="duty-viz">{d['viz']}</div>
                <p>{harmonics_text}</p>
            </div>
            """
        elif ch == 2:  # Triangle
            reaper_specific = f"""{TRIANGLE_DEEP['modern']}
            <p style="margin-top:10px"><strong>For {g['display_name']} specifically:</strong>
            Average note duration is {inst.get('avg_duration_ms', 0)}ms —
            {'set short MIDI notes for the staccato bass hits.' if inst.get('avg_duration_ms', 0) < 100 else
             'use longer MIDI notes for the sustained bass lines.' if inst.get('avg_duration_ms', 0) > 300 else
             'mix short and long notes to match the varied bass articulation.'}</p>"""
            comparison = f"""
            <table class="comparison-table">
                <tr><th>NES Hardware (RP2A03)</th><th>Recreating in REAPER (ReapNES Console)</th></tr>
                <tr>
                    <td>{TRIANGLE_DEEP['nes']}</td>
                    <td>{reaper_specific}</td>
                </tr>
            </table>
            <div class="harmonic-text">
                <h4>Harmonic Character — Triangle Wave</h4>
                <p>{harmonics_text}</p>
            </div>
            """
        else:  # Noise
            reaper_specific = f"""{NOISE_DEEP['modern']}
            <p style="margin-top:10px"><strong>For {g['display_name']} specifically:</strong>
            {inst['note_count']} drum hits at {inst.get('avg_duration_ms', 0)}ms average —
            {'this is a dense, driving pattern. Use tight velocity-driven hits with short decay.' if inst['note_count'] > 300 else
             'moderate percussion. Standard kick-snare-hat mapping works well.' if inst['note_count'] > 50 else
             'sparse accents. Place hits carefully on key beats for emphasis.'}</p>"""
            comparison = f"""
            <table class="comparison-table">
                <tr><th>NES Hardware (RP2A03)</th><th>Recreating in REAPER (ReapNES Console)</th></tr>
                <tr>
                    <td>{NOISE_DEEP['nes']}</td>
                    <td>{reaper_specific}</td>
                </tr>
            </table>
            <div class="harmonic-text">
                <h4>Harmonic Character — Noise Channel</h4>
                <p>{harmonics_text}</p>
            </div>
            """

        # Shape description
        shape_info = SHAPE_DEEP.get(shape, {"description": "", "character": "", "adsr": "", "synth_tip": ""})

        instruments_html.append(f"""
        <div class="instrument" style="border-left: 4px solid {color}">
            <div class="instrument-header" style="border-left: none">
                <h3 class="{CH_CSS.get(ch, '')}">{ch_name}</h3>
                <span class="tag">{inst['note_count']} notes · {inst.get('avg_duration_ms', 0)}ms avg</span>
            </div>
            <div class="instrument-body">

                <div class="harmonic-text">
                    {description_html}
                </div>

                <div class="envelope-row">
                    <div>
                        <div class="waveform-label">Volume Envelope</div>
                        {svg}
                        <div class="adsr-pills">
                            <span class="adsr-pill">A: {adsr['attack_ms']}ms</span>
                            <span class="adsr-pill">D: {adsr['decay_ms']}ms</span>
                            <span class="adsr-pill">S: {round(adsr['sustain_ratio']*100)}%</span>
                            <span class="adsr-pill">R: {adsr['release_ms']}ms</span>
                        </div>
                    </div>
                    <div>
                        <div class="waveform-label">Envelope Shape: {shape}</div>
                        <p style="font-size:13px;color:#999">{shape_info['description']}</p>
                        <p style="font-size:13px;color:#777;margin-top:6px">{shape_info['character']}</p>
                        <p style="font-size:12px;color:#00ff88;margin-top:6px"><strong>Synth tip:</strong> {shape_info.get('synth_tip', '')}</p>
                    </div>
                </div>

                <details>
                    <summary>NES Hardware vs Modern Synth — How to Recreate This Sound</summary>
                    <div>{comparison}</div>
                </details>
            </div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{g['display_name']} — NES Tone Database</title>
<style>{SHARED_CSS}</style>
</head>
<body>
{nav_bar("games")}
<div class="container">

<p style="color:#666;font-size:13px;margin-bottom:5px"><a href="index.html">NES Tone Database</a> &rsaquo; Games</p>
<h1>{g['display_name']}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px">
    <span class="tag tag-green">{driver_name}</span>
    <span class="tag tag-cyan">{g['num_channels']} channels active</span>
    <span class="tag">{g['total_notes']:,} notes captured</span>
</div>

<h2>Sound Architecture</h2>
<div class="card">
    <h4>{driver_name} Driver</h4>
    <p>{driver_info['summary']}</p>
    <details>
        <summary>Technical encoding format</summary>
        <div class="code-block">{driver_info['architecture']}</div>
    </details>
    <p style="font-style:italic;color:#888;margin-top:10px"><strong>Sonic signature:</strong> {driver_info['sound_character']}</p>
</div>

<h2>Instruments</h2>
{''.join(instruments_html)}

</div>
<footer>NES Tone Database &mdash; <a href="index.html">Back to Games</a></footer>
</body>
</html>"""

    slug = g['game'].replace(' ', '_')
    path = os.path.join(output_dir, 'games', f'{slug}.html')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def build_index(games_data, tones, docs, output_dir):
    """Build the main index page (Games tab as default)."""

    # Game cards
    cards = []
    for g in sorted(games_data, key=lambda x: x['display_name']):
        driver_name, _ = identify_driver(g['game'])
        slug = g['game'].replace(' ', '_')
        ch_summary = []
        for inst in g.get('instruments', []):
            ch = inst['channel']
            ch_summary.append(f'<span class="{CH_CSS.get(ch, "")}">{inst["channel_name"]}: {inst["note_count"]}</span>')

        cards.append(f"""
        <a href="games/{slug}.html" class="game-card">
            <div class="game-card-title">{g['display_name']}</div>
            <div class="game-card-meta">
                <span class="tag tag-green">{driver_name}</span>
                <span class="tag">{g['total_notes']:,} notes</span>
            </div>
            <div class="game-card-notes">{' · '.join(ch_summary)}</div>
        </a>
        """)

    total_games = len(games_data)
    total_tones = len(tones)
    total_notes = sum(t['note_count'] for t in tones)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NES Tone Database</title>
<style>{SHARED_CSS}</style>
</head>
<body>
{nav_bar("games")}
<div class="container">

<h1>NES Tone Database</h1>
<p class="subtitle">An educational resource for chiptune musicians and ROM hackers. Automated extraction from {total_games} NES games via headless ROM emulation.</p>

<div class="stats">
    <div class="stat"><div class="stat-num">{total_games}</div><div class="stat-label">Games</div></div>
    <div class="stat"><div class="stat-num">{total_tones}</div><div class="stat-label">Tone Profiles</div></div>
    <div class="stat"><div class="stat-num">{total_notes:,}</div><div class="stat-label">Notes Analyzed</div></div>
    <div class="stat"><div class="stat-num">212</div><div class="stat-label">REAPER Projects</div></div>
</div>

<input type="text" class="search-box" placeholder="Search games..." oninput="document.querySelectorAll('.game-card').forEach(c=>c.style.display=c.textContent.toLowerCase().includes(this.value.toLowerCase())?'':'none')">

<div class="game-grid">
{''.join(cards)}
</div>

</div>
<footer>NES Tone Database &mdash; Built with nes_rom_capture.py, extract_tones.py, and build_website.py</footer>
</body>
</html>"""

    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def build_how_it_works(output_dir):
    """Build the How It Works page."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>How It Works — NES Tone Database</title>
<style>{SHARED_CSS}</style>
</head>
<body>
{nav_bar("how")}
<div class="container">

<h1>How It Works</h1>
<p class="subtitle">From ROM bytes to REAPER projects — the complete NES music extraction pipeline.</p>

<h2>The NES Sound Chip (RP2A03)</h2>

<p>The NES has no sound samples, no wavetables, no DSP. All audio is generated by 5 simple waveform generators running at 1.789773 MHz, updated 60 times per second by the CPU. Every sound you've ever heard in an NES game — every melody, every bass line, every drum hit — is built from these 5 channels:</p>

<div class="card">
<h3 class="ch-sq1">Pulse 1 & 2 (Square Waves)</h3>
<table class="comparison-table">
<tr><th>NES Hardware</th><th>Modern Equivalent</th></tr>
<tr>
<td>
<p>Two identical pulse wave generators. Each has:</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>11-bit period register</strong> → frequencies from ~55Hz to ~12.4kHz</li>
<li><strong>4 duty cycles</strong>: 12.5%, 25%, 50%, 75% (waveform shape)</li>
<li><strong>4-bit volume</strong> (0-15) with optional hardware decay</li>
<li><strong>Sweep unit</strong> for automatic pitch bends</li>
</ul>
<p style="margin-top:10px">The CPU writes new values to these registers every frame (60Hz). That's how envelopes and vibrato work — not through hardware automation, but through the music driver manually updating registers 60 times per second.</p>
</td>
<td>
<p>In ReapNES Console (JSFX plugin for REAPER):</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>CC11</strong> = Volume (mapped to NES 0-15 range)</li>
<li><strong>CC12</strong> = Duty cycle (0-3 selecting waveform shape)</li>
<li><strong>MIDI note number</strong> = Pitch (quantized to semitones)</li>
<li><strong>Slider 33</strong> = Channel mode (0=Sq1, 1=Sq2)</li>
</ul>
<p style="margin-top:10px">The per-frame CC11/CC12 automation IS the NES envelope. Don't override it with ADSR — the captured data already contains the exact volume and timbre curve the game uses.</p>
</td>
</tr>
</table>
</div>

<div class="card">
<h3 class="ch-tri">Triangle (Bass)</h3>
<table class="comparison-table">
<tr><th>NES Hardware</th><th>Modern Equivalent</th></tr>
<tr>
<td>
<p>A 32-step staircase triangle wave. Unlike pulse channels:</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>No volume control</strong> — only on/off gating</li>
<li><strong>One octave lower</strong> than pulse for the same period (32-step vs 16-step sequencer)</li>
<li>All expression comes from note duration (staccato vs legato)</li>
</ul>
<p style="margin-top:10px">The triangle wave contains only odd harmonics falling off as 1/n², making it the darkest, smoothest waveform the NES can produce. It's always used for bass.</p>
</td>
<td>
<p>In ReapNES Console:</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>Channel Mode = 2</strong> (Triangle)</li>
<li><strong>CC11 always 127</strong> (full volume gate)</li>
<li>No CC12 (no duty cycle for triangle)</li>
<li>Articulation from MIDI note duration only</li>
</ul>
</td>
</tr>
</table>
</div>

<div class="card">
<h3 class="ch-noi">Noise (Percussion)</h3>
<table class="comparison-table">
<tr><th>NES Hardware</th><th>Modern Equivalent</th></tr>
<tr>
<td>
<p>A linear-feedback shift register (LFSR) generating pseudo-random noise:</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>16 period settings</strong> control noise 'brightness'</li>
<li><strong>2 modes</strong>: long (white noise) / short (metallic tonal)</li>
<li><strong>4-bit volume</strong> with hardware envelope</li>
<li>Every NES drum is SYNTHESIZED from noise — no samples</li>
</ul>
</td>
<td>
<p>In ReapNES Console:</p>
<ul style="margin:8px 0 0 20px;color:#999">
<li><strong>Channel Mode = 3</strong> (Noise)</li>
<li>MIDI notes map to drums: 36=kick, 38=snare, 42=hi-hat</li>
<li>Velocity = initial volume</li>
<li>ADSR envelope shapes each hit</li>
</ul>
</td>
</tr>
</table>
</div>

<h2>How We Extract the Music</h2>

<div class="code-block">NES ROM (.nes) → Headless Emulator (py65 6502 CPU) → APU Register Captures → Mesen CSV → MIDI → REAPER Project</div>

<div class="card">
<h4>Step 1: Boot the ROM</h4>
<p><code>nes_rom_capture.py</code> loads the ROM, emulates the 6502 CPU, handles mapper bank switching (MMC1, MMC3, UxROM, etc.), and simulates NMI interrupts at 60Hz. No graphics — we only care about writes to the APU registers at $4000-$4017.</p>
</div>

<div class="card">
<h4>Step 2: Capture APU Writes</h4>
<p>Every time the CPU writes to an APU register, we record it: frame number, register address, value. This is exactly what Mesen (a real NES emulator) captures — our output is format-compatible.</p>
</div>

<div class="card">
<h4>Step 3: Convert to MIDI</h4>
<p><code>mesen_to_midi.py</code> translates the register captures into standard MIDI: period changes become note-on/note-off events, volume writes become CC11, duty cycle writes become CC12. The result is a MIDI file that encodes the exact per-frame state of every NES channel.</p>
</div>

<div class="card">
<h4>Step 4: Generate REAPER Project</h4>
<p><code>generate_project.py</code> creates a REAPER DAW project with 4 tracks (one per NES channel), each loaded with the ReapNES Console JSFX synthesizer configured for the correct channel mode. Open the .rpp file in REAPER, press play, hear the NES music.</p>
</div>

<h2>The Three-Priority Cascade</h2>
<p>The ReapNES synthesizer has three input modes, auto-selected by what data arrives:</p>

<div class="card">
<h4>Priority 1: SysEx Register Replay (Maximum Fidelity)</h4>
<p>Raw APU register state encoded in MIDI SysEx messages. The synth becomes a software NES APU — it reads the registers and generates the exact waveform at the sample rate. Every hardware behavior is reproduced: sweep, phase reset, noise LFSR mode. <strong>This is the NES hardware running in software.</strong></p>
</div>

<div class="card">
<h4>Priority 2: CC11/CC12 (File Playback)</h4>
<p>Volume from CC11 (0-127 → NES 0-15), duty from CC12 (0-3), pitch from MIDI notes. This is what our ROM-extracted files use. Loses sweep unit detail and sub-semitone pitch, but captures the essential envelope and timbre perfectly.</p>
</div>

<div class="card">
<h4>Priority 3: ADSR Keyboard (Live Composing)</h4>
<p>When no file data arrives, the synth uses its own ADSR envelope to shape notes from a MIDI keyboard. Per-game presets capture each game's characteristic attack/decay/sustain/release values. This is for composers who want to write new music in the style of a specific NES game.</p>
</div>

<h2>Multi-Song Extraction</h2>
<p>Different games require different techniques to access all their songs:</p>

<table>
<tr><th>Method</th><th>How It Works</th><th>Games</th></tr>
<tr><td>Boot &amp; Capture</td><td>Music plays automatically on boot</td><td>50+ games</td></tr>
<tr><td>ZP Poke</td><td>Write song ID to a zero-page variable after boot</td><td>Final Fantasy ($4B), Zelda II ($E0)</td></tr>
<tr><td>ROM Patch</td><td>Change the <code>LDA #song_id</code> byte in boot code, reboot</td><td>Mega Man 2 ($9F53)</td></tr>
<tr><td>Hot-Swap</td><td>Switch PRG banks for one NMI frame to copy new song code to RAM</td><td>Kid Icarus</td></tr>
<tr><td>Direct Engine Call</td><td>Call the sound engine's play/tick routines directly</td><td>SMB3, Dick Tracy (Warhol)</td></tr>
</table>

</div>
<footer>NES Tone Database &mdash; <a href="index.html">Back to Games</a></footer>
</body>
</html>"""

    with open(os.path.join(output_dir, 'how-it-works.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def build_docs_page(docs, output_dir):
    """Build the Documents page."""
    cats = {}
    for d in docs:
        cat = d['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(d)

    sections = []
    for cat in ['Analysis', 'Technical', 'Skills', 'Rules', 'Extraction', 'Project']:
        if cat not in cats:
            continue
        items = []
        for d in sorted(cats[cat], key=lambda x: x['title']):
            items.append(f'<tr><td><span class="tag">{d["project"]}</span></td><td>{d["title"]}</td><td style="color:#555;font-size:12px">{d["preview"][:120]}</td></tr>')
        sections.append(f"""
        <h3>{cat} ({len(cats[cat])})</h3>
        <table>
        <tr><th style="width:120px">Project</th><th>Document</th><th>Preview</th></tr>
        {''.join(items)}
        </table>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Documents — NES Tone Database</title>
<style>{SHARED_CSS}</style>
</head>
<body>
{nav_bar("docs")}
<div class="container">

<h1>Documentation Library</h1>
<p class="subtitle">{len(docs)} technical documents across 4 NES project repositories</p>

<input type="text" class="search-box" placeholder="Search documents..." oninput="document.querySelectorAll('table tr:not(:first-child)').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(this.value.toLowerCase())?'':'none')">

{''.join(sections)}

</div>
<footer>NES Tone Database &mdash; <a href="index.html">Back to Games</a></footer>
</body>
</html>"""

    with open(os.path.join(output_dir, 'docs.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def build_tones_page(tones, output_dir):
    """Build the Tones overview page."""
    # Group by game, show summary cards
    games = {}
    for t in tones:
        g = t['game']
        if g not in games:
            games[g] = []
        games[g].append(t)

    cards = []
    for game in sorted(games.keys()):
        game_tones = games[game]
        total = sum(t['note_count'] for t in game_tones)
        if total < 5:
            continue
        channels = []
        for t in sorted(game_tones, key=lambda x: x['channel']):
            ch = t['channel']
            color = CH_COLORS.get(ch, '#888')
            svg = sparkline_svg(t.get('envelope_curve', []), color, 100, 30)
            channels.append(f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span class="{CH_CSS.get(ch,"")}" style="font-size:12px;width:70px">{t["channel_name"]}</span>{svg}<span style="color:#555;font-size:11px">{t["note_count"]} notes</span></div>')

        cards.append(f"""
        <div class="card">
            <h4 style="color:#00ccff;margin-bottom:8px">{game.replace('_',' ')}</h4>
            {''.join(channels)}
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tones — NES Tone Database</title>
<style>{SHARED_CSS}</style>
</head>
<body>
{nav_bar("tones")}
<div class="container">

<h1>Tone Profiles</h1>
<p class="subtitle">{len(tones)} instrument profiles across {len(games)} games — envelope shapes and ADSR analysis for every captured channel.</p>

<input type="text" class="search-box" placeholder="Search games..." oninput="document.querySelectorAll('.card').forEach(c=>c.style.display=c.textContent.toLowerCase().includes(this.value.toLowerCase())?'':'none')">

<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px">
{''.join(cards)}
</div>

</div>
<footer>NES Tone Database &mdash; <a href="index.html">Back to Games</a></footer>
</body>
</html>"""

    with open(os.path.join(output_dir, 'tones.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', default='output/tone_database/')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(os.path.join(args.output, 'games'), exist_ok=True)

    # Load data
    with open(os.path.join(args.output, 'tones.json')) as f:
        tones = json.load(f)

    docs_path = os.path.join(args.output, 'docs_index.json')
    docs = json.load(open(docs_path)) if os.path.exists(docs_path) else []

    # Generate game data
    games = {}
    for t in tones:
        g = t['game']
        if g not in games:
            games[g] = []
        games[g].append(t)

    games_data = []
    for game_name in sorted(games.keys()):
        game_tones = games[game_name]
        total = sum(t['note_count'] for t in game_tones)
        if total < 5:
            continue

        # Dedupe by channel
        channels = {}
        for t in game_tones:
            ch = t['channel']
            if ch not in channels or t['note_count'] > channels[ch]['note_count']:
                channels[ch] = t

        game_data = {
            'game': game_name,
            'display_name': game_name.replace('_', ' '),
            'total_notes': total,
            'num_channels': len(channels),
            'instruments': list(channels.values()),
        }
        games_data.append(game_data)

    print(f"Building website: {len(games_data)} games, {len(tones)} tones, {len(docs)} docs")

    # Build all pages
    for g in games_data:
        build_game_page(g, args.output)
    print(f"  {len(games_data)} game pages")

    build_index(games_data, tones, docs, args.output)
    print("  index.html")

    build_how_it_works(args.output)
    print("  how-it-works.html")

    build_tones_page(tones, args.output)
    print("  tones.html")

    build_docs_page(docs, args.output)
    print("  docs.html")

    print("Done!")


if __name__ == '__main__':
    main()
