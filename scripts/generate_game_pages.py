#!/usr/bin/env python3
"""Generate per-game HTML pages for the NES Tone Database website.

Reads tone profiles from tones.json and generates:
- Per-game JSON with technical details and instrument descriptions
- Individual HTML pages per game
- Games index page with filtering

Usage:
    python scripts/generate_game_pages.py -o output/tone_database/
"""

import json
import os
import argparse
import math

# ── Knowledge base ──────────────────────────────────────────────────────

DRIVER_INFO = {
    "Konami Maezawa": {
        "games": ["Castlevania", "Contra", "Gradius", "Life_Force"],
        "description": "Konami's workhorse NES driver, used across dozens of titles. Notes are nibble-packed: high 4 bits = pitch (C-B), low 4 bits = duration index. DX commands configure envelope and tempo per section.",
        "encoding": "Nibble-packed: [PPPP DDDD] where P=pitch, D=duration index. Duration = tempo × (D+1) frames.",
        "signature": "Dark, atmospheric sound. Parametric two-phase envelope (fast attack, controlled decay). Sparse but effective drum patterns.",
    },
    "Capcom": {
        "games": ["Mega_Man", "Darkwing", "Chip_n_Dale", "Duck_Tales", "Strider", "Mighty_Final", "Gargoyles", "Little_Nemo", "Ghosts_n_Goblins", "Bionic_Commando"],
        "description": "Capcom's internal NES sound engine, evolved across the Mega Man series (MM1-MM6) and Disney licensed titles. Known for extremely dense drum programming and bright pulse tones.",
        "encoding": "Octave + semitone byte. Full note identity in one byte — no separate octave command needed. Variable-width command dispatch.",
        "signature": "Bright, driving, rhythmic. Heavy noise channel usage (often 700+ hits per 80 seconds). Dual-duty pulse arrangement: 50% lead, 25% harmony. The most 'band-like' sound on NES.",
    },
    "Square": {
        "games": ["Final_Fantasy"],
        "description": "Square's NES sound engine for the Final Fantasy series. Music data starts at ROM $34010 with a Master Music Table of 23 songs × 3 channel pointers. MIDI-to-text conversion workflow.",
        "encoding": "First digit (0-B) = note (C through B). Second digit = duration (0=longest, 9=shortest). $D8-$DB = octave shift. $F = control string (tempo, instrument). $D0/$D1 = loop/repeat.",
        "signature": "Classical, arpeggiated. The Prelude's ascending arpeggio is the most recognizable NES musical motif. Minimal percussion — relies on pulse interplay for rhythm.",
    },
    "Nintendo": {
        "games": ["Kid_Icarus", "Kirby", "Metroid", "Ice_Climber", "Donkey_Kong", "Excitebike", "Balloon", "Dr_Mario", "Tetris"],
        "description": "Nintendo's first-party sound engines vary significantly per game. Some use data-driven players, others use code-as-music (songs as 6502 subroutines). Kid Icarus has a unique dual-engine architecture.",
        "encoding": "Varies by game. Kid Icarus: code-as-music + $AC88 config table. Kirby: data-driven with MMC3 banking. Early games (Ice Climber, DK): simple NROM drivers.",
        "signature": "Unpredictable and game-specific. Ranges from Kirby's lush four-channel arrangements to Metroid's sparse, atmospheric drones.",
    },
    "Rare": {
        "games": ["Battletoads", "Wizards"],
        "description": "Rare's custom NES drivers. Each game has its own engine — Battletoads uses a complex 20-command dispatch with dual-mode duration, while Wizards & Warriors uses a simpler 10-command format.",
        "encoding": "Byte index into period table. Notes ≥ $81, rest = $80, commands = $00-$7F. Duration is modal (set by command, persists). Software volume register with ramp/oscillate modes.",
        "signature": "Rich harmonies, moderate drums. Battletoads has the most complex command set of any NES driver we've analyzed (~20 opcodes).",
    },
    "Warhol": {
        "games": ["Dick_Tracy", "Maniac_Mansion", "Rocketeer", "Caesars_Palace", "Total_Recall", "Rad_Gravity", "Swords_Serpents"],
        "description": "David Warhol's driver for Realtime Associates (1990-1992). Composers created MIDI files in Cakewalk/Performer, which Warhol arranged and converted to NES format. Never uses DPCM.",
        "encoding": "MIDI-derived text format. Standard NTSC period table spanning 7 octaves. Entry points: $8029 = play_song(X), $80A0 = per-frame tick.",
        "signature": "The 'echo' instrument: hardware sweep every 13 frames creating reverb-like decay. Duty cycle basses. Square channel drums (especially in Defenders of Dynatron City).",
    },
    "Sunsoft": {
        "games": ["Batman", "Journey_to_Silius", "Blaster_Master"],
        "description": "Sunsoft's NES sound engine, famous for pushing the hardware to its limits. Journey to Silius and Blaster Master are considered among the best NES soundtracks ever made.",
        "encoding": "Data-driven player with per-channel state. Aggressive use of duty cycle switching for bass tones and rapid arpeggios for pseudo-polyphony.",
        "signature": "Punchy, bass-heavy. Blaster Master's 1063 triangle notes in one capture is the most bass-dense extraction in our collection. Deep grooves with funk influence.",
    },
    "Technos": {
        "games": ["Double_Dragon", "River_City"],
        "description": "Technos Japan's beat-em-up sound engine. Full four-channel arrangements with heavy drum programming for the action genre.",
        "encoding": "Standard data-driven player. Period table lookup with per-channel note streams.",
        "signature": "Action-oriented. Dense four-channel arrangements. Double Dragon's 1303 total notes shows balanced usage across all channels.",
    },
    "Enix": {
        "games": ["Dragon_Warrior"],
        "description": "Enix's RPG sound engine for the Dragon Quest/Dragon Warrior series. Orchestral-influenced compositions by Koichi Sugiyama.",
        "encoding": "Data-driven player. Standard period table. Song selection through RAM variable.",
        "signature": "Orchestral, stately. Three-channel focus (Sq1/Sq2/Triangle) with minimal percussion. The Overworld theme is one of the most recognizable JRPG melodies.",
    },
}

