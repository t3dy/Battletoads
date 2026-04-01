"""Channel state tracking across frames.

Maintains the full APU state for each channel as register writes arrive,
enabling detection of state changes (period changes, volume changes,
duty changes, etc.) with precise frame timing.

This is richer than the flat event_stream module — it tracks accumulated
state and can detect more nuanced behaviors like volume envelope patterns,
duty cycling, and sweep unit activity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nesml.static_analysis.apu import (
    decode_pulse_reg0,
    decode_pulse_reg1,
    decode_pulse_period,
    decode_noise_reg2,
    parse_addr,
)


@dataclass
class PulseState:
    """Accumulated state for a pulse channel (pulse1 or pulse2)."""
    duty: int = 0
    volume: int = 0
    constant_volume: bool = False
    length_halt: bool = False
    envelope_period: int = 0
    sweep_enable: bool = False
    sweep_period: int = 0
    sweep_negate: bool = False
    sweep_shift: int = 0
    period: int = 0
    length_load: int = 0
    enabled: bool = False
    last_write_frame: int = -1

    def apply_write(self, reg_index: int, value: int, frame: int) -> list[str]:
        """Apply a register write and return list of changed field names."""
        changes = []
        self.last_write_frame = frame

        if reg_index == 0:
            decoded = decode_pulse_reg0(value)
            if decoded["duty"] != self.duty:
                changes.append("duty")
                self.duty = decoded["duty"]
            if decoded["volume_envelope"] != self.volume or \
               decoded["constant_volume"] != self.constant_volume:
                changes.append("volume")
                self.volume = decoded["volume_envelope"]
                self.constant_volume = decoded["constant_volume"]
            self.length_halt = decoded["length_halt"]
            self.envelope_period = decoded["volume_envelope"]

        elif reg_index == 1:
            decoded = decode_pulse_reg1(value)
            if decoded["sweep_enable"] != self.sweep_enable:
                changes.append("sweep")
            self.sweep_enable = decoded["sweep_enable"]
            self.sweep_period = decoded["sweep_period"]
            self.sweep_negate = decoded["sweep_negate"]
            self.sweep_shift = decoded["sweep_shift"]

        elif reg_index == 2:
            new_period = (self.period & 0x700) | value
            if new_period != self.period:
                changes.append("period_lo")
                self.period = new_period

        elif reg_index == 3:
            new_period = ((value & 0x07) << 8) | (self.period & 0xFF)
            if new_period != self.period:
                changes.append("period")
            self.period = new_period
            self.length_load = (value >> 3) & 0x1F
            changes.append("length_load")  # always triggers re-start

        return changes

    def to_dict(self) -> dict:
        return {
            "duty": self.duty,
            "volume": self.volume,
            "constant_volume": self.constant_volume,
            "period": self.period,
            "sweep_enable": self.sweep_enable,
            "enabled": self.enabled,
        }


@dataclass
class TriangleState:
    """Accumulated state for the triangle channel."""
    linear_counter: int = 0
    control_flag: bool = False
    period: int = 0
    length_load: int = 0
    enabled: bool = False
    last_write_frame: int = -1

    def apply_write(self, reg_index: int, value: int, frame: int) -> list[str]:
        changes = []
        self.last_write_frame = frame

        if reg_index == 0:
            self.control_flag = bool(value & 0x80)
            new_lc = value & 0x7F
            if new_lc != self.linear_counter:
                changes.append("linear_counter")
                self.linear_counter = new_lc

        elif reg_index == 2:
            new_period = (self.period & 0x700) | value
            if new_period != self.period:
                changes.append("period_lo")
                self.period = new_period

        elif reg_index == 3:
            new_period = ((value & 0x07) << 8) | (self.period & 0xFF)
            if new_period != self.period:
                changes.append("period")
            self.period = new_period
            self.length_load = (value >> 3) & 0x1F
            changes.append("length_load")

        return changes

    def to_dict(self) -> dict:
        return {
            "linear_counter": self.linear_counter,
            "period": self.period,
            "enabled": self.enabled,
        }


@dataclass
class NoiseState:
    """Accumulated state for the noise channel."""
    volume: int = 0
    constant_volume: bool = False
    length_halt: bool = False
    mode: int = 0           # 0 = long, 1 = short
    period_index: int = 0
    enabled: bool = False
    last_write_frame: int = -1

    def apply_write(self, reg_index: int, value: int, frame: int) -> list[str]:
        changes = []
        self.last_write_frame = frame

        if reg_index == 0:
            decoded = decode_pulse_reg0(value)  # same bit layout
            if decoded["volume_envelope"] != self.volume or \
               decoded["constant_volume"] != self.constant_volume:
                changes.append("volume")
                self.volume = decoded["volume_envelope"]
                self.constant_volume = decoded["constant_volume"]
            self.length_halt = decoded["length_halt"]

        elif reg_index == 2:
            decoded = decode_noise_reg2(value)
            if decoded["mode"] != self.mode:
                changes.append("noise_mode")
                self.mode = decoded["mode"]
            if decoded["period_index"] != self.period_index:
                changes.append("period")
                self.period_index = decoded["period_index"]

        elif reg_index == 3:
            self.last_write_frame = frame
            changes.append("length_load")

        return changes

    def to_dict(self) -> dict:
        return {
            "volume": self.volume,
            "mode": self.mode,
            "period_index": self.period_index,
            "enabled": self.enabled,
        }


@dataclass
class DPCMState:
    """Accumulated state for the DPCM channel."""
    rate_index: int = 0
    loop: bool = False
    sample_address: int = 0
    sample_length: int = 0
    enabled: bool = False
    last_write_frame: int = -1

    def apply_write(self, reg_index: int, value: int, frame: int) -> list[str]:
        changes = []
        self.last_write_frame = frame

        if reg_index == 0:
            new_rate = value & 0x0F
            new_loop = bool(value & 0x40)
            if new_rate != self.rate_index:
                changes.append("rate")
                self.rate_index = new_rate
            if new_loop != self.loop:
                changes.append("loop")
                self.loop = new_loop

        elif reg_index == 1:
            # Direct load (DAC)
            changes.append("dac_load")

        elif reg_index == 2:
            addr = 0xC000 + (value * 64)
            if addr != self.sample_address:
                changes.append("sample_address")
                self.sample_address = addr

        elif reg_index == 3:
            length = (value * 16) + 1
            if length != self.sample_length:
                changes.append("sample_length")
                self.sample_length = length

        return changes

    def to_dict(self) -> dict:
        return {
            "rate_index": self.rate_index,
            "loop": self.loop,
            "sample_address": f"0x{self.sample_address:04X}",
            "sample_length": self.sample_length,
            "enabled": self.enabled,
        }


@dataclass
class APUState:
    """Full APU state across all channels."""
    pulse1: PulseState = field(default_factory=PulseState)
    pulse2: PulseState = field(default_factory=PulseState)
    triangle: TriangleState = field(default_factory=TriangleState)
    noise: NoiseState = field(default_factory=NoiseState)
    dpcm: DPCMState = field(default_factory=DPCMState)

    _BASE_ADDRS = {
        "pulse1": 0x4000, "pulse2": 0x4004,
        "triangle": 0x4008, "noise": 0x400C, "dpcm": 0x4010,
    }
    _CHANNELS = {}  # populated in __post_init__

    def __post_init__(self):
        self._CHANNELS = {
            "pulse1": self.pulse1, "pulse2": self.pulse2,
            "triangle": self.triangle, "noise": self.noise,
            "dpcm": self.dpcm,
        }

    def apply_write(self, address: int | str, value: int, frame: int) -> dict[str, list[str]]:
        """Apply a register write and return changes by channel.

        Returns dict mapping channel name to list of changed field names.
        """
        if isinstance(address, str):
            address = parse_addr(address)

        # Handle status register
        if address == 0x4015:
            self.pulse1.enabled = bool(value & 0x01)
            self.pulse2.enabled = bool(value & 0x02)
            self.triangle.enabled = bool(value & 0x04)
            self.noise.enabled = bool(value & 0x08)
            self.dpcm.enabled = bool(value & 0x10)
            return {"status": ["channel_enable"]}

        for ch_name, base in self._BASE_ADDRS.items():
            if base <= address < base + 4:
                reg_index = address - base
                channel = self._CHANNELS[ch_name]
                changes = channel.apply_write(reg_index, value, frame)
                if changes:
                    return {ch_name: changes}
                return {}

        return {}

    def snapshot(self) -> dict:
        """Return a snapshot of all channel states."""
        return {
            "pulse1": self.pulse1.to_dict(),
            "pulse2": self.pulse2.to_dict(),
            "triangle": self.triangle.to_dict(),
            "noise": self.noise.to_dict(),
            "dpcm": self.dpcm.to_dict(),
        }
