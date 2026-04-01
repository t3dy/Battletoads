"""NES APU register bitmask definitions.

Adapted from nesmdb (Chris Donahue, ISMIR 2018) with additions for
our extraction pipeline. These define the exact bit fields for all
APU registers, enabling decomposition of raw register writes into
individual parameter changes.

Reference: https://github.com/chrisdonahue/nesmdb
"""

# ---------------------------------------------------------------------------
# Pulse 1 ($4000-$4003)
# ---------------------------------------------------------------------------
P1_R0 = 0x4000  # DDLC VVVV
P1_DU = 0b11000000  # duty cycle (2 bits): 0=12.5%, 1=25%, 2=50%, 3=75%
P1_LH = 0b00100000  # length counter halt / envelope loop
P1_CV = 0b00010000  # constant volume (1) / use envelope (0)
P1_VO = 0b00001111  # volume / envelope divider period

P1_R1 = 0x4001  # EPPP NSSS
P1_SE = 0b10000000  # sweep enable
P1_SP = 0b01110000  # sweep period
P1_SN = 0b00001000  # sweep negate
P1_SS = 0b00000111  # sweep shift count

P1_R2 = 0x4002  # TTTT TTTT
P1_TL = 0b11111111  # timer low (8 bits)

P1_R3 = 0x4003  # LLLL LTTT
P1_LL = 0b11111000  # length counter load (5 bits)
P1_TH = 0b00000111  # timer high (3 bits)

# ---------------------------------------------------------------------------
# Pulse 2 ($4004-$4007) — identical layout to Pulse 1
# ---------------------------------------------------------------------------
P2_R0 = 0x4004
P2_DU = 0b11000000
P2_LH = 0b00100000
P2_CV = 0b00010000
P2_VO = 0b00001111

P2_R1 = 0x4005
P2_SE = 0b10000000
P2_SP = 0b01110000
P2_SN = 0b00001000
P2_SS = 0b00000111

P2_R2 = 0x4006
P2_TL = 0b11111111

P2_R3 = 0x4007
P2_LL = 0b11111000
P2_TH = 0b00000111

# ---------------------------------------------------------------------------
# Triangle ($4008-$400B)
# ---------------------------------------------------------------------------
TR_R0 = 0x4008  # CRRR RRRR
TR_CR = 0b10000000  # length counter halt / linear counter control
TR_LN = 0b01111111  # linear counter reload value

TR_R2 = 0x400A  # TTTT TTTT
TR_TL = 0b11111111  # timer low

TR_R3 = 0x400B  # LLLL LTTT
TR_LL = 0b11111000  # length counter load
TR_TH = 0b00000111  # timer high

# ---------------------------------------------------------------------------
# Noise ($400C-$400F)
# ---------------------------------------------------------------------------
NO_R0 = 0x400C  # --LC VVVV
NO_LH = 0b00100000  # length counter halt / envelope loop
NO_CV = 0b00010000  # constant volume
NO_VO = 0b00001111  # volume / envelope divider

NO_R2 = 0x400E  # L--- PPPP
NO_NL = 0b10000000  # noise loop (short mode)
NO_NP = 0b00001111  # noise period index (0-15)

NO_R3 = 0x400F  # LLLL L---
NO_LL = 0b11111000  # length counter load

# ---------------------------------------------------------------------------
# DMC ($4010-$4013)
# ---------------------------------------------------------------------------
DM_R0 = 0x4010  # IL-- RRRR
DM_IL = 0b10000000  # IRQ enable
DM_LP = 0b01000000  # loop
DM_RT = 0b00001111  # rate index

DM_R1 = 0x4011  # -DDD DDDD
DM_DL = 0b01111111  # direct load (7-bit DAC value)

DM_R2 = 0x4012  # AAAA AAAA
DM_SA = 0b11111111  # sample address (addr = $C000 + A * 64)

DM_R3 = 0x4013  # LLLL LLLL
DM_SL = 0b11111111  # sample length (len = L * 16 + 1)

# ---------------------------------------------------------------------------
# Status ($4015) and Frame Counter ($4017)
# ---------------------------------------------------------------------------
ST_R0 = 0x4015  # ---D NT21
ST_DN = 0b00010000  # DMC enable
ST_NO = 0b00001000  # noise enable
ST_TR = 0b00000100  # triangle enable
ST_P2 = 0b00000010  # pulse 2 enable
ST_P1 = 0b00000001  # pulse 1 enable

FC_R0 = 0x4017  # MI-- ----
FC_MD = 0b10000000  # frame counter mode (0=4-step, 1=5-step)
FC_IR = 0b01000000  # IRQ inhibit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CPU_CLK_NTSC = 1789773  # Hz
CPU_CLK_PAL = 1662607   # Hz

