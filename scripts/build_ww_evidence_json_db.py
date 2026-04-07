#!/usr/bin/env python3
"""Build a JSON-backed evidence database for Wizards & Warriors."""

from __future__ import annotations

import json
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


OUT_PATH = ROOT / "extraction" / "analysis" / "reconciled" / "ww_evidence_db.json"
GUIDE_PATH = ROOT / "extraction" / "analysis" / "reconciled" / "ww_evidence_db_guide.md"
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


def command_meanings() -> dict[str, dict]:
    return {
        "0x00": {"status": "verified", "meaning": "stop/end channel stream", "confidence": "high"},
        "0x01": {"status": "verified", "meaning": "jump to absolute stream address", "confidence": "high"},
        "0x02": {"status": "partial", "meaning": "clear flag bit 0 and continue", "confidence": "medium"},
        "0x03": {"status": "verified", "meaning": "skip one parameter byte and continue; no other handler-side state change", "confidence": "high"},
        "0x04": {"status": "verified", "meaning": "load 3-byte channel register shadow at $07C0/$07C1/$07C3", "confidence": "high"},
        "0x05": {"status": "verified", "meaning": "loop call with count + target", "confidence": "high"},
        "0x06": {"status": "verified", "meaning": "loop return", "confidence": "high"},
        "0x07": {"status": "verified", "meaning": "set per-channel duration mode byte at $07E0,X", "confidence": "high"},
        "0x08": {"status": "verified", "meaning": "force inline-duration sentinel by writing $FF to $07E0,X", "confidence": "high"},
        "0x09": {"status": "verified", "meaning": "set global frame-delay reload byte at $059B", "confidence": "high"},
        "0x0A": {"status": "partial", "meaning": "write one control byte into channel register shadow $07C0,X", "confidence": "high"},
    }


def build_title_parser_events() -> list[dict]:
    parser = WizardsAndWarriorsParser(NSF_PATH)
    song = parser.extract_all_song_pointers()[0]
    tempo_scale = get_song_tempo_scale(parser, 1)
    rows: list[dict] = []

    for channel in ("pulse1", "pulse2", "triangle", "noise"):
        parsed = parser.parse_channel(song.channel_pointers[channel], channel, max_events=512, visit_limit=128)
        frame = 0
        for event_index, evt in enumerate(parsed.events):
            row = {
                "channel": channel,
                "event_index": event_index,
                "frame_start": frame,
                "event_type": type(evt).__name__,
                "cpu_offset": hex(getattr(evt, "offset_cpu", 0)) if hasattr(evt, "offset_cpu") else None,
                "raw_value": None,
                "period": None,
                "midi_note": None,
                "duration_frames": None,
                "params": None,
                "description": None,
            }
            duration = 0
            if isinstance(evt, CommandEvent):
                row["raw_value"] = hex(evt.command)
                row["params"] = evt.params
                row["description"] = evt.description
            elif isinstance(evt, TableNoteEvent):
                row["raw_value"] = hex(evt.raw_byte)
                row["period"] = evt.period
                row["midi_note"] = midi_note_from_period(evt.period, channel == "triangle")
                duration = (evt.duration or 0) * tempo_scale
                row["duration_frames"] = duration
                row["description"] = "table note"
            elif isinstance(evt, DirectNoteEvent):
                row["raw_value"] = hex(evt.control_byte)
                row["period"] = evt.period
                row["midi_note"] = midi_note_from_period(evt.period, channel == "triangle")
                duration = (evt.duration or 0) * tempo_scale
                row["duration_frames"] = duration
                row["params"] = {
                    "volume_nibble": evt.volume_nibble,
                    "period_low_byte": evt.period_low_byte,
                }
                row["description"] = "direct period note"
            elif isinstance(evt, ChannelInitEvent):
                row["params"] = {
                    "reg0": evt.reg_4000_or_4004,
                    "reg1": evt.reg_4001_or_4005,
                    "reg3": evt.reg_4003_or_4007,
                }
                row["description"] = "3-byte channel init header"
            elif isinstance(evt, LoopCallEvent):
                row["params"] = {"loop_count": evt.loop_count, "target_cpu": hex(evt.target_cpu)}
                row["description"] = "loop call"
            elif isinstance(evt, LoopReturnEvent):
                row["description"] = "loop return"
            elif isinstance(evt, StopEvent):
                row["description"] = "stop"

            rows.append(row)
            frame += duration
    return rows


