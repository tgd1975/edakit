# 4 The parts database

One JSON file per part, named by its LCSC number (`hardware/parts/C17414.json`) – or, for a part bought from another
distributor, by its manufacturer part number (`hardware/parts/RC0805FR-0710KL.json`, characters a file name cannot
hold replaced by `_`) – or, for a part nobody sells, such as a board of your own, by the name it was given (4.5). A
component finds its entry by `lcsc`, and without one by `part` = the entry's `mpn`. The entry holds what the
datasheet says, in a form the checks and the simulation can use: pin types and roles, limits, parameters, SPICE
models, lead dimensions, the part's height and its mated plug, and who checked it against which datasheet revision.
Examples: [the Christmas bell's parts](https://github.com/tgd1975/automatic_christmas_bell/tree/main/hardware/parts).

## 4.1 Fields

| Field | Content |
|---|---|
| `lcsc`, `mpn`, `manufacturer` | identification; `lcsc` equals the file name, `mpn` is what a component names in `part` – STRUCT.identity compares them, with the `kind` and the value parameters; with a maker that matches by MPN (Eurocircuits, `[cart]`) `mpn` and `manufacturer` are required for every assembled part (PARTS.fact/mpn) and go into `bom_<board>_mpn.csv` |
| `order` | where a part bought separately is ordered, supplier → order code: `{"rs": "223-0562", "farnell": "…"}`; a value may be `{code, moq, step}` with the supplier's minimum and pack size, `{"lcsc": {"moq": 20, "step": 20}}` (the LCSC code defaults to `lcsc`). The first supplier is the default of `edakit order`; PARTS.supplier warns about a `bom: false` part with neither an LCSC number nor `order` – a `C99…` library number counts as none, LCSC does not sell it |
| `kind` | `resistor`, `capacitor`, `inductor`, `fuse`, `diode`, `led`, `led_rgb`, `npn`, `pnp`, `pmos`, `nmos`, `switch`, `dip_switch`, `button`, `potentiometer`, `battery_holder`, `buzzer`, `relay`, `connector`, `ic`, `module`, `motor`, `solenoid`, `speaker`, `heater`, `optocoupler`, `esd_array` |
| `package`, `footprint` | the footprint name must equal the EasyEDA footprint (SYNC.footprint compares it with the PCB) |
| `footprint_data` | optional: the footprint as data – origin, pads, outline and print in mm –, from which `edakit part build` builds the project's copy and to which SYNC.footprint holds it; an own footprint as text (4.5) |
| `jlc_class` | Basic / Extended Part; PARTS.stock warn when JLCPCB's catalogue lists another class |
| `datasheet` | `url`, `pinout_page`; `edakit part fetch` keeps the PDF beside the project, not in the entry (4.3) |
| `pins` | pin number → `name` (as in the EasyEDA symbol and identical to the graph – SYNC.schematic compares them), `type`, `role` (the meaning; for polarised parts it follows the footprint's polarity print when symbol and footprint disagree), `v_max_v`; from the datasheet where it applies: `strap` (`"high"`/`"low"`: level the pin needs at reset, LVL.boot), `pull` (`"up"`/`"down"`: internal or built-in pull resistor, with `pull_ohm` if known – REQ.missing, LVL.boot), `hint` (a warning from the datasheet, e.g. "ADC2: no analog reads while WiFi is on"); `adc` on a pin that converts (`{"range_v": [0.15, 2.45], "r_source_max_ohm": 10000, "c_hold_min_f": 1e-7}`: the window the converter reads in the attenuation the firmware uses, the source resistance it allows, the hold capacitor that lifts that limit – LIM.range/adc holds a net with `fn: adc` to the window in every scenario, REQ.value/adc the resistors on it, both warnings), `z_in_ohm` (an input's impedance, for the load on an instrument input), `short_proof` (true where a pin may go to a cable without a series resistor – REQ.missing/leave leaves it alone), `clamp` (`"none"` on an output without clamp diodes of its own – the L298's bridges –, `"internal"` where it has them: REQ.missing/clamp asks for a diode to the supply and one from ground where such an output drives a winding or a connector), `windows` (on a configuration pin that reads its setting by voltage: `[{"state": "right", "min_v": 0.825, "max_v": 1.245}, …]`, the windows the datasheet guarantees – between one trip point's maximum and the next one's minimum –, with the pin's `pull` and `pull_ohm` in the operating point: REQ.value/window), `drive` (`"open_drain"` or `"tristate"` on an output that lets go of its line: such outputs share a line without LVL.contention, and a line only they drive needs a pull-up, LVL.undefined/open_drain; `"bridge"` on a motor driver's half-bridge output, driven high or low while enabled: it defines its net like a push-pull output), `biased` (true on an analog input the part holds at its own DC level – an amplifier input at half its supply inside, the PAM8403's INL/INR: a net only a coupling capacitor reaches has its level, no LVL.undefined/analog), `float_ok` (true where the datasheet allows an unused input to float – otherwise an IC input in `nc` is LVL.undefined/nc; `false` on a bidirectional pin the part reads and that must not float – the BME280's SDO choosing its address –, which LEVELS then holds like an input), `needs` (what the pin needs from the circuit, from the datasheet's application section: a list of `{"what": "capacitor", "c_min_f": 1e-6, "c_max_f": 10e-6, "source": "…"}` – `what` one of `capacitor` (to ground), `pull_up` (to a supply), `pull_down` (to ground), `series_resistor` (each with `r_min_ohm`/`r_max_ohm`, a capacitor with `c_min_f`/`c_max_f`, either bound optional), `to_ground`, `never_to_ground`: an ESP32's EN with 10 kΩ and 1 µF, a regulator's output capacitor, USB series resistors, MAX6675 T− on ground and MAX31855 T− never; REQ.missing, REQ.value and REQ.forbidden hold them, grade `pin`, a warning; a need with `when` holds only in that config – a name of the entry's `configs`, a list of names – or, with `"connected"`, only while the pin is in a net: an INA226's ALERT wants its pull-up where it is used, a DS18B20's VDD goes to ground in parasite power, a DS3231's VBAT wants a capacitor as the primary supply); on MCU and module pins `functions` – what the pin-mux table offers, `<peripheral><instance>.<line>`: `["spi0.sck", "uart0.cts", "i2c1.sda", "pwm1.a", "uart0.tx"]`, `adc0`; for PWM the instance is the slice and the line the channel; `[]` = no free function (used on the module), no key = unknown (REQ.function); from the recommended operating conditions: `v_op_min_v`, `v_op_max_v` (a supply pin's range where it differs from the part's `vdd_op_min_v`/`vdd_op_max_v`) and the thresholds of one input pin, `vih_v` or `vih_ratio`, `vil_v` or `vil_ratio`, where they differ from the part's (LVL.threshold); on a serial output (SDO, Q7) of a clocked part: `out_edge` (`"rising"`/`"falling"`: the clock edge after which it changes) and `t_pd_ns` (`[min, max]` clock-to-output delay at the part's supply, `null` where the datasheet gives none) – `edakit check` shows them with HINT.readback |
| `address` | a device on a bus: `{"base": 104, "pins": {"9": 1}, "also": [112], "on": "6"}` – its address with every address pin low, what each pin adds when high (by pin number) – or, for a pin with four states, what it adds tied to each: `{"7": {"low": 0, "high": 1, "sda": 2, "scl": 3}}` (INA219, INA226: A0 on GND, VS, SDA or SCL) –, further addresses it always answers to (a PCA9685's All-Call), the pin whose net is the bus (default: the pin with the role `sda`). Two devices on one bus at one address are REQ.forbidden/address (a warning); a pin the graph does not hold high or low leaves the device out |
| `configs`, `config_default` | the configurations a part runs in, by name – `{"5v": {…}, "3v3": {…}}`, each with `about` and what differs from the entry: `limits` and `values` (a key replaces the entry's, `null` removes it), `pins` (per pin number the keys that differ – `type`, `role`, thresholds, `strap`, `needs`; `null` removes one), `needs` and `address` (replace the entry's, `null` removes them). A component names its config (`"config": "3v3"`, 3.1); without one `config_default` applies, without that the entry as it stands. In the library: CH340C and CH340G at 5 V or 3.3 V (V3 a 100 nF capacitor at 5 V, on VCC at 3.3 V), the CP2102 with its regulator in use or bypassed, the SSD1306 panel C2890596 in I2C (D0 SCL, D1 and D2 SDA, the BS straps) or 4-wire SPI, the DS18B20 powered or in parasite power, the DS3231 with a backup cell, on VBAT alone or without a battery, the HX711 with or without its regulator. `edakit part lint` holds every config to the schema as the entry it makes (`configs.<name>: …`) and every `when` to the configs; a component's config the entry does not know is STRUCT.entry |
| `matrix` | a microcontroller or module whose GPIO matrix routes peripherals to any GPIO: the fn kinds it routes, `["uart", "i2c", "i2s", "pwm", "can"]` (ESP32), from its datasheet's GPIO matrix section. A net's fn of those kinds is then served by any GPIO that can drive it (an input line, `rx`, also by an input-only pin), the nets of one fn_bus need no common instance, and PWM has no fixed slice (REQ.function). Without it only the pins' `functions` count – and only those of microcontrollers and modules: a peripheral's own functions do not answer for the MCU |
| `antenna` | a module with a printed antenna: `{"keepout_mm": [x0, y0, x1, y1]}` – the area around the antenna that stays free of copper, in mm in the footprint's frame (rotation 0, top), taken from the module's datasheet. The gate holds the board's copper on both layers to it where the part sits (GEO.keepout, a warning while new); a radio without it is listed by `edakit check --coverage` |
| `hints` | warnings of the datasheet for the part as a whole; `edakit check` shows them and the pin `hint`s of connected pins |
| `hot_loop` | switching regulators: the pin roles of the loop that carries the pulsed current, from the datasheet's layout section – a buck `["vin", "sw", "gnd"]`, an asynchronous boost `["sw", "gnd"]`; a ground pin without a role is `gnd`. REQ.missing wants a `layout.loops` entry on each of their nets and on the net behind a diode on `sw` |
| `symbol` | optional: the sides of the box `edakit schematic draw` draws for an IC or module – `{"left": [pins], "right": [pins], "top": [pins], "bottom": [pins]}`; without it the pins run as on a DIP package (6.5). With `footprint_data` and its `"symbol": "box"` also the box `edakit part build` draws as the copy's symbol in EasyEDA (4.5) |
| `limits` | what the part withstands or needs, per kind below – the engine LIMITS holds every quantity to them |
| `values` | what the simulation and the calculations read, per kind below; `behavior` for ICs (chapter 5) – `matrix_driver` for a multiplexing LED driver (MAX7219): the LEDs between its segment and digit pins have no DC state, the simulation lists them as information instead of SIM.state or SIM.driver |
| `spice` | `{"model": ".model SS34 D(IS=20u N=1.2 RS=0.04 …)"}` for diodes and transistors |
| `lead` | through-hole parts only: lead cross-section per pad number or `"*"`: `shape` (`square`, `round`, `rect`), `a_mm`, `b_mm`, `tol_mm`, `hole_rec_mm`, `source` – checks GEO.hole (before the layout, on the footprint geometry) and GEO.hole (in the gate, on the drill file); the ring a widened hole leaves: GEO.ring; a footprint with plated holes and no `lead` keeps GEO.hole pending; optional `length_mm`, the lead length below the seating plane – the mechanical model gives its protrusion (7.4) |
| `body` | optional: `{"h_mm": 2.3}`, the height of the body above the board, on the side the part sits on – for the mechanical model (7.4) |
| `mate` | optional, for a connector: its mated plug with the strain relief, `{"box": [x0, y0, x1, y1], "h_mm": 6.5, "exit": "+y"}` – `box` in footprint mm (relative to the part's origin at 0° on TOP, as `pcb dump` measures it), `h_mm` its height above the board, `exit` the direction the cable leaves the box: `+x`, `-x`, `+y`, `-y`, or `+z` (away from the board). `pcb plan` checks it (7.4) |
| `pad_map` | only when pad numbers are deliberately swapped on the placed part: `{PCB pad: library pad}` – check SYNC.footprint |
| `sources` | where every value comes from; "assumption …" marks what must be checked with extra care – also a value taken from a sibling part or the series. The gate protocol lists every source with the word "assumption" (8.2) |
| `compliance` | for the regulatory review (M-6, chapter 15): `rohs` (true, false or the exemption), `reach` (the supplier's SVHC statement), `radio` for a part that transmits – `bands_mhz` (`[[from, to], …]` in MHz: the bands it can transmit in, as datasheet or certificate state them), `max_dbm` (the conducted power at the RF port, as datasheets state it – not the radiated power), `antenna_dbi` (the gain of the antenna it transmits through in the product, from the module's datasheet or certificate), `eirp_dbm` (optional: the e.i.r.p. where a certificate states it), `doc` (URL of the EU declaration of conformity); its e.i.r.p. is `eirp_dbm`, else `max_dbm` + `antenna_dbi`, and LIM.eirp holds it to the limit of the band (3.3) –, or `"none"` for a part that does not transmit: a part of graph type `module` or `microcontroller` states one of the two, else PARTS.fact reports it (information, for a board that is sold a warning); `source` (page and date) |
| `verified` | `null` or the sign-off: `by`, `date`, `datasheet` (revision), `checked` (list), `open` (list: a text, or `{"text": "…", "when": "order"}` – `when` names the phase whose manual check answers it: `order` the assembly preview M-2, `acceptance` the delivered board M-4), optional `datasheet_sha256` (the file signed against, as `edakit part fetch` recorded it), optional `second_check` (the independent M-1 review). The gate protocol lists the open points (8.2) |
| `own` | a part nobody sells (4.5): `what` – `pcb` (a board of an edakit project), `bin` (from your stock, no longer to be had), `handmade`; for `pcb` its source: `project`, `connectors`, `state_sha256` (the board's circuit hash), and in the copy `path`, `commit`, `repo`, `released` – SYNC.source compares them |

**Pin types** (`type`): `passive`, `input`, `output`, `bidirectional`, `power_in`, `power_output`, `ground`, `analog`,
`current_sink`, `no_connect`, `mechanical`. LVL.undefined, LVL.contention, REQ.missing and PATH.unfed work with them: `power_in` needs a capacitor and
a net that a supply reaches, a `ground` pin the ground net, two `output`s on one net are a conflict, an `input` needs a
driver. An MCU pin that can only read (the ESP32's GPIO34–39) is `input`, even with the role `gpio`: the simulation
refuses to drive it (LVL.direction).

**Pin functions** (`functions`) come from the MCU's pin-mux table, not from memory: the example's Pico 2 entry
(`tests/fixtures/led-bar/hardware/parts/C41407547.json`) has them for the RP2350, from the pico-sdk headers it names
in `sources` – any RP2350 module takes the same list per GPIO. On the RP2040 and RP2350 the PWM slice of GPIO n is
(n >> 1) & 7 and the channel `a` for even, `b` for odd n.

**Pin roles** (`role`) tell the code what a pin does, independent of its name:

| kind | roles |
|---|---|
| capacitor | the pin numbers `1`, `2`; a polarized one `plus`, `minus` |
| diode, led | `anode`, `cathode` |
| led_rgb | common cathode: `anode_red`, `anode_green`, `anode_blue`, `cathode`; common anode: `anode`, `cathode_red`, `cathode_green`, `cathode_blue` – a pin with the role `anode` makes it a common anode |
| npn, pnp | `collector`, `base`, `emitter` |
| pmos, nmos | `drain`, `gate`, `source` |
| switch | `common`, `throw_a`, `throw_b` |
| button | `a`, `b` (pins connected inside share a role) |
| dip_switch | `a1`…`aN`, `b1`…`bN` |
| potentiometer | `end_a`, `wiper`, `end_b` |
| battery_holder | `plus`, `minus` (several cells: `plus_a`, `minus_a`, …) |
| buzzer | `plus`, `minus` |
| relay | `coil_plus`, `coil_minus`, `common`, `no`, `nc`; a second contact set (DPDT) `common_2`, `no_2`, `nc_2`, and so on – each set switched by the simulation |
| motor, solenoid, speaker | `plus`, `minus` (a motor's and a solenoid's winding `coil_ohm`, a speaker's `impedance_ohm`: the simulation's resistor; a switched winding needs its flyback diode, REQ.missing) |
| heater | the pin numbers (`value_ohm`: its resistance, LIM.p its power) |
| optocoupler | `anode`, `cathode`, `collector`, `emitter` (`vf_v`, `vf_at_a` of the LED; `ctr_min_ratio`: the transistor passes at least that share of the LED current); a PhotoMOS output `load_a`, `load_b` with `behavior: "photomos"`, `r_on_ohm`, `if_on_a` (the LED current that guarantees on – the datasheet's maximum operate current), `if_off_a` (guaranteed off – its minimum turn-off current), `i_leak_a`, and `limits` `v_load_max_v`, `i_load_max_a` (5.1) |
| esd_array | `io1` … `io8` (each protected line; two pins of one line share the role), `vbus` (the steering rail), `gnd` – `limits.vrwm_max_v` (the rail's stand-off: LIM.v holds the rail to it without margin), `values` `vbr_min_v`, `vf_v`, `vf_at_a`, `c_io_f`; HINT.esd counts the lines on its io pins as guarded |
| connector | free (`pin1`, …); `vbus`/`gnd` for a supply input; `cc1`, `cc2` on a USB-C receptacle (REQ.missing:cc; a module or breakout without these roles: `values.usb_c`) |
| ic, module | as the behaviour model needs them: `vin`, `vout`, `gnd`, `vsys`, `3v3`, `gpio`, `rext`, `out`, `oe_n`, `vdd`; `sda`, `scl` for I2C pins (REQ.missing); on shift registers and LED drivers `sdi`, `sdo` (serial data in and out) and the outputs numbered `out0` … `outN` where their order matters – the simulation reads them as `out`, the firmware contract numbers its channels by them (3.5) |

**Limits and values** per kind – what `edakit part lint` holds an entry to and the engines read; generated from
`edakit/catalog/kinds.toml` (`python -m edakit.catalog.handbook --write`):

<!-- edakit:generated kinds -->
| kind | limits | values |
|---|---|---|
| every kind | `p_max_w`, `rth_ja_k_per_w`, `tj_max_c`, `t_max_c`, `t_min_c` | – |
| `resistor` | `v_max_v` | `value_ohm`, `r_max_ohm`, `tolerance` |
| `potentiometer` | `v_max_v` | `value_ohm`, `tolerance` |
| `capacitor` | `v_max_v`, `vr_max_v`, `i_ripple_a` | `value_f`, `dielectric`, `polarized`, `tolerance`, `dc_bias`, `esr_ohm` |
| `crystal` | – | `f_hz`, `c_load_f` |
| `inductor` | `i_max_a`, `i_sat_a` | `value_h`, `dcr_ohm` |
| `fuse` | `v_max_v`, `i_max_a`, `i_hold_a`, `i_trip_a` | `r_min_ohm`, `r_max_ohm`, `i_hold_vs_temp` |
| `diode` | `vr_max_v`, `if_max_a`, `ifsm_max_a` | `vf_v`, `vf_at_a`, `ir_a`, `ir_at_v` |
| `led` | `vr_max_v`, `if_max_a` | `color`, `vf_typ_v`, `vf_min_v`, `vf_max_v`, `vf_at_a`, `rs_ohm` |
| `led_rgb` | `vr_max_v`, `if_max_a` | `vf_typ_v`, `vf_min_v`, `vf_max_v`, `vf_at_a`, `rs_ohm` |
| `npn` | `vce_max_v`, `veb_max_v`, `ic_max_a` | `hfe_min`, `hfe_max`, `vce_sat_v` |
| `pnp` | `vce_max_v`, `veb_max_v`, `ic_max_a` | `hfe_min`, `hfe_max`, `vce_sat_v` |
| `nmos` | `vds_max_v`, `vgs_max_v`, `id_max_a`, `is_body_max_a` | `vgs_th_v`, `rds_on_max_ohm`, `vsd_v_at_1a` |
| `pmos` | `vds_max_v`, `vgs_max_v`, `id_max_a`, `is_body_max_a` | `vgs_th_v`, `rds_on_max_ohm`, `vsd_v_at_1a` |
| `switch` | `v_max_v`, `i_max_a`, `i_contact_max_a`, `i_switch_max_a` | `r_on_ohm`, `force_n`, `min_load_a` |
| `dip_switch` | `v_max_v`, `i_max_a`, `i_contact_max_a`, `i_switch_max_a` | `r_on_ohm`, `min_load_a` |
| `button` | `v_max_v`, `i_max_a`, `i_contact_max_a`, `i_switch_max_a` | `r_on_ohm`, `force_n`, `min_load_a` |
| `battery_holder` | `i_max_a`, `v_max_v` | `r_contact_ohm` |
| `buzzer` | `v_max_v` | `coil_ohm` |
| `relay` | `v_coil_max_v`, `i_max_a`, `v_max_v`, `i_contact_max_a`, `i_switch_max_a` | `coil_ohm`, `v_operate_v`, `v_release_v`, `r_contact_ohm`, `min_load_a` |
| `connector` | `v_max_v`, `i_max_a`, `i_contact_max_a` | `pitch_mm`, `r_contact_ohm`, `r_source_ohm`, `usb_c` |
| `ic` | `vdd_max_v`, `vdd_op_min_v`, `vdd_op_max_v`, `vin_min_v`, `vin_max_v`, `vout_max_v`, `i_out_max_a`, `vin_rel_max_v`, `i_supply_pin_max_a`, `f_max_hz` | `behavior`, `vout_v`, `dropout_v`, `iq_a`, `efficiency`, `idd_max_a`, `iout_gain`, `iout_accuracy`, `vout_knee_v`, `vrext_v`, `vih_v`, `vil_v`, `vih_ratio`, `vil_ratio`, `first_bit_to`, `vout_swing_v`, `vicm_v`, `r_out_ohm`, `comparator`, `gain_min_ratio`, `f_clock_hz`, `vref_v`, `i_load_min_a`, `prog_v`, `icc_a`, `i_a`, `vdd_shunt_v`, `i_shunt_max_a`, `pd_request_v`, `r_on_ohm`, `vgs_th_v`, `r_on_high_ohm`, `r_on_low_ohm`, `v_headroom_v`, `uvlo_v`, `v_pre_v`, `i_pre_ratio`, `i_term_ratio`, `v_ovp_v`, `v_ovp_release_v`, `v_uvp_v`, `v_uvp_release_v`, `v_ocp_v`, `v_scp_v` |
| `module` | `vdd_op_min_v`, `vdd_op_max_v`, `vin_min_v`, `vin_max_v`, `vsys_min_v`, `vsys_max_v`, `i_out_max_a`, `gpio_v_max_v`, `gpio_i_max_a`, `gpio_i_total_max_a`, `f_max_hz` | `behavior`, `regulator`, `v_io_v`, `vout_v`, `dropout_v`, `efficiency`, `i_core_a`, `i_core_min_a`, `gpio_r_out_ohm`, `iq_a`, `vih_v`, `vil_v`, `vih_ratio`, `vil_ratio`, `usb_c`, `f_clock_hz` |
| `motor` | `v_max_v`, `i_max_a` | `coil_ohm` |
| `solenoid` | `v_max_v`, `i_max_a` | `coil_ohm` |
| `speaker` | `v_max_v` | `impedance_ohm` |
| `heater` | `v_max_v` | `value_ohm` |
| `optocoupler` | `if_max_a`, `vr_max_v`, `vce_max_v`, `ic_max_a`, `v_load_max_v`, `i_load_max_a` | `vf_v`, `vf_at_a`, `ctr_min_ratio`, `behavior`, `r_on_ohm`, `if_on_a`, `if_off_a`, `i_leak_a` |
| `esd_array` | `vrwm_max_v` | `vbr_min_v`, `vf_v`, `vf_at_a`, `c_io_f` |

Per pin: `v_max_v`, `v_op_min_v`, `v_op_max_v`, `vih_v`, `vil_v`, `vih_ratio`, `vil_ratio`, `pull_ohm`, `v_min_v`, `v_rel_max_v`, `v_max_powered_v`, `i_max_a`, `i_inject_max_a`, `r_load_min_ohm`, `c_load_max_f`; and `name`, `type`, `role`, `strap`, `pull`, `hint`, `functions`, `out_edge`, `t_pd_ns`, `needs`, `drive`, `float_ok`, `adc`, `z_in_ohm`, `short_proof`, `clamp`, `windows`, `biased`, `ref`, `rel_ref`. Every name ends in its unit: `_v` V, `_a` A, `_w` W, `_ohm` Ω, `_f` F, `_h` H, `_c` °C, `_hz` Hz, `_dbm` dBm, `_dbi` dBi, `_mm` mm, `_n` N, `_s` s, `_ns` ns, `_k_per_w` K/W, `_ratio` 1. Words: `behavior` ldo, buck, boost, buck_boost, mcu, cc_sink, opamp, logic, current, bridge, charger, protection, pd_sink, pass_gate, photomos, matrix_driver, none; `regulator` ldo, buck, boost, buck_boost, none; `color` red, green, blue, yellow, orange, white, warm_white, amber, uv, ir, rgb; `dielectric` C0G, NP0, X5R, X7R, X7S, X6S, Y5V, electrolytic, polymer, tantalum, film.
<!-- edakit:end -->

A limit named `<quantity>_max_<unit>` or `<quantity>_min_<unit>` is held to the quantity of that name at the part
(LIM.v, LIM.i, LIM.p, LIM.t, LIM.range – chapter 14.2); a limit on a pin (`v_max_v`) comes before the entry's, the
entry's before the default of the pin type. What the names do not say:

- switch, connector, battery holder `i_max_a`: what the part carries as a whole – a USB-C receptacle's two ground
  contacts at 1.25 A each are 2.5 A; fuse `i_hold_a`, `i_trip_a` with `values.i_hold_vs_temp` (`[[°C, A], …]`), which
  LIM.i reads at the lowest ambient of sim.json.
- MCU modules: `gpio_i_max_a` per output pin and `gpio_i_total_max_a` for all outputs together, sourced and sunk
  separately – the package's supply pins; with an on-board LDO (`regulator: "ldo"`) the `rth_ja_k_per_w` and
  `tj_max_c` of that regulator, from its datasheet – LIM.t holds its junction temperature with the core current it
  carries (5.3).
- any IC or module `vdd_op_min_v`, `vdd_op_max_v`: the operating supply range of the recommended operating
  conditions, not the absolute maximum – LIM.range holds every supply pin to it; a supply pin with another range has
  its own `v_op_min_v` / `v_op_max_v`. Own boards (behaviour `current`) `vin_min_v`, `vin_max_v` – the voltage at the
  connector over the board's own simulation (4.5).
- any part that dissipates – resistor, diode, LED, BJT, MOSFET – `rth_ja_k_per_w` (junction to ambient) and
  `tj_max_c`: LIM.t holds ambient + P × Rth(j-a) to the junction limit and, on a board people touch, to `touch_c`
  (5.3); without `rth_ja_k_per_w` the part gets no temperature item.
- a MOSFET used as a switch: `vgs_th_v` (`[min, typ, max]`) and `rds_on_max_ohm` as a table `{"-2.5": 0.085, "-4.5": 0.06}` (VGS → Ω) – LIM.range/gate reports one whose |VGS| lies between its threshold and the lowest VGS its RDS(on) is specified at: a P-MOSFET on 5 V that a 3.3 V output cannot switch off, an IRF520 at 3.3 V.
- a constant-current driver: `limits.i_supply_pin_max_a`, what its ground pin carries – LIM.i/supply_pin holds all its outputs together.
- an MCU: `values.f_clock_hz` and `limits.f_max_hz` as a table by supply voltage (`{"2.7": 10e6, "4.5": 20e6}`) – LIM.range/clock holds the clock to what its supply allows.
- an op-amp that is stable only above a gain: `values.gain_min_ratio` – REQ.value/gain against its closed-loop gain.
- an IC whose pins must not rise above its supply: `limits.vin_rel_max_v`, how far above (e.g. 0.5 V) – LIM.v/inject holds its inputs, bidirectional pins and outputs in every scenario. A pin with a limit of its own gives `v_rel_max_v` – against the pin its `ref` names (`"ref": "VDDIO"`, the BME280's interface pins), else against the part's supply; `null` for a pin rated above its supply (TP4056 CE) –, and where only a resistor feeds it, `i_inject_max_a`: then the current the clamp takes, (V − V_ref − v_rel) / R, is held to that instead of the voltage. `vih_ratio` and `vil_ratio` refer to the same `ref`; where the datasheet refers the maximum to another supply than the thresholds, `rel_ref` names that one (the MPU-6050's AD0: thresholds of VLOGIC, at most VDD + 0.5 V).
- pin limits beyond the voltage: `v_min_v` – the pin's own lower limit (an RS-485 line, −7.5 V) in place of the −0.3 V floor of an active pin; `v_max_powered_v` beside `v_max_v` where a pin takes more only while the part is powered (the RP2350's fault-tolerant GPIOs: 5.5 V powered, `v_max_v` unpowered) – stage G warns with grade powered, each scenario of stage E holds the one that applies; `i_max_a`, the pin's own current, and `i_group_max_a` of the entry, `{group: {pins = [numbers], max = A, dir = "sourced" | "sunk"}}` for a sum (an AVR's ports, whose datasheet sums sourced and sunk currents over different pins; an MCU's sums from its output ammeters) – LIM.i/pin on the operating point where resistors, LEDs and diodes alone are on the pin's net; `r_load_min_ohm` and `c_load_max_f`, what an output may drive (ACS712 VIOUT: 4.7 kΩ, 10 nF) – REQ.value/load on the DC load and the capacitors of its net.
- two supplies in a fixed order: `supply_order`, `[[lower pin, higher pin]]` by pin name (the MPU-6050's VLOGIC ≤ VDD) – LIM.v/order on the declared ranges and in every scenario.
- a polarized capacitor (an electrolytic, a tantalum): `values.polarized: true` and the pin roles `plus` and `minus`; `vr_max_v` the reverse voltage the series allows – LIM.v holds it in the declared ranges and the simulation, and PATH.reverse reports one a reversed source reaches (both grade `polarized`, warnings).
- resistor `value_ohm` `0` is a bridge that joins its nets (3.3); `r_max_ohm` its maximum resistance from the
  datasheet, simulated instead of 0 Ω (50 mΩ without it).
- LED `vf_typ_v`, `vf_min_v`, `vf_max_v`, `vf_at_a`, `rs_ohm` – an RGB LED one set per colour under `red`, `green`,
  `blue`, limits too.
- shift registers and LED drivers `first_bit_to`: the output the first shifted bit ends on, e.g. `"out7"`, from the
  datasheet's timing diagram – copied into the firmware contract (3.5).
- buzzer `coil_ohm`: a magnetic buzzer, a coil for REQ.missing (flyback diode); relay `v_operate_v`, `v_release_v`
  (must-operate and must-release voltage).
- contacts – switch, button, DIP switch, relay, connector: `i_contact_max_a`, what a closed contact carries (a
  connector's current rating per circuit, the JST XH's 3 A at AWG 22); `i_switch_max_a`, what it may break when it
  opens (a switching or electrical-life rating: the DSHP DIP switch's 25 mA at 24 V DC); `i_max_a` where a datasheet
  does not say which. The simulation holds the current through every closed contact to both (LIM.i; the switching
  rating grade `switching`, a warning), a supply's current at a connector shared among the connector's pins on the
  supply's net, and a fuse's hold current to `i_contact_max_a` as to `i_max_a`. `values.min_load_a`, the least
  current a contact needs to close reliably (a relay's "minimum applicable load", the HFD4's 10 µA): the DC through a
  closed contact at least that, and a contact in a signal path (3.1, net `signal`) rated for signal currents –
  `min_load_a` at most 10 µA (REQ.value/min_load, a warning).
- a module or breakout with a USB-C receptacle `usb_c`: `{"cc": "rd_5k1" | "controller" | "none", "source": "…"}` – how
  the board terminates its CC lines, from its schematic (REQ.missing:cc; the RP2350-Zero has 5.1 kΩ on CC1 and CC2,
  the breakout Soldered 333011 has none).
- a linear Li-ion charger: `prog_v`, the constant of its charge-current equation (I = `prog_v` / R_PROG – MCP73831
  1000 V, TP4056 1100 V or 1200 V by maker, read from the datasheet of that maker), its pins `prog` and `bat`, and
  `i_out_max_a`: LIM.i/charge holds the current the PROG resistor programs to the charger and to the cell's
  `i_charge_max_a` – of the cell state a battery holder on its battery pin has in any supply scenario of sim.json.
  With `behavior: "charger"` the simulation charges (5.1): `vout_v` the float voltage, `i_pre_ratio` and `v_pre_v`
  the precondition current (a ratio of the programmed one) below its threshold, `i_term_ratio` the termination
  current, `r_on_ohm` the pass element, `v_headroom_v` the least vin − bat it charges at, `uvlo_v` its start voltage,
  `iq_a` its supply current while charging.
- a bridge driver (`behavior: "bridge"`, DRV8833, TB6612): `r_on_high_ohm` and `r_on_low_ohm`, the on resistance of
  its high and low side (a datasheet that gives only their sum – the TB6612's Vsat(U+L) – split evenly, and say so in
  `verified`), and the pin roles `in1_x`, `in2_x`, `out1_x`, `out2_x`, `pwm_x`, `sense_x` per channel `x`, `vm`, `en`,
  `vcc`.
- a cell protection IC (`behavior: "protection"`, DW01A): `v_ovp_v`, `v_ovp_release_v`, `v_uvp_v`,
  `v_uvp_release_v` (overcharge and overdischarge detection and release), `v_ocp_v` and `v_scp_v` (overcurrent and
  short at VM), `r_out_ohm` (the outputs' resistance), and the pin roles `vdd`, `gnd`, `od`, `oc`, `vm`; its dual
  MOSFET the roles `gate_2`, `source_2` (and `drain_2`) of the second channel.
- a module's on-board regulator `values.regulator`: `ldo`, `buck`, `boost`, `buck_boost` (the Pico's RT6150) or
  `none`.
- an adjustable regulator: `vref_v` and the pin role `adj` or `fb`, with `i_load_min_a` where it needs a minimum load
  (chapter 5.2).
- any IC with logic inputs: the thresholds of the recommended operating conditions, `vih_v` | `vih_ratio` and
  `vil_v` | `vil_ratio` (a ratio of its supply, e.g. 0.7 and 0.3 for VIH 0.7 × VDD), which LVL.threshold holds its
  `input` pins and the MCU outputs that drive them to; ICs further in chapter 5.

**The parts library** (`edakit/parts/`) holds entries of popular parts and of the parts the building blocks use –
resistors, LEDs, the SS14/SS34 diodes, S8050, AO3401A, a USB-C receptacle, a polyfuse, buttons, a JST connector. Each
is written from its datasheet (the source with its revision) and counts once the owner has signed it: `edakit part
sign <key> --by NAME` writes the signature with the entry's SHA-256 into `edakit/parts/signed.toml`, and an entry
changed after its signature is a draft again. `edakit part add` lists the entries, signed or draft; `edakit part add
<key>` copies one into the project's parts folder – `edakit block add` does the same for a block's parts. The copy
names its library version in `library` (`key`, `sha256` of the entry, `signed`, `date`) and belongs to the project
from then on: checked like every entry, signed in the project like every entry. PARTS.library notes a copy whose
library entry has changed since (grade `newer`) – `edakit part add <key> --update` takes the new version over the copy
on purpose and names what changed – and a copy of an unsigned entry (grade `draft`). (Decided 2026-10-31,
rules-at-scale.md decision 8.)

## 4.2 Finding parts

The agent **part-selector** searches in its own context – datasheets and distributor pages do not fill the design
session – at the distributors of `[project] distributors` (default `["lcsc"]`), compares the candidates and writes the
entry of the one it recommends. How to search at each distributor is in its profile,
`skills/part-search/distributors/<name>.md`; a new distributor is a new profile, not a new agent. Which distributor
fits depends on how the board is built: JLCPCB assembles from LCSC's stock, so a part from RS or Farnell is
hand-soldered (`bom: false`), goes to another assembler, or reaches JLCPCB through its Global Sourcing or as a
consigned part (weeks, fees – the user's decision); in EasyEDA it needs the footprint of a part in the same package
(`easyeda_device`).

What an agent can reach (tried in October 2026):

| Distributor | Without a key | With a key in the environment |
|---|---|---|
| LCSC / JLCPCB | `edakit part search` (JLCPCB's catalogue), EasyEDA's device search, the part pages (curl) | – (APIs only on application) |
| Reichelt | search and part pages; stock without a count | – (no API) |
| DigiKey | WebFetch: search by part number leads to the part page; no RoHS/REACH | `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` |
| Mouser | nothing (the denial comes with HTTP 200) | `MOUSER_API_KEY` |
| Farnell | nothing (403) | `ELEMENT14_API_KEY` |
| RS | nothing (403); a web search finds the order number | only from RS's account managers |

Keys belong in the environment of the session, never into the repository. Without a key the agent says what it could
not see – stock from a search snippet is no stock figure.

At LCSC and JLCPCB:

- **`edakit part search "RGB LED 5mm common cathode"`** asks JLCPCB's public parts catalogue – the endpoint of PARTS.stock, no
  login, no EasyEDA, no bridge, no claim. One line per hit: LCSC number, manufacturer part number, manufacturer, class
  (Basic, Extended, preferred), JLCPCB's assembly stock, package, category; `C99…` numbers dropped, Basic first, then
  by stock. `--basic` keeps Basic and preferred parts, `--min-stock N` drops the rest, `--limit N` (25) is the page
  asked of the catalogue, `--json FILE` writes the hits. An LCSC number gives only its exact hit (the search is full
  text: `C2297` also finds MIC2297). Exit 2 when nothing is found, 1 when the catalogue does not answer. Function and
  package words work here, unlike in EasyEDA's search: that one query lists the Kingbright C6751358 and the XINGLIGHT
  C7371894, which took the reference project some 30 searches. **"Not available" only after three routes**, each
  named with its queries: this search, EasyEDA's device search, the manufacturer's series name (the LCSC profile).
- **`edakit part import C2297`** reads exactly that number from EasyEDA's public component data – the endpoint
  easyeda2kicad reads, no key, no EasyEDA, no bridge: manufacturer, manufacturer part number, footprint name,
  Basic/Extended and the symbol's pin numbers and names. Without an entry it writes a new one with these and
  `verified: null` – kind, pin types and roles, values and ratings are for whoever signs it off (4.3). An existing entry
  is never overwritten: the command lists where it differs from the library (exit 2), `--update` fills in only the
  fields it lacks. Either way the symbol goes to `<artifacts>/library/<LCSC>.json` and the footprint to
  `<artifacts>/footprints/<footprint>.json`, in the units and axes of `pcb dump` (mil, y up, rotation 0 on TOP), each
  pad with shape, size and, for a hole, `hole` [w, l] in mm and `plated`. With the symbol cached, STRUCT.entry compares the
  graph with it (3.3); `pcb plan` takes the footprint for a part that is not in the PCB yet (7.4). The endpoint is
  undocumented: an unknown number answers HTTP 200 with `success: false` ("not in the library", exit 1), and after
  some two dozen requests in a few minutes it answered HTTP 403 for a while – import what you need, not the catalogue.
  `C99…` numbers are refused: the library returns them like any part, but nobody sells them.
- `easyeda_schematic_search_device` with the **LCSC number** or the manufacturer part number. It returns footprint,
  manufacturer number, Basic/Extended and the parameter table (`otherProperty`), but **no stock and no price**.
  Free text ("led 5mm red") returns mostly noise; the classification filter has no effect. Series names work
  (e.g. `XL-304`, `KT-0805`, `UNI-ROYAL 0805W8F…`).
- **Exact match only:** the search is full text – take hits whose `supplierId` equals the number.
- `C99…` numbers are user libraries without an orderable part – STRUCT.identity refuses one on a part that goes into the BOM.
- **Stock and price:** `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx` (stock, price breaks,
  parameters). LCSC's own search blocks automated requests (HTTP 403); jlcsearch is too thin for single parts.
- **JLCPCB's assembly stock differs from LCSC's.** `edakit stock` asks JLCPCB's public catalogue
  (`selectSmtComponentList`) and part page (`jlcpcb.com/partdetail/<C…>`) about every assembled part and writes a dated
  snapshot, `hardware/stock.json`: listed, Basic/Extended/preferred, stock, MPN, PCBA type ("Economic and Standard" or
  "Standard Only"), MSL, X-ray, machine or hand soldering, attrition (`lossNumber`), minimum (`leastPatchNumber`) and
  price breaks. Check **PARTS.stock** reads it on every `edakit check`, offline: a part not listed (pre-order only), short of
  stock for `quantity` boards – under Standard PCBA plus the attrition, max(n + attrition, minimum) –, under another
  MPN than its entry, or "Standard Only" on an Economic order (`[release] assembly.pcba`) fails; MSL ≥ 5 (baked for a
  fee and two days), stock within `stock_margin_pct` and another class than `jlc_class` warn; a snapshot older than
  `stock_max_age_days` is pending. `edakit stock --lcsc C…` prints the same for candidates before they are in the
  graph. At the export PARTS.stock asks the catalogue again.
- Report stock as a number with a date. "Few" is not information.

## 4.3 Signing off a part

1. `edakit part fetch <key>` and read `<datasheets>/<key>.pdf` (4.6); note its revision, and its `sha256` from
   `<key>.json` as `verified.datasheet_sha256`.
2. Check pinout and pin names, **polarity at the footprint** (which pad is pin 1, anode, +), package, every value in
   `values` and `limits`, especially the ones marked as assumption.
3. Correct the file, extend `sources`.
4. `verified`: `{"by", "date", "datasheet", "checked": [...], "open": [...]}`.
5. Critical parts (MCU, regulators, drivers, polarised parts, connectors) get an independent second check (M-1) by the
   agent electrical-reviewer in its own session, recorded as `second_check`.

Every change to a parts file changes the circuit hash: sign-offs with scope `circuit` must be renewed (chapter 8).
With `[release] hash_ignore` (8.2) the keys listed there are left out – `sources`, `notes`, `verified` and `datasheet`
are the usual ones –, so recording a review or correcting a source voids nothing; a pin, a rating or a parameter
still does.

## 4.4 Library footprints are not always right

In the reference project the EasyEDA footprint of a 5-mm LED printed "+" next to pad 1, while symbol and datasheet
called pad 1 the cathode. Editing the project's footprint through the API went nowhere (chapter 9.4). The fix was in
the graph: the net of the anode goes to the pad with the "+" print, and the parts entry gives pin 1 the role `anode` –
so every check, the simulation and the firmware pin tables follow automatically. The gate's polarity sheet (one tile
per polarised part: copper, silkscreen, pad numbers, roles, nets) is what makes this visible at a glance. GEO.mark of the
gate finds it on its own: it reads the "+" the footprint draws in the silk Gerber and fails when the nearest pad with a
polarity role is a cathode (8.1).

Library symbols are not always right either – and a schematic is drawn from the symbol, whatever the parts entry
says. Writing the parts library (4.1) from the datasheets on 2026-10-31 turned up six whose EasyEDA symbol differs
from the manufacturer's datasheet: the WS2812B-V5/W (C2874885) numbers DIN 3 like VSS, so a schematic puts the data
input on ground and leaves pad 4 open; the XC6206P332MR-G (C5446) names pin 2 Vin and pin 3 Vout, Torex the other way
round – the regulator fed backwards; the DRV8825PWPR (C81582) numbers its exposed pad 28 like GND and has no pin for
pad 29, the PowerPAD; the Raspberry Pi Pico 2 (C41407547) numbers the test pads TP2–TP6 like pins 2–6 and swaps SWCLK
and SWDIO; the 6N138S-TA1-L (C22451885) names the LED's anode "2" and its cathode "NC"; the AQY212GS (C719745) has
three pins for four pads. `edakit part import` caches the symbol with the numbers it gives twice, and STRUCT.entry
compares it: names and numbers with the graph's pins as before, and – grade `symbol`, an error – a number given to
two pins, a pad of the footprint without a pin, a pin without a pad. Where the parts entry follows the datasheet on
purpose, `symbol_differs` names each such pin with the reason read from the datasheet
(`{"4": "DIN is pin 4 – Worldsemi WS2812B-V5/W V6.1, pin table"}`): the pin is left out of the comparison and a note
(grade `declared`) tells the project that a schematic drawn from that symbol wires it otherwise – check that
schematic against the datasheet pin by pin, or take another part number whose symbol is right. The six are written
up for EasyEDA and LCSC in `upstream/issue-6-easyeda-symbols.md`.

## 4.5 Own parts

Some parts nobody sells: a board of your own plugged onto the main board, a part from the bin that is no longer made,
something made by hand. Nobody wrote a datasheet for them. For a board designed with edakit, its project is the
datasheet – edakit derives the parts entry from it:

1. **In the board's project:** `edakit part datasheet --connector J1` – several connectors: repeat `--connector`, their
   pins are numbered on in that order. It writes `hardware/datasheet/<name>.json`, the parts entry, and `<name>.md`,
   the datasheet to read; the name is the project's unless `--name` gives another. Derived from the board:
   - `pins`: the net on the board is the pin's name. The simulation's source is `power_in` / `vin`, the ground
     `ground` / `gnd`, a rail the board makes `power_output` / `vout`, an I2C line `bidirectional` / `sda` or `scl`;
     any other pin takes the strongest type among the parts on its net (output, bidirectional, current_sink, input,
     analog, else passive). A resistor to a supply or to ground gives `pull` and `pull_ohm` (REQ.missing, LVL.boot count them);
     `v_max_v` is the lowest limit on the net – a pin's `v_max_v`, a capacitor's `v_max_v` / 1.5
   - `values`: behaviour `current`, the largest current from the connector over the board's scenarios (its DC
     scenarios: fault cases with `info` and transient runs are left out)
   - `limits`: `vin_min_v`, `vin_max_v` – the voltage at the connector over those scenarios
   - `compliance`: RoHS, REACH and radio as the board's parts entries state them – `radio` lists their radios, is
     `"none"` when none transmits and every module and microcontroller of the board says `"none"`, and is left out
     while one of them states nothing (PARTS.fact in the project that uses the board)

   The board's simulation must pass, and exactly one of the connectors must be a source of it: the supply the board
   draws from the project that uses it. `edakit part datasheet` without arguments renews every datasheet of the
   project. Commit them – a datasheet belongs to a state of the board, and SYNC.source says when it is older.
2. **In the project that uses the board:** `edakit part own ../board` copies the datasheet into the parts database
   and adds where it comes from: the path, the commit, the repository, and the gate run that released this state of
   the board if there is one and it was neither superseded nor withdrawn (`<reports>/*/fab/manifest.json` of the
   board's project, 8.3). The component names it like a
   part bought elsewhere – `"part": "<name>"`, `"bom": false` (JLCPCB does not have it), the pins as in the entry –
   and gets an `easyeda_device`: a symbol with these pin names and the board's footprint, from your EasyEDA library.
3. **Sign it off** like any part (4.3), against the datasheet at that commit. Copying the same state again keeps the
   sign-off; a changed board needs a new one.

The checks then treat the board like any IC: its pins take part in LIM.v, LVL and REQ, the simulation draws its
current from the supply pin, and LIM.range holds the voltage there inside `vin_min_v` … `vin_max_v` – the board was simulated
only in that range; give its own `sim.json` more if the host needs more. SYNC.source compares the copy with its source:

| Finding | Result |
|---|---|
| the board's project changed after its datasheet | pending – renew it there, copy again |
| copied from uncommitted changes | pending – commit there, copy again |
| the board is not released at the state of its datasheet | warning – release it there and copy again, or accept the warning in the sign-off file (8.2) |
| the board's project is not there (another machine, CI) | note – the copy is not compared |
| a datasheet of this project is older than the project | pending – `edakit part datasheet` |

Not covered: the board's logic levels and timing – its signal pins are typed, not simulated. A board on a cable is no
part of the host's PCB: it goes into the same project as a second board (`cables`, 3.1), or the host's connector gets
its current as an `external` load (5.1).

**Bought boards** – an MCU module, a sensor board, a USB-C breakout – are parts with an entry like any other (kind
`module`, or `connector` for a breakout that only passes lines on), written from the seller's schematic, with
`"bom": false` when JLCPCB does not assemble them. Plugged or soldered onto the board (pin headers, castellated pads)
they are components of that board: the footprint is the header or pad row, the pins are the ones the board brings
out. A USB-C receptacle on such a board is checked by REQ.missing:cc in one of two ways:

- its CC eyes as pins of the entry – a `connector` with the roles `cc1`, `cc2`, or a `module` whose entry says
  `values.usb_c` `{"cc": "none"}`: REQ.missing:cc wants the two 5.1 kΩ on those pins, as parts of the graph;
- its receptacle inside the board, CC lines no pins of the entry (an MCU module with USB-C on board): `values.usb_c`
  says what the board has – `rd_5k1` and `controller` pass, `none` fails.

A bought board on a cable – a breakout in an enclosure wired to the board's power connector – is a board of its own
that nobody makes:

```toml
[boards.usb]                 # Soldered 333011 on the cable W1 to J1 – bought, nobody draws it
title = "USB-C breakout"
bought = true                # no template, schematic, pcb or file: there is nothing to draw (10.1)
```

Its parts are components with `"board": "usb"` and `"bom": false` – the breakout with the eyes it brings out, and what
you solder onto it, such as the two 5.1 kΩ from CC1 and CC2 to GND; STRUCT wants `bom: false` on every one, nobody
assembles them. A cable joins it to your connector (`cables`, 3.1) with the resistance of its wires. The checks and the
simulation see it like any board: REQ.missing:cc the CC eyes, LIM.i the cable's rating, and sim.json's source sits at the
breakout's connector, with the cable in the path (5.1). Nobody draws it: the gate's stages S and L/F leave it out with
an information row each, the manifest, the `fab` hash, the layout hash and so the layout review M-5 cover the made
boards (8.1, 8.2), and the commands that make or read a layout refuse it with one line (`--board usb`) or skip it.
`edakit order` writes no BOM for it and puts its parts into the carts and under its board, marked bought, in
`hand_assembly.md`; `edakit cost` prices no PCB and no assembly for it (8.4).

**Without an edakit project** – a perfboard, an older board, a part from the bin, something made by hand – the user is
the datasheet. The skill `own-part` asks for pins, supply range and current once, has what nobody knows measured, and
writes the entry with `own: {"what": "pcb" | "bin" | "handmade", "notes": …}`: every value with its source ("measured
2026-11-02, multimeter …, all LEDs on: 182 mA"), what is guessed as "assumption …", and the sign-off against those
notes. The checks treat it like the copy of an edakit board; SYNC.source has nothing to compare it with.

### Own footprints as data

A footprint that exists only in EasyEDA – drawn in its editor, or rebuilt there by a script of the project – is not
text: the repository knows its name, `pcb dump` measures what was put there, and nobody can review or diff it. The
parts entry can hold it as data instead, in `footprint_data` beside `footprint`. edakit builds the project's copy from
it (`edakit part build`), holds the copy to it (SYNC.footprint), and a change of the footprint is a line of text. The Christmas
bell's T-Display, rebuilt today by its script `tdisplay_device.py` from the copy of a 2×12 female header, as data:

```json
"footprint": "HDR-TH_24P-P2.54-V-F-R2-C12-S2.54-2",
"footprint_data": {
 "symbol": "box",
 "origin": [0, 0],
 "pads": {
  "1": {"x": 11.43, "y": -13.97, "shape": "RECT", "w": 1.7, "h": 1.7, "hole": [1.1, 1.1]},
  "2": {"x": 11.43, "y": -11.43, "shape": "ELLIPSE", "w": 1.7, "h": 1.7, "hole": [1.1, 1.1]},
  …
  "24": {"x": -11.43, "y": 13.97, "shape": "ELLIPSE", "w": 1.7, "h": 1.7, "hole": [1.1, 1.1]}
 },
 "lines": [{"points": [[-12.83, -30.2], [12.83, -30.2], [12.83, 21.9], [-12.83, 21.9], [-12.83, -30.2]],
            "width": 0.1524},
           {"points": [[-4.6, -29.9], [4.6, -29.9], [4.6, -27.9], [-4.6, -27.9], [-4.6, -29.9]], "width": 0.1524}],
 "texts": [{"text": "USB", "x": 0, "y": -25.8, "size": 1.5, "width": 0.1524},
           {"text": "T-Display", "x": 0, "y": 18.3, "size": 1.5, "width": 0.1524}],
 "outline": [[-12.83, -30.2], [12.83, -30.2], [12.83, 21.9], [-12.83, 21.9]]
}
```

– the right row 1–12, the left row 13–24 at x = −11.43, pitch 2.54 mm, square pads 1 and 13 at the USB end. Lengths in
mm, y up, the footprint seen from the top at 0° – the axes of `pcb dump` (which measures in mil) and of the library
footprints `edakit part import` caches:

| Field | Content |
|---|---|
| `origin` | optional, `[x, y]`: where the footprint's origin lies in these coordinates – the point `[place]` positions and `pcb dump` measures from; default `[0, 0]`. Lets pads be written as a datasheet dimensions them (pin 1 at 0, 0) and the origin put elsewhere |
| `pads` | pad number → `x`, `y`, `shape` (`RECT`, `ELLIPSE`, `OVAL`), `w`, `h`, `rot` (degrees, default 0), `layer` (`TOP`, `BOTTOM`, `MULTI`; default `MULTI` with a hole, `TOP` without), `hole` `[w, l]` (a slot when l > w), `plated` (default true), `mechanical` (true on a pad whose number is no pin of the entry: a mounting pad) – the form `part import` caches pads in, in mm |
| `pads_same_number` | optional: number → every pad of a number used several times (shell legs), as the cache has them; `pads` holds the first |
| `lines` | silkscreen polylines `{points, width}`, closed when the last point is the first; width default 0.15 mm (JLCPCB prints nothing thinner) |
| `texts` | silkscreen texts `{text, x, y, size, width, rot}`, centred on x, y |
| `marks` | polarity marks `{sign, x, y, size, width}`: a `"+"` drawn as two strokes of `size` – as GEO.mark finds a "+" in the silk Gerber (strokes of 0.3 to 2 mm) –, a `"−"` as one |
| `outline` | the body on the component-shape layer, `[[x, y], …]`: the part's extent in EasyEDA |
| `symbol` | `"box"`: the copy's symbol is rebuilt too (below); without it the carrier's symbol stays |

**Why beside `footprint`, not in it.** `footprint` stays the name of the copy in EasyEDA: SYNC.footprint compares it with the PCB,
`part import` writes and compares it, `pcb plan`, GEO.hole and `part diff` find the library footprint by it, and the copy
keeps the carrier's footprint name (the bell's T-Display is still `HDR-TH_24P-…`, decision D-13 there). An object in
its place would break every reader of the name – and every older edakit that reads the entry; beside it, an entry
without `footprint_data` is what it was, and no project changes until it adds the data. The name says which copy, the
data what it looks like.

**The symbol** follows from `pins` and `symbol`, as `edakit schematic draw` draws a box (6.5): every pin of the entry
on the side `symbol` names (the others on the right), 10 units of 10 mil long, its name and number from the entry, the
body as wide as the names need. Nothing is missing for such a box. What the entry does not have is any other drawing:
a diode, an LED or a transistor is a shape `schematic draw` makes up, not data – so `"symbol": "box"` is for modules,
ICs and boards, and for every other part the carrier's symbol stays; its pins must be the entry's (STRUCT.entry against the
library symbol, SYNC.schematic in the gate). The designator prefix (U, J …) and the device's other properties stay the carrier's.
With `"symbol": "box"` STRUCT.entry does not compare the graph with the carrier's library symbol: it is not the copy's.

**The way:**

1. **A library footprint becomes an own one:** `edakit part footprint KEY` shows the footprint as data,
   `--write` puts it into the entry as `footprint_data` (with a line in `sources`); an entry that has the data is
   refused. The source is the dump of a placed part (`<board>.geometry.json`, `--board` picks the board), else the
   library footprint of `edakit part import`. The dump measures places and holes – shapes and sizes only of parts that
   have footprint data, and older dumps not even holes –, so shape and size come from the library footprint where it
   has the pad at the same place; what is still missing, PARTS.footprint names ("pads 1–24: shape missing"), exit 2. Neither the
   dump nor the cache has the print: without `lines`, `texts`, `marks` and `outline` the build keeps the copy's print,
   with any of them the copy's print is exactly the data's.
2. **Change the data** – a pad is a line. The circuit hash changes (the parts file, byte for byte), so M-1, which
   checks polarity at the footprint, is done again (decision 5 of design-as-text), and the layout hash, so a sign-off of
   scope `layout` lapses; the fab hash sees the copper at the next gate run.
3. **Build the copy:** `edakit part build KEY` checks the data (PARTS.footprint) and shows what it would build –
   `24 pads (24 with a hole), 2 lines, 2 texts, outline, symbol: a box with 24 pins`; `--write` builds it in
   EasyEDA, under the claim (`--board` picks the board; default the only made one). The carrier is the device the part
   is placed with – its LCSC number, which for a stand-in is another part's (the bell's T-Display on the female header
   C18722937), or its `easyeda_device` – and must be on the board's template once (`edakit schematic create`): a device
   created through the API cannot be placed in the local client, the copy of a system part can. edakit finds the
   carrier's copies there, opens the footprint copy in its editor, deletes its pads – and, where the data has print,
   the silkscreen, component-shape, marking and pin-soldering layers –, creates the data's, saves and reads the pads
   back; with `"symbol": "box"` the same for the symbol. Then it saves the project. With `[scripts]` the build is
   recorded like an easyeda script: `project-library:<b>` changed, the parts in the PCB and the routing from before it
   (8.6).
4. **Into the PCB:** placed parts keep their old copy (9.4) – delete them in the PCB, `edakit pcb parts --write`,
   `edakit pcb dump` (it measures the pads of parts with footprint data with shape, size, rotation and layer), then
   `edakit check`: SYNC.footprint holds the copy to the data. Then the round as usual, through `route all`.

**Checks** (3.3), only in a project where a parts entry has `footprint_data` – every other project runs the checks it
ran: **PARTS.footprint** the data is complete and consistent – every pad its place, shape and size, a through-hole pad its hole;
every pad a pin of the entry or `mechanical`, every pin a pad; lines, texts, marks and outline well formed; a `"+"`
mark nearest to a pad whose role is anode, plus or vbus, a `"−"` to cathode or minus (GEO.mark's test, on the text); a symbol
box whose sides name pins of the entry, each once. **SYNC.footprint** the copy equals the data – the footprint the dump measured
on the board has the footprint name of the entry and the data's pads: the same numbers, each within 0.02 mm of its
place (SYNC.plan's tolerance; the bell's copy lies 0.0013 mm off), the same hole within 0.01 mm, and where the dump measured
them shape, size, rotation and layer. SYNC.footprint runs on the dump, offline: in every `edakit check`, right after the dump of
a round, where a stale copy is found before anything is routed on it, and in the gate's stage P. Stage L does not
repeat it: there SYNC.footprint holds the PCB's pads to the same dump within 0.05 mm – data = dump in SYNC.footprint, dump = PCB in SYNC.footprint –,
and the PCB export has no holes and shapes, the dump has. The print is not measured by `pcb dump`; the gate sees it on
the silkscreen (GEO.mark, GEO.silk).

Until the dump has the part, `pcb plan`, `pcb place`, GEO.hole and `part diff` take the data as the part's geometry
("footprint data", before the library footprint), so holes and leads are checked on the text already.

Not covered yet: pad shapes NGON and POLYGON (written as RECT, ELLIPSE or OVAL), arcs and circles in the print
(written as points), the direction of a slot (built along the pad's longer side – the live run of step 3.6 has to show
it), and the print in SYNC.footprint. The build runs EasyEDA calls the bell's and the reference project's scripts use, but in this
form it has not run against EasyEDA yet (implementation plan, live run of 3.6).

## 4.6 Datasheets kept with the project

`edakit part fetch <key>` downloads the datasheet of a parts entry once and keeps it – every later reader, the
sign-off, the second check M-1, a review, reads the same file. `edakit part fetch --all` fetches every entry that has
none yet. The sources, in this order:

1. `--url URL`
2. the entry's `datasheet.url`
3. for an LCSC number, `pdfUrl` of LCSC's product data (`https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=…`)
4. `dataManualUrl` of exactly that number in JLCPCB's catalogue (the endpoint of PARTS.stock) – where that is LCSC's datasheet
   page (`www.lcsc.com/datasheet/lcsc_datasheet_<name>.pdf`), the file behind it
   (`wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/<name>.pdf`): the page is a page of the shop since 2026, the file
   sends the browser on to the PDF

A page is followed once, to the part's PDF: where it sends the browser by script or meta refresh (LCSC's file), else
its embedded viewer (the `iframe` of an `item.szlcsc.com` page), else a link whose address or words name the part –
its `mpn` or LCSC number – or say datasheet (the download of a JLCPCB part page). Its other PDF links are named, not
followed: the shop page links nothing but the certificates in its footer, and the first of them was once kept as the
datasheet of a battery holder (chapter 17). Only a complete PDF counts – it starts with `%PDF` and has its `%%EOF` in
the last 64 kB (some tools append metadata after it). A refused request, an HTML page, a download that broke off or an expired signed link is
reported with its reason, and an earlier copy stays as it is ("kept the copy of 2026-10-27", exit 2).

The copy goes to `<datasheets>/<key>.pdf` (`[project] datasheets`, default `<artifacts>/datasheets`: not versioned; a
folder in the repository keeps them with the project) and its record to `<key>.json`: `url` (the source's address),
`pdf_url` (the link a page led to), `source`, `sha256`, `fetched`, `bytes`, `pages`, `text` and `names_mpn`. The
parts entry is not touched – a change there renews the circuit hash and lapses the sign-offs (4.3). A sign-off
records the hash it read as `verified.datasheet_sha256`; a new download with another hash is a warning, "changed
since the sign-off".

With `pdftotext` (poppler-utils) on PATH the text is checked; `edakit doctor` says whether it is there:

| The text | Result |
|---|---|
| names the `mpn` as a whole word (case ignored) | ok, `names_mpn: "yes"` |
| does not name it | note, `"no"` – some vendors never print it (the KT-0805G sheet says only "0805"); compare package, drawing and values |
| names it only inside a longer part number | warning, the variant: `"MT3608L"` for MT3608 – a sheet of another part (pin 6 OC instead of NC) |
| has no text layer (fewer than 20 characters a page) | note, `text: false`: scanned, read the drawings as images (`pdftoppm -r 300 -png`) |
| no pdftotext | note, `text: null` – nothing checked |
