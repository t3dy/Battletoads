#!/usr/bin/env python3
"""Generate REAPER projects (.RPP) for NES-style music production.

Creates ready-to-open .RPP files with:
- Named tracks with ReapNES Console JSFX instruments loaded
- MIDI input configured (all devices, all channels, monitoring ON)
- Optional inline MIDI items from .mid files
- Correct RPP v7 format (tested with REAPER v7.27)
- Keyboard Mode enabled for live MIDI keyboard play

Usage:
    python generate_project.py --generic                     # Blank NES session
    python generate_project.py --song-set smb1_overworld     # Game palette
    python generate_project.py --midi file.mid               # MIDI import
    python generate_project.py --list-sets                   # List palettes
    python generate_project.py --all                         # Rebuild all
    python generate_project.py --midi extracted.mid --nes-native -o custom.rpp
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SONG_SETS_DIR = REPO_ROOT / "studio" / "song_sets"
PRESETS_DIR = REPO_ROOT / "studio" / "presets"
PROJECTS_DIR = REPO_ROOT / "studio" / "reaper_projects"

# Track colors (REAPER PEAKCOL format)
COLORS = {
    "pulse1": 16576606,
    "pulse2": 10092441,
    "triangle": 16744192,
    "noise": 11184810,
}

CHANNEL_LABELS = {
    "pulse1": "NES - Pulse 1",
    "pulse2": "NES - Pulse 2",
    "triangle": "NES - Triangle",
    "noise": "NES - Noise / Drums",
}

MIDI_CHANNELS = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}

# ReapNES_Console slider defaults (sequential 1-38):
#  1-8:   P1 Duty, Vol, Enable, Attack, Decay, Sustain, Release, Duty End
#  9-16:  P2 Duty, Vol, Enable, Attack, Decay, Sustain, Release, Duty End
# 17-19:  Tri Enable, Attack, Release
# 20-25:  Noise Period, Mode, Vol, Enable, Attack, Decay
# 26-27:  Vibrato Rate, Depth
# 28-31:  Mix (P1, P2, Tri, Noise)
# 32:     Master Gain
# 33:     Channel Mode: 0=P1 Only, 1=P2 Only, 2=Tri Only, 3=Noise Only, 4=Full APU
# 34:     Keyboard Mode: 0=Off, 1=On (remaps keyboard MIDI ch to track's channel)
# 35-38:  P1 Sweep (Enable, Period, Direction, Shift)
JSFX_PLUGIN = "ReapNES Studio/ReapNES_Console.jsfx"
CONSOLE_DEFAULTS = [
    2, 15, 1,                   # P1: duty=50%, vol=15, enable=on
    10, 80, 10, 100, 2,         # P1: ADSR + duty end=50%
    1, 15, 1,                   # P2: duty=25%, vol=15, enable=on
    5, 60, 10, 80, 1,           # P2: ADSR + duty end=25%
    1, 0, 50,                   # Tri: enable=on, attack=0, release=50ms
    0, 0, 15, 1, 0, 100,        # Noise: period=0, mode=long, vol=15, enable=on, atk=0, dec=100
    0, 0,                       # Vibrato: rate=0, depth=0
    0.50, 0.50, 0.40, 0.30,    # Mix: P1=0.5, P2=0.5, Tri=0.4, Noise=0.3
    0.8,                        # Master gain
    4,                          # Channel Mode: Full APU (placeholder — overridden per track)
    1,                          # Keyboard Mode: ON (remap keyboard MIDI to track's channel)
    0, 0, 0, 0,                 # P1 Sweep: all off
]

# Console channel mode is at index 32 (slider33)
CONSOLE_CH_MODE_IDX = 32

# Per-channel mode values for slider33
CHANNEL_MODES = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}

# ---------------------------------------------------------------------------
#  APU2 synth (hardware-accurate register replay + ADSR keyboard fallback)
# ---------------------------------------------------------------------------
JSFX_PLUGIN_APU2 = "ReapNES Studio/ReapNES_APU2.jsfx"

# APU2 slider layout (19 sliders):
#  1:     Channel Mode (0=P1, 1=P2, 2=Tri, 3=Noise, 4=Full APU)
#  2:     Keyboard Mode (0=Off, 1=On)
#  3-8:   P1 Duty, Vol, Attack, Decay, Sustain, Release
#  9-14:  P2 Duty, Vol, Attack, Decay, Sustain, Release
#  15-16: Tri Attack, Release
#  17-18: Noise Attack, Decay
#  19:    Master Gain
APU2_DEFAULTS = [
    4,                          # Channel Mode: Full APU (overridden per track)
    1,                          # Keyboard Mode: ON
    2, 15, 0, 80, 10, 100,     # P1: duty=50%, vol=15, ADSR
    1, 15, 0, 60, 10, 80,      # P2: duty=25%, vol=15, ADSR
    0, 50,                      # Tri: attack=0, release=50ms
    0, 100,                     # Noise: attack=0, decay=100ms
    0.8,                        # Master gain
]

APU2_CH_MODE_IDX = 0  # slider1 = channel mode

APU2_CHANNEL_MODES = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}


def apu2_slider_values(game: str = "", channel: str = "pulse1") -> list[float]:
    """Build APU2 slider values for a specific game + channel."""
    vals = list(APU2_DEFAULTS)
    vals[APU2_CH_MODE_IDX] = APU2_CHANNEL_MODES.get(channel, 4)

    # Apply game-specific ADSR if available
    game_key = game.split("_")[0] if "_" in game else game
    adsr = GAME_ADSR.get(game_key, {}).get(channel, {})
    if not adsr:
        for key in GAME_ADSR:
            if game.startswith(key):
                adsr = GAME_ADSR[key].get(channel, {})
                break

    if channel == "pulse1":
        if "duty" in adsr: vals[2] = adsr["duty"]
        if "atk" in adsr: vals[4] = adsr["atk"]
        if "dec" in adsr: vals[5] = adsr["dec"]
        if "sus" in adsr: vals[6] = adsr["sus"]
        if "rel" in adsr: vals[7] = adsr["rel"]
    elif channel == "pulse2":
        if "duty" in adsr: vals[8] = adsr["duty"]
        if "atk" in adsr: vals[10] = adsr["atk"]
        if "dec" in adsr: vals[11] = adsr["dec"]
        if "sus" in adsr: vals[12] = adsr["sus"]
        if "rel" in adsr: vals[13] = adsr["rel"]
    elif channel == "triangle":
        if "atk" in adsr: vals[14] = adsr["atk"]
        if "rel" in adsr: vals[15] = adsr["rel"]
    elif channel == "noise":
        if "atk" in adsr: vals[16] = adsr["atk"]
        if "dec" in adsr: vals[17] = adsr["dec"]

    return vals

# Game-specific ADSR presets derived from .reapnes-data analysis
GAME_ADSR = {
    "MegaMan": {
        "pulse1":   {"duty": 3, "atk": 0, "dec": 300, "sus": 12, "rel": 50, "duty_end": 3},
        "pulse2":   {"duty": 3, "atk": 0, "dec": 400, "sus": 14, "rel": 50, "duty_end": 3},
        "triangle": {"atk": 0, "rel": 30},
        "noise":    {"atk": 0, "dec": 80},
    },
    "Castlevania": {
        "pulse1":   {"duty": 1, "atk": 50, "dec": 0, "sus": 4, "rel": 40, "duty_end": 1},
        "pulse2":   {"duty": 2, "atk": 0, "dec": 120, "sus": 1, "rel": 30, "duty_end": 2},
        "triangle": {"atk": 0, "rel": 40},
        "noise":    {"atk": 0, "dec": 120},
    },
    "CastlevaniaII": {
        "pulse1":   {"duty": 2, "atk": 0, "dec": 200, "sus": 10, "rel": 60, "duty_end": 2},
        "pulse2":   {"duty": 1, "atk": 0, "dec": 150, "sus": 8, "rel": 50, "duty_end": 1},
        "triangle": {"atk": 0, "rel": 50},
        "noise":    {"atk": 0, "dec": 100},
    },
    "Metroid": {
        "pulse1":   {"duty": 2, "atk": 20, "dec": 0, "sus": 6, "rel": 80, "duty_end": 2},
        "pulse2":   {"duty": 2, "atk": 20, "dec": 0, "sus": 6, "rel": 80, "duty_end": 2},
        "triangle": {"atk": 0, "rel": 60},
        "noise":    {"atk": 0, "dec": 150},
    },
}


def console_slider_values(game: str = "", channel: str = "pulse1") -> list[float]:
    """Build Console slider values for a specific game + channel."""
    vals = list(CONSOLE_DEFAULTS)
    vals[CONSOLE_CH_MODE_IDX] = CHANNEL_MODES.get(channel, 4)

    # Apply game-specific ADSR if available
    game_key = game.split("_")[0] if "_" in game else game
    adsr = GAME_ADSR.get(game_key, {}).get(channel, {})
    if not adsr:
        for key in GAME_ADSR:
            if game.startswith(key):
                adsr = GAME_ADSR[key].get(channel, {})
                break

    if channel == "pulse1":
        if "duty" in adsr: vals[0] = adsr["duty"]
        if "atk" in adsr: vals[3] = adsr["atk"]
        if "dec" in adsr: vals[4] = adsr["dec"]
        if "sus" in adsr: vals[5] = adsr["sus"]
        if "rel" in adsr: vals[6] = adsr["rel"]
        if "duty_end" in adsr: vals[7] = adsr["duty_end"]
    elif channel == "pulse2":
        if "duty" in adsr: vals[8] = adsr["duty"]
        if "atk" in adsr: vals[11] = adsr["atk"]
        if "dec" in adsr: vals[12] = adsr["dec"]
        if "sus" in adsr: vals[13] = adsr["sus"]
        if "rel" in adsr: vals[14] = adsr["rel"]
        if "duty_end" in adsr: vals[15] = adsr["duty_end"]
    elif channel == "triangle":
        if "atk" in adsr: vals[17] = adsr["atk"]
        if "rel" in adsr: vals[18] = adsr["rel"]
    elif channel == "noise":
        if "atk" in adsr: vals[23] = adsr["atk"]
        if "dec" in adsr: vals[24] = adsr["dec"]

    return vals


def make_guid() -> str:
    """Generate a REAPER-style GUID."""
    return "{" + str(uuid.uuid4()).upper() + "}"


def fmt_slider_values(values: list[float], total: int = 64) -> str:
    """Format slider values as 64 space-separated fields (dash for unused)."""
    parts = []
    for i in range(total):
        if i < len(values):
            v = values[i]
            if isinstance(v, float) and v != int(v):
                parts.append(f"{v:.6f}")
            else:
                parts.append(f"{int(v)}" if v == int(v) else f"{v}")
        else:
            parts.append("-")
    return " ".join(parts)


# ---------------------------------------------------------------------------
#  RPP building blocks
# ---------------------------------------------------------------------------

def rpp_header(tempo: float = 120.0, title: str = "") -> str:
    """Generate a full RPP header matching REAPER's own saved-project format.

    All fields are derived from a known-good user-created project (Console_Test.rpp)
    where MIDI keyboard input works correctly.  Do NOT remove fields without
    testing in REAPER — the full header is required for proper audio/MIDI
    graph initialization.
    """
    return f"""<REAPER_PROJECT 0.1 "7.27/win64" 1707000000
  <NOTES 0 2
    |ReapNES Studio Project
    |{title}
  >
  RIPPLE 0
  GROUPOVERRIDE 0 0 0
  AUTOXFADE 129
  ENVATTACH 3
  POOLEDENVATTACH 0
  MIXERUIFLAGS 11 48
  ENVFADESZ10 40
  PEAKGAIN 1
  FEEDBACK 0
  PANLAW 1
  PROJOFFS 0 0 0
  MAXPROJLEN 0 0
  GRID 3199 8 1 8 1 0 0 0
  TIMEMODE 1 5 -1 30 0 0 -1
  VIDEO_CONFIG 0 0 65792
  PANMODE 3
  PANLAWFLAGS 3
  CURSOR 0
  ZOOM 100 0 0
  VZOOMEX 6 0
  USE_REC_CFG 0
  RECMODE 1
  SMPTESYNC 0 30 100 40 1000 300 0 0 1 0 0
  LOOP 0
  LOOPGRAN 0 4
  RECORD_PATH "Media" ""
  <RECORD_CFG
    ZXZhdxgAAQ==
  >
  <APPLYFX_CFG
  >
  RENDER_FILE ""
  RENDER_PATTERN ""
  RENDER_FMT 0 2 0
  RENDER_1X 0
  RENDER_RANGE 1 0 0 18 1000
  RENDER_RESAMPLE 3 0 1
  RENDER_ADDTOPROJ 0
  RENDER_STEMS 0
  RENDER_DITHER 0
  TIMELOCKMODE 1
  TEMPOENVLOCKMODE 1
  ITEMMIX 1
  DEFPITCHMODE 589824 0
  TAKELANE 1
  SAMPLERATE 44100 0 0
  <RENDER_CFG
    ZXZhdxgAAQ==
  >
  LOCK 1
  <METRONOME 6 2
    VOL 0.25 0.125
    BEATLEN 4
    FREQ 1760 880 1
    SAMPLES "" ""
    SPLIGNORE 0 0
    SPLDEF 2 660 "" 0
    SPLDEF 3 440 "" 0
    PATTERN 0 169
    PATTERNSTR ABBB
    MULT 1
  >
  GLOBAL_AUTO -1
  TEMPO {tempo} 4 4
  PLAYRATE 1 0 0.25 4
  SELECTION 0 0
  SELECTION2 0 0
  MASTERAUTOMODE 0
  MASTERTRACKHEIGHT 0 0
  MASTERPEAKCOL 16576
  MASTERMUTESOLO 0
  MASTERTRACKVIEW 0 0.6667 0.5 0.5 0 0 0 0 0 0 0 0 0 0
  MASTERHWOUT 0 0 1 0 0 0 0 -1
  MASTER_NCH 2 2
  MASTER_VOLUME 1 0 -1 -1 1
  MASTER_PANMODE 3
  MASTER_PANLAWFLAGS 3
  MASTER_FX 1
  MASTER_SEL 0
  <MASTERPLAYSPEEDENV
    EGUID {make_guid()}
    ACT 0 -1
    VIS 0 1 1
    LANEHEIGHT 0 0
    ARM 0
    DEFSHAPE 0 -1 -1
  >
  <TEMPOENVEX
    EGUID {make_guid()}
    ACT 1 -1
    VIS 1 0 1
    LANEHEIGHT 0 0
    ARM 0
    DEFSHAPE 1 -1 -1
  >
  <PROJBAY
  >"""


def rpp_track(
    name: str,
    color: int,
    slider_values: list[float] | None = None,
    midi_file: str = "",
    midi_length: float = 0,
    armed: bool = True,
    selected: bool = False,
    jsfx_plugin: str = "",
    midi_events: list[str] | None = None,
    ticks_per_beat: int = 480,
) -> str:
    """Generate a complete track block matching REAPER's saved-project format.

    All track fields are derived from a known-good user-created project
    (Console_Test.rpp) where MIDI keyboard input works correctly.

    Args:
        name: Track display name
        color: PEAKCOL color value
        slider_values: JSFX slider values (defaults used if None)
        midi_file: Absolute path to .mid file (used for fallback FILE ref)
        midi_length: Length of MIDI item in seconds
        armed: Whether to arm track for MIDI recording with monitoring
        selected: Whether this track is selected (first track should be True)
        jsfx_plugin: Override JSFX plugin path (default: JSFX_PLUGIN)
        midi_events: Inline MIDI events (E/X lines) for HASDATA embedding.
                     When provided, MIDI data is embedded directly in the RPP
                     for immediate playback. FILE reference is NOT used.
        ticks_per_beat: PPQ for HASDATA header (default 480)
    """
    plugin = jsfx_plugin if jsfx_plugin else JSFX_PLUGIN
    vals = slider_values if slider_values is not None else list(CONSOLE_DEFAULTS)
    params = fmt_slider_values(vals)
    track_guid = make_guid()

    # REC field: armed input monitor mode monitor_media preserve_pdc path
    # 5088 = 4096 (MIDI) + (31 << 5) (all devices) + 0 (all channels)
    # Device 31 = "All MIDI Inputs" in REAPER v7.27
    # CRITICAL: Always set input=5088 even when not armed. If input=0,
    # REAPER forgets the MIDI routing and defaults to audio input when
    # the user manually arms the track later.
    rec_armed = 1 if armed else 0
    rec_line = f"    REC {rec_armed} 5088 1 0 0 0 0 0"

    lines = []
    lines.append(f"  <TRACK {track_guid}")
    lines.append(f'    NAME "{name}"')
    lines.append(f"    PEAKCOL {color}")
    lines.append(f"    BEAT -1")
    lines.append(f"    AUTOMODE 0")
    lines.append(f"    PANLAWFLAGS 3")
    lines.append(f"    VOLPAN 1 0 -1 -1 1")
    lines.append(f"    MUTESOLO 0 0 0")
    lines.append(f"    IPHASE 0")
    lines.append(f"    PLAYOFFS 0 1")
    lines.append(f"    ISBUS 0 0")
    lines.append(f"    BUSCOMP 0 0 0 0 0")
    lines.append(f"    SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0")
    lines.append(f"    FIXEDLANES 9 0 0 0 0")
    lines.append(f"    SEL {1 if selected else 0}")
    lines.append(rec_line)
    lines.append(f"    VU 2")
    lines.append(f"    TRACKHEIGHT 0 0 0 0 0 0 0")
    lines.append(f"    INQ 0 0 0 0.5 100 0 0 100")
    lines.append(f"    NCHAN 2")
    lines.append(f"    FX 1")
    lines.append(f"    TRACKID {track_guid}")
    lines.append(f"    PERF 0")
    lines.append(f"    MIDIOUT -1")
    lines.append(f"    MAINSEND 1 0")
    # FX chain
    lines.append(f"    <FXCHAIN")
    lines.append(f"      WNDRECT 24 52 700 560")
    lines.append(f"      SHOW 0")
    lines.append(f"      LASTSEL 0")
    lines.append(f"      DOCKED 0")
    lines.append(f"      BYPASS 0 0 0")
    lines.append(f'      <JS "{plugin}" ""')
    lines.append(f"        {params}")
    lines.append(f"      >")
    lines.append(f"      FLOATPOS 0 0 0 0")
    lines.append(f"      FXID {make_guid()}")
    lines.append(f"      WAK 0 0")
    lines.append(f"    >")

    # MIDI item — inline HASDATA (plays back directly) or FILE reference
    if midi_events or midi_file:
        item_guid = make_guid()
        lines.append(f"    <ITEM")
        lines.append(f"      POSITION 0")
        lines.append(f"      LENGTH {midi_length}")
        lines.append(f"      LOOP 0")
        lines.append(f"      ALLTAKES 0")
        lines.append(f"      FADEIN 0 0 0 0 0 0 0")
        lines.append(f"      FADEOUT 0 0 0 0 0 0 0")
        lines.append(f"      MUTE 0 0")
        lines.append(f"      SEL 0")
        lines.append(f"      IGUID {item_guid}")
        if midi_events:
            # Embed MIDI data inline — REAPER plays this immediately
            lines.append(f"      <SOURCE MIDI")
            lines.append(f"        HASDATA 1 {ticks_per_beat} QN")
            lines.append(f"        CCINTERP 32")
            for evt in midi_events:
                lines.append(f"        {evt}")
            lines.append(f"        E 0 ff 2f 00")
            lines.append(f"      >")
        else:
            # Fallback: external file reference
            midi_path_fwd = midi_file.replace("\\", "/")
            lines.append(f'      <SOURCE MIDI')
            lines.append(f'        FILE "{midi_path_fwd}"')
            lines.append(f"      >")
        lines.append(f"    >")

    lines.append(f"  >")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  MIDI file conversion
# ---------------------------------------------------------------------------

def midi_track_to_events(track, sysex_track=None) -> list[str]:
    """Convert a mido track to RPP E/X event lines.

    Channel messages become E lines. SysEx messages become X lines.
    Meta events are skipped because REAPER's inline MIDI parser can
    choke on X meta lines, causing the entire item to appear empty.

    If sysex_track is provided, its SysEx events are merged into
    the output timeline (interleaved by absolute tick position).
    This is used for APU2 projects where the SysEx register data
    lives on a separate MIDI track but needs to be embedded in
    each channel's RPP item.
    """
    # Collect channel events with absolute ticks
    ch_events = []
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        if msg.is_meta:
            continue
        if msg.type in ("note_on", "note_off", "control_change", "program_change",
                        "pitchwheel", "aftertouch", "polytouch", "channel_pressure"):
            raw = msg.bin()
            hex_data = " ".join(f"{b:02x}" for b in raw)
            ch_events.append((abs_tick, f"E", hex_data))
        elif msg.type == "sysex":
            # SysEx on this track (F0 already stripped by mido, F7 not included)
            raw_bytes = [0xF0] + list(msg.data) + [0xF7]
            hex_data = " ".join(f"{b:02x}" for b in raw_bytes)
            ch_events.append((abs_tick, "X", hex_data))

    # Collect SysEx events from separate track if provided
    if sysex_track is not None:
        abs_tick = 0
        for msg in sysex_track:
            abs_tick += msg.time
            if msg.type == "sysex":
                raw_bytes = [0xF0] + list(msg.data) + [0xF7]
                hex_data = " ".join(f"{b:02x}" for b in raw_bytes)
                ch_events.append((abs_tick, "X", hex_data))

    # Sort by absolute tick (stable sort preserves order for same tick)
    ch_events.sort(key=lambda e: e[0])

    # Convert to delta-time RPP lines
    lines = []
    prev_tick = 0
    for abs_t, prefix, hex_data in ch_events:
        delta = abs_t - prev_tick
        lines.append(f"{prefix} {delta} {hex_data}")
        prev_tick = abs_t

    return lines


def midi_file_to_events(mid) -> list[str]:
    """Merge all non-meta MIDI events from a file into one RPP event stream."""
    merged = []
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.is_meta:
                continue
            if msg.type == "sysex":
                raw_bytes = [0xF0] + list(msg.data) + [0xF7]
                hex_data = " ".join(f"{b:02x}" for b in raw_bytes)
                merged.append((abs_tick, "X", hex_data))
            else:
                raw = msg.bin()
                hex_data = " ".join(f"{b:02x}" for b in raw)
                merged.append((abs_tick, "E", hex_data))

    merged.sort(key=lambda e: e[0])
    lines = []
    prev_tick = 0
    for abs_t, prefix, hex_data in merged:
        delta = abs_t - prev_tick
        lines.append(f"{prefix} {delta} {hex_data}")
        prev_tick = abs_t
    return lines


def analyze_midi(midi_path: Path) -> dict:
    """Analyze MIDI file for auto-mapping.

    Detects which channels have notes, assigns them to NES roles
    (pulse1, pulse2, triangle, noise), and creates a remapped copy
    of the MIDI with channels reassigned to 0-3 for our plugin.
    """
    import mido
    mid = mido.MidiFile(str(midi_path))

    tempo_us = 500000
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempo_us = msg.tempo
                break

    # Collect per-channel statistics across all tracks
    channel_stats: dict[int, dict] = {}
    for i, track in enumerate(mid.tracks):
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                if ch not in channel_stats:
                    channel_stats[ch] = {
                        "notes": [], "note_count": 0, "is_drum": ch == 9,
                    }
                channel_stats[ch]["notes"].append(msg.note)
                channel_stats[ch]["note_count"] += 1

    for ch, stats in channel_stats.items():
        stats["note_min"] = min(stats["notes"])
        stats["note_max"] = max(stats["notes"])
        stats["note_avg"] = sum(stats["notes"]) / len(stats["notes"])

    return {
        "channel_stats": channel_stats,
        "duration_seconds": mid.length,
        "tempo_bpm": 60_000_000 / tempo_us,
        "ticks_per_beat": mid.ticks_per_beat,
        "mid": mid,
    }


def auto_map_channels(midi_info: dict) -> dict[str, int | None]:
    """Auto-map MIDI channels to NES roles.

    Returns dict mapping NES role -> original MIDI channel number.
    Example: {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 9}
    """
    stats = midi_info["channel_stats"]
    drums = [(ch, s) for ch, s in stats.items() if s["is_drum"]]
    melodic = sorted(
        [(ch, s) for ch, s in stats.items() if not s["is_drum"]],
        key=lambda x: x[1]["note_avg"],
    )

    mapping: dict[str, int | None] = {
        "pulse1": None, "pulse2": None, "triangle": None, "noise": None,
    }

    # Drums -> noise channel
    if drums:
        mapping["noise"] = drums[0][0]

    # Melodic: lowest avg pitch -> triangle (bass), rest -> pulses by note count
    if melodic:
        mapping["triangle"] = melodic[0][0]
        rest = sorted(melodic[1:], key=lambda x: x[1]["note_count"], reverse=True)
        if rest:
            mapping["pulse1"] = rest[0][0]
        if len(rest) >= 2:
            mapping["pulse2"] = rest[1][0]
        # If only 1-2 melodic channels, assign the busiest to pulse1 if triangle is only one
        if len(melodic) == 1:
            # Single channel - use as pulse1 instead (more musical default)
            mapping["pulse1"] = melodic[0][0]
            mapping["triangle"] = None

    return mapping


def create_remapped_midi(midi_path: Path, channel_map: dict[int, int], output_dir: Path) -> Path:
    """Create a copy of the MIDI with channels remapped to 0-3.

    Args:
        midi_path: Source MIDI file
        channel_map: Dict mapping original_channel -> new_channel (0-3)
        output_dir: Directory for remapped files

    Returns:
        Path to the remapped MIDI file
    """
    import mido
    mid = mido.MidiFile(str(midi_path))

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{midi_path.stem}_nes.mid"

    for track in mid.tracks:
        for msg in track:
            if hasattr(msg, "channel") and msg.channel in channel_map:
                msg.channel = channel_map[msg.channel]

    mid.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
#  Project generation
# ---------------------------------------------------------------------------

def _detect_game_name(path: Path) -> str:
    """Try to detect game name from file path for ADSR preset matching."""
    name = path.stem
    # Try to match against known game ADSR keys
    for key in GAME_ADSR:
        if key.lower() in name.lower().replace("_", "").replace(" ", ""):
            return key
    return ""


def generate_generic_project(output_path: Path) -> None:
    """Generic NES session - per-channel modes, Track 1 armed for keyboard play."""
    lines = [rpp_header(tempo=120, title="Generic NES Session")]
    channels = ["pulse1", "pulse2", "triangle", "noise"]
    for i, ch in enumerate(channels):
        vals = list(CONSOLE_DEFAULTS)
        vals[CONSOLE_CH_MODE_IDX] = CHANNEL_MODES[ch]
        lines.append(rpp_track(
            name=CHANNEL_LABELS[ch], color=COLORS[ch], slider_values=vals,
            armed=(i == 0),
            selected=(i == 0),
        ))
    lines.append(">")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")


def generate_song_set_project(song_set_path: Path, output_path: Path) -> None:
    """Generate from a song set JSON."""
    with open(song_set_path, encoding="utf-8") as f:
        song_set = json.load(f)

    game = song_set["game"]["title"]
    song = song_set["song"]["title"]
    tempo = song_set["song"].get("tempo_bpm", 120)

    lines = [rpp_header(tempo=tempo, title=f"{game} - {song}")]
    channels = ["pulse1", "pulse2", "triangle", "noise"]
    for i, ch in enumerate(channels):
        ch_info = song_set.get("channels", {}).get(ch, {})
        role = ch_info.get("role", "")
        name = CHANNEL_LABELS.get(ch, ch)
        if role:
            name += f" [{role}]"
        vals = console_slider_values(game=game, channel=ch)
        lines.append(rpp_track(
            name=name, color=COLORS[ch], slider_values=vals,
            armed=(i == 0),
            selected=(i == 0),
        ))
    lines.append(">")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")
    print(f"  {game} - {song} ({tempo} BPM)")


def generate_midi_project(midi_path: Path, output_path: Path,
                          song_set_path: Path | None = None,
                          nes_native: bool = False,
                          synth: str = "console",
                          full_apu: bool = False) -> None:
    """Generate project with MIDI items, optionally remapping channels to 0-3.

    Creates a remapped MIDI copy where active channels are assigned to
    NES roles (0=Pulse1, 1=Pulse2, 2=Triangle, 3=Noise) and references
    that file from each track via SOURCE MIDI FILE.

    If nes_native=True, skip remapping — MIDI already uses channels 0-3
    in NES standard format (from ROM extraction). Channel 3 = drums.
    """
    midi_info = analyze_midi(midi_path)
    tempo = midi_info["tempo_bpm"]
    duration = midi_info["duration_seconds"]
    stats = midi_info["channel_stats"]

    title = f"MIDI Import - {midi_path.stem}"
    if song_set_path:
        with open(song_set_path, encoding="utf-8") as f:
            ss = json.load(f)
        title = f"{ss['game']['title']} - {ss['song']['title']}"

    nes_ch = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}

    if nes_native:
        # NES-native MIDI: channels already at 0-3, no remapping needed
        role_map = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}
        ch_remap = {0: 0, 1: 1, 2: 2, 3: 3}  # identity
        remapped_path = midi_path  # use original file directly
    else:
        role_map = auto_map_channels(midi_info)
        ch_remap = {}
        for role, orig_ch in role_map.items():
            if orig_ch is not None:
                ch_remap[orig_ch] = nes_ch[role]
        # Create remapped MIDI
        remapped_dir = output_path.parent / "midi_remapped"
        remapped_path = create_remapped_midi(midi_path, ch_remap, remapped_dir)

    game_name = _detect_game_name(midi_path)

    use_apu2 = synth == "apu2"
    plugin_name = JSFX_PLUGIN_APU2 if use_apu2 else JSFX_PLUGIN

    print(f"  MIDI: {midi_path.name} ({duration:.0f}s, {tempo:.0f} BPM)")
    print(f"  Synth: {synth} ({plugin_name})")
    print(f"  Channel mapping:")

    lines = [rpp_header(tempo=tempo, title=title)]

    if full_apu:
        full_events = midi_file_to_events(midi_info["mid"])
        vals = apu2_slider_values(game=game_name, channel="pulse1") if use_apu2 else console_slider_values(game=game_name, channel="pulse1")
        if use_apu2:
            vals[APU2_CH_MODE_IDX] = 4
            vals[1] = 0
        else:
            vals[CONSOLE_CH_MODE_IDX] = 4
        lines.append(rpp_track(
            name="NES - Full APU",
            color=16576,
            slider_values=vals,
            midi_length=duration,
            armed=True,
            selected=True,
            jsfx_plugin=plugin_name,
            midi_events=full_events,
            ticks_per_beat=midi_info["ticks_per_beat"],
        ))
        lines.append(">")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print("    full_apu   <- merged channels 0-3 + SysEx")
        print(f"Generated: {output_path}")
        return

    roles = ["pulse1", "pulse2", "triangle", "noise"]
    for i, role in enumerate(roles):
        orig_ch = role_map.get(role)
        name = CHANNEL_LABELS[role]

        # Use game-specific ADSR if detected, otherwise defaults
        if use_apu2:
            vals = apu2_slider_values(game=game_name, channel=role)
        else:
            vals = console_slider_values(game=game_name, channel=role)

        has_midi = False
        if orig_ch is not None and orig_ch in stats:
            has_midi = True
            s = stats[orig_ch]
            note_count = s["note_count"]
            drum_tag = " (drums)" if s["is_drum"] else ""
            print(f"    {role:<10s} <- MIDI ch {orig_ch} -> NES ch {nes_ch[role]} ({note_count} notes{drum_tag})")
            name += f" [ch{orig_ch}{drum_tag}]"
        else:
            print(f"    {role:<10s} <- (none)")

        # APU2: Keyboard Mode OFF for file playback (has MIDI data),
        # ON for empty tracks (live keyboard). When ON during file playback,
        # all channels get remapped to this track's channel = chaos.
        if use_apu2:
            APU2_KB_MODE_IDX = 1  # slider2 = Keyboard Mode
            vals[APU2_KB_MODE_IDX] = 0 if has_midi else 1

        # Convert MIDI tracks to inline events for HASDATA embedding
        import mido as _mido
        track_events = None
        if has_midi:
            _mid = _mido.MidiFile(str(remapped_path))
            # Find the track that contains data for this NES channel
            target_ch = nes_ch[role]
            ch_track = None
            sysex_trk = None
            for _t in _mid.tracks:
                has_ch = any(
                    hasattr(m, "channel") and m.channel == target_ch
                    for m in _t
                )
                if has_ch:
                    ch_track = _t
                # Find the SysEx track (has sysex messages, no channel messages)
                has_sysex = any(m.type == "sysex" for m in _t)
                has_notes = any(
                    hasattr(m, "channel") and m.type == "note_on"
                    for m in _t
                )
                if has_sysex and not has_notes:
                    sysex_trk = _t
            if ch_track is not None:
                # For APU2 projects, merge SysEx track into each channel's item
                track_events = midi_track_to_events(
                    ch_track,
                    sysex_track=sysex_trk if use_apu2 else None,
                )

        midi_file_str = str(remapped_path.resolve()).replace("\\", "/") if has_midi else ""
        lines.append(rpp_track(
            name=name, color=COLORS[role], slider_values=vals,
            midi_file=midi_file_str, midi_length=duration,
            armed=(i == 0),  # first track armed for keyboard play
            selected=(i == 0),
            jsfx_plugin=plugin_name,
            midi_events=track_events,
            ticks_per_beat=midi_info["ticks_per_beat"],
        ))

    lines.append(">")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated: {output_path}")


def generate_all() -> None:
    """Rebuild all projects."""
    sets = sorted(SONG_SETS_DIR.glob("*.json"))
    sets = [s for s in sets if s.name != "song_set_schema.json"]
    for ss in sets:
        out = PROJECTS_DIR / f"{ss.stem}.rpp"
        generate_song_set_project(ss, out)
    generate_generic_project(PROJECTS_DIR / "generic_nes.rpp")


def list_song_sets() -> None:
    sets = sorted(SONG_SETS_DIR.glob("*.json"))
    sets = [s for s in sets if s.name != "song_set_schema.json"]
    if not sets:
        print("No song sets found.")
        return
    print("Available song sets:\n")
    for ss in sets:
        with open(ss, encoding="utf-8") as f:
            d = json.load(f)
        print(f"  {ss.stem:<30s} {d['game']['title']} - {d['song']['title']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate REAPER projects for NES music")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--generic", action="store_true", help="Generic NES project")
    group.add_argument("--song-set", metavar="NAME", help="Song set name")
    group.add_argument("--midi", metavar="PATH", help="Import MIDI file into project")
    group.add_argument("--list-sets", action="store_true", help="List song sets")
    group.add_argument("--all", action="store_true", help="Rebuild all")
    parser.add_argument("-o", "--output", metavar="PATH", help="Output .RPP path")
    parser.add_argument("--palette", metavar="NAME", help="Song set to use with --midi")
    parser.add_argument("--nes-native", action="store_true",
                        help="MIDI already uses NES channels 0-3 (skip remapping)")
    parser.add_argument("--synth", choices=["console", "apu2"], default="console",
                        help="Synth plugin: console (ADSR) or apu2 (register replay)")
    parser.add_argument("--full-apu", action="store_true",
                        help="Generate a single full-APU playback track instead of per-channel tracks")

    args = parser.parse_args()

    if args.list_sets:
        list_song_sets()
    elif args.generic:
        out = Path(args.output) if args.output else PROJECTS_DIR / "generic_nes.rpp"
        generate_generic_project(out)
    elif args.song_set:
        ss = SONG_SETS_DIR / f"{args.song_set}.json"
        if not ss.exists():
            print(f"Not found: {ss}", file=sys.stderr)
            sys.exit(1)
        out = Path(args.output) if args.output else PROJECTS_DIR / f"{args.song_set}.rpp"
        generate_song_set_project(ss, out)
    elif args.midi:
        midi = Path(args.midi)
        if not midi.exists():
            print(f"Not found: {midi}", file=sys.stderr)
            sys.exit(1)
        ss = SONG_SETS_DIR / f"{args.palette}.json" if args.palette else None
        out = Path(args.output) if args.output else PROJECTS_DIR / f"{midi.stem}_nes.rpp"
        generate_midi_project(midi, out, ss, nes_native=args.nes_native, synth=args.synth, full_apu=args.full_apu)
    elif args.all:
        generate_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
