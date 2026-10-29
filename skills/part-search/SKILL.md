---
name: part-search
description: Find a part at the distributors the project buys from (LCSC/JLCPCB by default; RS, Farnell, Mouser, DigiKey, Reichelt with a profile each), check stock and assembly, and create its parts-database entry (hardware/parts/<LCSC number or manufacturer part number>.json) with pins, roles, ratings, compliance data and a datasheet sign-off. Use when a new part is needed, a part must be replaced (stock, variant, package, distributor), an LCSC or order number is mentioned or the graph check reports a missing entry (P-1). For a search across several distributors use the agent part-selector, which follows this skill in its own context.
argument-hint: "<part, requirement or LCSC number>"
---

# Find a part and enter it

Wanted: $ARGUMENTS. Fields of an entry: `${CLAUDE_PLUGIN_ROOT}/handbook/04-parts-database.md`.

## Frame

- If the boards are assembled by JLCPCB, a part that must be bought and soldered separately is no option unless the
  user says so. A part in stock beats a "better" one that is not.
- Basic parts first (no feeder fee), extended when needed. When the user declares something a must, keep searching
  instead of switching to an alternative. Where it does not matter to them, decide and give the reason.

## Search

At every distributor the project buys from – `[project] distributors` in edakit.toml, default `["lcsc"]` – as its
profile says: `${CLAUDE_PLUGIN_ROOT}/skills/part-search/distributors/<name>.md` (`lcsc`, `rs`, `farnell`, `mouser`,
`digikey`, `reichelt`). The profile tells how to search there, what loads without a key and what the page states.

- Report stock as a number with the date ("1 902 pcs at LCSC, 2026-10-25"), not as "few".
- "Not available" only after the routes the profile names (at LCSC: `edakit part search`, EasyEDA's search, the
  series name), each with its queries in the result.