CHANNEL_EXPLAINERS = {
    0: {  # Square 1
        "hardware": "Pulse wave generator with 4 selectable duty cycles (12.5%, 25%, 50%, 75%). 11-bit period register sets frequency. Hardware envelope with 4-bit volume (0-15). Optional sweep unit for pitch bends.",
        "reaper": "In ReapNES Console: Slider 33 = Channel Mode (set to 0 for Pulse 1). CC11 controls per-frame volume. CC12 controls duty cycle (0-3 mapped to 12.5%-75%). The synth generates a bandlimited pulse wave at the specified duty ratio.",
        "role": "Usually carries the melody (lead voice). In Capcom games, uses 50% duty for warm lead tone. In Konami games, often paired with Pulse 2 in call-and-response patterns.",
    },
    1: {  # Square 2
        "hardware": "Identical hardware to Square 1 — same duty cycles, period range, and envelope. The NES treats both pulse channels equally; the distinction is purely in how composers use them.",
        "reaper": "In ReapNES Console: Slider 33 = Channel Mode (set to 1 for Pulse 2). Same CC11/CC12 controls as Pulse 1. Typically assigned a different duty cycle than Pulse 1 for timbral contrast.",
        "role": "Harmony, countermelody, or echo. Capcom typically uses 25% duty (brighter/thinner than the 50% lead). Some games use Pulse 2 for arpeggiated chord fill or bass doubling.",
    },
    2: {  # Triangle
        "hardware": "Fixed triangle waveform — no duty cycle control, no volume control (only on/off gating via the linear counter). Produces a frequency one octave LOWER than pulse channels for the same period value (32-step vs 16-step sequencer).",
        "reaper": "In ReapNES Console: Slider 33 = Channel Mode (set to 2 for Triangle). CC11 is always 127 (gate signal only). No CC12 (no duty cycle). Volume is either full or silent — articulation comes from note duration only.",
        "role": "Bass. The only channel that can produce sub-bass frequencies. Staccato triangle = punchy bass hits. Legato triangle = sustained bass lines. The lack of volume control makes it the 'loudest' channel in the mix.",
    },
    3: {  # Noise
        "hardware": "Linear-feedback shift register (LFSR) with 16 selectable periods and 2 modes (long = white noise, short = metallic/tonal). 4-bit volume with hardware envelope. No pitch in the traditional sense — period controls 'brightness'.",
        "reaper": "In ReapNES Console: Slider 33 = Channel Mode (set to 3 for Noise). Note number maps to drum sound (36=kick, 38=snare, 42=hi-hat). Velocity sets initial volume. ADSR envelope shapes the hit.",
        "role": "Percussion. Low periods = hi-hats and cymbals. Mid periods = snare. High periods = kick drums. Some games use noise for wind/explosion effects. The short LFSR mode creates metallic tones used for distinctive 'chiptune snares'.",
    },
}

