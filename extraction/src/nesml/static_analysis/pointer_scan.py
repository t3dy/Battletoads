"""Pointer table discovery and analysis.

NES sound drivers typically use pointer tables to index songs, channels,
and patterns. This module provides tools for finding and interpreting
these structures in PRG ROM data.

Common NES pointer formats:
- 16-bit little-endian absolute addresses
- 16-bit addresses relative to a bank base
- Song headers that contain per-channel pointers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nesml.models.core import Confidence


@dataclass
class PointerEntry:
    """A single pointer found in ROM data."""
    rom_offset: int         # byte offset in PRG ROM where pointer lives
    target_address: int     # the resolved CPU address the pointer points to
    target_rom_offset: int | None = None  # resolved offset in PRG ROM (if known)
    bank: int | None = None               # ROM bank containing the target
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "rom_offset": f"0x{self.rom_offset:X}",
            "target_address": f"0x{self.target_address:04X}",
            "confidence": self.confidence.to_dict(),
        }
        if self.target_rom_offset is not None:
            d["target_rom_offset"] = f"0x{self.target_rom_offset:X}"
        if self.bank is not None:
            d["bank"] = self.bank
        return d


@dataclass
class PointerTable:
    """A table of pointers — typically a song table or channel pointer list."""
    rom_offset: int             # start of the table in PRG ROM
    entries: list[PointerEntry] = field(default_factory=list)
    label: str = ""
    purpose: str = ""           # "song_table", "channel_pointers", "pattern_table", etc.
    confidence: Confidence = field(default_factory=Confidence.provisional)

    def to_dict(self) -> dict:
        return {
            "rom_offset": f"0x{self.rom_offset:X}",
            "entries": [e.to_dict() for e in self.entries],
            "label": self.label,
            "purpose": self.purpose,
            "entry_count": len(self.entries),
            "confidence": self.confidence.to_dict(),
        }


def read_le16(data: bytes, offset: int) -> int:
    """Read a 16-bit little-endian value from ROM data."""
    return data[offset] | (data[offset + 1] << 8)


def scan_pointer_table(
    prg_data: bytes,
    offset: int,
    count: int,
    *,
    bank_base: int = 0x8000,
    prg_bank_offset: int = 0,
) -> PointerTable:
    """Read a table of 16-bit LE pointers from PRG data.

    Args:
        prg_data: PRG ROM bytes.
        offset: byte offset of the first pointer in prg_data.
        count: number of pointers to read.
        bank_base: CPU address base for the bank (default $8000).
        prg_bank_offset: byte offset in PRG ROM corresponding to bank_base.

    Returns:
        PointerTable with resolved entries.
    """
    entries = []
    for i in range(count):
        ptr_offset = offset + (i * 2)
        if ptr_offset + 2 > len(prg_data):
            break

        addr = read_le16(prg_data, ptr_offset)

        # Resolve to PRG ROM offset
        target_rom = None
        if bank_base <= addr < bank_base + 0x4000:
            target_rom = prg_bank_offset + (addr - bank_base)

        entries.append(PointerEntry(
            rom_offset=ptr_offset,
            target_address=addr,
            target_rom_offset=target_rom,
            confidence=Confidence.static_parse(
                0.6, f"pointer read at 0x{ptr_offset:X} -> ${addr:04X}"
            ),
        ))

    return PointerTable(
        rom_offset=offset,
        entries=entries,
        confidence=Confidence.static_parse(
            0.5, f"table of {count} pointers at 0x{offset:X}"
        ),
    )


def find_pointer_candidates(
    prg_data: bytes,
    target_range: tuple[int, int] = (0x8000, 0xFFFF),
    min_consecutive: int = 4,
) -> list[int]:
    """Scan PRG data for regions that look like pointer tables.

    A "pointer table candidate" is a sequence of consecutive 16-bit LE values
    that all fall within the target address range.

    Args:
        prg_data: PRG ROM bytes.
        target_range: (min_addr, max_addr) for valid pointer targets.
        min_consecutive: minimum consecutive valid pointers to report a candidate.

    Returns:
        List of PRG offsets where candidate pointer tables begin.
    """
    candidates = []
    run_start = None
    run_count = 0

    for i in range(0, len(prg_data) - 1, 2):
        addr = read_le16(prg_data, i)
        if target_range[0] <= addr <= target_range[1]:
            if run_start is None:
                run_start = i
                run_count = 1
            else:
                run_count += 1
        else:
            if run_count >= min_consecutive and run_start is not None:
                candidates.append(run_start)
            run_start = None
            run_count = 0

    if run_count >= min_consecutive and run_start is not None:
        candidates.append(run_start)

    return candidates
