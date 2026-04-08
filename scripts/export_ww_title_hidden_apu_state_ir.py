#!/usr/bin/env python3
"""Export hidden APU state IR for the Wizards & Warriors title phrase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Dev\NSFRIPPER")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.nsf_to_reaper import NsfEmulator, frames_to_channel_data, load_wizards_and_warriors_note_boundaries  # noqa: E402


NSF_PATH = ROOT / "state" / "ww_ref" / "Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).nsf"
OUT_JSON = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_hidden_apu_state_ir.json"
OUT_MD = ROOT / "extraction" / "analysis" / "reconciled" / "wizards_and_warriors_title_hidden_apu_state_ir_report.md"
WINDOW_START = 920
WINDOW_END = 980


def pulse_effective_mode(note: dict) -> str:
    return "constant_volume" if note["const_vol"] else "hardware_envelope"


def simulate_hidden_apu(frames: list[dict]) -> dict:
    pulse = {
        "pulse1": {"r0": 0, "env_start": False, "divider": 0, "decay": 0},
        "pulse2": {"r0": 0, "env_start": False, "divider": 0, "decay": 0},
    }
    tri = {"reload": 0, "control": 0, "counter": 0, "reload_flag": False}
    out = {"pulse1": [], "pulse2": [], "triangle": []}

    for frame_packet in frames:
        writes = frame_packet["writes"]
        for reg, value in writes:
            if reg == 0x4000:
                pulse["pulse1"]["r0"] = value
            elif reg == 0x4003:
                pulse["pulse1"]["env_start"] = True
            elif reg == 0x4004:
                pulse["pulse2"]["r0"] = value
            elif reg == 0x4007:
                pulse["pulse2"]["env_start"] = True
            elif reg == 0x4008:
                tri["control"] = (value >> 7) & 1
                tri["reload"] = value & 0x7F
            elif reg == 0x400B:
                tri["reload_flag"] = True

        for _ in range(4):
            for key in ("pulse1", "pulse2"):
                st = pulse[key]
                r0 = st["r0"]
                env_period = r0 & 0x0F
                env_loop = (r0 >> 5) & 1
                const_vol = (r0 >> 4) & 1
                if st["env_start"]:
                    st["env_start"] = False
                    st["decay"] = 15
                    st["divider"] = env_period
                else:
                    if st["divider"] == 0:
                        st["divider"] = env_period
                        if st["decay"] > 0:
                            st["decay"] -= 1
                        elif env_loop:
                            st["decay"] = 15
                    else:
                        st["divider"] -= 1

            if tri["reload_flag"]:
                tri["counter"] = tri["reload"]
            elif tri["counter"] > 0:
                tri["counter"] -= 1
            if tri["control"] == 0:
                tri["reload_flag"] = False

        for key in ("pulse1", "pulse2"):
            st = pulse[key]
            r0 = st["r0"]
            out[key].append(
                {
                    "const_vol": (r0 >> 4) & 1,
                    "env_loop": (r0 >> 5) & 1,
                    "env_period": r0 & 0x0F,
                    "effective_volume": (r0 & 0x0F) if ((r0 >> 4) & 1) else st["decay"],
                    "decay_level": st["decay"],
                    "divider": st["divider"],
                }
            )
        out["triangle"].append(
            {
                "linear_reload": tri["reload"],
                "linear_control": tri["control"],
                "linear_counter_model": tri["counter"],
                "reload_flag": tri["reload_flag"],
            }
        )
    return out


def build_ir() -> dict:
    emu = NsfEmulator(NSF_PATH)
    frames = emu.play_song(1, WINDOW_END + 8)
    channels = frames_to_channel_data(frames)
    boundaries = load_wizards_and_warriors_note_boundaries(NSF_PATH, 1)
    hidden = simulate_hidden_apu(frames)

    rows = []
    for frame in range(WINDOW_START, WINDOW_END + 1):
        p1 = channels["pulse1"]["notes"][frame]
        p2 = channels["pulse2"]["notes"][frame]
        tri = channels["triangle"]["notes"][frame]
        rows.append(
            {
                "frame": frame,
                "pulse1": {
                    "period": p1["period"],
                    "duty": p1["duty"],
                    "raw_low_nibble": p1["vol"],
                    "const_vol": p1["const_vol"],
                    "env_loop": p1["env_loop"],
                    "env_period": p1["env_period"],
                    "mode": pulse_effective_mode(p1),
                    "modeled_effective_volume": hidden["pulse1"][frame]["effective_volume"],
                    "modeled_decay_level": hidden["pulse1"][frame]["decay_level"],
                    "parser_boundary": frame in boundaries["pulse1"],
                },
                "pulse2": {
                    "period": p2["period"],
                    "duty": p2["duty"],
                    "raw_low_nibble": p2["vol"],
                    "const_vol": p2["const_vol"],
                    "env_loop": p2["env_loop"],
                    "env_period": p2["env_period"],
                    "mode": pulse_effective_mode(p2),
                    "modeled_effective_volume": hidden["pulse2"][frame]["effective_volume"],
                    "modeled_decay_level": hidden["pulse2"][frame]["decay_level"],
                    "parser_boundary": frame in boundaries["pulse2"],
                },
                "triangle": {
                    "period": tri["period"],
                    "linear_reload": tri["linear_reload"],
                    "linear_control": tri["linear_control"],
                    "current_export_linear": tri["linear"],
                    "modeled_linear_counter": hidden["triangle"][frame]["linear_counter_model"],
                    "modeled_reload_flag": hidden["triangle"][frame]["reload_flag"],
                    "parser_boundary": frame in boundaries["triangle"],
                    "warning": "current_export_linear is the reload register value, not proven live internal counter state",
                },
            }
        )

    return {
        "meta": {
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "source_nsf": str(NSF_PATH),
            "claim": "Pulse low nibble is often envelope period, not steady volume; triangle $4008 low bits are reload, not proven live counter state.",
        },
        "frames": rows,
    }


def build_report(ir: dict) -> str:
    key_frames = [row for row in ir["frames"] if row["frame"] in (928, 960, 976)]
    lines = [
        "# Wizards & Warriors Title Hidden APU State IR Report",
        "",
        "## Summary",
        "",
        "- This artifact preserves hidden-state interpretations that the current export path flattens.",
        "- Pulse channels retain constant-volume-vs-envelope mode separately from the low nibble.",
        "- Triangle retains linear reload and control bit separately from any claimed live gate/counter state.",
        "",
        "## Key Frames",
        "",
    ]
    for row in key_frames:
        lines.append(
            f"- Frame `{row['frame']}`: "
            f"pulse1=`{row['pulse1']['mode']}` nibble `{row['pulse1']['raw_low_nibble']}` effvol `{row['pulse1']['modeled_effective_volume']}` duty `{row['pulse1']['duty']}`, "
            f"pulse2=`{row['pulse2']['mode']}` nibble `{row['pulse2']['raw_low_nibble']}` effvol `{row['pulse2']['modeled_effective_volume']}` duty `{row['pulse2']['duty']}`, "
            f"triangle reload=`{row['triangle']['linear_reload']}` control=`{row['triangle']['linear_control']}` modeled_counter=`{row['triangle']['modeled_linear_counter']}`."
        )
    lines.extend(
        [
            "",
            "## Consequence",
            "",
            "- A pulse byte like `0x45` should not be read as steady volume `5` when `const_vol=0`.",
            "- Under a standard APU envelope model, the pulse effective volume falls over time after each timer-high retrigger.",
            "- A triangle byte like `0x81` should not be read as live linear counter `1`; it is only the reload/control register.",
            "- Under a standard linear-counter model with control bit `1`, the triangle counter remains armed, so pulse envelope behavior may be the stronger immediate missing hardware layer.",
            "",
            "These hidden-state fields need to exist before we can model true harpsichord-like pulse decay or muted plucked-bass triangle behavior.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ir = build_ir()
    OUT_JSON.write_text(json.dumps(ir, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_report(ir), encoding="utf-8")
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()