SHAPE_DESCRIPTIONS = {
    "percussive": "Sharp attack with rapid decay — the note hits hard and fades quickly. Common for lead melodies in action games where each note needs to 'pop' out of the mix. ADSR: zero attack, fast decay, low sustain.",
    "sustained": "Consistent volume throughout the note with minimal decay. Creates a smooth, legato feel. Common in RPG town themes and slower pieces. ADSR: zero attack, minimal decay, high sustain.",
    "decaying": "Natural fade from peak volume — like a plucked string. The most common envelope shape on NES. Gives notes a realistic quality. ADSR: zero attack, moderate decay, moderate sustain.",
    "swell": "Volume increases over the note's duration — a crescendo effect. Rare on NES due to the per-frame volume update overhead. Used for dramatic passages. ADSR: slow attack, minimal decay, high sustain.",
    "silent": "No audible output on this channel for this game's captured section. The channel may be used in other songs.",
    "flat": "Constant volume with no shaping. Raw, unprocessed tone. Sometimes used for bass lines where the triangle's gate-only volume makes envelope shaping impossible.",
}

DUTY_DESCRIPTIONS = {
    0: {"name": "12.5%", "sound": "Thin, nasal, almost buzzy. The narrowest pulse width creates the brightest, most cutting tone. Used sparingly — often for attack transients or special effects. Think: chiptune 'sting' or harpsichord-like pluck.", "waveform": "▁▁▁▁▁▁▁█"},
    1: {"name": "25%", "sound": "Bright and hollow, like a clarinet or oboe. The default 'chiptune' sound. Clear and present in the mix without being harsh. Most Capcom harmony parts use this duty cycle.", "waveform": "▁▁▁▁▁▁██"},
    2: {"name": "50%", "sound": "Warm, full, and round — a pure square wave. The richest harmonic content of any duty cycle. Most commonly used for lead melodies. Think: classic NES main theme sound.", "waveform": "▁▁▁▁████"},
    3: {"name": "75%", "sound": "Identical to 25% but phase-inverted. Sounds the same to human ears. Some drivers alternate between 25% and 75% for a subtle phasing effect.", "waveform": "▁▁██████"},
}


def identify_driver(game_name):
    """Guess the driver family from the game name."""
    gn = game_name.lower().replace('_', ' ')
    for driver, info in DRIVER_INFO.items():
        for pattern in info["games"]:
            if pattern.lower().replace('_', ' ') in gn:
                return driver, info
    return "Unknown", {"description": "Driver not yet identified.", "encoding": "Standard NES APU data-driven player.", "signature": "Varies."}


