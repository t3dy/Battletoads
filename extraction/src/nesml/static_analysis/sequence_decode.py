"""Sequence decoding helpers for driver-specific parsers.

This module provides base classes and utilities that driver-family parsers
use to decode command streams into symbolic events. Each driver family
implements its own subclass of SequenceDecoder.

The decoding process:
1. Start at a known byte offset (from pointer table)
2. Read command bytes
3. Dispatch to command handlers based on opcode
4. Emit symbolic events (NoteEvent, RestEvent, LoopPoint, etc.)
5. Track unknown opcodes as UnknownCommand
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from nesml.models.core import Confidence
from nesml.models.song import Pattern, Event
from nesml.models.events import NoteEvent, RestEvent, LoopPoint, JumpCall, UnknownCommand


@dataclass
class DecodeContext:
    """State tracked during sequence decoding."""
    prg_data: bytes
    offset: int                     # current read position in prg_data
    start_offset: int = 0           # where this decode run started
    current_frame: int = 0          # estimated frame counter
    channel: str = ""
    events: list[Event] = field(default_factory=list)
    unknowns: list[UnknownCommand] = field(default_factory=list)
    halted: bool = False            # True when decoder hits end/loop marker
    bytes_read: int = 0

    def read_byte(self) -> int:
        """Read one byte and advance the offset."""
        if self.offset >= len(self.prg_data):
            self.halted = True
            return 0
        val = self.prg_data[self.offset]
        self.offset += 1
        self.bytes_read += 1
        return val

    def read_le16(self) -> int:
        """Read a 16-bit little-endian value and advance."""
        lo = self.read_byte()
        hi = self.read_byte()
        return (hi << 8) | lo

    def peek_byte(self) -> int:
        """Peek at the next byte without advancing."""
        if self.offset >= len(self.prg_data):
            return 0
        return self.prg_data[self.offset]

    def emit(self, event: Event) -> None:
        """Add an event to the output list."""
        self.events.append(event)

    def emit_unknown(self, opcode: int, surrounding: int = 4) -> None:
        """Record an unknown opcode with context bytes."""
        start = max(0, self.offset - surrounding - 1)
        end = min(len(self.prg_data), self.offset + surrounding)
        self.unknowns.append(UnknownCommand(
            frame=self.current_frame,
            offset=self.offset - 1,
            opcode=opcode,
            surrounding_bytes=self.prg_data[start:end],
            confidence=Confidence.provisional("unrecognized opcode"),
        ))


class SequenceDecoder(ABC):
    """Abstract base for driver-family-specific sequence decoders.

    Subclasses implement decode_command() to handle one command byte at a time.
    The base class provides the decode loop and context management.
    """

    @abstractmethod
    def decode_command(self, ctx: DecodeContext, opcode: int) -> None:
        """Decode a single command byte and emit events.

        Must handle:
        - Note commands → emit NoteEvent
        - Rest/wait commands → emit RestEvent
        - Loop/jump commands → emit LoopPoint or JumpCall
        - Instrument/envelope commands → update state
        - End markers → set ctx.halted = True
        - Unknown opcodes → ctx.emit_unknown(opcode)
        """
        ...

    def decode_stream(
        self,
        prg_data: bytes,
        offset: int,
        channel: str = "",
        max_bytes: int = 4096,
    ) -> DecodeContext:
        """Decode a command stream starting at the given offset.

        Args:
            prg_data: PRG ROM data.
            offset: byte offset to start decoding.
            channel: channel name for context.
            max_bytes: safety limit on bytes to read.

        Returns:
            DecodeContext with accumulated events and unknowns.
        """
        ctx = DecodeContext(
            prg_data=prg_data,
            offset=offset,
            start_offset=offset,
            channel=channel,
        )

        while not ctx.halted and ctx.bytes_read < max_bytes:
            opcode = ctx.read_byte()
            if ctx.halted:
                break
            self.decode_command(ctx, opcode)

        return ctx

    def decode_to_pattern(
        self,
        prg_data: bytes,
        offset: int,
        pattern_id: str,
        channel: str = "",
        max_bytes: int = 4096,
    ) -> Pattern:
        """Decode a stream and wrap the result as a Pattern."""
        ctx = self.decode_stream(prg_data, offset, channel, max_bytes)

        return Pattern(
            id=pattern_id,
            events=ctx.events,
            rom_offset=offset,
            rom_length=ctx.bytes_read,
            confidence=Confidence.static_parse(
                0.6 if not ctx.unknowns else 0.4,
                f"decoded {ctx.bytes_read} bytes, {len(ctx.unknowns)} unknowns",
            ),
        )


class NullDecoder(SequenceDecoder):
    """Placeholder decoder that treats every byte as unknown.

    Useful for initial investigation of unidentified drivers.
    """
    def decode_command(self, ctx: DecodeContext, opcode: int) -> None:
        ctx.emit_unknown(opcode)
        # Stop after first unknown to avoid flooding
        if len(ctx.unknowns) > 100:
            ctx.halted = True
