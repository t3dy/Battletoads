# 2A03 APU Register Map ($4000–$4017)

Quick reference for ReapNES Studio development.
Source: NesDev Wiki — APU registers.

## Pulse 1 ($4000–$4003)

| Addr   | Bits     | Field                          |
|--------|----------|--------------------------------|
| $4000  | DD..VVVV | Duty (2), Loop/Disable LC (1), Constant Vol (1), Vol/Envelope (4) |
| $4001  | EPPP.NSSS | Sweep: Enable, Period, Negate, Shift |
| $4002  | TTTT.TTTT | Timer low 8 bits               |
| $4003  | LLLL.LTTT | Length counter load (5), Timer high 3 bits |

## Pulse 2 ($4004–$4007)

Identical layout to Pulse 1.

## Triangle ($4008–$400B)

| Addr   | Bits     | Field                          |
|--------|----------|--------------------------------|
| $4008  | CRRR.RRRR | Linear counter control/reload  |
| $400A  | TTTT.TTTT | Timer low 8 bits               |
| $400B  | LLLL.LTTT | Length counter load, Timer high 3 |

## Noise ($400C–$400F)

| Addr   | Bits     | Field                          |
|--------|----------|--------------------------------|
| $400C  | --LC.VVVV | Loop, Constant vol, Volume     |
| $400E  | M---.PPPP | Mode (short=1), Period index   |
| $400F  | LLLL.L--- | Length counter load             |

## DMC ($4010–$4013)

| Addr   | Bits     | Field                          |
|--------|----------|--------------------------------|
| $4010  | IL--.RRRR | IRQ enable, Loop, Rate index   |
| $4011  | -DDD.DDDD | Direct load (7-bit DAC)        |
| $4012  | AAAA.AAAA | Sample address = $C000 + A*64  |
| $4013  | LLLL.LLLL | Sample length = L*16 + 1 bytes |

## Status / Frame Counter

| Addr   | Bits     | Field                          |
|--------|----------|--------------------------------|
| $4015  | ---D.NT21 | Write: enable channels. Read: status |
| $4017  | MI--.---- | Mode (0=4-step, 1=5-step), IRQ inhibit |