def generate_instrument_description(tone):
    """Generate a rich 3-layer instrument description for a tone profile."""
    ch = tone['channel']
    hw = CHANNEL_EXPLAINERS.get(ch, CHANNEL_EXPLAINERS[0])
    shape_desc = SHAPE_DESCRIPTIONS.get(tone['dominant_shape'], "")

    if ch < 2:  # Pulse
        duty_info = DUTY_DESCRIPTIONS.get(tone['dominant_duty'], DUTY_DESCRIPTIONS[2])
        sonic = (
            f"{duty_info['sound']} "
            f"{shape_desc} "
            f"Average note duration: {tone['avg_duration_ms']}ms "
            f"({'rapid staccato' if tone['avg_duration_ms'] < 80 else 'moderate articulation' if tone['avg_duration_ms'] < 200 else 'legato phrasing'})."
        )
    elif ch == 2:  # Triangle
        sonic = (
            f"Pure triangle wave bass. No timbre variation possible — all expression comes from note timing. "
            f"{shape_desc} "
            f"{'Staccato bass hits.' if tone['avg_duration_ms'] < 100 else 'Sustained bass lines.' if tone['avg_duration_ms'] > 300 else 'Mixed bass articulation.'} "
            f"{tone['note_count']} notes captured."
        )
    else:  # Noise
        sonic = (
            f"Percussion channel. {tone['note_count']} hits captured. "
            f"{'Dense drum pattern — continuous beats.' if tone['note_count'] > 300 else 'Moderate percussion.' if tone['note_count'] > 50 else 'Sparse accents.'} "
            f"NES noise uses a shift register, not samples — every 'drum' is synthesized from filtered noise."
        )

    return {
        "hardware": hw["hardware"],
        "reaper_plugin": hw["reaper"],
        "sonic_character": sonic,
        "channel_role": hw["role"],
    }


def generate_game_data(game_name, game_tones):
    """Generate complete game page data."""
    driver_name, driver_info = identify_driver(game_name)

    # Deduplicate tones by channel
    channels = {}
    for tone in game_tones:
        ch = tone['channel']
        if ch not in channels or tone['note_count'] > channels[ch]['note_count']:
            channels[ch] = tone

    instruments = []
    for ch in sorted(channels.keys()):
        tone = channels[ch]
        desc = generate_instrument_description(tone)
        instruments.append({
            **tone,
            "instrument_description": desc,
        })

    total_notes = sum(t['note_count'] for t in instruments)

    return {
        "game": game_name,
        "display_name": game_name.replace('_', ' '),
        "driver_family": driver_name,
        "driver_description": driver_info.get("description", ""),
        "encoding_format": driver_info.get("encoding", ""),
        "sonic_signature": driver_info.get("signature", ""),
        "total_notes": total_notes,
        "num_channels": len(instruments),
        "instruments": instruments,
    }


