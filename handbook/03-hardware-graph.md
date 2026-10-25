# 3 The hardware graph

The graph is a pin-level netlist in JSON. It is the **only** place where parts, values and connections are decided.
Example: [the Christmas bell's graph](https://github.com/tgd1975/automatic_christmas_bell/blob/main/hardware/graph.json); the snippets below come from the
[test project](../tests/fixtures/led-bar/hardware/graph.json).

## 3.1 Format

```json
{"graph": {
  "name": "led-bar", "version": "1.0", "date": "2026-10-25", "description": "…",
  "components": [
    {"designator": "U2", "type": "ic", "label": "TLC5916 8-channel constant-current LED driver",
     "part": "TLC5916IDR", "lcsc": "C90107", "board": "main",
     "pins": {"1": "GND", "2": "SDI", "3": "CLK", "4": "LE(ED1)", "5": "OUT0", "…": "…", "16": "VDD"},
     "nc": ["14"], "notes": "I_OUT = 15 x 1.26 V / R1 (D-9)"},
    {"designator": "R2", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
    {"designator": "U1", "type": "microcontroller", "lcsc": "C41407547", "bom": false, "pins": {"…": "…"}}
  ],
  "nets": [
    {"name": "+5V", "pins": ["D1.1", "U1.39", "C2.1", "D2.1"], "v": [0, 5.5], "notes": "behind the reverse diode"},
    {"name": "LED_CLK", "pins": ["U1.5", "U2.3"], "v": [0, 3.4],
     "waive": {"G-4": "floating until the firmware runs, harmless: OE is pulled high"}}
  ],
  "cables": [
    {"name": "W1", "from": "J2", "to": "J1", "pins": {"1": "1", "2": "2"}, "r_ohm_per_wire": 0.065}
  ]
}}
```

| Field | Meaning |
|---|---|
| `designator` | as on schematic, PCB and silkscreen |
| `type` | rough class for the generated template layout and the schematic blocks: `microcontroller`, `module`, `ic`, `transistor`, `connector`, `regulator`, `diode`, `led`, `resistor`, `capacitor`, `inductor`, `button`, `switch`, `potentiometer`, `audio`, `testpoint`, `battery_holder`, `fuse` |
| `lcsc` | the LCSC number – identifies symbol, footprint, parts entry and the BOM line |
| `pins` | pin number → pin name, **with the pin numbers of the EasyEDA/LCSC symbol of exactly this part**. The names must equal the parts entry (P-1). |
| `nc` | pins deliberately unconnected; every pin is in exactly one net or in `nc` |
| `board` | which board the part is on (a key of `[boards]` in edakit.toml); may be omitted with one board |
| `value` | shown in the BOM ("10k", "100nF") |
| `bom: false` | the part is placed on the PCB but not in the BOM for assembly (hand-soldered, bought separately) |
| `easyeda_device` | for parts without LCSC number (bare test pads): `{name, uuid, libraryUuid}` of an EasyEDA library device |
| `verify` | an open question about pins/polarity that the library does not settle; blocks the release (G-9) until resolved |
| `waive` | `{check id: reason}` – a finding accepted on purpose; printed with its reason in every report |
| `notes` | free text; cite decision numbers here |
| net `v` | `[min, max]` voltage over **all** intended operating states (all supply variants, reversed supply, unloaded) |
| `cables` | wires between boards: connector pins joined 1:1; the cable is no part, its resistance feeds the simulation |

## 3.2 Conventions that save trouble

- **Pin numbers come from the EasyEDA symbol**, not from the datasheet. They usually agree; for LEDs and diodes they
  often do not (anode = 1 for one LED, = 2 for another of the same shape). Read them once from EasyEDA
  (`edakit schematic create --only U3` and `easyeda_schematic_component_pins`) and write the roles into the parts
  entry. Code that needs "the cathode" asks for the role, never for the pin name.
- **Net names are stable identifiers** used by firmware, simulation config and docs. Rename deliberately.
- **Voltage ranges are worst case.** `v` is what G-3 compares with the pin limits and what the simulation checks every
  scenario against. Think about the unloaded supply, the reversed supply, a programming cable plugged in at the same time.
- **Decisions in the graph.** "Why 2 k?" – `notes: "D-9: I_OUT = 9.45 mA"`. The decision log has the reasoning.
- **One part, one LCSC number.** A footprint variant is a different part.

## 3.3 Rule checks (stages P and G)

`edakit check` runs in well under a second; put it into the pre-commit hook and CI.

| Check | What | Finds e.g. |
|---|---|---|
| G-1 | structure: unique designators and nets, every pin in exactly one net or `nc`, nets with ≥ 2 pins, a voltage range per net, a known board per part, nets across boards only through a cable | a forgotten pin, a typo in a pin reference |
| G-2 | pin locks: pins the firmware relies on are on the expected nets (`[checks] pin_locks`); optionally a pin table in a Markdown document equals the graph (`[checks] doc_pin_table`) | firmware and hardware disagree |
| G-3 | voltage domains: every net's range within `vmax` of every pin on it | a 5-V signal on a 3.3-V GPIO |
| G-4 | no floating input: an input needs a driver or a pull resistor; an input driven only by MCU pins needs a pull (floats until the firmware runs); every BJT needs a base-emitter resistor | a floating OE or EN pin at power-up |
| G-5 | at most one push-pull output / supply output per net | two outputs against each other |
| G-6 | decoupling: per net at least one capacitor to ground per IC supply pin (`power_in`) | the missing 100 nF |
| G-8 | voltage ratings with margin: capacitors (×1.5), diodes VRRM (×1.5), BJT VCEO, MOSFET VDS/VGS (×1.5), fuses, switches, connectors | a 6.3-V capacitor on a 5-V rail |
| G-10 | reverse polarity from the topology: what a reversed source (battery holders, `[checks] reverse_protect`) reaches through fuses, switches and connectors may only be a capacitor, the anode of a diode whose cathode is outside, or the drain of a PMOS whose source and gate are outside | the protection diode bypassed, an IC directly on the battery |
| P-1 | graph pins (number and name) = parts entry; an entry exists for every LCSC number; no supply pin marked `nc` | a wrong part number, pins shifted by one |
| G-9 | sign-off: every part `verified` against its datasheet, no open `verify` note (pending – blocks only the release) | an unchecked part going into an order |

Results: `ERROR` (must be fixed), `WAIVED` (accepted in the graph with a reason), `PENDING` (open sign-off). Exit 1 on
errors, with `--release` also on pending sign-offs.

Polarity (is the LED the right way round?) is not a graph rule but a simulation result: a reversed LED shows up in
stage E as "LED reversed" or as a dark LED (chapter 5).

## 3.4 Working rules

1. Change the graph, never the schematic or the PCB. The hardware-change skill walks through the rest.
2. Every new LCSC number gets its parts entry first (part-search skill).
3. `edakit check` and `edakit sim` before every commit that touches `hardware/` – the pre-commit hook does it.
4. A finding is fixed or waived with a reason. Never edit a check to make a finding go away.
5. Generated files (firmware pin tables, the circuit description's parts list) are regenerated from the graph, never
   edited, and committed together with the graph change.
