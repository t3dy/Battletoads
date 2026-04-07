#!/usr/bin/env python3
"""Build a queryable Wizards & Warriors reverse-engineering evidence database."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import mido

ROOT = Path(r"C:\Dev\NSFRIPPER")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extraction.drivers.other.wizards_and_warriors_parser import (  # noqa: E402
    ChannelInitEvent,
    CommandEvent,
    DirectNoteEvent,
    LoopCallEvent,
    LoopReturnEvent,
    StopEvent,
    TableNoteEvent,
    WizardsAndWarriorsParser,
)
from extraction.drivers.other.wizards_and_warriors_simulator import get_song_tempo_scale  # noqa: E402


DB_PATH = ROOT / "extraction" / "analysis" / "reconciled" / "ww_evidence.sqlite"
MANIFEST_PATH = ROOT / "extraction" / "manifests" / "wizards_and_warriors.json"
MIDI_PATH = ROOT / "Projects" / "Wizards_and_Warriors" / "midi" / "Wizards_&_Warriors_01_Wizards_&_Warriors_Title_audiblestate_v4.mid"
ART_PATH = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_articulation_breakthrough.json"
IR_PATH = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_audible_state_ir.json"
M3U_PATH = ROOT / "state" / "ww_ref" / "Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).m3u"
NSF_PATH = ROOT / "state" / "ww_ref" / "Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).nsf"


def midi_note_from_period(period: int, is_triangle: bool) -> int:
    import math

    if period <= (2 if is_triangle else 8):
        return 0
    div = 32 if is_triangle else 16
    freq = 1789773 / (div * (period + 1))
    return round(69 + 12 * math.log2(freq / 440))


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=DELETE;
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS sources;
        DROP TABLE IF EXISTS tracks;
        DROP TABLE IF EXISTS command_handlers;
        DROP TABLE IF EXISTS known_locations;
        DROP TABLE IF EXISTS mysterious_locations;
        DROP TABLE IF EXISTS title_parser_events;
        DROP TABLE IF EXISTS title_midi_notes;
        DROP TABLE IF EXISTS title_articulation_frames;
        DROP TABLE IF EXISTS evidence_notes;

        CREATE TABLE metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          exists_flag INTEGER NOT NULL,
          notes TEXT
        );

        CREATE TABLE tracks (
          song_number INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          pulse1_ptr TEXT,
          pulse2_ptr TEXT,
          triangle_ptr TEXT,
          noise_ptr TEXT
        );

        CREATE TABLE command_handlers (
          opcode TEXT PRIMARY KEY,
          handler_addr TEXT NOT NULL,
          status TEXT NOT NULL,
          known_meaning TEXT,
          confidence TEXT,
          notes TEXT
        );

        CREATE TABLE known_locations (
          location_id TEXT PRIMARY KEY,
          address TEXT NOT NULL,
          address_space TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          meaning TEXT,
          evidence TEXT
        );

        CREATE TABLE mysterious_locations (
          mystery_id TEXT PRIMARY KEY,
          address TEXT NOT NULL,
          address_space TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          current_hypothesis TEXT,
          evidence TEXT,
          next_test TEXT,
          priority INTEGER NOT NULL
        );

        CREATE TABLE title_parser_events (
          row_id INTEGER PRIMARY KEY AUTOINCREMENT,
          channel TEXT NOT NULL,
          event_index INTEGER NOT NULL,
          frame_start INTEGER,
          event_type TEXT NOT NULL,
          cpu_offset TEXT,
          raw_value TEXT,
          period INTEGER,
          midi_note INTEGER,
          duration_frames INTEGER,
          params_json TEXT,
          description TEXT
        );

        CREATE TABLE title_midi_notes (
          row_id INTEGER PRIMARY KEY AUTOINCREMENT,
          channel_name TEXT NOT NULL,
          midi_channel INTEGER NOT NULL,
          midi_note INTEGER NOT NULL,
          start_tick INTEGER NOT NULL,
          end_tick INTEGER NOT NULL,
          start_frame INTEGER NOT NULL,
          end_frame INTEGER NOT NULL,
          duration_frames INTEGER NOT NULL,
          source_midi TEXT NOT NULL
        );

        CREATE TABLE title_articulation_frames (
          frame INTEGER PRIMARY KEY,
          pulse1_flags INTEGER,
          pulse1_level INTEGER,
          pulse2_flags INTEGER,
          pulse2_level INTEGER,
          triangle_flags INTEGER,
          triangle_level INTEGER,
          composite_attack INTEGER NOT NULL,
          audio_high_z REAL,
          audio_low_z REAL,
          notes TEXT
        );

        CREATE TABLE evidence_notes (
          note_id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          source_ref TEXT
        );
        """
    )