def build_title_midi_notes() -> list[dict]:
    mid = mido.MidiFile(str(MIDI_PATH))
    channel_names = {0: "pulse1", 1: "pulse2", 2: "triangle", 3: "noise"}
    open_notes: dict[tuple[int, int], int] = {}
    rows: list[dict] = []
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if not hasattr(msg, "channel"):
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes[(msg.channel, msg.note)] = abs_tick
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in open_notes:
                    start_tick = open_notes.pop(key)
                    end_tick = abs_tick
                    rows.append(
                        {
                            "channel_name": channel_names.get(msg.channel, f"ch{msg.channel}"),
                            "midi_channel": msg.channel,
                            "midi_note": msg.note,
                            "start_tick": start_tick,
                            "end_tick": end_tick,
                            "start_frame": start_tick // 16,
                            "end_frame": end_tick // 16,
                            "duration_frames": max(0, (end_tick - start_tick) // 16),
                            "source_midi": str(MIDI_PATH),
                        }
                    )
    return rows


def build_database() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ir = json.loads(IR_PATH.read_text(encoding="utf-8"))
    tracks = [
        {
            "song_number": int(song_number),
            "name": row["name"],
            "pulse1_ptr": row.get("pulse1"),
            "pulse2_ptr": row.get("pulse2"),
            "triangle_ptr": row.get("triangle"),
            "noise_ptr": row.get("noise"),
        }
        for song_number, row in sorted(manifest["tracks"].items(), key=lambda kv: int(kv[0]))
    ]

    sources = []
    for key, path in manifest.get("evidence_sources", {}).items():
        p = Path(path)
        sources.append({"source_id": key, "kind": key, "path": str(p), "exists": p.exists(), "notes": "manifest evidence source"})
    for source_id, path, kind, notes in (
        ("title_articulation_breakthrough", ART_PATH, "analysis_json", "critical phrase articulation evidence"),
        ("title_audible_state_ir", IR_PATH, "analysis_json", "first-class audible-state IR"),
        ("title_midi_audiblestate_v4", MIDI_PATH, "midi", "title MIDI with audible-state sideband"),
        ("track_list_m3u", M3U_PATH, "m3u", "reference song titles"),
    ):
        sources.append({"source_id": source_id, "kind": kind, "path": str(path), "exists": path.exists(), "notes": notes})

    command_handlers = []
    meanings = command_meanings()
    for opcode, handler in manifest["command_set"]["handlers"].items():
        info = meanings.get(opcode, {"status": "mystery", "meaning": None, "confidence": "low"})
        command_handlers.append(
            {
                "opcode": opcode,
                "handler_addr": handler,
                "status": info["status"],
                "known_meaning": info["meaning"],
                "confidence": info["confidence"],
                "notes": "seeded from manifest + project notes",
            }
        )

    known_locations = [
        {"location_id": "rom_dispatch", "address": "0xEEEE", "address_space": "rom_cpu", "label": "command_dispatch_table", "status": "verified", "meaning": "dispatch table for commands 0x00-0x0A", "evidence": "parser + manifest"},
        {"location_id": "rom_play", "address": "0xEE55", "address_space": "rom_cpu", "label": "play_routine", "status": "verified", "meaning": "main NSF play routine", "evidence": "NSF header + disassembly"},
        {"location_id": "rom_init", "address": "0xFFC0", "address_space": "rom_cpu", "label": "init_routine", "status": "verified", "meaning": "main NSF init routine", "evidence": "NSF header"},
        {"location_id": "rom_table_note", "address": "0xEFD9", "address_space": "rom_cpu", "label": "table_note_period_table", "status": "verified", "meaning": "little-endian table-note periods", "evidence": "parser + manifest"},
        {"location_id": "rom_direct_period", "address": "0xF000", "address_space": "rom_cpu", "label": "direct_period_table", "status": "verified", "meaning": "big-endian direct periods", "evidence": "parser + manifest"},
        {"location_id": "rom_song_ptrs", "address": "0xEC6F", "address_space": "rom_cpu", "label": "song_pointer_table", "status": "verified", "meaning": "song/channel pointer table", "evidence": "manifest"},
        {"location_id": "ram_channel_flags", "address": "0x0780", "address_space": "ram", "label": "channel_flags_base", "status": "partial", "meaning": "per-channel init flags after song init", "evidence": "init emulation"},
        {"location_id": "ram_channel_ptr_lo", "address": "0x0782", "address_space": "ram", "label": "channel_pointer_lo", "status": "verified", "meaning": "per-channel stream pointer low byte after init", "evidence": "init emulation"},
        {"location_id": "ram_channel_ptr_hi", "address": "0x0783", "address_space": "ram", "label": "channel_pointer_hi", "status": "verified", "meaning": "per-channel stream pointer high byte after init", "evidence": "init emulation"},
        {"location_id": "ram_duration_mode", "address": "0x07E0", "address_space": "ram", "label": "duration_mode_byte", "status": "verified", "meaning": "negative = inline durations, non-negative = persistent duration; written by commands 0x07 and 0x08", "evidence": "handler disassembly + parser behavior"},
        {"location_id": "ram_global_delay_active", "address": "0x059A", "address_space": "ram", "label": "global_delay_active", "status": "verified", "meaning": "active global frame delay countdown decremented each play call", "evidence": "play routine disassembly"},
        {"location_id": "ram_global_delay_reload", "address": "0x059B", "address_space": "ram", "label": "global_delay_reload", "status": "verified", "meaning": "global frame delay reload byte set by command 0x09 and copied into 0x059A when countdown expires", "evidence": "handler + play routine disassembly"},
        {"location_id": "ram_channel_reg0_shadow", "address": "0x07C0", "address_space": "ram", "label": "channel_reg0_shadow", "status": "verified", "meaning": "per-channel shadow for the APU control byte written to $4000/$4004/$4008/$400C; note playback copies it directly to hardware and commands 0x04/0x0A update it", "evidence": "handler disassembly + melodic note path"},
        {"location_id": "ram_channel_reg1_shadow", "address": "0x07C1", "address_space": "ram", "label": "channel_reg1_shadow", "status": "verified", "meaning": "per-channel shadow for $4001/$4005/$4009/$400D class byte; written by 0x04", "evidence": "handler disassembly"},
        {"location_id": "ram_channel_reg3_shadow", "address": "0x07C3", "address_space": "ram", "label": "channel_reg3_shadow", "status": "verified", "meaning": "per-channel shadow for high period / length byte; written by 0x04 and combined with note data at playback", "evidence": "handler + note decode disassembly"},
        {"location_id": "stream_sentinel_f1e0", "address": "0xF1E0", "address_space": "rom_cpu", "label": "common_inactive_noise_stream", "status": "partial", "meaning": "frequently silent/sentinel-like stream for noise/inactive channels", "evidence": "song survey + notes"},
    ]

    mysterious_locations = [
        {"mystery_id": "cmd_0A", "address": "0xEF54", "address_space": "rom_cpu", "label": "command_0x0A_handler", "status": "partial", "current_hypothesis": "single-byte write into the pulse control shadow $07C0,X; current evidence suggests it changes duty/constant-volume/volume nibble without touching sibling shadow bytes", "evidence": "handler disassembly + pulse-only occurrence pattern in songs 8, 13, and 15", "next_test": "decode argument families into specific duty and volume-bit changes, then compare with audible pulse timbre shifts", "priority": 8},
        {"mystery_id": "triangle_release", "address": "triangle_gate", "address_space": "virtual", "label": "triangle_release_mechanism", "status": "open", "current_hypothesis": "effective release/damping state still missing beyond attack truth", "evidence": "user-heard contradiction remains; current sideband fixes attack, not full damping", "next_test": "infer frame-level release classes from MP3 + write/trace evidence", "priority": 10},
        {"mystery_id": "pulse2_timbre_softening", "address": "pulse2_output_path", "address_space": "virtual", "label": "pulse2_end_softening_mechanism", "status": "partial", "current_hypothesis": "stepped volume softening is known; remaining softness may need output-stage or articulation details", "evidence": "trace shows real 13->9->6->3 volume drops", "next_test": "separate output filter effects from attack envelope effects", "priority": 6},
    ]

    title_articulation_frames = []
    for row in ir["frame_audible_state_ir"]["frames"]:
        title_articulation_frames.append(
            {
                "frame": row["frame"],
                "pulse1": {
                    "flags": {
                        "parser_boundary": row["channels"]["pulse1"]["parser_boundary"],
                        "hidden_retrigger": row["channels"]["pulse1"]["hidden_retrigger"],
                        "visible_period_attack": row["channels"]["pulse1"]["visible_period_attack"],
                        "sounding": row["channels"]["pulse1"]["sounding"],
                    },
                    "level": row["channels"]["pulse1"]["effective_level"],
                },
                "pulse2": {
                    "flags": {
                        "parser_boundary": row["channels"]["pulse2"]["parser_boundary"],
                        "hidden_retrigger": row["channels"]["pulse2"]["hidden_retrigger"],
                        "visible_period_attack": row["channels"]["pulse2"]["visible_period_attack"],
                        "sounding": row["channels"]["pulse2"]["sounding"],
                    },
                    "level": row["channels"]["pulse2"]["effective_level"],
                },
                "triangle": {
                    "flags": {
                        "parser_boundary": row["channels"]["triangle"]["parser_boundary"],
                        "hidden_retrigger": row["channels"]["triangle"]["hidden_retrigger"],
                        "visible_period_attack": row["channels"]["triangle"]["visible_period_attack"],
                        "sounding": row["channels"]["triangle"]["sounding"],
                    },
                    "level": row["channels"]["triangle"]["effective_level"],
                },
                "composite_attack": row["composite_attack"],
                "audio_high_z_phrase": row.get("audio_high_z_phrase"),
                "audio_low_z_phrase": row.get("audio_low_z_phrase"),
                "notes": {
                    "composite_attack_channels": row["composite_attack_channels"],
                    "parser_attack_channels": row["parser_attack_channels"],
                    "visible_period_attack_channels": row["visible_period_attack_channels"],
                },
            }
        )

    title_midi_notes = build_title_midi_notes()
    title_parser_events = build_title_parser_events()
    track_names = [line.strip() for line in M3U_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.startswith("#")]

    evidence_notes = [
        {
            "note_id": "n1",
            "category": "architecture",
            "title": "Plain MIDI is too lossy for title fidelity",
            "body": "The title phrase has same-pitch attacks that do not appear as new latched periods; note-only and latch-only exports both miss them.",
            "source_ref": str(IR_PATH),
        },
        {
            "note_id": "n2",
            "category": "title_phrase",
            "title": "Composite attack at frame 960/961",
            "body": "Pulse1 and triangle both carry hidden retrigger truth at the same phrase point, and the MP3 shows the strongest bright onset there.",
            "source_ref": str(ART_PATH),
        },
        {
            "note_id": "n3",
            "category": "open_problem",
            "title": "Triangle release/damping remains unresolved",
            "body": "Attack truth is now modeled better than before, but the user-heard bass over-ring implies the effective damping/release layer is still incomplete.",
            "source_ref": str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_title_playback_contract_update.md'),
        },
        {
            "note_id": "n4",
            "category": "handler_semantics",
            "title": "0x03 is a true one-byte skip and 0x09 writes the global delay reload",
            "body": "ROM disassembly shows 0x03 only performs INY then returns to stream dispatch, while 0x09 stores its byte to $059B and the play loop later copies $059B into $059A when the active global delay expires.",
            "source_ref": str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_handler_semantics_pass_1.md'),
        },
        {
            "note_id": "n5",
            "category": "handler_semantics",
            "title": "0x0A updates the pulse control byte shadow, not title triangle release",
            "body": "The handler writes only to $07C0,X, the melodic note path copies $07C0,X straight into $4000/$4004, and quick occurrence scans show 0x0A only on pulse channels in songs 8, 13, and 15, not in the title triangle path.",
            "source_ref": str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_control_byte_pass_1.md'),
        },
        {
            "note_id": "n6",
            "category": "audio_falsification",
            "title": "Title frame 960 behaves like attack-heavy damped bass, not full sustain",
            "body": "In the reference WAV, low-band energy has already decayed substantially before frame 960, while frame 960 shows a stronger high-band spike than low-band body; the next full bass-body resurgence does not happen until frame 976.",
            "source_ref": str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_title_triangle_release_pass_1.md'),
        },
        {
            "note_id": "n7",
            "category": "hidden_apu_state",
            "title": "Title pulse and triangle bytes were being flattened into the wrong live state",
            "body": "The title pulse control bytes 0x45 and 0x43 are hardware-envelope mode, not constant-volume loudness values, and the title triangle 0x81 byte carries linear reload/control semantics rather than a proven live current linear-counter value.",
            "source_ref": str(ROOT / 'extraction' / 'analysis' / 'reconciled' / 'wizards_and_warriors_hidden_apu_state_breakthrough.md'),
        },
    ]

    return {
        "metadata": {
            "game": "Wizards & Warriors",
            "db_type": "json_table_store",
            "db_version": 1,
            "purpose": "Query current certain knowledge and unresolved reverse-engineering targets",
            "primary_title_midi": str(MIDI_PATH),
            "track_names_from_m3u": track_names,
        },
        "sources": sources,
        "tracks": tracks,
        "command_handlers": command_handlers,
        "known_locations": known_locations,
        "mysterious_locations": mysterious_locations,
        "title_parser_events": title_parser_events,
        "title_midi_notes": title_midi_notes,
        "title_articulation_frames": title_articulation_frames,
        "evidence_notes": evidence_notes,
    }


def build_guide(db: dict) -> str:
    return "\n".join(
        [
            "# Wizards & Warriors Evidence DB Guide",
            "",
            f"Database file: `{OUT_PATH}`",
            "",
            "## What it contains",
            "",
            "- `sources`: canonical file inputs and artifact paths",
            "- `tracks`: song names and channel stream pointers",
            "- `command_handlers`: command opcodes, handler addresses, and current meaning status",
            "- `known_locations`: ROM/RAM locations with certain or partial meaning",
            "- `mysterious_locations`: unresolved handlers/locations with next-test suggestions",
            "- `title_parser_events`: title parser event stream with frame starts, periods, durations, MIDI notes",
            "- `title_midi_notes`: note spans from the current title MIDI artifact",
            "- `title_articulation_frames`: frame-level attack/retrigger evidence for the title phrase window",
            "- `evidence_notes`: high-level claims worth preserving",
            "",
            "## Suggested investigation loop",
            "",
            "1. Pick the highest-priority row in `mysterious_locations`.",
            "2. Find matching `command_handlers` or `known_locations` rows by address.",
            "3. Compare affected frames in `title_parser_events` and `title_articulation_frames`.",
            "4. Promote a mystery to `partial` or `verified` only when ROM/parser/write/trace evidence agree.",
            "",
            "## Immediate top mysteries",
            "",
        ]
        + [
            f"- `{row['mystery_id']}` at `{row['address']}`: {row['current_hypothesis']} "
            f"(next: {row['next_test']})"
            for row in sorted(db["mysterious_locations"], key=lambda row: -row["priority"])[:5]
        ]
    )


if __name__ == "__main__":
    db = build_database()
    OUT_PATH.write_text(json.dumps(db, indent=2), encoding="utf-8")
    GUIDE_PATH.write_text(build_guide(db), encoding="utf-8")
    print(OUT_PATH)
    print(GUIDE_PATH)