def generate_game_html(game_data):
    """Generate an HTML page for one game."""
    g = game_data

    # Instrument cards
    inst_cards = []
    for inst in g['instruments']:
        ch = inst['channel']
        ch_name = inst['channel_name']
        desc = inst['instrument_description']
        adsr = inst['adsr']

        # Color per channel
        colors = ['#ff6b6b', '#ffa94d', '#51cf66', '#748ffc']
        color = colors[ch] if ch < 4 else '#888'

        # SVG sparkline
        curve = inst.get('envelope_curve', [])
        if curve and max(curve) > 0:
            mx = max(curve)
            pts = " ".join(f"{i*(200/max(len(curve)-1,1)):.0f},{78-(v/mx*76):.0f}" for i, v in enumerate(curve))
            svg = f'<svg width="200" height="80" class="sparkline"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/></svg>'
        else:
            svg = '<svg width="200" height="80" class="sparkline"><text x="50" y="45" fill="#444" font-size="12">no envelope data</text></svg>'

        # Duty waveform for pulse channels
        duty_html = ""
        if ch < 2:
            duty = inst.get('dominant_duty', 2)
            duty_info = DUTY_DESCRIPTIONS.get(duty, DUTY_DESCRIPTIONS[2])
            duty_html = f'''
                <div class="duty-section">
                    <div class="duty-label">Duty Cycle: {duty_info["name"]}</div>
                    <div class="duty-wave">{duty_info["waveform"]}</div>
                    <div class="duty-desc">{duty_info["sound"]}</div>
                </div>
            '''

        # Shape badge
        shape = inst.get('dominant_shape', 'unknown')
        shape_desc = SHAPE_DESCRIPTIONS.get(shape, "")

        inst_cards.append(f'''
            <div class="instrument-card" style="border-left-color: {color}">
                <div class="inst-header">
                    <h3 style="color: {color}">{ch_name}</h3>
                    <span class="note-badge">{inst["note_count"]} notes</span>
                </div>

                <div class="inst-body">
                    <div class="envelope-section">
                        <div class="section-label">Volume Envelope</div>
                        {svg}
                        <div class="adsr-values">
                            <span>A: {adsr["attack_ms"]}ms</span>
                            <span>D: {adsr["decay_ms"]}ms</span>
                            <span>S: {round(adsr["sustain_ratio"]*100)}%</span>
                            <span>R: {adsr["release_ms"]}ms</span>
                        </div>
                        <div class="shape-badge {shape}">{shape}</div>
                        <p class="shape-desc">{shape_desc}</p>
                    </div>

                    {duty_html}

                    <details class="explainer">
                        <summary>How the NES hardware makes this sound</summary>
                        <p>{desc["hardware"]}</p>
                    </details>

                    <details class="explainer">
                        <summary>How to recreate in REAPER (ReapNES Console)</summary>
                        <p>{desc["reaper_plugin"]}</p>
                    </details>

                    <details class="explainer">
                        <summary>What it sounds like</summary>
                        <p>{desc["sonic_character"]}</p>
                    </details>

                    <div class="channel-role">
                        <div class="section-label">Role in the mix</div>
                        <p>{desc["channel_role"]}</p>
                    </div>
                </div>
            </div>
        ''')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{g["display_name"]} — NES Tone Database</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0a; color: #d0d0d0; padding: 20px; max-width: 960px; margin: 0 auto; line-height: 1.6; }}
