#!/usr/bin/env python3
"""Build SQLite database of NES tone profiles and generate static HTML browser.

Reads tones.json from extract_tones.py and produces:
1. tone_database/tones.db — SQLite database
2. tone_database/index.html — browsable single-page site

Usage:
    python scripts/build_tone_db.py -i output/tone_database/tones.json -o output/tone_database/
"""

import argparse
import json
import os
import sqlite3


def build_database(tones, db_path):
    """Build SQLite database from tone profiles."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS tones")
    c.execute("""
        CREATE TABLE tones (
            id INTEGER PRIMARY KEY,
            game TEXT,
            channel INTEGER,
            channel_name TEXT,
            note_count INTEGER,
            attack_ms INTEGER,
            decay_ms INTEGER,
            sustain_ratio REAL,
            release_ms INTEGER,
            peak_volume INTEGER,
            dominant_shape TEXT,
            dominant_duty INTEGER,
            duty_name TEXT,
            envelope_curve TEXT,
            note_range_lo INTEGER,
            note_range_hi INTEGER,
            avg_duration_ms INTEGER,
            description TEXT
        )
    """)

    for tone in tones:
        c.execute("""
            INSERT INTO tones (game, channel, channel_name, note_count,
                attack_ms, decay_ms, sustain_ratio, release_ms,
                peak_volume, dominant_shape, dominant_duty, duty_name,
                envelope_curve, note_range_lo, note_range_hi,
                avg_duration_ms, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tone['game'], tone['channel'], tone['channel_name'], tone['note_count'],
            tone['adsr']['attack_ms'], tone['adsr']['decay_ms'],
            tone['adsr']['sustain_ratio'], tone['adsr']['release_ms'],
            tone['peak_volume'], tone['dominant_shape'],
            tone['dominant_duty'], tone['duty_name'],
            json.dumps(tone['envelope_curve']),
            tone['note_range'][0], tone['note_range'][1],
            tone['avg_duration_ms'], tone['description'],
        ))

    conn.commit()
    print(f"Saved {len(tones)} tones to {db_path}")
    return conn


