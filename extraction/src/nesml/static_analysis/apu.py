"""NES APU register definitions and channel mappings.

The NES APU has five channels mapped to registers $4000-$4017.
This module provides constants and utilities for working with raw register data.
"""

# APU register address ranges per channel
PULSE1_REGS = range(0x4000, 0x4004)    # $4000-$4003
PULSE2_REGS = range(0x4004, 0x4008)    # $4004-$4007
TRIANGLE_REGS = range(0x4008, 0x400C)  # $4008-$400B
NOISE_REGS = range(0x400C, 0x4010)     # $400C-$400F
DPCM_REGS = range(0x4010, 0x4014)      # $4010-$4013
STATUS_REG = 0x4015                     # $4015 — channel enable/status
FRAME_COUNTER_REG = 0x4017             # $4017 — frame counter control

# Channel names (canonical)
CHANNEL_NAMES = ["pulse1", "pulse2", "triangle", "noise", "dpcm"]

# Register-to-channel mapping
ADDR_TO_CHANNEL = {}
for addr in PULSE1_REGS:
    ADDR_TO_CHANNEL[addr] = "pulse1"
for addr in PULSE2_REGS:
    ADDR_TO_CHANNEL[addr] = "pulse2"
for addr in TRIANGLE_REGS:
    ADDR_TO_CHANNEL[addr] = "triangle"
for addr in NOISE_REGS:
    ADDR_TO_CHANNEL[addr] = "noise"
for addr in DPCM_REGS:
    ADDR_TO_CHANNEL[addr] = "dpcm"
ADDR_TO_CHANNEL[STATUS_REG] = "status"
ADDR_TO_CHANNEL[FRAME_COUNTER_REG] = "frame_counter"

# NTSC and PAL frame rates
NTSC_FRAME_RATE = 60.0988
PAL_FRAME_RATE = 50.007

# NTSC period-to-frequency table for pulse/triangle channels
# frequency = CPU_CLOCK / (16 * (period + 1)) for pulse
# frequency = CPU_CLOCK / (32 * (period + 1)) for triangle
NTSC_CPU_CLOCK = 1789773  # Hz


def addr_to_hex(addr: int) -> str:
    """Format an integer address as '$XXXX'."""
    return f"${addr:04X}"


def parse_addr(addr_str: str) -> int:
    """Parse a '$XXXX' hex string to integer."""
    return int(addr_str.lstrip("$"), 16)


def channel_for_address(addr: int) -> str | None:
    """Return the canonical channel name for an APU register address."""
    return ADDR_TO_CHANNEL.get(addr)


def pulse_period_to_freq(period: int) -> float:
    """Convert a pulse channel timer period to frequency in Hz (NTSC)."""
    if period < 8:
        return 0.0  # periods below 8 are muted on real hardware
    return NTSC_CPU_CLOCK / (16 * (period + 1))


def triangle_period_to_freq(period: int) -> float:
    """Convert a triangle channel timer period to frequency in Hz (NTSC)."""
    if period < 2:
        return 0.0  # ultrasonic, effectively silent
    return NTSC_CPU_CLOCK / (32 * (period + 1))


def decode_pulse_reg0(value: int) -> dict:
    """Decode pulse channel register 0 ($4000/$4004).

    Bits: DDlc.vvvv
      DD   = duty cycle (0-3)
      l    = length counter halt / envelope loop
      c    = constant volume flag
      vvvv = volume/envelope period
    """
    return {
        "duty": (value >> 6) & 0x03,
        "length_halt": bool((value >> 5) & 0x01),
        "constant_volume": bool((value >> 4) & 0x01),
        "volume_envelope": value & 0x0F,
    }


def decode_pulse_reg1(value: int) -> dict:
    """Decode pulse channel register 1 ($4001/$4005) — sweep unit.

    Bits: Eppp.nsss
      E    = sweep enable
      ppp  = period
      n    = negate
      sss  = shift count
    """
    return {
        "sweep_enable": bool((value >> 7) & 0x01),
        "sweep_period": (value >> 4) & 0x07,
        "sweep_negate": bool((value >> 3) & 0x01),
        "sweep_shift": value & 0x07,
    }


def decode_pulse_period(reg2: int, reg3: int) -> int:
    """Extract 11-bit timer period from registers 2 and 3.

    reg2 = low 8 bits of period
    reg3 = llll.lHHH  (length counter load, high 3 bits of period)
    """
    return ((reg3 & 0x07) << 8) | reg2


def decode_noise_reg2(value: int) -> dict:
    """Decode noise channel register 2 ($400E).

    Bits: M---.pppp
      M    = mode flag (short/long)
      pppp = period index
    """
    return {
        "mode": (value >> 7) & 0x01,  # 0 = long, 1 = short
        "period_index": value & 0x0F,
    }