a {{ color: #00ccff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
h1 {{ color: #00ff88; font-size: 28px; margin-bottom: 5px; }}
h2 {{ color: #00ccff; font-size: 20px; margin: 30px 0 15px; border-bottom: 1px solid #222; padding-bottom: 8px; }}
h3 {{ font-size: 16px; margin: 0; }}
.breadcrumb {{ color: #666; font-size: 13px; margin-bottom: 15px; }}
.meta {{ display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px; }}
.meta-tag {{ background: #1a1a2e; padding: 5px 12px; border-radius: 4px; font-size: 12px; border: 1px solid #333; }}
.driver-section {{ background: #111; padding: 20px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #222; }}
.driver-section h4 {{ color: #00ff88; margin-bottom: 10px; }}
.driver-section p {{ margin-bottom: 10px; color: #aaa; font-size: 14px; }}
.encoding-box {{ background: #0d0d1a; padding: 12px; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 13px; color: #ccc; border-left: 3px solid #00ff88; margin: 10px 0; }}
.signature {{ font-style: italic; color: #888; }}
.instrument-card {{ background: #111; border: 1px solid #222; border-left: 4px solid #888; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
.inst-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
.note-badge {{ background: #1a1a2e; padding: 4px 10px; border-radius: 12px; font-size: 12px; color: #888; }}
.inst-body {{ display: flex; flex-direction: column; gap: 15px; }}
.section-label {{ font-size: 11px; text-transform: uppercase; color: #555; letter-spacing: 1px; margin-bottom: 5px; }}
.sparkline {{ background: #080812; border-radius: 4px; padding: 2px; }}
.adsr-values {{ display: flex; gap: 12px; font-size: 12px; color: #888; margin-top: 5px; }}
.adsr-values span {{ background: #1a1a2e; padding: 3px 8px; border-radius: 3px; }}
.shape-badge {{ display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 11px; margin-top: 8px; }}
.shape-badge.percussive {{ background: #3a1a1a; color: #ff6b6b; }}
.shape-badge.sustained {{ background: #1a3a1a; color: #51cf66; }}
.shape-badge.decaying {{ background: #3a3a1a; color: #ffa94d; }}
.shape-badge.swell {{ background: #1a1a4a; color: #748ffc; }}
.shape-badge.silent {{ background: #1a1a1a; color: #444; }}
.shape-desc {{ font-size: 13px; color: #777; margin-top: 8px; }}
.duty-section {{ background: #0d0d1a; padding: 12px; border-radius: 6px; }}
.duty-label {{ font-size: 12px; color: #00ff88; margin-bottom: 4px; }}
.duty-wave {{ font-family: monospace; font-size: 24px; letter-spacing: 2px; color: #00ccff; margin: 5px 0; }}
.duty-desc {{ font-size: 13px; color: #888; }}
.explainer {{ margin-top: 8px; }}
.explainer summary {{ cursor: pointer; font-size: 13px; color: #00ccff; padding: 6px 0; border-bottom: 1px solid #1a1a2e; }}
.explainer summary:hover {{ color: #fff; }}
.explainer p {{ font-size: 13px; color: #999; padding: 10px 0 5px; }}
.channel-role {{ margin-top: 5px; }}
.channel-role p {{ font-size: 13px; color: #888; }}
footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #222; color: #444; font-size: 11px; text-align: center; }}
</style>
</head>
<body>

<div class="breadcrumb"><a href="index.html">NES Tone Database</a> &rsaquo; {g["display_name"]}</div>

<h1>{g["display_name"]}</h1>

<div class="meta">
    <span class="meta-tag">Driver: {g["driver_family"]}</span>
    <span class="meta-tag">{g["num_channels"]} channels</span>
    <span class="meta-tag">{g["total_notes"]:,} notes captured</span>
</div>

<div class="driver-section">
    <h4>Sound Driver: {g["driver_family"]}</h4>
    <p>{g["driver_description"]}</p>
    <div class="encoding-box">{g["encoding_format"]}</div>
    <p class="signature">Sonic signature: {g["sonic_signature"]}</p>
</div>

<h2>Instruments</h2>
{''.join(inst_cards)}

<footer>
    <a href="index.html">&larr; Back to NES Tone Database</a> &mdash; Generated by generate_game_pages.py
</footer>

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', default='output/tone_database/')
    args = parser.parse_args()

    with open(os.path.join(args.output, 'tones.json')) as f:
        tones = json.load(f)

    # Group tones by game
    games = {}
    for tone in tones:
        g = tone['game']
        if g not in games:
            games[g] = []
        games[g].append(tone)

    # Generate pages
    games_dir = os.path.join(args.output, 'games')
    os.makedirs(games_dir, exist_ok=True)

    all_game_data = []
    for game_name in sorted(games.keys()):
        game_tones = games[game_name]
        if sum(t['note_count'] for t in game_tones) < 5:
            continue

        game_data = generate_game_data(game_name, game_tones)
        all_game_data.append(game_data)

        html = generate_game_html(game_data)
        slug = game_name.replace(' ', '_')
        with open(os.path.join(games_dir, f'{slug}.html'), 'w', encoding='utf-8') as f:
            f.write(html)

    # Save game data JSON
    with open(os.path.join(args.output, 'games_data.json'), 'w') as f:
        json.dump(all_game_data, f, indent=2)

    print(f"Generated {len(all_game_data)} game pages in {games_dir}/")
    return all_game_data


if __name__ == '__main__':
    main()