# Noise period lookup table (CPU cycles per LFSR clock)
NOISE_PERIOD_TABLE = [
    4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068
]

# Length counter lookup table
LENGTH_COUNTER_TABLE = [
    10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14,
    12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30
]

# MIDI CC assignments (nesmdb standard)
CC_VELOCITY = 11   # Expression — mid-note volume changes (0-15)
CC_TIMBRE = 12     # Duty cycle / noise loop (0-3 for pulse, 0-1 for noise)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pulse_freq(timer: int, cpu_clk: int = CPU_CLK_NTSC) -> float:
    """Convert 11-bit pulse timer value to frequency in Hz."""
    if timer < 8:
        return 0.0  # too high, muted by hardware
    return cpu_clk / (16 * (timer + 1))


def triangle_freq(timer: int, cpu_clk: int = CPU_CLK_NTSC) -> float:
    """Convert 11-bit triangle timer value to frequency in Hz."""
    if timer < 2:
        return 0.0  # ultrasonic, effectively muted
    return cpu_clk / (32 * (timer + 1))


def freq_to_midi(freq: float) -> int:
    """Convert frequency to nearest MIDI note number."""
    import math
    if freq <= 0:
        return 0
    midi = round(69 + 12 * math.log2(freq / 440))
    if midi < 21 or midi > 108:
        return 0
    return midi


def timer_to_midi_pulse(timer: int, cpu_clk: int = CPU_CLK_NTSC) -> int:
    """Convert pulse timer directly to MIDI note."""
    return freq_to_midi(pulse_freq(timer, cpu_clk))


def timer_to_midi_triangle(timer: int, cpu_clk: int = CPU_CLK_NTSC) -> int:
    """Convert triangle timer directly to MIDI note."""
    return freq_to_midi(triangle_freq(timer, cpu_clk))


def decompose_register(address: int, value: int) -> dict:
    """Decompose a raw APU register write into named fields.

    Returns a dict mapping field names to their values.
    """
    fields = {}
    reg = address & 0x1F  # strip high bits

    if reg == 0x00:  # P1 R0
        fields["du"] = (value & P1_DU) >> 6
        fields["lh"] = (value & P1_LH) >> 5
        fields["cv"] = (value & P1_CV) >> 4
        fields["vo"] = value & P1_VO
    elif reg == 0x01:  # P1 R1
        fields["se"] = (value & P1_SE) >> 7
        fields["sp"] = (value & P1_SP) >> 4
        fields["sn"] = (value & P1_SN) >> 3
        fields["ss"] = value & P1_SS
    elif reg == 0x02:  # P1 R2
        fields["tl"] = value & P1_TL
    elif reg == 0x03:  # P1 R3
        fields["ll"] = (value & P1_LL) >> 3
        fields["th"] = value & P1_TH
    elif reg == 0x04:  # P2 R0
        fields["du"] = (value & P2_DU) >> 6
        fields["lh"] = (value & P2_LH) >> 5
        fields["cv"] = (value & P2_CV) >> 4
        fields["vo"] = value & P2_VO
    elif reg == 0x05:  # P2 R1
        fields["se"] = (value & P2_SE) >> 7
        fields["sp"] = (value & P2_SP) >> 4
        fields["sn"] = (value & P2_SN) >> 3
        fields["ss"] = value & P2_SS
    elif reg == 0x06:  # P2 R2
        fields["tl"] = value & P2_TL
    elif reg == 0x07:  # P2 R3
        fields["ll"] = (value & P2_LL) >> 3
        fields["th"] = value & P2_TH
    elif reg == 0x08:  # TR R0
        fields["cr"] = (value & TR_CR) >> 7
        fields["ln"] = value & TR_LN
    elif reg == 0x0A:  # TR R2
        fields["tl"] = value & TR_TL
    elif reg == 0x0B:  # TR R3
        fields["ll"] = (value & TR_LL) >> 3
        fields["th"] = value & TR_TH
    elif reg == 0x0C:  # NO R0
        fields["lh"] = (value & NO_LH) >> 5
        fields["cv"] = (value & NO_CV) >> 4
        fields["vo"] = value & NO_VO
    elif reg == 0x0E:  # NO R2
        fields["nl"] = (value & NO_NL) >> 7
        fields["np"] = value & NO_NP
    elif reg == 0x0F:  # NO R3
        fields["ll"] = (value & NO_LL) >> 3
    elif reg == 0x15:  # Status
        fields["dn"] = (value & ST_DN) >> 4
        fields["no"] = (value & ST_NO) >> 3
        fields["tr"] = (value & ST_TR) >> 2
        fields["p2"] = (value & ST_P2) >> 1
        fields["p1"] = value & ST_P1

    return fields
