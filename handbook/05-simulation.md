# 5 Simulation (stage E)

`edakit sim` turns the graph into an ngspice netlist per scenario, computes the DC operating point, and checks every
part against its ratings and the circuit against its function – in seconds, on every commit.

Why DC operating points first: the expensive errors on a small board are static. A resistor that cooks at full
brightness, a regulator without headroom at the low end of the USB voltage, an LED the wrong way round, a net that
reaches a pin with more than it tolerates, a supply that cannot deliver the sum of all loads. A DC sweep over supply
corners × load cases × LED tolerance corners finds those. Where the supply itself changes – plug, unplug, a
switch-over between two sources – a DC scenario sits on one side of the gap or the other; transient runs (5.2) follow
the supply over time and E-5 judges them. Switching spikes and fast edges are measured on the delivered board
(acceptance test): the behaviour models know no switching.

## 5.1 How the netlist is built

- Resistors, capacitors, inductors (with DCR), fuses, diodes, LEDs (model from Vf at a test current), BJTs, MOSFETs
  come from the graph 1:1, values and SPICE models from the parts database. A 0 Ω bridge (`value_ohm: 0`) is its
  `r_max_ohm`, 50 mΩ without one – ngspice finds no operating point with 0 Ω.
- An RGB LED (`led_rgb`) is three LEDs, one per colour with that colour's `params` and `ratings`. The roles choose the
  layout (4.1): with a common cathode each colour runs from `anode_<color>` to `cathode`, with a common anode from
  `anode` to `cathode_<color>` – the layout a constant-current sink or a low-side switch per colour needs. Each colour
  is checked as an LED of its own (`D10_RED`, `D10_GREEN`, `D10_BLUE`): E-2 against its ratings, E-3 on its driver
  output or by the load's `leds_on`, where the designator turns on all three colours and `D10_RED` one.
- Switches, buttons, DIP switches are closed or open as the scenario's load says (`buttons`, `open`, `dip_closed`).
  A relay is its coil (`coil_ohm`) plus a contact from `common` to `no` when the load lists it in `relays_on`, else to
  `nc`.
- Supplies: connectors listed under `sources` (a voltage source behind a source resistance), battery holders with a
  cell state (`cells`). A module that brings its own supply (an Arduino Nano on USB) is a source as well: `plus` is
  its 5V pin, the voltage is USB minus its on-board diode – or USB itself on a module without that diode;
  `combine_sources` (5.2) puts it into scenarios with the other sources.
- `i_min_a` on a source: the least current the supply needs to stay on – USB power banks switch off below
  50–100 mA after a few seconds. E-3 checks every scenario against it.
- No supply is fed backwards: where two supplies meet and nothing blocks the way, the higher one feeds the lower one –
  into a PC's USB port through a module whose 5 V pin is its VBUS, into primary cells. E-3 holds the current into
  every source (against its direction) to `i_back_max_a` of the source, and the current into every cell of a battery
  holder to `i_charge_max_a` of its cell state (`"cells": {"nimh": {"v": 1.3, "r": 0.05, "i_charge_max_a": 0.1}}` for a
  pack its charger charges on purpose); both are `criteria.blocking_max_a` (1 mA) unless set.
- Every net is one node – a track is 0 Ω – unless sim.json `copper` names it (5.2): then each of its pins gets a node
  of its own, with the routed tracks and vias as resistors in between, and every check sees the voltage at the pin.
- Off-board loads (a servo, a motor, a strip at a connector): the load's `external`, e.g.
  `{"J1": {"plus": "2", "minus": "1", "i_a": 0.3}}` – a constant current between the two pins; it counts for the
  connector's contact current and for the track widths.
- ICs and modules are replaced by **behaviour models** (`params.behavior` in the parts entry):

