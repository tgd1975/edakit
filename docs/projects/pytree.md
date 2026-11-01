# pytree

A programming advent calendar. Every day it sets a small Python task; the answer is an 8-bit code, set on the DIP
switch of a Christmas tree made of circuit boards. With each code the tree wakes a little more: one LED on the first
of December, the whole tree with its golden star and a melody from the buzzer on the 24th. Its repository is private;
this page is the one description of it in edakit.

**State 2026-11-01:** the tree board released in gate run 20261031-110510; edakit's gate makes the same
manufacturing files from the same board (run 20261101-003052). Not ordered yet; a small batch of five is planned.

## What it is

- **The tree.** A Waveshare RP2350-Zero on a pin header, three LED drivers, 30 through-hole LEDs on 24 outputs, an RGB
  star and a buzzer, powered over USB-C in a 3D-printed hill.
- **The board.** Two layers, about 120 parts and 98 nets. All tracks run on the back: the front carries only the LEDs,
  the star, the print and a copper area. Routed by Freerouting into about 1500 track pieces and 220 vias, DRC 0.
- **The assembly.** JLCPCB makes the board and assembles the back side; the through-hole parts are soldered by hand.

## What it changed in edakit

edakit was grown on this project: the first released manufacturing files came five days after the first graph. The
simulation ran 41 scenarios with about 11 000 single checks in about 3 seconds. What went wrong on the way, and what
edakit learned from it, is in [lessons learned](../../handbook/13-lessons-learned.md).
