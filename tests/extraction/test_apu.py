"""Tests for APU register decoding and utility functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.apu import (
    addr_to_hex,
    parse_addr,
    channel_for_address,
    decode_pulse_reg0,
    decode_pulse_reg1,
    decode_pulse_period,
    decode_noise_reg2,
    pulse_period_to_freq,
    triangle_period_to_freq,
)


def test_addr_to_hex():
    assert addr_to_hex(0x4000) == "$4000"
    assert addr_to_hex(0x4015) == "$4015"


def test_parse_addr():
    assert parse_addr("$4000") == 0x4000
    assert parse_addr("$400F") == 0x400F


def test_channel_for_address():
    assert channel_for_address(0x4000) == "pulse1"
    assert channel_for_address(0x4003) == "pulse1"
    assert channel_for_address(0x4004) == "pulse2"
    assert channel_for_address(0x4008) == "triangle"
    assert channel_for_address(0x400C) == "noise"
    assert channel_for_address(0x4010) == "dpcm"
    assert channel_for_address(0x4015) == "status"
    assert channel_for_address(0x4017) == "frame_counter"
    assert channel_for_address(0x4020) is None


def test_decode_pulse_reg0():
    # Duty=2, length halt, constant vol, volume=15 => 10_1_1_1111 = 0xBF = 191
    decoded = decode_pulse_reg0(0xBF)
    assert decoded["duty"] == 2
    assert decoded["length_halt"] is True
    assert decoded["constant_volume"] is True
    assert decoded["volume_envelope"] == 15

    # Duty=0, no halt, no const, vol=0 => 00_0_0_0000 = 0
    decoded = decode_pulse_reg0(0x00)
    assert decoded["duty"] == 0
    assert decoded["constant_volume"] is False
    assert decoded["volume_envelope"] == 0


def test_decode_pulse_reg1():
    # Sweep enable, period=3, negate, shift=2 => 1_011_1_010 = 0xBA = 186
    decoded = decode_pulse_reg1(0xBA)
    assert decoded["sweep_enable"] is True
    assert decoded["sweep_period"] == 3
    assert decoded["sweep_negate"] is True
    assert decoded["sweep_shift"] == 2


def test_decode_pulse_period():
    # lo=253, hi=0 => period = 253
    assert decode_pulse_period(253, 0) == 253
    # lo=0, hi=7 => period = 0x700 = 1792
    assert decode_pulse_period(0, 7) == 1792
    # lo=0xFF, hi=0x07 => period = 0x7FF = 2047
    assert decode_pulse_period(0xFF, 0x07) == 2047


def test_decode_noise_reg2():
    decoded = decode_noise_reg2(0x84)  # mode=1, period=4
    assert decoded["mode"] == 1
    assert decoded["period_index"] == 4

    decoded = decode_noise_reg2(0x04)  # mode=0, period=4
    assert decoded["mode"] == 0
    assert decoded["period_index"] == 4


def test_pulse_period_to_freq():
    # Period 253 should give roughly 440 Hz (A4)
    freq = pulse_period_to_freq(253)
    assert 430 < freq < 450

    # Muted below period 8
    assert pulse_period_to_freq(7) == 0.0


def test_triangle_period_to_freq():
    freq = triangle_period_to_freq(253)
    assert 215 < freq < 225  # triangle divides by 32 instead of 16

    assert triangle_period_to_freq(1) == 0.0
