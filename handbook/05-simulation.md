# 5 Simulation (stage E)

`edakit sim` turns the graph into an ngspice netlist per scenario, computes the DC operating point, and checks every
part against its ratings and the circuit against its function – in seconds, on every commit.

Why DC operating points and not transients: the expensive errors on a small board are static. A resistor that cooks
at full brightness, a regulator without headroom at the low end of the USB voltage, an LED the wrong way round, a
net that reaches a pin with more than it tolerates, a supply that cannot deliver the sum of all loads. A DC sweep over
supply corners × load cases × LED tolerance corners finds those. Transients (inrush, switching spikes) are measured
on the delivered board instead (acceptance test).

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
  its 5V pin, the voltage is USB minus its on-board diode.
- `i_min_a` on a source: the least current the supply needs to stay on – USB power banks switch off below
  50–100 mA after a few seconds. E-3 checks every scenario against it.
- Off-board loads (a servo, a motor, a strip at a connector): the load's `external`, e.g.
  `{"J1": {"plus": "2", "minus": "1", "i_a": 0.3}}` – a constant current between the two pins; it counts for the
  connector's contact current and for the track widths.
- ICs and modules are replaced by **behaviour models** (`params.behavior` in the parts entry):

| Model | Roles | Parameters | Behaviour |
|---|---|---|---|
| `ldo` | `vin`, `vout`, (`gnd`) | `vout_v`, `dropout_v`, `iq_a` | output = min(vout, vin − dropout); input current = output current + iq |
| `buck`, `boost` | `vin`, `vout` | `vout_v`, `efficiency`, `iq_a` | ideal output; input power = output power / efficiency |
| `mcu` | `vsys`/`vin`/`vdd`, optional `vout`/`3v3`, `gpio` | `v_io` (V, or `"vin"` when the I/O runs from the supply pin, as on a 5 V AVR), `i_core_a`, `gpio_r_out_ohm`, `regulator` (`buck`/`ldo`), `vout_v` (regulator output, default `v_io`), `efficiency`, `vih_v`/`vih_ratio`, `vil_v`/`vil_ratio` | on-board regulator feeding the core and external loads; GPIO outputs as sources with output resistance (levels from the load's `gpio`), pull-ups from the config; the config's `inputs` must sit at a defined logic level |
| `cc_sink` | `rext`, `out`, `vdd`, `oe_n` | `vrext_v`, `iout_gain`, `vout_knee_v`, `idd_max_a` | constant-current LED driver (TLC5916, STP08CP05, …): R-EXT held at vrext, every enabled output sinks gain × I(R-EXT) with a soft knee; `oe_n` high = all off; pins of type `output` (SDO to the next driver's SDI or to an MCU input that reads the chain back) low through 50 Ω, as in `logic`; an unconnected SDO stays out of the netlist |
| `logic` | supply pins (`power_in`), outputs | `icc_a` | supply current, outputs low |
| `current` | supply pins | `i_a` | constant supply current |
| `none` | – | – | nothing |

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
cable plugged in, external supply off"; `"info": true` turns failures into information). A load with
`"matrix": false` runs only where an extra scenario names it – fault cases such as a stalled servo, whose result you
want to see and record as a decision, but which must not block every commit. Battery projects add
`"cells": {"fresh": {"v": 1.6, "r": 0.15}, "empty": {"v": 1.0, "r": 0.4}}` and supplies like `{"BT1": "fresh"}`.

## 5.3 Checks

| Check | What |
|---|---|
| E-1 | the operating point converges |
| E-2 | stress of every part against its ratings with derating: resistor power ≤ 50 %, currents ≤ 80 %, capacitor/diode/transistor voltages ≤ 67 %, LED forward current and reverse voltage, fuse hold current at ambient, connector, switch and relay contact current, relay coil voltage, the current of every MCU output (`gpio_i_max_a`) and of all outputs together, sourced and sunk (`gpio_i_total_max_a`) – each pin may be fine and the sum beyond the package |
| E-3 | function: current from every source (≤ `i_max_a`), regulator outputs within tolerance, input above `vin_min`, LDO junction temperature, MCU supply voltage and load on its regulator, MCU inputs at a defined level (≤ VIL or ≥ VIH – a 3.3 V signal into a 5 V AVR is the classic case), MCU outputs only on pins that can drive (an output on an input-only pin is reported and not driven), LED driver output headroom and junction temperature, every LED on or dark as the load says (driver channels: ≥ 80 % of its share of the set current, also for an LED behind 0 Ω bridges or one resistor; parallel LEDs share within a ratio – below the table), relays pull in (`v_operate`) and release (`v_release`) as the load says, diodes that must block (`expect_blocking`), every net inside its declared range `v`, plus the plugin's checks |

A reversed LED on a driver output fails as "LED reversed"; a reversed LED elsewhere stays dark where it should light.
That is the polarity check of the graph.

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
track below the IPC width and warns below the class width.

## 5.5 Every check seen red

The tests in `tests/test_sim.py` build faults into copies of the example (a reversed LED, an overloaded resistor, a
too narrow voltage range, a too weak supply) and expect the matching check to fail. Do the same for checks you add in
a plugin: a check that never failed may not work.