- For JLCPCB assembly: `edakit stock --lcsc <C…>` for every candidate – listed, JLCPCB's stock, "Standard Only",
  MSL, X-ray – before it is chosen (P-4 checks the same later, from the project's snapshot).
- Datasheet: `edakit part fetch <key>` once the entry exists (`--url` for one from the manufacturer) – it keeps the
  PDF beside the project and says whether it is of this part (a warning names a longer variant: MT3608L for
  MT3608); read that file and note its revision.
- A part from outside LCSC is hand-soldered (`bom: false`) or goes to another assembler; in EasyEDA it needs a
  footprint – the `easyeda_device` of a part in the same package (handbook 3.1).
- A part nobody sells is no search: a board of an edakit project comes with `edakit part datasheet` in its project
  and `edakit part own <path>` here; anything else – own board without edakit, from the bin, made by hand – with the
  skill own-part (handbook 4.5).

## Entry

- An LCSC part: `edakit part import <LCSC>` writes the start – identification, footprint, the symbol's pin numbers
  and names – and caches the library's symbol and footprint (P-1 then compares the graph with the symbol).
- `hardware/parts/<LCSC>.json` – from another distributor `hardware/parts/<manufacturer part number>.json` with
  `mpn` set and `order` for the order numbers (`{"rs": "223-0562"}`, with a minimum or pack size
  `{"rs": {"code": "223-0562", "moq": 10, "step": 10}}`); the graph names it in `part`. A part bought
  separately at LCSC with a minimum gets `{"lcsc": {"moq": 20}}` – `edakit order` rounds its cart line up. After the
  pattern of a similar part: `kind`, `pins` (names identical to the graph, `type`, `role`, `vmax`), `params`,
  `ratings`, `spice` for diodes/transistors, `lead` for through-hole parts (P-7 stays pending without it and holds
  it to the footprint's holes at once; with `length_mm` when the drawing gives it), `body` `h_mm` when the board goes
  into an enclosure, `mate` for a connector whose plug needs room (the mated plug from the manufacturer's assembly
  drawing, handbook 4.1), `sources` (mark every assumption as "assumption" – also a value taken from a
  sibling part or the series, e.g. "VR_max = 5 V from XL-304UGD of the same series: assumption"; the gate protocol
  lists them). The block library (`edakit/blocks/parts/` of the plugin) has checked entries to copy from.
- What the checks read from the datasheet besides the limits: input-only pins `type: input`; strapping pins `"strap":
  "high"|"low"` with the internal `"pull"` at reset (G-12); built-in pull resistors `"pull": "up"`, `"pull_ohm"` (I2C
  modules, G-11); roles `sda`/`scl` (G-11) and `cc1`/`cc2` on a USB-C receptacle (G-14), and for a module or breakout
  with USB-C `params.usb_c` `{"cc": "rd_5k1" | "controller" | "none"}` from its schematic (G-14); MCU output current
  `gpio_i_max_a` per pin and `gpio_i_total_max_a` for all together (E-2); from the recommended operating conditions of
  an IC the supply range `vdd_op_min`/`vdd_op_max` (`v_op` on a pin with a range of its own) and the input thresholds
  `vih_v`|`vih_ratio`, `vil_v`|`vil_ratio` (E-3); for a part that dissipates – resistor, diode, transistor, MOSFET,
  regulator, LED driver – `rth_ja_k_per_w` (RθJA, steady state) and `tj_max_c` (E-2: junction and touch temperature),
  on an MCU module with an on-board LDO (`regulator: "ldo"`) those of that regulator, from its datasheet (E-3); on
  the serial output of a shift register or LED driver (SDO, Q7) the clock edge it changes after, `out_edge`, and its
  delay from the switching characteristics, `t_pd_ns: [min, max]` with `null` for a value the datasheet does not give
  (H-9); MCU pin `functions` from the pin-mux table (`["spi0.sck", "i2c1.sda", "pwm1.a", "adc0"]`, `[]` for a pin used
  on the module – G-15, handbook 4.1); a fuse's `i_hold_a`, `i_trip_a` and its derating table `i_hold_vs_temp`, and the
  `i_max_a` of a connector or switch as a whole – every contact of the current path counted (G-17); a 0 Ω jumper
  `value_ohm: 0` with its maximum resistance `r_max_ohm` (it joins its nets, handbook 3.3); a switching regulator's
  `hot_loop`, the pin roles of its hot loop from the datasheet's layout section (G-18); a pin `hint` or part `hints` for
  what the datasheet warns about (shown by `edakit hints`).
- `compliance` for the regulatory review (M-6, handbook 15): `rohs` (true, false or the exemption), `reach` (the
  supplier's SVHC statement), for a part that transmits `radio` (`bands_mhz`; `max_dbm`, the conducted power at the
  RF port as the datasheet states it; `antenna_dbi`, the gain of its antenna in the product – a module's datasheet
  or certificate; `eirp_dbm` where a certificate states the e.i.r.p.; `doc` = URL of the EU declaration of
  conformity – G-24 compares the e.i.r.p. with the band's limit), `"radio": "none"` for a module or microcontroller
  without a transmitter (P-11 asks every one of them), and `source` (page and date). Take it from the
  distributor's part page or the manufacturer's declaration; what nobody states stays out – the reviewer reports it
  as open, not as fine.
- Check against the datasheet: pinout, polarity at the footprint (which pad is pin 1 / anode / +), package, every
  rating. Library footprints are sometimes wrong (a "+" printed at the cathode pad) – the polarity sheet of the gate
  and the second check M-1 exist for that. Then `verified` with by, date, datasheet revision, `datasheet_sha256`
  (from `<datasheets>/<key>.json`), `checked`, `open`. An open point that only the assembly preview or the delivered
  board answers names its phase: `{"text": "flat side of the star against the footprint", "when": "order"}`
  (`"acceptance"`: on the delivered board) – the gate protocol puts it under that phase's manual checks.
- Record the choice in the decision log (alternatives and why they were dropped).

Then `edakit stock` and `edakit check` (P-1, P-4, P-6 – the graph's `lcsc`, `part`, `value` and `type` name this
entry –, G-9), and the hardware-change skill if the part goes into the graph.
