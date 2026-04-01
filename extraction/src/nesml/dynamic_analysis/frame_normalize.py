"""Frame normalization — group raw APU register writes by frame and channel.

Takes a trace (list of writes with frame numbers) and produces a frame-indexed
structure where each frame contains the register writes that occurred during it,
organized by channel.

This is the bridge between raw trace data and higher-level event reconstruction.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from nesml.static_analysis.apu import ADDR_TO_CHANNEL, parse_addr, CHANNEL_NAMES


class FrameNormalizeError(Exception):
    """Raised when frame normalization encounters invalid data."""


def normalize_by_frame(trace: dict) -> list[dict]:
    """Group trace writes by frame, with per-channel bucketing.

    Args:
        trace: A trace dict with a 'writes' list (as from trace_ingest.load_trace).

    Returns:
        A list of frame dicts, indexed by frame number. Each frame dict has:
          - frame: int
          - channels: dict mapping channel name to list of writes
          - write_count: int (total writes this frame)

    Frames with no writes are omitted from the output.
    """
    writes = trace.get("writes", [])
    if not writes:
        return []

    # Group writes by frame
    frames: dict[int, list[dict]] = defaultdict(list)
    for w in writes:
        frame_num = w["frame"]
        frames[frame_num].append(w)

    # Build normalized output
    result = []
    for frame_num in sorted(frames.keys()):
        frame_writes = frames[frame_num]
        channels: dict[str, list[dict]] = defaultdict(list)

        for w in frame_writes:
            addr = _resolve_address(w["address"])
            channel = ADDR_TO_CHANNEL.get(addr)
            if channel is None:
                # Not an APU register we track — skip silently
                continue
            channels[channel].append({
                "address": w["address"],
                "value": w["value"],
                "cycle": w.get("cycle"),
            })

        result.append({
            "frame": frame_num,
            "channels": dict(channels),
            "write_count": sum(len(v) for v in channels.values()),
        })

    return result


def frame_range(frames: list[dict]) -> tuple[int, int] | None:
    """Return (first_frame, last_frame) from normalized frame list, or None if empty."""
    if not frames:
        return None
    return frames[0]["frame"], frames[-1]["frame"]


def channel_activity_summary(frames: list[dict]) -> dict[str, int]:
    """Count how many frames each channel has at least one write in.

    Returns a dict mapping channel name to frame count.
    """
    counts: dict[str, int] = defaultdict(int)
    for f in frames:
        for ch in f["channels"]:
            if ch in CHANNEL_NAMES:
                counts[ch] += 1
    return dict(counts)


def extract_channel_writes(frames: list[dict], channel: str) -> list[dict]:
    """Extract all writes for a specific channel across all frames.

    Returns a list of dicts with 'frame', 'address', 'value', 'cycle'.
    """
    result = []
    for f in frames:
        for w in f["channels"].get(channel, []):
            result.append({
                "frame": f["frame"],
                "address": w["address"],
                "value": w["value"],
                "cycle": w.get("cycle"),
            })
    return result


def _resolve_address(addr: Any) -> int:
    """Convert address to integer, accepting both int and '$XXXX' string."""
    if isinstance(addr, int):
        return addr
    if isinstance(addr, str):
        return parse_addr(addr)
    raise FrameNormalizeError(f"Invalid address type: {type(addr)}")
