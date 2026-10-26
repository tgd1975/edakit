# 4 The parts database

One JSON file per part, named by its LCSC number (`hardware/parts/C17414.json`) – or, for a part bought from another
distributor, by its manufacturer part number (`hardware/parts/RC0805FR-0710KL.json`, characters a file name cannot
hold replaced by `_`). A component finds its entry by `lcsc`, and without one by `part` = the entry's `mpn`. The entry
holds what the datasheet says, in a form the checks and the simulation can use: pin types and roles, limits,
parameters, SPICE models, lead dimensions, and who checked it against which datasheet revision.
Examples: [the Christmas bell's parts](https://github.com/tgd1975/automatic_christmas_bell/tree/main/hardware/parts).

## 4.1 Fields

| Field | Content |
|---|---|
| `lcsc`, `mpn`, `manufacturer` | identification; `mpn` is what a component without `lcsc` names in `part` |
| `order` | order numbers at other distributors: `{"rs": "223-0562", "farnell": "…", "mouser": "…", "digikey": "…"}` |
| `kind` | `resistor`, `capacitor`, `inductor`, `fuse`, `diode`, `led`, `led_rgb`, `npn`, `pnp`, `pmos`, `nmos`, `switch`, `dip_switch`, `button`, `potentiometer`, `battery_holder`, `buzzer`, `relay`, `connector`, `ic`, `module` |
| `package`, `footprint` | the footprint name must equal the EasyEDA footprint (L-4 compares it with the PCB) |
| `jlc_class` | Basic / Extended Part |
| `datasheet` | `url`, `pinout_page` |
| `pins` | pin number → `name` (as in the EasyEDA symbol and identical to the graph – S-2 compares them), `type`, `role` (the meaning; for polarised parts it follows the footprint's polarity print when symbol and footprint disagree), `vmax`; from the datasheet where it applies: `strap` (`"high"`/`"low"`: level the pin needs at reset, G-12), `pull` (`"up"`/`"down"`: internal or built-in pull resistor, with `pull_ohm` if known – G-11, G-12), `hint` (a warning from the datasheet, e.g. "ADC2: no analog reads while WiFi is on") |
| `hints` | warnings of the datasheet for the part as a whole; `edakit hints` shows them and the pin `hint`s of connected pins |
| `symbol` | optional: the sides of the box `edakit schematic draw` draws for an IC or module – `{"left": [pins], "right": [pins], "top": [pins], "bottom": [pins]}`; without it the pins run as on a DIP package (6.5) |
| `params` | values for simulation and calculations; `behavior` for ICs (chapter 5) |
| `ratings` | limits for the stress checks |
| `spice` | `{"model": ".model SS34 D(IS=20u N=1.2 RS=0.04 …)"}` for diodes and transistors |
| `lead` | through-hole parts only: lead cross-section per pad number or `"*"`: `shape` (`square`, `round`, `rect`), `a_mm`, `b_mm`, `tol_mm`, `hole_rec_mm`, `source` – check L-9 |
| `pad_map` | only when pad numbers are deliberately swapped on the placed part: `{PCB pad: library pad}` – check L-10 |
| `sources` | where every value comes from; "assumption …" marks what must be checked with extra care |
| `compliance` | for the regulatory review (M-6, chapter 15): `rohs` (true, false or the exemption), `reach` (the supplier's SVHC statement), `radio` for a part that transmits (`bands_mhz` [[from, to]], `max_dbm`, `doc` = URL of the EU declaration of conformity), `source` (page and date) |
| `verified` | `null` or the sign-off: `by`, `date`, `datasheet` (revision), `checked` (list), `open` (list), optional `second_check` (the independent M-1 review) |

**Pin types** (`type`): `passive`, `input`, `output`, `bidirectional`, `power_in`, `power_output`, `ground`, `analog`,
`current_sink`, `no_connect`, `mechanical`. G-4, G-5 and G-6 work with them: `power_in` needs a capacitor, two
`output`s on one net are a conflict, an `input` needs a driver. An MCU pin that can only read (the ESP32's GPIO34–39)
is `input`, even with the role `gpio`: the simulation refuses to drive it (E-3).

**Pin roles** (`role`) tell the code what a pin does, independent of its name:

| kind | roles |
|---|---|
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
| relay | `coil_plus`, `coil_minus`, `common`, `no`, `nc` |
| connector | free (`pin1`, …); `vbus`/`gnd` for a supply input; `cc1`, `cc2` on a USB-C receptacle (G-14) |
| ic, module | as the behaviour model needs them: `vin`, `vout`, `gnd`, `vsys`, `3v3`, `gpio`, `rext`, `out`, `oe_n`, `vdd`; `sda`, `scl` for I2C pins (G-11) |

**Ratings** per kind (what the checks read): resistor `p_max_w`, `v_max`; capacitor `v_max`; diode `if_avg_a`, `vrrm`;
LED `if_max_a`, `vr_max` (per colour for RGB); BJT `ic_max_a`, `vceo`, `vebo`, `p_max_w`; MOSFET `id_max_a`, `vds_max`,
`vgs_max`, `p_max_w`; fuse `i_hold_a` (+ `params.i_hold_vs_temp`); switch/connector `i_max_a`, `v_max`; inductor
`i_rated_a`, `i_sat_a`; regulators `vin_min`, `i_out_max_a`, `rth_ja_k_per_w`; MCU modules `vin_min`/`vsys_min`,
`i_out_max_a`, `gpio_i_max_a` (per output pin) and `gpio_i_total_max_a` (all outputs together, sourced and sunk
separately – the package's supply pins); relays `v_coil_max`, `i_max_a` (contacts); LED drivers `rth_ja_k_per_w`.

**Parameters**: resistor `value_ohm` (`0`: a bridge that joins its nets, 3.3), `r_max_ohm` (a bridge's maximum
resistance from the datasheet, simulated instead of 0 Ω; 50 mΩ without it); capacitor `value_f`; inductor `value_h`,
`dcr_ohm`; LED `vf_typ`, `vf_min`, `vf_max`, `vf_at_a`, `rs_ohm` (RGB: one set per colour, under `red`, `green`,
`blue`); switch/button `r_on_ohm`; buzzer `coil_ohm` (a magnetic buzzer; it is a coil for G-13); relay `coil_ohm`,
`v_operate`, `v_release` (must-operate and must-release voltage), `r_contact_ohm`; ICs see chapter 5.

The block library (`edakit/blocks/parts/`) holds checked entries of the parts the building blocks use – resistors,
LEDs, the SS14/SS34 diodes, S8050, AO3401A, a USB-C receptacle, a polyfuse, buttons, a JST connector – to copy from.

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
| LCSC / JLCPCB | EasyEDA's device search, the part pages (curl) | – (APIs only on application) |
| Reichelt | search and part pages; stock without a count | – (no API) |
| DigiKey | WebFetch: search by part number leads to the part page; no RoHS/REACH | `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` |
| Mouser | nothing (the denial comes with HTTP 200) | `MOUSER_API_KEY` |
| Farnell | nothing (403) | `ELEMENT14_API_KEY` |
| RS | nothing (403); a web search finds the order number | only from RS's account managers |

Keys belong in the environment of the session, never into the repository. Without a key the agent says what it could
not see – stock from a search snippet is no stock figure.

At LCSC and JLCPCB:

- `easyeda_schematic_search_device` with the **LCSC number** or the manufacturer part number. It returns footprint,
  manufacturer number, Basic/Extended and the parameter table (`otherProperty`), but **no stock and no price**.
  Free text ("led 5mm red") returns mostly noise; the classification filter has no effect. Series names work
  (e.g. `XL-304`, `KT-0805`, `UNI-ROYAL 0805W8F…`).
- **Exact match only:** the search is full text – take hits whose `supplierId` equals the number.
- `C99…` numbers are user libraries without an orderable part.
- **Stock and price:** `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx` (stock, price breaks,
  parameters). LCSC's own search blocks automated requests (HTTP 403); jlcsearch is too thin for single parts.
- **JLCPCB's assembly stock differs from LCSC's.** The gate asks JLCPCB's public catalogue
  (`selectSmtComponentList`) for every BOM line and the stock for `quantity` boards (F-2). A part missing there can only
  be pre-ordered.
- Report stock as a number with a date. "Few" is not information.

## 4.3 Signing off a part

1. Open the datasheet (`datasheet.url`), note its revision.
2. Check pinout and pin names, **polarity at the footprint** (which pad is pin 1, anode, +), package, every value in
   `params` and `ratings`, especially the ones marked as assumption.
3. Correct the file, extend `sources`.
4. `verified`: `{"by", "date", "datasheet", "checked": [...], "open": [...]}`.
5. Critical parts (MCU, regulators, drivers, polarised parts, connectors) get an independent second check (M-1) by the
   agent electrical-reviewer in its own session, recorded as `second_check`.

Every change to a parts file changes the circuit hash: sign-offs with scope `circuit` must be renewed (chapter 8).

## 4.4 Library footprints are not always right

In the reference project the EasyEDA footprint of a 5-mm LED printed "+" next to pad 1, while symbol and datasheet
called pad 1 the cathode. Editing the project's footprint through the API went nowhere (chapter 9.4). The fix was in
the graph: the net of the anode goes to the pad with the "+" print, and the parts entry gives pin 1 the role `anode` –
so every check, the simulation and the firmware pin tables follow automatically. The gate's polarity sheet (one tile
per polarised part: copper, silkscreen, pad numbers, roles, nets) is what makes this visible at a glance.