def generate_html(tones, output_path):
    """Generate a static HTML tone browser."""

    # Group tones by game, dedup
    games = {}
    for tone in tones:
        game = tone['game']
        if game not in games:
            games[game] = []
        # Skip if we already have this channel for this game
        existing_channels = [t['channel'] for t in games[game]]
        if tone['channel'] not in existing_channels:
            games[game].append(tone)

    # Sort games alphabetically
    sorted_games = sorted(games.keys())

    # Build tone cards
    cards_html = []
    for game in sorted_games:
        game_tones = sorted(games[game], key=lambda t: t['channel'])
        total_notes = sum(t['note_count'] for t in game_tones)
        if total_notes < 5:
            continue

        channels_html = []
        for tone in game_tones:
            # SVG sparkline for envelope curve
            curve = tone['envelope_curve']
            if not curve or max(curve) == 0:
                svg = '<svg width="120" height="40" class="sparkline"><text x="10" y="25" fill="#666" font-size="10">no data</text></svg>'
            else:
                max_val = max(curve) or 1
                points = []
                for i, v in enumerate(curve):
                    x = i * (120 / max(len(curve) - 1, 1))
                    y = 38 - (v / max_val * 36)
                    points.append(f"{x:.1f},{y:.1f}")
                polyline = " ".join(points)
                svg = f'<svg width="120" height="40" class="sparkline"><polyline points="{polyline}" fill="none" stroke="{_channel_color(tone["channel"])}" stroke-width="2"/></svg>'

            # ADSR badge
            adsr = tone['adsr']
            adsr_str = f"A:{adsr['attack_ms']}ms D:{adsr['decay_ms']}ms S:{round(adsr['sustain_ratio']*100)}% R:{adsr['release_ms']}ms"

            # Duty badge
            duty_html = f'<span class="duty duty-{tone["dominant_duty"]}">{tone["duty_name"]}</span>' if tone['channel'] < 2 else ''

            # Shape badge
            shape_class = tone['dominant_shape']

            channels_html.append(f"""
                <div class="channel ch-{tone['channel']}">
                    <div class="ch-header">
                        <span class="ch-name">{tone['channel_name']}</span>
                        <span class="note-count">{tone['note_count']} notes</span>
                        {duty_html}
                    </div>
                    <div class="ch-body">
                        {svg}
                        <div class="adsr"><span class="shape-badge {shape_class}">{tone['dominant_shape']}</span> {adsr_str}</div>
                        <div class="desc">{tone['description']}</div>
                    </div>
                </div>
            """)

        cards_html.append(f"""
            <div class="game-card" data-game="{game.lower()}">
                <h3>{game.replace('_', ' ')}</h3>
                <div class="channels">
                    {''.join(channels_html)}
                </div>
            </div>
        """)

    # Stats
    total_games = len([g for g in sorted_games if sum(t['note_count'] for t in games[g]) >= 5])
    total_tones = sum(len(games[g]) for g in sorted_games)
    total_notes = sum(t['note_count'] for ts in games.values() for t in ts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NES Tone Database — ReapNES</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Courier New', monospace; background: #0a0a0a; color: #e0e0e0; padding: 20px; }}
h1 {{ color: #00ff88; font-size: 24px; margin-bottom: 5px; }}
.subtitle {{ color: #888; margin-bottom: 20px; font-size: 14px; }}
.stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
.stat {{ background: #1a1a2e; padding: 10px 15px; border-radius: 6px; border: 1px solid #333; }}
.stat-num {{ color: #00ff88; font-size: 24px; font-weight: bold; }}
.stat-label {{ color: #888; font-size: 11px; }}
.search {{ width: 100%; padding: 10px; margin-bottom: 20px; background: #111; border: 1px solid #333; color: #fff; font-family: inherit; font-size: 14px; border-radius: 6px; }}
.search:focus {{ outline: none; border-color: #00ff88; }}
.filters {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
.filter-btn {{ padding: 6px 14px; background: #1a1a2e; border: 1px solid #333; color: #aaa; cursor: pointer; border-radius: 4px; font-family: inherit; font-size: 12px; }}
.filter-btn:hover {{ border-color: #00ff88; color: #fff; }}
.filter-btn.active {{ background: #00ff88; color: #000; border-color: #00ff88; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; }}
.game-card {{ background: #111; border: 1px solid #222; border-radius: 8px; padding: 16px; }}
.game-card h3 {{ color: #00ccff; margin-bottom: 12px; font-size: 16px; border-bottom: 1px solid #222; padding-bottom: 8px; }}
.channel {{ margin-bottom: 10px; padding: 8px; background: #0a0a1a; border-radius: 4px; border-left: 3px solid #333; }}
.ch-0 {{ border-left-color: #ff6b6b; }}
.ch-1 {{ border-left-color: #ffa94d; }}
.ch-2 {{ border-left-color: #51cf66; }}
.ch-3 {{ border-left-color: #748ffc; }}
.ch-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
.ch-name {{ font-weight: bold; font-size: 12px; }}
.note-count {{ color: #666; font-size: 11px; }}
.duty {{ font-size: 10px; padding: 2px 6px; background: #2a2a3e; border-radius: 3px; color: #ddd; }}
.ch-body {{ display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; }}
.sparkline {{ flex-shrink: 0; background: #0d0d1a; border-radius: 3px; }}
.adsr {{ font-size: 10px; color: #888; }}
.shape-badge {{ padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 4px; }}
.shape-badge.percussive {{ background: #4a1a1a; color: #ff6b6b; }}
.shape-badge.sustained {{ background: #1a3a1a; color: #51cf66; }}
.shape-badge.decaying {{ background: #3a3a1a; color: #ffa94d; }}
.shape-badge.swell {{ background: #1a1a4a; color: #748ffc; }}
.shape-badge.flat {{ background: #2a2a2a; color: #aaa; }}
.shape-badge.silent {{ background: #1a1a1a; color: #444; }}
.desc {{ font-size: 11px; color: #777; line-height: 1.4; margin-top: 4px; }}
.hidden {{ display: none; }}
footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #222; color: #444; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>NES Tone Database</h1>
<p class="subtitle">Extracted from ROM emulation via ReapNES Studio &mdash; {total_games} games, {total_tones} instrument profiles, {total_notes:,} notes analyzed</p>

<div class="stats">
    <div class="stat"><div class="stat-num">{total_games}</div><div class="stat-label">GAMES</div></div>
    <div class="stat"><div class="stat-num">{total_tones}</div><div class="stat-label">TONE PROFILES</div></div>
    <div class="stat"><div class="stat-num">{total_notes:,}</div><div class="stat-label">NOTES ANALYZED</div></div>
</div>

<input type="text" class="search" placeholder="Search games..." oninput="filterGames(this.value)">

<div class="filters">
    <button class="filter-btn active" onclick="filterShape('all', this)">All Shapes</button>
    <button class="filter-btn" onclick="filterShape('percussive', this)">Percussive</button>
    <button class="filter-btn" onclick="filterShape('sustained', this)">Sustained</button>
    <button class="filter-btn" onclick="filterShape('decaying', this)">Decaying</button>
    <button class="filter-btn" onclick="filterShape('swell', this)">Swell</button>
</div>

<div class="grid">
{''.join(cards_html)}
</div>

<footer>
    Generated by extract_tones.py + build_tone_db.py &mdash; NES ROM emulation via nes_rom_capture.py
</footer>

<script>
function filterGames(query) {{
    const cards = document.querySelectorAll('.game-card');
    const q = query.toLowerCase();
    cards.forEach(card => {{
        card.classList.toggle('hidden', !card.dataset.game.includes(q));
    }});
}}

let activeShape = 'all';
function filterShape(shape, btn) {{
    activeShape = shape;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.game-card').forEach(card => {{
        if (shape === 'all') {{ card.classList.remove('hidden'); return; }}
        const badges = card.querySelectorAll('.shape-badge');
        const match = Array.from(badges).some(b => b.textContent === shape);
        card.classList.toggle('hidden', !match);
    }});
}}
</script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated {output_path}")


def _channel_color(ch):
    return ['#ff6b6b', '#ffa94d', '#51cf66', '#748ffc'][ch] if ch < 4 else '#888'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', default='output/tone_database/tones.json')
    parser.add_argument('-o', '--output', default='output/tone_database/')
    args = parser.parse_args()

    with open(args.input) as f:
        tones = json.load(f)

    os.makedirs(args.output, exist_ok=True)

    # Build SQLite DB
    db_path = os.path.join(args.output, 'tones.db')
    build_database(tones, db_path)

    # Generate HTML
    html_path = os.path.join(args.output, 'index.html')
    generate_html(tones, html_path)


if __name__ == '__main__':
    main()
