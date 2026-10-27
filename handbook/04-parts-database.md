# 4 The parts database

One JSON file per part, named by its LCSC number (`hardware/parts/C17414.json`) – or, for a part bought from another
distributor, by its manufacturer part number (`hardware/parts/RC0805FR-0710KL.json`, characters a file name cannot
hold replaced by `_`) – or, for a part nobody sells, such as a board of your own, by the name it was given (4.5). A
component finds its entry by `lcsc`, and without one by `part` = the entry's `mpn`. The entry holds what the
datasheet says, in a form the checks and the simulation can use: pin types and roles, limits, parameters, SPICE
models, lead dimensions, and who checked it against which datasheet revision.
Examples: [the Christmas bell's parts](https://github.com/tgd1975/automatic_christmas_bell/tree/main/hardware/parts).

## 4.1 Fields

| Field | Content |
|---|---|
| `lcsc`, `mpn`, `manufacturer` | identification; `lcsc` equals the file name, `mpn` is what a component names in `part` – P-6 compares them, with the `kind` and the value parameters |
| `order` | where a part bought separately is ordered, supplier → order code: `{"rs": "223-0562", "farnell": "…"}`; a value may be `{code, moq, step}` with the supplier's minimum and pack size, `{"lcsc": {"moq": 20, "step": 20}}` (the LCSC code defaults to `lcsc`). The first supplier is the default of `edakit order`; P-5 warns about a `bom: false` part with neither an LCSC number nor `order` |
| `kind` | `resistor`, `capacitor`, `inductor`, `fuse`, `diode`, `led`, `led_rgb`, `npn`, `pnp`, `pmos`, `nmos`, `switch`, `dip_switch`, `button`, `potentiometer`, `battery_holder`, `buzzer`, `relay`, `connector`, `ic`, `module` |
| `package`, `footprint` | the footprint name must equal the EasyEDA footprint (L-4 compares it with the PCB) |
| `jlc_class` | Basic / Extended Part; P-4 and F-2 warn when JLCPCB's catalogue lists another class |
| `datasheet` | `url`, `pinout_page`; `edakit part fetch` keeps the PDF beside the project, not in the entry (4.3) |
| `pins` | pin number → `name` (as in the EasyEDA symbol and identical to the graph – S-2 compares them), `type`, `role` (the meaning; for polarised parts it follows the footprint's polarity print when symbol and footprint disagree), `vmax`; from the datasheet where it applies: `strap` (`"high"`/`"low"`: level the pin needs at reset, G-12), `pull` (`"up"`/`"down"`: internal or built-in pull resistor, with `pull_ohm` if known – G-11, G-12), `hint` (a warning from the datasheet, e.g. "ADC2: no analog reads while WiFi is on"); on MCU and module pins `functions` – what the pin-mux table offers, `<peripheral><instance>.<line>`: `["spi0.sck", "uart0.cts", "i2c1.sda", "pwm1.a", "uart0.tx"]`, `adc0`; for PWM the instance is the slice and the line the channel; `[]` = no free function (used on the module), no key = unknown (G-15); from the recommended operating conditions: `v_op` (`[min, max]` of a supply pin that differs from the part's `vdd_op_min`/`vdd_op_max`) and the thresholds of one input pin, `vih_v` or `vih_ratio`, `vil_v` or `vil_ratio`, where they differ from the part's (E-3); on a serial output (SDO, Q7) of a clocked part: `out_edge` (`"rising"`/`"falling"`: the clock edge after which it changes) and `t_pd_ns` (`[min, max]` clock-to-output delay at the part's supply, `null` where the datasheet gives none) – `edakit hints` shows them with H-9 |
| `hints` | warnings of the datasheet for the part as a whole; `edakit hints` shows them and the pin `hint`s of connected pins |
| `hot_loop` | switching regulators: the pin roles of the loop that carries the pulsed current, from the datasheet's layout section – a buck `["vin", "sw", "gnd"]`, an asynchronous boost `["sw", "gnd"]`; a ground pin without a role is `gnd`. G-18 wants a `layout.loops` entry on each of their nets and on the net behind a diode on `sw` |
| `symbol` | optional: the sides of the box `edakit schematic draw` draws for an IC or module – `{"left": [pins], "right": [pins], "top": [pins], "bottom": [pins]}`; without it the pins run as on a DIP package (6.5) |
| `params` | values for simulation and calculations; `behavior` for ICs (chapter 5) |
| `ratings` | limits for the stress checks |
| `spice` | `{"model": ".model SS34 D(IS=20u N=1.2 RS=0.04 …)"}` for diodes and transistors |
| `lead` | through-hole parts only: lead cross-section per pad number or `"*"`: `shape` (`square`, `round`, `rect`), `a_mm`, `b_mm`, `tol_mm`, `hole_rec_mm`, `source` – checks P-7 (before the layout, on the footprint geometry) and L-9 (in the gate, on the drill file); the ring a widened hole leaves: L-16; a footprint with plated holes and no `lead` keeps P-7 pending |
| `pad_map` | only when pad numbers are deliberately swapped on the placed part: `{PCB pad: library pad}` – check L-10 |
| `sources` | where every value comes from; "assumption …" marks what must be checked with extra care |
| `compliance` | for the regulatory review (M-6, chapter 15): `rohs` (true, false or the exemption), `reach` (the supplier's SVHC statement), `radio` for a part that transmits (`bands_mhz` [[from, to]], `max_dbm`, `doc` = URL of the EU declaration of conformity), `source` (page and date) |
| `verified` | `null` or the sign-off: `by`, `date`, `datasheet` (revision), `checked` (list), `open` (list), optional `datasheet_sha256` (the file signed against, as `edakit part fetch` recorded it), optional `second_check` (the independent M-1 review) |
| `own` | a part nobody sells (4.5): `what` – `pcb` (a board of an edakit project), `bin` (from your stock, no longer to be had), `handmade`; for `pcb` its source: `project`, `connectors`, `state_sha256` (the board's circuit hash), and in the copy `path`, `commit`, `repo`, `released` – P-3 compares them |

**Pin types** (`type`): `passive`, `input`, `output`, `bidirectional`, `power_in`, `power_output`, `ground`, `analog`,
`current_sink`, `no_connect`, `mechanical`. G-4, G-5, G-6 and G-16 work with them: `power_in` needs a capacitor and
a net that a supply reaches, a `ground` pin the ground net, two `output`s on one net are a conflict, an `input` needs a
driver. An MCU pin that can only read (the ESP32's GPIO34–39) is `input`, even with the role `gpio`: the simulation
refuses to drive it (E-3).

**Pin functions** (`functions`) come from the MCU's pin-mux table, not from memory: the example's Pico 2 entry
(`tests/fixtures/led-bar/hardware/parts/C41407547.json`) has them for the RP2350, from the pico-sdk headers it names
in `sources` – any RP2350 module takes the same list per GPIO. On the RP2040 and RP2350 the PWM slice of GPIO n is
(n >> 1) & 7 and the channel `a` for even, `b` for odd n.

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
| connector | free (`pin1`, …); `vbus`/`gnd` for a supply input; `cc1`, `cc2` on a USB-C receptacle (G-14; a module or breakout without these roles: `params.usb_c`) |
| ic, module | as the behaviour model needs them: `vin`, `vout`, `gnd`, `vsys`, `3v3`, `gpio`, `rext`, `out`, `oe_n`, `vdd`; `sda`, `scl` for I2C pins (G-11) |

**Ratings** per kind (what the checks read): resistor `p_max_w`, `v_max`; capacitor `v_max`; diode `if_avg_a`, `vrrm`;
LED `if_max_a`, `vr_max` (per colour for RGB); BJT `ic_max_a`, `vceo`, `vebo`, `p_max_w`; MOSFET `id_max_a`, `vds_max`,
`vgs_max`, `p_max_w`; fuse `i_hold_a`, `i_trip_a` (+ `params.i_hold_vs_temp`: `[[°C, A], …]`, G-17); switch/connector
`i_max_a` (what the part carries as a whole: a USB-C receptacle's two ground contacts at 1.25 A each are 2.5 A),
`v_max`; inductor `i_rated_a`, `i_sat_a`; regulators `vin_min`, `i_out_max_a`, `rth_ja_k_per_w`; MCU modules
`vin_min`/`vsys_min`, `i_out_max_a`, `gpio_i_max_a` (per output pin) and `gpio_i_total_max_a` (all outputs together,
sourced and sunk separately – the package's supply pins); relays `v_coil_max`, `i_max_a` (contacts); LED drivers
`rth_ja_k_per_w`; any IC or module `vdd_op_min`, `vdd_op_max` – the operating supply range of the recommended operating
conditions, not the absolute maximum (E-3 holds every supply pin to it); own boards (behaviour `current`) `vin_min`,
`vin_max` – the voltage at the connector over the board's own simulation (4.5, E-3); any part that dissipates –
resistor, diode, LED, BJT, MOSFET – `rth_ja_k_per_w` (thermal resistance junction to ambient) and `tj_max_c`: E-2 holds
ambient + P × Rth(j-a) to the junction limit and, on a board people touch, to `touch_c` (5.3); without `rth_ja_k_per_w`
the part gets no temperature item.

**Parameters**: resistor `value_ohm` (`0`: a bridge that joins its nets, 3.3), `r_max_ohm` (a bridge's maximum
resistance from the datasheet, simulated instead of 0 Ω; 50 mΩ without it); capacitor `value_f`; inductor `value_h`,
`dcr_ohm`; LED `vf_typ`, `vf_min`, `vf_max`, `vf_at_a`, `rs_ohm` (RGB: one set per colour, under `red`, `green`,
`blue`); switch/button `r_on_ohm`; buzzer `coil_ohm` (a magnetic buzzer; it is a coil for G-13); relay `coil_ohm`,
`v_operate`, `v_release` (must-operate and must-release voltage), `r_contact_ohm`; a module or breakout with a USB-C
receptacle `usb_c`: `{"cc": "rd_5k1" | "controller" | "none", "source": "…"}` – how the board terminates its
CC lines, from its schematic (G-14; the RP2350-Zero has 5.1 kΩ on CC1 and CC2, the breakout Soldered 333011 has
none); ICs see chapter 5 – and for any IC with logic inputs the thresholds of the recommended operating
conditions, `vih_v` | `vih_ratio` and `vil_v` | `vil_ratio` (a ratio of its supply, e.g. 0.7 and 0.3 for VIH 0.7 × VDD),
which E-3 holds its `input` pins and the MCU outputs that drive them to.

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
| LCSC / JLCPCB | `edakit part search` (JLCPCB's catalogue), EasyEDA's device search, the part pages (curl) | – (APIs only on application) |
| Reichelt | search and part pages; stock without a count | – (no API) |
| DigiKey | WebFetch: search by part number leads to the part page; no RoHS/REACH | `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` |
| Mouser | nothing (the denial comes with HTTP 200) | `MOUSER_API_KEY` |
| Farnell | nothing (403) | `ELEMENT14_API_KEY` |
| RS | nothing (403); a web search finds the order number | only from RS's account managers |

Keys belong in the environment of the session, never into the repository. Without a key the agent says what it could
not see – stock from a search snippet is no stock figure.

At LCSC and JLCPCB:

- **`edakit part search "RGB LED 5mm common cathode"`** asks JLCPCB's public parts catalogue – the endpoint of F-2, no
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
  pad with shape, size and, for a hole, `hole` [w, l] in mm and `plated`. With the symbol cached, P-1 compares the
  graph with it (3.3); `pcb plan` takes the footprint for a part that is not in the PCB yet (7.4). The endpoint is
  undocumented: an unknown number answers HTTP 200 with `success: false` ("not in the library", exit 1), and after
  some two dozen requests in a few minutes it answered HTTP 403 for a while – import what you need, not the catalogue.
  `C99…` numbers are refused: the library returns them like any part, but nobody sells them.
- `easyeda_schematic_search_device` with the **LCSC number** or the manufacturer part number. It returns footprint,
  manufacturer number, Basic/Extended and the parameter table (`otherProperty`), but **no stock and no price**.
  Free text ("led 5mm red") returns mostly noise; the classification filter has no effect. Series names work
  (e.g. `XL-304`, `KT-0805`, `UNI-ROYAL 0805W8F…`).
- **Exact match only:** the search is full text – take hits whose `supplierId` equals the number.
- `C99…` numbers are user libraries without an orderable part – P-6 refuses one on a part that goes into the BOM.
- **Stock and price:** `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx` (stock, price breaks,
  parameters). LCSC's own search blocks automated requests (HTTP 403); jlcsearch is too thin for single parts.
- **JLCPCB's assembly stock differs from LCSC's.** `edakit stock` asks JLCPCB's public catalogue
  (`selectSmtComponentList`) and part page (`jlcpcb.com/partdetail/<C…>`) about every assembled part and writes a dated
  snapshot, `hardware/stock.json`: listed, Basic/Extended/preferred, stock, MPN, PCBA type ("Economic and Standard" or
  "Standard Only"), MSL, X-ray, machine or hand soldering, attrition (`lossNumber`), minimum (`leastPatchNumber`) and
  price breaks. Check **P-4** reads it on every `edakit check`, offline: a part not listed (pre-order only), short of
  stock for `quantity` boards – under Standard PCBA plus the attrition, max(n + attrition, minimum) –, under another
  MPN than its entry, or "Standard Only" on an Economic order (`[release] assembly.pcba`) fails; MSL ≥ 5 (baked for a
  fee and two days), stock within `stock_margin_pct` and another class than `jlc_class` warn; a snapshot older than
  `stock_max_age_days` is pending. `edakit stock --lcsc C…` prints the same for candidates before they are in the
  graph. At the export F-2 asks the catalogue again.
- Report stock as a number with a date. "Few" is not information.

## 4.3 Signing off a part

1. `edakit part fetch <key>` and read `<datasheets>/<key>.pdf` (4.6); note its revision, and its `sha256` from
   `<key>.json` as `verified.datasheet_sha256`.
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
per polarised part: copper, silkscreen, pad numbers, roles, nets) is what makes this visible at a glance. L-8 of the
gate finds it on its own: it reads the "+" the footprint draws in the silk Gerber and fails when the nearest pad with a
polarity role is a cathode (8.1).

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
     analog, else passive). A resistor to a supply or to ground gives `pull` and `pull_ohm` (G-11, G-12 count them);
     `vmax` is the lowest limit on the net – a pin's `vmax`, a capacitor's `v_max` / 1.5
   - `params`: behaviour `current`, the largest current from the connector over the board's scenarios
   - `ratings`: `vin_min`, `vin_max` – the voltage at the connector over those scenarios
   - `compliance`: RoHS, REACH and radio as the board's parts entries state them

   The board's simulation must pass, and exactly one of the connectors must be a source of it: the supply the board
   draws from the project that uses it. `edakit part datasheet` without arguments renews every datasheet of the
   project. Commit them – a datasheet belongs to a state of the board, and P-3 says when it is older.
2. **In the project that uses the board:** `edakit part own ../board` copies the datasheet into the parts database
   and adds where it comes from: the path, the commit, the repository, and the gate run that released this state of
   the board if there is one (`<reports>/*/fab/manifest.json` of the board's project). The component names it like a
   part bought elsewhere – `"part": "<name>"`, `"bom": false` (JLCPCB does not have it), the pins as in the entry –
   and gets an `easyeda_device`: a symbol with these pin names and the board's footprint, from your EasyEDA library.
3. **Sign it off** like any part (4.3), against the datasheet at that commit. Copying the same state again keeps the
   sign-off; a changed board needs a new one.

The checks then treat the board like any IC: its pins take part in G-3 to G-6, G-11 and G-12, the simulation draws its
current from the supply pin, and E-3 holds the voltage there inside `vin_min` … `vin_max` – the board was simulated
only in that range; give its own `sim.json` more if the host needs more. P-3 compares the copy with its source:

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
out. A USB-C receptacle on such a board is checked by G-14 in one of two ways:

- its CC eyes as pins of the entry – a `connector` with the roles `cc1`, `cc2`, or a `module` whose entry says
  `params.usb_c` `{"cc": "none"}`: G-14 wants the two 5.1 kΩ on those pins, as parts of the graph;
- its receptacle inside the board, CC lines no pins of the entry (an MCU module with USB-C on board): `params.usb_c`
  says what the board has – `rd_5k1` and `controller` pass, `none` fails.

A bought board on a cable – a breakout in an enclosure wired to the board's power connector – has no place in the
graph yet: every board of `[boards]` is one edakit makes, with schematic, PCB and manufacturing files in the gate.
Its supply goes into sim.json as the source at your connector (5.1), and its CC termination is a question for the
electrical review (M-1) until it is.

**Without an edakit project** – a perfboard, an older board, a part from the bin, something made by hand – the user is
the datasheet. The skill `own-part` asks for pins, supply range and current once, has what nobody knows measured, and
writes the entry with `own: {"what": "pcb" | "bin" | "handmade", "notes": …}`: every value with its source ("measured
2026-11-02, multimeter …, all LEDs on: 182 mA"), what is guessed as "assumption …", and the sign-off against those
notes. The checks treat it like the copy of an edakit board; P-3 has nothing to compare it with.

## 4.6 Datasheets kept with the project

`edakit part fetch <key>` downloads the datasheet of a parts entry once and keeps it – every later reader, the
sign-off, the second check M-1, a review, reads the same file. `edakit part fetch --all` fetches every entry that has
none yet. The sources, in this order:

1. `--url URL`
2. the entry's `datasheet.url`
3. for an LCSC number, `pdfUrl` of LCSC's product data (`https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=…`)
4. `dataManualUrl` of exactly that number in JLCPCB's catalogue (the endpoint of F-2)

An HTML page is searched once for a link to a PDF (the viewer of an `item.szlcsc.com` page, the download of a JLCPCB
part page). Only a complete PDF counts – it starts with `%PDF` and has its `%%EOF` in the last 64 kB (some tools
append metadata after it). A refused request, an HTML page, a download that broke off or an expired signed link is
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