| Model | Roles | Parameters | Behaviour |
|---|---|---|---|
| `ldo` | `vin`, `vout`, (`gnd`) | `vout_v`, `dropout_v`, `iq_a` | output = min(vout, vin − dropout); input current = output current + iq |
| `buck`, `boost` | `vin`, `vout` | `vout_v`, `efficiency`, `iq_a` | ideal output; input power = output power / efficiency |
| `mcu` | `vsys`/`vin`/`vdd`, optional `vout`/`3v3`, `gpio` | `v_io` (V, or `"vin"` when the I/O runs from the supply pin, as on a 5 V AVR), `i_core_a`, `gpio_r_out_ohm`, `regulator` (`buck`/`ldo`), `vout_v` (regulator output, default `v_io`), `efficiency`, `vih_v`/`vih_ratio`, `vil_v`/`vil_ratio` | on-board regulator feeding the core and external loads; GPIO outputs as sources with output resistance (levels from the load's `gpio`), pull-ups from the config; the config's `inputs` must sit at a defined logic level |
| `cc_sink` | `rext`, `out` (or `out0` … `outN`), `vdd`, `oe_n` | `vrext_v`, `iout_gain`, `vout_knee_v`, `idd_max_a` | constant-current LED driver (TLC5916, STP08CP05, …): R-EXT held at vrext, every enabled output sinks gain × I(R-EXT) with a soft knee; `oe_n` high = all off; pins of type `output` (SDO to the next driver's SDI or to an MCU input that reads the chain back) low through 50 Ω, as in `logic`; an unconnected SDO stays out of the netlist |
| `logic` | supply pins (`power_in`), outputs | `icc_a` | supply current, outputs low |
| `current` | supply pins | `i_a` | constant supply current; with `ratings` `vin_min`/`vin_max` (an own board, 4.5) E-3 checks the voltage at its supply pins against them |
| `none` | – | – | nothing |

Two model rules hold for every scenario and matter in transient runs. A regulator whose ratings give `vin_min` – an
`ldo`, `buck` or `boost`, and the `mcu` model's on-board regulator with `vin_min` or `vsys_min` – locks out below it:
its output and its input current fall to 0 over the 0.2 V below `vin_min`. A constant-current load – `i_core_a`,
`idd_max_a`, `icc_a`, `i_a`, an `external` load – falls to 0 below 0.5 V across it, so a rail nothing feeds stays at
0 V instead of being pulled below ground. Above these voltages both are what the table says; a DC result with every
input above its minimum is the same as without them.

A project adds its own models in a plugin file (`sim_plugin = "hardware/sim_plugin.py"` in `[project]`):

```python
def my_boost(nl, des, part):            # nl: the netlist builder, see edakit/sim/netlist.py
    roles = nl.roles(des)               # role -> net
    nl._regulator(des, nl.n(roles["in"]), nl.n(roles["out"]), "0", "boost", part["params"])

MODELS = {"my_boost": my_boost}

def checks(design, cfg, res, meta, load, add):   # extra E-3 checks per scenario
    v = res.get("n_v_led", 0)
    add("E-3", "V_LED", "LED rail", v, "5.0 V ± 3 %", abs(v - 5.0) <= 0.15, unit=" V")
```

## 5.2 Scenarios

`hardware/sim.json` (the snippet is from the [test project](../tests/fixtures/led-bar/hardware/sim.json); a USB-powered
module with a servo: [Christmas bell](https://github.com/tgd1975/automatic_christmas_bell/blob/main/hardware/sim.json)):

```json
{
  "ambient_c": 40,
  "sources": {"J1": {"plus": "1", "minus": "2", "r_ohm": 0.3, "i_max_a": 0.5}},
  "supplies": {"usb-min": {"J1": 4.75}, "usb-nom": {"J1": 5.0}, "usb-max": {"J1": 5.25}},
  "loads": {
    "idle":   {"gpio": {"LED_OE": 1}, "leds_on": []},
    "all_on": {"gpio": {"LED_OE": 0}, "cc_on": {"U2": "all"}, "buttons": ["SW1"]}
  },
  "corners": ["min", "max"],
  "mcu": {"U1": {"outputs": ["LED_SDI", "LED_CLK", "LED_LE", "LED_OE"], "pullups": ["BTN"], "pullup_ohm": 50000}},
  "derating": {"p": 0.5, "i": 0.8, "v_cap": 0.67, "v_diode": 0.67, "v_bjt": 0.67},
  "criteria": {"net_range_tol_v": 0.05, "led_on_min_ratio": 0.8, "led_off_max_a": 1e-5, "rail_tol": 0.03, "tj_max_c": 110},
  "report": ["+5V", "3V3"]
}
```

Scenarios = supplies × loads × corners (LED forward voltage at min/max), plus `extra_scenarios` (e.g. "programming
cable plugged in, external supply off"; `"info": true` turns failures into information).

A board with several sources – a supply connector and a module that brings its own USB, USB and cells – gets the
combinations from `combine_sources` instead of by hand: a map from each source to its range, `[low, high]` in volts for
a source of `sources`, two cell states of `cells` for a battery holder.

```json
"combine_sources": {"J1": [4.75, 5.25], "U1": [4.75, 5.25], "BT1": ["empty", "fresh"]}
```

It generates supplies named after what they set: each source alone at both ends (`J1 4.75`, `J1 5.25`, …, `BT1 fresh`)
and, with more than one, all of them together, each one high in turn and the others low (`J1 5.25 + U1 4.75 + BT1
empty`, `U1 5.25 + J1 4.75 + BT1 empty`, `BT1 fresh + J1 4.75 + U1 4.75`) – where one supply feeds the others
hardest (E-3: no supply fed backwards). They run with every load and corner like a supply of `supplies`; `edakit sim`
prints them once. A hand-written case is not run twice: a supply of `supplies` with the same settings runs under its
own name instead, and an extra scenario with the same supply and load takes that load's case out of the matrix – the
way to keep a combination a procedure excludes ("unplug J1 while flashing") as `"info": true`. Without the key nothing
is generated. A load with
`"matrix": false` runs only where an extra scenario names it – fault cases such as a stalled servo, whose result you
want to see and record as a decision, but which must not block every commit. `ambient_c` is the ambient of the
scenarios (E-2 derates the fuses' hold current to it); `ambient_min_c`, optional, the lowest one – G-17 holds a fuse's
hold current there against the connectors it protects (without it: the datasheet's `i_hold_a`). Battery projects add
`"cells": {"fresh": {"v": 1.6, "r": 0.15}, "empty": {"v": 1.0, "r": 0.4}}` and supplies like `{"BT1": "fresh"}`.

A board people reach – picked up, held, pressed – gets its touch limit: `"touch_c": {"main": 48}`, a map from each such
board to the temperature in °C its parts may reach (E-2, 5.3). The number comes from the standard the product follows,
for the surface and the time a hand stays on it; IEC 62368-1 TS1 allows 48 °C for longer than a minute, 60 °C on plastic
(51 °C on metal) for 10 s to 1 min and 77 °C (60 °C) for 1–10 s. A board without it gets no touch item; a name that is
no board of edakit.toml stops the run.

**Routed copper.** Once a board is routed, `copper` brings the resistance of its tracks into every scenario:

```json
"copper": {"nets": ["+5V", "VIN"], "oz": 1, "via_ohm": 0.001}
```

For each listed net and each board, `edakit sim` reads the routing as `edakit route check` does
(`<artifacts>/route/<board>.ses` with `<board>_board.json`). Every track piece becomes a resistor ρ × L / (w × t)
(0.0172 Ω·mm²/m, t = `oz` × 35 µm, default 1 oz), every via `via_ohm` (default 1 mΩ) between its layers. A pin's pads
join where a track or a via ends on them; on a layer where the board file pours the net (`[[pours]]`) its copper counts
as ideal. Each pin gets its own node, and every check reads its pin: the MCU's supply, a regulator's input, a
driver's headroom, an operating range. A net's range `v` holds for its lowest and highest pin ("4.365 V (D9.1) …
4.442 V (D1.1)"), the `report` shows the lowest. The ground net stays the reference and cannot be listed. A listed
net that cannot be annotated stays one node, and E-1 notes why: the board has no routing yet, a pin has no pad in the
board json, or a pin is not connected by the routed tracks, vias or pours (`edakit route check`). On the example, a
+5V track of 200 mm × 0.15 mm (0.655 Ω) from D1 to the loads drops the far LED anode from 4.442 V to 4.365 V. A range
`v: [4.45, 5.5]` passes without `copper` and fails with it. The routing is an artifact of `edakit route`, so run
`edakit sim` again after every routing run; the gate does that in stage E. Without `copper`, every net is one node as
before.

**Transient runs.** `transients` names runs over time, each with its supplies as curves, a load and limits:

```json
"transients": {
  "usb-unplug": {"supply": {"J1": [[0, 4.75], [0.001, 4.75], [0.00101, 0]]}, "load": "all_on", "corner": "max",
                 "stop_s": 0.0013, "step_s": 1e-6, "expect": {"+5V": {"min_v": 1.8}}},
  "usb-plug":   {"supply": {"J1": [[0, 0], [0.001, 4.75]]}, "load": "all_on", "stop_s": 0.002,
                 "expect": {"J1": {"i_max_a": 0.5}}}
}
```

`supply` gives each source of `sources` a voltage or `[t, V]` points (seconds, rising from 0; linear in between, the
last value held) and each battery holder a cell state of `cells`; what it leaves out is not plugged in. `load` and
`corner` (default `typ`) are those of the scenarios; `stop_s` is the length of the run, `step_s` the largest time step
(default `stop_s` / 1000). ngspice starts from the operating point with every source at its first point – 0 V on every
net for a plug-in, the DC state for an unplug – and runs `.tran`. `expect` holds limits per net (`min_v`, `max_v`, the
lowest and highest voltage during the run) and per source (`i_max_a`, the peak current it delivers); every MCU whose
ratings give `vin_min` (or `vsys_min`) is held to it as well, from the moment its supply pin first reaches it – a plug
run passes once the MCU has started and never browns out, an unplug fails as soon as the rail falls below it (E-5).
`"info": true` turns failures into information. Each run gets its row in the scenario table with the lowest and highest
voltage of the `report` nets and the peak current of each source; a run adds no stress items and no net currents.
On the example, J1 dropping to 0 V in 10 µs leaves +5V at 2.99 V after 0.3 ms with C2 = 22 µF and at 1.59 V with
1 µF, where the Pico 2 locks out; the plug-in takes 0.22 A from J1 while C2 charges. A switch-over between two sources
– two P-MOSFETs back to back next to a USB diode – is a run with both in `supply`, the one ramping while the other
holds; its gap comes from the MOSFETs' thresholds and body diodes, and the capacitors bridge it or not. Without
`transients` nothing runs.

`leds_on` lists the LEDs that light in a load – the designator, or `D10_RED` for one colour of an RGB LED, `"all"` for
every one; the others are expected dark. LEDs on the output of a constant-current sink go by the channel instead (5.3).
As soon as an LED is on no driver output, every load needs `leds_on`, `[]` when none lights (E-4).

## 5.3 Checks

| Check | What |
|---|---|
| E-1 | the operating point converges, a transient run runs to its end; a net of `copper` that stays one node is noted (info) with the reason |
| E-2 | stress of every part against its ratings with derating: resistor power ≤ 50 %, currents ≤ 80 %, capacitor/diode/transistor voltages ≤ 67 %, LED forward current and reverse voltage, fuse hold current at ambient, connector, switch and relay contact current, relay coil voltage, the current of every MCU output (`gpio_i_max_a`) and of all outputs together, sourced and sunk (`gpio_i_total_max_a`) – each pin may be fine and the sum beyond the package; the junction temperature of every part with `rth_ja_k_per_w` against its `tj_max_c`, and on a board of `touch_c` against the touch limit (below the table) |
| E-3 | function: current from every source (≤ `i_max_a`), no source and no cell fed backwards (≤ `i_back_max_a`, `i_charge_max_a`, 1 mA by default), regulator outputs within tolerance, input above `vin_min`, LDO junction temperature (against the same limit as E-2's), MCU supply voltage and load on its regulator, MCU inputs at a defined level (≤ VIL or ≥ VIH – a 3.3 V signal into a 5 V AVR is the classic case), every part with an operating supply range inside it, every input pin with thresholds at a defined level and the high level of every MCU output reaching the VIH of the inputs on its net (below the table), MCU outputs only on pins that can drive (an output on an input-only pin is reported and not driven), LED driver output headroom and junction temperature, every LED on or dark as the load says (driver channels: ≥ 80 % of its share of the set current, also for an LED behind 0 Ω bridges or one resistor; parallel LEDs share within a ratio – below the table), relays pull in (`v_operate`) and release (`v_release`) as the load says, an own board supplied inside the range it was simulated for (`vin_min` … `vin_max`, 4.5), diodes that must block (`expect_blocking`), every net inside its declared range `v` (a net of `copper`: its lowest and highest pin), plus the plugin's checks |
| E-4 | LED has a known driver: in every scenario every LED – each colour of an RGB LED – has a state E-3 checks, its cathode on a driver output (directly, behind 0 Ω bridges or one resistor) or the load's `leds_on`; an LED with neither, or one the netlist left out because its parts entry lacks a role it reads (anode, cathode and their colours, 4.1), fails as "LED without a known driver" |
| E-5 | transient limits: in every run of `transients` each limit of its `expect` – a net's lowest voltage ≥ `min_v`, highest ≤ `max_v`, a source's peak current ≤ `i_max_a` – and every MCU's supply pin, once it has reached its `vin_min` (`vsys_min`), never below it again before the run ends; actual value with the time it occurs ("2.985 V at 1.3 ms") |

**Heat and touch.** Half the power rating is no temperature: an AO3401A (125 K/W) at E-2's 0.45 W runs at 96 °C
at 40 °C ambient. Every part whose entry gives `rth_ja_k_per_w` gets its junction temperature in every scenario,
`ambient_c` + P × Rth(j-a), with P the power of all its elements – a resistor's I²R, a diode's or LED's VF × IF, a
transistor's VCE × IC + VBE × IB, a MOSFET's VDS × ID, its body diode included (ngspice counts it in the drain
current). It is held to the part's `tj_max_c`, at most the criteria's `tj_max_c` (default 125 °C) – the limit of the
LDO and LED driver items of E-3 as well ("junction temperature at 40 °C: 0.0751 W × 125 K/W"). On a board of
`touch_c` the same temperature – the upper bound of the part's surface – is held to the touch limit, for the LDOs and
LED drivers too ("temperature where people touch (board main)"). A P-MOSFET switched off while fresh cells and USB
meet passes every rating with 0.27 W in its body diode and still reaches 74 °C under a hand.

**Operating range and logic levels.** A part whose entry gives its operating supply range – `ratings` `vdd_op_min` /
`vdd_op_max` for its supply pins (the `power_in` pins with the role `vdd` or `vcc`, else all of them), or `v_op: [min,
max]` on a pin – is supplied inside it in every scenario, measured from the pin to the part's own ground pin. An input
pin (type `input`) of a part with thresholds – `vih_v` | `vih_ratio` and `vil_v` | `vil_ratio` on the pin, else in the
part's `params`; a ratio is taken of the voltage at the part's supply pin – sits at ≤ VIL or ≥ VIH ("input level
undefined at OE(ED2)"). A DC scenario drives most outputs low, so the high level of every MCU output on the input's
net (behind 0 Ω bridges too) is held against VIH as well, whatever the load drives: `v_io`, or the supply pin's
voltage with `"vin"` ("output high level reaches VIH of U2 SDI"). These are the recommended operating conditions of
the datasheet, not its absolute maxima (G-3): a 5 V-only LED driver behind a 3.3 V MCU stays inside every absolute
maximum and does not work. A part entry without them gets no item; an MCU's own inputs go by the config's `inputs`.

A reversed LED on a driver output fails as "LED reversed"; a reversed LED elsewhere stays dark where it should light.
That is the polarity check of the graph – for an LED with an expected state. E-4 makes sure every LED has one: an LED
on no driver output in a load without `leds_on` would be skipped, and so would an LED whose parts entry the netlist
cannot read, with neither polarity nor current checked. Both fail E-4 instead. An LED with a pin in nc (the unused
colour of an RGB LED) is not simulated and needs nothing.

An LED counts on the output of a constant-current sink when its cathode is on that output – directly, behind 0 Ω
bridges, or behind one resistor that joins its cathode net to this output and no other: a series resistor that takes
voltage off the driver, or several LEDs in parallel on one channel, each with its balancing resistor. The LEDs on one
output form a group, and the load's `leds_on` does not apply to them: with the channel on, each carries at least
`led_on_min_ratio` (default 0.8) × set current / number of LEDs in the group ("LED current (LED7)"), and min/mean of
the group reaches `chain_min_ratio` (default 0.7; both under `criteria`); with the channel off, each is dark. A cathode
net that reaches two outputs through resistors, and the ground net, count on no output – such an LED goes by
`leds_on`.

## 5.4 Track widths from the simulation

`edakit sim` writes the largest current of a single part per net to `<artifacts>/sim/net_currents.json` (the supply
current also on both supply nets, ground included). `edakit pcb plan` derives net classes from it (IPC-2221 outer layer,
1 oz, 10 K rise, × 1.5) with practical minimum widths from `[net_classes]` of the board file; the gate check L-5 fails a
track below the IPC width and warns below the class width. Its voltage drop is an upper bound, shown as information;
the drop itself the simulation computes once the board is routed and `copper` names the net (5.2).

## 5.5 Every check seen red

The tests in `tests/test_sim.py` build faults into copies of the example (a reversed LED, an overloaded resistor, a
too narrow voltage range, a too weak supply) and expect the matching check to fail. Do the same for checks you add in
a plugin: a check that never failed may not work.