def insert_metadata(conn: sqlite3.Connection) -> None:
    rows = [
        ("game", "Wizards & Warriors"),
        ("db_version", "1"),
        ("purpose", "Query current certain knowledge and unresolved reverse-engineering targets"),
        ("primary_title_midi", str(MIDI_PATH)),
    ]
    conn.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", rows)


def insert_sources(conn: sqlite3.Connection, manifest: dict) -> None:
    rows = []
    for key, path in manifest.get("evidence_sources", {}).items():
        p = Path(path)
        rows.append((key, key, str(p), int(p.exists()), "manifest evidence source"))
    for extra_id, path, kind, notes in (
        ("title_articulation_breakthrough", ART_PATH, "analysis_json", "critical phrase articulation evidence"),
        ("title_audible_state_ir", IR_PATH, "analysis_json", "first-class audible-state IR"),
        ("title_midi_audiblestate_v4", MIDI_PATH, "midi", "current title MIDI with audible-state sideband"),
        ("track_list_m3u", M3U_PATH, "m3u", "reference song titles"),
    ):
        rows.append((extra_id, kind, str(path), int(path.exists()), notes))
    conn.executemany(
        "INSERT INTO sources(source_id, kind, path, exists_flag, notes) VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def insert_tracks(conn: sqlite3.Connection, manifest: dict) -> None:
    rows = []
    for song_number, row in sorted(manifest["tracks"].items(), key=lambda kv: int(kv[0])):
        rows.append(
            (
                int(song_number),
                row["name"],
                row.get("pulse1"),
                row.get("pulse2"),
                row.get("triangle"),
                row.get("noise"),
            )
        )
    conn.executemany(
        """
        INSERT INTO tracks(song_number, name, pulse1_ptr, pulse2_ptr, triangle_ptr, noise_ptr)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def command_meanings() -> dict[str, tuple[str, str, str]]:
    return {
        "0x00": ("verified", "stop/end channel stream", "high"),
        "0x01": ("verified", "jump to absolute stream address", "high"),
        "0x02": ("partial", "clear flag bit 0 and continue", "medium"),
        "0x03": ("mystery", "consumes one parameter; exact semantic unknown", "low"),
        "0x04": ("partial", "set channel instrument/register seed bytes", "medium"),
        "0x05": ("verified", "loop call with count + target", "high"),
        "0x06": ("verified", "loop return", "high"),
        "0x07": ("partial", "set persistent duration / channel duration mode byte", "medium"),
        "0x08": ("partial", "force inline duration mode", "medium"),
        "0x09": ("partial", "song-level tempo scale / duration multiplier", "medium"),
        "0x0A": ("mystery", "set channel volume/control register; exact side effects unresolved", "low"),
    }


def insert_command_handlers(conn: sqlite3.Connection, manifest: dict) -> None:
    meanings = command_meanings()
    rows = []
    for opcode, handler in manifest["command_set"]["handlers"].items():
        status, meaning, confidence = meanings.get(opcode, ("mystery", None, "low"))
        rows.append((opcode, handler, status, meaning, confidence, "seeded from manifest + project notes"))
    conn.executemany(
        """
        INSERT INTO command_handlers(opcode, handler_addr, status, known_meaning, confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def insert_locations(conn: sqlite3.Connection) -> None:
    known = [
        ("rom_dispatch", "0xEEEE", "rom_cpu", "command_dispatch_table", "verified", "dispatch table for commands 0x00-0x0A", "parser + manifest"),
        ("rom_play", "0xEE55", "rom_cpu", "play_routine", "verified", "main NSF play routine", "NSF header + disassembly"),
        ("rom_init", "0xFFC0", "rom_cpu", "init_routine", "verified", "main NSF init routine", "NSF header"),
        ("rom_table_note", "0xEFD9", "rom_cpu", "table_note_period_table", "verified", "little-endian table-note periods", "parser + manifest"),
        ("rom_direct_period", "0xF000", "rom_cpu", "direct_period_table", "verified", "big-endian direct periods", "parser + manifest"),
        ("rom_song_ptrs", "0xEC6F", "rom_cpu", "song_pointer_table", "verified", "song/channel pointer table", "manifest"),
        ("ram_channel_flags", "0x0780", "ram", "channel_flags_base", "partial", "per-channel init flags after song init", "init emulation"),
        ("ram_channel_ptr_lo", "0x0782", "ram", "channel_pointer_lo", "verified", "per-channel stream pointer low byte after init", "init emulation"),
        ("ram_channel_ptr_hi", "0x0783", "ram", "channel_pointer_hi", "verified", "per-channel stream pointer high byte after init", "init emulation"),
        ("ram_duration_mode", "0x07E0", "ram", "duration_mode_byte", "partial", "negative = inline durations, non-negative = persistent duration", "project notes"),
        ("stream_sentinel_f1e0", "0xF1E0", "rom_cpu", "common_inactive_noise_stream", "partial", "frequently silent/sentinel-like stream for noise/inactive channels", "song survey + notes"),
    ]
    conn.executemany(
        """
        INSERT INTO known_locations(location_id, address, address_space, label, status, meaning, evidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        known,
    )

    mysteries = [
        ("cmd_03", "0xEF33", "rom_cpu", "command_0x03_handler", "open", "1-byte parameter command; may touch channel control or articulation", "handler address known, meaning unresolved", "trace handler effects vs per-frame register diffs when 0x03 appears", 10),
        ("cmd_07", "0xEF4A", "rom_cpu", "command_0x07_handler", "partial", "persistent duration setter with possible extra mode semantics", "known to alter duration behavior; full side effects unresolved", "compare channels before/after 0x07 across non-title songs", 9),
        ("cmd_08", "0xEF41", "rom_cpu", "command_0x08_handler", "partial", "forces inline duration mode; possible other state reset", "structural parse known, exact runtime semantics partial", "trace note onset alignment around 0x08 boundaries", 8),
        ("cmd_09", "0xEF37", "rom_cpu", "command_0x09_handler", "partial", "song-level tempo/duration multiplier", "known 2x/3x in songs 6 and 4", "systematically infer exact scaling math from frame counts", 8),
        ("cmd_0A", "0xEF54", "rom_cpu", "command_0x0A_handler", "open", "channel volume/control register setter", "called as 1-byte parameter command; exact hardware effect unresolved", "correlate occurrences with register writes in title and active-noise songs", 10),
        ("triangle_release", "triangle_gate", "virtual", "triangle_release_mechanism", "open", "effective release/damping state still missing beyond attack truth", "user-heard contradiction remains; current sideband fixes attack, not full damping", "infer frame-level release classes from MP3 + write/trace evidence", 10),
        ("pulse2_timbre_softening", "pulse2_output_path", "virtual", "pulse2_end_softening_mechanism", "partial", "stepped volume softening is known; remaining softness may need output-stage or articulation details", "trace shows real 13->9->6->3 volume drops", "separate output filter effects from attack envelope effects", 6),
    ]
    conn.executemany(
        """
        INSERT INTO mysterious_locations(mystery_id, address, address_space, label, status, current_hypothesis, evidence, next_test, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        mysteries,
    )


def insert_title_parser_events(conn: sqlite3.Connection) -> None:
    parser = WizardsAndWarriorsParser(NSF_PATH)
    song = parser.extract_all_song_pointers()[0]
    tempo_scale = get_song_tempo_scale(parser, 1)
    rows = []

    for channel in ("pulse1", "pulse2", "triangle", "noise"):
        parsed = parser.parse_channel(song.channel_pointers[channel], channel, max_events=512, visit_limit=128)
        frame = 0
        event_index = 0
        for evt in parsed.events:
            event_type = type(evt).__name__
            cpu_offset = hex(getattr(evt, "offset_cpu", 0)) if hasattr(evt, "offset_cpu") else None
            raw_value = None
            period = None
            midi_note = None
            duration = None
            params_json = None
            description = None

            if isinstance(evt, CommandEvent):
                raw_value = hex(evt.command)
                params_json = json.dumps(evt.params)
                description = evt.description
            elif isinstance(evt, TableNoteEvent):
                raw_value = hex(evt.raw_byte)
                period = evt.period
                duration = (evt.duration or 0) * tempo_scale
                midi_note = midi_note_from_period(period, channel == "triangle")
                description = "table note"
            elif isinstance(evt, DirectNoteEvent):
                raw_value = hex(evt.control_byte)
                period = evt.period
                duration = (evt.duration or 0) * tempo_scale
                midi_note = midi_note_from_period(period, channel == "triangle")
                params_json = json.dumps({"volume_nibble": evt.volume_nibble, "period_low_byte": evt.period_low_byte})
                description = "direct period note"
            elif isinstance(evt, ChannelInitEvent):
                params_json = json.dumps(
                    {
                        "reg0": evt.reg_4000_or_4004,
                        "reg1": evt.reg_4001_or_4005,
                        "reg3": evt.reg_4003_or_4007,
                    }
                )
                description = "3-byte channel init header"
            elif isinstance(evt, LoopCallEvent):
                params_json = json.dumps({"loop_count": evt.loop_count, "target_cpu": hex(evt.target_cpu)})
                description = "loop call"
            elif isinstance(evt, LoopReturnEvent):
                description = "loop return"
            elif isinstance(evt, StopEvent):
                description = "stop"

            rows.append(
                (
                    channel,
                    event_index,
                    frame,
                    event_type,
                    cpu_offset,
                    raw_value,
                    period,
                    midi_note,
                    duration,
                    params_json,
                    description,
                )
            )
            if duration:
                frame += duration
            event_index += 1

    conn.executemany(
        """
        INSERT INTO title_parser_events(
          channel, event_index, frame_start, event_type, cpu_offset, raw_value,
          period, midi_note, duration_frames, params_json, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def insert_title_midi_notes(conn: sqlite3.Connection) -> None:
    mid = mido.MidiFile(str(MIDI_PATH))
    channel_names = {0: "pulse1", 1: "pulse2", 2: "triangle", 3: "noise"}
    open_notes: dict[tuple[int, int], int] = {}
    rows = []
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if not hasattr(msg, "channel"):
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes[(msg.channel, msg.note)] = abs_tick
            elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in open_notes:
                    start_tick = open_notes.pop(key)
                    end_tick = abs_tick
                    rows.append(
                        (
                            channel_names.get(msg.channel, f"ch{msg.channel}"),
                            msg.channel,
                            msg.note,
                            start_tick,
                            end_tick,
                            start_tick // 16,
                            end_tick // 16,
                            max(0, (end_tick - start_tick) // 16),
                            str(MIDI_PATH),
                        )
                    )
    conn.executemany(
        """
        INSERT INTO title_midi_notes(
          channel_name, midi_channel, midi_note, start_tick, end_tick,
          start_frame, end_frame, duration_frames, source_midi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def insert_title_articulation(conn: sqlite3.Connection) -> None:
    ir = json.loads(IR_PATH.read_text(encoding="utf-8"))
    frame_rows = []

    def encode_flags(ch_state: dict, composite_attack: bool) -> int:
        flags = 0
        if ch_state["parser_boundary"]:
            flags |= 0x01
        if ch_state["hidden_retrigger"]:
            flags |= 0x02
        if ch_state["visible_period_attack"]:
            flags |= 0x04
        if composite_attack:
            flags |= 0x08
        if ch_state["sounding"]:
            flags |= 0x10
        return flags

    for row in ir["frame_audible_state_ir"]["frames"]:
        ch = row["channels"]
        frame_rows.append(
            (
                row["frame"],
                encode_flags(ch["pulse1"], row["composite_attack"]),
                ch["pulse1"]["effective_level"],
                encode_flags(ch["pulse2"], row["composite_attack"]),
                ch["pulse2"]["effective_level"],
                encode_flags(ch["triangle"], row["composite_attack"]),
                ch["triangle"]["effective_level"],
                int(bool(row["composite_attack"])),
                row.get("audio_high_z_phrase"),
                row.get("audio_low_z_phrase"),
                json.dumps(
                    {
                        "composite_attack_channels": row["composite_attack_channels"],
                        "parser_attack_channels": row["parser_attack_channels"],
                        "visible_period_attack_channels": row["visible_period_attack_channels"],
                    }
                ),
            )
        )
    conn.executemany(
        """
        INSERT INTO title_articulation_frames(
          frame, pulse1_flags, pulse1_level, pulse2_flags, pulse2_level,
          triangle_flags, triangle_level, composite_attack,
          audio_high_z, audio_low_z, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        frame_rows,
    )


def insert_notes(conn: sqlite3.Connection) -> None:
    notes = [
        (
            "n1",
            "architecture",
            "Plain MIDI is too lossy for title fidelity",
            "The title phrase has same-pitch attacks that do not appear as new latched periods; note-only and latch-only exports both miss them.",
            str(IR_PATH),
        ),
        (
            "n2",
            "title_phrase",
            "Composite attack at frame 960/961",
            "Pulse1 and triangle both carry hidden retrigger truth at the same phrase point, and the MP3 shows the strongest bright onset there.",
            str(ART_PATH),
        ),
        (
            "n3",
            "open_problem",
            "Triangle release/damping remains unresolved",
            "Attack truth is now modeled better than before, but the user-heard bass over-ring implies the effective damping/release layer is still incomplete.",
            str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_title_playback_contract_update.md'),
        ),
    ]
    conn.executemany(
        "INSERT INTO evidence_notes(note_id, category, title, body, source_ref) VALUES (?, ?, ?, ?, ?)",
        notes,
    )


def build_db() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        insert_metadata(conn)
        insert_sources(conn, manifest)
        insert_tracks(conn, manifest)
        insert_command_handlers(conn, manifest)
        insert_locations(conn)
        insert_title_parser_events(conn)
        insert_title_midi_notes(conn)
        insert_title_articulation(conn)
        insert_notes(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    build_db()
    print(DB_PATH)
