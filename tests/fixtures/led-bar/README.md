# Test project: led-bar

The data the tests build their faults into (it never ran through EasyEDA). The documented example is the
[Christmas bell](https://github.com/tgd1975/automatic_christmas_bell).

A Raspberry Pi Pico 2 drives eight green LEDs through a TLC5916 constant-current sink (9.45 mA per LED, set by R1).
5 V come in through a JST PH connector and a Schottky diode against reverse polarity; R2 keeps the LEDs dark until the
firmware runs; one push button to ground. Two layers, 90 × 40 mm, rounded corners, two M3 holes, two tooling holes
for JLCPCB Economic assembly.

| File | |
|---|---|
| [edakit.toml](edakit.toml) | the table of contents: project, board, where the files are, release |
| [hardware/graph.json](hardware/graph.json) | 17 parts, 18 nets, the hand-over to the layout and the check settings – the only source of the circuit |
| [hardware/boards/main.toml](hardware/boards/main.toml) | the board: outline, holes, placement plan, routing rules, pours, silkscreen |
| [hardware/schematic.toml](hardware/schematic.toml) | the blocks, notes and pin table of the schematic |
| [hardware/parts/](hardware/parts/) | 10 parts entries, signed against their datasheets |
| [hardware/sim.json](hardware/sim.json) | 3 supply voltages × 2 loads × 2 LED corners |
| [hardware/signoff.json](hardware/signoff.json) | manual checks M-1, M-6, M-5, M-2, M-4 (open) |

Offline, from this folder:

```bash
edakit check      # 0 errors, 3 waived (SDI/CLK/LE float at boot – harmless, OE is pulled high)
edakit sim        # 12 scenarios, ~700 checks
edakit gate       # P, G, E pass; NOT RELEASED: M-1/M-5 open, stages S/L/F need EasyEDA
```

With EasyEDA Pro (project "led-bar" created by hand once and open, bridge connected): `edakit schematic create --save`, then
the steps of [handbook chapter 6–8](../../../handbook/README.md). The placement plan is a starting point: run `edakit pcb
dump` once the parts are in the PCB and adjust positions after `edakit pcb plan`.

The parts entries were copied from a real project where each was checked against its datasheet; the Pico 2 and the
TLC5916 entries got the generic behaviour models `mcu` and `cc_sink`.
